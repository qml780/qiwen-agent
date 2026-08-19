# 《漆问》PHASE 0 — RISKS

> 评分：Probability（P）和 Impact（I）各 1–5；Score = P × I。15–25 为 Critical，8–14 为 High，4–7 为 Medium，1–3 为 Low。风险责任人是角色建议，需在项目确认后实名分配。

## 风险登记表

| ID | 风险 | P | I | Score | 预防/缓解 | 触发与应急 | Owner |
|---|---|---:|---:|---:|---|---|---|
| R-01 | Approval Gate 只做成 UI，后端/Bridge 可绕过 | 3 | 5 | 15 | 服务端不可变 approval、version freshness、action token、状态转移测试 | 发现无 approval 的副作用立即停写、撤销 Bridge 配对、审计全部 action | Backend/Security |
| R-02 | Agent 或 MCP 任意代码执行破坏 Unity 工程/用户资产 | 4 | 5 | 20 | 不暴露 `execute_code/eval/shell`；custom narrow tools；路径 allowlist；generated area；动作 diff/receipt | 暂停队列，人工接管；从版本/备份恢复；保留证据 | Unity/Bridge |
| R-03 | 官方 Unity MCP beta/preview 版本不兼容、崩溃或 entitlement 变化 | 4 | 4 | 16 | 已确认当前无 entitlement，MVP 默认 Coplay；官方 adapter 只在 capability probe 成功后启用；固定 Unity/Assistant patch；Mock | 保持/切回 Coplay；禁止自动升级；记录兼容矩阵 | Unity |
| R-04 | Coplay 或其他社区 MCP 供应链/维护变化 | 3 | 4 | 12 | 固定 commit/release、校验包哈希、最小 fork policy、依赖扫描、contract tests | 暂停升级；回退已知版本；必要时维护窄 fork | Unity/Security |
| R-05 | 多 Unity 实例连错工程并写入 | 3 | 5 | 15 | canonical path + PID/instance id 双绑定；用户确认；每 action 校验 identity；禁止选第一个 | 立即停止动作并标记 incident；比较 action receipts/文件变更 | Bridge |
| R-06 | Domain reload/编译期间重复执行导致资产或对象重复 | 4 | 4 | 16 | idempotency key、action journal、atomic tool、heartbeat/compile-aware wait | 查原 receipt；只重试未开始或明确可重入动作 | Bridge/Unity |
| R-07 | DeepSeek 模型名、接口、价格或输出行为变化 | 4 | 3 | 12 | model discovery/health、provider config、schema validation、成本上限、兼容测试 | 自动降级 Flash/暂停 real LLM/启用 Mock；要求管理员确认新模型 | AI/Operations |
| R-08 | DeepSeek tool arguments/JSON 无效或幻觉参数 | 4 | 4 | 16 | Pydantic/JSON Schema、枚举/引用检查、repair 上限、tool proposal 不直接执行 | 拒绝 proposal 并展示可恢复错误，不调用外部工具 | AI/Backend |
| R-09 | API key 泄漏到浏览器、Unity、日志或版本库 | 3 | 5 | 15 | 后端 secrets only；日志脱敏；secret scan；Bridge 无 provider key；`.env` gitignore | 立即轮换、撤销、审计账单与日志、通知 owner | Security/Operations |
| R-10 | 远端 Provider 临时 URL 过期，资产永久丢失 | 4 | 4 | 16 | 成功后同步 ingest；重试/校验 hash；任务状态与 object key 同事务关联 | 在 URL 有效期内重新下载；过期则 query/regenerate 并保留失败记录 | Provider |
| R-11 | 生成文件格式/拓扑/材质不适合 Unity 或 Web | 4 | 3 | 12 | MIME/GLB/mesh/PBR 校验；面数预算；R3F 和 Unity 双预览；转换 pipeline | 标记 bad_output，自动请求减面/格式转换或人工替换 | 3D/Unity |
| R-12 | 图像/3D/音乐供应商许可不允许目标商用或训练数据不透明 | 3 | 5 | 15 | 每 provider legal checklist；保存 model/terms/version/provenance；用户确认账户方案 | 隔离受影响资产，阻止发布 build，替换或重新生成 | Product/Legal |
| R-13 | 用户现有图片、音频、FBX、文献权利不清 | 4 | 5 | 20 | 已确认作为 curated demo candidates；导入登记 `user_provided / rights_unverified / internal_demo_only`，保留原文件；补来源/作者/授权后才能发布 | 不进入可发布 artifact；由用户补权利证明或替换 | Product/Curator |
| R-14 | 漆文化内容错误、浅表化、误用或文化不尊重 | 3 | 5 | 15 | curated 来源、知识引用、Game Affordance 与事实分层；人类策展 gate；敏感用法规则 | 退回概念/资产阶段；显示引用与争议；请求专家审核 | Curator/Product |
| R-15 | Agent 把文化知识变成装饰风格而非玩法含义 | 4 | 4 | 16 | Game Affordance Layer；GameLogicSpec 必须引用知识与机制映射；审批解释“为何这样设计” | 拒绝候选、要求提出机制级替代 | Design/Curator |
| R-16 | Mock 与真实 Provider 行为分叉，Demo 通过但集成失败 | 3 | 4 | 12 | 同一 contract tests/job/ingest path；Mock 故障场景；真实 sandbox tests | 阻止 provider 发布，补契约与 fixture | QA/Provider |
| R-17 | 自动编译修复进入无限循环或扩大改动范围 | 3 | 5 | 15 | 最多 3 轮；error fingerprint；只改 generated area；diff size 上限 | 停止并人工接管；不继续消耗 token/修改工程 | AI/Unity |
| R-18 | Unity 工程无版本控制/备份导致不可恢复 | 3 | 5 | 15 | M1 前建立 git/LFS 策略；每 build run checkpoint；不覆盖现有工程 | 停止写入；先做完整可恢复副本，再继续 | Operations/Unity |
| R-19 | 大型二进制素材进入普通 Git，仓库膨胀 | 4 | 3 | 12 | 原始/生成资产用 object storage 或 Git LFS；清晰 `.gitignore` | 迁移 LFS/存储，保留引用映射；不重写共享历史未经批准 | Operations |
| R-20 | pgvector/RAG 返回相似但不权威的知识 | 3 | 4 | 12 | 结构化过滤优先；来源权重；引用可见；embedding 可重建不作事实源 | 回退 exact/curated search，标记低置信结果 | Data/Curator |
| R-21 | 上传文化资料到外部 LLM/Provider 违反隐私或地域要求 | 3 | 5 | 15 | 数据分类、最小上下文、provider region policy、默认不上传原文件 | 阻止调用并切 Mock/本地；审计已传内容 | Security/Product |
| R-22 | 本地 Bridge 被恶意网页/本机进程调用 | 3 | 5 | 15 | loopback、origin reject、短期 token、one-time pairing、请求签名、速率限制 | 撤销设备 token、停 Bridge、审计 receipts | Bridge/Security |
| R-23 | 远程 Bridge 暴露公网入站控制 | 2 | 5 | 10 | 只 outbound WSS；设备认证；无公网 listener；租户/project scope | 关闭通道、撤销设备和会话、incident review | Security |
| R-24 | Provider 成本失控（重复生成、修复循环、长上下文） | 4 | 4 | 16 | 全局月预算 30 元；不设单项目硬预算；submit 前计入已用与未结算估价；缓存、幂等、Flash 路由 | 预计超额即暂停并提示用户选择继续付费、改用 Mock、取消或推迟；不静默扣费 | Product/Operations |
| R-25 | Web/Unity 预览结果与最终 build 差异大 | 3 | 4 | 12 | 同一 artifact version/hash；Unity screenshot/playtest 是最终证据；颜色/材质基线 | 标记 build mismatch，阻止 final approval | Frontend/Unity |
| R-26 | SSE/断线导致 UI 丢进度或重复提交 | 3 | 3 | 9 | event id/Last-Event-ID、持久化 run state、mutation idempotency | 重连读取状态，不重新创建 job | Web/Backend |
| R-27 | 状态机或下游 stale 传播错误 | 3 | 5 | 15 | transition property tests、dependency graph tests、不可变版本、事务 | 冻结 stage，重建依赖投影，人工核对 approvals | Backend/QA |
| R-28 | 数据库/本地对象文件不一致 | 3 | 4 | 12 | staged upload → verify → DB commit；outbox；垃圾回收只处理无引用对象 | reconciliation job 修复/隔离；不自动删有疑问对象 | Backend/Operations |
| R-29 | 过早搭建宏大多 Agent/微服务导致进度失控 | 4 | 3 | 12 | modular monolith API；单 Co-Creator；有触发阈值才拆服务/加队列 | 停止扩展，按 Milestone acceptance 重排 | Tech Lead/Product |
| R-30 | PHASE 0 后未经确认自动进入开发 | 1 | 5 | 5 | TASKS 明确 stop gate；所有技术选择标 Proposed/Open | 不创建代码骨架，等待用户书面确认 | Project Lead |

## 必须在 MILESTONE 1 前关闭或有明确接受者的风险

1. **R-03**：当前已确认无官方 Unity MCP entitlement，因此以 Coplay 为 MVP 默认；M5 再对官方 adapter 做 capability spike。
2. **R-12/R-13/R-14**：现有素材已确认作为 curated demo candidates，但权利未核验前仅限内部演示；继续补全知识来源、授权和外部上传边界。
3. **R-18/R-19**：确定现有 Unity 项目的版本控制、备份和大文件策略。
4. **R-24**：已确定全局月预算 30 元及超额提示策略；M3/M4 必须验证供应商费用可观测性。
5. **R-30**：由用户确认 Phase 0 结论，才可开始 MILESTONE 1。

## 安全红线

- 不把任何 Provider key 放到 browser、Unity package、生成游戏或可下载项目中。
- 不向 Agent 暴露 shell、PowerShell、任意 C# eval、任意反射或任意文件路径。
- 不在未经批准时自动删除、覆盖或移动用户资产。
- 不因“模型说已完成”就标记编译、测试、Playtest 或 build 成功；只接受工具实证。
- 不把远端临时 URL、聊天内容或 embedding 当作文化知识的事实源。
- 不让 approval 自动继承到修改后的版本。
- 不在没有明确许可的情况下把用户资料上传给外部模型或生成服务。

## 风险复审节奏

- 每个 Milestone 开始和结束复审一次。
- Unity/DeepSeek/Provider 版本升级前复审相关技术、价格、terms 和安全风险。
- 任何 Unity 写错项目、密钥暴露、许可争议或文化事实纠错均触发即时复审，而非等待里程碑。

## MILESTONE 6 复审（2026-08-10）

- R-06：构建状态和 Unity 事件使用单调序号；Domain Reload 后通过幂等恢复入口继续，第二次真实复跑无人干预完成。
- R-17：Bridge 强制最多三轮、错误指纹、生成脚本长度/API/命名空间校验；真正的 Agent 补丁仍须在 M8/M9 经过预览与审批。
- R-22：重试与人工接管继续使用 loopback Bridge token，浏览器不能直接取得令牌。
- R-26：SSE 支持 `after` 回放，刷新从已保存任务 ID 恢复；自动测试证明重连不会重复执行构建。
- 新边界：桥接任务请求会持久化到 D 盘以支持重启后重试，其中包含生成 C#；该目录必须保持本机权限，导出研究数据时必须排除源代码和令牌。

## MILESTONE 7 复审（2026-08-10）

- R-14/R-15：每个模板定义都必须包含中文文化可玩性说明；目标模板采用点漆落点而非暴力射击叙事。
- R-16：五类模板共享同一运行时契约并分别通过 EditMode/PlayMode 测试，Demo 与正式组件没有第二套逻辑。
- R-25：当前 Demo 使用基础黑白几何，仅验证机制；正式文化资产仍绑定已批准 artifact hash，不能把示意几何误认为最终资产。
- 新边界：模板胜负条件为可配置机制内核，不等同于文化事实；任何对漆艺工序的新增或修改仍须知识引用与人工审批。

## MILESTONE 8 复审（2026-08-10）

- R-01/R-02：未批准提议不调用 Bridge；批准后仍经过 token、路径、动作、Transform、命名空间和危险 API 校验。
- R-06/R-18：每次 Unity 写操作先复制当前 Scene checkpoint；撤销同时恢复 Scene，并只清理 receipt 指定的共创生成脚本。
- R-17：Agent 不生成任意编辑器代码；可执行逻辑来自 M7 allowlist 组件，生成脚本只保存受控交互说明和审计意图。
- R-26/R-28：共创状态、preview、receipt、checkpoint 和撤销时间持久化到 PostgreSQL；API 重启恢复计数与最终状态一致。
- 新边界：checkpoint 会累积磁盘空间；M11 可提供只删除无引用旧 checkpoint 的显式维护动作，当前不自动删除。

## MILESTONE 9 复审（2026-08-10）

- R-01/R-27：试玩修改创建逻辑新版本时旧批准立即失效；真实验证项目退回 logic_review，重新批准后当前/批准版本同为 2。
- R-06/R-17：再次试玩前必须等待 Domain Reload、重新连接 MCP 并确认 Console 错误为 0；失败时不进入 Play Mode。
- R-07/R-16：当前无 DeepSeek key，明确记录 Mock provider/model；同一 Provider contract 已在 M3 测试，不将 Mock 结果标记为真实 DeepSeek。
- R-26/R-28：Playtest Session 绑定 build/version/feedback/change/receipt，API 重启后完整恢复。
- 新边界：人工 1–5 评分不是客观性能指标；M10 导出时保留其“玩家评价”语义，不与编译成功或系统质量混为一谈。

## MILESTONE 10 复审（2026-08-10）

- R-09/R-21：匿名导出安全测试确认不包含密钥名、原始玩家想法、生成脚本正文和真实项目编号；文件只写入 E 盘受控研究目录。
- R-26/R-28：时间线由持久化事件、版本、审批、Unity receipt 与试玩会话重建；API 重启后 67 条事件和全部指标一致。
- R-27：审批记录绑定阶段与 artifact version；建议决定与试玩批准同步，避免“已执行但研究记录仍待定”。
- 新边界：稳定匿名编号仍可能在组合外部数据时产生重识别风险；对外共享前需最小化时间精度、审查小样本并建立保留期限。

## MILESTONE 11 最终复审（2026-08-10）

- R-25：桌面与 390 像素手机视口完成真实浏览器全页检查；黑白灰扫描异常 0、横向溢出 0。
- R-03/R-04：最终 Unity EditMode/PlayMode 各 5/5，Console 错误 0；当前继续固定 Coplay 适配器，不自动升级。
- R-07/R-12/R-13：未配置生产 Provider 凭据与素材授权时明确显示精选模拟模式，禁止把演示证据表述为真实供应商或可公开发行资产。
- R-17/R-22：Bridge 最终 6/6；仍坚持 loopback、受控工具、最多三轮修复、预览审批和人工接管边界。
- 最终开放风险：生产发布前仍需关闭真实供应商凭据、素材许可、部署安全、数据库备份和研究数据治理五类事项；这些不影响当前单机精选演示版验收。

## MILESTONE 2 复审（2026-08-10）

- R-01/R-27：Approval Gate 已进入数据库事务，审批绑定 artifact version；并发审批测试证明只有一个请求成功，失败事务不推进 revision。
- R-28：资产路径、MIME、大小与 SHA-256 已持久化，关闭 API 和 PostgreSQL 后重启仍能逐项恢复；备份恢复到隔离数据库后的关键表计数完全一致。
- 新的运维边界：本地 PostgreSQL 账号和密码仅供 loopback 开发环境使用，不可直接复用到共享或生产部署；生产环境必须改用 secret manager、独立账号、TLS 和受控备份。
- Outbox 当前只提供事务内事件与幂等写入，尚无外部副作用 worker；在 M3/M4 首次启用真实外部调用前必须补 lease、重试、dead-letter 与端到端幂等测试。
