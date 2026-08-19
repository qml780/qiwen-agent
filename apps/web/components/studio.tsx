"use client";

import Image from "next/image";
import { useSearchParams } from "next/navigation";
import {
  Box,
  Check,
  ChevronRight,
  Code2,
  ImageIcon,
  ImagePlus,
  FileText,
  Library,
  LoaderCircle,
  MessageSquareText,
  Music2,
  Paperclip,
  RotateCcw,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiRequestError, api, unityEventUrl } from "@/lib/api";
import { knowledgeEntries } from "@/lib/knowledge-v2";
import { groupStatus, stageGroups, type Asset, type Project } from "@/lib/domain";
import { ModelViewer } from "./model-viewer";

type ConceptData = {
  game_name: string;
  selected_knowledge: string;
  genre: string;
  player_fantasy: string;
  world: string;
  learning_objective: string;
  core_mechanic: string;
  core_loop: string;
  player_actions: string[];
  rules: string[];
  feedback: string[];
  failure_conditions: string[];
  win_condition: string;
  level_structure: string;
  estimated_duration: string;
  alignment: { represented: string[]; missing: string[]; score: string };
};

type VisualData = { prompt: string; variants: { id: string; title: string; url: string }[]; selected: string; provider: string };
type ThreeDData = { name: string; file: string; format: string; polygon_count: number; texture: string; version: number; provider: string };
type TwoDData = { mode: "2d" | "3d"; prompt: string; variants: { id: string; title: string; url: string }[]; selected: string; provider: string };
type GameAssetPlanItem = { id: string; name: string; category: string; prompt: string; asset_id: string | null; status: "pending" | "generated" | "approved" };
type GameAssetPlanData = { mode?: "2d" | "3d"; style: string; items: GameAssetPlanItem[] };
type MusicData = { prompt: string; mood: string; tempo: number; duration: number; loop: boolean; tracks: { id: string; title: string; url: string }[]; selected: string; provider: string };
type UnityBuildPlanData = { template_id: string; game_title: string; objective: string; player_instructions: string; target_count: number; time_limit_seconds: number; failure_limit: number; speed: number; sequence_steps: string[]; asset_roles: string[]; audio_cues: string[] };
type LogicData = { player: string; painting: string[]; rounds: string; win: string; fail: string; audio_cues: string[]; acceptance: string[]; unity_build_plan?: UnityBuildPlanData };

const templateLabel = (id: string) => ({
  "simulation-layering": "模拟·薄髹层积", "timing-polish": "时机·推光节律", "collection-materials": "收集·材料辨识",
  "puzzle-process": "谜题·工序排序", "target-lacquer-drops": "目标·纹样点漆",
  "topdown-dodge": "动作·俯视角躲避",
}[id] ?? "未识别模板");

const stageKind = (stage: string) => {
  if (stage.startsWith("concept")) return "concept";
  if (stage.startsWith("visual")) return "visual";
  if (stage.startsWith("3d")) return "3d";
  if (stage.startsWith("music")) return "music";
  if (stage.startsWith("logic")) return "logic";
  return "knowledge";
};

function dataOf<T>(project: Project | null, key: string): T | null {
  return (project?.artifacts[key]?.data as T | undefined) ?? null;
}

const assetTypeLabels: Record<string, string> = { ALL: "全部", IMAGE: "图像", "3D": "三维", AUDIO: "音频", CODE: "代码", DOCUMENT: "文档" };
const decisionLabels: Record<string, string> = { accepted: "已接受", rejected: "已拒绝", modified: "待修改", discuss: "继续讨论" };
const alignmentLabels: Record<string, string> = { Strong: "高度对应", Partial: "部分对应", Weak: "对应较弱" };
const localizedAssetName = (name: string) => name
  .replace(/^3d\s*/i, "三维")
  .replace(/^visual\s*/i, "视觉")
  .replace(/^music\s*/i, "音乐")
  .replace(/^LacquerBowl_v1$/i, "漆碗模型·第一版");

function productionModeOf(project: Project): "2d" | "3d" | null {
  const selected = (project.artifacts.production_mode?.data as { mode?: string } | undefined)?.mode;
  if (selected === "2d" || selected === "3d") return selected;
  const gameAsset = project.artifacts["3d"]?.data as { mode?: string } | undefined;
  if (gameAsset?.mode === "2d") return "2d";
  if (project.artifacts.visual || project.artifacts["3d"]) return "3d";
  return null;
}

const publicText = (value: string) => value
  .replace(/米醋(?:图片)?|micu(?:-image)?/gi, "当前服务")
  .replace(/深度求索|deepseek/gi, "共创助手")
  .replace(/混元(?:生)?(?:三维|3D)?|hunyuan3d/gi, "当前素材服务")
  .replace(/腾讯\s*MPS|tencent[_-]?mps/gi, "当前音频服务")
  .replace(/gpt-[a-z0-9.-]+/gi, "当前服务")
  .replace(/\bAPI\b/gi, "服务")
  .replace(/MCP/g, "工具通道");

function ImagePreviewButton({ url, label = "预览" }: { url: string; label?: string }) {
  const [open, setOpen] = useState(false);
  return <><button type="button" onClick={() => setOpen(true)}>{label}</button>{open && <div className="image-modal" role="dialog" aria-modal="true" aria-label="图片预览" onClick={() => setOpen(false)}><div onClick={(event) => event.stopPropagation()}><button className="image-modal-close" type="button" aria-label="关闭预览" onClick={() => setOpen(false)}><X size={18} /></button><Image src={url} alt="素材大图预览" fill sizes="90vw" unoptimized /></div></div>}</>;
}

function stageStateLabel(stage: Project["current_stage"]) {
  const labels: Record<Project["current_stage"], string> = {
    knowledge_selection: "选择知识与想法",
    concept_drafting: "准备概念",
    concept_review: "审阅概念",
    visual_drafting: "准备视觉",
    visual_review: "审阅视觉",
    "3d_drafting": "准备游戏素材",
    "3d_review": "审阅游戏素材",
    music_drafting: "准备音乐",
    music_review: "审阅音乐",
    logic_drafting: "准备游戏逻辑",
    logic_review: "审阅游戏逻辑",
    ready_to_build: "可以构建",
    unity_connecting: "正在连接 Unity",
    unity_building: "正在构建",
    unity_review: "构建完成，等待试玩",
    playtesting: "正在试玩与修订",
    revision: "正在修订",
    completed: "项目已完成",
  };
  return labels[stage];
}

export function Studio() {
  const searchParams = useSearchParams();
  const knowledgeId = searchParams.get("knowledge") ?? "MAT-001";
  const requestedProjectId = searchParams.get("project");
  const knowledge = knowledgeEntries.find((entry) => entry.id === knowledgeId) ?? knowledgeEntries[0];
  const [project, setProject] = useState<Project | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [idea, setIdea] = useState("我想把薄髹做成一个节奏游戏，每完成一次有效髹漆，就增加一层音乐。");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [agentInput, setAgentInput] = useState("");
  const [agentBusy, setAgentBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<Asset[]>([]);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const busyRef = useRef(false);
  const [assetFilter, setAssetFilter] = useState("ALL");
  const [libraryScope, setLibraryScope] = useState<"PROJECT" | "LIBRARY">("PROJECT");
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [reviewGroup, setReviewGroup] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);
  const [budgetRetry, setBudgetRetry] = useState<null | (() => Promise<Project>)>(null);
  const [budgetDetail, setBudgetDetail] = useState<Record<string, unknown> | null>(null);

  const createOrRestore = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      await api.health();
      let current: Project;
      if (requestedProjectId) {
        try {
          current = await api.getProject(requestedProjectId);
        } catch {
          current = await api.createProject(knowledgeId);
        }
      } else {
        const savedProjectId = window.localStorage.getItem(`qiwen-project-${knowledgeId}`);
        if (savedProjectId) {
          try {
            current = await api.getProject(savedProjectId);
          } catch {
            window.localStorage.removeItem(`qiwen-project-${knowledgeId}`);
            current = await api.createProject(knowledgeId);
          }
        } else {
          current = await api.createProject(knowledgeId);
        }
      }
      if (current.id !== requestedProjectId) {
        const query = new URLSearchParams({ knowledge: knowledgeId, project: current.id });
        window.history.replaceState({}, "", `/studio?${query.toString()}`);
      }
      window.localStorage.setItem(`qiwen-project-${knowledgeId}`, current.id);
      setProject(current);
      setAssets(await api.assets(current.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法连接漆问服务");
    } finally {
      setBusy(false);
    }
  }, [knowledgeId, requestedProjectId]);

  useEffect(() => {
    const task = window.setTimeout(() => void createOrRestore(), 0);
    return () => window.clearTimeout(task);
  }, [createOrRestore]);

  useEffect(() => {
    setShowGuide(window.localStorage.getItem("qiwen-guide-dismissed") !== "yes");
  }, []);

  useEffect(() => {
    if (project?.player_idea) setIdea(project.player_idea);
  }, [project?.id, project?.player_idea]);

  const mutate = async (action: () => Promise<Project>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      const next = await action();
      setProject(next);
      setAssets(await api.assets(next.id));
    }
    catch (reason) {
      const message = reason instanceof Error ? reason.message : "操作失败";
      if ((reason instanceof ApiRequestError && reason.code === "invalid_stage") && project) {
        try { setProject(await api.getProject(project.id)); } catch { /* 保留原始错误 */ }
        setError("项目阶段刚刚发生变化，已自动同步最新状态。请确认页面内容后再继续。");
      } else if (reason instanceof ApiRequestError && reason.code === "monthly_budget_requires_choice" && reason.retryWithBudget) {
        setBudgetDetail(reason.detail ?? {});
        setBudgetRetry(() => () => reason.retryWithBudget!() as Promise<Project>);
        setError("");
      } else if (message === "idea_stage_closed") {
        setError("当前是在已批准阶段的回看页面，不能直接保存。请先点击“单独修改本阶段”。");
      } else setError(message);
    }
    finally { busyRef.current = false; setBusy(false); }
  };

  const regenerate = async (kind: "visual" | "3d" | "music", prompt?: string) => {
    if (!project) return;
    const productionMode = productionModeOf(project);
    await mutate(async () => {
      await api.reopen(project.id, kind);
      return api.generate(project.id, kind, prompt, [], kind === "3d" && productionMode === "2d" ? "2d" : undefined);
    });
    setLibraryScope("PROJECT");
    setAssetFilter(kind === "visual" || (kind === "3d" && productionMode === "2d") ? "IMAGE" : kind === "3d" ? "3D" : "AUDIO");
  };

  const sendAgent = async (mode: "chat" | "code" = "chat", suggested?: string) => {
    if (!project) return;
    const message = suggested ?? agentInput.trim();
    if (!message && !pendingAttachments.length) return;
    setAgentBusy(true);
    setError("");
    setAgentInput("");
    try {
      await api.agent(project.id, message, mode, pendingAttachments.map((item) => item.id));
      const refreshed = await api.getProject(project.id);
      setProject(refreshed);
      setPendingAttachments([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "共创助手暂时不可用");
    } finally { setAgentBusy(false); }
  };

  const uploadFiles = async (files: FileList | null) => {
    if (!project || !files?.length) return;
    setUploadBusy(true); setError("");
    try {
      const uploaded: Asset[] = [];
      for (const file of Array.from(files).slice(0, 6)) {
        const dataUrl = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(reader.error); reader.readAsDataURL(file); });
        uploaded.push(await api.upload(project.id, file.name, file.type || "text/plain", dataUrl.split(",", 2)[1]));
      }
      setPendingAttachments((current) => [...current, ...uploaded].slice(0, 8));
      setAssets(await api.assets(project.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "附件上传失败"); }
    finally { setUploadBusy(false); if (imageInputRef.current) imageInputRef.current.value = ""; if (fileInputRef.current) fileInputRef.current.value = ""; }
  };

  const generateFromReferences = async () => {
    if (!project) return;
    const references = pendingAttachments.filter((item) => item.type === "IMAGE");
    if (!references.length) return;
    if (!project.current_stage.startsWith("visual")) { setError("请先完成游戏概念审批，进入视觉阶段后再按参考图生成。"); return; }
    const mode = productionModeOf(project);
    const prompt = agentInput.trim() || (mode === "3d"
      ? "参考上传图片的美术语言，生成《漆问》彩色卡通 3D 游戏概念图；保留其色彩、造型、材质与氛围特征，但不要复制具体角色，不要黑白灰，不要文字水印。"
      : "参考上传图片的美术语言，生成《漆问》彩色卡通 2D 游戏概念图；保留其色彩、轮廓、材质与氛围特征，但不要复制具体角色，不要三维写实，不要黑白灰，不要文字水印。");
    await mutate(async () => {
      if (project.current_stage === "visual_review") await api.reopen(project.id, "visual");
      return api.generate(project.id, "visual", prompt, references.map((item) => item.id));
    });
    setPendingAttachments([]); setAgentInput(""); setLibraryScope("PROJECT"); setAssetFilter("IMAGE");
  };

  const decideSuggestion = async (suggestionId: string, content: string, action: "accepted" | "rejected" | "modified" | "discuss") => {
    setError("");
    try {
      await api.respondToSuggestion(suggestionId, action, action === "rejected" ? "请不要坚持原方案" : "");
      if (action === "rejected") void sendAgent("chat", `我拒绝这条建议：${content}\n请不要坚持原方案，先询问原因并提出不同方向。`);
      if (action === "modified") setAgentInput(`请修改这条建议，同时保留我的原始想法：${content}`);
      if (action === "discuss") setAgentInput(`我想继续讨论这条建议：${content}`);
      setProject(await api.getProject(project!.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "记录建议选择失败"); }
  };

  const visibleAssets = useMemo(
    () => assets.filter((asset) => asset.scope === libraryScope && (assetFilter === "ALL" || asset.type === assetFilter)),
    [assetFilter, assets, libraryScope],
  );
  const selectedAsset = assets.find((asset) => asset.id === selectedAssetId) ?? null;
  const applyAsset = async (asset: Asset) => {
    await mutate(() => api.useAsset(project!.id, asset.id));
    setLibraryScope("PROJECT");
    setAssetFilter(asset.type);
  };

  if (!project && busy) return <main className="loading-screen" role="status" aria-live="polite"><LoaderCircle className="spin" /> 正在准备共创空间……</main>;
  if (!project) return (
    <main className="loading-screen error-state">
      <strong>创作室服务尚未启动。</strong>
      <span>{error ? publicText(error) : "请先启动本地服务，然后重新连接。"}</span>
      <button className="button button-primary" onClick={() => void createOrRestore()}>重新连接</button>
    </main>
  );

  const reviewStages: Record<string, Project["current_stage"]> = {
    knowledge: "knowledge_selection",
    concept: "concept_review",
    visual: "visual_review",
    "3d": "3d_review",
    music: "music_review",
    logic: "logic_review",
  };
  const displayProject = reviewGroup && reviewStages[reviewGroup]
    ? { ...project, current_stage: reviewStages[reviewGroup] }
    : project;
  const kind = stageKind(project.current_stage);
  const currentGroup = stageGroups.find((group) => group.stages.includes(displayProject.current_stage as never));

  return (
    <main className="studio-shell">
      {budgetRetry && <div className="budget-dialog-backdrop" role="presentation"><section className="budget-dialog" role="dialog" aria-modal="true" aria-labelledby="budget-dialog-title"><small>费用确认</small><h2 id="budget-dialog-title">继续生成可能超出本月预算</h2><p>本月预算 {String(budgetDetail?.budget_cny ?? 30)} 元，已使用 {String(budgetDetail?.spent_cny ?? "—")} 元，本次预计 {String(budgetDetail?.estimated_cny ?? "—")} 元。</p><p>只有你确认后才会再次发送生成请求。</p><div><button type="button" onClick={() => { setBudgetRetry(null); setBudgetDetail(null); }}>暂不生成</button><button className="button button-primary" type="button" onClick={() => { const retry = budgetRetry; setBudgetRetry(null); setBudgetDetail(null); void mutate(retry); }}>继续生成</button></div></section></div>}
      <a className="skip-link" href="#studio-workspace">跳到创作区</a>
      {showGuide && <section className="onboarding-guide" aria-label="首次使用提示">
        <span><strong>从左到右完成创作</strong><small>选择素材，在中央审阅每个阶段，并在右侧与共创助手讨论。所有生成内容都要由你批准。</small></span>
        <button type="button" onClick={() => { window.localStorage.setItem("qiwen-guide-dismissed", "yes"); setShowGuide(false); }}>我知道了</button>
      </section>}
      <div className="studio-stagebar">
        <div className="project-title">
          <small>当前项目</small>
          <strong>{project.title}</strong>
          <small>编号 {project.id.slice(0, 8)}</small>
        </div>
        <div className="stage-tabs">
          {stageGroups.map((group, index) => {
            const status = groupStatus(project, group.stages);
            const canReview = status === "complete" && Boolean(reviewStages[group.key]);
            const selected = reviewGroup === group.key;
            return <button
              type="button"
              className={`stage-tab ${status} ${selected ? "selected" : ""}`}
              key={group.key}
              disabled={!canReview && status !== "active"}
              title={canReview ? `回看已批准的${group.label}阶段` : undefined}
              onClick={() => setReviewGroup(status === "active" ? null : group.key)}
            ><span>{status === "complete" ? <Check size={11} /> : `0${index + 1}`}</span>{group.label}</button>;
          })}
        </div>
        <div className="provider-mode" role="status"><span />项目已保存</div>
      </div>

      <div className="studio-grid">
        <aside className="asset-panel">
          <div className="panel-heading"><Library size={15} /><strong>素材库</strong></div>
          <div className="scope-switch">
            <button className={libraryScope === "PROJECT" ? "active" : ""} onClick={() => setLibraryScope("PROJECT")}>当前项目</button>
            <button className={libraryScope === "LIBRARY" ? "active" : ""} onClick={() => setLibraryScope("LIBRARY")}>我的素材</button>
          </div>
          <div className="asset-filters">
            {[
              ["ALL", <Library key="all" size={13} />],
              ["IMAGE", <ImageIcon key="image" size={13} />],
              ["3D", <Box key="3d" size={13} />],
              ["AUDIO", <Music2 key="audio" size={13} />],
              ["CODE", <Code2 key="code" size={13} />],
              ["DOCUMENT", <FileText key="document" size={13} />],
            ].map(([label, icon]) => <button key={String(label)} className={assetFilter === label ? "active" : ""} onClick={() => setAssetFilter(String(label))}>{icon}{assetTypeLabels[String(label)]}</button>)}
          </div>
          <div className="asset-list">
            {visibleAssets.map((asset) => (
              <button
                type="button"
                className={`asset-item ${selectedAssetId === asset.id ? "selected" : ""} ${project.selected_assets?.[asset.type] === asset.id ? "in-use" : ""}`}
                key={asset.id}
                onClick={() => setSelectedAssetId(asset.id)}
              >
                {asset.type === "IMAGE" ? <Image src={asset.url} alt={`${asset.name}素材预览`} width={56} height={48} unoptimized={asset.url.startsWith("http://")} /> : <div className="asset-icon" aria-hidden="true">{asset.type === "3D" ? <Box size={17} /> : asset.type === "DOCUMENT" ? <FileText size={17} /> : <Music2 size={17} />}</div>}
                <span><strong>{localizedAssetName(asset.name)}</strong><small>{project.selected_assets?.[asset.type] === asset.id ? "正在使用" : `${assetTypeLabels[asset.type]} · 可选择`}</small></span>
              </button>
            ))}
            {!visibleAssets.length && <p className="empty-assets">这里还没有{assetTypeLabels[assetFilter]}素材。</p>}
          </div>
          {selectedAsset && selectedAsset.scope === libraryScope && (
            <div className="asset-quick-panel">
              {selectedAsset.type === "IMAGE" && <Image src={selectedAsset.url} alt={`${selectedAsset.name}大图预览`} width={220} height={138} unoptimized={selectedAsset.url.startsWith("http://")} />}
              <strong>{localizedAssetName(selectedAsset.name)}</strong>
              <div>
                {selectedAsset.type === "IMAGE" && <ImagePreviewButton url={selectedAsset.url} label="预览大图" />}
                <button type="button" disabled={busy || project.selected_assets?.[selectedAsset.type] === selectedAsset.id} onClick={() => void applyAsset(selectedAsset)}>
                  {project.selected_assets?.[selectedAsset.type] === selectedAsset.id ? "当前正在使用" : selectedAsset.scope === "LIBRARY" ? "加入项目并使用" : "立即使用"}
                </button>
                {selectedAsset.scope === "PROJECT" && <button type="button" disabled={busy || project.selected_assets?.[selectedAsset.type] === selectedAsset.id} onClick={() => { if (window.confirm(`从项目素材库删除“${localizedAssetName(selectedAsset.name)}”？`)) void mutate(() => api.deleteAsset(project.id, selectedAsset.id)); }}>删除素材</button>}
              </div>
            </div>
          )}
          <div className="library-note">精选演示素材始终保留原文件。移除项目引用不会删除素材源文件。</div>
        </aside>

        <section id="studio-workspace" className={`workspace-panel ${reviewGroup ? "workspace-reviewing" : ""}`} tabIndex={-1}>
          <header className="workspace-heading">
            <div><p className="eyebrow">{reviewGroup ? "回看已批准阶段" : `${currentGroup?.label ?? "知识"}创作区`}</p><h1>{workspaceTitle(displayProject.current_stage)}</h1></div>
            {reviewGroup
              ? <div className="workspace-heading-actions"><button disabled={busy} title="只修改这一项，后续内容保留" onClick={() => void mutate(async () => { const next = await api.revise(project.id, reviewGroup); setReviewGroup(null); return next; })}>单独修改本阶段</button><button className="return-current" onClick={() => setReviewGroup(null)}>返回当前阶段 <ChevronRight size={12} /></button></div>
              : project.current_stage.endsWith("_review")
                ? <button disabled={busy} title="只修改这一项，后续内容保留" onClick={() => void mutate(() => api.revise(project.id, stageKind(project.current_stage)))}>单独修改当前阶段</button>
                  : ["ready_to_build", "unity_connecting", "unity_building", "unity_review", "playtesting", "revision", "completed"].includes(project.current_stage)
                  ? <button disabled={busy} title="只修改逻辑，概念、视觉、素材和音乐会保留" onClick={() => void mutate(() => api.revise(project.id, "logic"))}>单独修改逻辑与构建计划</button>
                  : <span className="stage-state">{stageStateLabel(project.current_stage)}</span>}
          </header>
          {error && <div className="inline-error" role="alert"><X size={14} />{publicText(error)}</div>}
          {renderWorkspace({ project: displayProject, knowledge, idea, setIdea, busy, mutate, sendAgent, regenerate, readOnly: Boolean(reviewGroup) })}
        </section>

        <aside className="cocreator-panel">
          <div className="panel-heading"><MessageSquareText size={15} /><strong>共创助手</strong><span>在线</span></div>
          <div className="agent-context">
            <small>当前讨论内容</small>
            <strong>{currentGroup?.label} · {knowledge.title}</strong>
            <p>我会保留你的原始创意，并把知识动作连接到可玩的机制。我的建议可以拒绝或修改。</p>
          </div>
          <div className="chat-stream">
            <div className="chat-message assistant">
              <small>共创助手</small>
              <p>{project.player_idea ? "你的想法已经进入项目。下一步由你决定生成、讨论或修改。" : "先告诉我：你希望玩家通过这个知识做什么、感受到什么？"}</p>
            </div>
            {project.conversation_history.map((message) => (
              <div className={`chat-message ${message.role === "user" ? "user" : "assistant"}`} key={message.id}>
                <small>{message.role === "user" ? "你" : "共创助手"}</small>
                <p>{publicText(message.content)}</p>
                {message.role === "assistant" && message.suggestion_id && <div className="suggestion-actions">
                  {message.suggestion_response ? <span className="suggestion-decision">{decisionLabels[message.suggestion_response]}</span> : <>
                    <button onClick={() => void decideSuggestion(message.suggestion_id!, message.content, "accepted")}><Check size={11} />接受</button>
                    <button onClick={() => void decideSuggestion(message.suggestion_id!, message.content, "rejected")}><X size={11} />拒绝</button>
                    <button onClick={() => void decideSuggestion(message.suggestion_id!, message.content, "modified")}>修改</button>
                    <button onClick={() => void decideSuggestion(message.suggestion_id!, message.content, "discuss")}>讨论</button>
                  </>}
                </div>}
              </div>
            ))}
            {agentBusy && <div className="chat-message assistant thinking" role="status" aria-live="polite"><LoaderCircle className="spin" size={14} /> 共创助手正在思考你的方向……</div>}
          </div>
          <div className="chat-input">
            {pendingAttachments.length > 0 && <div className="pending-attachments">{pendingAttachments.map((item) => <span key={item.id}>{item.type === "IMAGE" ? <ImageIcon size={12} /> : <FileText size={12} />}{item.name}<button type="button" aria-label={`移除${item.name}`} onClick={() => setPendingAttachments((current) => current.filter((entry) => entry.id !== item.id))}><X size={11} /></button></span>)}</div>}
            <textarea value={agentInput} onChange={(event) => setAgentInput(event.target.value)} placeholder="讨论、拒绝或修改一条建议……" rows={3} />
            <div>
              <input ref={imageInputRef} hidden type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={(event) => void uploadFiles(event.target.files)} />
              <input ref={fileInputRef} hidden type="file" accept=".json,.md,.txt,.csv,application/json,text/plain,text/markdown,text/csv" multiple onChange={(event) => void uploadFiles(event.target.files)} />
              <button type="button" className="attachment-button" disabled={uploadBusy || agentBusy} onClick={() => imageInputRef.current?.click()}><ImagePlus size={13} />上传图片</button>
              <button type="button" className="attachment-button" disabled={uploadBusy || agentBusy} onClick={() => fileInputRef.current?.click()}><Paperclip size={13} />上传文件</button>
              {pendingAttachments.some((item) => item.type === "IMAGE") && <button type="button" className="reference-generate" disabled={busy || uploadBusy} onClick={() => void generateFromReferences()}><Sparkles size={13} />按参考图生成</button>}
              {kind === "logic" && <button className="code-proposal" onClick={() => void sendAgent("code", "基于当前已批准内容和游戏逻辑规格，提出一个安全的 Unity C# 代码结构方案。只提议，不执行。") }><Code2 size={13} />代码提议</button>}
              <button className="send-button" aria-label="发送给共创助手" disabled={(!agentInput.trim() && !pendingAttachments.length) || agentBusy || uploadBusy} onClick={() => void sendAgent()}><Send size={14} /></button>
            </div>
          </div>
        </aside>
      </div>

      <footer className="progress-bar">
        <div><small>项目进度</small><strong>{project.progress}%</strong></div>
        <div className="progress-track"><span style={{ width: `${Math.max(3, project.progress)}%` }} /></div>
        <div className="progress-summary">
          {stageGroups.slice(0, 6).map((group) => {
            const status = groupStatus(project, group.stages);
            return <span className={status} key={group.key}>{status === "complete" ? <Check size={10} /> : <i />}{group.label}</span>;
          })}
        </div>
      </footer>
    </main>
  );
}

function workspaceTitle(stage: string) {
  if (stage === "knowledge_selection") return "从你的想法开始";
  if (stage === "concept_drafting") return "让知识变成机制";
  if (stage === "concept_review") return "审阅游戏概念";
  if (stage === "visual_drafting") return "定义视觉方向";
  if (stage === "visual_review") return "选择视觉语言";
  if (stage === "3d_drafting") return "准备可直接使用的游戏素材";
  if (stage === "3d_review") return "审阅角色、道具与场景素材";
  if (stage === "music_drafting") return "让工序拥有声音层次";
  if (stage === "music_review") return "试听并选择项目音乐";
  if (stage === "logic_drafting") return "先批准逻辑，再谈代码";
  if (stage === "logic_review") return "审阅游戏逻辑规格";
  return "可以开始构建";
}

type WorkspaceProps = {
  project: Project;
  knowledge: (typeof knowledgeEntries)[number];
  idea: string;
  setIdea: (value: string) => void;
  busy: boolean;
  mutate: (action: () => Promise<Project>) => Promise<void>;
  sendAgent: (mode: "chat" | "code", suggested?: string) => Promise<void>;
  regenerate: (kind: "visual" | "3d" | "music", prompt?: string) => Promise<void>;
  readOnly: boolean;
};

function renderWorkspace({ project, knowledge, idea, setIdea, busy, mutate, sendAgent, regenerate, readOnly }: WorkspaceProps) {
  const stage = project.current_stage;
  const activeLogicData = project.artifacts.logic?.data as Record<string, unknown> | undefined;
  if (stage === "logic_review" && activeLogicData?.playtest_revision) return <ReadyToBuild project={project} mutate={mutate} />;
  if (readOnly && stage === "knowledge_selection") return (
    <div className="idea-workspace review-only-workspace">
      <div className="selected-knowledge">
        <Image src={knowledge.image_url} alt={`${knowledge.title}知识条目配图`} fill sizes="35vw" />
        <span><small>已选择的知识</small><strong>{knowledge.title}</strong><p>{knowledge.summary}</p></span>
      </div>
      <div className="idea-editor"><label>你的原始游戏想法</label><div className="review-only-idea">{project.player_idea || "尚未填写游戏想法"}</div><p>这是已批准阶段的历史记录。需要修改时，请使用右上角的“单独修改本阶段”。</p></div>
    </div>
  );
  if (stage === "knowledge_selection") return (
    <div className="idea-workspace">
      <div className="selected-knowledge">
        <Image src={knowledge.image_url} alt={`${knowledge.title}知识条目配图`} fill sizes="35vw" />
        <span><small>已选择的知识</small><strong>{knowledge.title}</strong><p>{knowledge.summary}</p></span>
      </div>
      <div className="idea-editor">
        <label htmlFor="player-idea">你的游戏想法</label>
        <textarea id="player-idea" value={idea} onChange={(event) => setIdea(event.target.value)} rows={6} />
        <p>你的原始想法会被保留。共创助手可以提出问题，但不能替你批准方向。</p>
        <button className="button button-primary" disabled={busy || idea.trim().length < 3} onClick={() => void mutate(() => api.saveIdea(project.id, idea.trim()))}>保存想法，进入概念 <ChevronRight size={14} /></button>
      </div>
    </div>
  );
  if (stage === "concept_drafting") return <ConceptPromptDraft project={project} idea={idea} setIdea={setIdea} mutate={mutate} busy={busy} />;
  if (stage === "concept_review") {
    const concept = dataOf<ConceptData>(project, "concept");
    if (!concept) return null;
    return <div className="concept-canvas">
      <div className="concept-hero"><span><small>游戏名称 / 第 {project.versions.concept} 版</small><h2>{concept.game_name}</h2><p>{concept.player_fantasy}</p></span><div><small>类型</small><strong>{concept.genre}</strong><small>时长</small><strong>{concept.estimated_duration}</strong></div></div>
      <div className="concept-grid">
        {[ ["游戏世界", concept.world], ["学习目标", concept.learning_objective], ["核心机制", concept.core_mechanic], ["核心循环", concept.core_loop], ["胜利条件", concept.win_condition], ["关卡结构", concept.level_structure] ].map(([label, value]) => <div key={label}><small>{label}</small><p>{value}</p></div>)}
      </div>
      <div className="alignment-check"><div><small>知识对应度</small><strong>{alignmentLabels[concept.alignment.score] ?? concept.alignment.score}</strong></div><div>{concept.alignment.represented.map((item) => <span key={item}><Check size={11} />{item}</span>)}{concept.alignment.missing.map((item) => <span className="missing" key={item}><i />{item} · 尚未体现</span>)}</div></div>
      <ApprovalActions label="批准游戏概念" onDiscuss={() => sendAgent("chat", "我想继续讨论这个概念，先指出它最可能偏离漆艺知识的地方。") } onApprove={() => mutate(() => api.approve(project.id, "concept"))} busy={busy} />
    </div>;
  }
  if (stage === "visual_drafting") return <VisualPromptDraft key={`${project.versions.production_mode ?? 0}-${project.versions.visual ?? 0}`} project={project} mutate={mutate} busy={busy} />;
  if (stage === "visual_review") {
    const visual = dataOf<VisualData>(project, "visual");
    if (!visual) return null;
    const selected = visual.variants.find((variant) => variant.id === visual.selected) ?? visual.variants[0];
    const save = async () => {
      if (!selected) return;
      const downloadUrl = new URL(selected.url, window.location.href);
      downloadUrl.searchParams.set("download", "1");
      const response = await fetch(downloadUrl, { cache: "no-store" });
      if (!response.ok) throw new Error("图片下载失败");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(await response.blob());
      link.download = `${selected.title || "漆问视觉方案"}.png`;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
    };
    const editPrompt = () => {
      const next = window.prompt("修改图片提示词（3 至 800 个字符）", visual.prompt)?.trim();
      if (next && next !== visual.prompt) void regenerate("visual", next);
    };
      return <div><div className="prompt-line"><small>当前提示词</small><p>{visual.prompt}</p></div><div className="visual-grid">{visual.variants.map((variant) => <figure className={variant.id === visual.selected ? "selected" : ""} key={variant.id}><div><Image src={variant.url} alt={variant.title} fill sizes="25vw" unoptimized={variant.url.startsWith("http://")} /></div><figcaption><span><small>方案 {variant.id.slice(-1)}</small><strong>{variant.title}</strong></span>{variant.id === visual.selected && <Check size={14} />}</figcaption></figure>)}</div>{busy && <p className="generation-status" role="status"><LoaderCircle className="spin" size={14} /> 当前画面正在生成，请稍候。</p>}<div className="asset-tool-row">{selected && <ImagePreviewButton url={selected.url} />}<button disabled={busy || !selected} onClick={() => void save().catch(() => window.alert("图片保存失败，请稍后重试。"))}>保存到电脑</button><button disabled={busy} onClick={() => void regenerate("visual")}>{busy ? "当前画面正在生成" : "重新生成并保留旧版"}</button><button disabled={busy} onClick={editPrompt}>修改提示词并生成</button><button disabled={busy} onClick={() => void mutate(() => api.reopen(project.id, "visual"))}>更改 2D / 3D 制作方式</button></div><ApprovalActions label="批准视觉方向" onDiscuss={() => sendAgent("chat", "比较这些视觉候选，重点分析哪一个最能表达薄髹与层积，而不是只谈好看。") } onApprove={() => mutate(() => api.approve(project.id, "visual"))} busy={busy} /></div>;
  }
  if (stage === "3d_drafting") return <TwoDAssetDraft key={project.versions.game_asset_plan ?? 0} project={project} mutate={mutate} busy={busy} />;
  if (stage === "3d_review") {
    const assetData = dataOf<ThreeDData | TwoDData>(project, "3d");
    if (!assetData) return null;
    if ("mode" in assetData && Array.isArray(assetData.variants)) {
      const selected = assetData.variants.find((item) => item.id === assetData.selected) ?? assetData.variants[0];
      const saveAsset = () => { if (!selected) return; const link = document.createElement("a"); link.href = selected.url; link.download = `漆问-${selected.title}.${assetData.mode === "3d" ? "glb" : "png"}`; link.rel = "noopener"; link.click(); };
      return <div><div className="prompt-line"><small>素材清单</small><p>共 {assetData.variants.length} 项独立{assetData.mode === "3d" ? "三维" : "二维"}游戏素材</p></div><div className="visual-grid">{assetData.variants.map((variant) => <figure className={variant.id === assetData.selected ? "selected" : ""} key={variant.id}><div>{assetData.mode === "3d" ? <ModelViewer url={variant.url} /> : <Image src={variant.url} alt={variant.title} fill sizes="40vw" unoptimized={variant.url.startsWith("http://")} />}</div><figcaption><span><small>{assetData.mode === "3d" ? "三维素材" : "二维素材"}</small><strong>{variant.title}</strong></span>{variant.id === assetData.selected && <Check size={14} />}</figcaption></figure>)}</div><div className="asset-tool-row"><button disabled={!selected} onClick={saveAsset}>保存到电脑</button><span>已逐项加入项目素材库</span></div><ApprovalActions label={`批准${assetData.mode === "3d" ? "三维" : "二维"}素材组`} onDiscuss={() => sendAgent("chat", "检查这些角色、道具、特效与场景是否足够支持实际游戏制作。") } onApprove={() => mutate(() => api.approve(project.id, "3d"))} busy={busy} /></div>;
    }
    const model = assetData as ThreeDData;
    const saveModel = () => { const link = document.createElement("a"); link.href = model.file; link.download = `${model.name}.glb`; link.rel = "noopener"; link.click(); };
    return <div className="model-review"><ModelViewer url={model.file} /><div className="model-metadata">{[["文件", model.name], ["格式", model.format], ["面数", model.polygon_count.toLocaleString()], ["材质", model.texture], ["版本", `第 ${project.versions["3d"]} 版`]].map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}</div><section className="code-boundary"><Box size={17} /><span><strong>这是旧版单模型项目</strong><p>当时只生成了一个模型。重新制作后会拆成角色、道具、特效和场景等多个独立条目。</p></span></section><div className="asset-tool-row"><button onClick={saveModel}>保存旧模型</button><button disabled={busy} onClick={() => void mutate(() => api.reworkGameAssets(project.id, "2d"))}>按 2D 多素材重做</button><button disabled={busy} onClick={() => void mutate(() => api.reworkGameAssets(project.id, "3d"))}>按 3D 多素材重做</button></div></div>;
  }
  if (stage === "music_drafting") return <MusicPromptDraft project={project} mutate={mutate} busy={busy} />;
  if (stage === "music_review") {
    const music = dataOf<MusicData>(project, "music");
    if (!music) return null;
    return <div className="music-review"><div className="prompt-line"><small>音乐提示词</small><p>{music.prompt}</p></div><div className="music-spec"><div><small>情绪</small><strong>{music.mood}</strong></div><div><small>速度</small><strong>每分钟 {music.tempo} 拍</strong></div><div><small>时长</small><strong>{music.duration} 秒</strong></div><div><small>循环</small><strong>{music.loop ? "是" : "否"}</strong></div></div>{music.tracks.map((track, index) => <div className={`audio-track ${track.id === music.selected ? "selected" : ""}`} key={track.id}><span><Music2 size={16} /><span><small>音轨 {index + 1}{track.id === music.selected ? " · 当前选择" : ""}</small><strong>{track.title}</strong></span></span><audio src={track.url} aria-label={`试听${track.title}`} controls loop /><span className="audio-actions">{track.id !== music.selected && <button disabled={busy} onClick={() => void mutate(() => api.selectMusicTrack(project.id, track.id))}>选择这个版本</button>}<button disabled={busy} onClick={() => { if (window.confirm(`删除“${track.title}”？`)) void mutate(() => api.deleteMusicTrack(project.id, track.id)); }}>删除</button></span></div>)}<div className="asset-tool-row"><button disabled={busy} onClick={() => void mutate(() => api.reopen(project.id, "music"))}>修改提示词并继续生成</button></div><ApprovalActions label="批准音乐" onDiscuss={() => sendAgent("chat", "检查这些音轨是否具有持续和弦、旋律与低音，而不是只有敲击声。") } onApprove={() => mutate(() => api.approve(project.id, "music"))} busy={busy} /></div>;
  }
  if (stage === "logic_drafting") return <LogicPromptDraft project={project} mutate={mutate} busy={busy} />;
  if (stage === "logic_review") {
    const logic = dataOf<LogicData>(project, "logic");
    if (!logic) return null;
    const plan = logic.unity_build_plan;
    return <div className="logic-spec"><LogicBlock label="玩家操作" value={logic.player} /><LogicBlock label="玩法规则" value={logic.painting} /><LogicBlock label="回合" value={logic.rounds} /><div className="logic-split"><LogicBlock label="胜利" value={logic.win} /><LogicBlock label="失败" value={logic.fail} /></div><LogicBlock label="声音事件" value={logic.audio_cues} /><LogicBlock label="验收条件" value={logic.acceptance} />{plan && <section className="code-boundary"><Code2 size={17} /><span><strong>Unity 构建计划</strong><p>{templateLabel(plan.template_id)} · 《{plan.game_title}》</p><p>{plan.player_instructions}</p><p>目标 {plan.target_count} · 限时 {plan.time_limit_seconds} 秒 · 允许失误 {plan.failure_limit}</p><p>素材角色：{plan.asset_roles.join("、") || "等待分配"}</p><p>声音事件：{plan.audio_cues.join("、") || "无"}</p></span><button onClick={() => void sendAgent("chat", "检查这份 Unity 构建计划是否准确对应我的游戏概念、素材和胜负规则。")}>讨论构建计划</button></section>}<div className="code-boundary"><Code2 size={17} /><span><strong>代码边界</strong><p>批准后只能执行这里显示的受约束计划；不能换成固定演示游戏。</p></span><button onClick={() => void sendAgent("code", "为这个游戏逻辑规格提出 Unity C# 类结构、状态和测试方案。不要执行或写文件。")}>请求代码提议</button></div><ApprovalActions label="批准逻辑与构建计划" onDiscuss={() => sendAgent("chat", "审查这份逻辑和 Unity 构建计划，并指出需要我决定的地方。") } onApprove={() => mutate(() => api.approve(project.id, "logic"))} busy={busy} /></div>;
  }
  return <ReadyToBuild project={project} mutate={mutate} />;
}

function ConceptPromptDraft({ project, idea, setIdea, mutate, busy }: { project: Project; idea: string; setIdea: (value: string) => void; mutate: (action: () => Promise<Project>) => Promise<void>; busy: boolean }) {
  const existing = dataOf<ConceptData>(project, "concept");
  const initialDirection = existing
    ? `游戏名称：${existing.game_name}\n类型：${existing.genre}\n玩家体验：${existing.player_fantasy}\n世界：${existing.world}\n学习目标：${existing.learning_objective}\n核心机制：${existing.core_mechanic}\n核心循环：${existing.core_loop}\n胜利条件：${existing.win_condition}\n关卡结构：${existing.level_structure}`
    : "请根据我的原始想法和所选漆艺知识，设计一个真正可玩的游戏概念。写清玩家操作、核心循环、胜负条件、关卡结构和知识如何进入玩法。";
  const [direction, setDirection] = useState(initialDirection);
  const generate = async () => {
    const saved = await api.saveIdea(project.id, idea.trim());
    return api.generate(saved.id, "concept", direction.trim());
  };
  return <div className="draft-panel prompt-draft">
    <div className="draft-symbol"><Sparkles size={18} /></div>
    <p className="eyebrow">生成前可以修改</p>
    <h2>游戏概念</h2>
    <label><span>你的原始游戏想法</span><textarea rows={5} maxLength={2000} value={idea} onChange={(event) => setIdea(event.target.value)} /></label>
    <label><span>概念修改要求</span><textarea rows={9} maxLength={3000} value={direction} onChange={(event) => setDirection(event.target.value)} /></label>
    <button className="button button-primary" disabled={busy || idea.trim().length < 3 || direction.trim().length < 3} onClick={() => void mutate(generate)}>{busy ? <LoaderCircle className="spin" size={14} /> : <Sparkles size={14} />}{busy ? "正在生成游戏概念" : "按当前要求生成概念"}</button>
    <small>重新生成会保留旧版本，并要求从本阶段开始重新审批。</small>
  </div>;
}

function VisualPromptDraft({ project, mutate, busy }: { project: Project; mutate: (action: () => Promise<Project>) => Promise<void>; busy: boolean }) {
  const mode = productionModeOf(project);
  const plannedAssets = dataOf<GameAssetPlanData>(project, "game_asset_plan")?.items ?? [];
  const existingPrompt = dataOf<VisualData>(project, "visual")?.prompt;
  const twoDPrompt = "彩色卡通 2D 横版游戏概念图，中国漆艺主题；清晨漆林连接温暖作坊，学徒角色、漆树、漆碗和可交互工序道具；清晰轮廓、分层绘制、丰富协调的青绿、朱红与金色，不要三维写实，不要黑白灰，不要文字水印。";
  const threeDPrompt = "彩色卡通 3D 游戏概念图，中国漆艺主题；清晨漆林与温暖作坊，学徒角色、漆树、漆碗和可交互工序道具；风格化低多边形造型、清晰体块、青绿朱红与金色、漆面高光，不要写实恐怖感，不要黑白灰，不要文字水印。";
  const [prompt, setPrompt] = useState(existingPrompt ?? (mode === "3d" ? threeDPrompt : twoDPrompt));
  return <div className="draft-panel prompt-draft"><div className="draft-symbol"><Sparkles size={18} /></div><p className="eyebrow">先选择制作方式</p><h2>选择 2D 或 3D 游戏</h2><p>两条路线都会保留。选择后可以继续修改提示词，再决定是否生成。</p><div className="mode-choice" role="group" aria-label="游戏制作方式"><button type="button" className={mode === "2d" ? "active" : ""} disabled={busy} onClick={() => void mutate(() => api.setProductionMode(project.id, "2d"))}><strong>2D 游戏</strong><span>角色精灵、分层场景、横版或俯视玩法</span></button><button type="button" className={mode === "3d" ? "active" : ""} disabled={busy} onClick={() => void mutate(() => api.setProductionMode(project.id, "3d"))}><strong>3D 游戏</strong><span>立体角色、模型、材质与可旋转场景</span></button></div>{mode === "2d" && plannedAssets.length > 0 && <section className="code-boundary"><ImageIcon size={17} /><span><strong>本游戏需要 {plannedAssets.length} 项独立素材</strong><p>{plannedAssets.map((item) => item.name).join("、")}</p></span></section>}<label><span>整体美术风格提示词</span><textarea rows={7} maxLength={800} value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label><div className="draft-fields"><span>彩色卡通</span><span>{mode === "3d" ? "风格化三维游戏" : "二维游戏画面"}</span><span>角色、场景与漆艺道具</span></div><button className="button button-primary" disabled={busy || !mode || prompt.trim().length < 3} onClick={() => void mutate(() => api.generate(project.id, "visual", prompt.trim()))}>{busy ? <LoaderCircle className="spin" size={14} /> : <Sparkles size={14} />}{busy ? "当前画面正在生成" : mode ? "生成整体风格参考" : "请先选择 2D 或 3D"}</button><small>批准整体风格后，以上素材会逐项生成、命名、预览、确认或删除。</small></div>;
}

function MusicPromptDraft({ project, mutate, busy }: { project: Project; mutate: (action: () => Promise<Project>) => Promise<void>; busy: boolean }) {
  const existing = dataOf<MusicData>(project, "music");
  const [prompt, setPrompt] = useState(existing?.prompt ?? "彩色卡通漆艺游戏循环配乐，温暖而专注；持续和弦、清晰但克制的主旋律、柔和低音线与轻量木质节奏，适合手工髹涂过程，不要只有敲击声，不要语音。");
  return <div className="draft-panel prompt-draft"><div className="draft-symbol"><Music2 size={18} /></div><p className="eyebrow">生成前可以修改</p><h2>设计游戏音乐</h2><label><span>音乐提示词</span><textarea rows={7} maxLength={800} value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label><div className="draft-fields"><span>持续和弦</span><span>主旋律</span><span>低音线</span><span>轻量节奏</span></div><button className="button button-primary" disabled={busy || prompt.trim().length < 3} onClick={() => void mutate(() => api.generate(project.id, "music", prompt.trim()))}>{busy ? <LoaderCircle className="spin" size={14} /> : <Music2 size={14} />}{busy ? "当前音乐正在生成" : "按当前提示词生成音乐"}</button><small>新版本会保留在当前音乐列表中；生成后可以试听、选择或删除任意版本。</small></div>;
}

function LogicPromptDraft({ project, mutate, busy }: { project: Project; mutate: (action: () => Promise<Project>) => Promise<void>; busy: boolean }) {
  const existing = dataOf<LogicData>(project, "logic");
  const initial = existing
    ? `玩家操作：${existing.player}\n玩法规则：${existing.painting.join("；")}\n回合：${existing.rounds}\n胜利：${existing.win}\n失败：${existing.fail}\n声音事件：${existing.audio_cues.join("；")}`
    : "请根据已批准概念与素材设计可在 Unity 中执行的游戏逻辑。写清玩家操作、交互对象、回合、胜利、失败、声音事件和验收条件；不得替换成固定演示游戏。";
  const [prompt, setPrompt] = useState(initial);
  return <div className="draft-panel prompt-draft"><div className="draft-symbol"><Code2 size={18} /></div><p className="eyebrow">可修改逻辑方向</p><h2>游戏逻辑规格</h2><label><span>逻辑修改要求</span><textarea rows={9} maxLength={2000} value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label><button className="button button-primary" disabled={busy || prompt.trim().length < 3} onClick={() => void mutate(() => api.generate(project.id, "logic", prompt.trim()))}>{busy ? <LoaderCircle className="spin" size={14} /> : <Code2 size={14} />}{busy ? "正在生成逻辑" : "按修改要求生成逻辑与构建计划"}</button><small>生成后仍需重新审批；旧版本和之前的 Unity 构建证据继续保留。</small></div>;
}

function TwoDAssetDraft({ project, mutate, busy }: { project: Project; mutate: (action: () => Promise<Project>) => Promise<void>; busy: boolean }) {
  const source = dataOf<GameAssetPlanData>(project, "game_asset_plan") ?? { style: "彩色卡通二维游戏美术，清晰深色描边，青绿、朱红、鎏金与深漆色统一搭配，透明背景，无文字。", items: [] };
  const mode = source.mode ?? productionModeOf(project) ?? "2d";
  const [style, setStyle] = useState(source.style);
  const [items, setItems] = useState<GameAssetPlanItem[]>(source.items);
  const [assets, setAssets] = useState<Asset[]>([]);
  useEffect(() => { void api.assets(project.id).then(setAssets); }, [project.id, project.versions.game_asset_plan]);
  const update = (id: string, key: "name" | "category" | "prompt", value: string) => setItems((current) => current.map((item) => item.id === id ? { ...item, [key]: value } : item));
  const persist = () => api.saveGameAssetPlan(project.id, style, items);
  const generate = (itemId: string) => mutate(async () => { await persist(); return api.generateGameAsset(project.id, itemId); });
  const addItem = () => setItems((current) => [...current, { id: `custom-${Date.now()}`, name: "新素材", category: "道具", prompt: "彩色卡通 2D 游戏独立素材，单个完整对象，透明背景，无文字。", asset_id: null, status: "pending" }]);
  const allApproved = items.length > 0 && items.every((item) => item.status === "approved");
  return <div className="game-asset-board">
    <header><div><small>独立素材清单</small><h2>逐项生成游戏素材</h2></div><button type="button" onClick={addItem}>添加素材</button></header>
    <label className="style-field"><span>统一美术风格</span><textarea rows={3} value={style} maxLength={500} onChange={(event) => setStyle(event.target.value)} /></label>
    <div className="asset-item-list">{items.map((item, index) => {
      const asset = assets.find((entry) => entry.id === item.asset_id);
      return <article className="asset-item-card" key={item.id}>
        <div className="asset-item-number">{String(index + 1).padStart(2, "0")}</div>
        <div className="asset-item-editor"><div><input aria-label={`素材名称 ${index + 1}`} value={item.name} maxLength={80} onChange={(event) => update(item.id, "name", event.target.value)} /><input aria-label={`素材分类 ${index + 1}`} value={item.category} maxLength={40} onChange={(event) => update(item.id, "category", event.target.value)} /></div><textarea aria-label={`${item.name}提示词`} rows={5} value={item.prompt} maxLength={800} onChange={(event) => update(item.id, "prompt", event.target.value)} /></div>
        <div className="asset-item-result">{asset ? <><div>{mode === "3d" ? <ModelViewer url={asset.url} /> : <Image src={asset.url} alt={item.name} fill sizes="180px" unoptimized />}</div><strong>{item.status === "approved" ? "已确认" : "待确认"}</strong><span>{mode === "2d" && <ImagePreviewButton url={asset.url} />}<button type="button" disabled={busy} onClick={() => void mutate(() => api.deleteGameAsset(project.id, asset.id))}>删除</button>{item.status !== "approved" && <button type="button" disabled={busy} onClick={() => void mutate(() => api.approveGameAsset(project.id, asset.id))}>确认使用</button>}</span></> : <><div className="asset-empty">{mode === "3d" ? <Box size={20} /> : <ImageIcon size={20} />}</div><button type="button" disabled={busy || item.prompt.trim().length < 3 || item.name.trim().length < 1} onClick={() => void generate(item.id)}>{busy ? "生成中" : "生成这一项"}</button></>}</div>
      </article>;
    })}</div>
    <div className="asset-board-actions"><button type="button" disabled={busy} onClick={() => void mutate(persist)}>保存清单</button><button className="button button-primary" type="button" disabled={busy || !allApproved} onClick={() => void mutate(() => api.finalizeGameAssets(project.id))}>全部确认，进入素材总审阅</button></div>
  </div>;
}

function ApprovalActions({ label, onDiscuss, onApprove, busy }: { label: string; onDiscuss: () => Promise<void>; onApprove: () => Promise<void>; busy: boolean }) {
  return <div className="approval-actions"><div><button onClick={() => void onDiscuss()}>讨论与修改</button><span><RotateCcw size={12} /> 当前版本已自动保存</span></div><button className="approve-button" disabled={busy} onClick={() => void onApprove()}>{busy ? <LoaderCircle className="spin" size={14} /> : <Check size={14} />}{label}</button></div>;
}

function LogicBlock({ label, value }: { label: string; value: string | string[] }) {
  return <div className="logic-block"><small>{label}</small>{Array.isArray(value) ? <ul>{value.map((item) => <li key={item}>{item}</li>)}</ul> : <p>{value}</p>}</div>;
}

function ReadyToBuild({ project, mutate }: { project: Project; mutate: (action: () => Promise<Project>) => Promise<void> }) {
  const approvedPlan = dataOf<LogicData>(project, "logic")?.unity_build_plan;
  const [health, setHealth] = useState<{ bridge: string; unity: string; mcp: string; detail: string } | null>(null);
  const [buildJob, setBuildJob] = useState<Awaited<ReturnType<typeof api.buildInUnity>> | null>(null);
  const [buildError, setBuildError] = useState("");
  const [starting, setStarting] = useState(false);
  const [streamState, setStreamState] = useState("等待任务");
  const [coAssets, setCoAssets] = useState<Asset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [coObjectName, setCoObjectName] = useState("玩家资产_漆碗");
  const [templateId, setTemplateId] = useState(approvedPlan?.template_id ?? "simulation-layering");
  const [changes, setChanges] = useState<Awaited<ReturnType<typeof api.unityChanges>>>([]);
  const [coBusy, setCoBusy] = useState(false);
  const [playtests, setPlaytests] = useState<Awaited<ReturnType<typeof api.playtests>>>([]);
  const [playtestFeedback, setPlaytestFeedback] = useState("层积节奏太快，希望每层完成时有更清晰的停顿与反馈。");
  const [playtestRating, setPlaytestRating] = useState(3);
  const [playtestBusy, setPlaytestBusy] = useState(false);
  const storageKey = `漆问-Unity-任务-${project.id}`;

  useEffect(() => {
    let active = true;
    const refreshHealth = () => void api.unityHealth().then((value) => { if (active) setHealth(value); }).catch((reason) => {
      if (active) setBuildError(reason instanceof Error ? reason.message : "无法连接本地桥接");
    });
    refreshHealth();
    const timer = window.setInterval(refreshHealth, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    const savedJobId = window.localStorage.getItem(storageKey);
    if (!savedJobId) return;
    void api.unityJob(savedJobId).then(setBuildJob).catch(() => window.localStorage.removeItem(storageKey));
  }, [storageKey]);

  useEffect(() => {
    let active = true;
    void Promise.all([api.assets(project.id), api.unityChanges(project.id), api.playtests(project.id)]).then(([assets, history, sessions]) => {
      if (!active) return;
      const twoD = (project.artifacts["3d"]?.data as Record<string, unknown> | undefined)?.mode === "2d";
      const models = assets.filter((asset) => twoD ? asset.type === "IMAGE" && ((asset.metadata.artifact === "game_asset" && asset.metadata.approved === true) || asset.metadata.artifact === "3d") : asset.type === "3D");
      setCoAssets(models);
      setSelectedAssetId((current) => current || models[0]?.id || "");
      setChanges(history);
      setPlaytests(sessions);
    }).catch((reason) => { if (active) setBuildError(reason instanceof Error ? reason.message : "无法读取共创记录"); });
    return () => { active = false; };
  }, [project.id, project.artifacts]);

  useEffect(() => {
    if (!buildJob?.id) return;
    if (["成功", "失败", "已取消", "已接管"].includes(buildJob.status)) {
      return;
    }
    const jobId = buildJob.id;
    let active = true;
    const source = new EventSource(unityEventUrl(jobId, 0));
    const refresh = () => void api.unityJob(jobId).then((value) => {
      if (active) setBuildJob(value);
    }).catch((reason) => {
      if (active) setBuildError(reason instanceof Error ? reason.message : "无法读取 Unity 构建状态");
    });
    source.onopen = () => { if (active) setStreamState("实时连接正常"); };
    source.addEventListener("构建事件", refresh);
    source.onerror = () => { if (active) setStreamState("实时连接重连中"); };
    const fallback = window.setInterval(refresh, 5000);
    return () => { active = false; source.close(); window.clearInterval(fallback); };
  }, [buildJob?.id, buildJob?.status]);

  const startBuild = async () => {
    setStarting(true);
    setBuildError("");
    try {
      const job = await api.buildInUnity(project.id);
      window.localStorage.setItem(storageKey, job.id);
      setBuildJob(job);
    }
    catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法启动 Unity 构建"); }
    finally { setStarting(false); }
  };

  const retryBuild = async () => {
    if (!buildJob) return;
    setStarting(true); setBuildError("");
    try { setBuildJob(await api.retryUnityJob(buildJob.id)); }
    catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法重试 Unity 构建"); }
    finally { setStarting(false); }
  };

  const takeover = async () => {
    if (!buildJob) return;
    setStarting(true); setBuildError("");
    try { setBuildJob(await api.takeoverUnityJob(buildJob.id)); }
    catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法切换到人工接管"); }
    finally { setStarting(false); }
  };

  const previewChange = async (action: "add_asset" | "adjust_asset" | "request_interaction") => {
    setCoBusy(true); setBuildError("");
    try {
      const payload: Record<string, unknown> = {
        action,
        object_name: coObjectName,
        transform: { position: [1.5, 0.25, 0], rotation: [0, 45, 0], scale: [1, 1, 1] },
      };
      if (action === "add_asset") payload.asset_id = selectedAssetId;
      if (action === "request_interaction") {
        payload.template_id = templateId;
        payload.interaction = "玩家操作资产时，按照所选模板推进可见状态并给出中文反馈。";
      }
      const change = await api.previewUnityChange(project.id, payload);
      setChanges((current) => [change, ...current]);
    } catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法生成 Unity 变更预览"); }
    finally { setCoBusy(false); }
  };

  const decideChange = async (changeId: string, decision: "approve" | "reject") => {
    setCoBusy(true); setBuildError("");
    try {
      const result = await api.decideUnityChange(changeId, decision);
      setChanges((current) => current.map((item) => item.id === result.id ? result : item));
    } catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法处理 Unity 变更"); }
    finally { setCoBusy(false); }
  };

  const undoChange = async (changeId: string) => {
    setCoBusy(true); setBuildError("");
    try {
      const result = await api.undoUnityChange(changeId);
      setChanges((current) => current.map((item) => item.id === result.id ? result : item));
    } catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法撤销 Unity 变更"); }
    finally { setCoBusy(false); }
  };

  const replacePlaytest = (session: Awaited<ReturnType<typeof api.startPlaytest>>) => setPlaytests((current) => [session, ...current.filter((item) => item.id !== session.id)]);

  const startPlaytest = async () => {
    setPlaytestBusy(true); setBuildError("");
    try { replacePlaytest(await api.startPlaytest(project.id, buildJob?.status === "成功" ? buildJob.id : undefined)); }
    catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法开始试玩"); }
    finally { setPlaytestBusy(false); }
  };

  const submitPlaytestFeedback = async (final = false) => {
    const session = playtests[0]; if (!session) return;
    setPlaytestBusy(true); setBuildError("");
    try { replacePlaytest(final ? await api.completePlaytest(session.id, playtestFeedback, playtestRating) : await api.playtestFeedback(session.id, playtestFeedback, playtestRating)); }
    catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法记录试玩反馈"); }
    finally { setPlaytestBusy(false); }
  };

  const proposeRevision = async () => {
    const session = playtests[0]; if (!session) return;
    setPlaytestBusy(true); setBuildError("");
    try { const result = await api.proposePlaytestRevision(session.id, coObjectName, templateId); replacePlaytest(result.playtest); setChanges((current) => [result.change, ...current]); }
    catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法提出试玩修改"); }
    finally { setPlaytestBusy(false); }
  };

  const approveRevision = async () => {
    const session = playtests[0]; if (!session) return;
    setPlaytestBusy(true); setBuildError("");
    try { const result = await api.approvePlaytestRevision(session.id); replacePlaytest(result.playtest); setChanges((current) => current.map((item) => item.id === result.change.id ? result.change : item)); }
    catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法批准试玩修改"); }
    finally { setPlaytestBusy(false); }
  };

  const finishProject = async () => {
    setPlaytestBusy(true); setBuildError("");
    try {
      await mutate(() => api.finishProject(project.id));
      setPlaytests(await api.playtests(project.id));
    } catch (reason) { setBuildError(reason instanceof Error ? reason.message : "无法完成项目"); }
    finally { setPlaytestBusy(false); }
  };

  const twoDProject = productionModeOf(project) === "2d";
  const items = [
    ["知识", "已批准"], ["游戏概念", `第 ${project.versions.concept} 版已批准`],
    ["视觉", `第 ${project.versions.visual} 版已批准`], [twoDProject ? "二维素材" : "三维资产", `已确认 ${coAssets.length} 项`],
    ["音乐", `第 ${project.versions.music} 版已批准`], ["游戏逻辑", `第 ${project.versions.logic} 版已批准`],
    ["Unity", buildJob?.status ?? "等待玩家启动"],
  ];
  const latestEvent = buildJob?.events.at(-1);
  const running = ["排队中", "执行中"].includes(buildJob?.status ?? "");
  const terminal = ["成功", "失败", "已取消", "已接管"].includes(buildJob?.status ?? "");
  const canRetry = buildJob?.status === "失败" && buildJob.attempt < buildJob.maxAttempts;
  const domainEvent = buildJob?.events.slice().reverse().find((event) => event.message.includes("域重载") || event.stage === "编译");
  const visibleStreamState = buildJob && ["成功", "失败", "已取消", "已接管"].includes(buildJob.status) ? "任务已结束" : streamState;
  const pendingChange = changes.find((change) => change.status === "preview");
  const activePlaytest = playtests[0];
  return <div className="ready-build">
    <p className="eyebrow">所有必要审批均已记录</p><h2>可以开始构建</h2>
    <p>构建过程在可见的 Unity 编辑器中执行。Unity 只执行你已批准的构建计划，不会替换成固定演示游戏。</p>
    {approvedPlan && <section className="code-boundary"><Code2 size={17} /><span><strong>将要构建：{templateLabel(approvedPlan.template_id)}</strong><p>《{approvedPlan.game_title}》 · {approvedPlan.player_instructions}</p><p>目标 {approvedPlan.target_count} · 限时 {approvedPlan.time_limit_seconds} 秒 · 允许失误 {approvedPlan.failure_limit}</p></span></section>}
    <div>{items.map(([label, value]) => <span key={label}><small>{label}</small><strong><Check size={13} />{value}</strong></span>)}</div>
    <section className="unity-monitor">
      <header><div><small>本地连接</small><strong>{health?.bridge ?? "检测中"}</strong></div><div><small>Unity 编辑器</small><strong>{health?.unity ?? "检测中"}</strong></div><div><small>工具通道</small><strong>{health?.mcp ?? "检测中"}</strong></div><div><small>实时事件</small><strong>{buildJob ? visibleStreamState : "等待任务"}</strong></div></header>
      <div className="unity-current"><div><small>当前动作</small><strong>{publicText(latestEvent?.stage ?? "尚未开始")}</strong><p>{publicText(latestEvent?.message ?? health?.detail ?? "正在检查本机环境…")}</p></div><b>{latestEvent?.progress ?? 0}%</b></div>
      <div className="progress-track" aria-label="构建进度"><span style={{ width: `${latestEvent?.progress ?? 0}%` }} /></div>
      <dl className="unity-facts"><div><dt>任务状态</dt><dd>{buildJob?.status ?? "未启动"}</dd></div><div><dt>执行轮次</dt><dd>{buildJob ? `${buildJob.attempt} / ${buildJob.maxAttempts}` : "—"}</dd></div><div><dt>编译与域重载</dt><dd>{domainEvent?.message ?? "等待编译"}</dd></div><div><dt>错误指纹</dt><dd>{buildJob?.errorFingerprint ?? "无"}</dd></div></dl>
      <div className="unity-console"><div className="unity-console-title"><strong>实时控制台</strong><small>{buildJob?.events.length ?? 0} 条事件</small></div>{buildJob?.events.length ? <ol>{buildJob.events.map((event) => <li key={event.sequence} data-level={event.level}><time>{new Date(event.time).toLocaleTimeString("zh-CN", { hour12: false })}</time><b>{event.source ?? "桥接"}</b><span>{publicText(event.stage)}</span><p>{publicText(event.message)}</p></li>)}</ol> : <p className="unity-empty">构建开始后，这里会连续显示桥接、Unity 与控制台事件。</p>}</div>
      {buildError && <p className="inline-error">{publicText(buildError)}</p>}
    </section>
    <section className="co-creation-panel">
      <header><div><small>游戏构建</small><h3>写入 Unity</h3></div></header>
      <div className="co-creation-controls">
        <label><span>选择游戏素材</span><select value={selectedAssetId} onChange={(event) => setSelectedAssetId(event.target.value)}>{coAssets.map((asset) => <option key={asset.id} value={asset.id}>{localizedAssetName(asset.name)}</option>)}</select></label>
        <label><span>场景对象名称</span><input value={coObjectName} maxLength={80} onChange={(event) => setCoObjectName(event.target.value)} /></label>
        <label><span>交互模板</span><select value={templateId} onChange={(event) => setTemplateId(event.target.value)}><option value="simulation-layering">模拟·薄髹层积</option><option value="timing-polish">时机·推光节律</option><option value="collection-materials">收集·材料辨识</option><option value="puzzle-process">谜题·工序排序</option><option value="target-lacquer-drops">目标·纹样点漆</option><option value="topdown-dodge">动作·俯视角躲避</option></select></label>
      </div>
      <div className="co-creation-buttons"><button disabled={coBusy || !selectedAssetId} onClick={() => void previewChange("add_asset")}>预览加入场景</button><button disabled={coBusy} onClick={() => void previewChange("adjust_asset")}>预览调整资产</button><button disabled={coBusy} onClick={() => void previewChange("request_interaction")}>请求交互提议</button></div>
      {pendingChange && <article className="change-preview"><div><small>尚未写入</small><h4>{pendingChange.preview.title}</h4><p>{pendingChange.preview.summary}</p></div><ul>{pendingChange.preview.differences.map((difference) => <li key={difference}>{difference}</li>)}</ul>{pendingChange.preview.generated_script && <details><summary>查看受控脚本差异</summary><pre>{pendingChange.preview.generated_script}</pre></details>}<footer><button disabled={coBusy} onClick={() => void decideChange(pendingChange.id, "reject")}>拒绝</button><button className="approve-change" disabled={coBusy} onClick={() => void decideChange(pendingChange.id, "approve")}>批准并建立检查点</button></footer></article>}
      <div className="change-history"><strong>变更与检查点</strong>{changes.length ? <ol>{changes.slice(0, 8).map((change) => <li key={change.id}><span><b>{change.action_label}</b><small>{change.status === "preview" ? "等待决定" : change.status === "applied" ? "已应用" : change.status === "undone" ? "已撤销" : change.status === "rejected" ? "已拒绝" : change.status === "failed" ? "失败" : change.status === "applying" ? "应用中" : change.status}</small></span><code>{change.id.slice(0, 8)}</code>{change.status === "applied" && <button disabled={coBusy} onClick={() => void undoChange(change.id)}>撤销到检查点</button>}</li>)}</ol> : <p>还没有共创变更。先选择资产并生成预览。</p>}</div>
    </section>
    <section className="playtest-panel">
      <header><div><small>试玩与修订</small><h3>试玩 → 反馈 → 修改 → 编译 → 再次试玩</h3></div><span>{activePlaytest?.status_label ?? "尚未开始"}</span></header>
      {!activePlaytest || activePlaytest.status === "completed" ? <div className="playtest-complete">{activePlaytest ? <dl><div><dt>绑定构建</dt><dd>{activePlaytest.build_job_id?.slice(0, 8) ?? "当前场景"}</dd></div><div><dt>逻辑修订</dt><dd>第 {activePlaytest.logic_version} 版 → 第 {String(activePlaytest.evidence.proposed_logic_version ?? activePlaytest.logic_version)} 版</dd></div><div><dt>首次评价</dt><dd>{activePlaytest.initial_rating} / 5 · {activePlaytest.initial_feedback}</dd></div><div><dt>编译证据</dt><dd>{String(activePlaytest.evidence.compile_errors ?? "—")} 个错误 · {activePlaytest.evidence.play_again ? "已再次试玩" : "未再次试玩"}</dd></div><div><dt>最终评价</dt><dd>{activePlaytest.final_rating} / 5 · {activePlaytest.final_feedback}</dd></div></dl> : <p>从当前已批准逻辑和成功构建开始一次可回看的试玩。</p>}<button disabled={playtestBusy || !["ready_to_build", "unity_review", "playtesting"].includes(project.current_stage)} onClick={() => void startPlaytest()}>开始新的试玩</button></div> : <div className="playtest-flow">
        <ol><li data-active={activePlaytest.status === "playing"}>首次试玩</li><li data-active={activePlaytest.status === "feedback"}>记录反馈</li><li data-active={activePlaytest.status === "revision_preview"}>审阅修改</li><li data-active={activePlaytest.status === "replaying"}>再次试玩</li><li data-active={activePlaytest.status === "awaiting_final_approval"}>最终确认</li></ol>
        <dl><div><dt>试玩会话</dt><dd>{activePlaytest.id.slice(0, 8)}</dd></div><div><dt>构建任务</dt><dd>{activePlaytest.build_job_id?.slice(0, 8) ?? "当前场景"}</dd></div><div><dt>绑定逻辑</dt><dd>第 {activePlaytest.logic_version} 版</dd></div><div><dt>批准新鲜度</dt><dd>{String(activePlaytest.evidence.approval_freshness ?? "当前版本已批准")}</dd></div></dl>
        {(activePlaytest.status === "playing" || activePlaytest.status === "replaying") && <div className="feedback-editor"><label>你的试玩反馈<textarea value={playtestFeedback} onChange={(event) => setPlaytestFeedback(event.target.value)} /></label><label>评分<select value={playtestRating} onChange={(event) => setPlaytestRating(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating} 分</option>)}</select></label><button disabled={playtestBusy || playtestFeedback.trim().length < 2} onClick={() => void submitPlaytestFeedback(activePlaytest.status === "replaying")}>{activePlaytest.status === "replaying" ? "保存最终试玩结果" : "记录反馈"}</button></div>}
        {activePlaytest.status === "feedback" && <div className="playtest-decision"><p>反馈已绑定到当前构建与逻辑版本。智能助手只提出最小修改，不会直接写入。</p><button disabled={playtestBusy} onClick={() => void proposeRevision()}>生成最小修改预览</button></div>}
        {activePlaytest.status === "revision_preview" && <div className="playtest-decision"><p>逻辑已生成新版本，旧批准已失效。批准后才会建立检查点、写入、真实编译并再次试玩。</p><button disabled={playtestBusy} onClick={() => void approveRevision()}>批准修改并再次试玩</button></div>}
        {activePlaytest.status === "awaiting_final_approval" && <div className="playtest-decision"><p>最终试玩结果已经保存。只有你确认后，项目才会标记为完成。</p><button disabled={playtestBusy} onClick={() => void finishProject()}>完成项目</button></div>}
      </div>}
    </section>
    <div className="ready-actions">
      {canRetry && <button type="button" disabled={starting} onClick={() => void retryBuild()}><RotateCcw size={13} />重试失败步骤</button>}
      {running && <button type="button" disabled={starting} onClick={() => void takeover()}><X size={13} />人工接管</button>}
      <button className="build-button" disabled={starting || running} onClick={() => void startBuild()}>{starting ? <LoaderCircle className="spin" size={14} /> : null}{terminal ? "重新构建" : "在 Unity 中构建"} <ChevronRight size={14} /></button>
    </div>
  </div>;
}
