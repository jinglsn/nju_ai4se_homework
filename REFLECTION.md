# REFLECTION.md — Coding Agent Harness 项目反思

## 一、项目概述

本项目构建了一个面向"测试驱动修复"场景的 Coding Agent Harness，核心等式为 **Agent = LLM + Harness**。Harness 内核从零编码实现，覆盖决策封装、动作/工具、上下文与记忆、治理护栏、反馈闭环、配置六大维度，其中反馈闭环为重点深入维度。技术栈为 Python 3.13 + pytest + FastAPI + keyring + Docker，LLM 对接 njusehub.info 的 glm-5.2 模型。

## 二、架构设计反思

### 2.1 分层架构的演进

设计阶段我采用了分层架构：底层 LLM 抽象 + 工具层，中层护栏 + 反馈闭环 + 记忆，上层 agent 主循环 + CLI 入口 + Web 仪表盘。这个架构在实现过程中被证明是合理的——各层之间通过明确的接口通信，修改一个模块不需要改动其他模块。

有两个关键修正值得一提：
- **架构命名**：在 brainstorming 阶段，我将 `src/core/` 改为 `src/agent_loop/`，`src/guardrails/` 统一为 `src/guardrail/`。命名的准确性直接影响代码的可读性，在冷启动验证中，其他 agent 能仅凭文件名就理解模块职责。
- **记忆层定位**：从"入口层组件"下沉为"全局基础组件"，因为记忆系统被 agent 主循环、CLI、Web 仪表盘三个模块共享，应该作为横切关注点。

### 2.2 LLM 抽象的边界设计

LLM 抽象层只定义了两个 dataclass（`LLMResponse`、`ToolCall`）和一个抽象方法 `chat()`。这个极简设计是有意为之——不引入 Message、Conversation 等高层概念，让 harness 控制对话结构而非 LLM 层。MockLLM 通过预设响应队列实现确定性测试，`call_history` 和 `call_count` 让测试可以验证 LLM 被调用了多少次、传入了什么参数。这种设计使"移除真实 LLM 后能否用确定性测试验证核心机制"这一硬性标准成为可能。

## 三、TDD 实践反思

### 3.1 红-绿-重构的纪律

本项目严格遵循 TDD 流程：每个模块先写失败测试（红色），确认 ImportError 或 AssertionError 后再写最小实现（绿色），最后在测试保护下重构。110 个测试全部通过，所有测试均使用 MockLLM，不依赖网络与真实 LLM。

TDD 带来几个意外收获：
- **测试即文档**：`test_guardrail.py` 中的 15 个测试清晰展示了三级护栏的完整行为，比任何注释都准确地描述了系统预期。
- **重构信心**：在实现 loop.py 时，我多次调整了 `_append_feedback` 和 `_handle_hitl_intercept` 的内部逻辑，每次修改后立即运行测试，3 秒内就知道是否破坏已有功能。
- **边界条件发现**：写测试时被迫思考"如果 LLM 返回 error 怎么办？""如果 tool_calls 为空呢？"这些问题在写实现时容易忽略，但测试强制覆盖。

### 3.2 测试中的实际问题

在实现过程中遇到几个测试相关的实际问题：
- **HITL 测试的 Windows 兼容性**：`signal.alarm` 在 Windows 上不可用，导致 HITL 超时测试失败。最终简化为 `try/except (EOFError, KeyboardInterrupt)`，移除了对 Unix 信号的依赖。
- **`sys.stdin.isatty()` 在 pytest 中返回 False**：HITL 测试需要使用 `patch("sys.stdin.isatty", return_value=True)` 来模拟交互式终端环境。
- **emoji 编码问题**：演示脚本中的 emoji 在 Windows GBK 终端下抛出 `UnicodeEncodeError`，替换为 ASCII 标记 `[PASS]` / `[OK]` / `[FAIL]`。

## 四、反馈闭环深度设计

### 4.1 为什么选择反馈闭环

反馈闭环是本次项目重点深入的维度。选择它的原因有三：第一，它天然契合 TDD 工作流——测试结果是客观的、确定的反馈信号；第二，它可以通过纯代码实现（解析器 + 分类器 + 构建器），不需要任何提示词工程；第三，它是让 agent 从"一次性执行"走向"多轮自我修正"的关键机制。

### 4.2 设计细节

反馈闭环的核心流程是：运行测试 → 解析输出 → 分类失败 → 映射修复策略 → 构建结构化反馈 → 回灌 LLM。

分类器是纯确定性的正则匹配，10 种失败类型各有对应的修复策略：
- SyntaxError → 定位报错行号
- ImportError → 检查包名拼写
- AssertionError → 对比期望值与实际值
- AttributeError → 检查对象类型和属性名
- TypeError → 检查参数类型和数量
- Timeout → 建议优化或增加超时
- NameError → 检查变量/函数名是否已定义
- ValueError → 检查参数值合法性
- UnknownError → 原文回灌，由 LLM 自主分析

### 4.3 回归检测

反馈构建器还实现了回归检测：如果本次测试失败中出现之前没有的失败测试文件，标记为回归。这个机制在冷启动验证后被证明是必要的——agent 在修复一个 bug 时可能引入新的 bug，回归检测让 LLM 及时意识到副作用。

## 五、冷启动验证的收获

冷启动验证是本次项目最关键的客观证据。我使用不同类型的 agent，全新 session，仅凭 SPEC+PLAN 试实现 Task 2（LLM 抽象基类）和 Task 13（反馈解析器 + 分类器），发现了 5 个缺陷：

1. **测试输出解析器只支持 pytest 格式**：修复方案是增加 unittest 格式支持和 fallback 关键词匹配。
2. **失败分类器缺少 NameError 和 ValueError**：从 8 种扩展到 10 种分类。
3. **edit_file 缺少 replace_all 参数**：agent 在修复多处相同错误时效率低下，增加了 `replace_all` 选项。
4. **HITL 在非交互模式下无降级策略**：添加了 `sys.stdin.isatty()` 检查和自动拒绝逻辑。
5. **停机判断中的死循环检测粒度不够**：改进了工具调用历史记录的比较逻辑。

这次验证让我深刻体会到：SPEC 写得再详细，一旦交给另一个 agent 去实现，总会暴露出隐含假设。这些假设在写 SPEC 时习以为常，但对陌生 agent 来说却是缺失信息。

## 六、凭据安全的实际考量

凭据管理使用系统 keyring（Windows Credential Manager），API Key 绝不硬编码、不提交 Git、不写入日志。内存存储模块的 `filter_sensitive()` 函数在写盘前自动过滤 API Key、Token、密码等敏感信息。但在实际使用中，我意识到一个局限：keyring 在 Docker 容器中通常不可用，这意味着容器化部署需要额外的环境变量注入机制。这个限制已在 README 中注明。

## 七、Superpowers 框架的使用体验

Superpowers 七步工作流（brainstorming → writing-plans → using-git-worktrees → subagent-driven-development → TDD → code-review → finishing）在本次项目中发挥了重要作用：

- **brainstorming** 的逐项追问机制避免了设计盲区，特别是"机制是代码还是提示词"这条约束贯穿始终。
- **writing-plans** 产出的 19 任务计划颗粒度足够细，每个 task 2-5 分钟，可独立测试。
- 实际上由于时间限制，subagent-driven-development 和 git-worktrees 没有完全按计划执行——大部分任务由主会话直接完成。但 PLAN 的拆分方式使得即使不使用 subagent，也能保持清晰的实现节奏。

## 八、如果重新来过

三个我会做出不同选择的地方：

1. **更早引入冷启动验证**：应该在 SPEC 完成后立即做冷启动验证，而不是在实现一半时再做。早期暴露的缺陷修复成本更低。
2. **Web 仪表盘的功能边界**：当前 Web 仪表盘是只读的，但 REFLECTION 写到这里时我意识到，如果能通过 Web 触发一次 agent 运行并实时查看日志，演示效果会更好。
3. **Docker 镜像的体积优化**：当前 Dockerfile 使用 `python:3.13-slim` 作为基础镜像，如果改用 `alpine` 版本可以进一步减小镜像体积，但需要处理 Alpine 下的一些兼容性问题。

## 九、核心收获

本项目验证了一个核心命题：**LLM 只负责"决定下一步做什么"，其余都是工程**。我实现了 6 个维度的 harness 内核，其中护栏分级、反馈分类器、死循环检测、敏感信息过滤等机制都是纯代码——它们不需要 LLM 就能工作，可以用 MockLLM 做确定性测试。110 个测试在 1 秒内全部通过，不依赖任何网络请求。

这让我对"AI 辅助软件工程"有了更具体的理解：AI 的价值不在于替代工程实践，而在于放大了工程实践的效果。好的测试、清晰的接口、确定的反馈信号——这些传统软件工程的基石，在 AI 时代变得更加重要，而非更不重要。