# AGENT_LOG.md — Agent 协作日志

## 概述

本项目使用 Claude Code (claude.ai/code) 作为编码智能体，在 Superpowers 框架下完成全部开发工作。日志按时间线记录每次会话的关键操作与产出。

---

## 2026-07-12 · Session 1 · 项目启动与技术选型

**操作**：
- 阅读作业要求，提取 9+ 交付物、六大维度、硬性纪律等关键信息
- 输出作业要求总览与 12 步执行计划，写入 memory 系统
- 安装 Go 1.26.5 和 Rust 1.97.0（备用语言）
- 使用 Superpowers brainstorming 技能启动设计对话

**关键决策**：
- 编程语言：Python 3.13.5
- 重点深入维度：反馈闭环
- 分发方式：Docker
- LLM 供应商：自有平台 njusehub.info

**产出**：memory 系统中的需求文档与执行计划

---

## 2026-07-12 · Session 2 · Brainstorming 完整设计

**操作**：
- 逐项进行 brainstorming：工具集、反馈闭环、护栏、记忆、配置、LLM 抽象、停机、WebUI、部署
- 11 轮关键问答，覆盖所有设计决策点
- 用户主动补充记忆系统完整规范（800+ 字）和配置分层细节
- 架构命名修正：`src/core/` → `src/agent_loop/`，`src/guardrails/` → `src/guardrail/`

**产出**：完整设计共识，为 SPEC.md 提供素材

---

## 2026-07-12 · Session 3 · 生成 SPEC.md

**操作**：
- 使用 Superpowers writing-plans 技能生成完整设计文档
- 11 章内容：问题陈述、6 个用户故事、功能规约、架构图、数据模型、凭据设计、技术选型、领域与机制设计、验收标准、5 个风险

**产出**：`SPEC.md`

---

## 2026-07-12 · Session 4 · 生成 PLAN.md + SPEC_PROCESS.md

**操作**：
- 使用 writing-plans 技能生成 19 任务实现计划
- 每任务标注文件路径、接口依赖、TDD 步骤、验证命令
- 撰写 SPEC_PROCESS.md 记录 brainstorming 过程

**产出**：`PLAN.md`、`SPEC_PROCESS.md`

---

## 2026-07-13 · Session 5 · 冷启动验证

**操作**：
- 使用不同 agent 全新 session 仅凭 SPEC+PLAN 试实现 Task 2 和 Task 13
- 发现 5 个缺陷：测试解析器仅支持 pytest 格式、分类器缺少 NameError/ValueError、edit_file 缺少 replace_all、HITL 非交互模式无降级、停机判断粒度不足
- 全部修复

**产出**：冷启动验证分析、5 处修复 diff

---

## 2026-07-13 · Session 6 · 实现 Phase 1-4（Tasks 1-14）

**操作**：
- 创建项目脚手架（目录结构、requirements.txt、conftest.py）
- 实现 LLM 抽象层（base.py、mock.py、real.py）
- 实现配置层（loader.py、keyring.py）
- 实现记忆系统（store.py、filter.py、retriever.py）
- 实现工具层（registry.py、file_tools.py、search_tools.py、shell_tools.py）
- 实现护栏（classifier.py、sandbox.py、hitl.py）
- 实现反馈闭环（parser.py、classifier.py、builder.py）
- 每个模块严格遵循 TDD：先写测试 → 确认失败 → 写实现 → 确认通过

**测试结果**：87 passed

---

## 2026-07-14 · Session 7 · 实现 Phase 5-6（Tasks 15-19）

**操作**：
- 实现 Agent 主循环（loop.py）：按 PLAN 执行，修复了 LLM error 时缺少 return 和测试预期 call_count 偏差
- 实现 CLI 入口（cli.py）：4 个子命令（run/memory/keyring/config）
- 实现 Web 仪表盘（web/app.py）：HTML 仪表盘 + 2 个 API 端点
- 创建 Dockerfile + setup.py + GitHub Actions CI 配置
- 创建 3 个机制演示脚本
- 修复 Windows GBK 编码不支持 emoji 的问题

**测试结果**：110 passed

---

## 2026-07-14 · Session 8 · 文档与收尾

**操作**：
- 撰写 REFLECTION.md（约 2500 字反思报告）
- 撰写 README.md（安装、运行、配置、安全说明）
- 撰写 AGENT_LOG.md（本文件）
- 创建 .gitignore
- 凭据泄露检查（全部通过）
- Git init + 首次提交

**最终测试结果**：110 passed, 0 failed

---

## Agent 协作统计

| 指标 | 数值 |
|------|------|
| 总会话数 | 8 |
| 文件数（源码 + 测试） | 30+ |
| 单元测试数 | 110 |
| 测试通过率 | 100% |
| 代码行数（不含测试） | ~1200 |
| SPEC 迭代轮数 | 11 |
| 冷启动发现缺陷 | 5 |
| 机制演示脚本 | 3 |

## 关键经验

1. **TDD 纪律**：先写测试后写实现，虽然前期稍慢，但后期重构和调试效率极高
2. **冷启动验证**：SPEC 写完后让另一个 agent 试实现，暴露了 5 个隐含假设缺陷
3. **机制即代码**：所有核心机制（护栏、分类器、停机判断）都是纯代码，不依赖提示词，MockLLM 下 100% 确定性可测
4. **Superpowers 框架**：brainstorming + writing-plans 两步保证了设计完整性和任务可拆分性