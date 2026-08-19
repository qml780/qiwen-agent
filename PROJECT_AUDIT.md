# 漆问 Agent 项目架构与冷启动审计

> 审计日期：2026-08-15—2026-08-19  
> 最高验收依据：`MASTER_SPEC.md`（本次审计不修改该文件）  
> 状态：本轮审计完成；最终结论见 `FINAL_ACCEPTANCE_REPORT.md`。

## 1. 系统边界

本项目是一个桌面优先的中文 Web 共创工作台。玩家从预置漆艺知识出发，经过自由想法、Agent 讨论、概念、视觉、2D/3D 素材、音乐、玩法逻辑和多道人工批准门，最终通过本地桥接与 Unity MCP 操作可见的 Unity Editor。网页不是游戏本体，也不能把静态预览冒充 Unity 游戏。

## 2. 代码与运行架构

| 层级 | 实现 | 主要路径 | 当前审计结论 |
|---|---|---|---|
| Web 前台 | Next.js 16、React 19、Three.js | `apps/web/app`、`apps/web/components`、`apps/web/lib` | 已发现首页、知识库、项目列表、工作台和 3D 查看器；待构建与浏览器回归 |
| 后端 API | FastAPI、Pydantic、异步 SQLAlchemy | `apps/api/app/main.py`、`domain.py`、`repository.py` | 路由覆盖项目、素材、Agent、审批、Unity、试玩和研究导出；待逐路由实测 |
| 状态与持久化 | PostgreSQL 18、Alembic | `apps/api/app/models.py`、`migrations` | 数据库曾异常终止；这是当前链接中断的直接系统级原因之一 |
| Agent / 文本生成 | `LLMProvider` 边界、后端转发 | `apps/api/app/providers.py` | 密钥不进入前端；最近一次真实 Agent 请求返回 502，待外部依赖复测 |
| 图片 / 3D / 音乐 | Provider 边界、对象存储、版本记录 | `apps/api/app/asset_providers.py`、`object_storage.py` | 存在真实 Provider 与本地/精选回退；回退不得计作真实生成 PASS |
| 知识库 / RAG | 预置 V2 JSON、结构化检索上下文 | `apps/api/app/knowledge_v2.json`、`apps/web/data/knowledge-v2.json` | 待用至少五个知识点验证检索与机制转译 |
| Local Bridge | Node.js HTTP 服务、令牌鉴权、任务持久化 | `apps/bridge/src` | 默认 4567；只允许 D/E 盘路径；当前未运行 |
| Unity 执行 | Unity 6 工程、Coplay MCP、五种模板、自定义 Editor 工具 | `unity/QIWEN-VerticalSlice` | 工程声明 Unity 6000.3.18f1；本机尚未发现可执行 Editor，待检查 D 盘运行时 |
| 证据与研究 | 活动、试玩、导出、日志 | `apps/api/app/research.py`、`playtests.py`、`exports`、`logs` | 待验证真实闭环与导出内容 |

## 3. 主要数据流

1. Web 只调用 `http://127.0.0.1:8000`，外部 API Key 仅由后端读取。
2. 后端以正式状态机和数据库审批记录限制阶段前进。
3. 生成产物写入 D 盘对象存储，并以资产和版本记录关联项目。
4. Unity 构建由玩家触发：API → Local Bridge → Unity MCP → 可见 Unity Editor。
5. Bridge 对路径、令牌、模板和生成脚本做白名单校验，任务证据写入 `D:\qiwen-runtime\bridge\jobs`。

## 4. 冷启动环境基线

| 项目 | 检测结果 |
|---|---|
| Node.js | v24.11.1 |
| npm | 11.6.2 |
| pnpm | 11.19.0；根工作区配置与 pnpm 不完全匹配，但项目声明 npm |
| Python | 系统 3.12.10；项目另有 `.venv`，待单独验证 |
| Git | 2.53.0；当前项目目录不是 Git 工作树 |
| Java | PATH 中不存在；当前 Web/API 不直接需要，相关 Unity 工具若依赖则会阻断 |
| Unity | `C:\Program Files\Unity\Hub\Editor` 未发现版本；配置期待 `D:\qiwen-runtime\Unity\6000.3.18f1\Editor\Unity.exe`，待核实 |
| PostgreSQL | 运行时与数据均在 D 盘；冷启动前数据库已异常退出 |

## 5. 配置审计

- `.env` 中生成服务、图片和 3D 凭据均已配置；报告只记录掩码，绝不输出完整值。
- 月预算为 30 元；当前多个成本估算为静态配置，必须验证是否真实累计与超额询问。
- 所有项目对象、Unity 工程、Bridge 令牌和研究导出路径均位于 D 盘，符合本机文件约束。
- 音乐优先指向本机 8001；该端口在本次冷启动前未监听。
- 前端公开变量仅为 API 地址，未发现密钥配置到 `NEXT_PUBLIC_*`。

## 6. 已确认的启动前故障

1. **数据库异常退出**：PostgreSQL 日志显示 23:34:57 后端进程在提交时被系统异常终止，随后数据库终止其他进程并重初始化；检查时 55432 已不监听。
2. **僵而不健康的 API**：8000 仍监听，但健康请求因数据库不可用而超时，启动脚本未能持续监测数据库掉线。
3. **Agent 外部请求失败**：最近一次 `/agent/respond` 为 502；前台中文化后只显示连接中断，未给出可追踪错误编号。
4. **Unity 环境未证实**：Unity 项目和 MCP 包存在不等于本机 Editor 可执行或真实构建成功。
5. **模板语义风险**：现有五个模板覆盖模拟、时机、收集、工序谜题和目标互动；需要验证 Agent 玩法与模板选择是否一致，不能仅因知识文本含“顺序”就错误选择谜题模板。

## 7. 后续强制验证清单

- 完全停止后，独立验证数据库、迁移、API、Web、音乐服务、Bridge 和 Unity。
- 执行前端安装/类型检查/测试/生产构建，后端导入/迁移/测试，Bridge 构建/测试。
- 以全新项目走完真实用户路径，并保留请求、数据库、文件和可见界面证据。
- 至少五个知识点验证 RAG；验证自由输入、拒绝/修改、审批门和任意阶段单独修改。
- 图片、音乐、3D 和文本分别辨别真实生成、静态回退和外部阻断。
- Unity 必须以真实 Editor 打开、写入、编译、读 Console、运行 Play Mode 才可通过。
- 验证刷新、返回、第二项目、删除、版本、素材库、预算、错误恢复、发布、画廊和评分。

## 8. 2026-08-19 审计收口

- 数据库、Web、API、Bridge、本地音乐和 Unity MCP 均已恢复并通过冷启动。
- Unity 可执行文件已确认位于 `D:\qiwen-runtime\Unity\6000.3.18f1\Editor\Unity.exe`；真实 `topdown-dodge` 构建和 Play Mode 通过。
- API 62/62、Web 3/3、Bridge 8/8；Web lint/typecheck/production build 通过。
- 本地音乐真实生成通过，两段同请求版本哈希不同。
- 当前图片外部主机连接失败，六项新素材未生成，完整当前项目 E2E 因此 BLOCKED。
- 发布/社区画廊不存在，符合 `MASTER_SPEC.md` 第 76 节 MVP 禁止做社区；试玩评分存在。
- 最终审批已改为独立玩家操作，最终反馈不会自动完成项目。
