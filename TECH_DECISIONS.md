# 《漆问》PHASE 0 — TECH DECISIONS

> 状态含义：`Proposed` 等待项目负责人确认；`Accepted by MASTER SPEC` 是 MASTER SPEC 已明确规定；`Deferred` 不在当前里程碑决定。PHASE 0 不把 Proposed 偷换成已批准。

## 决策总表

| ID | 决策 | 状态 | 选择 | 关键理由 |
|---|---|---|---|---|
| TD-001 | 产品控制权 | Accepted by MASTER SPEC | Backend-enforced Human-in-the-loop Approval Gates | Agent 只能提议；阶段推进与副作用不可由 LLM 决定 |
| TD-002 | 可见 Agent 形态 | Accepted by MASTER SPEC | 单一 Co-Creator UI | 与 Human–Agent co-creation 定位一致；内部职责不转成多 Agent 面板 |
| TD-003 | Web 技术 | Proposed | Next.js 16.2.x Active LTS + React 19.2 + TS strict | 成熟生态、SSR/streaming、R3F 集成；避开 preview 版本 |
| TD-004 | Backend 技术 | Proposed | Python 3.13 + FastAPI + Pydantic v2 + SQLAlchemy 2 | Provider/AI/数据生态成熟，schema 与异步任务清晰 |
| TD-005 | 数据库 | Implemented 2026-08-10 | PostgreSQL 18.4；pgvector 延至语义检索里程碑 | M2 使用事务、JSONB、版本记录与 outbox；当前没有 embedding 数据，不提前引入扩展 |
| TD-006 | 文件存储 | Proposed | Local content-addressed storage，`ObjectStorage` 后续换 S3 | 快速本地演示但不把迁移成本写死；避免 blob 入 DB |
| TD-007 | Unity 版本 | Confirmed 2026-08-10 | Unity 6.3 LTS 6000.3.x 固定验证 patch | 支持至 2027-12；满足官方 MCP Unity 6+ 条件 |
| TD-008 | Unity 控制 | Confirmed 2026-08-10 | 架构保留 `Official Unity MCP` preferred；因当前无 entitlement，MVP 默认 `Coplay v10.1.2`；另有 Mock | 官方路径与开源可用性兼得；避免 entitlement/preview 单点故障 |
| TD-009 | Unity CLI | Proposed | 只作 discovery/open/health/CI；Pipeline custom commands 先 spike | 官方新工具有价值但仍 experimental；不开放任意 eval |
| TD-010 | Local Bridge | Confirmed 2026-08-10 | Node 24 LTS + TypeScript + official MCP TS SDK，独立进程 | 适合 stdio/process/HTTP/WebSocket，和 Web 共享 TS 工具链 |
| TD-011 | DeepSeek | Accepted by MASTER SPEC / details Proposed | 后端 `deepseek-v4-pro` + `deepseek-v4-flash`，Chat Completions | 官方当前模型；复杂/简单任务路由；key 不进入 browser/Unity |
| TD-012 | Agent 编排 | Proposed | 自研显式状态机，不引入 LangGraph/AutoGen 核心依赖 | 阶段由规范确定，需强审计和稳定 Approval Gate |
| TD-013 | Provider 契约 | Accepted by MASTER SPEC / details Proposed | Mock/Real 同一异步 job + ingest 契约 | 没 key 可完整演示；供应商可替换 |
| TD-014 | 3D Provider | Confirmed 2026-08-10 | Hunyuan3D first；Tripo optional fallback | 符合 MASTER SPEC 优先级，API 覆盖减面/UV/rig；Tripo 易于 GLB 对照 |
| TD-015 | Image Provider | Confirmed 2026-08-10 | 即梦 AI 企业 API（火山引擎 Visual API）；Mock 始终保留 | 用户指定即梦；以 provider capability discovery 选择当时可用的即梦模型版本，不绑定消费端网站 |
| TD-016 | Music Provider | Confirmed 2026-08-10 | Tencent Cloud MPS AIGC Audio；Mock 始终保留 | 国内 API/密钥体系；异步 Create/Describe task；模型版本配置化 |
| TD-017 | Unity 生成策略 | Proposed | GameLogicSpec → UnityBuildPlan → custom tools/templates | 降低直接生成任意 C# 的风险，提高可测试性 |
| TD-018 | 自动修复 | Proposed | 每 build run 最多 3 轮，仅改 generated area | 防无限循环和用户代码破坏；超限人工接管 |
| TD-019 | 实时传输 | Proposed | UI 采用 REST + SSE；远端 Bridge 才用 outbound WSS | 简单、可恢复、足够覆盖 token/job/build progress |
| TD-020 | Workflow messaging | Proposed | DB transactional outbox，先不引入 Redis/Celery | 首期减少基础设施，保证副作用一致性；规模需要时再升级 |
| TD-021 | Knowledge retrieval | Proposed | 结构化过滤优先，pgvector 语义检索辅助 | curated schema/Game Affordance 是事实层，embedding 不是事实源 |
| TD-022 | 依赖管理 | Proposed | 锁定 patch + Renovate/Dependabot + compatibility suite | Unity AI/MCP 和 Web 安全更新都很快，需可控更新 |
| TD-023 | API 预算 | Confirmed 2026-08-10 | 全局每月 30 元；不设单项目硬预算；预计超额时暂停并提示用户选择 | 不允许静默超支；选择可包括继续付费、改用 Mock、取消或推迟 |

## TD-001：Approval Gate 是服务端能力控制

**Context**：如果批准只存在前端，LLM、重放请求或 Bridge 调用均可绕过阶段顺序。

**Decision**：Approval decision 是不可变服务端记录，绑定精确 artifact version、stage、scope 和 actor。Workflow transition 在同一事务中验证 prerequisites；对 Unity/Provider 的副作用通过短期 action token 和 outbox 发出。

**Consequences**：实现复杂度上升，但能保证 MASTER SPEC 的最高优先级规则；前端不能“乐观推进”实际 stage。

## TD-007/008：Unity 6.3 LTS 与双 MCP Adapter

**Context**：官方 Unity MCP 已出现但仍在 AI Assistant preview 体系，并有 subscription/seat/project-link 条件；社区 MCP 更开放，但安全与维护质量不一。

**Decision proposed**：

- Unity baseline 采用 6.3 LTS，首次实现时固定经验证 patch 与 Assistant package 版本。
- `OfficialUnityMcpAdapter` 为首选。
- `CoplayUnityMcpAdapter` 固定在验证过的 MIT release，禁用遥测和高危工具，作为无 entitlement/preview 故障回退。
- `MockUnityAdapter` 始终可用。
- 所有 adapter 必须通过同一 contract tests；产品域只认 normalized QIWEN commands。

**Rejected alternatives**：

- 只依赖官方 MCP：商业访问和 preview 稳定性构成单点风险。
- 直接暴露 Coplay 全量 tools：与最小权限、Approval Gate 冲突。
- 直接使用 DeepSeek 在 Unity 内生成/执行：泄露 key，绕过产品状态机。

## TD-010：独立 TypeScript Local Bridge

**Context**：浏览器不能安全控制本地 Unity；FastAPI 可以做本地进程但会把 OS 权限混入产品 API 部署。

**Decision proposed**：独立 Node 24/TypeScript bridge，使用 MCP official TS SDK，向 Backend 提供版本化的 narrow protocol。Bridge 只 loopback / outbound connection，不为浏览器开放特权 API。

**Consequences**：增加一个可发布组件；换来清晰信任边界、多 Unity 适配和未来远端托管能力。首个 spike 必须验证 Windows 安装、自动更新、进程退出和凭据存储；若打包成本显著超预期，可在 ADR 中重新比较 Python sidecar。

## TD-011：DeepSeek 双模型路由

**Context**：MASTER SPEC 要求 DeepSeek-only backend，并偏好 Pro/Flash。官方当前模型已经更新，旧模型名退役。

**Decision**：

- API base URL 为配置，默认 `https://api.deepseek.com`。
- `deepseek-v4-pro`：概念综合、Game Logic Spec、构建计划、编译错误修复。
- `deepseek-v4-flash`：标签、简单结构转换、UI 短建议、低风险摘要字段。
- Chat Completions 作为共同接口；不依赖只支持单模型的实验接口。
- thinking/reasoning effort 由 ModelRouter 根据任务类设置，用户文本不能覆写。
- Tool Calls 是 proposal envelope；参数经 schema 和 policy 检查后仍需人类批准。

**Operational policy**：429 指数退避并尊重 Retry-After；网络失败使用幂等 request id；JSON/tool arguments 永远不可信；usage/cost 逐调用记录；密钥只由后端 secret manager/env 获取。

## TD-012：显式状态机，不使用通用 Agent 图框架

**Context**：OpenGame/Codex 展示了灵活 agent loop 的优点，但 QIWEN 的阶段、审批、文化约束和输出类型已被 MASTER SPEC 明确定义。

**Decision proposed**：以数据库状态、纯 transition functions 和 domain events 实现 workflow。LLM 不持有循环控制权；每次 run 有最大步骤/成本/时间。

**Revisit trigger**：当出现至少三个需要持久化并行分支、人工中断恢复和跨日调度的真实用例，且自研状态机明显重复实现成熟框架能力时，再写 ADR 比较 Temporal/LangGraph 等。

## TD-013：Mock 与 Real Provider 完全同构

**Decision**：Mock 不返回前端特殊假数据，而是创建真实 `provider_job`、进度事件、artifact version、files、provenance 和 approval request。可用故障 fixture 覆盖超时、审核拒绝、坏文件、临时 URL 过期和取消。

**Consequences**：Demo 可以证明真实架构，不会在接 API 时推倒重来；测试可以确定性覆盖等待与失败路径。

## TD-014/015/016：生成供应商顺序

**3D proposed**：Hunyuan3D first real adapter；先做 text/image-to-3D、poll、GLB ingest、基础 mesh validation；减面/UV/rig 延后按 Unity prototype 需求开启。Tripo 只在 A/B spike 后接入。

**Image confirmed**：先 Mock，真实实现使用火山引擎“即梦 AI”企业 API。当前官方提供 `visual.volcengineapi.com` 的即梦同源图像生成能力；模型/`req_key` 必须配置化，接入时通过 capability/账户授权验证选择受支持版本。不得将消费端即梦网站自动化当作 API。

**Music confirmed**：先登记现有项目音频并实现 Mock；真实实现使用 Tencent Cloud MPS `CreateAigcAudioTask` / `DescribeAigcAudioTask`。具体模型名称和版本是运行时配置；首个 sandbox spike 比较当前 MPS 支持模型对“漆林/髹漆工序/探索节奏”纯音乐 brief 的表现。

## TD-017/018：Unity 安全生成与有界修复

**Decision proposed**：模型首先生成 schema-valid `GameLogicSpec` 和 `UnityBuildPlan`；Unity custom tools 将计划映射到模板。只有必须新增的 glue code 才写入 `Assets/QIWEN/Generated/<build-id>/`。每轮编译后读取真实 Console，修复最多 3 次；不自动修改模板、Packages、ProjectSettings 或用户导入资产。

**Escalation conditions**：重复同类错误、需要升级 package、需要删除/覆盖用户文件、需要切换 render pipeline、测试失败原因不确定、Unity crash/connection identity 改变。

## TD-020：先用 Outbox，不急于消息队列

**Decision proposed**：PostgreSQL `outbox_events` + worker lease/heartbeat 处理 LLM、Provider 和 Bridge 长任务；外部调用携带幂等 key。暂不引入 Redis/Celery，降低开发和部署面。

**Revisit trigger**：单节点 worker 不能满足并发、需要独立队列优先级/延迟任务、或 outbox 表运维成本变高时，再选择队列。

## 用户确认记录（2026-08-10）

1. 接受 Unity 6.3 LTS。
2. 接受官方 Unity MCP 优先、Coplay 回退；当前没有 Unity MCP entitlement，因此 MVP 实际默认 Coplay。
3. 接受 Node/TypeScript 独立 Local Bridge。
4. 第一批 3D 真实 Provider 为 Hunyuan3D。
5. 图像真实 Provider 为即梦 AI 企业 API（火山引擎）。
6. 音乐真实 Provider 为 Tencent Cloud MPS。
7. API 全局月预算 30 元，不设单项目预算；预计超额时暂停并提示用户选择，不自动扣费或静默降级。
8. E 盘现有素材作为 curated demo 候选导入。导入前登记为 `user_provided / rights_unverified / internal_demo_only`，原文件不覆盖；补全授权后才能进入可发布产物。
9. 项目负责人暂任知识与素材策展确认人；每条文化知识仍需来源和引用字段。

## MILESTONE 2 执行记录（2026-08-10）

- PostgreSQL 18.4 仅监听 `127.0.0.1:55432`，本地开发数据目录位于 `D:\qiwen-data\postgres18`。
- SQLAlchemy 2 异步会话与 Alembic migration 已投入使用；9 张业务表覆盖项目、知识、对话、资产、版本、审批、活动、Provider job 与 outbox。
- 数据库 schema 使用 JSONB 保存可演进结构字段；审批、版本和活动采用追加式记录。
- `pgvector` 暂未安装：M2 没有 embedding 或语义检索验收项，避免无使用者依赖；进入实际检索实现前再固定扩展版本并补 migration。
- 本地对象文件不写入数据库；资产记录保存路径、MIME、大小和 SHA-256，以便恢复时核对引用与内容。
- M2 已完成并停止；未获得“开始 MILESTONE 3”授权前，不实现真实 DeepSeek Agent。

## TD-021：运行时改用米醋 Provider（2026-08-10）

**Context**：项目负责人在完成原定里程碑后，明确要求将聊天、代码和图片运行 Provider 改为米醋 API，音频暂不接真实服务；MASTER SPEC 文件保持不变。

**Decision**：统一 `LLMProvider` 契约新增 `MicuLLMProvider`，对话路由 `gpt-5.6-terra`，结构化设计与 Unity 代码路由 `gpt-5.6-sol`；使用实际可工作的 `/v1/chat/completions`，并保留 schema 校验与修复。`ImageProvider` 新增 `MicuImageProvider`，使用 `gpt-image-2-pro`，远端 URL/base64 都必须摄取到 E 盘内容寻址存储。DeepSeek 与即梦 adapter 保留为可替换实现，不散落到 UI。音乐继续 Mock。

**验证**：米醋 LLM Key 的模型清单、聊天模型、代码模型和 JSON 输出均已真实调用验证；米醋图片已真实生成 1024×1024 PNG 并通过签名、SHA-256、大小和本地对象服务验证。混元新 Key 已通过 TokenHub 无计费查询鉴权，Provider 已升级为 Bearer 鉴权、`hy-3d-3.1` 与 `/v1/api/3d/submit|query`；尚未提交付费生成任务，所以“真实 3D 产物摄取”仍待首次玩家生成验证。
