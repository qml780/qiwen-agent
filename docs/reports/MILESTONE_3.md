# MILESTONE 3 REPORT — DeepSeek Agent

## Completed

- 实现统一 `LLMProvider`，Mock 与 DeepSeek 共享对话和结构化生成契约。
- Pro 用于结构化概念、逻辑与代码提议，Flash 用于普通共创对话；模型名、超时、重试和价格均由环境变量配置。
- 多轮历史、原始玩家想法、Agent 建议及玩家接受/拒绝/修改/讨论全部持久化。
- Concept 与 Logic 使用 JSON mode、Pydantic schema 和最多一次修复；Knowledge Alignment 使用 Strong/Moderate/Weak 并保存机制映射和解释。
- 增加 SSE 状态/完成/错误事件；断开请求会取消当前生成协程。
- 429、5xx、网络超时使用有界重试；不合法响应明确失败，不假装成功。
- 每次调用保存 provider、model、task、token、人民币估算成本和 prompt version。
- 全局月预算为 30 元；预计超额时返回继续付费、改用模拟、取消、推迟四种选择，不静默超支。

## Tests

- API：10/10 通过。
- 覆盖完整 Mock 流程、Approval Gate、并发审批、持久化、多轮对话、原始想法不变、建议决策幂等、结构化 Alignment、预算拦截、SSE 与 DeepSeek Pro 路由/usage 契约。
- Alembic：隔离数据库完成 baseline → M3 head → M2 → M3 head；确认新增列和表可正确回滚、恢复。
- Web：TypeScript、ESLint、3 个单元测试和 Next.js production build 全部通过。

## Known Issues

- 当前环境没有 `DEEPSEEK_API_KEY`，因此没有产生真实费用；真实账号权限和账单只能在提供密钥后小额验证。
- SSE 当前发送可观察状态与最终结果，不暴露模型内部思维链。
- 价格由环境变量保存为人民币估算，供应商调价时必须更新配置。

## Decision

用户已明确连续授权完成剩余 MASTER SPEC，因此 M3 测试通过后直接进入 M4，不等待新的阶段口令。
