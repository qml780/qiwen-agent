# MILESTONE 5 验收报告

## 完成情况

- Unity 版本：6.3 LTS `6000.3.18f1`，可见编辑器运行，非 Batch Mode。
- Unity MCP：Coplay 固定提交 `c21bf496bca87d54e75bad048563c3adb1782081`，本地 HTTP MCP `127.0.0.1:8080`。
- Local Bridge：仅监听 `127.0.0.1:4567`，令牌校验、D/E 路径白名单和 Unity/MCP 分离健康检查已启用。
- 运行工作区：`D:\qiwen-runtime\unity-projects\QIWEN-VerticalSlice`；E 盘保留权威源与验收产物。
- 已完成点击构建后的完整链路：连接 Unity → 创建 Scene → 导入 GLB/WAV → 创建对象 → 生成并挂载 C# → 编译 → Play Mode。
- 相机已配置 `AudioListener`，漆碗 `AudioSource` 可循环播放，生成脚本驱动漆碗旋转。

## 真实验收证据

- 最终结果：`success: true`，阶段“完成”，时间 `2026-08-11T01:05:56.2994647Z`。
- 事件链：30、40、50、60、70、75、85、90、95、100，最后一项确认进入 Play Mode。
- 最终复跑：C# 编译错误 0、异常 0、AudioListener 警告 0。
- Unity 首次 D 盘运行工作区导入：12.100 秒；项目加载：16.259 秒。
- 生成场景：`Assets/QIWEN/Scenes/漆问最小切片.unity`。
- 生成脚本：`Assets/QIWEN/Runtime/LacquerBowlExperience.cs`。

## 测试与修复

- 修复 E 盘 Git 所有权导致的 UPM Git 依赖失败，改用固定提交本地包。
- 修复 Unity 默认 C 盘包缓存 SQLite I/O 问题，使用 `D:\qiwen-runtime\unity-cache`。
- E 盘不支持目录联接且 Unity Library 极慢，采用 E 源码 + D 运行工作区方案。
- 增加 Unity MCP 自动引导脚本与显式“继续最小垂直切片”恢复入口。
- 修复重试仍处于 Play Mode 的状态问题：正式通过 MCP `manage_editor: stop` 退出。
- 修复相机缺少 AudioListener 的音频可听性问题，并完成无警告复跑。

## 已知问题

- Web 当前构建任务仍需在 M6 中接入真实事件回放、断线恢复、Console、重试与人工接管。
- Unity 自身仍会写少量编辑器偏好、许可和 GI 缓存到用户配置目录；项目生成文件、运行工作区和自定义日志均位于 D/E。
- E 盘留下 `Library-source-backup` 和一次未完成迁移的 `Library-slow-backup`，均为可重建缓存备份，未自动删除。

## 决策

- M5 真实垂直切片门槛已通过，允许进入 M6。
- 后续 Unity 自动化以 D 盘运行工作区执行，E 盘作为权威源码和交付产物位置。
