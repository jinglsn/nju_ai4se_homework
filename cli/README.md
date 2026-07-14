# Coding Agent Harness

面向"测试驱动修复"场景的 Coding Agent Harness。核心等式：**Agent = LLM + Harness**。

## 快速开始

### 环境要求

- Python >= 3.13
- Windows / Linux / macOS

### 安装

```bash
git clone https://github.com/jinglsn/nju_ai4se_homework.git
cd ai4se
pip install -r requirements.txt
pip install -e .
```

### 配置 API Key

```bash
# 交互式录入（推荐）
harness keyring set

# 查看状态
harness keyring status

# 清除
harness keyring clear
```

### 运行

```bash
# 在项目目录下运行 agent
harness run "fix the failing tests"

# 管理项目记忆
harness memory list
harness memory set test_command "python -m pytest"
harness memory clear

# 查看当前配置
harness config show
```

### 启动 Web 仪表盘

```bash
python -m uvicorn web.app:app --reload --port 8000
```

浏览器打开 `http://localhost:8000` 查看项目状态。

线上部署: **https://nju-ai4se-homework.onrender.com/**

### 运行测试

```bash
python -m pytest tests/ -v
```

## 项目结构

```
src/
├── agent_loop/    # Agent 主循环 + 停机判断
├── llm/           # LLM 抽象 (base + mock + real)
├── tools/         # 工具注册表 + 6 个工具
├── guardrail/     # 三级护栏 + 沙箱 + HITL
├── feedback/      # 测试解析 + 失败分类 + 反馈构建
├── memory/        # 记忆存储 + 检索 + 敏感信息过滤
└── config/        # 配置加载 + 凭据管理
web/               # FastAPI 仪表盘
demo/              # 机制演示脚本
tests/             # 单元测试 (110 tests)
```

## 核心机制

### 治理护栏（三级）

| 级别 | 行为 | 示例 |
|------|------|------|
| Level 1 | 自动放行 | `pytest`, `grep`, `read_file` |
| Level 2 | 放行但记录 | `write_file`, `pip install` |
| Level 3 | 拦截 + HITL | `rm -rf`, `git push --force`, `DROP TABLE` |

### 反馈闭环（重点深入维度）

`运行测试 → 解析输出 → 分类失败 → 映射修复策略 → 结构化反馈 → 回灌 LLM`

失败分类器支持 10 种类型：SyntaxError, ImportError, AssertionError, AttributeError, TypeError, Timeout, NameError, ValueError, UnknownError

### 停机条件

- `test_passed`: 测试通过
- `max_iterations`: 达到最大轮次
- `llm_stopped`: LLM 主动停止（有文本无工具调用）
- `dead_loop`: 检测到连续重复工具调用

## 凭据安全

- API Key 存储在系统密钥环（Windows Credential Manager / macOS Keychain / Linux Secret Service）
- 绝不硬编码、不提交 Git、不写入日志
- 记忆系统写盘前自动过滤敏感信息（API Key、Token、密码等）

**已知限制**：系统 keyring 在 Docker 容器中不可用，需通过环境变量 `HARNESS_API_KEY` 注入。`get_api_key()` 会优先读 keyring，失败时自动回退到环境变量。

## Docker 部署

```bash
docker build -t harness .
# 凭据通过环境变量注入（容器内 keyring 不可用）
docker run -e HARNESS_API_KEY="your-key" harness run "your task"
# 启动 Web 仪表盘
docker run -e HARNESS_API_KEY="your-key" -p 8000:8000 harness web
```

## 机制演示

```bash
# 演示 ①：护栏拦截危险动作
python demo/test_guardrail_demo.py

# 演示 ②：反馈闭环驱动自我修正
python demo/test_feedback_loop_demo.py

# 演示 ③：失败分类器 10 种类型全覆盖
python demo/test_classifier_demo.py
```

## CI/CD

GitHub Actions 自动运行测试 + Docker 构建，见 `.github/workflows/unit-test.yml`。

## 许可

本项目为南京大学 AI4SE 课程期末项目。