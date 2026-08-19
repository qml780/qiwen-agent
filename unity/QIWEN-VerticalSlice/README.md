# 漆问 Unity 最小垂直切片

此项目由“漆问本地桥接”以可见方式打开。桥接通过 Coplay Unity MCP 调用菜单 `漆问/执行最小垂直切片`，依次创建场景、导入 GLB 与 WAV、生成运行时 C#、等待编译、挂载组件并进入试玩。

运行结果写入 `QIWEN/Results/vertical-slice.json`，逐步事件写入 `QIWEN/Results/vertical-slice-events.jsonl`。这些状态文件全部保留在 E 盘项目内。
