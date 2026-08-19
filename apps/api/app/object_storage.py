from __future__ import annotations

import hashlib
import base64
import ipaddress
import io
import json
import mimetypes
import socket
import struct
import wave
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import settings

MAX_BYTES = {"visual": 20 * 1024 * 1024, "3d": 200 * 1024 * 1024, "music": 256 * 1024 * 1024}
EXTENSIONS = {"visual": {".png", ".jpg", ".jpeg", ".webp"}, "3d": {".glb"}, "music": {".wav", ".mp3", ".m4a", ".aac", ".flac"}}


class ObjectValidationError(Exception): pass


def _validate_bytes(kind: str, data: bytes) -> None:
    if not data or len(data) > MAX_BYTES[kind]: raise ObjectValidationError("文件为空或超过大小限制")
    valid = {
        "visual": data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")) or (data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
        "3d": data.startswith(b"glTF"),
        "music": (data.startswith(b"RIFF") and data[8:12] == b"WAVE") or data.startswith((b"ID3", b"fLaC")) or data[:2] in {b"\xff\xfb", b"\xff\xf3"},
    }[kind]
    if not valid: raise ObjectValidationError(f"{kind} 文件签名不合法")


def _inspect(kind: str, data: bytes) -> dict[str, int | float]:
    if kind == "visual" and data.startswith(b"\x89PNG") and len(data) >= 24:
        width,height=struct.unpack(">II",data[16:24]); return {"width":width,"height":height}
    if kind == "3d":
        if len(data) < 20: raise ObjectValidationError("GLB 头不完整")
        _,version,total=struct.unpack("<4sII",data[:12])
        if version != 2 or total != len(data): raise ObjectValidationError("GLB 版本或长度不合法")
        chunk_length,chunk_type=struct.unpack("<II",data[12:20])
        if chunk_type != 0x4E4F534A: raise ObjectValidationError("GLB 缺少 JSON chunk")
        document=json.loads(data[20:20+chunk_length].decode("utf-8").rstrip(" \x00"))
        triangles=0
        accessors=document.get("accessors",[])
        for mesh in document.get("meshes",[]):
            for primitive in mesh.get("primitives",[]):
                index=primitive.get("indices")
                if isinstance(index,int) and index < len(accessors): triangles += int(accessors[index].get("count",0)) // 3
        return {"polygon_count":triangles,"mesh_count":len(document.get("meshes",[]))}
    if kind == "music" and data.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(data),"rb") as audio:
                return {"duration":round(audio.getnframes()/audio.getframerate(),3),"sample_rate":audio.getframerate(),"channels":audio.getnchannels()}
        except wave.Error:
            channels = sample_rate = byte_rate = data_bytes = 0
            offset = 12
            while offset + 8 <= len(data):
                chunk_id = data[offset:offset + 4]
                chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
                payload = offset + 8
                if chunk_id == b"fmt " and chunk_size >= 16:
                    channels = struct.unpack_from("<H", data, payload + 2)[0]
                    sample_rate = struct.unpack_from("<I", data, payload + 4)[0]
                    byte_rate = struct.unpack_from("<I", data, payload + 8)[0]
                elif chunk_id == b"data":
                    data_bytes = min(chunk_size, len(data) - payload)
                    break
                offset = payload + chunk_size + (chunk_size % 2)
            if not channels or not sample_rate or not byte_rate or not data_bytes:
                raise ObjectValidationError("无法读取 WAV 音频信息")
            return {"duration":round(data_bytes/byte_rate,3),"sample_rate":sample_rate,"channels":channels}
    return {}


def _safe_remote(url: str) -> None:
    parsed=urlparse(url)
    if parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port == 8001:
        return
    if parsed.scheme != "https" or not parsed.hostname: raise ObjectValidationError("只允许 HTTPS Provider 输出")
    for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        address=ipaddress.ip_address(item[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved: raise ObjectValidationError("拒绝访问本地或保留地址")


async def ingest_url(kind: str, url: str) -> dict[str, str | int | float]:
    if url.startswith("data:audio/wav;base64,"):
        if kind != "music": raise ObjectValidationError("声音数据只能作为音乐素材保存")
        try:
            data = base64.b64decode(url.split(",", 1)[1], validate=True)
        except ValueError as exc:
            raise ObjectValidationError("base64 声音数据不合法") from exc
        _validate_bytes(kind, data)
        digest = hashlib.sha256(data).hexdigest(); root = Path(settings.object_storage_root); root.mkdir(parents=True, exist_ok=True)
        path = root / f"{digest}.wav"
        if not path.exists(): path.write_bytes(data)
        return {"url":f"http://127.0.0.1:8000/objects/{path.name}","sha256":digest,"bytes":len(data),"mime":"audio/wav",**_inspect(kind,data)}
    if url.startswith("data:image/"):
        if kind != "visual" or ";base64," not in url:
            raise ObjectValidationError("只允许图片 Provider 使用 base64 data URL")
        header, encoded = url.split(",", 1)
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ObjectValidationError("base64 图片数据不合法") from exc
        _validate_bytes(kind, data)
        mime = header[5:].split(";", 1)[0]
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
        digest = hashlib.sha256(data).hexdigest(); root = Path(settings.object_storage_root); root.mkdir(parents=True, exist_ok=True)
        path = root / f"{digest}{suffix}"
        if not path.exists(): path.write_bytes(data)
        return {"url":f"http://127.0.0.1:8000/objects/{path.name}","sha256":digest,"bytes":len(data),"mime":mime,**_inspect(kind,data)}
    if url.startswith(("/demo/", "/curated/")):
        candidates=[Path(__file__).resolve().parents[3] / "apps" / "web" / "public" / url.lstrip("/"), Path("E:/漆vr游戏/apps/web/public") / url.lstrip("/")]
        path=next((item for item in candidates if item.is_file()),None)
        if not path: raise ObjectValidationError("模拟资产不存在")
        data=path.read_bytes(); _validate_bytes(kind,data)
        return {"url":url,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),"mime":mimetypes.guess_type(path.name)[0] or "application/octet-stream",**_inspect(kind,data)}
    _safe_remote(url)
    async with httpx.AsyncClient(timeout=120,follow_redirects=False) as client:
        response=await client.get(url,headers={"Accept":"*/*"}); response.raise_for_status(); data=response.content
    _validate_bytes(kind,data)
    suffix=Path(urlparse(url).path).suffix.lower()
    if suffix not in EXTENSIONS[kind]: suffix={"visual":".png","3d":".glb","music":".wav"}[kind]
    digest=hashlib.sha256(data).hexdigest(); root=Path(settings.object_storage_root); root.mkdir(parents=True,exist_ok=True)
    path=root / f"{digest}{suffix}"
    if not path.exists(): path.write_bytes(data)
    return {"url":f"http://127.0.0.1:8000/objects/{path.name}","sha256":digest,"bytes":len(data),"mime":mimetypes.guess_type(path.name)[0] or "application/octet-stream",**_inspect(kind,data)}


async def ingest_urls(kind: str, urls: list[str]) -> list[dict[str, str | int | float]]:
    return [await ingest_url(kind,url) for url in urls]
