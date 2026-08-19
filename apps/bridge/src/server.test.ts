import { afterEach, describe, expect, it } from "vitest";
import { config } from "./config.js";
import { createBridgeServer } from "./server.js";
import type { BuildRequest, UnityAdapter } from "./types.js";

let closeServer: (() => Promise<void>) | undefined;

afterEach(async () => {
  await closeServer?.();
  closeServer = undefined;
});

async function start(adapter: UnityAdapter) {
  const server = createBridgeServer(adapter);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("Test server did not bind");
  closeServer = () => new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return `http://127.0.0.1:${address.port}`;
}

const adapter: UnityAdapter = {
  name: "Test adapter",
  health: async () => ({ unity: "已连接", mcp: "已连接", detail: "test" }),
  build: async (_request, emit) => emit({ stage: "完成", progress: 100, message: "done", level: "成功", source: "Unity" }),
};

const payload: BuildRequest = {
  projectId: "test-project",
  unityProjectPath: "D:\\游戏agent\\qiwen-verify\\unity\\QIWEN-VerticalSlice",
  mode: "2d",
  spritePaths: ["D:\\游戏agent\\qiwen-verify\\storage\\sprite-01.png"],
  audioPath: "D:\\游戏agent\\qiwen-verify\\storage\\music.wav",
  runtimeScript: `namespace QIWEN.Runtime { public class LacquerBowlExperience { ${"/* safe */".repeat(20)} } }`,
  buildPlan: {
    schema_version: 1, template_id: "puzzle-process", game_title: "Test", objective: "Test", player_instructions: "Test",
    target_count: 3, time_limit_seconds: 60, failure_limit: 3, speed: 1, sequence_steps: [], asset_roles: [], audio_cues: [],
  },
};

describe("local bridge", () => {
  it("reports the selected adapter health", async () => {
    const url = await start(adapter);
    const response = await fetch(`${url}/health`);
    expect(response.status).toBe(200);
    expect((await response.json()).adapter).toBe("Test adapter");
  });

  it("requires a token for builds", async () => {
    const url = await start(adapter);
    expect((await fetch(`${url}/build`, { method: "POST", body: JSON.stringify(payload) })).status).toBe(401);
  });

  it("accepts a validated 2d build request", async () => {
    const url = await start(adapter);
    const response = await fetch(`${url}/build`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-qiwen-bridge-token": config.token },
      body: JSON.stringify(payload),
    });
    expect(response.status).toBe(202);
    const job = await response.json() as { id: string };
    expect(job.id).toBeTruthy();
  });

  it("rejects paths outside D and E", async () => {
    const url = await start(adapter);
    const response = await fetch(`${url}/build`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-qiwen-bridge-token": config.token },
      body: JSON.stringify({ ...payload, unityProjectPath: "C:\\invalid" }),
    });
    expect(response.status).toBe(400);
  });
});
