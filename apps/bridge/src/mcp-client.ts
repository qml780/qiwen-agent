export class McpHttpClient {
  private sessionId = "";
  private nextId = 1;

  constructor(private readonly url: string, private readonly timeoutMs = 15_000) {}

  private async rpc(method: string, params: Record<string, unknown> = {}) {
    const response = await fetch(this.url, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "application/json, text/event-stream",
        ...(this.sessionId ? { "mcp-session-id": this.sessionId } : {}),
      },
      body: JSON.stringify({ jsonrpc: "2.0", id: this.nextId++, method, params }),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!response.ok) throw new Error(`MCP 返回 ${response.status}`);
    const newSession = response.headers.get("mcp-session-id");
    if (newSession) this.sessionId = newSession;
    const raw = await response.text();
    const dataLine = raw.split("\n").find((line) => line.startsWith("data:"));
    const payload = JSON.parse(dataLine ? dataLine.slice(5).trim() : raw) as { error?: { message?: string }; result?: unknown };
    if (payload.error) throw new Error(payload.error.message ?? "MCP 调用失败");
    return payload.result;
  }

  async initialize() {
    await this.rpc("initialize", {
      protocolVersion: "2025-06-18",
      capabilities: {},
      clientInfo: { name: "QIWEN Local Bridge", version: "0.1.0" },
    });
    await fetch(this.url, {
      method: "POST",
      headers: { "content-type": "application/json", ...(this.sessionId ? { "mcp-session-id": this.sessionId } : {}) },
      body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
  }

  async callTool(name: string, args: Record<string, unknown>) {
    if (!this.sessionId) await this.initialize();
    const result = await this.rpc("tools/call", { name, arguments: args });
    if (result && typeof result === "object" && "isError" in result && result.isError) {
      const content = "content" in result && Array.isArray(result.content) ? result.content : [];
      const message = content.find((item) => item && typeof item === "object" && "text" in item)?.text;
      throw new Error(typeof message === "string" ? message : `MCP 工具 ${name} 执行失败`);
    }
    return result;
  }

  async ping() {
    if (!this.sessionId) await this.initialize();
    await this.rpc("ping");
  }
}
