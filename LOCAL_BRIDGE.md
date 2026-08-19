# 本地桥接

Local Bridge 是 Node 24/TypeScript 独立进程，默认监听 `127.0.0.1:4567`，只接受 loopback、配对令牌和受允许来源。它不持有 DeepSeek 或媒体 Provider 密钥。

职责包括 Unity 实例/项目身份验证、能力探测、构建与共创任务队列、SSE 事件、幂等重试、Domain Reload 恢复、Console 读取、检查点和人工接管。任务及事件写入 D 盘运行目录，API 重启或网页重连后可以按事件序号恢复。

禁止公网入站、任意命令、任意文件路径和宽泛 MCP 工具。状态至少区分桥接、Unity 编辑器、工具通道、排队、执行、编译、成功、失败与已接管。

