# 漆问

漆问是一套桌面优先的人机共创游戏工作室。玩家从漆艺知识和自己的想法出发，与单一共创助手逐阶段设计概念、视觉、三维、音乐和游戏逻辑；每一步由玩家批准后，才通过本地桥接在可见的 Unity 编辑器中构建、试玩和修订。

## 架构

- `apps/web`：Next.js 工作室。
- `apps/api`：FastAPI、状态机、DeepSeek/媒体 Provider、研究导出。
- `apps/bridge`：Node/TypeScript loopback Unity Bridge。
- PostgreSQL：项目、版本、审批、对话、任务、Unity 回执和试玩记录。
- `unity/QIWEN-VerticalSlice`：Unity 源工程。

详细说明见 `ARCHITECTURE.md`、`LOCAL_BRIDGE.md` 与 `UNITY_ARCHITECTURE.md`。

## 环境要求

- Windows 10/11
- Node.js 22 或更高版本
- Python 3.12 或更高版本
- PostgreSQL 18
- Unity 6.3.18f1（只在真实构建/试玩时需要）

## 安装与环境变量

```powershell
git clone https://github.com/qml780/qiwen-agent.git
cd qiwen-agent
npm install
Copy-Item .env.example .env
Get-Content scripts\database\start-postgres.ps1 -Raw -Encoding UTF8 | Invoke-Expression
python -m venv .venv
.venv\Scripts\python -m pip install -e apps\api
Push-Location apps\api
..\..\.venv\Scripts\python -m alembic upgrade head
Pop-Location
```

所有密钥只写入后端 `.env`，禁止放入 `NEXT_PUBLIC_*`、浏览器、Bridge、Unity 或版本库。完整变量和默认值见 `.env.example`。

## 一键运行

双击根目录 `打开漆问.cmd`。它会启动 PostgreSQL、执行迁移、启动 API 与网页并打开浏览器。访问：

`http://127.0.0.1:3000`

## 分别运行

后端：

```powershell
cd qiwen-agent\apps\api
..\..\.venv\Scripts\python -m app.server
```

网页：

```powershell
cd qiwen-agent
npm run dev:web
```

本地桥接：

```powershell
cd qiwen-agent\apps\bridge
npm run build
npm run start
```

Bridge 默认监听 `127.0.0.1:4567`，Unity MCP 默认监听 `127.0.0.1:8080/mcp`。

## 聊天与代码模型

当前运行配置优先使用米醋 OpenAI 兼容接口：对话为 `gpt-5.6-terra`，结构化设计与 Unity 代码为 `gpt-5.6-sol`。只在后端 `.env` 配置 `MICU_LLM_API_KEY`，浏览器与 Unity 不接触密钥。若未配置米醋 Key，仍可使用 MASTER SPEC 原定的 DeepSeek adapter；两者都未配置时使用同契约精选模拟服务。模型输出先做结构校验，代码仅作为提议，不能替玩家批准或直接写 Unity。

## Unity MCP

安装 Unity 6.3.18f1，打开 D 盘运行工程，并启用已固定的 Coplay MCP 包。Bridge 会验证项目路径、实例和能力。官方 Unity MCP adapter 保留，但当前账号无 entitlement 时会明确失败并保持 Coplay，不会误连其他工程。

## 精选模拟与真实生成服务

默认无需任何付费凭据即可跑完整流程。当前真实图像 Provider 为米醋 `gpt-image-2-pro`，三维为混元生 3D，音频暂时保留精选模拟服务；分别配置有效凭据后仍使用相同任务、验证、摄取和审批路径。`/health` 的 Provider 名称表示已配置路由，供应商账号是否有效仍以真实请求结果为准。全局月预算 30 元，预计超额时暂停并提示选择，不会静默扣费。

## 数据与备份

- PostgreSQL：`D:\qiwen-data\postgres18`，端口 `127.0.0.1:55432`。
- 运行与证据：`D:\qiwen-runtime`。
- 素材、备份和研究导出：由 `.env` 中的路径变量配置，默认不提交到版本库。

```powershell
Get-Content scripts\database\backup.ps1 -Raw -Encoding UTF8 | Invoke-Expression
```

## 验证

```powershell
npm run typecheck:web
npm run test:web
npm run build:web
apps\api\.venv\Scripts\python -m pytest apps\api\tests
```

Unity 测试必须在可见编辑器中运行 EditMode 与 PlayMode，并读取 Console；模型文字不能替代测试证据。

## 常见问题

- 网页打不开：确认 3000 端口监听，重新运行 `打开漆问.cmd`。
- 显示“创作室服务尚未启动”：确认 API 的 `/health` 可访问并检查 PostgreSQL。
- Unity 未连接：保持正确工程在可见编辑器中打开，检查 Bridge 4567 与 MCP 8080，再点重试。
- Domain Reload 后看似暂停：等待 Bridge 恢复连接；任务会按事件序号继续，不要重复提交。
- 真实生成不可用：检查后端凭据、预算和供应商任务；可选择回到精选模拟模式，项目不会丢失。
