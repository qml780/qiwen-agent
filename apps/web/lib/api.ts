import type { AgentResponse, Asset, Project } from "./domain";

export type UnityHealth = { bridge: string; unity: string; mcp: string; adapter: string; detail: string; port: number };
export type UnityBuildEvent = {
  sequence: number;
  time: string;
  stage: string;
  progress: number;
  message: string;
  level: string;
  source?: "桥接" | "Unity" | "控制台";
};
export type UnityBuildJob = {
  id: string;
  projectId: string;
  status: string;
  adapter: string;
  createdAt: string;
  updatedAt: string;
  attempt: number;
  maxAttempts: number;
  errorFingerprint?: string;
  events: UnityBuildEvent[];
};
export type UnityChange = {
  id: string;
  project_id: string;
  asset_id?: string;
  action: string;
  action_label: string;
  status: string;
  request: Record<string, unknown>;
  preview: { title: string; summary: string; differences: string[]; generated_script?: string; generated_area?: string; undo_available_after_apply: boolean };
  receipt: Record<string, unknown>;
  checkpoint_path?: string;
  created_at: string;
  applied_at?: string;
  undone_at?: string;
};
export type PlaytestSession = {
  id: string;
  project_id: string;
  build_job_id?: string;
  logic_version: number;
  status: string;
  status_label: string;
  initial_feedback?: string;
  initial_rating?: number;
  revision_change_id?: string;
  final_feedback?: string;
  final_rating?: number;
  evidence: Record<string, unknown>;
  created_at: string;
  completed_at?: string;
};
export type ResearchSnapshot = {
  schema_version: number;
  anonymized_project_id: string;
  generated_at: string;
  metric_definitions: Record<string, string>;
  metrics: {
    timeline_events: number;
    conversation_events: number;
    suggestions: { total: number; responded: number; accepted: number; rejected: number; modified: number; discuss: number; pending: number; acceptance_rate: number | null };
    revision_count: number;
    version_counts: Record<string, number>;
    asset_generations: number;
    asset_selections: number;
    approval_events: number;
    playtest_iterations: number;
    knowledge_alignment_versions: number;
    game_design_versions: number;
    research_exports: number;
  };
  approval_history: Array<Record<string, string | number>>;
  timeline: Array<{ id: string; type: string; label: string; time: string; source: string; details: Record<string, unknown> }>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const unityEventUrl = (jobId: string, after = 0) =>
  `${API_URL}/unity/jobs/${encodeURIComponent(jobId)}/events?after=${after}`;

export class ApiRequestError extends Error {
  constructor(message: string, readonly code?: string, readonly detail?: Record<string, unknown>, readonly retryWithBudget?: () => Promise<unknown>) {
    super(message);
    this.name = "ApiRequestError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = body.detail;
    const code = typeof detail?.code === "string" ? detail.code : undefined;
    const message = typeof detail === "string"
      ? detail
      : typeof detail?.message === "string"
        ? detail.message
        : code === "invalid_stage"
          ? "项目阶段已经更新，正在同步最新内容。"
          : "操作没有完成，请稍后重试。";
    const retryWithBudget = code === "monthly_budget_requires_choice"
      ? () => request(path, { ...init, headers: { ...(init?.headers ?? {}), "X-Qiwen-Budget-Choice": "continue" } })
      : undefined;
    throw new ApiRequestError(message, code, typeof detail === "object" && detail ? detail : undefined, retryWithBudget);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; llm_mode: string; monthly_budget_cny: number }>("/health"),
  createProject: (knowledgeId: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ knowledge_id: knowledgeId }) }),
  projects: (limit = 40, offset = 0) => request<Project[]>(`/projects?limit=${limit}&offset=${offset}`),
  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),
  deleteProject: (projectId: string) => request<void>(`/projects/${projectId}`, { method: "DELETE" }),
  assets: (projectId: string) => request<Asset[]>(`/assets?project_id=${encodeURIComponent(projectId)}`),
  useAsset: (projectId: string, assetId: string) =>
    request<Project>(`/projects/${projectId}/assets/${encodeURIComponent(assetId)}/use`, { method: "POST" }),
  deleteAsset: (projectId: string, assetId: string) =>
    request<Project>(`/projects/${projectId}/assets/${encodeURIComponent(assetId)}`, { method: "DELETE" }),
  saveIdea: (projectId: string, idea: string) =>
    request<Project>(`/projects/${projectId}/idea`, { method: "POST", body: JSON.stringify({ idea }) }),
  setProductionMode: (projectId: string, mode: "2d" | "3d") =>
    request<Project>(`/projects/${projectId}/production-mode`, { method: "POST", body: JSON.stringify({ mode }) }),
  saveGameAssetPlan: (projectId: string, style: string, items: Array<Record<string, unknown>>) =>
    request<Project>(`/projects/${projectId}/game-assets/plan`, { method: "POST", body: JSON.stringify({ style, items }) }),
  generateGameAsset: (projectId: string, itemId: string) =>
    request<Project>(`/projects/${projectId}/game-assets/generate`, { method: "POST", body: JSON.stringify({ item_id: itemId }) }),
  approveGameAsset: (projectId: string, assetId: string) =>
    request<Project>(`/projects/${projectId}/game-assets/${encodeURIComponent(assetId)}/approve`, { method: "POST" }),
  deleteGameAsset: (projectId: string, assetId: string) =>
    request<Project>(`/projects/${projectId}/game-assets/${encodeURIComponent(assetId)}`, { method: "DELETE" }),
  finalizeGameAssets: (projectId: string) =>
    request<Project>(`/projects/${projectId}/game-assets/finalize`, { method: "POST" }),
  reworkGameAssets: (projectId: string, mode: "2d" | "3d") =>
    request<Project>(`/projects/${projectId}/game-assets/rework`, { method: "POST", body: JSON.stringify({ mode }) }),
  generate: (projectId: string, kind: string, prompt?: string, referenceAssetIds: string[] = [], mode?: "2d") =>
    request<Project>(`/projects/${projectId}/generate/${kind}`, { method: "POST", body: prompt || referenceAssetIds.length || mode ? JSON.stringify({ prompt, reference_asset_ids: referenceAssetIds, mode }) : undefined }),
  approve: (projectId: string, kind: string) =>
    request<Project>(`/projects/${projectId}/approve/${kind}`, { method: "POST" }),
  selectMusicTrack: (projectId: string, trackId: string) =>
    request<Project>(`/projects/${projectId}/music/tracks/${encodeURIComponent(trackId)}/select`, { method: "POST" }),
  deleteMusicTrack: (projectId: string, trackId: string) =>
    request<Project>(`/projects/${projectId}/music/tracks/${encodeURIComponent(trackId)}`, { method: "DELETE" }),
  reopen: (projectId: string, kind: string) =>
    request<Project>(`/projects/${projectId}/reopen/${kind}`, { method: "POST" }),
  revise: (projectId: string, kind: string) =>
    request<Project>(`/projects/${projectId}/revise/${kind}`, { method: "POST" }),
  agent: (projectId: string, message: string, mode: "chat" | "code", attachmentIds: string[] = []) =>
    request<AgentResponse>("/agent/respond", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, message, mode, attachment_ids: attachmentIds }),
    }),
  upload: (projectId: string, name: string, mime: string, dataBase64: string) =>
    request<Asset>(`/projects/${projectId}/uploads`, { method: "POST", body: JSON.stringify({ name, mime, data_base64: dataBase64 }) }),
  respondToSuggestion: (suggestionId: string, action: "accepted" | "rejected" | "modified" | "discuss", note = "") =>
    request<{ status: string; action: string }>(`/agent/suggestions/${suggestionId}/respond`, {
      method: "POST",
      body: JSON.stringify({ action, note }),
    }),
  unityHealth: () => request<UnityHealth>("/unity/health"),
  buildInUnity: (projectId: string) => request<UnityBuildJob>(`/projects/${projectId}/unity/build`, { method: "POST" }),
  unityJob: (jobId: string) => request<UnityBuildJob>(`/unity/jobs/${jobId}`),
  retryUnityJob: (jobId: string) => request<UnityBuildJob>(`/unity/jobs/${jobId}/retry`, { method: "POST" }),
  takeoverUnityJob: (jobId: string) => request<UnityBuildJob>(`/unity/jobs/${jobId}/takeover`, { method: "POST" }),
  unityChanges: (projectId: string) => request<UnityChange[]>(`/projects/${projectId}/unity/changes`),
  previewUnityChange: (projectId: string, payload: Record<string, unknown>) => request<UnityChange>(`/projects/${projectId}/unity/changes/preview`, { method: "POST", body: JSON.stringify(payload) }),
  decideUnityChange: (changeId: string, decision: "approve" | "reject") => request<UnityChange>(`/unity/changes/${changeId}/decision`, { method: "POST", body: JSON.stringify({ decision }) }),
  undoUnityChange: (changeId: string) => request<UnityChange>(`/unity/changes/${changeId}/undo`, { method: "POST" }),
  playtests: (projectId: string) => request<PlaytestSession[]>(`/projects/${projectId}/playtests`),
  startPlaytest: (projectId: string, buildJobId?: string) => request<PlaytestSession>(`/projects/${projectId}/playtests/start`, { method: "POST", body: JSON.stringify({ build_job_id: buildJobId }) }),
  playtestFeedback: (playtestId: string, feedback: string, rating: number) => request<PlaytestSession>(`/playtests/${playtestId}/feedback`, { method: "POST", body: JSON.stringify({ feedback, rating }) }),
  proposePlaytestRevision: (playtestId: string, objectName: string, templateId: string) => request<{ playtest: PlaytestSession; change: UnityChange; project: Project }>(`/playtests/${playtestId}/propose-revision`, { method: "POST", body: JSON.stringify({ object_name: objectName, template_id: templateId }) }),
  approvePlaytestRevision: (playtestId: string) => request<{ playtest: PlaytestSession; change: UnityChange; project: Project }>(`/playtests/${playtestId}/approve-revision`, { method: "POST" }),
  completePlaytest: (playtestId: string, feedback: string, rating: number) => request<PlaytestSession>(`/playtests/${playtestId}/complete`, { method: "POST", body: JSON.stringify({ feedback, rating }) }),
  finishProject: (projectId: string) => request<Project>(`/projects/${projectId}/finish`, { method: "POST" }),
  research: (projectId: string) => request<ResearchSnapshot>(`/projects/${projectId}/research`),
  exportResearch: async (projectId: string, format: "json" | "csv") => {
    const response = await fetch(`${API_URL}/projects/${projectId}/research/export?format=${format}`, { method: "POST" });
    if (!response.ok) throw new Error("研究数据导出失败");
    const disposition = response.headers.get("content-disposition") ?? "";
    const encoded = disposition.match(/filename\*=utf-8''([^;]+)/i)?.[1];
    return { blob: await response.blob(), filename: encoded ? decodeURIComponent(encoded) : `漆问研究导出.${format}` };
  },
};
