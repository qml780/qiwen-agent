import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, normalize, parse } from "node:path";

const runtimeRoot = process.env.QIWEN_RUNTIME_ROOT ?? "D:\\游戏agent\\qiwen-verify\\runtime\\bridge";
const tokenPath = process.env.QIWEN_BRIDGE_TOKEN_FILE ?? `${runtimeRoot}\\bridge-token`;

function assertDataDrive(path: string): string {
  const resolved = normalize(path);
  const root = parse(resolved).root.toUpperCase();
  if (!isAbsolute(resolved) || (root !== "D:\\" && root !== "E:\\")) {
    throw new Error(`Bridge files must be on D: or E:: ${resolved}`);
  }
  return resolved;
}

function loadToken(): string {
  const fromEnvironment = process.env.QIWEN_BRIDGE_TOKEN?.trim();
  if (fromEnvironment) return fromEnvironment;
  const safePath = assertDataDrive(tokenPath);
  try {
    const existing = readFileSync(safePath, "utf8").trim();
    if (existing.length >= 32) return existing;
  } catch {
    // Create the local token on first start.
  }
  mkdirSync(dirname(safePath), { recursive: true });
  const token = randomBytes(32).toString("hex");
  writeFileSync(safePath, token, { encoding: "utf8", mode: 0o600 });
  return token;
}

export const config = {
  host: "127.0.0.1" as const,
  port: Number(process.env.QIWEN_BRIDGE_PORT ?? 4567),
  token: loadToken(),
  unityPath: assertDataDrive(process.env.QIWEN_UNITY_PATH ?? "D:\\qiwen-runtime\\Unity\\6000.3.18f1\\Editor\\Unity.exe"),
  projectRoot: assertDataDrive(process.env.QIWEN_UNITY_PROJECT_ROOT ?? "D:\\游戏agent\\qiwen-verify\\unity\\QIWEN-VerticalSlice"),
  mcpUrl: process.env.QIWEN_UNITY_MCP_URL ?? "http://127.0.0.1:8080/mcp",
  adapter: process.env.QIWEN_UNITY_ADAPTER ?? "coplay",
  allowedOrigin: process.env.QIWEN_WEB_ORIGIN ?? "http://127.0.0.1:3000",
  assetRoots: (process.env.QIWEN_ASSET_ROOTS ?? "D:\\游戏agent\\qiwen-verify;D:\\qiwen-runtime")
    .split(";").map((item) => assertDataDrive(item.trim())),
};

export function isPathAllowed(path: string): boolean {
  try {
    const safe = assertDataDrive(path);
    const lower = safe.toLowerCase();
    return lower.startsWith(config.projectRoot.toLowerCase())
      || config.assetRoots.some((root) => lower.startsWith(root.toLowerCase()));
  } catch {
    return false;
  }
}
