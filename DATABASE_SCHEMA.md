# 数据库结构

PostgreSQL 是业务事实源，Alembic 管理迁移。核心实体包括：

- `projects`：当前阶段、revision、玩家原始想法和进度。
- `knowledge_entries`：精选知识与来源元数据。
- `conversation_messages`、`agent_suggestions`：多轮对话、结构化建议和玩家决定。
- `artifact_versions`、`approvals`：不可变产物版本与绑定版本的审批历史。
- `assets`、`provider_jobs`：对象引用、SHA-256、媒体元数据、来源、许可、费用和供应商任务。
- `activity_log`、`domain_events`、`outbox`：审计、领域事件和外部副作用幂等边界。
- `unity_changes`、`playtest_sessions`：预览/批准/检查点/回执、试玩版本、反馈与再次试玩证据。
- `research_exports`：匿名编号、格式、事件数、文件哈希和 E 盘路径。

所有并发修改校验 project revision；批准与 artifact version 绑定；mutation key 防止重复写入。

