# 《漆问》执行任务与里程碑

> `QIWEN《漆问》.md` 是最高优先级。本文把 MASTER SPEC 的 Milestone 转换为可验证任务，不改变其顺序或范围。用户已于 2026-08-10 连续授权完成剩余规范；后续里程碑连续执行，不再等待阶段间口令。

## 当前状态

| Milestone | 名称 | 状态 | 进入条件 |
|---|---|---|---|
| 0 | Research & Architecture | **Completed and decisions confirmed 2026-08-10** | 已阅读 MASTER SPEC |
| 1 | UI + Full Mock Workflow | **Completed 2026-08-10** | 用户已明确授权并完成验收 |
| 2 | Database + Persistence | **Completed 2026-08-10** | 用户已明确授权并完成验收 |
| 3 | DeepSeek Agent | **Completed 2026-08-10** | M2 测试通过且用户连续授权 |
| 4 | Asset Providers | **Completed 2026-08-10** | M3 测试通过 |
| 5 | Unity Minimum Vertical Slice | **Completed 2026-08-10** | M4 三类 Provider 独立验收通过 |
| 6 | Unity Build Monitor | **Completed 2026-08-10** | M5 真实 Play Mode 验收通过 |
| 7 | Game Templates | **Completed 2026-08-10** | M6 真实事件监控验收通过 |
| 8 | Human–Agent Unity Co-Creation | **Completed 2026-08-10** | M7 五类模板验收通过 |
| 9 | Playtest & Revision | **Completed 2026-08-10** | M8 共创审批/撤销闭环验收通过 |
| 10 | Research Logging | **Completed 2026-08-10** | M9 完整试玩修订闭环验收通过 |
| 11 | Polish | **Completed 2026-08-10** | M10 匿名研究导出验收通过 |

## MILESTONE 0 — Research & Architecture

### 已完成

- [x] 完整阅读 `QIWEN《漆问》.md`，将其设为 MASTER SPEC。
- [x] 检查 `E:\漆vr游戏`，确认已有图片、SVG、DOCX、PPTX、音频、视频、FBX、ZIP 与可能的 Unity 项目目录；未删除、移动、改写任何用户文件。
- [x] 源码级研究最低九个指定 GitHub 项目，而非只读 README。
- [x] 补查 Unity 官方 MCP、Unity AI、Unity CLI/Pipeline、MCP SDK、OpenAI Codex 和额外 Unity MCP/CLI 实现。
- [x] 核对 DeepSeek V4 当前模型、Chat Completions、tool calls、schema 风险、限额与价格结构。
- [x] 研究 Web/Local Bridge、Editor 本地控制、Provider Architecture、图像/3D/音乐 API。
- [x] 决定性建议：Unity adapter、DeepSeek backend adapter、Mock/Real provider、PostgreSQL/pgvector、object storage、显式 state machine。
- [x] 输出 `RESEARCH_NOTES.md`、`ARCHITECTURE.md`、`TECH_DECISIONS.md`、`RISKS.md`、`TASKS.md`。
- [x] 未创建产品代码、Unity 工程或 Milestone 1 骨架。

### M0 Exit Review

- [x] 确认 Unity 6.3 LTS。
- [x] 确认官方 Unity MCP preferred + Coplay fallback + Mock；当前无官方 entitlement，MVP 默认 Coplay。
- [x] 确认 Local Bridge 使用 Node 24/TypeScript 独立进程。
- [x] 确认 API 全局月预算 30 元、不设单项目预算、预计超额时暂停并提示用户选择。
- [x] 确认首批真实 Provider：即梦 AI 图片、Hunyuan3D、Tencent MPS 音乐。
- [x] 确认现有 E 盘素材作为 curated demo candidates；未核验权利前仅限内部演示，原文件不覆盖。
- [x] 确认推荐项目目录方向和现有素材导入策略。
- [x] 用户明确授权开始 `MILESTONE 1`。

**STOP GATE：以上最后一项未完成前，不得开始 MILESTONE 1。**

## MILESTONE 1 — UI + Full Mock Workflow

> MASTER SPEC 要求本里程碑完全不使用真实 AI，并完整走通 Knowledge → Select → Player Idea → Mock Agent → Concept → Approve → Visual → Approve → 3D → Approve → Music → Approve → Logic → Approve → Ready to Build。

### 已完成任务

- [x] 建立 monorepo、基础 lint/typecheck/test/build 与环境示例；不写真实 key。
- [x] 建立设计 tokens、最小组件与 desktop-first shell；先完成信息结构，不投入大量动画。
- [x] 实现 Knowledge 探索、选择和 Game Affordance 展示。
- [x] 实现 Player Idea 输入与单一 Co-Creator UI。
- [x] 实现 deterministic Mock Agent 与 Mock Image/3D/Music fixtures。
- [x] 实现 Concept、Visual、3D、Music、Logic 每阶段候选、修改/重新生成、拒绝建议、批准。
- [x] 实现服务端/内存原型的 Approval Gate 与可只读回看的 stage navigation，不能只禁用按钮。
- [x] 实现 Asset Library、Progress 和 Ready to Build 页面。
- [x] 图片、GLB、音乐可真实预览；无 key/无 Unity 可演示。
- [x] API 自动测试覆盖完整 happy path 与越级 Gate；运行时检查覆盖刷新前端状态恢复。完整浏览器 E2E 自动化留待后续测试基建。

### Exit Criteria

- [x] 从新项目到 Ready to Build 全流程不使用外部 AI/API。
- [x] 任一阶段不可越过 approval；已批准阶段只读，不能从回看模式修改或重复批准。
- [x] 演示 fixture 可重复、包含 provider/provenance；连接失败有错误与重试 UI。
- [x] Run、测试、检查、修复、重测、生成 `MILESTONE_REPORT.md` 后等待确认。

## MILESTONE 2 — Database + Persistence

### 已完成任务

- [x] PostgreSQL 18.4、Alembic migration、seed、备份/恢复基线。
- [x] Projects、Knowledge、Chat、Assets、Versions、Approvals、Progress、Activity Log 全部持久化。
- [x] Artifact version 与 approval history 不可变；修订号用于并发保护。
- [x] Provider jobs、domain events、transactional outbox 和对象 hash/metadata。
- [x] 浏览器刷新、API 与 PostgreSQL 全部关闭、重新打开后完整项目恢复。
- [x] 并发审批、事务回滚、migration upgrade/downgrade 测试。

### Exit Criteria

- [x] MASTER SPEC 指定持久化对象全部恢复，二进制 hash/引用一致。
- [x] 同一 mutation key 重放不会重复写入 outbox、artifact 或 activity。
- [x] 生成里程碑报告并等待确认。

## MILESTONE 3 — DeepSeek Agent

### 已完成任务

- [x] `LLMProvider` contract + `MockLLMProvider` 同构契约与测试。
- [x] `DeepSeekLLMProvider`：后端 secret、SSE、超时、429/5xx 有界重试、usage/cost logging。
- [x] Pro/Flash ModelRouter 与环境变量集中配置。
- [x] 系统持久化并逐轮重放 conversation history，不依赖 API 自动记忆。
- [x] Stage-aware Knowledge Context、System Prompt、Game Design Agent、Structured Game Concept、Knowledge Alignment、Logic Specification。
- [x] Pydantic/JSON schema validation、一次有限 repair、代码输出仅为 proposal。
- [x] Prompt/schema 版本、结构化建议决策记录与 Mock fallback。

### Exit Criteria

- [x] 多轮对话在重启后恢复；每个概念有知识映射、解释与结构 payload。
- [x] key 不进入 browser、Bridge、Unity、日志或 artifact。
- [x] 无 key 时完整 Mock 流程仍工作。
- [x] 生成里程碑报告；用户已预授权继续 M4。

## MILESTONE 4 — Asset Providers

### 顺序（严格）

1. Image
2. 3D
3. Music

每个 Provider 独立完成：

- [x] Mock/real 契约一致。
- [x] validate、submit、poll、cancel、timeout 和 ingest；供应商错误明确返回且不假装成功。
- [x] 下载远端结果、SHA-256/MIME/尺寸/时长/GLB mesh 验证、provenance、许可字段。
- [x] 候选版本不覆盖、重新生成保留旧版、Approval Gate 不变。
- [x] 无 API key 自动 Demo Generation Mode。
- [x] SDK/HTTP contract tests、资产摄取集成测试与全局成本监控。

Provider 实现顺序仍遵循 MASTER SPEC：Image（即梦 AI 企业 API）→ 3D（Hunyuan3D）→ Music（Tencent MPS）。3D 内部顺序为基础文/图生 3D → GLB ingest → Unity/Web 双检 → 按需减面/UV/rig；Tripo 只在另行批准后接入。

### Exit Criteria

- [x] Image、3D、Music 分别独立契约测试；顺序为 Image → 3D → Music。
- [x] 真实远端结果先摄取至 E 盘 content-addressed storage，项目不依赖临时 URL。
- [x] 生成里程碑报告；用户已预授权继续 M5。

## MILESTONE 5 — Unity Minimum Vertical Slice

### 已完成任务

- [x] M5 前 spike：Unity 6.3.18f1、官方 MCP entitlement/连接失败路径、Coplay fallback、custom tool schema。
- [x] Local Bridge pairing、loopback security、Unity identity、capability probe。
- [x] 点击 `BUILD IN UNITY` 后连接可见 Unity。
- [x] 打开/创建 Project，创建 Scene。
- [x] 从已批准 artifact 导入一个 GLB 和一个 Audio。
- [x] 创建 GameObject，生成一个受限 C# script，挂载。
- [x] 真实 Compile、读 Console、进入 Play Mode。
- [x] 每步 action receipt、失败恢复和人工停止；幂等重试继续在 M6 加固。

### Exit Criteria

- [x] MASTER SPEC 的单一 vertical slice 从按钮到 Play Mode 完全成功且可重复。
- [x] 官方 MCP 和 fallback 至少各完成 capability/失败测试；产品不会误连其他 Unity 工程。
- [x] 只有该链完全成功才进入 M6。

## MILESTONE 6 — Unity Build Monitor

- [x] connection status、action status、progress、console、error、retry、human takeover。
- [x] SSE event replay；断线后不重复动作。
- [x] 编译/Domain Reload 期间明确状态。
- [x] 最多 3 轮修复；error fingerprint；generated-area diff。
- [x] Web 实时看到 Unity 正在做什么及其证据。
- [x] 生成里程碑报告；用户已连续授权进入 M7。

## MILESTONE 7 — Game Templates

按顺序逐个实现，不并行铺开：

1. [x] Simulation + test demo
2. [x] Timing + test demo
3. [x] Collection + test demo
4. [x] Puzzle + test demo
5. [x] Simple Target/Shooting + test demo

每个模板需：schema、prefab/component 映射、输入与胜负条件、EditMode/PlayMode tests、build receipt、文化 affordance 示例、错误 fixture。每完成一个先运行/汇报，再开始下一个。

## MILESTONE 8 — Human–Agent Unity Co-Creation

- [x] 玩家选择 Asset、加入 Scene、调整 Asset、请求交互。
- [x] Agent 提议添加组件、写/改 generated script、配置逻辑。
- [x] 每次 Agent 写操作有 preview/diff、approval、undo/checkpoint。
- [x] Human takeover 不关闭 Unity，不丢当前工作。
- [x] 生成里程碑报告；用户已连续授权进入 M9。

## MILESTONE 9 — Playtest & Revision

- [x] Play → Feedback → Agent Modify → Compile → Play Again 完整闭环。
- [x] Feedback 绑定 build/version/playtest session。
- [x] 修改导致下游 version/approval freshness 正确更新。
- [x] 编译、测试、Play evidence 和人工评价全部可回看。
- [x] 生成里程碑报告；用户已连续授权进入 M10。

## MILESTONE 10 — Research Logging

- [x] Event logging、Timeline、Suggestion acceptance、Revision count、Approval history、Export。
- [x] 导出不包含 secrets/reasoning；时间线可关联知识、artifact、provider、Unity receipt。
- [x] 指标定义已写入 `docs/research/METRICS.md`，并在界面直接公开口径。
- [x] 生成里程碑报告；用户已连续授权进入 M11。

## MILESTONE 11 — Polish

最后才做：

- [x] animation
- [x] empty states
- [x] onboarding
- [x] loading
- [x] error UX
- [x] accessibility
- [x] visual polish
- [x] performance
- [x] responsive

在功能里程碑未通过前，禁止把大量时间投入动画。完成后运行全套测试、性能/可访问性/安全检查并生成最终里程碑报告。

## 每个 Milestone 的统一完成规则

严格遵循 MASTER SPEC：

1. Run。
2. Test。
3. Inspect。
4. Fix。
5. Test again。
6. 更新文档与风险。
7. 输出 `MILESTONE_REPORT.md`（Completed / Tests / Known issues / Decisions / Next proposal）。
8. 默认停止并等待用户确认；本轮用户已明确要求连续完成全部 MASTER SPEC，因此在逐里程碑验收与报告后继续。

## 下一动作

当前动作：PHASE 0 与 MILESTONE 1–11 已全部完成；停止扩展范围，等待负责人决定生产凭据、版权核验或部署工作。
