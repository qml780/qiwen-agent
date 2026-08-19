import type { BuildRequest, UnityAdapter } from "../types.js";

const stages = ["启动编辑器", "连接工具通道", "创建场景", "导入画面", "导入音频", "创建对象", "生成脚本", "挂载脚本", "编译", "试玩"] as const;

export class MockUnityAdapter implements UnityAdapter {
  readonly name = "可重复模拟适配器";

  async health() {
    return { unity: "已连接" as const, mcp: "已连接" as const, detail: "模拟模式仅用于自动化测试" };
  }

  async build(_request: BuildRequest, emit: Parameters<UnityAdapter["build"]>[1], context: Parameters<UnityAdapter["build"]>[2]) {
    for (const [index, stage] of stages.entries()) {
      if (context.signal.aborted) throw new Error("构建已由玩家接管");
      emit({ stage, progress: (index + 1) * 10, message: `模拟完成：${stage}`, level: "成功", source: "桥接" });
    }
  }
}
