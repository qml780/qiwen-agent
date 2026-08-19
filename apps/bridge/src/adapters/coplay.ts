import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { access, copyFile, mkdir, readFile, readdir, unlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { McpHttpClient } from "../mcp-client.js";
import type { BuildEvent, BuildRequest, UnityAdapter } from "../types.js";

const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export class CoplayUnityAdapter implements UnityAdapter {
  readonly name = "Coplay Unity MCP";

  constructor(private readonly unityPath: string, private readonly mcpUrl: string) {}

  async health() {
    let installed = false;
    try { await access(this.unityPath); installed = true; } catch { /* 由界面显示安装状态。 */ }
    let unity: "已连接" | "未连接" = "未连接";
    let mcp: "已连接" | "未连接" = "未连接";
    try {
      const client = new McpHttpClient(this.mcpUrl, 1_500);
      await client.ping();
      mcp = "已连接";
      await client.callTool("manage_scene", { action: "get_active" });
      unity = "已连接";
    } catch { /* 编辑器或插件尚未连接。 */ }
    const detail = !installed ? "未检测到 Unity 编辑器" : mcp === "未连接" ? "Unity 已安装，MCP Server 尚未启动" : unity === "未连接" ? "Unity 已安装，等待编辑器与 MCP 插件连接" : "Unity 与 MCP 均已连接";
    return { unity, mcp, detail };
  }

  async build(request: BuildRequest, emit: Parameters<UnityAdapter["build"]>[1], context: Parameters<UnityAdapter["build"]>[2]) {
    const checkControl = () => { if (context.signal.aborted) throw new Error("构建已由玩家接管"); };
    await access(this.unityPath);
    const visualPaths = request.mode === "2d" ? (request.spritePaths?.length ? request.spritePaths : request.spritePath ? [request.spritePath] : []) : request.modelPath ? [request.modelPath] : [];
    if (!visualPaths.length) throw new Error("构建请求缺少已批准的视觉素材");
    await Promise.all([...visualPaths.map((path) => access(path)), access(request.audioPath)]);
    const inputRoot = join(request.unityProjectPath, "Assets", "QIWEN", "Input");
    await mkdir(inputRoot, { recursive: true });
    if (request.mode === "2d") {
      const spriteRoot = join(inputRoot, "Sprites");
      await mkdir(spriteRoot, { recursive: true });
      for (const name of await readdir(spriteRoot)) if (/^sprite-\d+\.png$/i.test(name)) await unlink(join(spriteRoot, name));
      await Promise.all(visualPaths.map((path, index) => copyFile(path, join(spriteRoot, `sprite-${String(index + 1).padStart(2, "0")}.png`))));
    } else await copyFile(visualPaths[0]!, join(inputRoot, "lacquer-bowl.glb"));
    await copyFile(request.audioPath, join(inputRoot, "main-theme.wav"));
    const requestPath = join(request.unityProjectPath, "QIWEN", "Requests", "pending.json");
    await mkdir(dirname(requestPath), { recursive: true });
    await writeFile(requestPath, JSON.stringify({ ...request, createdAt: new Date().toISOString() }, null, 2), "utf8");
    const scriptHash = createHash("sha256").update(request.runtimeScript).digest("hex").slice(0, 12);
    emit({ stage: "生成脚本", progress: 8, message: `受控生成区差异已确认；脚本指纹 ${scriptHash}；第 ${context.attempt} 次尝试`, level: "信息", source: "桥接" });

    let client: McpHttpClient | undefined;
    try {
      const probe = new McpHttpClient(this.mcpUrl, 2_000);
      await probe.callTool("manage_scene", { action: "get_active" });
      client = probe;
    } catch {
      emit({ stage: "启动编辑器", progress: 10, message: "正在以可见方式打开 Unity 编辑器", level: "信息", source: "桥接" });
      const logPath = join(request.unityProjectPath, "Logs", "Editor-current.log");
      await mkdir(dirname(logPath), { recursive: true });
      const child = spawn(this.unityPath, ["-projectPath", request.unityProjectPath, "-logFile", logPath], {
        detached: true,
        stdio: "ignore",
        windowsHide: false,
        env: { ...process.env, UPM_CACHE_ROOT: "D:\\qiwen-runtime\\unity-cache" },
      });
      child.unref();
    }

    const connectionDeadline = Date.now() + 600_000;
    while (!client && Date.now() < connectionDeadline) {
      checkControl();
      try {
        const probe = new McpHttpClient(this.mcpUrl, 5_000);
        await probe.callTool("manage_scene", { action: "get_active" });
        client = probe;
      } catch { await wait(2_000); }
    }
    if (!client) throw new Error("Unity 已打开，但 MCP 在十分钟内没有连接");
    emit({ stage: "连接 MCP", progress: 20, message: "本地桥接已通过 MCP 连接 Unity", level: "成功", source: "桥接" });

    checkControl();
    try { await client.callTool("manage_editor", { action: "stop" }); } catch { /* 非 Play Mode 时无需停止。 */ }
    const resultPath = join(request.unityProjectPath, "QIWEN", "Results", "vertical-slice.json");
    const eventPath = join(request.unityProjectPath, "QIWEN", "Results", "vertical-slice-events.jsonl");
    await Promise.all([unlink(resultPath).catch(() => undefined), unlink(eventPath).catch(() => undefined)]);
    await client.callTool("execute_menu_item", { menu_path: "漆问/执行最小垂直切片" });
    await wait(1_500);
    try { await client.callTool("execute_menu_item", { menu_path: "漆问/继续最小垂直切片" }); } catch { /* 域重载时由恢复入口继续。 */ }

    let eventCount = 0;
    let latestStage = "";
    let lastResumeAt = Date.now();
    const resultDeadline = Date.now() + 300_000;
    while (Date.now() < resultDeadline) {
      checkControl();
      try {
        const lines = (await readFile(eventPath, "utf8")).split(/\r?\n/).filter(Boolean);
        for (const line of lines.slice(eventCount)) {
          const event = JSON.parse(line) as Omit<BuildEvent, "sequence" | "source">;
          latestStage = event.stage;
          emit({ stage: event.stage, progress: event.progress, message: event.message, level: event.level, source: "Unity" });
        }
        eventCount = lines.length;
      } catch { /* 事件文件尚未创建。 */ }
      if (latestStage === "编译" && Date.now() - lastResumeAt >= 5_000) {
        lastResumeAt = Date.now();
        try {
          const resumedClient = new McpHttpClient(this.mcpUrl, 5_000);
          await resumedClient.callTool("execute_menu_item", { menu_path: "漆问/继续最小垂直切片" });
          emit({ stage: "编译", progress: 80, message: "编译与域重载已完成，正在恢复构建", level: "信息", source: "桥接" });
        } catch { /* MCP 尚在重连时保持轮询，不会重复创建任务。 */ }
      }
      try {
        const result = JSON.parse(await readFile(resultPath, "utf8")) as { success: boolean; stage: string; message: string };
        if (!result.success) throw new Error(result.message);
        emit({ stage: "完成", progress: 100, message: result.message, level: "成功", source: "Unity" });
        return;
      } catch (error) {
        if (error instanceof Error && !error.message.includes("ENOENT") && !error.message.includes("Unexpected end") && !error.message.includes("JSON")) throw error;
      }
      await wait(1_000);
    }
    throw new Error("Unity 垂直切片执行超时");
  }
}
