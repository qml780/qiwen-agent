import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { McpHttpClient } from "./mcp-client.js";
import type { CoCreationRequest } from "./types.js";

const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export function validCoCreationRequest(value: unknown): value is CoCreationRequest {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const vectorValid = (vector: unknown) => vector === undefined || (Array.isArray(vector) && vector.length === 3 && vector.every((number) => typeof number === "number" && Number.isFinite(number) && Math.abs(number) <= 1000));
  const script = item.generatedScript;
  return typeof item.id === "string" && /^[a-f0-9-]{36}$/.test(item.id)
    && typeof item.projectId === "string"
    && typeof item.unityProjectPath === "string"
    && ["add_asset", "adjust_asset", "request_interaction", "undo"].includes(String(item.action))
    && typeof item.objectName === "string" && item.objectName.length >= 1 && item.objectName.length <= 80
    && vectorValid(item.position) && vectorValid(item.rotation) && vectorValid(item.scale)
    && (script === undefined || (typeof script === "string" && script.length <= 8_000
      && script.includes("namespace QIWEN.Generated")
      && !["System.IO", "System.Net", "System.Diagnostics", "UnityEditor", "DllImport", "Process.", "File.", "Directory."].some((token) => script.includes(token))));
}

export async function applyCoCreationRequest(request: CoCreationRequest, mcpUrl: string) {
  const requestPath = join(request.unityProjectPath, "QIWEN", "CoCreation", "pending.json");
  const receiptPath = join(request.unityProjectPath, "QIWEN", "CoCreation", "Receipts", `${request.id}.json`);
  await mkdir(dirname(requestPath), { recursive: true });
  await writeFile(requestPath, JSON.stringify(request, null, 2), "utf8");

  const client = new McpHttpClient(mcpUrl, 10_000);
  try { await client.callTool("manage_editor", { action: "stop" }); } catch { /* 非 Play Mode 无需停止。 */ }
  await client.callTool("execute_menu_item", { menu_path: request.action === "undo" ? "漆问/共创/撤销到检查点" : "漆问/共创/应用已批准变更" });

  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const receipt = JSON.parse(await readFile(receiptPath, "utf8")) as { success: boolean; message: string };
      if (!receipt.success) throw new Error(receipt.message);
      if (request.playAfterApply) {
        await wait(3_000);
        let reconnected: McpHttpClient | undefined;
        for (let attempt = 0; attempt < 30 && !reconnected; attempt += 1) {
          try {
            const probe = new McpHttpClient(mcpUrl, 5_000);
            await probe.callTool("manage_scene", { action: "get_active" });
            reconnected = probe;
          } catch { await wait(1_000); }
        }
        if (!reconnected) throw new Error("脚本编译后 Unity MCP 未能重新连接");
        const consoleResult = await reconnected.callTool("read_console", { action: "get", types: ["error"], count: 50, format: "detailed" });
        const rawConsole = JSON.stringify(consoleResult);
        if (!rawConsole.includes("Retrieved 0 log entries") && !rawConsole.includes('\\"data\\":[]')) throw new Error("Unity 编译后控制台存在错误，已停止再次试玩");
        await reconnected.callTool("manage_editor", { action: "play" });
        return { ...receipt, compilerErrors: 0, playMode: true };
      }
      return receipt;
    } catch (error) {
      if (error instanceof Error && !error.message.includes("ENOENT") && !error.message.includes("Unexpected end")) throw error;
    }
    await wait(500);
  }
  throw new Error("Unity 共创变更在一分钟内没有返回回执");
}
