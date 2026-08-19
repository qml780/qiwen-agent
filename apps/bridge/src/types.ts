export type BridgeStatus = "未连接" | "连接中" | "已连接" | "错误";

export type BuildStage =
  | "等待" | "启动编辑器" | "连接 MCP" | "连接工具通道" | "创建场景" | "导入模型" | "导入画面" | "导入音频"
  | "创建对象" | "生成脚本" | "挂载脚本" | "编译" | "试玩" | "完成" | "失败" | "人工接管";

export interface BuildRequest {
  projectId: string;
  unityProjectPath: string;
  modelPath?: string;
  spritePath?: string;
  spritePaths?: string[];
  mode?: "2d" | "3d";
  audioPath: string;
  runtimeScript: string;
  buildPlan: {
    schema_version: 1;
    template_id: "simulation-layering" | "timing-polish" | "collection-materials" | "puzzle-process" | "target-lacquer-drops" | "topdown-dodge";
    game_title: string;
    objective: string;
    player_instructions: string;
    target_count: number;
    time_limit_seconds: number;
    failure_limit: number;
    speed: number;
    sequence_steps: string[];
    asset_roles: string[];
    audio_cues: string[];
  };
}

export interface BuildEvent {
  sequence: number;
  time: string;
  stage: BuildStage;
  progress: number;
  message: string;
  level: "信息" | "成功" | "警告" | "错误";
  source?: "桥接" | "Unity" | "控制台";
}

export interface BuildJob {
  id: string;
  projectId: string;
  status: "排队中" | "执行中" | "成功" | "失败" | "已取消" | "已接管";
  adapter: string;
  createdAt: string;
  updatedAt: string;
  attempt: number;
  maxAttempts: number;
  errorFingerprint?: string;
  events: BuildEvent[];
}

export interface BuildContext {
  signal: AbortSignal;
  attempt: number;
}

export interface UnityAdapter {
  readonly name: string;
  health(): Promise<{ unity: BridgeStatus; mcp: BridgeStatus; detail: string }>;
  build(request: BuildRequest, emit: (event: Omit<BuildEvent, "sequence" | "time">) => void, context: BuildContext): Promise<void>;
}

export type CoCreationAction = "add_asset" | "adjust_asset" | "request_interaction" | "undo";

export interface CoCreationRequest {
  id: string;
  projectId: string;
  unityProjectPath: string;
  action: CoCreationAction;
  assetId?: string;
  assetPath?: string;
  objectName: string;
  position?: [number, number, number];
  rotation?: [number, number, number];
  scale?: [number, number, number];
  templateId?: string;
  interaction?: string;
  generatedScript?: string;
  checkpointPath?: string;
  originalScenePath?: string;
  playAfterApply?: boolean;
}
