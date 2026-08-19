from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Stage(StrEnum):
    KNOWLEDGE_SELECTION = "knowledge_selection"
    CONCEPT_DRAFTING = "concept_drafting"
    CONCEPT_REVIEW = "concept_review"
    VISUAL_DRAFTING = "visual_drafting"
    VISUAL_REVIEW = "visual_review"
    THREE_D_DRAFTING = "3d_drafting"
    THREE_D_REVIEW = "3d_review"
    MUSIC_DRAFTING = "music_drafting"
    MUSIC_REVIEW = "music_review"
    LOGIC_DRAFTING = "logic_drafting"
    LOGIC_REVIEW = "logic_review"
    READY_TO_BUILD = "ready_to_build"
    UNITY_CONNECTING = "unity_connecting"
    UNITY_BUILDING = "unity_building"
    UNITY_REVIEW = "unity_review"
    PLAYTESTING = "playtesting"
    REVISION = "revision"
    COMPLETED = "completed"


class KnowledgeEntry(BaseModel):
    id: str
    category: str
    title: str
    english_title: str = ""
    summary: str
    full_text: str = ""
    image_url: str = ""
    steps: list[str] = Field(default_factory=list)
    core_facts: list[str] = Field(default_factory=list)
    cause_effect_relations: list[str] = Field(default_factory=list)
    key_actions: list[str]
    common_errors: list[str] = Field(default_factory=list)
    common_misconceptions: list[str] = Field(default_factory=list)
    expert_notes: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    references: list[dict[str, str]] = Field(default_factory=list)
    image_prompt_zh: str = ""
    verification: str = ""
    related_ids: list[str] = Field(default_factory=list)
    source: str = ""
    affordances: list[str] = Field(default_factory=list)
    game_affordances: list[str] = Field(default_factory=list)


class AgentAttachment(BaseModel):
    id: str
    name: str
    mime: str = "application/octet-stream"
    type: str
    data_url: str | None = None
    text: str | None = None


class Approval(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    artifact: str
    version: int
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stage: str = ""
    status: str = "approved"
    approved_by: str = "player"
    comment: str = ""


class ConversationMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str
    content: str
    provider: str = "human"
    suggestion_id: str | None = None
    suggestion_response: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "未命名漆艺游戏"
    selected_knowledge_id: str
    current_stage: Stage = Stage.KNOWLEDGE_SELECTION
    player_idea: str = ""
    original_player_idea: str = ""
    artifacts: dict[str, Any] = Field(default_factory=dict)
    selected_assets: dict[str, str] = Field(default_factory=dict)
    approvals: dict[str, Approval] = Field(default_factory=dict)
    versions: dict[str, int] = Field(default_factory=dict)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    activity_log: list[str] = Field(default_factory=list)
    progress: int = 0
    revision: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreateProjectRequest(BaseModel):
    knowledge_id: str
    title: str | None = None


class IdeaRequest(BaseModel):
    idea: str = Field(min_length=3, max_length=2000)


class ProductionModeRequest(BaseModel):
    mode: str = Field(pattern="^(2d|3d)$")


class GameAssetPlanItem(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=40)
    prompt: str = Field(min_length=3, max_length=800)
    asset_id: str | None = None
    status: str = Field(default="pending", pattern="^(pending|generated|approved)$")


class GameAssetPlanRequest(BaseModel):
    style: str = Field(min_length=3, max_length=500)
    items: list[GameAssetPlanItem] = Field(min_length=1, max_length=30)


class GameAssetGenerateRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=80)


class AgentRequest(BaseModel):
    project_id: str
    message: str = Field(default="", max_length=8000)
    mode: str = Field(default="chat", pattern="^(chat|code)$")
    attachment_ids: list[str] = Field(default_factory=list, max_length=8)
    attachments: list[AgentAttachment] = Field(default_factory=list)


class UploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    mime: str = Field(min_length=1, max_length=100)
    data_base64: str = Field(min_length=1)


class AgentResponse(BaseModel):
    provider: str
    model: str
    content: str
    demo_mode: bool
    suggestion_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_cny: float = 0


class SuggestionResponseRequest(BaseModel):
    action: str = Field(pattern="^(accepted|rejected|modified|discuss)$")
    note: str = Field(default="", max_length=2000)


class UnityTransform(BaseModel):
    position: tuple[float, float, float] = (0, 0, 0)
    rotation: tuple[float, float, float] = (0, 0, 0)
    scale: tuple[float, float, float] = (1, 1, 1)


class UnityChangePreviewRequest(BaseModel):
    action: str = Field(pattern="^(add_asset|adjust_asset|request_interaction)$")
    asset_id: str | None = None
    object_name: str = Field(default="玩家资产_漆碗", min_length=1, max_length=80)
    transform: UnityTransform = Field(default_factory=UnityTransform)
    template_id: str | None = Field(default=None, pattern="^(simulation-layering|timing-polish|collection-materials|puzzle-process|target-lacquer-drops|topdown-dodge)$")
    interaction: str = Field(default="", max_length=500)


class UnityChangeDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")


class PlaytestStartRequest(BaseModel):
    build_job_id: str | None = None


class PlaytestFeedbackRequest(BaseModel):
    feedback: str = Field(min_length=2, max_length=2000)
    rating: int = Field(ge=1, le=5)


class PlaytestRevisionRequest(BaseModel):
    object_name: str = Field(default="玩家资产_漆碗二号", min_length=1, max_length=80)
    template_id: str = Field(default="simulation-layering", pattern="^(simulation-layering|timing-polish|collection-materials|puzzle-process|target-lacquer-drops|topdown-dodge)$")


class StructuredGeneration(BaseModel):
    provider: str
    model: str
    data: dict[str, Any]
    demo_mode: bool
    input_tokens: int = 0
    output_tokens: int = 0
    cost_cny: float = 0


class Asset(BaseModel):
    id: str
    project_id: str | None = None
    type: str
    name: str
    url: str
    scope: str
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalError(Exception):
    pass


GENERATION_TRANSITIONS: dict[str, tuple[Stage, Stage]] = {
    "concept": (Stage.CONCEPT_DRAFTING, Stage.CONCEPT_REVIEW),
    "visual": (Stage.VISUAL_DRAFTING, Stage.VISUAL_REVIEW),
    "3d": (Stage.THREE_D_DRAFTING, Stage.THREE_D_REVIEW),
    "music": (Stage.MUSIC_DRAFTING, Stage.MUSIC_REVIEW),
    "logic": (Stage.LOGIC_DRAFTING, Stage.LOGIC_REVIEW),
}

APPROVAL_TRANSITIONS: dict[str, tuple[Stage, Stage]] = {
    "concept": (Stage.CONCEPT_REVIEW, Stage.VISUAL_DRAFTING),
    "visual": (Stage.VISUAL_REVIEW, Stage.THREE_D_DRAFTING),
    "3d": (Stage.THREE_D_REVIEW, Stage.MUSIC_DRAFTING),
    "music": (Stage.MUSIC_REVIEW, Stage.LOGIC_DRAFTING),
    "logic": (Stage.LOGIC_REVIEW, Stage.READY_TO_BUILD),
}
