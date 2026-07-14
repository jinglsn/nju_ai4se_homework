# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
永远使用中文和我对话
## Project Context

This is the **AI4SE (AI for Software Engineering) 期末项目** — building a **Coding Agent Harness** (A 类).

核心命题：**Agent = LLM + Harness**。自行编码实现 harness 内核，将 LLM 封装为稳定可靠工作的系统。

作业要求详见 `memory/ai4se-final-project-requirements.md`，执行计划详见 `memory/ai4se-final-project-plan.md`。

## User Preference

**遇到任何选型或分歧时必须向用户询问，不可自行决定。**

## Mandatory Constraints

- **Superpowers 框架**：必须使用 https://github.com/obra/superpowers 的七步工作流（brainstorming → writing-plans → using-git-worktrees → subagent-driven-development → TDD → code-review → finishing）
- **TDD 硬性要求**：先红、再绿、再重构，不可先写实现再补测试
- **机制必须是代码，不是提示词**：护栏、反馈闭环等核心机制必须用代码实现，替换为 mock/stub LLM 后能用确定性单元测试验证
- **不可寄生于现成 agent 框架**：不允许使用 LangChain AgentExecutor、AutoGen、CrewAI 等高层循环，必须自己实现 agent 主循环
- **凭据安全**：key 绝不硬编码、不提交 Git、不写入日志/终端 history
- **冷启动验证**：实现前必须用不同类型的 agent 全新 session 仅凭 SPEC+PLAN 验证

## Environment

- **OS**: Windows 11, bash shell (Git Bash)
- **Node.js**: v24.14.0, npm 11.9.0
- **Python**: 3.13.5 (Anaconda), pip 26.0.1
- **Git**: 2.53.0
- **Docker**: 28.4.0, Docker Compose v2.39.4
- **Claude Code**: 2.1.139
- **Go/Rust**: 未安装
- **TypeScript**: 未安装（需 `npm install typescript`）
- **make/GitHub CLI**: 未安装

## Memory System

项目 memory 位于 `C:\Users\吴佳静\.claude\projects\D--nju-3-ai4se\memory\`，包含：
- `ai4se-final-project-requirements.md` — 完整作业要求
- `ai4se-final-project-plan.md` — 12 步执行计划
- `save-important-to-memory.md` — 每次对话提取重要内容写入 memory 的规则
- `MEMORY.md` — 索引

重要决策和进展需持续更新到 memory 系统。