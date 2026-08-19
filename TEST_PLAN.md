# 测试计划

## 自动测试

- 单元：状态分组、schema、预算、Provider、研究指标。
- API/数据库：完整 happy path、越级门禁、并发审批、事务回滚、幂等、迁移、重启恢复、匿名导出。
- Bridge：健康状态、身份/令牌、任务、重试、SSE、共创与试玩流程。
- Unity：五个模板的 EditMode 与 PlayMode；构建、Domain Reload、Console 和 Play Mode 实证。
- Web：TypeScript strict、组件/领域单测、生产构建。

## 人工与端到端

完整路径必须覆盖知识、讨论、拒绝/接受/修改建议、逐阶段审批、媒体预览、Unity 构建、玩家组装、试玩、反馈、最小修订、重新批准、编译和再次试玩。专门验证智能助手不能批准、不能跳过概念、逻辑未批准不能构建、不能自动发布。

## 故障恢复

覆盖 DeepSeek/媒体超时与失败、腐坏 GLB、Unity 未安装、项目缺失、MCP 断线、编译错误、素材缺失、网络中断和服务重启。任何失败都不得导致项目消失。

## 当前基线

API 34/34、Bridge 6/6、Web 3/3 与生产构建、Unity EditMode 5/5、PlayMode 5/5、Console 错误 0。
