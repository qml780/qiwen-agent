# MILESTONE 9 验收报告

## 完成情况

实现并真实跑通：

`Play → Feedback → Agent Modify → Compile → Play Again`

- 试玩会话绑定项目、成功构建任务、首次逻辑版本和原审批 ID。
- 首次反馈包含中文评价、1–5 分评分和记录时间。
- 代码智能助手根据反馈提出最小修改；无 DeepSeek key 时使用同契约 Mock，不伪装真实调用。
- 提议修改创建逻辑新版本，并立即移除旧逻辑批准，项目退回逻辑审阅。
- 玩家批准新逻辑和 Unity 差异后才建立 checkpoint、写受控生成区、等待 Domain Reload、检查 Console 并再次进入 Play Mode。
- 最终反馈、评分、编译证据和再次试玩证据持久化并可在中文 Web 界面回看。

## 真实闭环证据

- Playtest Session：`f6e8dfe4-8c59-4f21-842d-f9a855ea88a5`。
- 绑定成功构建：`2e67f176-3b1a-4d85-b8c5-24adf69b7ac3`。
- 初始逻辑：第 1 版，审批 `feb2d7c5-febf-45e1-ad18-546ccae2fb63`。
- 首次评价：3/5；“薄髹层增加得太快，希望每层完成后有更清晰的节奏停顿和反馈。”
- 智能助手：`mock/mock-code-proposal-v2`；建议记录 `e38a7603-8e8e-47d0-83ac-ef263c50f533`。
- 修订提议：`2f274f6a-e024-4ab1-a90f-94f4f647f666`，逻辑升级至第 2 版。
- Freshness 验证：提议后 `current_stage=logic_review`，`approvals.logic=null`；批准后 `current_stage=ready_to_build`，当前逻辑与批准均为第 2 版。
- Unity：checkpoint 创建成功、脚本写入成功、编译错误 0、`playMode=true`。
- 最终评价：5/5；“节奏停顿和反馈已经清晰，可以继续保留。”
- UI 证据：`D:\qiwen-runtime\evidence\m9-playtest-final.png`。

## 测试与持久化

- Alembic：`20260810_0006 (head)`，新增 `playtest_sessions`。
- API 测试：33/33 通过，新增完整 freshness、批准、编译回执、再次试玩和完成测试。
- Bridge 测试：6/6 通过。
- Web TypeScript 检查通过，前端测试 3/3。
- Unity 最终复测：EditMode 5/5、PlayMode 5/5、Console 错误 0。
- API 重启后 Session 状态仍为 completed，构建 ID、3→5 评分、逻辑 1→2、0 编译错误和再次试玩证据完全恢复。
- 项目重启恢复：当前阶段 ready_to_build，逻辑第 2 版，批准版本第 2 版。

## 联调中发现并修复

- 修复在 Play Mode 中直接启动 EditMode tests 的失败：测试辅助器先显式退出 Play Mode，再有界等待 Test Runner。
- Bridge 的 `playAfterApply` 会等待脚本编译/Domain Reload、重新连接 MCP、读取 Console；存在错误时停止再次试玩。
- Web 完成态由单一评分扩展为完整证据：构建、逻辑修订、首次反馈、编译、再次试玩和最终反馈。

## 已知边界

- 当前环境未配置 DeepSeek key，因此真实闭环使用 Mock 代码智能助手；M3 已实现并测试 DeepSeek provider，同一 endpoint 在配置 key 后切换。
- Session 的 `logic_version` 固定表示首次试玩版本；修订版本保存在 `evidence.proposed_logic_version`，避免改写历史含义。
- 试玩的自动性能遥测属于后续扩展；本里程碑记录人工评价、编译和 Play Mode 工具证据。

## 决策

- M9 完成规则已满足，按用户连续授权进入 M10。
- M10 将把项目活动、Unity receipt、建议决定、版本、批准和 Playtest 统一成可导出研究时间线，并排除密钥、思维过程和生成脚本正文。

