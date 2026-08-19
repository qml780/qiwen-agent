from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from .config import settings
from .domain import AgentRequest, AgentResponse, KnowledgeEntry, Project, StructuredGeneration

PROMPT_VERSION = "m3-v1"
logger = logging.getLogger(__name__)


def _redact_provider_message(message: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", message)


class Alignment(BaseModel):
    represented: list[str]
    missing: list[str]
    mechanic_mapping: dict[str, str] = Field(default_factory=dict)
    score: str = Field(pattern="^(Strong|Moderate|Weak)$")
    explanation: str


class GameConcept(BaseModel):
    game_name: str
    selected_knowledge: str
    genre: str
    player_fantasy: str
    world: str
    learning_objective: str
    core_mechanic: str
    core_loop: str
    player_actions: list[str]
    rules: list[str]
    feedback: list[str]
    failure_conditions: list[str]
    win_condition: str
    level_structure: str
    estimated_duration: str
    alignment: Alignment


class LogicSpecification(BaseModel):
    player: str
    painting: list[str]
    rounds: str
    win: str
    fail: str
    audio_cues: list[str]
    acceptance: list[str]


class UnityBuildPlan(BaseModel):
    """模型提出、服务端校验、Unity 模板执行的稳定中间表示。"""
    schema_version: int = Field(default=1, ge=1, le=1)
    template_id: Literal["simulation-layering", "timing-polish", "collection-materials", "puzzle-process", "target-lacquer-drops", "topdown-dodge"]
    game_title: str = Field(min_length=1, max_length=60)
    objective: str = Field(min_length=1, max_length=240)
    player_instructions: str = Field(min_length=1, max_length=240)
    target_count: int = Field(default=3, ge=1, le=20)
    time_limit_seconds: int = Field(default=45, ge=10, le=180)
    failure_limit: int = Field(default=3, ge=1, le=10)
    speed: float = Field(default=1.0, ge=0.2, le=10.0)
    sequence_steps: list[str] = Field(default_factory=list, max_length=8)
    asset_roles: list[str] = Field(default_factory=list, max_length=12)
    audio_cues: list[str] = Field(default_factory=list, max_length=12)


class AudioDesignPlan(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    mood: str = Field(min_length=1, max_length=100)
    tempo: int = Field(default=76, ge=40, le=180)
    duration: int = Field(default=20, ge=8, le=60)
    loop: bool = True
    layers: list[dict[str, Any]] = Field(default_factory=list, min_length=1, max_length=6)
    event_cues: list[str] = Field(default_factory=list, min_length=1, max_length=8)


class GeneratedCode(BaseModel):
    provider: str
    model: str
    source: str
    demo_mode: bool
    input_tokens: int = 0
    output_tokens: int = 0
    cost_cny: float = 0


class ProviderFailure(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class LLMProvider(ABC):
    name: str = "unknown"
    @abstractmethod
    async def respond(self, request: AgentRequest, project: Project, knowledge: KnowledgeEntry) -> AgentResponse:
        raise NotImplementedError

    @abstractmethod
    async def generate_structured(self, kind: str, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        raise NotImplementedError

    @abstractmethod
    async def generate_unity_code(self, project: Project, knowledge: KnowledgeEntry) -> GeneratedCode:
        raise NotImplementedError

    @abstractmethod
    async def generate_unity_plan(self, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        raise NotImplementedError


RUNTIME_SCRIPT_TEMPLATE = """using UnityEngine;

namespace QIWEN.Runtime
{
    public sealed class LacquerBowlExperience : MonoBehaviour
    {
        [SerializeField] private int lacquerLayers;
        private Vector3 baseScale;

        private void Start()
        {
            baseScale = transform.localScale;
            var source = GetComponent<AudioSource>();
            if (source != null && source.clip != null && !source.isPlaying) source.Play();
        }

        private void Update()
        {
            var pulse = 1f + Mathf.Sin(Time.time * 1.8f) * 0.015f;
            transform.localScale = baseScale * pulse;
        }

        private void OnMouseDown()
        {
            lacquerLayers = Mathf.Min(lacquerLayers + 1, 5);
            var sprite = GetComponent<SpriteRenderer>();
            if (sprite != null) sprite.color = Color.Lerp(Color.white, new Color(0.75f, 0.25f, 0.18f), lacquerLayers / 5f);
        }
    }
}
"""


def validate_unity_code(source: str) -> str:
    clean = source.strip().removeprefix("```csharp").removeprefix("```cs").removesuffix("```").strip()
    required = ("namespace QIWEN.Runtime", "class LacquerBowlExperience", "MonoBehaviour")
    forbidden = ("System.IO", "System.Diagnostics", "System.Net", "UnityEditor", "DllImport", "Process.", "File.", "Directory.")
    if len(clean) > 12_000 or not all(value in clean for value in required) or any(value in clean for value in forbidden):
        raise ProviderFailure("unsafe_generated_code", "生成的 Unity 代码未通过窄权限校验")
    return clean + "\n"


def _expected_template(project: Project) -> str:
    concept = project.artifacts.get("concept", {}).get("data", {})
    logic = project.artifacts.get("logic", {}).get("data", {})
    text = json.dumps({"idea": project.original_player_idea, "concept": concept, "logic": logic}, ensure_ascii=False)
    # 先识别核心操作循环。玩法中提到“按顺序完成工序”并不等于排序谜题；
    # 只有明确操作卡片/排列工序时才选择谜题模板。
    if any(token in text for token in ("躲避", "闪避", "弹幕", "漆滴", "液滴", "危险物", "四方向移动", "方向键移动", "不能攻击", "坚持倒计时")):
        return "topdown-dodge"
    if any(token in text for token in ("排序", "排列工序", "工序卡", "依次选择卡片")):
        return "puzzle-process"
    if any(token in text for token in ("收集", "材料辨识", "样本")):
        return "collection-materials"
    if any(token in text for token in ("推光", "节拍", "节奏命中")):
        return "timing-polish"
    if any(token in text for token in ("纹样", "点漆", "落点", "瞄准")):
        return "target-lacquer-drops"
    return "simulation-layering"


def _constrain_plan_to_approved(project: Project, plan: dict[str, Any]) -> dict[str, Any]:
    concept = project.artifacts.get("concept", {}).get("data", {})
    logic = project.artifacts.get("logic", {}).get("data", {})
    result = dict(plan)
    result["template_id"] = _expected_template(project)
    game_title = str(concept.get("game_name") or "").strip()
    objective = str(logic.get("win") or "").strip()
    player_instructions = str(logic.get("player") or "").strip()
    if game_title: result["game_title"] = game_title[:60]
    if objective: result["objective"] = objective[:240]
    if player_instructions: result["player_instructions"] = player_instructions[:240]
    if logic.get("audio_cues"):
        result["audio_cues"] = [str(item).strip() for item in logic["audio_cues"] if str(item).strip()][:12]
    approved_text = json.dumps({"idea":project.original_player_idea,"concept":concept,"logic":logic}, ensure_ascii=False)
    count_match = re.search(r"([1-9]|1\d|20)\s*(?:步|层|个|次|种|回合)", approved_text)
    if count_match: result["target_count"] = int(count_match.group(1))
    if result["template_id"] == "puzzle-process":
        known_steps = [step for step in ("清理胎体", "髹涂底漆", "阴干", "打磨", "推光") if step in approved_text]
        if "底漆" in approved_text and "髹涂底漆" not in known_steps: known_steps.insert(1 if known_steps else 0, "底漆")
        if known_steps:
            result["sequence_steps"] = list(dict.fromkeys(known_steps))
            result["target_count"] = len(result["sequence_steps"])
    return UnityBuildPlan.model_validate(result).model_dump()


def _mock_unity_plan(project: Project) -> dict[str, Any]:
    concept = project.artifacts.get("concept", {}).get("data", {})
    logic = project.artifacts.get("logic", {}).get("data", {})
    template_id = _expected_template(project)
    titles = {
        "simulation-layering": "薄髹层积", "timing-polish": "推光节律", "collection-materials": "漆艺材料采集",
        "puzzle-process": "漆艺工序排序", "target-lacquer-drops": "纹样点漆", "topdown-dodge": "漆坊避险",
    }
    instructions = {
        "simulation-layering": "点击髹涂，表面出现缺陷时先打磨，再完成下一层。",
        "timing-polish": "观察往返节拍标记，在标记进入中心区域时按空格。",
        "collection-materials": "使用方向键或 WASD 移动，触碰并收集不同材料。",
        "puzzle-process": "按正确工序顺序点击卡片，错误选择会计入失误。",
        "target-lacquer-drops": "点击高亮纹样落点，完成所有不重复目标。",
        "topdown-dodge": "使用方向键或 WASD 移动小工匠，躲避落下的漆滴并坚持到倒计时结束。",
    }
    plan = UnityBuildPlan(
        template_id=template_id,
        game_title=(str(concept.get("game_name") or "").strip()[:60] or titles[template_id]),
        objective=(str(logic.get("win") or concept.get("win_condition") or "").strip()[:240] or "完成当前漆艺挑战"),
        player_instructions=instructions[template_id],
        target_count=5 if template_id == "simulation-layering" else 3,
        time_limit_seconds=60,
        failure_limit=3,
        speed=1.0,
        sequence_steps=["清理胎体", "髹涂底漆", "阴干", "打磨"],
        asset_roles=["玩家", "主要交互物", "反馈效果", "场景背景"],
        audio_cues=[str(item).strip() for item in (logic.get("audio_cues") or ["操作成功", "操作失败", "完成目标"]) if str(item).strip()][:12],
    ).model_dump()
    return _constrain_plan_to_approved(project, plan)


def _mock_audio_design(project: Project) -> dict[str, Any]:
    logic = project.artifacts.get("logic", {}).get("data", {})
    return AudioDesignPlan(
        title="漆层呼吸",
        mood="温暖、专注、手作",
        tempo=76,
        duration=20,
        layers=[
            {"waveform": "sine", "frequency": 220, "rhythm_division": 1, "volume": 0.28},
            {"waveform": "triangle", "frequency": 330, "rhythm_division": 2, "volume": 0.18},
            {"waveform": "sine", "frequency": 440, "rhythm_division": 4, "volume": 0.10},
        ],
        event_cues=list(logic.get("audio_cues") or ["操作成功", "操作失败", "完成目标"]),
    ).model_dump()


def _mock_concept(knowledge: KnowledgeEntry) -> dict[str, Any]:
    return GameConcept(
        game_name="一层之间", selected_knowledge=knowledge.title, genre="节奏 · 工艺模拟",
        player_fantasy="以工匠的手感，让器物在层层等待中显出光泽。",
        world="清晨漆林与安静作坊之间的五次髹涂。",
        learning_objective="理解薄涂、均匀、等待与重复共同构成漆层。",
        core_mechanic="控制刷速与压力，使每层厚度落入安全区间。",
        core_loop="观察 → 髹涂 → 判断均匀度 → 荫干 → 研磨 → 下一层",
        player_actions=["移动漆刷", "调节压力", "决定何时停止", "等待与检查"],
        rules=["单层不可过厚", "覆盖达到 90%", "未干透不能研磨"],
        feedback=["表面反光", "刷痕密度", "层次音乐", "边缘积漆警示"],
        failure_conditions=["三次厚涂失败", "未干透强行进入下一步"],
        win_condition="完成五层有效薄髹并显出稳定光泽",
        level_structure="五个逐渐收窄容错区间的工序回合", estimated_duration="8–12 分钟",
        alignment=Alignment(
            represented=["薄层", "重复", "均匀", "等待"], missing=["湿度"],
            mechanic_mapping={"薄层":"厚度安全区", "重复":"五层回合", "等待":"荫干阶段"},
            score="Strong", explanation="核心操作直接表达知识动作；湿度暂未进入规则。",
        ),
    ).model_dump()


def _mock_logic() -> dict[str, Any]:
    return LogicSpecification(
        player="鼠标控制漆刷；按压时髹涂。",
        painting=["移动速度影响厚度", "厚度越界触发皱缩反馈", "覆盖率超过 90% 才可提交"],
        rounds="5 层；每层完成后进入荫干与细磨反馈。", win="完成 5 层有效薄髹。",
        fail="累计 3 次无效髹涂。", audio_cues=["每完成一层增加一层音乐", "厚涂时加入闷响"],
        acceptance=["厚度阈值可配置", "覆盖率可见", "失败可恢复", "规则与知识一致"],
    ).model_dump()


class MockLLMProvider(LLMProvider):
    name = "mock"
    async def respond(self, request: AgentRequest, project: Project, knowledge: KnowledgeEntry) -> AgentResponse:
        if request.mode == "code":
            content = "这是可拒绝的代码结构提议：把已批准逻辑映射为输入、厚度状态、覆盖率和反馈；生成脚本只能进入受控目录，必须真实编译后才能报告成功。"
            model = "mock-code-proposal-v2"
        else:
            content = f"我保留你的原始想法“{project.original_player_idea or project.player_idea}”。结合“{knowledge.title}”，建议先把“{knowledge.key_actions[0]}”变成玩家操作；你可以接受、拒绝、修改或继续讨论。"
            model = "mock-conversation-v2"
        return AgentResponse(provider="mock", model=model, content=content, demo_mode=True)

    async def generate_structured(self, kind: str, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        if kind == "concept":
            data = _mock_concept(knowledge)
        elif kind == "logic":
            data = _mock_logic()
        elif kind == "audio":
            data = _mock_audio_design(project)
        else:
            raise ProviderFailure("unsupported_structured_kind", kind)
        return StructuredGeneration(provider="mock", model="mock-structured-v2", data=data, demo_mode=True)

    async def generate_unity_code(self, project: Project, knowledge: KnowledgeEntry) -> GeneratedCode:
        return GeneratedCode(provider="mock", model="mock-unity-code-v1", source=validate_unity_code(RUNTIME_SCRIPT_TEMPLATE), demo_mode=True)

    async def generate_unity_plan(self, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        return StructuredGeneration(provider="mock", model="mock-unity-plan-v1", data=_mock_unity_plan(project), demo_mode=True)


class DeepSeekLLMProvider(LLMProvider):
    name = "deepseek"
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.chat_model = settings.deepseek_chat_model
        self.code_model = settings.deepseek_code_model

    def _price(self, model: str, input_tokens: int, output_tokens: int) -> float:
        if model == self.code_model:
            incoming, outgoing = settings.deepseek_pro_input_cny_per_million, settings.deepseek_pro_output_cny_per_million
        else:
            incoming, outgoing = settings.deepseek_flash_input_cny_per_million, settings.deepseek_flash_output_cny_per_million
        return round((input_tokens * incoming + output_tokens * outgoing) / 1_000_000, 6)

    def _context(self, project: Project, knowledge: KnowledgeEntry, *, kind: str | None = None) -> str:
        rejected = [m.content for m in project.conversation_history if m.role == "user" and ("不好" in m.content or "拒绝" in m.content)][-4:]
        dependencies = {
            "concept": (),
            "visual": ("concept",),
            "3d": ("concept", "visual"),
            "audio": ("concept", "visual", "3d"),
            "logic": ("concept", "visual", "3d", "music"),
            "unity": ("concept", "visual", "3d", "music", "logic"),
        }
        keys = dependencies.get(kind or "", tuple(project.approvals))
        approved = {
            key: project.artifacts[key]["data"]
            for key in keys
            if key in project.approvals and key in project.artifacts
        }
        return json.dumps({
            "stage": project.current_stage.value,
            "original_player_idea": project.original_player_idea or project.player_idea,
            "knowledge": {
                "title": knowledge.title, "summary": knowledge.summary,
                "core_facts": knowledge.core_facts,
                "cause_effect_relations": knowledge.cause_effect_relations,
                "key_actions": knowledge.key_actions,
                "common_misconceptions": knowledge.common_misconceptions or knowledge.common_errors,
                "learning_objectives": knowledge.learning_objectives,
                "references": knowledge.references,
                "game_affordances_for_agent_only": knowledge.game_affordances or knowledge.affordances,
                "source": knowledge.source,
            },
            "approved_artifacts": approved,
            "player_revision_directions": {
                k.removeprefix("player_").removesuffix("_direction"): v.get("data", {}).get("prompt", "")
                for k, v in project.artifacts.items()
                if k.startswith("player_") and k.endswith("_direction")
            },
            "recent_rejections": rejected,
        }, ensure_ascii=False)

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(settings.deepseek_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.deepseek_timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                        json=payload,
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < settings.deepseek_max_retries:
                        delay = min(float(response.headers.get("Retry-After", 2 ** attempt)), 8.0)
                        await asyncio.sleep(delay)
                        continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last = exc
                if attempt < settings.deepseek_max_retries:
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                raise ProviderFailure("network_timeout", str(exc), True) from exc
            except httpx.HTTPStatusError as exc:
                raise ProviderFailure(f"http_{exc.response.status_code}", str(exc), exc.response.status_code in {429, 500, 502, 503, 504}) from exc
        raise ProviderFailure("provider_failed", str(last), True)

    @staticmethod
    def _usage(data: dict[str, Any]) -> tuple[int, int]:
        usage = data.get("usage") or {}
        return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))

    async def respond(self, request: AgentRequest, project: Project, knowledge: KnowledgeEntry) -> AgentResponse:
        model = self.code_model if request.mode == "code" else self.chat_model
        history = [{"role": m.role, "content": m.content} for m in project.conversation_history[-20:-1] if m.role in {"user", "assistant"}]
        system = "你是《漆问》的游戏共创伙伴。保留玩家原意，把策展知识转译为可玩机制；重要建议必须可拒绝、可修改，不代替玩家审批，不声称执行工具。只用简洁中文。玩家尚未提出独立想法前，不得主动展示 game_affordances_for_agent_only；只用于内部核验、追问，或玩家明确询问时说明。"
        if request.mode == "code":
            system += "你只能给出代码提议；不得输出密钥、shell 命令或任意路径，不得声称代码已写入或编译成功。"
        user_text = request.message.strip() or "请分析我上传的附件。"
        document_parts = [f"\n\n附件《{item.name}》内容：\n{item.text[:12000]}" for item in request.attachments if item.type == "DOCUMENT" and item.text]
        user_content: str | list[dict[str, Any]] = user_text + "".join(document_parts)
        images = [item for item in request.attachments if item.type == "IMAGE" and item.data_url]
        if images:
            user_content = [{"type":"text","text":str(user_content)}, *[{"type":"image_url","image_url":{"url":item.data_url}} for item in images]]
        payload = {"model": model, "messages": [{"role":"system","content":system}, {"role":"system","content":self._context(project, knowledge)}, *history, {"role":"user","content":user_content}], "thinking":{"type":"enabled" if request.mode == "code" else "disabled"}, "stream":False, "max_tokens":1400 if request.mode == "code" else 700, "user_id":f"project-{project.id}"}
        data = await self._post(payload)
        try:
            content = data["choices"][0]["message"]["content"]
            if not content:
                raise KeyError("empty_content")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderFailure("invalid_response", "模型返回缺少可展示内容") from exc
        incoming, outgoing = self._usage(data)
        return AgentResponse(provider="deepseek", model=model, content=content, demo_mode=False, input_tokens=incoming, output_tokens=outgoing, cost_cny=self._price(model, incoming, outgoing))

    async def generate_structured(self, kind: str, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        schema: type[BaseModel] = GameConcept if kind == "concept" else AudioDesignPlan if kind == "audio" else LogicSpecification
        model = self.code_model
        prompt = f"根据上下文生成 {kind}。如果是 audio，必须设计成有持续和弦、可辨识旋律、低音线和轻量节奏的循环游戏配乐，不能只有敲击声；layers 中每项使用 role(pad/melody/bass/percussion)、waveform(sine/triangle/square)、frequency(80-1200)、rhythm_division(1-8)、volume(0.02-0.4)。输出 json，必须严格符合此 JSON Schema：{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        messages = [{"role":"system","content":"你是《漆问》游戏设计 Agent。只能基于给定策展知识与玩家原始想法，输出合法 json；不自动批准。"}, {"role":"system","content":self._context(project, knowledge, kind=kind)}, {"role":"user","content":prompt}]
        total_in = total_out = 0
        for repair in range(2):
            data = await self._post({"model":model, "messages":messages, "thinking":{"type":"enabled"}, "reasoning_effort":"high", "response_format":{"type":"json_object"}, "stream":False, "max_tokens":2600, "user_id":f"project-{project.id}"})
            incoming, outgoing = self._usage(data); total_in += incoming; total_out += outgoing
            raw = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            try:
                parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
                valid = schema.model_validate(parsed).model_dump()
                return StructuredGeneration(provider="deepseek", model=model, data=valid, demo_mode=False, input_tokens=total_in, output_tokens=total_out, cost_cny=self._price(model, total_in, total_out))
            except (json.JSONDecodeError, ValidationError):
                if repair == 0:
                    messages.extend([{"role":"assistant","content":raw[:12000]}, {"role":"user","content":"上一个 JSON 不符合 schema。只修复格式和缺失字段，仍输出 json。"}])
                    continue
                raise ProviderFailure("schema_validation_failed", "结构化结果两次未通过 schema 校验")
        raise ProviderFailure("schema_validation_failed", "结构化结果无效")

    async def generate_unity_code(self, project: Project, knowledge: KnowledgeEntry) -> GeneratedCode:
        approved_logic = project.artifacts.get("logic", {}).get("data", {})
        build_plan = approved_logic.get("unity_build_plan", {})
        messages = [
            {"role": "system", "content": "你是《漆问》的 Unity C# 代码 Agent。只输出一个可编译的 C# 源文件，不使用 Markdown。脚本只能继承 MonoBehaviour，只能辅助当前 GameObject 的视觉与 AudioSource 反馈；核心玩法由已批准的受测模板执行。禁止文件、网络、进程、编辑器、反射和原生调用。命名空间必须是 QIWEN.Runtime，类名必须是 LacquerBowlExperience。"},
            {"role": "system", "content": self._context(project, knowledge, kind="unity")},
            {"role": "user", "content": f"根据这份已批准构建计划生成与其匹配的视觉/声音反馈辅助脚本，不得改成固定点击漆碗玩法：{json.dumps(build_plan, ensure_ascii=False)}。只输出源码。"},
        ]
        total_in = total_out = 0
        last_error: ProviderFailure | None = None
        for attempt in range(2):
            data = await self._post({"model": self.code_model, "messages": messages, "thinking": {"type": "enabled"}, "reasoning_effort": "high", "stream": False, "max_tokens": 1600, "user_id": f"project-{project.id}"})
            incoming, outgoing = self._usage(data)
            total_in += incoming; total_out += outgoing
            raw = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            try:
                source = validate_unity_code(raw)
                return GeneratedCode(provider="deepseek", model=self.code_model, source=source, demo_mode=False, input_tokens=total_in, output_tokens=total_out, cost_cny=self._price(self.code_model, total_in, total_out))
            except ProviderFailure as error:
                last_error = error
                messages.extend([{"role": "assistant", "content": raw[:12000]}, {"role": "user", "content": "上一个源文件未通过安全校验。删除禁用能力并严格遵守类名、命名空间和 MonoBehaviour 约束，只输出完整源码。"}])
        raise last_error or ProviderFailure("unsafe_generated_code", "代码生成失败")

    async def generate_unity_plan(self, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        explicit = {"original_player_idea":project.original_player_idea,"approved_concept":project.artifacts.get("concept",{}).get("data",{}),"approved_logic":project.artifacts.get("logic",{}).get("data",{}),"required_template":_expected_template(project)}
        prompt = (
            "把已批准游戏概念与游戏逻辑映射为一个 Unity 构建计划。必须从六个 template_id 中选择最匹配的一种；"
            "禁止把所有项目变成同一种游戏。目标、输入、数值、素材角色和声音事件必须来自当前项目。"
            "玩家原始想法和已批准内容优先级最高，知识条目只能补充文化约束，不能替换玩法。"
            f"明确批准内容：{json.dumps(explicit, ensure_ascii=False)}。"
            f"只输出 JSON，严格符合：{json.dumps(UnityBuildPlan.model_json_schema(), ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": "你是《漆问》的 Unity 构建规划 Agent。只提出受约束计划，不执行 Unity，也不能跳过玩家审批。"},
            {"role": "system", "content": self._context(project, knowledge, kind="unity")},
            {"role": "user", "content": prompt},
        ]
        total_in = total_out = 0
        validation_messages: list[str] = []
        for repair in range(2):
            data = await self._post({"model": self.code_model, "messages": messages, "response_format": {"type": "json_object"}, "stream": False, "max_tokens": 2200, "user_id": f"project-{project.id}"})
            incoming, outgoing = self._usage(data); total_in += incoming; total_out += outgoing
            raw = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            try:
                parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
                valid = _constrain_plan_to_approved(project, UnityBuildPlan.model_validate(parsed).model_dump())
                return StructuredGeneration(provider="deepseek", model=self.code_model, data=valid, demo_mode=False, input_tokens=total_in, output_tokens=total_out, cost_cny=self._price(self.code_model, total_in, total_out))
            except json.JSONDecodeError as exc:
                validation_message = f"JSON 格式错误：第 {exc.lineno} 行第 {exc.colno} 列"
                validation_messages.append(validation_message)
                logger.warning("Unity build plan JSON validation failed for project %s: %s", project.id, validation_message)
                if repair == 0:
                    messages.extend([{"role": "assistant", "content": raw[:12000]}, {"role": "user", "content": f"计划未通过校验：{validation_message}。只修复 JSON 和字段，不改变已批准玩法。"}])
                    continue
            except ValidationError as exc:
                fields = [".".join(str(part) for part in item["loc"]) for item in exc.errors(include_url=False)]
                validation_message = "字段不合法：" + "、".join(dict.fromkeys(fields))
                validation_messages.append(validation_message)
                logger.warning("Unity build plan schema validation failed for project %s: %s", project.id, validation_message)
                if repair == 0:
                    messages.extend([{"role": "assistant", "content": raw[:12000]}, {"role": "user", "content": f"计划未通过校验：{validation_message}。只修复 JSON 和字段，不改变已批准玩法。"}])
                    continue

        # 构建计划是受约束的中间表示。模型连续返回坏 JSON 时，根据已批准内容
        # 生成确定性的安全计划，避免整个流程因供应商格式波动卡死。
        fallback = _mock_unity_plan(project)
        logger.warning(
            "Unity build plan used deterministic recovery for project %s after: %s",
            project.id,
            "; ".join(validation_messages),
        )
        return StructuredGeneration(
            provider=self.name,
            model=f"{self.code_model}+受约束恢复",
            data=fallback,
            demo_mode=False,
            input_tokens=total_in,
            output_tokens=total_out,
            cost_cny=self._price(self.code_model, total_in, total_out),
        )


def get_llm_provider(task: str | None = None) -> LLMProvider:
    if task == "music" and (os.getenv("MICU_MUSIC_LLM_API_KEY") or settings.micu_music_llm_api_key):
        return MicuLLMProvider(
            api_key=os.getenv("MICU_MUSIC_LLM_API_KEY") or settings.micu_music_llm_api_key,
            chat_model=settings.micu_music_model,
            code_model=settings.micu_music_model,
        )
    if os.getenv("MICU_LLM_API_KEY") or settings.micu_llm_api_key:
        return MicuLLMProvider()
    return DeepSeekLLMProvider() if os.getenv("DEEPSEEK_API_KEY") else MockLLMProvider()


class MicuLLMProvider(DeepSeekLLMProvider):
    """米醋 OpenAI Chat Completions 兼容 Provider；密钥只在后端读取。"""

    name = "micu"

    def __init__(self, api_key: str | None = None, chat_model: str | None = None, code_model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("MICU_LLM_API_KEY") or settings.micu_llm_api_key
        self.base_url = settings.micu_base_url.rstrip("/")
        self.chat_model = chat_model or settings.micu_chat_model
        self.code_model = code_model or settings.micu_code_model

    def _price(self, model: str, input_tokens: int, output_tokens: int) -> float:
        if model == self.code_model:
            incoming, outgoing = settings.micu_code_input_cny_per_million, settings.micu_code_output_cny_per_million
        else:
            incoming, outgoing = settings.micu_chat_input_cny_per_million, settings.micu_chat_output_cny_per_million
        token_estimate = (input_tokens * incoming + output_tokens * outgoing) / 1_000_000
        return round(token_estimate if token_estimate > 0 else settings.micu_estimated_cny_per_call, 6)

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = {key: value for key, value in payload.items() if key not in {"thinking", "reasoning_effort", "user_id"}}
        last: Exception | None = None
        for attempt in range(settings.micu_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.micu_timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "codex_cli_rs/0.77.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                        },
                        json=request,
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < settings.micu_max_retries:
                        await asyncio.sleep(min(2 ** attempt, 8))
                        continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                last = exc
                if attempt < settings.micu_max_retries:
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                raise ProviderFailure("network_timeout", "当前生成服务连接中断，已自动重试仍未完成。请稍后重试。", True) from exc
            except httpx.HTTPStatusError as exc:
                message = _redact_provider_message(exc.response.text[:500] or str(exc))
                if "rate_limited" in message or "Too many requests" in message:
                    raise ProviderFailure("service_busy", "当前生成服务繁忙，请稍后重试。", True) from exc
                if "no access to model" in message:
                    raise ProviderFailure("model_unavailable", "当前密钥没有所选生成能力，请检查模型权限。", False) from exc
                raise ProviderFailure(f"http_{exc.response.status_code}", message, exc.response.status_code in {429, 500, 502, 503, 504}) from exc
        raise ProviderFailure("provider_failed", str(last), True)

    async def respond(self, request: AgentRequest, project: Project, knowledge: KnowledgeEntry) -> AgentResponse:
        if any(item.type == "IMAGE" for item in request.attachments):
            self.chat_model = os.getenv("MICU_VISION_MODEL", "gpt-5.6-luna")
        response = await super().respond(request, project, knowledge)
        return response.model_copy(update={"provider": self.name})

    async def generate_structured(self, kind: str, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        result = await super().generate_structured(kind, project, knowledge)
        return result.model_copy(update={"provider": self.name})

    async def generate_unity_code(self, project: Project, knowledge: KnowledgeEntry) -> GeneratedCode:
        result = await super().generate_unity_code(project, knowledge)
        return result.model_copy(update={"provider": self.name})

    async def generate_unity_plan(self, project: Project, knowledge: KnowledgeEntry) -> StructuredGeneration:
        result = await super().generate_unity_plan(project, knowledge)
        return result.model_copy(update={"provider": self.name})


def is_real_llm_provider(provider: LLMProvider) -> bool:
    return provider.name != "mock"
