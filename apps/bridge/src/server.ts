import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { join } from "node:path";
import { CoplayUnityAdapter } from "./adapters/coplay.js";
import { MockUnityAdapter } from "./adapters/mock.js";
import { applyCoCreationRequest, validCoCreationRequest } from "./co-creation.js";
import { config, isPathAllowed } from "./config.js";
import { McpHttpClient } from "./mcp-client.js";
import type { BuildEvent, BuildJob, BuildRequest, UnityAdapter } from "./types.js";

const adapter: UnityAdapter = config.adapter === "mock" ? new MockUnityAdapter() : new CoplayUnityAdapter(config.unityPath, config.mcpUrl);
const jobs = new Map<string, BuildJob>();
const requests = new Map<string, BuildRequest>();
const controllers = new Map<string, AbortController>();
const subscribers = new Map<string, Set<ServerResponse>>();
const jobRoot = "D:\\qiwen-runtime\\bridge\\jobs";

function send(response: ServerResponse, status: number, body: unknown) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(JSON.stringify(body));
}

function authorized(request: IncomingMessage): boolean {
  const supplied = request.headers["x-qiwen-bridge-token"];
  if (typeof supplied !== "string" || supplied.length !== config.token.length) return false;
  return timingSafeEqual(Buffer.from(supplied), Buffer.from(config.token));
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  let raw = "";
  for await (const chunk of request) {
    raw += chunk;
    if (raw.length > 64 * 1024) throw new Error("请求体过大");
  }
  return JSON.parse(raw || "{}");
}

function validBuildRequest(value: unknown): value is BuildRequest {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const runtimeScript = item.runtimeScript;
  const plan = item.buildPlan as Record<string, unknown> | undefined;
  const allowedTemplates = ["simulation-layering", "timing-polish", "collection-materials", "puzzle-process", "target-lacquer-drops", "topdown-dodge"];
  return typeof item.projectId === "string"
    && typeof item.unityProjectPath === "string" && isPathAllowed(item.unityProjectPath)
    && (item.mode === "2d"
      ? Array.isArray(item.spritePaths) && item.spritePaths.length > 0 && item.spritePaths.every((path) => typeof path === "string" && isPathAllowed(path))
      : typeof item.modelPath === "string" && isPathAllowed(item.modelPath))
    && typeof item.audioPath === "string" && isPathAllowed(item.audioPath)
    && typeof runtimeScript === "string" && runtimeScript.length > 100 && runtimeScript.length <= 12_000
    && !!plan && allowedTemplates.includes(String(plan.template_id))
    && typeof plan.game_title === "string" && plan.game_title.length > 0 && plan.game_title.length <= 60
    && typeof plan.objective === "string" && typeof plan.player_instructions === "string"
    && typeof plan.target_count === "number" && plan.target_count >= 1 && plan.target_count <= 20
    && typeof plan.time_limit_seconds === "number" && plan.time_limit_seconds >= 10 && plan.time_limit_seconds <= 180
    && typeof plan.failure_limit === "number" && plan.failure_limit >= 1 && plan.failure_limit <= 10
    && runtimeScript.includes("namespace QIWEN.Runtime") && runtimeScript.includes("class LacquerBowlExperience")
    && !["System.IO", "System.Net", "System.Diagnostics", "UnityEditor", "DllImport", "Process.", "File.", "Directory."].some((token) => runtimeScript.includes(token));
}

async function persist(job: BuildJob) {
  await mkdir(jobRoot, { recursive: true });
  await writeFile(join(jobRoot, `${job.id}.json`), JSON.stringify(job, null, 2), "utf8");
  const request = requests.get(job.id);
  if (request) await writeFile(join(jobRoot, `request-${job.id}.json`), JSON.stringify(request, null, 2), "utf8");
}

function restoreJobs() {
  if (!existsSync(jobRoot)) return;
  for (const name of readdirSync(jobRoot).filter((item) => item.endsWith(".json") && !item.startsWith("request-"))) {
    try {
      const restored = JSON.parse(readFileSync(join(jobRoot, name), "utf8")) as BuildJob;
      if (!restored.id || !Array.isArray(restored.events)) continue;
      const requestPath = join(jobRoot, `request-${restored.id}.json`);
      if (existsSync(requestPath)) {
        const request = JSON.parse(readFileSync(requestPath, "utf8")) as unknown;
        if (validBuildRequest(request)) requests.set(restored.id, request);
      }
      if (["排队中", "执行中"].includes(restored.status)) {
        restored.status = "失败";
        const message = "本地桥接曾在任务执行中重启，可安全重试该任务";
        restored.errorFingerprint = createHash("sha256").update(message).digest("hex").slice(0, 12);
        restored.events.push({ sequence: (restored.events.at(-1)?.sequence ?? 0) + 1, time: new Date().toISOString(), stage: "失败", progress: restored.events.at(-1)?.progress ?? 0, message, level: "错误", source: "桥接" });
      }
      jobs.set(restored.id, restored);
    } catch { /* 损坏的单个证据文件不会阻止桥接启动。 */ }
  }
}

function publish(job: BuildJob, event: BuildEvent) {
  for (const response of subscribers.get(job.id) ?? []) {
    response.write(`id: ${event.sequence}\nevent: 构建事件\ndata: ${JSON.stringify(event)}\n\n`);
  }
}

function emitter(job: BuildJob) {
  return (event: Omit<BuildEvent, "sequence" | "time">) => {
    const item: BuildEvent = { ...event, sequence: (job.events.at(-1)?.sequence ?? 0) + 1, time: new Date().toISOString() };
    job.events.push(item);
    job.updatedAt = item.time;
    publish(job, item);
    void persist(job);
  };
}

async function runJob(job: BuildJob, activeAdapter: UnityAdapter = adapter) {
  const payload = requests.get(job.id);
  if (!payload) throw new Error("构建请求已过期，请重新启动构建");
  const controller = new AbortController();
  controllers.set(job.id, controller);
  const emit = emitter(job);
  job.status = "执行中";
  job.attempt += 1;
  job.updatedAt = new Date().toISOString();
  await persist(job);
  try {
    await activeAdapter.build(payload, emit, { signal: controller.signal, attempt: job.attempt });
    if (!isTakenOver(job)) job.status = "成功";
  } catch (error) {
    if (!isTakenOver(job)) {
      const message = error instanceof Error ? error.message : "未知构建错误";
      job.status = "失败";
      job.errorFingerprint = createHash("sha256").update(message).digest("hex").slice(0, 12);
      emit({ stage: "失败", progress: job.events.at(-1)?.progress ?? 0, message, level: "错误", source: "桥接" });
    }
  } finally {
    controllers.delete(job.id);
    job.updatedAt = new Date().toISOString();
    await persist(job);
  }
}

function isTakenOver(job: BuildJob): boolean {
  return job.status === "已接管";
}

export function createBridgeServer(adapterOverride?: UnityAdapter) {
  if (jobs.size === 0) restoreJobs();
  const activeAdapter = adapterOverride ?? adapter;
  return createServer(async (request, response) => {
    try {
      const url = new URL(request.url ?? "/", `http://${config.host}:${config.port}`);
      if (request.method === "GET" && url.pathname === "/health") {
        const state = await activeAdapter.health();
        return send(response, 200, { bridge: "已连接", adapter: activeAdapter.name, ...state, port: config.port });
      }
      const match = url.pathname.match(/^\/jobs\/([^/]+)(?:\/(events|retry|takeover))?$/);
      if (match && request.method === "GET" && match[2] === "events") {
        const job = jobs.get(match[1]!);
        if (!job) return send(response, 404, { detail: "找不到构建任务" });
        const after = Number(url.searchParams.get("after") ?? 0);
        response.writeHead(200, { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-cache", connection: "keep-alive" });
        for (const event of job.events.filter((item) => item.sequence > after)) response.write(`id: ${event.sequence}\nevent: 构建事件\ndata: ${JSON.stringify(event)}\n\n`);
        const set = subscribers.get(job.id) ?? new Set<ServerResponse>();
        set.add(response); subscribers.set(job.id, set);
        const heartbeat = setInterval(() => response.write(": 心跳\n\n"), 15_000);
        request.on("close", () => { clearInterval(heartbeat); set.delete(response); });
        return;
      }
      if (match && request.method === "GET" && !match[2]) {
        const job = jobs.get(match[1]!);
        return job ? send(response, 200, job) : send(response, 404, { detail: "找不到构建任务" });
      }
      if (match && request.method === "POST" && ["retry", "takeover"].includes(match[2] ?? "")) {
        if (!authorized(request)) return send(response, 401, { detail: "本地桥接令牌无效" });
        const job = jobs.get(match[1]!);
        if (!job) return send(response, 404, { detail: "找不到构建任务" });
        if (match[2] === "takeover") {
          controllers.get(job.id)?.abort();
          job.status = "已接管";
          emitter(job)({ stage: "人工接管", progress: job.events.at(-1)?.progress ?? 0, message: "自动化已停止，Unity 保持打开，控制权已交给玩家", level: "警告", source: "桥接" });
          return send(response, 200, job);
        }
        if (job.status !== "失败") return send(response, 409, { detail: "只有失败任务可以重试" });
        if (job.attempt >= job.maxAttempts) return send(response, 409, { detail: "已达到最多三次修复尝试" });
        emitter(job)({ stage: "等待", progress: 0, message: `准备第 ${job.attempt + 1} 次尝试`, level: "信息", source: "桥接" });
        void runJob(job, activeAdapter);
        return send(response, 202, job);
      }
      if (request.method === "POST" && url.pathname === "/build") {
        if (!authorized(request)) return send(response, 401, { detail: "本地桥接令牌无效" });
        const payload = await readJson(request);
        if (!validBuildRequest(payload)) return send(response, 400, { detail: "构建参数或路径不在允许范围内" });
        const now = new Date().toISOString();
        const job: BuildJob = { id: randomUUID(), projectId: payload.projectId, status: "排队中", adapter: activeAdapter.name, createdAt: now, updatedAt: now, attempt: 0, maxAttempts: 3, events: [] };
        jobs.set(job.id, job); requests.set(job.id, payload);
        void runJob(job, activeAdapter);
        return send(response, 202, job);
      }
      if (request.method === "POST" && url.pathname === "/co-creation/apply") {
        if (!authorized(request)) return send(response, 401, { detail: "本地桥接令牌无效" });
        const payload = await readJson(request);
        if (!validCoCreationRequest(payload) || !isPathAllowed(payload.unityProjectPath)) {
          return send(response, 400, { detail: "共创参数、脚本或路径不在允许范围内" });
        }
        const receipt = await applyCoCreationRequest(payload, config.mcpUrl);
        return send(response, 200, receipt);
      }
      if (request.method === "POST" && url.pathname === "/playtest/play") {
        if (!authorized(request)) return send(response, 401, { detail: "本地桥接令牌无效" });
        const client = new McpHttpClient(config.mcpUrl, 10_000);
        await client.callTool("manage_editor", { action: "play" });
        return send(response, 200, { success: true, playMode: true, time: new Date().toISOString(), message: "Unity 已进入试玩" });
      }
      return send(response, 404, { detail: "不支持的本地桥接操作" });
    } catch (error) {
      return send(response, 500, { detail: error instanceof Error ? error.message : "本地桥接错误" });
    }
  });
}

if (process.env.NODE_ENV !== "test") {
  createBridgeServer().listen(config.port, config.host, () => console.log(`漆问本地桥接已启动：http://${config.host}:${config.port}`));
}
