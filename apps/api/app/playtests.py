from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PlaytestSessionRow


STATUS_LABELS = {
    "playing": "首次试玩中",
    "feedback": "已记录反馈",
    "revision_preview": "等待批准修改",
    "replaying": "再次试玩中",
    "awaiting_final_approval": "等待玩家完成确认",
    "completed": "迭代已完成",
    "failed": "迭代失败",
}


def serialize_playtest(row: PlaytestSessionRow) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "build_job_id": row.build_job_id,
        "logic_version": row.logic_version,
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "initial_feedback": row.initial_feedback,
        "initial_rating": row.initial_rating,
        "revision_change_id": row.revision_change_id,
        "final_feedback": row.final_feedback,
        "final_rating": row.final_rating,
        "evidence": row.evidence,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


async def list_playtests(session: AsyncSession, project_id: str) -> list[dict]:
    rows = (await session.scalars(select(PlaytestSessionRow).where(PlaytestSessionRow.project_id == project_id).order_by(PlaytestSessionRow.created_at.desc()))).all()
    return [serialize_playtest(row) for row in rows]


def update_evidence(row: PlaytestSessionRow, **items: object) -> None:
    row.evidence = {**(row.evidence or {}), **items}
    row.updated_at = datetime.now(UTC)
