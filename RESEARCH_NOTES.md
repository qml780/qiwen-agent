# 《漆问》PHASE 0 — RESEARCH NOTES

> 研究基线：2026-08-10。本文只记录 PHASE 0 的检索、源码阅读、比较与判断；`QIWEN《漆问》.md` 始终是本项目 MASTER SPEC，本文不替代、不改写它。

## 1. 研究范围与方法

本轮对用户指定的九个 GitHub 项目进行了仓库级与关键源码级检查，不以 README 结论代替源码判断。检查项包括：仓库活跃度、发布节奏、License、依赖、服务端与 Unity 端边界、传输协议、工具注册方式、主线程调度、编译与测试闭环、多实例支持、任意代码执行面、可复用性及产品契合度。

另外补查了 Unity 官方 MCP / Unity AI / Unity CLI、MCP 官方 SDK、OpenAI Codex，以及 2026 年仍活跃的 Unity MCP/CLI 实现；同时核对 DeepSeek、3D、图像和音乐供应商的官方 API 文档。

研究用浅克隆位于 `D:\游戏agent\phase0-repos`，不属于产品代码，也不会自动并入项目。所有 GitHub 指标是 2026-08-10 的快照，后续会变化。

## 2. 必查 GitHub 项目比较

| 项目 | 活跃度快照 | 架构与关键实现 | License | 适合直接复用 | 主要问题 | 结论 |
|---|---:|---|---|---|---|---|
| [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp) | 13,297 stars；2026-08-07 推送；v10.1.2（2026-08-02） | Unity UPM 包 + Python FastMCP 服务；默认 stdio，可选 HTTP；服务端与 Unity 插件通过 WebSocket hub；多 Editor 实例路由；场景、对象、组件、脚本、资源、Console、测试、Play Mode、Build、Profiler、截图、批处理等完整工具面 | MIT | 在官方 MCP 不可用时，固定版本复用其 MCP server/Unity package；借用其多实例、批处理、测试与 Console 闭环 | 工具面很大；含 `execute_code`/反射等高危能力；需关闭遥测、限制监听地址、做命令 allowlist；FastMCP 私有接口使用值得持续监控 | **开放回退首选；不直接把原始全量工具暴露给 Agent** |
| [IvanMurzak/Unity-MCP](https://github.com/IvanMurzak/Unity-MCP) | 3,853 stars；2026-08-09 推送；v0.87.0 | Unity 插件 + TypeScript CLI；支持 stdio/Streamable HTTP、本地与云端；自定义 C# 方法注册工具，含运行时编译游戏支持；服务器发行物与云服务分布在其生态仓库 | Apache-2.0 | 参考 CLI 安装/发现、custom tool、运行时工具模式；可作为技术备选 | 依赖其分离的 server/CLI/cloud 生态，部署边界比 Coplay 复杂；QIWEN 不需要云端登录耦合 | **参考与二级备选，不作默认依赖** |
| [CoderGamester/mcp-unity](https://github.com/CoderGamester/mcp-unity) | 1,862 stars；2026-08-10 推送；v1.4.0 | MCP client ⇄ Node/TS stdio server ⇄ WebSocket ⇄ Unity Editor；Unity 侧用 EditorCoroutine 主线程执行；工具定义在 Node 与 C# 两侧 | MIT | 小而清晰，适合参考 WebSocket RPC、主线程调度、编译等待和错误返回 | 工具 schema 两端重复；能力比 Coplay 少；多一层 Node server | **架构参考或轻量回退** |
| [yagizeraslan/DeepSeek-Unity](https://github.com/yagizeraslan/DeepSeek-Unity) | 35 stars；2026-02-26 推送；无正式 release | UnityWebRequest 直连 `/chat/completions`；API key 存 ScriptableObject；自写 SSE；使用旧 `deepseek-chat` / `deepseek-reasoner` | MIT | 只能参考 Unity SSE 事件接口和取消语义 | 密钥进入 Unity 客户端；模型名已退役；缺少后端审计、限流、成本、工具审批与持久化 | **禁止直接复用集成；QIWEN 必须后端调用 DeepSeek** |
| [leigest519/OpenGame](https://github.com/leigest519/OpenGame) | 2,799 stars；2026-04-22 推送；v0.6.0 代码；无 GitHub release | Node 20+ monorepo；模型/工具/MCP、shell/filesystem/web、容器 sandbox、审批模式、shadow-git checkpoint、会话恢复、子 Agent allowlist、事件流与遥测 | Apache-2.0 | 参考权限分类、checkpoint/restore、任务事件、sandbox、上下文隔离 | 面向终端与 Web 游戏生成；体量大，强耦合其模型/CLI；并非 Unity 产品框架 | **设计参考，不嵌入运行时** |
| [wanghaisheng/OpenAgenticGame-Studios](https://github.com/wanghaisheng/OpenAgenticGame-Studios) | 11 stars；2026-06-03 推送 | 大量 Agent/skill/workflow/质量门文档，覆盖多引擎与制作岗位 | MIT | 选择性参考里程碑 QA、Unity 检查表和交接字段 | 主要是 prompt/文档集合；85 Agent/72 skill 过度复杂；没有可复用产品运行时 | **仅参考少量 QA 规则** |
| [pamirtuna/gamestudio-subagents](https://github.com/pamirtuna/gamestudio-subagents) | 243 stars；最后推送 2025-08-24 | 12 个岗位型子 Agent、Unity/Godot/Unreal 配置、项目模板、handoff 与 Python 管理脚本 | MIT | 参考结构化 handoff、角色产物和引擎模板 | 已近一年不活跃；多 Agent 用户体验与 MASTER SPEC 的单一 Co-Creator 界面冲突 | **内部职责可参考，产品层不展示多 Agent** |
| [IvanMurzak/ai-game-dev-plugin](https://github.com/IvanMurzak/ai-game-dev-plugin) | 2 stars；2026-07-13 推送 | Codex/Claude 插件清单、Unity/Godot/Unreal game-dev skills 与同步脚本 | Apache-2.0 | 参考 Unity 开发技能的约束和安装引导 | 是 coding-agent 插件，不是 Web 产品、Provider 或 Unity Bridge | **参考，不作为产品依赖** |
| [Yuan-ManX/ai-game-devtools](https://github.com/Yuan-ManX/ai-game-devtools) | 1,296 stars；2026-07-21 推送 | 静态 HTML/CSS/JS 的 AI 游戏开发工具目录 | MIT | 作为供应商/工具发现索引 | 没有 Agent、Bridge、Provider 或生成流水线实现 | **研究索引，不复用代码** |

## 3. 新增项目与官方实现

### 3.1 Unity 官方 MCP（优先候选）

Unity AI 已在 2026 年进入 Unity 6.0+ Open Beta，包含官方 MCP Server。官方文档显示可以向外部 MCP client 暴露 Editor 上下文和操作，也支持通过 `[McpTool]`、typed parameters、`JObject` schema 或运行时 API 注册自定义工具。首连需要在 Unity 侧批准，符合《漆问》“Unity 必须可见、关键动作人类可控”的方向。

已确认的约束：

- 依赖 Unity AI Assistant preview package，当前仍可能出现版本兼容或编译问题。
- MCP / AI Gateway 访问可能要求符合条件的 Unity 订阅、组织 seat 和 Cloud project 关联；不能把商业可用性建立在“肯定免费且长期不变”的假设上。
- relay/bridge 和批准机制适合本地接入，但必须固定 Unity package 版本并做启动兼容性检测。
- 官方 custom MCP tool 很适合实现 QIWEN 的窄工具：导入批准资产、按结构化 Game Logic Spec 生成场景、读 Console、编译、Play/Stop、截图、运行测试。比开放任意 `eval` 更安全。

来源：[Unity AI Open Beta 概览](https://unity.com/blog/unity-ai-how-to-get-started)、[自定义 MCP Tool](https://docs.unity.cn/Packages/com.unity.ai.assistant%402.9/manual/integration/unity-mcp-tool-registration.html)、[AI Gateway / MCP access requirements](https://docs.unity.cn/Packages/com.unity.ai.assistant%402.9/manual/integration/ai-gateway-get-started.html)。

### 3.2 Unity 官方 CLI / Pipeline（补充控制面）

2026-07 发布的 Unity CLI 是独立 `unity` binary，支持编辑器/模块/项目发现与结构化 JSON/TSV 输出。实验性 `com.unity.pipeline` 可控制运行中的 Editor，并支持 `[CliCommand]` 与 `unity command eval`。

判断：CLI 很适合 Local Bridge 做 Unity 安装发现、版本检查、打开项目、健康检查和 CI；Pipeline 仍标为 experimental，`eval` 又是任意 C# 执行，因此不能替代审批门或成为 Agent 的直接 shell。只允许调用 QIWEN 自己注册的窄命令，`eval` 仅保留给人工诊断并默认关闭。

来源：[Unity CLI 发布说明](https://unity.com/blog/meet-the-unity-cli)、[Unity CLI Docs](https://docs.unity.com/en-us/unity-cli)。

### 3.3 其他活跃 Unity 控制实现

| 项目 | 价值 | 复用判断 |
|---|---|---|
| [FunplayAI/funplay-unity-mcp](https://github.com/FunplayAI/funplay-unity-mcp) | 2026 活跃；MIT；Unity 2022.3+；156 工具；Unity 内直接 HTTP MCP；per-project port；实验 broker 跨 domain reload；工具暴露配置 | 值得做兼容性 spike，尤其参考 per-project port 和 reload resilience；项目较新、规模小于三大实现，暂不列默认 |
| [AnkleBreaker-Studio/unity-mcp-server](https://github.com/AnkleBreaker-Studio/unity-mcp-server) | 330+ 工具、二级 lazy tool、HTTP Unity plugin、多实例与 heartbeat | 自定义 License 带显著署名和转售限制，不满足“可无障碍并入商业产品”的确定性；只参考二级工具发现、heartbeat，不复制代码 |
| [youngwoocho02/unity-cli](https://github.com/youngwoocho02/unity-cli) | MIT；Go 单 binary + Unity HTTP connector；instance registry/heartbeat；跨 domain reload；命令输出清晰 | 参考健康发现与 heartbeat；其核心强调任意 `exec`，QIWEN 不能向模型开放；官方 Unity CLI 已成为优先评估对象 |
| [openai/codex](https://github.com/openai/codex) | Apache-2.0；成熟 coding agent；MCP、审批、sandbox、AGENTS 约束和任务事件模型 | 参考工具权限、审批和执行隔离；不把 Codex CLI 内嵌为产品 Agent 编排器 |
| [modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk) | 官方 MCP TypeScript SDK，持续活跃 | Local Bridge 的直接依赖候选，固定兼容版本并做契约测试 |

## 4. Unity MCP 能力矩阵

| 维度 | 官方 Unity MCP | Coplay | IvanMurzak | CoderGamester | Funplay |
|---|---|---|---|---|---|
| Unity 版本 | Unity 6+ | 2021.3+（包声明） | 2022.3+ | 2022.3+ | 2022.3+ |
| 通信 | relay/本地 bridge/MCP stdio | MCP stdio/HTTP + WebSocket plugin hub | stdio/Streamable HTTP + plugin | stdio Node + WebSocket | Unity 内 HTTP MCP；可选 broker |
| 自定义窄工具 | 官方 `[McpTool]` | 支持 custom tools | 强项 | 可扩展两端 | 支持 |
| 多 Editor | 可按 project/instance 配置，需验证 | 原生多实例路由 | 支持 | 较基础 | per-project port |
| 编译/Console/Test | 有基础能力，需实际 spike 核验 | 完整 | 完整 | 完整 | 完整 |
| License/商业确定性 | Unity terms / seat 约束 | MIT | Apache-2.0 | MIT | MIT |
| 当前成熟度 | 官方但 beta/preview | 社区最成熟 | 社区成熟 | 社区成熟、较小 | 新且活跃 |
| QIWEN 角色 | **Preferred adapter** | **Fallback adapter** | Reference/backup | Reference/backup | Compatibility spike |

推荐不是“选一个仓库并锁死”，而是定义 `UnityExecutionAdapter`：

1. `OfficialUnityMcpAdapter`：满足订阅和版本条件时首选。
2. `CoplayUnityMcpAdapter`：无 Unity AI entitlement、官方 preview 故障或离线部署时回退。
3. `MockUnityAdapter`：无 Unity 时可演示完整状态、日志、编译失败与修复回路。
4. `UnityCliProbe`：只负责安装/版本/进程/项目发现和受控健康检查，不作为 Agent 任意执行通道。

## 5. DeepSeek API 研究

DeepSeek 官方当前模型是 `deepseek-v4-pro` 与 `deepseek-v4-flash`；旧 `deepseek-chat` 与 `deepseek-reasoner` 已于 2026-07-24 退役。两者支持 OpenAI-compatible Chat Completions、thinking/non-thinking、JSON output 和 tool calls，当前官方标注 1M context、最大 384K output。价格和限额会变化，只能作为运行时配置和成本记录，不能硬编码业务逻辑。

QIWEN 方案：

- 仅 FastAPI 后端持有 `DEEPSEEK_API_KEY`，浏览器、Unity 工程和 Local Bridge 都不能获得密钥。
- 使用 OpenAI-compatible Chat Completions adapter；复杂概念推演、规划和错误修复路由 `deepseek-v4-pro`，分类、改写结构字段、简短 UI 辅助路由 `deepseek-v4-flash`。
- tool call 只产生“提议”，工具参数必须经 Pydantic/JSON Schema 校验、权限策略与 Approval Gate；模型不能直接调用 Unity。
- 默认不用 beta strict endpoint；普通 schema 校验失败时执行有上限的 repair/retry。官方也明确提醒 arguments 可能不是合法 JSON 或包含幻觉参数。
- 支持 SSE，但必须处理 keep-alive、超时、429、取消、断线续传与幂等；保存最终答案、工具提议和 usage，不保存/展示内部 reasoning。
- 每次调用记录 provider/model/request id/token/cached token/cost estimate/latency/status/schema version，不记录 API key。
- 启动时用模型列表或小额 health call 检查 model id，避免模型退役后静默失败。

来源：[模型与价格](https://api-docs.deepseek.com/quick_start/pricing)、[Tool Calls](https://api-docs.deepseek.com/guides/tool_calls)、[Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion)、[Rate Limit](https://api-docs.deepseek.com/quick_start/rate_limit/)。

`DeepSeek-Unity` 不能直接复用的根本原因不是代码质量，而是安全边界与产品边界错误：它把模型连接放在 Unity client；QIWEN 要求 DeepSeek 是后端 Provider，且人类审批是服务端状态机的一部分。

## 6. 图像、3D、音乐 Provider

### 6.1 统一 Provider 契约

四类 Provider 都使用相同的异步生命周期：`validate → submit → queued/running → succeeded/failed/cancelled → ingest → verify → present variants → human approve`。远端 URL 不作为永久资产；任务成功后立刻下载到受控存储，计算 SHA-256、MIME、尺寸/时长/面数等元数据，并保存 prompt、negative prompt、seed（若有）、模型版本、供应商任务 ID、许可/来源声明和父版本。

### 6.2 3D

- **腾讯混元生3D**：官方 API 已覆盖专业版/极速版、纹理、减面、UV、动作、自动绑定和格式转换，且 MASTER SPEC 已要求优先。适合做首个真实 `ThreeDGenerationProvider`。
- **Tripo v3**：文/图/多视图到模型，异步 task，GLB 可直入 Unity/Three.js；结果 URL 仅约 5 分钟有效，验证了“立即 ingest”是硬需求。作为第二供应商和对照测试。
- **Meshy**：接口成熟且有 Unity 使用路径，可列后续备选，但 PHASE 0 不建议同时实现三家。

来源：[混元生3D API 概览](https://cloud.tencent.cn/document/product/1804/120838)、[Tripo Quick Start](https://developers.tripo3d.ai/en/docs/quick-start)。

### 6.3 图像

- **用户已确认即梦 AI**：真实 `ImageGenerationProvider` 采用火山引擎企业 API，而不是自动化操作消费端即梦网站。官方当前提供即梦同源图片生成 API，入口为 `visual.volcengineapi.com`，覆盖文生图、图像编辑、多图组合和 4K 输出。模型/`req_key` 是账户能力与版本相关配置，接入时做 capability probe，不在产品域中硬编码营销名称。
- **Seedream/方舟关系**：即梦能力源于字节 Seedream/SeedEdit 系列；火山方舟还提供 Seedream 标准 Image Generations API。但既然用户指定“即梦”，首个真实 adapter 使用官方标注的即梦企业接口，Seedream 方舟接口只作为同供应商后备实现。
- 首期仍先实现可重复的 Mock image variants；真实调用进入 MILESTONE 4，并受全局月预算约束。

来源：[即梦 AI 图片生成 4.0 企业接口](https://www.volcengine.com/docs/85621/1863351)、[火山方舟 Image Generations](https://api.volcengine.com/api-docs/view?action=ImageGenerations&serviceCode=ark&version=2024-01-01)。

### 6.4 音乐

- **用户已确认腾讯云 MPS AIGC 音频**：使用 `CreateAigcAudioTask` 提交、`DescribeAigcAudioTask` 轮询。官方当前聚合 GL、MiniMaxMusic 等模型，不把模型版本写死；在 sandbox 中选择实际账户可用且最适合纯音乐的版本。
- 现有项目音频作为 curated demo candidates 登记，不被 Mock Provider 覆盖或改写；未补齐权利信息前标记为 internal-demo-only。
- ElevenLabs Music v2 保留为研究对照，不进入首批实现。

来源：[腾讯云 MPS AI 音乐生成](https://cloud.tencent.com/document/product/862/133520)、[CreateAigcAudioTask](https://cloud.tencent.com/document/product/862/132830)。

## 7. Web、Local Bridge 与依赖基线

### 7.1 推荐基线

- Web：Next.js 16.2.x Active LTS、React 19.2、TypeScript strict、R3F/Three.js（按 React 19 兼容矩阵固定具体版本）。
- Backend：Python 3.13.x、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、psycopg 3。
- Local Bridge：Node.js 24 LTS + TypeScript + 官方 MCP TS SDK；独立进程，不运行在浏览器。
- DB：PostgreSQL 18 + pgvector 0.8.x；向量能力 feature-gated，知识库早期以结构化查询为主。
- Storage：本地文件存储先行，统一 `ObjectStorage` 接口；后续可换 S3-compatible。
- Unity：Unity 6.3 LTS（6000.3.x 固定 patch）；官方支持至 2027-12。避免新项目锁到将于 2026-10 结束标准支持的 Unity 6.0 LTS。

版本选择原则：只固定经 smoke test 的 patch，启用依赖更新监控；preview/beta 依赖单独锁文件和兼容性测试，不自动更新。Unity 版本来源：[Unity 6 Support](https://unity.com/releases/unity-6/support)。

### 7.2 Local Bridge 可行性

浏览器不能可靠且安全地启动 Unity/relay，也不能持有本地路径与 OS 权限，因此必须有 Local Bridge。推荐 Node/TS 是因为 Web 前端已有 Node 工具链，官方 MCP TypeScript SDK 可直接作为 client，且 Windows 子进程、stdio、HTTP 与 WebSocket 适配成熟。Bridge 对上只暴露 QIWEN normalized commands，对下可切换官方 MCP、Coplay MCP 与 Mock。

Bridge 安全底线：

- 仅绑定 `127.0.0.1`，不监听 `0.0.0.0`；随机或用户配置端口。
- 后端与 Bridge 配对后使用短期 bearer/session token；浏览器不能直接访问 Bridge。
- CORS/origin allowlist、请求体大小上限、速率限制、路径 canonicalization 与项目根目录 allowlist。
- 禁止 Agent 传 shell、C# eval 或任意 menu path；只允许固定 schema 的 domain commands。
- 每个写操作携带 `project_id`、`approval_id`、`action_id`、`idempotency_key` 和期望版本；Bridge 再向后端验证授权。
- 多 Unity 实例必须以 canonical project path + Editor PID/instance id 绑定，绝不“默认选第一个”。
- 远程部署时只能由 Bridge 主动建立 outbound WSS；不在用户电脑开放公网入站端口。

## 8. 可复用能力总表

| 能力 | 直接复用 | 只参考 | 自行实现 |
|---|---|---|---|
| Unity MCP transport/tools | 官方 MCP；Coplay MIT fallback | CoderGamester/Funplay/Ivan/youngwoo 的连接恢复、多实例、主线程模式 | `UnityExecutionAdapter`、能力探测、QIWEN allowlist、审批票据校验 |
| Agent coding safety | MCP SDK | OpenGame/Codex 的审批、sandbox、checkpoint | 后端阶段状态机、Approval Gate、版本失效传播、Unity action policy |
| DeepSeek | 官方 OpenAI-compatible API/SDK | DeepSeek-Unity 的 SSE UI 语义 | 后端 provider、模型路由、schema repair、成本/审计、工具提议层 |
| 资产生成 | Hunyuan/Tripo/ElevenLabs 官方 API | 各家 prompt/async job 模式 | 统一 Provider 契约、Mock、ingestion、provenance、variant/version/approval |
| 知识库 | PostgreSQL/pgvector | RAG 常规检索模式 | 漆文化 curated schema、Game Affordance Layer、引用与版本治理 |
| Unity 游戏生成 | Unity templates、已批准第三方 MCP package | Agentic Game Studio 的 QA/handoff | 结构化 Game Logic Spec、模板选择、编译修复上限、可视 build monitor、人工接管 |

## 9. 研究结论

1. QIWEN 不应把任一“全能 Unity Agent”仓库直接嵌入产品；其价值在 Editor 操作，不在产品审批、知识、版本与文化约束。
2. Unity 接入采用 adapter 而非单一供应商：官方 MCP 优先，Coplay 固定版回退，Mock 保证无 Unity 演示。
3. Agent 只能提交提议；Approval Gate、状态推进和 Unity 写权限由后端确定性代码执行。
4. DeepSeek-Unity 不适合复用，DeepSeek 只在后端；`v4-pro`/`v4-flash` 双模型路由与 MASTER SPEC 一致。
5. 真实生成 Provider 不应阻塞产品骨架。先交付契约一致的 Mock，再对用户确认的一家/类做真实 adapter。
6. 用户已确认 3D 为混元生3D、图像为即梦 AI 企业 API、音乐为腾讯云 MPS；三者仍须在 MILESTONE 4 逐个完成 sandbox、成本与商用条款验证。
7. 所有生成资产必须本地 ingest、可追溯、版本化并经人类批准，不能把供应商临时 URL 当项目资产。
8. API 全局月预算为 30 元；不设单项目硬预算，预计超额时暂停并由用户选择继续付费、改用 Mock、取消或推迟。
