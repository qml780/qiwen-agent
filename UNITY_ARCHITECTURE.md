# Unity 架构

目标版本为 Unity 6.3.18f1。Web 不直接控制编辑器：API 创建受审批约束的任务，loopback Local Bridge 验证项目身份和令牌，再通过适配器调用 Unity MCP。当前环境使用 Coplay adapter；官方 Unity MCP 无 entitlement 时安全失败，Mock 只用于非真实测试。

Unity 工具限制为创建/打开指定项目与场景、导入已批准资产、创建受控对象/组件、写 generated area、编译、读 Console、运行测试和进入/退出 Play Mode。禁止任意 shell、eval、反射或任意路径。

每个动作写 receipt；域重载后通过幂等键继续。自动修复最多三轮，使用错误指纹且只能修改受控生成区。玩家可在不中断 Unity 的情况下人工接管。M7 五类模板各有 schema、运行时组件、示例场景及 EditMode/PlayMode 测试。

