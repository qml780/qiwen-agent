# MILESTONE 4 REPORT — Asset Providers

## Completed

- 按 Image → 3D → Music 顺序实现统一 `AssetProvider` 的 validate、submit、poll、cancel 与 Mock fallback。
- 图像真实 Adapter 使用即梦企业 API `CVSync2AsyncSubmitTask/GetResult`，`req_key` 可配置，默认采用已研究的 `t2i_v40_jimeng`。
- 三维真实 Adapter 使用腾讯混元生3D OpenAI-compatible submit/query，模型版本配置为 3.1，支持文本和参考图。
- 音乐真实 Adapter 使用腾讯云 MPS `CreateAigcAudioTask/DescribeAigcAudioTask` 官方 SDK；模型名和版本不写死。
- 三类 Mock 与真实 Adapter 返回同一 `ProviderTask`，没有凭据时自动使用 Mock，不发送付费请求。
- Provider 远端结果先摄取至 `E:\漆vr游戏\storage\objects`，使用 SHA-256 content addressing，不依赖临时 URL。
- 摄取校验覆盖 PNG/JPEG/WEBP、GLB 2.0 header/JSON chunk/mesh/三角面、WAV/MP3/FLAC 签名以及 WAV 时长/采样率。
- 每次生成创建新的 artifact/asset version；重新生成保留旧版本，Approval Gate 仍由后端限制。
- LLM 与资产 Provider 共用 30 元全局月预算；预计超额时返回继续付费、改用模拟、取消、推迟。

## Tests

- API 全套：23/23 通过。
- Provider 独立契约：12/12 通过，包括三类 Mock、即梦 submit/poll、混元3D submit/query、腾讯 MPS request/describe、取消幂等、签名/hash 校验和错误格式拒绝。
- Web：TypeScript、ESLint、3/3 单元测试和 production build 全部通过。
- Alembic：隔离数据库完成 M4 upgrade → M3 downgrade → M4 upgrade，成本字段正确回滚恢复。
- 运行时 health：数据库正常；当前无供应商凭据，明确显示 `mock-image / mock-3d / mock-music`；预算已用 0 元、剩余 30 元。

## Known Issues

- 当前没有即梦、混元生3D或腾讯 MPS 凭据，因此没有声称真实生成成功；真实 Adapter 以官方 SDK/HTTP 契约测试验证。
- 供应商模型、价格和账户 entitlement 仍需在提供凭据后进行小额 sandbox 验收。
- 真实远端对象 URL 仅允许 HTTPS，并拒绝本地、保留或私网地址，避免 Provider 结果触发 SSRF。

## Next

用户已连续授权，直接进入 MILESTONE 5；先验证本机 Unity 与 MCP 的真实可用性，只有完整可见垂直切片成功才进入 M6。
