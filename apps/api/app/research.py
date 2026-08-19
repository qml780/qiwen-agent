from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import (
    ActivityRow, AgentSuggestionRow, ApprovalRow, ArtifactVersionRow, ConversationRow,
    PlaytestSessionRow, ProviderJobRow, ResearchExportRow, UnityChangeRow,
)


def anonymous_project_id(project_id: str) -> str:
    return hashlib.sha256(f"qiwen-research:{project_id}".encode()).hexdigest()[:16]


def event(event_id: str, event_type: str, label: str, time: datetime, source: str, details: dict) -> dict:
    return {"id": event_id, "type": event_type, "label": label, "time": time.isoformat(), "source": source, "details": details}


KIND_LABELS = {"concept": "游戏概念", "visual": "视觉", "3d": "三维资产", "music": "音乐", "logic": "游戏逻辑"}
FORMAT_LABELS = {"json": "结构化数据", "csv": "表格数据"}


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, kind)


def localized_activity(message: str) -> str:
    localized = message.replace("mock 服务", "精选模拟服务").replace("deepseek 服务", "深度求索服务")
    localized = localized.replace("Agent", "智能助手").replace("Play Mode", "运行模式")
    localized = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "匿名记录", localized, flags=re.IGNORECASE)
    for kind, label in KIND_LABELS.items():
        localized = localized.replace(f" {kind} ", f" {label} ").replace(f"{kind} 第", f"{label} 第")
    return localized


async def research_snapshot(session: AsyncSession, project_id: str) -> dict:
    activities = (await session.scalars(select(ActivityRow).where(ActivityRow.project_id == project_id))).all()
    conversations = (await session.scalars(select(ConversationRow).where(ConversationRow.project_id == project_id))).all()
    suggestions = (await session.scalars(select(AgentSuggestionRow).where(AgentSuggestionRow.project_id == project_id))).all()
    artifacts = (await session.scalars(select(ArtifactVersionRow).where(ArtifactVersionRow.project_id == project_id))).all()
    approvals = (await session.scalars(select(ApprovalRow).where(ApprovalRow.project_id == project_id))).all()
    provider_jobs = (await session.scalars(select(ProviderJobRow).where(ProviderJobRow.project_id == project_id))).all()
    unity_changes = (await session.scalars(select(UnityChangeRow).where(UnityChangeRow.project_id == project_id))).all()
    playtests = (await session.scalars(select(PlaytestSessionRow).where(PlaytestSessionRow.project_id == project_id))).all()
    exports = (await session.scalars(select(ResearchExportRow).where(ResearchExportRow.project_id == project_id))).all()

    timeline: list[dict] = []
    for item in activities:
        timeline.append(event(f"activity-{item.id}", "project_event", localized_activity(item.message), item.created_at, "项目", {"sequence": item.sequence}))
    for item in conversations:
        timeline.append(event(item.id, "conversation", "玩家消息" if item.role == "user" else "共创助手消息", item.created_at, "对话", {"role": item.role, "provider": item.provider, "content_length": len(item.content), "suggestion_id": item.suggestion_id}))
    for item in suggestions:
        decision = item.player_response or "pending"
        timeline.append(event(item.id, "suggestion", "智能助手建议", item.created_at, "建议", {"agent_type": item.agent_type, "stage": item.related_stage, "decision": decision, "content_length": len(item.content), "response_note_length": len(item.response_note or "")}))
    for item in artifacts:
        details = {"artifact": item.kind, "version": item.version}
        if item.kind == "concept": details["knowledge_alignment_score"] = item.data.get("alignment", {}).get("score")
        timeline.append(event(item.id, "revision", f"{kind_label(item.kind)} 第 {item.version} 版", item.created_at, "版本", details))
    for item in approvals:
        timeline.append(event(item.id, "approval", f"批准{kind_label(item.artifact)}第 {item.version} 版", item.approved_at, "审批", {"stage": item.stage or item.artifact, "artifact": item.artifact, "version": item.version, "status": item.status, "approved_by": item.approved_by, "comment_length": len(item.comment or "")}))
    for item in provider_jobs:
        timeline.append(event(item.id, "asset_generation", f"{kind_label(item.kind)}生成", item.created_at, "生成服务", {"provider": item.provider, "kind": item.kind, "status": item.status, "cost_cny": float(item.cost_cny)}))
    for item in unity_changes:
        safe_receipt = item.receipt_payload or {}
        timeline.append(event(item.id, "unity_action", {"add_asset": "加入场景资产", "adjust_asset": "调整场景资产", "request_interaction": "配置场景交互", "undo": "撤销 Unity 变更"}.get(item.action, "Unity 变更"), item.created_at, "Unity", {"action": item.action, "status": item.status, "object_name": item.request_payload.get("objectName"), "has_checkpoint": bool(item.checkpoint_path), "compiler_errors": safe_receipt.get("compilerErrors"), "play_mode": safe_receipt.get("playMode")}))
    for item in playtests:
        timeline.append(event(item.id, "playtest", "试玩迭代", item.created_at, "试玩", {"status": item.status, "build_job_id": item.build_job_id, "initial_logic_version": item.logic_version, "revised_logic_version": item.evidence.get("proposed_logic_version"), "initial_rating": item.initial_rating, "final_rating": item.final_rating, "initial_feedback_length": len(item.initial_feedback or ""), "final_feedback_length": len(item.final_feedback or ""), "compile_errors": item.evidence.get("compile_errors"), "play_again": item.evidence.get("play_again")}))
    for item in exports:
        timeline.append(event(item.id, "research_export", f"导出匿名研究数据（{FORMAT_LABELS.get(item.format, item.format)}）", item.created_at, "研究", {"format": item.format, "event_count": item.event_count, "sha256_prefix": item.sha256[:12]}))
    timeline.sort(key=lambda item: (item["time"], item["id"]))

    decisions = Counter(item.player_response or "pending" for item in suggestions)
    responded = sum(decisions[key] for key in ["accepted", "rejected", "modified", "discuss"])
    version_counts = Counter(item.kind for item in artifacts)
    revision_count = sum(max(count - 1, 0) for count in version_counts.values())
    metrics = {
        "timeline_events": len(timeline),
        "conversation_events": len(conversations),
        "suggestions": {"total": len(suggestions), "responded": responded, "accepted": decisions["accepted"], "rejected": decisions["rejected"], "modified": decisions["modified"], "discuss": decisions["discuss"], "pending": decisions["pending"], "acceptance_rate": round(decisions["accepted"] / responded, 4) if responded else None},
        "revision_count": revision_count,
        "version_counts": dict(sorted(version_counts.items())),
        "asset_generations": sum(1 for item in provider_jobs if item.kind in {"visual", "3d", "music"}),
        "asset_selections": sum(1 for item in unity_changes if item.action == "add_asset" and item.status in {"applied", "undone"}),
        "approval_events": len(approvals),
        "playtest_iterations": sum(1 for item in playtests if item.status == "completed"),
        "knowledge_alignment_versions": sum(1 for item in artifacts if item.kind == "concept" and "alignment" in item.data),
        "game_design_versions": version_counts["concept"] + version_counts["logic"],
        "research_exports": len(exports),
    }
    approval_history = [{"approval_id": item.id, "stage": item.stage or item.artifact, "artifact": item.artifact, "artifact_version": item.version, "status": item.status, "approved_by": item.approved_by, "approved_at": item.approved_at.isoformat(), "comment": item.comment} for item in sorted(approvals, key=lambda row: row.approved_at)]
    return {"schema_version": 1, "anonymized_project_id": anonymous_project_id(project_id), "generated_at": datetime.now(UTC).isoformat(), "metric_definitions": {"suggestion_acceptance_rate": "accepted / responded；responded 包含接受、拒绝、修改后接受和继续讨论", "revision_count": "各版本化 artifact 超出首版的版本数量之和", "playtest_iterations": "状态为 completed 的试玩会话数量", "asset_selections": "已应用或后来撤销的 add_asset Unity 变更数量"}, "metrics": metrics, "approval_history": approval_history, "timeline": timeline}


async def create_research_export(session: AsyncSession, project_id: str, export_format: str) -> tuple[Path, ResearchExportRow]:
    snapshot = await research_snapshot(session, project_id)
    root = Path(settings.research_export_root)
    if root.drive.upper() not in {"D:", "E:"}:
        raise ValueError("研究导出目录必须位于 D 盘或 E 盘")
    root.mkdir(parents=True, exist_ok=True)
    export_id = str(uuid4())
    if export_format == "json":
        content = json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")
        suffix = "json"
    elif export_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=["anonymized_project_id", "event_id", "time", "type", "label", "source", "details_json"])
        writer.writeheader()
        for item in snapshot["timeline"]:
            writer.writerow({"anonymized_project_id": snapshot["anonymized_project_id"], "event_id": item["id"], "time": item["time"], "type": item["type"], "label": item["label"], "source": item["source"], "details_json": json.dumps(item["details"], ensure_ascii=False, separators=(",", ":"))})
        content = ("\ufeff" + output.getvalue()).encode("utf-8")
        suffix = "csv"
    else:
        raise ValueError("导出格式只支持 json 或 csv")
    path = root / f"漆问研究导出-{snapshot['anonymized_project_id']}-{export_id[:8]}.{suffix}"
    path.write_bytes(content)
    row = ResearchExportRow(id=export_id, project_id=project_id, format=export_format, anonymized_project_id=snapshot["anonymized_project_id"], event_count=len(snapshot["timeline"]), sha256=hashlib.sha256(content).hexdigest(), path=str(path), created_at=datetime.now(UTC))
    session.add(row)
    await session.flush()
    return path, row
