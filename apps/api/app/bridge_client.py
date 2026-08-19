from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from .config import settings


class LocalBridgeError(RuntimeError):
    pass


def _token() -> str:
    path = Path(settings.local_bridge_token_file)
    if path.drive.upper() not in {"D:", "E:"}:
        raise LocalBridgeError("本地桥接令牌路径必须位于 D 盘或 E 盘")
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise LocalBridgeError("本地桥接尚未启动，令牌文件不存在") from error
    if len(token) < 32:
        raise LocalBridgeError("本地桥接令牌无效")
    return token


async def bridge_health() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(f"{settings.local_bridge_url}/health")
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise LocalBridgeError("无法连接漆问本地桥接") from error


async def start_unity_build(payload: dict[str, str]) -> dict[str, Any]:
    return await _bridge_action("/build", payload, timeout=10)


async def bridge_job(job_id: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(f"{settings.local_bridge_url}/jobs/{job_id}")
        if response.status_code == 404:
            raise LocalBridgeError("找不到 Unity 构建任务")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise LocalBridgeError("读取 Unity 构建状态失败") from error


async def retry_bridge_job(job_id: str) -> dict[str, Any]:
    return await _bridge_action(f"/jobs/{job_id}/retry", {})


async def takeover_bridge_job(job_id: str) -> dict[str, Any]:
    return await _bridge_action(f"/jobs/{job_id}/takeover", {})


async def apply_co_creation(payload: dict[str, Any]) -> dict[str, Any]:
    return await _bridge_action("/co-creation/apply", {key: value for key, value in payload.items() if value is not None}, timeout=75)


async def start_playtest_in_unity() -> dict[str, Any]:
    return await _bridge_action("/playtest/play", {}, timeout=20)


async def _bridge_action(path: str, payload: dict[str, Any], timeout: float = 10) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(
                f"{settings.local_bridge_url}{path}",
                headers={"X-QIWEN-Bridge-Token": _token()},
                json=payload,
            )
        if response.status_code >= 400:
            detail = response.json().get("detail", "本地桥接拒绝操作")
            raise LocalBridgeError(str(detail))
        return response.json()
    except httpx.HTTPError as error:
        raise LocalBridgeError("向本地桥接提交操作失败") from error


async def stream_bridge_events(job_id: str, after: int = 0) -> AsyncIterator[bytes]:
    """原样转发桥接 SSE；浏览器断线后用 after 回放缺失事件。"""
    try:
        async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
            async with client.stream(
                "GET", f"{settings.local_bridge_url}/jobs/{job_id}/events", params={"after": max(after, 0)}
            ) as response:
                if response.status_code == 404:
                    raise LocalBridgeError("找不到 Unity 构建任务")
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
    except httpx.HTTPError as error:
        raise LocalBridgeError("Unity 实时事件连接中断") from error
