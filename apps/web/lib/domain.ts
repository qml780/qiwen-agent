export type Stage =
  | "knowledge_selection"
  | "concept_drafting"
  | "concept_review"
  | "visual_drafting"
  | "visual_review"
  | "3d_drafting"
  | "3d_review"
  | "music_drafting"
  | "music_review"
  | "logic_drafting"
  | "logic_review"
  | "ready_to_build"
  | "unity_connecting"
  | "unity_building"
  | "unity_review"
  | "playtesting"
  | "revision"
  | "completed";

export type KnowledgeEntry = {
  id: string;
  category: string;
  title: string;
  english_title: string;
  summary: string;
  full_text: string;
  image_url: string;
  steps: string[];
  core_facts: string[];
  cause_effect_relations: string[];
  key_actions: string[];
  common_errors: string[];
  common_misconceptions: string[];
  expert_notes: string[];
  related_ids: string[];
  source: string;
  affordances: string[];
  game_affordances: string[];
  learning_objectives: string[];
  references: { title: string; url: string }[];
  image_prompt_zh: string;
  verification: string;
};

export type Approval = {
  id: string;
  artifact: string;
  version: number;
  approved_at: string;
};

export type ConversationMessage = {
  id: string;
  role: string;
  content: string;
  provider: string;
  suggestion_id: string | null;
  suggestion_response: string | null;
  created_at: string;
};

export type Project = {
  id: string;
  title: string;
  selected_knowledge_id: string;
  current_stage: Stage;
  player_idea: string;
  original_player_idea: string;
  artifacts: Record<string, { version: number; data: Record<string, unknown> }>;
  selected_assets: Record<string, string>;
  approvals: Record<string, Approval>;
  versions: Record<string, number>;
  conversation_history: ConversationMessage[];
  activity_log: string[];
  progress: number;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type Asset = {
  id: string;
  project_id: string | null;
  type: string;
  name: string;
  url: string;
  scope: "PROJECT" | "LIBRARY";
  sha256: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AgentResponse = {
  provider: string;
  model: string;
  content: string;
  demo_mode: boolean;
  suggestion_id: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_cny: number;
};

export const stageGroups = [
  { key: "knowledge", label: "知识", stages: ["knowledge_selection"] },
  { key: "concept", label: "概念", stages: ["concept_drafting", "concept_review"] },
  { key: "visual", label: "视觉", stages: ["visual_drafting", "visual_review"] },
  { key: "3d", label: "游戏素材", stages: ["3d_drafting", "3d_review"] },
  { key: "music", label: "音乐", stages: ["music_drafting", "music_review"] },
  { key: "logic", label: "逻辑", stages: ["logic_drafting", "logic_review"] },
  { key: "build", label: "构建", stages: ["ready_to_build", "unity_connecting", "unity_building", "unity_review", "playtesting", "revision", "completed"] },
] as const;

export const stageOrder: Stage[] = [
  "knowledge_selection",
  "concept_drafting",
  "concept_review",
  "visual_drafting",
  "visual_review",
  "3d_drafting",
  "3d_review",
  "music_drafting",
  "music_review",
  "logic_drafting",
  "logic_review",
  "ready_to_build",
  "unity_connecting",
  "unity_building",
  "unity_review",
  "playtesting",
  "revision",
  "completed",
];

export function groupStatus(project: Project, stages: readonly string[]) {
  const currentIndex = stageOrder.indexOf(project.current_stage);
  const indices = stages.map((stage) => stageOrder.indexOf(stage as Stage));
  const start = Math.min(...indices);
  const end = Math.max(...indices);
  if (currentIndex > end) return "complete";
  if (currentIndex >= start && currentIndex <= end) return "active";
  return "pending";
}
