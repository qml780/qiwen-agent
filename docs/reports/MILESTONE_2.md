# MILESTONE 2 验收报告

## 完成情况

- 接入 PostgreSQL、SQLAlchemy 与 Alembic，持久化项目、知识、对话、素材、产物版本、审批、进度和活动日志。
- 产物版本与审批历史不可变；项目 revision 提供并发保护。
- 新增 Provider job、domain event、transactional outbox 和对象 SHA-256/MIME/大小等元数据。
- mutation key 重放保持幂等；并发审批只有一个事务能推进状态。
- 完成数据库迁移升降级、事务回滚、服务和数据库重启恢复、隔离数据库备份恢复验证。

## 验收

- 浏览器、API 和 PostgreSQL 依次关闭重启后，项目阶段、版本、审批、素材引用与活动记录完整恢复。
- 二进制对象引用与哈希一致；失败事务不推进版本或 outbox。
- 最终 schema 已持续升级至 M10 研究记录迁移，API 全量回归 34/34 通过。

## 已知边界与决策

- 当前数据库账号、密码和 loopback 配置只适用于本地开发；生产部署必须使用独立 secret、TLS、备份与访问控制。
- outbox 在 M2 建立事务边界，外部供应商的租约、重试与死信行为在 M3/M4 完成。
- M2 完成后按用户授权进入 M3。
