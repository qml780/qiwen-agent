from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .domain import Approval, Asset, ConversationMessage, KnowledgeEntry, Project, Stage
from .mock_data import KNOWLEDGE
from .models import (
    ActivityRow,
    AgentSuggestionRow,
    ApprovalRow,
    ArtifactVersionRow,
    AssetRow,
    ConversationRow,
    KnowledgeRow,
    LLMCallRow,
    OutboxRow,
    ProjectRow,
    ProviderJobRow,
)


DEMO_ASSETS = [
    {"id": "asset-1", "type": "IMAGE", "name": "漆林晨雾", "url": "/demo/lacquer-forest.png", "scope": "PROJECT"},
    {"id": "asset-2", "type": "IMAGE", "name": "匠人作坊", "url": "/demo/lacquer-workshop.png", "scope": "PROJECT"},
    {"id": "asset-3", "type": "IMAGE", "name": "未完成漆碗", "url": "/demo/lacquer-bowl.png", "scope": "LIBRARY"},
    {"id": "asset-4", "type": "3D", "name": "漆碗模型", "url": "/demo/lacquer-bowl-v1.glb", "scope": "PROJECT"},
    {"id": "asset-5", "type": "AUDIO", "name": "作坊静层", "url": "/demo/main-theme.wav", "scope": "PROJECT"},
    {"id": "asset-6", "type": "AUDIO", "name": "采漆晨行", "url": "/demo/harvest-theme.wav", "scope": "LIBRARY"},
    {"id": "curated-color-forest", "type": "IMAGE", "name": "彩色卡通 · 漆林采集关卡", "url": "/curated/彩色卡通-漆林采集关卡.png", "scope": "LIBRARY"},
    {"id": "curated-color-workshop", "type": "IMAGE", "name": "彩色卡通 · 漆艺工坊关卡", "url": "/curated/彩色卡通-漆艺工坊关卡.png", "scope": "LIBRARY"},
    {"id": "curated-color-bowl", "type": "IMAGE", "name": "彩色卡通 · 层漆碗道具", "url": "/curated/彩色卡通-层漆碗道具.png", "scope": "LIBRARY"},
    {"id": "curated-color-apprentice", "type": "IMAGE", "name": "彩色卡通 · 漆艺学徒角色", "url": "/curated/彩色卡通-漆艺学徒角色.png", "scope": "LIBRARY"},
]


def _asset_hash(url: str) -> str | None:
    root = Path(__file__).resolve().parents[3]
    path = root / "apps" / "web" / "public" / url.lstrip("/")
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def seed_reference_data(session: AsyncSession) -> None:
    for entry in KNOWLEDGE:
        values = {
            "id": entry.id,
            "category": entry.category,
            "title": entry.title,
            "payload": entry.model_dump(mode="json"),
            "updated_at": datetime.now(UTC),
        }
        statement = pg_insert(KnowledgeRow).values(**values).on_conflict_do_update(
            index_elements=[KnowledgeRow.id],
            set_={"category": values["category"], "title": values["title"], "payload": values["payload"], "updated_at": values["updated_at"]},
        )
        await session.execute(statement)
    for item in DEMO_ASSETS:
        if item["scope"] != "LIBRARY":
            continue
        values = {**item, "project_id": None, "sha256": _asset_hash(item["url"]), "metadata_json": {"provenance": "curated_demo"}}
        await session.execute(pg_insert(AssetRow).values(**values).on_conflict_do_update(
            index_elements=[AssetRow.id],
            set_={
                AssetRow.name: values["name"],
                AssetRow.url: values["url"],
                AssetRow.sha256: values["sha256"],
                AssetRow.metadata_json: values["metadata_json"],
            },
        ))
    await session.commit()


async def attach_project_assets(session: AsyncSession, project_id: str) -> None:
    for item in DEMO_ASSETS:
        if item["scope"] != "PROJECT":
            continue
        values = {
            **item,
            "id": f"{project_id}:{item['id']}",
            "project_id": project_id,
            "sha256": _asset_hash(item["url"]),
            "metadata_json": {"provenance": "curated_demo", "source_id": item["id"]},
        }
        await session.execute(pg_insert(AssetRow).values(**values).on_conflict_do_nothing(index_elements=[AssetRow.id]))


async def list_knowledge(session: AsyncSession) -> list[KnowledgeEntry]:
    rows = (await session.scalars(select(KnowledgeRow).order_by(KnowledgeRow.created_at, KnowledgeRow.id))).all()
    return [KnowledgeEntry.model_validate(row.payload) for row in rows]


async def get_knowledge(session: AsyncSession, knowledge_id: str) -> KnowledgeEntry | None:
    row = await session.get(KnowledgeRow, knowledge_id)
    return KnowledgeEntry.model_validate(row.payload) if row else None


async def list_assets(session: AsyncSession, project_id: str | None) -> list[Asset]:
    condition = AssetRow.project_id.is_(None) if not project_id else or_(AssetRow.project_id == project_id, AssetRow.project_id.is_(None))
    rows = (await session.scalars(select(AssetRow).where(condition).order_by(AssetRow.scope, AssetRow.created_at, AssetRow.id))).all()
    return [Asset(
        id=row.id,
        project_id=row.project_id,
        type=row.type,
        name=row.name,
        url=row.url,
        scope=row.scope,
        sha256=row.sha256,
        metadata=row.metadata_json,
        created_at=row.created_at,
    ) for row in rows]


async def use_asset_in_project(session: AsyncSession, project_id: str, asset_id: str) -> tuple[str, str, str] | None:
    source = await session.get(AssetRow, asset_id)
    if source is None or source.project_id not in {None, project_id}:
        return None
    if source.project_id == project_id:
        target_id = source.id
    else:
        target_id = f"{project_id}:library:{source.id}"
        values = {
            "id": target_id,
            "project_id": project_id,
            "type": source.type,
            "name": source.name,
            "url": source.url,
            "scope": "PROJECT",
            "sha256": source.sha256,
            "metadata_json": {**(source.metadata_json or {}), "source_id": source.id, "selected_from_library": True},
        }
        await session.execute(pg_insert(AssetRow).values(**values).on_conflict_do_update(
            index_elements=[AssetRow.id],
            set_={AssetRow.url: values["url"], AssetRow.sha256: values["sha256"], AssetRow.metadata_json: values["metadata_json"]},
        ))
        await session.flush()
    project_assets = (await session.scalars(select(AssetRow).where(
        AssetRow.project_id == project_id,
        AssetRow.type == source.type,
    ))).all()
    for item in project_assets:
        item.metadata_json = {**(item.metadata_json or {}), "selected": item.id == target_id}
    return target_id, source.type, source.name


async def load_project(session: AsyncSession, project_id: str, *, for_update: bool = False) -> Project | None:
    statement = select(ProjectRow).where(ProjectRow.id == project_id)
    if for_update:
        statement = statement.with_for_update()
    row = await session.scalar(statement)
    if not row:
        return None

    artifact_rows = (await session.scalars(
        select(ArtifactVersionRow).where(ArtifactVersionRow.project_id == project_id).order_by(ArtifactVersionRow.kind, ArtifactVersionRow.version)
    )).all()
    artifacts: dict[str, dict] = {}
    versions: dict[str, int] = {}
    for artifact in artifact_rows:
        versions[artifact.kind] = max(versions.get(artifact.kind, 0), artifact.version)
        artifacts[artifact.kind] = {"version": artifact.version, "data": artifact.data}

    approval_rows = (await session.scalars(
        select(ApprovalRow).where(ApprovalRow.project_id == project_id).order_by(ApprovalRow.approved_at)
    )).all()
    approvals = {
        approval.artifact: Approval(id=approval.id, artifact=approval.artifact, version=approval.version, approved_at=approval.approved_at, stage=approval.stage, status=approval.status, approved_by=approval.approved_by, comment=approval.comment)
        for approval in approval_rows
    }
    messages = (await session.scalars(
        select(ConversationRow).where(ConversationRow.project_id == project_id).order_by(ConversationRow.created_at, ConversationRow.id)
    )).all()
    suggestion_rows = (await session.scalars(
        select(AgentSuggestionRow).where(AgentSuggestionRow.project_id == project_id)
    )).all()
    suggestion_responses = {item.id: item.player_response for item in suggestion_rows}
    activities = (await session.scalars(
        select(ActivityRow).where(ActivityRow.project_id == project_id).order_by(ActivityRow.sequence)
    )).all()
    selected_asset_rows = (await session.scalars(
        select(AssetRow).where(AssetRow.project_id == project_id)
    )).all()
    selected_assets = {
        item.type: item.id for item in selected_asset_rows if (item.metadata_json or {}).get("selected") is True
    }
    return Project(
        id=row.id,
        title=row.title,
        selected_knowledge_id=row.selected_knowledge_id,
        current_stage=Stage(row.current_stage),
        player_idea=row.player_idea,
        original_player_idea=row.original_player_idea,
        artifacts=artifacts,
        selected_assets=selected_assets,
        approvals=approvals,
        versions=versions,
        conversation_history=[ConversationMessage(id=item.id, role=item.role, content=item.content, provider=item.provider, suggestion_id=item.suggestion_id, suggestion_response=suggestion_responses.get(item.suggestion_id), created_at=item.created_at) for item in messages],
        activity_log=[item.message for item in activities],
        progress=row.progress,
        revision=row.revision,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_projects(session: AsyncSession, *, limit: int | None = None, offset: int = 0) -> list[Project]:
    statement = select(ProjectRow.id).order_by(ProjectRow.updated_at.desc()).offset(offset)
    if limit is not None:
        statement = statement.limit(limit)
    project_ids = (await session.scalars(statement)).all()
    projects: list[Project] = []
    for project_id in project_ids:
        project = await load_project(session, project_id)
        if project:
            projects.append(project)
    return projects


async def save_project(session: AsyncSession, project: Project) -> None:
    project.progress = round(len(project.approvals) / 5 * 100)
    project.revision += 1
    project_values = {
        "id": project.id,
        "title": project.title,
        "selected_knowledge_id": project.selected_knowledge_id,
        "current_stage": project.current_stage.value,
        "player_idea": project.player_idea,
        "original_player_idea": project.original_player_idea,
        "progress": project.progress,
        "revision": project.revision,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    await session.execute(pg_insert(ProjectRow).values(**project_values).on_conflict_do_update(
        index_elements=[ProjectRow.id],
        set_={key: value for key, value in project_values.items() if key not in {"id", "created_at"}},
    ))

    for message in project.conversation_history:
        await session.execute(pg_insert(ConversationRow).values(
            id=message.id,
            project_id=project.id,
            role=message.role,
            content=message.content,
            provider=message.provider,
            suggestion_id=message.suggestion_id,
            created_at=message.created_at,
        ).on_conflict_do_nothing(index_elements=[ConversationRow.id]))

    for kind, artifact in project.artifacts.items():
        artifact_id = str(uuid5(NAMESPACE_URL, f"qiwen:{project.id}:{kind}:{artifact['version']}"))
        await session.execute(pg_insert(ArtifactVersionRow).values(
            id=artifact_id,
            project_id=project.id,
            kind=kind,
            version=artifact["version"],
            data=artifact["data"],
        ).on_conflict_do_nothing(constraint="uq_artifact_version"))

    for approval in project.approvals.values():
        await session.execute(pg_insert(ApprovalRow).values(
            id=approval.id,
            project_id=project.id,
            artifact=approval.artifact,
            version=approval.version,
            approved_at=approval.approved_at,
            stage=approval.stage or approval.artifact,
            status=approval.status,
            approved_by=approval.approved_by,
            comment=approval.comment,
        ).on_conflict_do_nothing(constraint="uq_approval_version"))

    for sequence, message in enumerate(project.activity_log, start=1):
        await session.execute(pg_insert(ActivityRow).values(
            project_id=project.id,
            sequence=sequence,
            message=message,
        ).on_conflict_do_nothing(constraint="uq_activity_sequence"))
        event_key = f"project:{project.id}:activity:{sequence}"
        await session.execute(pg_insert(OutboxRow).values(
            id=str(uuid5(NAMESPACE_URL, event_key)),
            project_id=project.id,
            event_type="project.activity_recorded",
            payload={"sequence": sequence, "message": message},
            idempotency_key=event_key,
        ).on_conflict_do_nothing(index_elements=[OutboxRow.idempotency_key]))


async def record_provider_job(session: AsyncSession, project: Project, kind: str, version: int, response: dict, provider: str = "mock") -> None:
    key = f"{provider}:{project.id}:{kind}:{version}"
    await session.execute(pg_insert(ProviderJobRow).values(
        id=str(uuid5(NAMESPACE_URL, key)),
        project_id=project.id,
        provider=provider,
        kind=kind,
        status="completed",
        idempotency_key=key,
        request_payload={"kind": kind, "version": version},
        response_payload=response,
        cost_cny=float(response.get("actual_cost_cny",0)),
    ).on_conflict_do_nothing(index_elements=[ProviderJobRow.idempotency_key]))


async def record_generated_assets(session: AsyncSession, project: Project, kind: str, version: int, artifact: dict) -> None:
    if kind == "visual": urls=[item["url"] for item in artifact.get("variants",[])]
    elif kind == "3d": urls=[item["url"] for item in artifact.get("variants",[])] if artifact.get("mode") == "2d" else [artifact.get("file")]
    elif kind == "music": urls=[item["url"] for item in artifact.get("tracks",[])]
    else: return
    ingested={item.get("url"):item for item in artifact.get("ingested",[]) if isinstance(item,dict)}
    asset_type="IMAGE" if kind == "3d" and artifact.get("mode") == "2d" else {"visual":"IMAGE","3d":"3D","music":"AUDIO"}[kind]
    for index,url in enumerate(item for item in urls if item):
        metadata=ingested.get(url,{})
        asset_id=str(uuid5(NAMESPACE_URL,f"qiwen:{project.id}:{kind}:{version}:{index}"))
        values={"id":asset_id,"project_id":project.id,"type":asset_type,"name":f"{kind} 第 {version} 版 · {index+1}","url":url,"scope":"PROJECT","sha256":metadata.get("sha256"),"metadata_json":{"artifact":kind,"version":version,"provider":artifact.get("provider"),**metadata}}
        await session.execute(pg_insert(AssetRow).values(**values).on_conflict_do_update(index_elements=[AssetRow.id],set_={AssetRow.url:url,AssetRow.sha256:values["sha256"],AssetRow.metadata_json:values["metadata_json"]}))


async def persistence_counts(session: AsyncSession, project_id: str) -> dict[str, int]:
    tables = {
        "chat": ConversationRow,
        "assets": AssetRow,
        "versions": ArtifactVersionRow,
        "approvals": ApprovalRow,
        "activity": ActivityRow,
        "outbox": OutboxRow,
        "suggestions": AgentSuggestionRow,
        "llm_calls": LLMCallRow,
    }
    result: dict[str, int] = {}
    for name, model in tables.items():
        result[name] = int(await session.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0)
    return result


async def record_llm_call(
    session: AsyncSession,
    project_id: str,
    task: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_cny: float,
    *,
    status: str = "completed",
    request_id: str | None = None,
    error_code: str | None = None,
) -> None:
    await session.execute(pg_insert(LLMCallRow).values(
        id=str(uuid4()), project_id=project_id, provider=provider, model=model,
        task=task, status=status, request_id=request_id, input_tokens=input_tokens,
        output_tokens=output_tokens, cost_cny=cost_cny, prompt_version="m3-v1",
        error_code=error_code,
    ))


async def monthly_llm_cost(session: AsyncSession) -> float:
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    value = await session.scalar(select(func.coalesce(func.sum(LLMCallRow.cost_cny), 0)).where(LLMCallRow.created_at >= start))
    return float(value or 0)


async def monthly_api_cost(session: AsyncSession) -> float:
    """返回已确认的真实支出；不得把估算价累计成真实扣费。"""
    return float(settings.confirmed_monthly_spend_cny)


async def monthly_estimated_cost(session: AsyncSession) -> float:
    """历史估算仅用于参考，不参与预算拦截。"""
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    llm = await session.scalar(select(func.coalesce(func.sum(LLMCallRow.cost_cny), 0)).where(LLMCallRow.created_at >= start))
    assets = await session.scalar(select(func.coalesce(func.sum(ProviderJobRow.cost_cny), 0)).where(ProviderJobRow.created_at >= start))
    return float(llm or 0) + float(assets or 0)


async def create_suggestion(session: AsyncSession, project: Project, content: str, agent_type: str = "game_design") -> str:
    suggestion_id = str(uuid4())
    await session.execute(pg_insert(AgentSuggestionRow).values(
        id=suggestion_id, project_id=project.id, agent_type=agent_type,
        content=content, related_stage=project.current_stage.value,
    ))
    return suggestion_id


async def respond_to_suggestion(session: AsyncSession, suggestion_id: str, action: str, note: str) -> str | None:
    row = await session.get(AgentSuggestionRow, suggestion_id)
    if not row:
        return None
    if row.player_response:
        return "already_responded"
    row.player_response = action
    row.response_note = note
    row.responded_at = datetime.now(UTC)
    return "updated"
