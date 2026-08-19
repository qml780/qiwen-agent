from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
from datetime import UTC, datetime
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete as sqlalchemy_delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .bridge_client import (
    LocalBridgeError,
    bridge_health,
    bridge_job,
    retry_bridge_job,
    start_unity_build,
    stream_bridge_events,
    takeover_bridge_job,
    apply_co_creation,
    start_playtest_in_unity,
)
from .co_creation import bridge_payload, create_change_preview, list_project_changes, serialize_change, undo_payload
from .playtests import list_playtests, serialize_playtest, update_evidence
from .research import create_research_export, research_snapshot
from .asset_providers import AssetGenerationRequest, AssetProviderError, extract_provider_urls, get_asset_provider, run_asset_provider, task_to_artifact
from .object_storage import ObjectValidationError, ingest_urls
from .database import SessionFactory, get_session, verify_database
from .domain import (
    APPROVAL_TRANSITIONS,
    GENERATION_TRANSITIONS,
    AgentRequest,
    AgentResponse,
    AgentAttachment,
    Approval,
    Asset,
    ConversationMessage,
    CreateProjectRequest,
    IdeaRequest,
    UploadRequest,
    Project,
    Stage,
    SuggestionResponseRequest,
    UnityChangeDecisionRequest,
    UnityChangePreviewRequest,
    PlaytestFeedbackRequest,
    PlaytestRevisionRequest,
    PlaytestStartRequest,
    ProductionModeRequest,
    GameAssetPlanRequest,
    GameAssetGenerateRequest,
)
from .models import ApprovalRow, AssetRow, PlaytestSessionRow, ProjectRow, UnityChangeRow
from .providers import MicuLLMProvider, ProviderFailure, UnityBuildPlan, get_llm_provider, is_real_llm_provider
from .repository import (
    attach_project_assets,
    get_knowledge,
    list_assets,
    list_knowledge,
    list_projects,
    load_project,
    monthly_api_cost,
    monthly_estimated_cost,
    persistence_counts,
    create_suggestion,
    record_llm_call,
    record_generated_assets,
    record_provider_job,
    respond_to_suggestion,
    save_project,
    seed_reference_data,
    use_asset_in_project,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await verify_database()
    async with SessionFactory() as session:
        await seed_reference_data(session)
    yield


app = FastAPI(title="QIWEN Product API", version="0.4.0", lifespan=lifespan)
Path(settings.object_storage_root).mkdir(parents=True, exist_ok=True)
app.mount("/objects", StaticFiles(directory=settings.object_storage_root), name="objects")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)

UPLOAD_MIMES = {
    "image/png": ("IMAGE", ".png", 20 * 1024 * 1024),
    "image/jpeg": ("IMAGE", ".jpg", 20 * 1024 * 1024),
    "image/webp": ("IMAGE", ".webp", 20 * 1024 * 1024),
    "application/json": ("DOCUMENT", ".json", 2 * 1024 * 1024),
    "text/plain": ("DOCUMENT", ".txt", 2 * 1024 * 1024),
    "text/markdown": ("DOCUMENT", ".md", 2 * 1024 * 1024),
    "text/csv": ("DOCUMENT", ".csv", 2 * 1024 * 1024),
}


def validate_upload(mime: str, data: bytes) -> tuple[str, str, int]:
    spec = UPLOAD_MIMES.get(mime.lower())
    if not spec:
        raise HTTPException(status_code=415, detail={"code":"unsupported_upload","message":"仅支持 PNG、JPG、WebP、JSON、Markdown、TXT 和 CSV。"})
    kind, _, limit = spec
    if not data or len(data) > limit:
        raise HTTPException(status_code=413, detail={"code":"upload_too_large","message":"图片不能超过 20MB，文档不能超过 2MB。"})
    if kind == "IMAGE":
        valid = data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")) or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        if not valid:
            raise HTTPException(status_code=422, detail={"code":"invalid_image","message":"图片内容与文件类型不一致。"})
    return spec


def asset_domain(row: AssetRow) -> Asset:
    return Asset(id=row.id, project_id=row.project_id, type=row.type, name=row.name, url=row.url, scope=row.scope, sha256=row.sha256, metadata=row.metadata_json, created_at=row.created_at)

def touch(project: Project, activity: str) -> None:
    project.updated_at = datetime.now(UTC)
    project.activity_log.append(activity)


async def get_project_or_404(session: AsyncSession, project_id: str, *, for_update: bool = False) -> Project:
    project = await load_project(session, project_id, for_update=for_update)
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")
    return project


def next_version(project: Project, artifact: str) -> int:
    version = project.versions.get(artifact, 0) + 1
    project.versions[artifact] = version
    project.approvals.pop(artifact, None)
    return version


def local_asset_path(url: str) -> str:
    if url.startswith("/demo/"):
        path = Path(settings.web_public_root) / url.removeprefix("/")
    elif url.startswith("/objects/") or url.startswith("http://127.0.0.1:8000/objects/") or url.startswith("http://localhost:8000/objects/"):
        path = Path(settings.object_storage_root) / Path(url).name
    else:
        raise HTTPException(status_code=409, detail="资产尚未保存到本地，不能发送给 Unity")
    resolved = path.resolve()
    if resolved.drive.upper() not in {"D:", "E:"} or not resolved.is_file():
        raise HTTPException(status_code=409, detail="找不到已批准的本地资产")
    return str(resolved)


def approved_unity_inputs(project: Project) -> tuple[list[str], str, str]:
    model_artifact = project.artifacts.get("3d", {})
    music_artifact = project.artifacts.get("music", {})
    model_data = model_artifact.get("data", {}) if isinstance(model_artifact, dict) else {}
    music_data = music_artifact.get("data", {}) if isinstance(music_artifact, dict) else {}
    two_d = model_data.get("mode") == "2d"
    if two_d or model_data.get("mode") == "3d" and model_data.get("variants"):
        model_urls = [item.get("url") for item in model_data.get("variants", []) if isinstance(item.get("url"), str)]
    else:
        model_urls = [model_data.get("file")]
    selected = music_data.get("selected")
    tracks = music_data.get("tracks", [])
    music_url = next((item.get("url") for item in tracks if item.get("id") == selected), None)
    if not model_urls or not all(isinstance(item, str) for item in model_urls) or not isinstance(music_url, str):
        raise HTTPException(status_code=409, detail="缺少已批准的二维素材或音乐")
    return [local_asset_path(item) for item in model_urls], local_asset_path(music_url), "2d" if two_d else "3d"


def default_game_asset_plan(project: Project | None = None, mode: str = "2d") -> dict[str, Any]:
    """根据已批准概念建立可编辑的逐项素材清单，不把所有游戏套成同一组素材。"""
    style = "彩色卡通二维游戏美术，清晰深色描边，青绿、朱红、鎏金与深漆色统一搭配，漆面柔和高光，无文字。"
    concept = (project.artifacts.get("concept", {}).get("data", {}) if project else {}) or {}
    concept_text = json.dumps(concept, ensure_ascii=False)
    if any(token in concept_text for token in ("躲避", "闪避", "弹幕", "漆滴", "液滴", "危险物", "四方向移动", "方向键移动", "不能攻击", "坚持倒计时")):
        specs = [
            ("craftsperson", "小工匠", "角色", "轻微俯视的完整小工匠角色，站立待移动姿势，透明背景"),
            ("lacquer-drop", "常规漆艺液滴", "移动物件", "单个圆润漆艺液滴，湿润反光，透明背景"),
            ("fast-lacquer-drop", "高速漆艺液滴", "移动物件", "单个高速飞行漆艺液滴，轮廓清楚，透明背景"),
            ("lacquer-splash", "漆液展开效果", "特效", "单个漆液接触展开特效，透明背景"),
            ("warning-ring", "机器启动提示光圈", "特效", "鎏金与朱红同心提示光圈，中心透明"),
            ("machine-bg", "漆艺机械作坊", "场景", "横向二维游戏背景，深色漆艺机械作坊，完整场景，无角色"),
        ]
    elif any(token in concept_text for token in ("排序", "排列工序", "工序卡", "依次选择卡片")):
        specs = [
            ("process-card", "工序卡片组", "交互物", "一组可分别点击的漆艺工序卡片，图标清晰，统一尺寸，透明背景"),
            ("selection-marker", "选择标记", "界面反馈", "用于标记当前选择的鎏金与朱红色边框光效，中心透明"),
            ("correct-effect", "正确反馈", "特效", "青绿色与鎏金色的简洁正确反馈特效，透明背景"),
            ("error-effect", "错误反馈", "特效", "朱红色的简洁错误反馈特效，透明背景"),
            ("workshop-bg", "漆艺工序作坊", "场景", "横向二维游戏背景，传统漆艺作坊与工序台，完整场景，无角色"),
        ]
    elif any(token in concept_text for token in ("收集", "材料", "样本")):
        specs = [
            ("collector", "采集者角色", "角色", "轻微俯视的完整采集者角色，待移动姿势，透明背景"),
            ("collectible", "可收集材料", "交互物", "单个漆艺原料或工具收集物，轮廓清楚，透明背景"),
            ("hazard", "干扰物", "障碍", "单个容易与材料区分的游戏障碍物，透明背景"),
            ("collect-effect", "收集反馈", "特效", "青绿与鎏金色的收集成功特效，透明背景"),
            ("collection-bg", "材料采集场景", "场景", "横向二维游戏背景，漆林与材料整理区域，完整场景，无角色"),
        ]
    elif any(token in concept_text for token in ("推光", "节拍", "节奏命中")):
        specs = [
            ("polishing-tool", "推光工具", "工具", "单个漆艺推光工具，侧视游戏图标，透明背景"),
            ("lacquer-surface", "待推光漆面", "交互物", "单块待推光漆面，能清楚显示明暗变化，透明背景"),
            ("timing-marker", "节奏指针", "界面反馈", "鎏金与青绿色节奏指针和命中区域，中心透明"),
            ("polish-effect", "推光完成效果", "特效", "漆面完成时的柔和鎏金高光特效，透明背景"),
            ("polishing-bg", "推光工作台", "场景", "横向二维游戏背景，漆艺推光工作台，完整场景，无角色"),
        ]
    elif any(token in concept_text for token in ("纹样", "点漆", "落点")):
        specs = [
            ("craftsperson", "小工匠", "角色", "轻微俯视的完整小工匠角色，站立待移动姿势，透明背景"),
            ("lacquer-drop", "常规漆艺液滴", "移动物件", "单个圆润漆艺液滴，湿润反光，透明背景"),
            ("fast-lacquer-drop", "高速漆艺液滴", "移动物件", "单个横向拉长的高速漆艺液滴，短流线尾部，透明背景"),
            ("lacquer-splash", "漆液展开效果", "特效", "单个漆液接触展开特效，透明背景"),
            ("warning-ring", "机器启动提示光圈", "特效", "鎏金与朱红同心提示光圈，中心透明"),
            ("machine-bg", "漆艺机械作坊", "场景", "横向二维游戏背景，深色漆艺机械作坊，完整场景，无角色"),
        ]
    else:
        specs = [
            ("lacquer-brush", "髹涂漆刷", "工具", "单个可操控漆刷，轻微俯视，刷毛带少量深漆色，透明背景"),
            ("workpiece", "待髹器物", "交互物", "单个待髹涂器物或漆面试板，轮廓清楚，透明背景"),
            ("lacquer-layer", "漆层覆盖效果", "特效", "用于叠加在器物上的半透明漆层覆盖效果，边缘清楚，透明背景"),
            ("thickness-warning", "厚度警示", "界面反馈", "朱红与鎏金色的漆层过厚警示标记，中心透明"),
            ("finished-sheen", "完成光泽", "特效", "髹涂完成后的柔和高光与鎏金反射特效，透明背景"),
            ("layering-workshop", "髹涂工作台", "场景", "横向二维游戏背景，安静漆艺作坊与髹涂工作台，完整场景，无角色"),
        ]
    if mode == "3d":
        style = "彩色卡通三维游戏美术，风格化低多边形，统一比例，青绿、朱红、鎏金与深漆色搭配，漆面 PBR 柔和高光，适合实时游戏，无文字。"
    return {"mode": mode, "style": style, "items": [
        {"id": item_id, "name": name, "category": category, "prompt": (
            f"3D 游戏独立资产，{prompt.replace('透明背景', '完整单体造型').replace('横向二维游戏背景', '模块化三维游戏场景')}。输出 GLB，低面数，完整 PBR 材质。"
            if mode == "3d" else f"2D 游戏素材，{prompt}。"
        ), "asset_id": None, "status": "pending"}
        for item_id, name, category, prompt in specs
    ]}


def mock_artifact(kind: str, project: Project) -> Any:
    if kind == "concept":
        return {
            "game_name": "一层之间",
            "selected_knowledge": "薄髹与层积",
            "genre": "节奏 · 工艺模拟",
            "player_fantasy": "以工匠的手感，让器物在层层等待中显出光泽。",
            "world": "清晨漆林与安静作坊之间的五次髹涂。",
            "learning_objective": "理解薄涂、均匀、等待与重复共同构成漆层。",
            "core_mechanic": "控制刷速与压力，使每层厚度落入安全区间。",
            "core_loop": "观察 → 髹涂 → 判断均匀度 → 荫干 → 研磨 → 下一层",
            "player_actions": ["移动漆刷", "调节压力", "决定何时停止", "等待与检查"],
            "rules": ["单层不可过厚", "覆盖达到 90%", "未干透不能研磨"],
            "feedback": ["表面反光", "刷痕密度", "层次音乐", "边缘积漆警示"],
            "failure_conditions": ["三次厚涂失败", "未干透强行进入下一步"],
            "win_condition": "完成五层有效薄髹并显出稳定光泽",
            "level_structure": "五个逐渐收窄容错区间的工序回合",
            "estimated_duration": "8–12 分钟",
            "alignment": {"represented": ["薄层", "重复", "均匀", "等待"], "missing": ["湿度"], "score": "HIGH"},
        }
    if kind == "visual":
        return {
            "prompt": "克制的中国漆艺作坊，黑漆、木色与一线大漆红，柔和晨光，编辑式构图",
            "variants": [
                {"id": "image-a", "title": "漆林晨雾", "url": "/demo/lacquer-forest.png"},
                {"id": "image-b", "title": "匠人作坊", "url": "/demo/lacquer-workshop.png"},
                {"id": "image-c", "title": "未完成漆碗", "url": "/demo/lacquer-bowl.png"},
                {"id": "image-d", "title": "木屋与工序", "url": "/demo/lacquer-house.png"},
            ],
            "selected": "image-b",
            "provider": "mock",
        }
    if kind == "3d":
        return {
            "name": "漆碗模型",
            "file": "/demo/lacquer-bowl-v1.glb",
            "format": "GLB",
            "polygon_count": 960,
            "texture": "程序化黑漆材质",
            "version": 1,
            "provider": "mock",
        }
    if kind == "music":
        return {
            "prompt": "克制、缓慢层积、木质打击与呼吸感，纯音乐循环",
            "mood": "专注 / 清晨 / 手作",
            "tempo": 76,
            "duration": 58,
            "loop": True,
            "tracks": [
                {"id": "bgm-v1", "title": "作坊静层", "url": "/demo/main-theme.wav"},
                {"id": "bgm-v2", "title": "采漆晨行", "url": "/demo/harvest-theme.wav"},
            ],
            "selected": "bgm-v1",
            "provider": "mock",
        }
    if kind == "logic":
        return {
            "player": "鼠标控制漆刷；按压时髹涂。",
            "painting": ["移动速度影响厚度", "厚度越界触发皱缩反馈", "覆盖率超过 90% 才可提交"],
            "rounds": "5 层；每层完成后进入荫干与细磨反馈。",
            "win": "完成 5 层有效薄髹。",
            "fail": "累计 3 次无效髹涂。",
            "audio_cues": ["每完成一层增加一层音乐", "厚涂时降低高频并加入闷响"],
            "acceptance": ["厚度阈值可配置", "覆盖率可见", "失败可恢复", "规则与薄髹知识一致"],
        }
    raise HTTPException(status_code=400, detail="unknown_artifact_kind")


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    provider = get_llm_provider()
    database_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
    return {
        "status": "ok",
        "database": database_status,
        "llm_mode": provider.name,
        "monthly_budget_cny": settings.api_monthly_budget_cny,
        "asset_modes": {kind:get_asset_provider(kind).name for kind in ("image","3d","music")},
    }


@app.get("/health/dependencies")
async def dependency_health(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Read-only dependency snapshot; never starts generation or spends API quota."""
    dependencies: dict[str, dict[str, Any]] = {}
    try:
        await session.execute(text("SELECT 1"))
        dependencies["数据库"] = {"status": "connected"}
    except Exception as exc:
        dependencies["数据库"] = {"status": "unavailable", "detail": type(exc).__name__}

    storage_root = Path(settings.object_storage_root)
    dependencies["本地素材存储"] = {
        "status": "available" if storage_root.is_dir() else "unavailable",
        "path": str(storage_root),
    }

    try:
        dependencies["本地桥"] = {"status": "connected", "detail": await bridge_health()}
    except Exception as exc:
        dependencies["本地桥"] = {"status": "unavailable", "detail": type(exc).__name__}

    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            music_response = await client.get(os.getenv("ACESTEP_BASE_URL", "http://127.0.0.1:8001").rstrip("/") + "/health")
            music_response.raise_for_status()
        dependencies["本地音乐生成"] = {"status": "connected"}
    except Exception as exc:
        dependencies["本地音乐生成"] = {"status": "unavailable", "detail": type(exc).__name__}

    dependencies["图像生成"] = {
        "status": "configured" if (os.getenv("MICU_IMAGE_API_KEY") or settings.micu_image_api_key) else "not_configured",
        "note": "仅报告配置状态；健康检查不会发起付费生成",
    }
    dependencies["三维生成"] = {
        "status": "configured" if (os.getenv("HUNYUAN3D_API_KEY") or settings.hunyuan3d_api_key) else "not_configured",
        "note": "仅报告配置状态；健康检查不会发起付费生成",
    }
    overall = "ok" if all(item["status"] in {"connected", "available", "configured"} for item in dependencies.values()) else "degraded"
    return {"status": overall, "dependencies": dependencies}


@app.get("/budget")
async def budget_status(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    spent=round(await monthly_api_cost(session),6)
    estimated=round(await monthly_estimated_cost(session),6)
    return {"budget_cny":settings.api_monthly_budget_cny,"spent_cny":spent,"remaining_cny":max(round(settings.api_monthly_budget_cny-spent,6),0),"estimated_ledger_cny":estimated,"cost_basis":"供应商余额页确认值","scope":"global_monthly","project_limit":None}


@app.get("/unity/health")
async def unity_health() -> dict[str, Any]:
    try:
        return await bridge_health()
    except LocalBridgeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/unity/jobs/{job_id}")
async def unity_job(job_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    try:
        job = await bridge_job(job_id)
    except LocalBridgeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    project_id = job.get("projectId")
    if isinstance(project_id, str) and job.get("status") in {"成功", "失败", "已取消", "已接管"}:
        async with session.begin():
            project = await get_project_or_404(session, project_id, for_update=True)
            if project.current_stage == Stage.UNITY_BUILDING:
                project.current_stage = Stage.UNITY_REVIEW if job.get("status") == "成功" else Stage.READY_TO_BUILD
                touch(project, "Unity 构建已完成并等待试玩" if job.get("status") == "成功" else f"Unity 构建未完成：{job.get('status')}")
                await save_project(session, project)
    return job


@app.get("/unity/jobs/{job_id}/events")
async def unity_job_events(job_id: str, after: int = 0) -> StreamingResponse:
    return StreamingResponse(
        stream_bridge_events(job_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/unity/jobs/{job_id}/retry", status_code=202)
async def retry_unity_job(job_id: str) -> dict[str, Any]:
    try:
        return await retry_bridge_job(job_id)
    except LocalBridgeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/unity/jobs/{job_id}/takeover")
async def takeover_unity_job(job_id: str) -> dict[str, Any]:
    try:
        return await takeover_bridge_job(job_id)
    except LocalBridgeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/projects/{project_id}/unity/build", status_code=202)
async def build_in_unity(project_id: str, budget_choice: str | None = Header(default=None, alias="X-Qiwen-Budget-Choice"), session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    provider = get_llm_provider()
    async with session.begin():
        snapshot = await get_project_or_404(session, project_id, for_update=True)
        if snapshot.current_stage not in {Stage.READY_TO_BUILD, Stage.UNITY_REVIEW}:
            raise HTTPException(status_code=409, detail="必须先批准知识、概念、视觉、三维、音乐与游戏逻辑")
        knowledge = await get_knowledge(session, snapshot.selected_knowledge_id)
        if not knowledge:
            raise HTTPException(status_code=409, detail="项目引用的知识条目不存在")
        visual_asset_paths, audio_path, game_mode = approved_unity_inputs(snapshot)
        logic_data = snapshot.artifacts.get("logic", {}).get("data", {})
        try:
            build_plan = UnityBuildPlan.model_validate(logic_data.get("unity_build_plan"))
        except Exception as exc:
            raise HTTPException(status_code=409, detail="已批准游戏逻辑缺少有效的 Unity 构建计划，请重新生成并批准游戏逻辑") from exc
        expected_revision = snapshot.revision
        spent = await monthly_api_cost(session)
    if is_real_llm_provider(provider) and spent + 0.10 > settings.api_monthly_budget_cny and budget_choice != "continue":
        raise HTTPException(status_code=402, detail={"code":"monthly_budget_requires_choice", "spent_cny":spent, "estimated_cny":0.10, "budget_cny":settings.api_monthly_budget_cny, "choices":["继续付费", "改用模拟服务", "取消", "推迟"]})
    try:
        generated = await provider.generate_unity_code(snapshot, knowledge)
        job = await start_unity_build({
            "projectId": snapshot.id,
            "unityProjectPath": settings.unity_project_path,
            "modelPath": visual_asset_paths[0] if game_mode == "3d" else None,
            "spritePath": visual_asset_paths[0] if game_mode == "2d" else None,
            "spritePaths": visual_asset_paths if game_mode == "2d" else [],
            "mode": game_mode,
            "audioPath": audio_path,
            "runtimeScript": generated.source,
            "buildPlan": build_plan.model_dump(mode="json"),
        })
    except ProviderFailure as error:
        raise HTTPException(status_code=502, detail={"code":error.code, "message":str(error), "retryable":error.retryable}) from error
    except LocalBridgeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    async def persist_started_job() -> None:
        async with SessionFactory() as persist_session:
            async with persist_session.begin():
                project = await get_project_or_404(persist_session, project_id, for_update=True)
                if project.revision != expected_revision or project.current_stage not in {Stage.READY_TO_BUILD, Stage.UNITY_REVIEW}:
                    raise HTTPException(status_code=409, detail="生成代码期间项目已被修改，请重新点击构建")
                project.current_stage = Stage.UNITY_BUILDING
                version = next_version(project, "unity_job")
                project.artifacts["unity_job"] = {"version": version, "data": {"id": job["id"], "status": job.get("status", "排队中")}}
                touch(project, f"玩家启动 Unity 构建：{job['id']}；模板 {build_plan.template_id}；代码来源 {generated.provider}/{generated.model}")
                await save_project(persist_session, project)
                await record_llm_call(persist_session, project.id, "unity_code", generated.provider, generated.model, generated.input_tokens, generated.output_tokens, generated.cost_cny)
    await asyncio.shield(persist_started_job())
    return job


@app.get("/projects/{project_id}/unity/changes")
async def unity_changes(project_id: str, session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    await get_project_or_404(session, project_id)
    return await list_project_changes(session, project_id)


@app.post("/projects/{project_id}/unity/changes/preview", status_code=201)
async def preview_unity_change(project_id: str, request: UnityChangePreviewRequest, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if project.current_stage not in {Stage.READY_TO_BUILD, Stage.UNITY_REVIEW, Stage.PLAYTESTING}:
            raise HTTPException(status_code=409, detail="只有完成全部审批的项目可以提出 Unity 共创变更")
        try:
            row = await create_change_preview(session, project_id, request)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        touch(project, f"Agent 提出 Unity 变更预览：{row.id}；尚未写入")
        await save_project(session, project)
    return serialize_change(row)


@app.post("/unity/changes/{change_id}/decision")
async def decide_unity_change(change_id: str, request: UnityChangeDecisionRequest, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    async with session.begin():
        row = await session.get(UnityChangeRow, change_id, with_for_update=True)
        if not row:
            raise HTTPException(status_code=404, detail="找不到 Unity 共创提议")
        if row.status != "preview":
            raise HTTPException(status_code=409, detail="该提议已经处理")
        row.decided_at = datetime.now(UTC)
        if request.decision == "reject":
            row.status = "rejected"
            return serialize_change(row)
        row.status = "applying"
        payload = bridge_payload(row, settings.unity_project_path)
    try:
        receipt = await apply_co_creation(payload)
    except LocalBridgeError as error:
        async with session.begin():
            failed = await session.get(UnityChangeRow, change_id, with_for_update=True)
            if failed:
                failed.status = "failed"
                failed.receipt_payload = {"success": False, "message": str(error)}
        raise HTTPException(status_code=503, detail=str(error)) from error
    async with session.begin():
        applied = await session.get(UnityChangeRow, change_id, with_for_update=True)
        if not applied:
            raise HTTPException(status_code=404, detail="共创提议在应用期间消失")
        applied.status = "applied"
        applied.receipt_payload = receipt
        applied.checkpoint_path = receipt.get("checkpointPath")
        applied.applied_at = datetime.now(UTC)
        project = await get_project_or_404(session, applied.project_id, for_update=True)
        touch(project, f"玩家批准并应用 Unity 变更：{applied.id}；检查点 {applied.checkpoint_path}")
        await save_project(session, project)
        return serialize_change(applied)


@app.post("/unity/changes/{change_id}/undo")
async def undo_unity_change(change_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    async with session.begin():
        row = await session.get(UnityChangeRow, change_id, with_for_update=True)
        if not row:
            raise HTTPException(status_code=404, detail="找不到 Unity 共创变更")
        if row.status != "applied" or not row.checkpoint_path:
            raise HTTPException(status_code=409, detail="只有已应用且具有检查点的变更可以撤销")
        undo_id = str(uuid4())
        payload = undo_payload(row, undo_id, settings.unity_project_path)
    try:
        receipt = await apply_co_creation(payload)
    except LocalBridgeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    async with session.begin():
        undone = await session.get(UnityChangeRow, change_id, with_for_update=True)
        if not undone:
            raise HTTPException(status_code=404, detail="共创变更在撤销期间消失")
        undone.status = "undone"
        undone.undone_at = datetime.now(UTC)
        undone.receipt_payload = {**undone.receipt_payload, "undo_receipt": receipt}
        project = await get_project_or_404(session, undone.project_id, for_update=True)
        touch(project, f"玩家撤销 Unity 变更：{undone.id}；已恢复检查点")
        await save_project(session, project)
        return serialize_change(undone)


@app.get("/projects/{project_id}/playtests")
async def project_playtests(project_id: str, session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    await get_project_or_404(session, project_id)
    return await list_playtests(session, project_id)


@app.post("/projects/{project_id}/playtests/start", status_code=201)
async def start_playtest(project_id: str, request: PlaytestStartRequest, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    if request.build_job_id:
        try:
            job = await bridge_job(request.build_job_id)
        except LocalBridgeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if job.get("status") != "成功":
            raise HTTPException(status_code=409, detail="只能对成功构建启动试玩")
    snapshot = await get_project_or_404(session, project_id)
    snapshot_logic_version = snapshot.versions.get("logic", 0)
    snapshot_approval = snapshot.approvals.get("logic")
    if snapshot.current_stage not in {Stage.READY_TO_BUILD, Stage.UNITY_REVIEW, Stage.PLAYTESTING} or not snapshot_approval or snapshot_approval.version != snapshot_logic_version:
        raise HTTPException(status_code=409, detail="当前逻辑版本尚未批准，不能开始试玩")
    await session.rollback()
    try:
        play_receipt = await start_playtest_in_unity()
    except LocalBridgeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        logic_version = project.versions.get("logic", 0)
        approval = project.approvals.get("logic")
        if project.current_stage not in {Stage.READY_TO_BUILD, Stage.UNITY_REVIEW, Stage.PLAYTESTING} or not approval or approval.version != logic_version:
            raise HTTPException(status_code=409, detail="当前逻辑版本尚未批准，不能开始试玩")
        now = datetime.now(UTC)
        row = PlaytestSessionRow(id=str(uuid4()), project_id=project_id, build_job_id=request.build_job_id, logic_version=logic_version, status="playing", evidence={"initial_play": play_receipt, "logic_approval_id": approval.id}, created_at=now, updated_at=now)
        session.add(row)
        project.current_stage = Stage.PLAYTESTING
        touch(project, f"开始试玩会话：{row.id}；逻辑第 {logic_version} 版")
        await save_project(session, project)
        return serialize_playtest(row)


@app.post("/playtests/{playtest_id}/feedback")
async def record_playtest_feedback(playtest_id: str, request: PlaytestFeedbackRequest, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    async with session.begin():
        row = await session.get(PlaytestSessionRow, playtest_id, with_for_update=True)
        if not row:
            raise HTTPException(status_code=404, detail="找不到试玩会话")
        if row.status != "playing":
            raise HTTPException(status_code=409, detail="当前会话不在首次试玩阶段")
        row.initial_feedback = request.feedback
        row.initial_rating = request.rating
        row.status = "feedback"
        update_evidence(row, feedback_recorded_at=datetime.now(UTC).isoformat())
        project = await get_project_or_404(session, row.project_id, for_update=True)
        touch(project, f"记录试玩反馈：{row.id}；评分 {request.rating}/5")
        await save_project(session, project)
        return serialize_playtest(row)


@app.post("/playtests/{playtest_id}/propose-revision")
async def propose_playtest_revision(playtest_id: str, request: PlaytestRevisionRequest, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    row = await session.get(PlaytestSessionRow, playtest_id)
    if not row:
        raise HTTPException(status_code=404, detail="找不到试玩会话")
    if row.status != "feedback" or not row.initial_feedback:
        raise HTTPException(status_code=409, detail="必须先记录首次试玩反馈")
    project_snapshot = await get_project_or_404(session, row.project_id)
    knowledge = await get_knowledge(session, project_snapshot.selected_knowledge_id)
    if not knowledge:
        raise HTTPException(status_code=409, detail="项目知识条目不存在")
    feedback = row.initial_feedback
    await session.rollback()
    provider = get_llm_provider()
    try:
        agent_response = await provider.respond(AgentRequest(project_id=project_snapshot.id, message=f"根据试玩反馈提出最小修改：{feedback}", mode="code"), project_snapshot, knowledge)
    except ProviderFailure as error:
        raise HTTPException(status_code=502, detail={"code": error.code, "message": str(error), "retryable": error.retryable}) from error
    async with session.begin():
        locked = await session.get(PlaytestSessionRow, playtest_id, with_for_update=True)
        if not locked or locked.status != "feedback":
            raise HTTPException(status_code=409, detail="试玩会话已被其他请求修改")
        project = await get_project_or_404(session, locked.project_id, for_update=True)
        previous_logic = project.artifacts.get("logic", {}).get("data", {})
        version = next_version(project, "logic")
        project.artifacts["logic"] = {"version": version, "data": {**previous_logic, "playtest_revision": {"session_id": locked.id, "feedback": locked.initial_feedback, "agent_proposal": agent_response.content, "template_id": request.template_id}}}
        project.current_stage = Stage.LOGIC_REVIEW
        change = await create_change_preview(session, project.id, UnityChangePreviewRequest(action="request_interaction", object_name=request.object_name, template_id=request.template_id, interaction=locked.initial_feedback))
        locked.revision_change_id = change.id
        locked.status = "revision_preview"
        update_evidence(locked, agent_provider=agent_response.provider, agent_model=agent_response.model, proposed_logic_version=version, approval_freshness="旧逻辑批准已失效")
        suggestion_id = await create_suggestion(session, project, agent_response.content, agent_type="unity_revision")
        update_evidence(locked, suggestion_id=suggestion_id)
        touch(project, f"试玩反馈生成逻辑第 {version} 版；旧批准失效；等待玩家批准")
        await save_project(session, project)
        await record_llm_call(session, project.id, "playtest_revision", agent_response.provider, agent_response.model, agent_response.input_tokens, agent_response.output_tokens, agent_response.cost_cny)
        return {"playtest": serialize_playtest(locked), "change": serialize_change(change), "project": project.model_dump(mode="json")}


@app.post("/playtests/{playtest_id}/approve-revision")
async def approve_playtest_revision(playtest_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    async with session.begin():
        row = await session.get(PlaytestSessionRow, playtest_id, with_for_update=True)
        if not row or row.status != "revision_preview" or not row.revision_change_id:
            raise HTTPException(status_code=409, detail="当前没有可批准的试玩修改")
        change = await session.get(UnityChangeRow, row.revision_change_id, with_for_update=True)
        if not change or change.status != "preview":
            raise HTTPException(status_code=409, detail="Unity 修改提议不可用")
        project = await get_project_or_404(session, row.project_id, for_update=True)
        version = project.versions.get("logic", 0)
        if project.current_stage != Stage.LOGIC_REVIEW:
            raise HTTPException(status_code=409, detail="项目不在新逻辑审批阶段")
        project.approvals["logic"] = Approval(artifact="logic", version=version)
        project.current_stage = Stage.READY_TO_BUILD
        suggestion_id = row.evidence.get("suggestion_id") if isinstance(row.evidence, dict) else None
        if suggestion_id:
            await respond_to_suggestion(session, str(suggestion_id), "accepted", "玩家批准试玩修改")
        change.status = "applying"
        change.decided_at = datetime.now(UTC)
        payload = {**bridge_payload(change, settings.unity_project_path), "playAfterApply": True}
        revision_change_id = change.id
        touch(project, f"玩家批准试玩修改与逻辑第 {version} 版；开始编译并再次试玩")
        await save_project(session, project)
    try:
        receipt = await apply_co_creation(payload)
    except LocalBridgeError as error:
        async with session.begin():
            failed_session = await session.get(PlaytestSessionRow, playtest_id, with_for_update=True)
            failed_change = await session.get(UnityChangeRow, revision_change_id, with_for_update=True)
            if failed_session: failed_session.status = "failed"; update_evidence(failed_session, error=str(error))
            if failed_change: failed_change.status = "failed"; failed_change.receipt_payload = {"success": False, "message": str(error)}
        raise HTTPException(status_code=503, detail=str(error)) from error
    async with session.begin():
        replay = await session.get(PlaytestSessionRow, playtest_id, with_for_update=True)
        applied = await session.get(UnityChangeRow, replay.revision_change_id, with_for_update=True) if replay else None
        if not replay or not applied:
            raise HTTPException(status_code=404, detail="试玩修改记录消失")
        applied.status = "applied"; applied.receipt_payload = receipt; applied.checkpoint_path = receipt.get("checkpointPath"); applied.applied_at = datetime.now(UTC)
        replay.status = "replaying"; update_evidence(replay, compile_errors=receipt.get("compilerErrors"), play_again=receipt.get("playMode"), revision_receipt=receipt)
        project = await get_project_or_404(session, replay.project_id, for_update=True)
        project.current_stage = Stage.PLAYTESTING
        touch(project, f"试玩修改已编译通过并再次进入 Play Mode：{replay.id}")
        await save_project(session, project)
        return {"playtest": serialize_playtest(replay), "change": serialize_change(applied), "project": project.model_dump(mode="json")}


@app.post("/playtests/{playtest_id}/complete")
async def complete_playtest(playtest_id: str, request: PlaytestFeedbackRequest, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    async with session.begin():
        row = await session.get(PlaytestSessionRow, playtest_id, with_for_update=True)
        if not row:
            raise HTTPException(status_code=404, detail="找不到试玩会话")
        if row.status != "replaying":
            raise HTTPException(status_code=409, detail="必须先完成修改、编译与再次试玩")
        now = datetime.now(UTC)
        row.final_feedback = request.feedback; row.final_rating = request.rating; row.status = "awaiting_final_approval"
        update_evidence(row, final_feedback_recorded_at=now.isoformat())
        project = await get_project_or_404(session, row.project_id, for_update=True)
        project.current_stage = Stage.PLAYTESTING
        touch(project, f"记录最终试玩结果：{row.id}；评分 {request.rating}/5；等待玩家完成项目确认")
        await save_project(session, project)
        return serialize_playtest(row)


@app.post("/projects/{project_id}/finish", response_model=Project)
async def finish_project(project_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        row = await session.scalar(
            select(PlaytestSessionRow)
            .where(PlaytestSessionRow.project_id == project_id)
            .order_by(PlaytestSessionRow.created_at.desc())
            .with_for_update()
        )
        if project.current_stage != Stage.PLAYTESTING or not row or row.status != "awaiting_final_approval":
            raise HTTPException(status_code=409, detail={"code":"final_approval_not_ready","message":"必须先完成修改、编译、再次试玩并保存最终反馈。"})
        now = datetime.now(UTC)
        row.status = "completed"
        row.completed_at = now
        update_evidence(row, completed_at=now.isoformat(), final_approved_by="player")
        final_version = max(project.versions.get("logic", 1), 1)
        project.approvals["final"] = Approval(artifact="final", version=final_version, comment="玩家明确确认完成项目")
        project.current_stage = Stage.COMPLETED
        touch(project, f"玩家完成最终审批：{row.id}；项目已完成")
        await save_project(session, project)
        return project


@app.get("/projects/{project_id}/research")
async def project_research(project_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    await get_project_or_404(session, project_id)
    return await research_snapshot(session, project_id)


@app.post("/projects/{project_id}/research/export")
async def export_project_research(project_id: str, format: str = Query(default="json", pattern="^(json|csv)$"), session: AsyncSession = Depends(get_session)) -> FileResponse:
    await get_project_or_404(session, project_id)
    await session.rollback()
    async with session.begin():
        path, export_row = await create_research_export(session, project_id, format)
    media_type = "application/json" if format == "json" else "text/csv"
    return FileResponse(path, media_type=media_type, filename=path.name, headers={"X-QIWEN-Export-Id": export_row.id, "X-QIWEN-Export-SHA256": export_row.sha256})


@app.get("/knowledge")
async def list_knowledge_endpoint(session: AsyncSession = Depends(get_session)) -> list[Any]:
    return await list_knowledge(session)


@app.get("/knowledge/{knowledge_id}")
async def knowledge_detail(knowledge_id: str, session: AsyncSession = Depends(get_session)) -> Any:
    entry = await get_knowledge(session, knowledge_id)
    if not entry:
        raise HTTPException(status_code=404, detail="knowledge_not_found")
    return entry


@app.post("/projects", response_model=Project)
async def create_project(request: CreateProjectRequest, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        knowledge = await get_knowledge(session, request.knowledge_id)
        if not knowledge:
            raise HTTPException(status_code=400, detail="knowledge_not_found")
        project = Project(
            selected_knowledge_id=knowledge.id,
            title=request.title or f"{knowledge.title} · 新游戏",
            current_stage=Stage.KNOWLEDGE_SELECTION,
        )
        touch(project, f"已选择知识：{knowledge.title}")
        await save_project(session, project)
        await attach_project_assets(session, project.id)
    return project


@app.get("/projects", response_model=list[Project])
async def read_projects(
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[Project]:
    return await list_projects(session, limit=limit, offset=offset)


@app.get("/projects/{project_id}", response_model=Project)
async def read_project(project_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    return await get_project_or_404(session, project_id)


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    async with session.begin():
        row = await session.get(ProjectRow, project_id, with_for_update=True)
        if row is None:
            raise HTTPException(status_code=404, detail={"code":"project_not_found","message":"项目不存在或已经删除。"})
        await session.delete(row)
    return {"deleted": True}


@app.get("/assets", response_model=list[Asset])
async def read_assets(project_id: str | None = None, session: AsyncSession = Depends(get_session)) -> list[Asset]:
    return await list_assets(session, project_id)


@app.post("/projects/{project_id}/assets/{asset_id}/use", response_model=Project)
async def use_project_asset(project_id: str, asset_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        selected = await use_asset_in_project(session, project_id, asset_id)
        if selected is None:
            raise HTTPException(status_code=404, detail="asset_not_found")
        selected_id, asset_type, asset_name = selected
        project.selected_assets[asset_type] = selected_id
        touch(project, f"已选用素材：{asset_name}")
        await save_project(session, project)
    return project


@app.get("/projects/{project_id}/persistence")
async def read_persistence(project_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    project = await get_project_or_404(session, project_id)
    return {"project_id": project.id, "progress": project.progress, "revision": project.revision, "counts": await persistence_counts(session, project_id)}


@app.post("/projects/{project_id}/idea", response_model=Project)
async def save_idea(project_id: str, request: IdeaRequest, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if project.current_stage not in {Stage.KNOWLEDGE_SELECTION, Stage.CONCEPT_DRAFTING}:
            raise HTTPException(status_code=409, detail="idea_stage_closed")
        project.player_idea = request.idea
        if not project.original_player_idea:
            project.original_player_idea = request.idea
        project.current_stage = Stage.CONCEPT_DRAFTING
        project.conversation_history.append(ConversationMessage(role="user", content=request.idea))
        touch(project, "玩家想法已保存")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/production-mode", response_model=Project)
async def set_production_mode(project_id: str, request: ProductionModeRequest, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if project.current_stage not in {Stage.KNOWLEDGE_SELECTION, Stage.CONCEPT_DRAFTING, Stage.CONCEPT_REVIEW, Stage.VISUAL_DRAFTING}:
            raise HTTPException(status_code=409, detail={"code":"mode_locked","message":"视觉画面生成后如需切换制作模式，请先返回视觉草稿阶段。"})
        version = next_version(project, "production_mode")
        project.artifacts["production_mode"] = {"version":version,"data":{"mode":request.mode}}
        existing_plan = project.artifacts.get("game_asset_plan", {}).get("data", {})
        existing_items = existing_plan.get("items", [])
        if not existing_items or all(item.get("status") == "pending" for item in existing_items):
            plan_version = next_version(project, "game_asset_plan")
            project.artifacts["game_asset_plan"] = {"version": plan_version, "data": default_game_asset_plan(project, request.mode)}
        touch(project, f"玩家选择{'二维' if request.mode == '2d' else '三维'}游戏制作模式")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/generate/{kind}", response_model=Project)
async def generate_artifact(project_id: str, kind: str, payload: dict[str, Any] | None = Body(default=None), budget_choice: str | None = Header(default=None, alias="X-Qiwen-Budget-Choice"), session: AsyncSession = Depends(get_session)) -> Project:
    transition = GENERATION_TRANSITIONS.get(kind)
    if not transition:
        raise HTTPException(status_code=400, detail="unknown_generation_stage")
    required, target = transition
    llm_provider = get_llm_provider("music" if kind == "music" else None)
    structured = None
    unity_plan = None
    audio_design = None
    asset_task = None
    asset_request = None
    if kind in {"concept", "logic"}:
        async with session.begin():
            snapshot = await get_project_or_404(session, project_id, for_update=True)
            if snapshot.current_stage != required:
                raise HTTPException(status_code=409, detail={"code": "invalid_stage", "expected": required, "actual": snapshot.current_stage})
            knowledge = await get_knowledge(session, snapshot.selected_knowledge_id)
            expected_revision = snapshot.revision
            spent = await monthly_api_cost(session)
        requested_direction = (payload or {}).get("prompt")
        if kind in {"concept", "logic"} and isinstance(requested_direction, str) and requested_direction.strip():
            snapshot = snapshot.model_copy(deep=True)
            snapshot.artifacts[f"player_{kind}_direction"] = {"version": 1, "data": {"prompt": requested_direction.strip()}}
        if is_real_llm_provider(llm_provider) and spent + 0.10 > settings.api_monthly_budget_cny and budget_choice != "continue":
            raise HTTPException(status_code=402, detail={"code":"monthly_budget_requires_choice", "spent_cny":spent, "budget_cny":settings.api_monthly_budget_cny, "choices":["继续付费", "改用模拟服务", "取消", "推迟"]})
        async def generate_design(provider):
            generated = await provider.generate_structured(kind, snapshot, knowledge)
            generated_plan = None
            if kind == "logic":
                plan_snapshot = snapshot.model_copy(deep=True)
                plan_snapshot.artifacts["logic"] = {"version": next_version(snapshot, "logic"), "data": generated.data}
                plan_snapshot.approvals["logic"] = Approval(artifact="logic", version=plan_snapshot.artifacts["logic"]["version"])
                generated_plan = await provider.generate_unity_plan(plan_snapshot, knowledge)
            return generated, generated_plan

        try:
            structured, unity_plan = await generate_design(llm_provider)
        except ProviderFailure as exc:
            if exc.retryable and isinstance(llm_provider, MicuLLMProvider):
                fallback_provider = MicuLLMProvider(code_model=settings.micu_chat_model)
                try:
                    structured, unity_plan = await generate_design(fallback_provider)
                except ProviderFailure as fallback_exc:
                    raise HTTPException(status_code=502, detail={"code":fallback_exc.code, "message":str(fallback_exc), "retryable":fallback_exc.retryable}) from fallback_exc
            else:
                raise HTTPException(status_code=502, detail={"code":exc.code, "message":str(exc), "retryable":exc.retryable}) from exc
    elif kind in {"visual", "3d", "music"}:
        async with session.begin():
            snapshot = await get_project_or_404(session, project_id, for_update=True)
            if snapshot.current_stage != required:
                raise HTTPException(status_code=409, detail={"code":"invalid_stage","expected":required,"actual":snapshot.current_stage})
            expected_revision = snapshot.revision
            spent = await monthly_api_cost(session)
            asset_knowledge = await get_knowledge(session, snapshot.selected_knowledge_id) if kind == "music" else None
        saved_mode = (
            snapshot.artifacts.get("production_mode", {})
            .get("data", {})
            .get("mode")
        )
        if kind == "music":
            music_snapshot = snapshot.model_copy(deep=True)
            requested_music_prompt = (payload or {}).get("prompt")
            if isinstance(requested_music_prompt, str) and requested_music_prompt.strip():
                music_snapshot.artifacts["player_music_direction"] = {"version": 1, "data": {"prompt": requested_music_prompt.strip()}}
            try:
                audio_design = await llm_provider.generate_structured("audio", music_snapshot, asset_knowledge)
            except ProviderFailure:
                # 音乐设计分析是辅助步骤，不能因为它的凭据或服务异常阻断音乐生成。
                # 优先改用主共创服务；主服务也不可用时，直接保留玩家提示词继续生成。
                try:
                    audio_design = await get_llm_provider().generate_structured("audio", music_snapshot, asset_knowledge)
                except ProviderFailure:
                    audio_design = None
        requested_mode = (payload or {}).get("mode") or saved_mode or "3d"
        two_d_mode = kind == "3d" and requested_mode == "2d"
        visual_prompt = (
            "彩色卡通 3D 中国漆艺游戏概念图，风格化低多边形角色、立体场景与漆艺道具，"
            "清晰体块、丰富协调的青绿朱红与金色、漆面高光与温暖光影，不要黑白灰，不要文字水印"
            if saved_mode == "3d"
            else "彩色卡通 2D 中国漆艺游戏概念图，清晰轮廓与分层绘制，丰富协调的色彩，"
            "漆面高光与温暖光影，可玩的横版游戏场景，不要三维写实，不要黑白灰，不要文字水印"
        )
        defaults = {
            "visual": AssetGenerationRequest(prompt=visual_prompt),
            "3d": AssetGenerationRequest(prompt="适合 Unity 的低面数黑漆碗，完整 PBR 材质，GLB"),
            "music": AssetGenerationRequest(prompt="克制、缓慢层积、木质打击与呼吸感的纯音乐循环"),
        }
        if two_d_mode:
            defaults["3d"] = AssetGenerationRequest(prompt="彩色卡通 2D 游戏素材表，中国漆艺主题，角色、漆碗道具和横版场景元素，透明感清晰轮廓，统一比例，不要三维写实，不要文字水印")
        asset_request = defaults[kind]
        if kind == "music" and audio_design is not None:
            sound = audio_design.data
            asset_request = AssetGenerationRequest(
                prompt=f"{sound.get('title','游戏声音')}；{sound.get('mood','专注、手作')}；事件：{'、'.join(sound.get('event_cues',[]))}"[:800],
                mood=str(sound.get("mood", "专注、手作")), tempo=int(sound.get("tempo", 76)), duration=int(sound.get("duration", 20)),
                loop=bool(sound.get("loop", True)), sound_layers=list(sound.get("layers", [])), cue_names=list(sound.get("event_cues", [])),
            )
        prompt_override = (payload or {}).get("prompt")
        if prompt_override is not None:
            if not isinstance(prompt_override, str) or not 3 <= len(prompt_override.strip()) <= 800:
                raise HTTPException(status_code=422, detail={"code":"invalid_prompt","message":"提示词需要 3 至 800 个字符"})
            asset_request = asset_request.model_copy(update={"prompt": prompt_override.strip()})
        reference_asset_ids = (payload or {}).get("reference_asset_ids", [])
        if reference_asset_ids:
            if kind != "visual" or not isinstance(reference_asset_ids, list) or len(reference_asset_ids) > 6:
                raise HTTPException(status_code=422, detail={"code":"invalid_references","message":"参考图最多 6 张，且仅用于视觉生成。"})
            references: list[str] = []
            async with SessionFactory() as reference_session:
                for asset_id in reference_asset_ids:
                    row = await reference_session.get(AssetRow, str(asset_id))
                    if not row or row.project_id != project_id or row.type != "IMAGE":
                        raise HTTPException(status_code=404, detail={"code":"reference_missing","message":"参考图不存在或不属于当前项目。"})
                    references.append(row.url)
            asset_request = asset_request.model_copy(update={"reference_urls": references})
        generation_kind = "visual" if kind == "visual" or two_d_mode else kind
        asset_provider = get_asset_provider("image" if generation_kind == "visual" else generation_kind)
        local_generation = asset_provider.name.startswith("mock") or asset_provider.name == "agent-designed-audio"
        estimate = 0 if local_generation else float({"visual":os.getenv("MICU_IMAGE_ESTIMATED_COST_CNY",os.getenv("JIMENG_ESTIMATED_COST_CNY","1")),"3d":os.getenv("HUNYUAN3D_ESTIMATED_COST_CNY","10"),"music":os.getenv("TENCENT_MPS_ESTIMATED_COST_CNY","2")}[generation_kind])
        if spent + estimate > settings.api_monthly_budget_cny and budget_choice != "continue":
            raise HTTPException(status_code=402, detail={"code":"monthly_budget_requires_choice","spent_cny":spent,"estimated_cny":estimate,"budget_cny":settings.api_monthly_budget_cny,"choices":["继续付费","改用模拟服务","取消","推迟"]})
        try:
            asset_task = await run_asset_provider(asset_provider, asset_request)
            source_urls = extract_provider_urls(generation_kind, asset_task.payload)
            if not source_urls:
                raise AssetProviderError(
                    "provider_output_missing",
                    "当前生成服务没有返回可用文件，请稍后重试。",
                    True,
                )
            ingested = await ingest_urls(generation_kind, source_urls)
            asset_task.payload = {**asset_task.payload,"source_urls":source_urls,"urls":[item["url"] for item in ingested],"ingested":ingested}
        except (AssetProviderError, ObjectValidationError, httpx.HTTPError) as exc:
            # 真实服务失败时绝不把精选素材、静态文件或本地回退冒充本次生成结果。
            # Mock 仍可在显式开发配置中作为独立 Provider 使用，但不能由失败路径自动切换。
            code = exc.code if isinstance(exc, AssetProviderError) else "provider_http_failed"
            retryable = exc.retryable if isinstance(exc, AssetProviderError) else True
            raise HTTPException(status_code=502, detail={"code":code,"message":str(exc),"retryable":retryable}) from exc

    artifact_kind = "2d" if kind == "3d" and locals().get("two_d_mode", False) else kind
    try:
        artifact_data = structured.data if structured is not None else task_to_artifact(artifact_kind, asset_task, asset_request) if asset_task is not None else mock_artifact(kind, snapshot)
    except AssetProviderError as exc:
        raise HTTPException(status_code=502, detail={"code": exc.code, "message": str(exc), "retryable": exc.retryable}) from exc

    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if project.current_stage != required:
            raise HTTPException(status_code=409, detail={"code": "invalid_stage", "expected": required, "actual": project.current_stage})
        if structured is not None and project.revision != expected_revision:
            raise HTTPException(status_code=409, detail={"code":"project_changed_during_generation"})
        version = next_version(project, kind)
        if kind == "logic" and unity_plan is not None:
            artifact_data = {**artifact_data, "unity_build_plan": unity_plan.data}
        if kind == "music" and audio_design is not None:
            artifact_data = {**artifact_data, "sound_design": audio_design.data}
        if kind == "music":
            previous_music = project.artifacts.get("music", {}).get("data", {})
            previous_tracks = list(previous_music.get("tracks", []))
            new_tracks = [
                {**track, "id": f"music-{version}-{index + 1}", "title": f"音乐版本 {len(previous_tracks) + index + 1}"}
                for index, track in enumerate(artifact_data.get("tracks", []))
            ]
            artifact_data = {
                **artifact_data,
                "tracks": [*previous_tracks, *new_tracks],
                "selected": new_tracks[0]["id"] if new_tracks else previous_music.get("selected"),
            }
        project.artifacts[kind] = {"version": version, "data": artifact_data}
        project.current_stage = target
        provider_name = structured.provider if structured is not None else asset_task.provider if asset_task is not None else "mock"
        touch(project, f"{provider_name} 服务已生成 {kind} 第 {version} 版")
        await save_project(session, project)
        await record_provider_job(session, project, kind, version, artifact_data, provider_name)
        await record_generated_assets(session, project, kind, version, artifact_data)
        if structured is not None:
            await record_llm_call(session, project.id, kind, structured.provider, structured.model, structured.input_tokens, structured.output_tokens, structured.cost_cny)
        if unity_plan is not None:
            await record_llm_call(session, project.id, "unity_build_plan", unity_plan.provider, unity_plan.model, unity_plan.input_tokens, unity_plan.output_tokens, unity_plan.cost_cny)
        if audio_design is not None:
            await record_llm_call(session, project.id, "audio_design", audio_design.provider, audio_design.model, audio_design.input_tokens, audio_design.output_tokens, audio_design.cost_cny)
    return project


@app.post("/projects/{project_id}/music/tracks/{track_id}/select", response_model=Project)
async def select_music_track(project_id: str, track_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        editable_stages = {Stage.MUSIC_REVIEW, Stage.LOGIC_DRAFTING, Stage.LOGIC_REVIEW, Stage.READY_TO_BUILD}
        if project.current_stage not in editable_stages:
            raise HTTPException(status_code=409, detail={"code":"invalid_stage","message":"当前阶段不能更换音乐版本。"})
        current = project.artifacts.get("music", {}).get("data", {})
        if not any(track.get("id") == track_id for track in current.get("tracks", [])):
            raise HTTPException(status_code=404, detail={"code":"track_missing","message":"音乐版本不存在。"})
        version = next_version(project, "music")
        project.artifacts["music"] = {"version": version, "data": {**current, "selected": track_id}}
        for item in ("music", "logic"):
            project.approvals.pop(item, None)
        await session.execute(sqlalchemy_delete(ApprovalRow).where(ApprovalRow.project_id == project.id, ApprovalRow.artifact.in_(["music", "logic"])))
        project.current_stage = Stage.MUSIC_REVIEW
        touch(project, "玩家选择了音乐版本")
        await save_project(session, project)
    return project


@app.delete("/projects/{project_id}/music/tracks/{track_id}", response_model=Project)
async def delete_music_track(project_id: str, track_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        editable_stages = {Stage.MUSIC_REVIEW, Stage.LOGIC_DRAFTING, Stage.LOGIC_REVIEW, Stage.READY_TO_BUILD}
        if project.current_stage not in editable_stages:
            raise HTTPException(status_code=409, detail={"code":"invalid_stage","message":"当前阶段不能删除音乐版本。"})
        current = project.artifacts.get("music", {}).get("data", {})
        tracks = list(current.get("tracks", []))
        removed = next((track for track in tracks if track.get("id") == track_id), None)
        if removed is None:
            raise HTTPException(status_code=404, detail={"code":"track_missing","message":"音乐版本不存在。"})
        remaining = [track for track in tracks if track.get("id") != track_id]
        version = next_version(project, "music")
        selected = current.get("selected")
        if selected == track_id:
            selected = remaining[0]["id"] if remaining else None
        project.artifacts["music"] = {"version": version, "data": {**current, "tracks": remaining, "selected": selected}}
        rows = (await session.scalars(select(AssetRow).where(AssetRow.project_id == project.id, AssetRow.url == removed.get("url")))).all()
        for row in rows:
            await session.delete(row)
        for item in ("music", "logic"):
            project.approvals.pop(item, None)
        await session.execute(sqlalchemy_delete(ApprovalRow).where(ApprovalRow.project_id == project.id, ApprovalRow.artifact.in_(["music", "logic"])))
        project.current_stage = Stage.MUSIC_REVIEW if remaining else Stage.MUSIC_DRAFTING
        touch(project, "玩家删除了一个音乐版本")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/approve/{kind}", response_model=Project)
async def approve_artifact(project_id: str, kind: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        transition = APPROVAL_TRANSITIONS.get(kind)
        if not transition:
            raise HTTPException(status_code=400, detail="unknown_approval_stage")
        required, target = transition
        if project.current_stage != required:
            raise HTTPException(status_code=409, detail={"code": "invalid_stage", "expected": required, "actual": project.current_stage})
        artifact = project.artifacts.get(kind)
        if not artifact:
            raise HTTPException(status_code=409, detail="artifact_missing")
        project.approvals[kind] = Approval(artifact=kind, version=artifact["version"])
        local_revision = project.artifacts.get("local_revision_resume", {}).get("data", {})
        # A revision opened from its own review screen is an ordinary approval:
        # continue to the next stage instead of returning to that same review.
        if local_revision.get("kind") == kind and local_revision.get("stage") and local_revision["stage"] != required.value:
            project.current_stage = Stage(local_revision["stage"])
            project.artifacts.pop("local_revision_resume", None)
        else:
            project.current_stage = target
            project.artifacts.pop("local_revision_resume", None)
        if kind == "visual" and project.artifacts.get("production_mode", {}).get("data", {}).get("mode") == "2d" and "game_asset_plan" not in project.artifacts:
            project.versions["game_asset_plan"] = 1
            mode = project.artifacts.get("production_mode", {}).get("data", {}).get("mode", "2d")
            project.artifacts["game_asset_plan"] = {"version": 1, "data": default_game_asset_plan(project, mode)}
        touch(project, f"玩家已批准 {kind} 第 {artifact['version']} 版")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/game-assets/plan", response_model=Project)
async def save_game_asset_plan(project_id: str, request: GameAssetPlanRequest, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if project.current_stage not in {Stage.THREE_D_DRAFTING, Stage.THREE_D_REVIEW}:
            raise HTTPException(status_code=409, detail={"code":"invalid_stage","message":"当前阶段不能修改游戏素材清单。"})
        existing = project.artifacts.get("game_asset_plan", {}).get("data", {}).get("items", [])
        asset_by_item = {item.get("id"): (item.get("asset_id"), item.get("status")) for item in existing}
        items = []
        for item in request.items:
            data = item.model_dump()
            if item.id in asset_by_item:
                data["asset_id"], data["status"] = asset_by_item[item.id]
            items.append(data)
        version = next_version(project, "game_asset_plan")
        project.artifacts["game_asset_plan"] = {"version":version,"data":{"style":request.style.strip(),"items":items}}
        touch(project, "玩家更新了独立游戏素材清单")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/game-assets/rework", response_model=Project)
async def rework_game_assets(project_id: str, request: ProductionModeRequest, session: AsyncSession = Depends(get_session)) -> Project:
    """把项目显式退回多素材阶段；旧素材和后续成果保留，只让素材组重新确认。"""
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if "concept" not in project.artifacts:
            raise HTTPException(status_code=409, detail={"code":"concept_missing","message":"请先完成游戏概念。"})
        mode_version = next_version(project, "production_mode")
        project.artifacts["production_mode"] = {"version": mode_version, "data": {"mode": request.mode}}
        plan_version = next_version(project, "game_asset_plan")
        project.artifacts["game_asset_plan"] = {"version": plan_version, "data": default_game_asset_plan(project, request.mode)}
        project.approvals.pop("3d", None)
        await session.execute(
            sqlalchemy_delete(ApprovalRow).where(
                ApprovalRow.project_id == project.id,
                ApprovalRow.artifact == "3d",
            )
        )
        project.artifacts["local_revision_resume"] = {
            "version": project.versions.get("local_revision_resume", 0) + 1,
            "data": {"kind": "3d", "stage": project.current_stage.value},
        }
        project.versions["local_revision_resume"] = project.artifacts["local_revision_resume"]["version"]
        project.current_stage = Stage.THREE_D_DRAFTING
        touch(project, f"玩家要求按{'二维' if request.mode == '2d' else '三维'}多素材清单重新制作游戏素材")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/game-assets/generate", response_model=Project)
async def generate_game_asset(project_id: str, request: GameAssetGenerateRequest, budget_choice: str | None = Header(default=None, alias="X-Qiwen-Budget-Choice"), session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        snapshot = await get_project_or_404(session, project_id, for_update=True)
        if snapshot.current_stage not in {Stage.THREE_D_DRAFTING, Stage.THREE_D_REVIEW}:
            raise HTTPException(status_code=409, detail={"code":"invalid_stage","message":"当前阶段不能生成游戏素材。"})
        plan = snapshot.artifacts.get("game_asset_plan", {}).get("data", {})
        item = next((entry for entry in plan.get("items", []) if entry.get("id") == request.item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail={"code":"asset_item_missing","message":"素材条目不存在。"})
        expected_revision = snapshot.revision
        spent = await monthly_api_cost(session)
    asset_mode = snapshot.artifacts.get("production_mode", {}).get("data", {}).get("mode", "2d")
    provider_kind = "3d" if asset_mode == "3d" else "image"
    provider = get_asset_provider(provider_kind)
    estimate = 0 if provider.name.startswith("mock") else float(
        os.getenv("HUNYUAN3D_ESTIMATED_COST_CNY", "10") if asset_mode == "3d" else os.getenv("MICU_IMAGE_ESTIMATED_COST_CNY", "1")
    )
    if spent + estimate > settings.api_monthly_budget_cny and budget_choice != "continue":
        raise HTTPException(status_code=402, detail={"code":"monthly_budget_requires_choice","message":"继续生成可能超出本月预算，请选择是否继续。","spent_cny":spent,"estimated_cny":estimate,"budget_cny":settings.api_monthly_budget_cny,"choices":["继续生成","暂不生成"]})
    generation_request = AssetGenerationRequest(prompt=f"{item['prompt']}\n统一风格：{plan.get('style','彩色卡通二维游戏美术')}"[:800])
    try:
        task = await run_asset_provider(provider, generation_request)
        ingest_kind = "3d" if asset_mode == "3d" else "visual"
        urls = extract_provider_urls(ingest_kind, task.payload)
        ingested = await ingest_urls(ingest_kind, urls)
    except AssetProviderError as exc:
        raise HTTPException(status_code=502, detail={"code":exc.code,"message":str(exc),"retryable":exc.retryable}) from exc
    except (ObjectValidationError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail={"code":"asset_save_failed","message":"图片生成完成，但保存到素材库失败。请重试。","retryable":True}) from exc
    if not ingested:
        raise HTTPException(status_code=502, detail={"code":"provider_output_missing","message":"没有收到可用图片，请重试。","retryable":True})
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if project.revision != expected_revision:
            raise HTTPException(status_code=409, detail={"code":"project_changed_during_generation","message":"生成期间素材清单已修改，请重新生成这一项。"})
        plan = project.artifacts["game_asset_plan"]["data"]
        item = next(entry for entry in plan["items"] if entry.get("id") == request.item_id)
        old_asset_id = item.get("asset_id")
        if old_asset_id:
            old = await session.get(AssetRow, old_asset_id)
            if old:
                old.metadata_json = {**(old.metadata_json or {}), "superseded": True, "approved": False}
        result = ingested[0]
        asset_id = f"game-{project.id[:8]}-{request.item_id}-{uuid4().hex[:8]}"
        row = AssetRow(
            id=asset_id, project_id=project.id, type="3D" if asset_mode == "3d" else "IMAGE", name=item["name"], url=str(result["url"]), scope="PROJECT",
            sha256=str(result.get("sha256") or ""), metadata_json={"artifact":"game_asset","item_id":request.item_id,"category":item["category"],"prompt":item["prompt"],"style":plan.get("style"),"approved":False,**result},
        )
        session.add(row)
        item["asset_id"] = asset_id
        item["status"] = "generated"
        version = next_version(project, "game_asset_plan")
        project.artifacts["game_asset_plan"] = {"version":version,"data":plan}
        touch(project, f"已生成独立素材：{item['name']}")
        await save_project(session, project)
        await record_provider_job(session, project, "game_asset", version, {"estimated_cost_cny":task.estimated_cost_cny,"item_id":request.item_id}, task.provider)
    return project


@app.post("/projects/{project_id}/game-assets/{asset_id}/approve", response_model=Project)
async def approve_game_asset(project_id: str, asset_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        row = await session.get(AssetRow, asset_id)
        if not row or row.project_id != project_id or row.metadata_json.get("artifact") != "game_asset":
            raise HTTPException(status_code=404, detail={"code":"asset_missing","message":"素材不存在。"})
        row.metadata_json = {**row.metadata_json, "approved":True}
        plan = project.artifacts.get("game_asset_plan", {}).get("data", {})
        item = next((entry for entry in plan.get("items", []) if entry.get("asset_id") == asset_id), None)
        if item:
            item["status"] = "approved"
        version = next_version(project, "game_asset_plan")
        project.artifacts["game_asset_plan"] = {"version":version,"data":plan}
        touch(project, f"玩家批准独立素材：{row.name}")
        await save_project(session, project)
    return project


@app.delete("/projects/{project_id}/game-assets/{asset_id}", response_model=Project)
async def delete_game_asset(project_id: str, asset_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        row = await session.get(AssetRow, asset_id)
        if not row or row.project_id != project_id or row.metadata_json.get("artifact") != "game_asset":
            raise HTTPException(status_code=404, detail={"code":"asset_missing","message":"素材不存在。"})
        plan = project.artifacts.get("game_asset_plan", {}).get("data", {})
        item = next((entry for entry in plan.get("items", []) if entry.get("asset_id") == asset_id), None)
        if item:
            item["asset_id"] = None
            item["status"] = "pending"
        await session.delete(row)
        version = next_version(project, "game_asset_plan")
        project.artifacts["game_asset_plan"] = {"version":version,"data":plan}
        touch(project, f"玩家从素材库删除独立素材：{row.name}")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/game-assets/finalize", response_model=Project)
async def finalize_game_assets(project_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if project.current_stage != Stage.THREE_D_DRAFTING:
            raise HTTPException(status_code=409, detail={"code":"invalid_stage","message":"当前阶段不能完成素材清单。"})
        plan = project.artifacts.get("game_asset_plan", {}).get("data", {})
        items = plan.get("items", [])
        if not items or any(item.get("status") != "approved" for item in items):
            raise HTTPException(status_code=409, detail={"code":"assets_not_approved","message":"请先为清单中的每项素材生成图片并逐项确认。"})
        rows = [await session.get(AssetRow, item["asset_id"]) for item in items]
        if any(row is None for row in rows):
            raise HTTPException(status_code=409, detail={"code":"asset_missing","message":"素材库中有文件缺失，请重新生成。"})
        version = next_version(project, "3d")
        variants = [{"id":item["id"],"title":item["name"],"url":row.url,"category":item["category"],"asset_id":row.id} for item,row in zip(items,rows)]
        mode = plan.get("mode") or project.artifacts.get("production_mode", {}).get("data", {}).get("mode", "2d")
        artifact_data = {"mode":mode,"prompt":"独立素材清单","style":plan.get("style"),"selected":variants[0]["id"],"variants":variants}
        if mode == "3d":
            artifact_data.update({"name":"三维游戏素材组","file":variants[0]["url"],"format":"GLB","polygon_count":0,"texture":"PBR 材质","version":version})
        project.artifacts["3d"] = {"version":version,"data":artifact_data}
        project.current_stage = Stage.THREE_D_REVIEW
        touch(project, f"独立素材清单已完成，共 {len(variants)} 项")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/reopen/{kind}", response_model=Project)
async def reopen_artifact(project_id: str, kind: str, session: AsyncSession = Depends(get_session)) -> Project:
    transition=GENERATION_TRANSITIONS.get(kind)
    if not transition: raise HTTPException(status_code=400,detail="unknown_generation_stage")
    drafting,review=transition
    async with session.begin():
        project=await get_project_or_404(session,project_id,for_update=True)
        if project.current_stage != review:
            raise HTTPException(status_code=409,detail={"code":"invalid_stage","expected":review,"actual":project.current_stage})
        project.current_stage=drafting
        touch(project,f"玩家要求重新生成 {kind}；现有版本保留")
        await save_project(session,project)
    return project


@app.post("/projects/{project_id}/revise/{kind}", response_model=Project)
async def revise_stage(project_id: str, kind: str, session: AsyncSession = Depends(get_session)) -> Project:
    ordered = ["knowledge", "concept", "visual", "3d", "music", "logic"]
    drafting = {
        "knowledge": Stage.KNOWLEDGE_SELECTION,
        "concept": Stage.CONCEPT_DRAFTING,
        "visual": Stage.VISUAL_DRAFTING,
        "3d": Stage.THREE_D_DRAFTING,
        "music": Stage.MUSIC_DRAFTING,
        "logic": Stage.LOGIC_DRAFTING,
    }
    if kind not in drafting:
        raise HTTPException(status_code=400, detail={"code":"unknown_stage","message":"这个阶段不能修改。"})
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        if kind != "knowledge" and kind not in project.artifacts:
            raise HTTPException(status_code=409, detail={"code":"artifact_missing","message":"这个阶段还没有可修改的内容。"})
        # 知识阶段没有对应的审批记录；其余阶段只撤销当前阶段的审批。
        # 后续内容和审批保留，供玩家继续回看和单独修改。
        review_stage = None
        if kind != "knowledge":
            project.approvals.pop(kind, None)
            await session.execute(sqlalchemy_delete(ApprovalRow).where(ApprovalRow.project_id == project.id, ApprovalRow.artifact == kind))
            review_stage = APPROVAL_TRANSITIONS[kind][0]
        if project.current_stage != review_stage:
            project.artifacts["local_revision_resume"] = {
                "version": project.versions.get("local_revision_resume", 0) + 1,
                "data": {"kind": kind, "stage": project.current_stage.value},
            }
            project.versions["local_revision_resume"] = project.artifacts["local_revision_resume"]["version"]
        else:
            project.artifacts.pop("local_revision_resume", None)
        project.current_stage = drafting[kind]
        touch(project, f"玩家单独修改 {kind} 阶段；后续内容与审批已保留，完成后将回到原工作位置")
        await save_project(session, project)
    return project


@app.post("/projects/{project_id}/uploads", response_model=Asset)
async def upload_project_file(project_id: str, request: UploadRequest, session: AsyncSession = Depends(get_session)) -> Asset:
    try:
        data = base64.b64decode(request.data_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code":"invalid_base64","message":"附件数据损坏。"}) from exc
    kind, suffix, _ = validate_upload(request.mime, data)
    digest = hashlib.sha256(data).hexdigest()
    path = Path(settings.object_storage_root) / f"{digest}{suffix}"
    if not path.exists():
        path.write_bytes(data)
    metadata: dict[str, Any] = {"source":"chat_upload","mime":request.mime,"original_name":request.name,"bytes":len(data)}
    if kind == "DOCUMENT":
        try:
            metadata["extracted_text"] = data.decode("utf-8-sig")[:20000]
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail={"code":"invalid_text_encoding","message":"文档需要使用 UTF-8 编码。"}) from exc
    row_id = f"upload-{digest[:20]}-{project_id[:7]}"
    async with session.begin():
        await get_project_or_404(session, project_id)
        row = await session.get(AssetRow, row_id)
        if not row:
            row = AssetRow(id=row_id, project_id=project_id, type=kind, name=request.name, url=f"http://127.0.0.1:8000/objects/{path.name}", scope="PROJECT", sha256=digest, metadata_json=metadata)
            session.add(row)
        else:
            row.name = request.name
            row.metadata_json = metadata
        await session.flush()
    return asset_domain(row)


@app.delete("/projects/{project_id}/assets/{asset_id}", response_model=Project)
async def delete_project_asset(project_id: str, asset_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    async with session.begin():
        project = await get_project_or_404(session, project_id, for_update=True)
        row = await session.get(AssetRow, asset_id)
        if not row or row.project_id != project_id:
            raise HTTPException(status_code=404, detail={"code":"asset_missing","message":"素材不存在或不属于当前项目。"})
        if asset_id in project.selected_assets.values():
            raise HTTPException(status_code=409, detail={"code":"asset_in_use","message":"这项素材正在使用，请先选择其他素材。"})
        if row.metadata_json.get("artifact") == "game_asset":
            plan = project.artifacts.get("game_asset_plan", {}).get("data", {})
            item = next((entry for entry in plan.get("items", []) if entry.get("asset_id") == asset_id), None)
            if item:
                item["asset_id"] = None
                item["status"] = "pending"
                version = next_version(project, "game_asset_plan")
                project.artifacts["game_asset_plan"] = {"version":version,"data":plan}
        name = row.name
        await session.delete(row)
        touch(project, f"玩家从项目素材库删除：{name}")
        await save_project(session, project)
    return project


@app.post("/agent/respond", response_model=AgentResponse)
async def agent_respond(request: AgentRequest, budget_choice: str | None = Header(default=None, alias="X-Qiwen-Budget-Choice"), session: AsyncSession = Depends(get_session)) -> AgentResponse:
    provider = get_llm_provider()
    async with session.begin():
        project = await get_project_or_404(session, request.project_id, for_update=True)
        attachments = []
        attachment_names = []
        for asset_id in request.attachment_ids:
            row = await session.get(AssetRow, asset_id)
            if not row or row.project_id != request.project_id or row.type not in {"IMAGE", "DOCUMENT"}:
                raise HTTPException(status_code=404, detail={"code":"attachment_missing","message":"附件不存在或不属于当前项目。"})
            item: dict[str, Any] = {"id":row.id,"name":row.name,"mime":row.metadata_json.get("mime","application/octet-stream"),"type":row.type}
            if row.type == "IMAGE":
                file_path = Path(settings.object_storage_root) / Path(row.url).name
                item["data_url"] = f"data:{item['mime']};base64,{base64.b64encode(file_path.read_bytes()).decode('ascii')}"
            else:
                item["text"] = row.metadata_json.get("extracted_text", "")
            attachments.append(AgentAttachment.model_validate(item)); attachment_names.append(row.name)
        if not request.message.strip() and not attachments:
            raise HTTPException(status_code=422, detail={"code":"empty_message","message":"请输入消息或添加附件。"})
        request = request.model_copy(update={"attachments":attachments})
        shown = request.message.strip() or "请查看我上传的附件。"
        if attachment_names:
            shown += "\n附件：" + "、".join(attachment_names)
        project.conversation_history.append(ConversationMessage(role="user", content=shown))
        touch(project, "玩家向共创助手发送消息")
        await save_project(session, project)
        knowledge = await get_knowledge(session, project.selected_knowledge_id)
        spent = await monthly_api_cost(session)
    if is_real_llm_provider(provider) and spent + 0.10 > settings.api_monthly_budget_cny and budget_choice != "continue":
        raise HTTPException(status_code=402, detail={"code":"monthly_budget_requires_choice", "spent_cny":spent, "budget_cny":settings.api_monthly_budget_cny, "choices":["继续付费", "改用模拟服务", "取消", "推迟"]})
    try:
        response = await provider.respond(request, project, knowledge)
    except ProviderFailure as exc:
        raise HTTPException(status_code=502, detail={"code":exc.code, "message":str(exc), "retryable":exc.retryable}) from exc
    async with session.begin():
        project = await get_project_or_404(session, request.project_id, for_update=True)
        suggestion_id = await create_suggestion(session, project, response.content, "unity_builder" if request.mode == "code" else "game_design")
        response.suggestion_id = suggestion_id
        project.conversation_history.append(
            ConversationMessage(role="assistant", content=response.content, provider=response.provider, suggestion_id=suggestion_id)
        )
        touch(project, f"共创助手通过 {response.provider}/{response.model} 回复")
        await save_project(session, project)
        await record_llm_call(session, project.id, request.mode, response.provider, response.model, response.input_tokens, response.output_tokens, response.cost_cny)
    return response


@app.post("/agent/suggestions/{suggestion_id}/respond")
async def suggestion_response(suggestion_id: str, request: SuggestionResponseRequest, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    async with session.begin():
        result = await respond_to_suggestion(session, suggestion_id, request.action, request.note)
        if result is None:
            raise HTTPException(status_code=404, detail="suggestion_not_found")
        if result == "already_responded":
            raise HTTPException(status_code=409, detail="suggestion_already_responded")
    return {"status":"recorded", "action":request.action}


@app.post("/agent/respond/stream")
async def agent_respond_stream(request: AgentRequest, session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    async def events():
        yield "event: status\ndata: {\"status\":\"thinking\"}\n\n"
        try:
            response = await agent_respond(request, session=session)
            yield f"event: complete\ndata: {json.dumps(response.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        except HTTPException as exc:
            payload = {"status":"error", "code":exc.status_code, "detail":exc.detail}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control":"no-cache", "X-Accel-Buffering":"no"})
