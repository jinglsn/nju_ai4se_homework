# SPEC.md — Coding Agent Harness 设计文档

## 一、问题陈述

### 要解决什么问题

构建一个面向"测试驱动修复"场景的 Coding Agent Harness。核心等式：**Agent = LLM + Harness**。LLM 只负责"决定下一步做什么"，而 harness 负责将 LLM 封装为一台能稳定可靠工作的系统。

### 目标用户

需要在 Python 项目中自动化修复测试失败、执行代码修改的开发者。

### 为什么值得做

当 LLM 能完成大部分编码工作时，工程师的真正价值落在 harness 这层工程上——治理、反馈、上下文、安全、分发。本项目通过从零编码实现一个 harness 内核，回答"一个可靠的系统到底需要哪些工程"。

---

## 二、用户故事

1. **修复失败测试**：作为开发者，我输入 `harness run "fix the failing tests"`，agent 自动运行测试、定位失败原因、修改代码，直到所有测试通过或达到上限。
2. **安全审批**：作为开发者，当 agent 尝试执行 `rm -rf` 等危险命令时，系统拦截并等待我手动确认，防止误操作。
3. **项目记忆复用**：作为开发者，我上次修复同类报错的经验被自动记录，下次遇到类似问题时 agent 更快定位。
4. **配置定制**：作为开发者，我可以在 `.harness/config.json` 中声明测试命令、超时时间、护栏规则，agent 按我的项目约定运行。
5. **凭据安全管理**：作为开发者，首次运行时系统引导我安全录入 API Key，Key 存储在系统密钥环中，不会出现在代码或日志中。
6. **状态可观测**：作为开发者，我可以通过 Web 仪表盘查看 agent 运行状态、历史任务记录和项目记忆摘要。

---

## 三、功能规约

### 3.1 CLI 入口

| 项目 | 说明 |
|------|------|
| 命令 | `harness run "<任务描述>"` |
| 输入 | 自然语言任务描述 |
| 行为 | 启动 agent 主循环，执行任务，输出执行过程 |
| 输出 | 终端实时日志 + 最终结果（成功/失败/超轮次/死循环） |
| 边界条件 | 项目目录下必须有 `.harness/` 目录（首次运行自动创建） |
| 错误处理 | 配置文件非法 JSON → 提示格式错误并退出；LLM 调用失败 → 重试 3 次后报错 |

### 3.2 工具层（6 个工具）

| 工具 | 输入 | 行为 | 输出 | 边界条件 |
|------|------|------|------|----------|
| `read_file` | 文件路径、行号范围(可选) | 读取文件内容 | 文件内容字符串 | 路径越界被沙箱拦截；文件不存在返回错误 |
| `write_file` | 文件路径、内容 | 创建或覆写文件 | 成功/失败 | 路径越界拦截；单文件修改超过配置阈值(默认30%)触发人工确认 |
| `edit_file` | 文件路径、search、replace | 精准替换匹配文本 | 替换成功/未找到匹配 | 仅替换首次匹配；未找到匹配返回错误 |
| `grep` | 正则模式、搜索路径 | 搜索匹配行 | 匹配行列表(含行号) | 路径越界拦截；无匹配返回空列表 |
| `list_dir` | 目录路径 | 列出目录结构 | 文件/子目录列表 | 深度受配置限制(默认3层) |
| `run_shell` | 命令字符串 | 执行 shell 命令 | stdout + stderr + exit_code | 受护栏三级规则管控 |

### 3.3 反馈闭环（重点深入维度）

**流程**：运行测试 → 解析结果 → 分类失败 → 映射修复策略 → 构建结构化反馈 → 回灌 LLM

**失败分类器**（确定性代码，不依赖 LLM）：

| 失败类型 | 判定规则 | 修复策略 |
|----------|----------|----------|
| 语法错误 | `SyntaxError` 或 `IndentationError` | 直接定位行号，提示修复语法 |
| 导入错误 | `ModuleNotFoundError` / `ImportError` | 检查包名拼写或缺失依赖 |
| 断言失败 | `AssertionError`（含 `assert` 行号） | 对比期望值 vs 实际值，分析差异 |
| 属性错误 | `AttributeError` | 检查对象类型和方法名 |
| 类型错误 | `TypeError` | 检查参数类型和数量 |
| 超时 | 命令执行超过配置阈值 | 建议优化或增加超时时间 |
| 引入新失败 | 本次修改前通过、修改后失败的测试 | 标记为回归，回滚风险高 |
| 未知错误 | 不匹配以上分类 | 原文回灌，由 LLM 自主分析 |

**结构化反馈格式**：
```json
{
  "test_result": "FAIL",
  "failures": [
    {
      "type": "AssertionError",
      "file": "test_calc.py",
      "line": 42,
      "message": "assert 5 == 6",
      "expected": "6",
      "actual": "5",
      "strategy": "对比期望值与实际值差异，检查 calc() 函数逻辑"
    }
  ],
  "summary": "1/3 tests failed: test_calc.py::test_add",
  "regression": false
}
```

### 3.4 治理护栏

**三级分级规则**：

| 级别 | 类型 | 行为 | 示例 |
|------|------|------|------|
| 1 | 只读安全 | 自动放行 | `grep`、`list_dir`、`read_file`、`pytest`、`mypy` |
| 2 | 有风险但可逆 | 警告后放行 | `pip install`、`git commit`、文件写入 |
| 3 | 不可逆破坏 | 拦截 + 人工确认 | `rm -rf`、`git push --force`、`DROP TABLE`、`chmod 777` |

**HITL 状态机**：
- 触发 3 级操作 → 暂停主循环 → 通过 CLI 交互等待用户输入（y/n/always）→ 根据选择继续/跳过/永久放行
- "永久放行"写入项目记忆的灰名单

**沙箱路径校验**：所有文件操作都受根路径范围约束，禁止越界访问项目目录外文件。

**敏感信息过滤器**：记忆写入前自动扫描并过滤命中密钥正则模式的内容。

### 3.5 记忆系统

详见用户提供的记忆系统规范（§六），核心要点：

- 静态项目约定 + 动态运行沉淀，存储于 `.harness/project_memory.json`
- 禁止存储完整源码、敏感信息、跨项目内容
- 检索由代码层 `src/memory/retriever.py` 完成，非 LLM 自主控制
- 注入上下文长度硬限制（不超过总 token 15%）
- CLI 命令：`harness memory list/clear/set`

### 3.6 配置系统

**分层**：`~/.harness/global.json`（全局默认）< `.harness/config.json`（项目覆盖）< CLI 参数（运行时覆盖）

**核心配置域**：

| 域 | 配置项 |
|----|--------|
| 安全治理 | 沙箱路径边界、命令三级管控规则、单文件最大修改占比、人工确认触发阈值 |
| 运行控制 | 最大修复迭代轮数(默认10)、命令执行超时(默认120s)、测试/Lint 命令模板 |
| 记忆策略 | 持久化开关、自动写入条件、项目约定识别规则 |
| 工具权限 | 单工具启用/禁用、文件操作范围、目录遍历深度限制 |

### 3.7 凭据安全存储

- API Key 存储在系统密钥环（Windows Credential Manager / macOS Keychain / Linux Secret Service）
- 首次运行：引导用户通过隐藏输入录入 Key
- CLI 命令：`harness keyring status`（不显明文）、`harness keyring set`、`harness keyring clear`
- 威胁模型：进程内存可见、`.env` 明文风险、日志泄露风险，对策为密钥环 + 日志脱敏

---

## 四、非功能性需求

### 性能
- 单次 LLM 调用超时 30s，含重试 3 次
- Shell 命令执行超时可配置，默认 120s
- Mock 单元测试全部在 5s 内完成

### 安全
- **凭据威胁模型**：攻击者获取源代码 → 无法获取 Key（密钥环存储）；攻击者获取进程内存 → 可读取 Key（操作系统级限制，超出本项目范围）；攻击者读取日志 → 已脱敏不显明文
- 护栏拦截所有 3 级危险操作
- 记忆文件禁止存敏感信息（正则过滤）

### 可观测性
- 终端实时输出执行步骤
- Web 仪表盘展示运行状态、历史、记忆摘要
- 审计日志记录所有记忆写入、工具执行、护栏拦截

### 可用性
- 单条命令启动：`harness run "<任务>"`
- 首次运行自动创建 `.harness/` 目录
- 所有 CLI 命令有 `--help` 说明

---

## 五、系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     CLI 入口 (harness run)                │
├─────────────────────────────────────────────────────────┤
│  全局基础层                                              │
│  ┌──────────────┐  ┌──────────────────────────────────┐  │
│  │ 配置层        │  │ 记忆层 (src/memory/)              │  │
│  │ src/config/  │  │ .harness/project_memory.json     │  │
│  │ config.json  │  │ 静态约定 + 动态沉淀 + 审计链路     │  │
│  │ keyring.py   │  │ 敏感信息过滤 + 沙箱路径校验        │  │
│  └──────────────┘  └──────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    Agent 主循环 (src/agent_loop/)         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  读取配置 + 加载记忆 → 组织上下文 → 调用 LLM      │    │
│  │       ↑                              ↓          │    │
│  │  回灌反馈 ← 审计日志写记忆 ← 工具执行 ← 护栏拦截  │    │
│  │       ↓                                         │    │
│  │  停机判断：测试通过/达到上限/LLM主动停止/死循环     │    │
│  │  死循环判定：连续 N 轮报错一致 + 工具调用无变化     │    │
│  └─────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────┤
│  反馈闭环 (src/feedback/)    │  治理护栏 (src/guardrail/) │
│  ┌──────────────────────┐   │  ┌──────────────────────┐  │
│  │ 测试结果解析器        │   │  │ 三级分级拦截器        │  │
│  │ 失败分类器（语法/断言 │   │  │ HITL 状态机           │  │
│  │ /超时/新失败）        │   │  │ 沙箱路径校验          │  │
│  │ 修复策略映射           │   │  │ 敏感信息过滤器        │  │
│  │ 结构化反馈构建器       │   │  └──────────────────────┘  │
│  └──────────────────────┘   │                            │
├─────────────────────────────────────────────────────────┤
│  LLM 抽象层 (src/llm/)      │  工具层 (src/tools/)        │
│  ┌──────────────────────┐   │  ┌──────────────────────┐  │
│  │ RealLLM (自有平台API) │   │  │ read_file / write_file│  │
│  │ MockLLM (测试用)      │   │  │ edit_file / grep      │  │
│  │ LLMResponse (含error) │   │  │ list_dir / run_shell   │  │
│  │ call_history 审计     │   │  │ 执行结果写审计链路     │  │
│  └──────────────────────┘   │  └──────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Web 仪表盘 (web/app.py) — FastAPI，只读状态展示          │
│  部署平台：Render（Docker 模式）                          │
└─────────────────────────────────────────────────────────┘
```

### 数据流

1. 用户输入 `harness run "fix the failing tests"`
2. CLI 入口加载配置 + 项目记忆，将任务和上下文组装为初始 messages
3. 主循环调用 LLM 抽象层，获取决策（工具调用或文本响应）
4. 工具调用 → 护栏拦截检查 → 安全则分发执行 → 执行结果写入审计日志
5. 测试命令执行结果 → 反馈闭环解析/分类 → 构建结构化反馈 → 回灌 LLM
6. 停机判断：测试通过/达到上限/LLM 主动停止/死循环检测
7. 任务结束后，动态沉淀写入项目记忆

### 外部依赖

- LLM 供应商：自有平台 API（HTTP）
- 操作系统密钥环：Windows Credential Manager
- 部署平台：Render（Docker）
- 无其他外部服务依赖

---

## 六、数据模型

### 项目记忆 (`.harness/project_memory.json`)

```json
{
  "project": {
    "name": "my-project",
    "tech_stack": {"language": "python", "test_framework": "pytest"},
    "dirs": {"src": "src/", "tests": "tests/", "protected": ["data/"]}
  },
  "conventions": {
    "test_command": "python -m pytest -v",
    "lint_command": "flake8 src/",
    "timeout": 120
  },
  "fix_history": [
    {
      "error_type": "AssertionError",
      "file": "calc.py",
      "strategy": "修复返回值逻辑",
      "timestamp": "2026-07-14T10:30:00"
    }
  ],
  "graylist_commands": [],
  "audit_log": []
}
```

### LLM 请求/响应

```python
class LLMResponse:
    text: str | None = None
    tool_calls: list[ToolCall] | None = None
    error: str | None = None

class ToolCall:
    name: str
    args: dict[str, Any]
```

### 反馈结构

```python
class FeedbackResult:
    test_result: Literal["PASS", "FAIL", "TIMEOUT", "ERROR"]
    failures: list[FailureInfo]
    summary: str
    regression: bool

class FailureInfo:
    type: str  # 失败分类
    file: str
    line: int | None
    message: str
    expected: str | None
    actual: str | None
    strategy: str  # 修复策略建议
```

---

## 七、凭据与分发设计

### 凭据存储

- 方案：Windows Credential Manager（`keyring` 库）
- 录入：`harness keyring set` → 隐藏输入 → 存入密钥环
- 查看：`harness keyring status` → 显示"已配置/未配置"，不回显明文
- 清除：`harness keyring clear`
- 威胁模型：见 §四 安全部分

### 分发

- 形态：Docker 镜像
- 构建：`docker build -t harness .`
- 运行：`docker run -v $(pwd):/workspace -it harness run "task"`
- 推送：GitHub Container Registry（CI 自动构建）
- 平台：linux/amd64（支持 Windows Docker Desktop）
- Key 配置：通过环境变量或 Docker secrets 注入

---

## 八、技术选型与理由

| 组件 | 选择 | 理由 |
|------|------|------|
| 编程语言 | Python 3.13 | 最熟悉，生态丰富（pytest、keyring、FastAPI） |
| LLM 抽象 | 自定义接口 + 自有平台 API | 作业要求自实现，不可寄生框架 |
| 测试框架 | pytest | Python 标准，模拟真实 coding agent 场景 |
| Web 框架 | FastAPI | 轻量、高性能、Docker 部署简单 |
| 密钥环 | keyring | 跨平台，Windows/macOS/Linux 统一接口 |
| 分发 | Docker | 最通用，与 Render 部署复用 |
| CI | GitHub Actions | 生态好，学生免费，与 Render 联动 |
| 部署 | Render (Docker 模式) | 学生免费，零运维，自动 HTTPS |

---

## 九、领域与机制设计（A 类专属）

### 领域反馈信号

Coding 领域的客观反馈信号：

| 信号 | 类型 | 确定性 |
|------|------|--------|
| 测试结果（pass/fail） | 客观 | 是 |
| 测试失败详情（行号、期望值、实际值） | 客观 | 是 |
| 退出码（0=成功） | 客观 | 是 |
| 命令执行超时 | 客观 | 是 |
| Lint/类型检查警告 | 客观 | 是 |

### 危险动作

- 文件系统破坏：`rm -rf`、`del /f`、格式化磁盘命令
- Git 破坏：`git push --force`、`git reset --hard`
- 数据库破坏：`DROP TABLE`、`DROP DATABASE`
- 权限变更：`chmod 777`、`chown`
- 系统级：`shutdown`、`reboot`、`systemctl stop`

### 重点维度：反馈闭环

选择理由：测试驱动修复场景下，反馈信号（测试结果）是客观、确定、可回灌的，反馈闭环每个环节都能用纯代码实现，8 种失败分类器完全是确定性逻辑，不依赖 LLM 智能，可全部用 mock LLM 做确定性单元测试，完美契合作业判定标准。

### 机制编码实现方式

- 失败分类器：纯 Python 代码，正则匹配 + 结构化解析
- 修复策略映射：分类 → 策略的字典查找
- 结构化反馈构建：JSON 序列化，非 LLM 生成
- 护栏拦截：`guardrail(action) → {allow, warn, block}` 纯函数
- HITL 状态机：有限状态自动机
- 记忆检索：关键词匹配 + 路径匹配，非向量检索
- 配置合并：递归字典合并算法

---

## 十、验收标准

| 功能 | 验收标准 |
|------|----------|
| 主循环 | Mock LLM 下运行 3 轮后正常停机，参数可配 |
| 工具分发 | 6 个工具均可被 LLM 调用并返回正确结果 |
| 反馈闭环 | 注入模拟测试失败 → 分类器正确识别类型 → 策略映射正确 → 结构化反馈回灌 |
| 护栏拦截 | 注入 `rm -rf` 命令 → 被拦截 → CLI 等待确认 |
| 记忆系统 | 创建/读取/更新记忆文件，检索匹配正确，敏感信息过滤 |
| 配置系统 | 全局+项目合并正确，缺失项继承默认值 |
| 凭据安全 | `keyring set` 存入密钥环，`status` 不回显明文 |
| 测试 | `pytest` 一键运行，全部 mock 测试通过，不依赖网络 |
| 机制演示 | ① 护栏拦截 ② 反馈闭环驱动修正 ③ 失败分类器 8 种类型全覆盖 |
| 分发 | `docker build && docker run` 可运行 |
| Web | Render 部署后公网可访问仪表盘 |

---

## 十一、风险与未决问题

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 自有平台 API 兼容性不确定 | LLM 调用可能失败 | 抽象层隔离，Mock LLM 保证核心可测 |
| 失败分类器覆盖不全 | 未知错误类型漏分类 | "未知错误"兜底分类，原文回灌 |
| Mock LLM 响应预设太理想化 | 测试可能偏离真实行为 | 补充真实 LLM 集成测试（非必跑） |
| keyring 库在 Windows 的兼容性 | 凭据存储可能出问题 | 备选方案：加密文件 + 主密码 |
| Docker 构建在 Windows 的路径问题 | 容器化可能遇到坑 | 使用 WSL2 后端 |