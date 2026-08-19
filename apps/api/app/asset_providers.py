from __future__ import annotations

import asyncio, base64, hashlib, io, json, logging, math, os, re, struct, wave
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse
import mimetypes
from typing import Any
import httpx
from pydantic import BaseModel, Field

from .config import settings

logger = logging.getLogger(__name__)


class AssetProviderError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message); self.code, self.retryable = code, retryable


def _redact_provider_message(message: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", message)


class AssetGenerationRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=800)
    reference_urls: list[str] = Field(default_factory=list, max_length=10)
    mood: str = "专注、清晨、手作"
    tempo: int = Field(default=76, ge=30, le=240)
    duration: int = Field(default=60, ge=5, le=600)
    loop: bool = True
    sound_layers: list[dict[str, Any]] = Field(default_factory=list, max_length=6)
    cue_names: list[str] = Field(default_factory=list, max_length=8)


class ProviderTask(BaseModel):
    provider: str; kind: str; task_id: str; status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    estimated_cost_cny: float = 0


class AssetProvider(ABC):
    kind: str; name: str
    def validate(self, request: AssetGenerationRequest):
        if not request.prompt.strip(): raise AssetProviderError("invalid_prompt", "提示词不能为空")
    @abstractmethod
    async def submit(self, request: AssetGenerationRequest) -> ProviderTask: ...
    @abstractmethod
    async def poll(self, task: ProviderTask) -> ProviderTask: ...
    async def cancel(self, task: ProviderTask) -> ProviderTask:
        return task if task.status in {"completed","failed","cancelled"} else task.model_copy(update={"status":"cancelled"})


class MockAssetProvider(AssetProvider):
    def __init__(self, kind: str): self.kind, self.name = kind, f"mock-{kind}"
    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request)
        fixtures={"image":{"urls":["/demo/lacquer-forest.png","/demo/lacquer-workshop.png","/demo/lacquer-bowl.png","/demo/lacquer-house.png"],"mime":"image/png"},"3d":{"urls":["/demo/lacquer-bowl-v1.glb"],"mime":"model/gltf-binary","polygon_count":960},"music":{"urls":["/demo/main-theme.wav","/demo/harvest-theme.wav"],"mime":"audio/wav","duration":request.duration}}
        return ProviderTask(provider=self.name,kind=self.kind,task_id=f"mock-{self.kind}",status="completed",payload={**fixtures[self.kind],"prompt":request.prompt,"provenance":"curated_demo","rights":"internal_demo_only"})
    async def poll(self, task: ProviderTask) -> ProviderTask: return task


class CuratedImageFallbackProvider(AssetProvider):
    """Keeps the visual workflow usable when the external image endpoint is down."""
    kind, name = "image", "curated-image-fallback"

    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request)
        urls = [
            "/curated/彩色卡通-漆艺工坊关卡.png",
            "/curated/彩色卡通-漆艺学徒角色.png",
            "/curated/彩色卡通-层漆碗道具.png",
            "/curated/彩色卡通-漆林采集关卡.png",
        ]
        return ProviderTask(
            provider=self.name, kind=self.kind, task_id="curated-image-fallback", status="completed",
            payload={"urls": urls, "prompt": request.prompt, "provenance": "curated_local_fallback", "rights": "project_demo_assets"},
        )

    async def poll(self, task: ProviderTask) -> ProviderTask:
        return task


class JimengImageProvider(AssetProvider):
    kind, name = "image", "jimeng"
    def __init__(self): self.ak,self.sk,self.req_key=os.getenv("VOLC_ACCESSKEY",""),os.getenv("VOLC_SECRETKEY",""),os.getenv("JIMENG_REQ_KEY","t2i_v40_jimeng")
    def _service(self):
        if not self.ak or not self.sk: raise AssetProviderError("credentials_missing","未配置即梦企业 API 凭据")
        from volcengine.visual.VisualService import VisualService
        service=VisualService(); service.set_ak(self.ak); service.set_sk(self.sk); return service
    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request); body={"req_key":self.req_key,"prompt":request.prompt,"image_urls":request.reference_urls,"force_single":False}
        raw=await asyncio.to_thread(self._service().cv_sync2async_submit_task,body); data=json.loads(raw) if isinstance(raw,str) else raw
        if data.get("code") != 10000: raise AssetProviderError("submit_failed",data.get("message","即梦提交失败"))
        return ProviderTask(provider=self.name,kind=self.kind,task_id=str(data["data"]["task_id"]),status="queued",payload={"req_key":self.req_key},estimated_cost_cny=float(os.getenv("JIMENG_ESTIMATED_COST_CNY","1")))
    async def poll(self, task: ProviderTask) -> ProviderTask:
        body={"req_key":self.req_key,"task_id":task.task_id,"req_json":json.dumps({"return_url":True})}; raw=await asyncio.to_thread(self._service().cv_sync2async_get_result,body); data=json.loads(raw) if isinstance(raw,str) else raw
        state=(data.get("data") or {}).get("status","failed"); status={"in_queue":"queued","generating":"running","done":"completed"}.get(state,"failed")
        return task.model_copy(update={"status":status,"payload":data.get("data") or {}})


class MicuImageProvider(AssetProvider):
    kind, name = "image", "micu-image"

    def __init__(self):
        self.key = os.getenv("MICU_IMAGE_API_KEY") or settings.micu_image_api_key
        self.base = os.getenv("MICU_IMAGE_BASE_URL", "https://www.micuapi.ai/v1").rstrip("/")
        self.model = os.getenv("MICU_IMAGE_MODEL", "gpt-image-2-pro")
        self.size = os.getenv("MICU_IMAGE_SIZE", "1024x1024")

    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request)
        if not self.key:
            raise AssetProviderError("credentials_missing", "未配置米醋图片 API Key")
        body = {"model": self.model, "prompt": request.prompt, "n": 1, "size": self.size, "response_format": "url"}
        headers = {"Authorization": f"Bearer {self.key}", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QIWEN/1.0"}
        files = []
        field = "image" if len(request.reference_urls) == 1 else "image[]"
        for reference in request.reference_urls:
            parsed = urlparse(reference)
            if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.startswith("/objects/"):
                raise AssetProviderError("invalid_reference", "参考图必须是当前项目已上传的本地图片。")
            path = Path(settings.object_storage_root) / Path(parsed.path).name
            if not path.is_file():
                raise AssetProviderError("reference_missing", "参考图文件不存在。")
            files.append((field, (path.name, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png")))

        response: httpx.Response | None = None
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=float(os.getenv("MICU_IMAGE_TIMEOUT_SECONDS", "180"))) as client:
                    if files:
                        edit_body = {"model":self.model,"prompt":request.prompt,"size":self.size,"response_format":"url"}
                        response = await client.post(f"{self.base}/images/edits", headers=headers, data=edit_body, files=files)
                    else:
                        response = await client.post(f"{self.base}/images/generations", headers={**headers,"Content-Type":"application/json"}, json=body)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                last_error = AssetProviderError("provider_busy", f"当前图像服务暂时不可用（HTTP {response.status_code}）", True)
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        if response is None:
            logger.error(
                "[IMAGE] provider connection failed after 3 attempts: base=%s error=%s",
                self.base,
                type(last_error).__name__ if last_error else "unknown",
                exc_info=last_error,
            )
            raise AssetProviderError("provider_connection_failed", "当前图像服务连接失败，请稍后重试。", True) from last_error
        if response.status_code == 429 or response.status_code >= 500:
            raise AssetProviderError("provider_busy", f"当前图像服务暂时不可用（HTTP {response.status_code}）", True)
        if response.status_code == 400 and "content_policy" in response.text.lower():
            raise AssetProviderError(
                "content_requires_revision",
                "这条素材提示词或参考图未通过检查。请修改容易误解的词语，或清除参考图后重试。",
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AssetProviderError(f"http_{response.status_code}", _redact_provider_message(response.text[:500] or str(exc))) from exc
        data = response.json()
        urls = []
        for item in data.get("data", []):
            if item.get("url"):
                urls.append(item["url"])
            elif item.get("b64_json"):
                try:
                    base64.b64decode(item["b64_json"], validate=True)
                except ValueError as exc:
                    raise AssetProviderError("invalid_response", "米醋图片返回了无效的 base64 数据") from exc
                urls.append(f"data:image/png;base64,{item['b64_json']}")
        if not urls:
            raise AssetProviderError("provider_output_missing", "米醋图片任务没有返回图片")
        return ProviderTask(
            provider=self.name,
            kind=self.kind,
            task_id=str(data.get("id") or data.get("created") or "micu-sync"),
            status="completed",
            payload={"urls": urls, "model": self.model, "size": self.size, "rights": "provider_terms_apply"},
            estimated_cost_cny=float(os.getenv("MICU_IMAGE_ESTIMATED_COST_CNY", "1")),
        )

    async def poll(self, task: ProviderTask) -> ProviderTask:
        return task


class HunyuanThreeDProvider(AssetProvider):
    kind, name = "3d", "hunyuan3d"
    def __init__(self):
        self.key = os.getenv("HUNYUAN3D_API_KEY") or settings.hunyuan3d_api_key
        self.base = os.getenv("HUNYUAN3D_BASE_URL", "https://tokenhub.tencentmaas.com/v1/api/3d").rstrip("/")
        self.model = os.getenv("HUNYUAN3D_MODEL", "hy-3d-3.1")
        self.tokenhub = "tokenhub.tencentmaas.com" in self.base

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.key}" if self.tokenhub else self.key, "Content-Type": "application/json"}

    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request)
        if not self.key: raise AssetProviderError("credentials_missing","未配置混元生3D API Key")
        if self.tokenhub:
            body={"model":self.model,"prompt":request.prompt}
            if request.reference_urls: body["image_url"]={"url":request.reference_urls[0]}
            url=f"{self.base}/submit"
        else:
            body={"Prompt":request.prompt,"Model":"3.1"}
            if request.reference_urls: body["ImageUrl"]={"Url":request.reference_urls[0]}
            url=f"{self.base}/v1/ai3d/submit"
        async with httpx.AsyncClient(timeout=60) as client: response=await client.post(url,headers=self._headers(),json=body)
        response.raise_for_status(); data=response.json(); task_id=data.get("id") if self.tokenhub else data.get("JobId") or data.get("job_id")
        if not task_id: raise AssetProviderError("invalid_response", "混元生3D 提交结果缺少任务编号")
        return ProviderTask(provider=self.name,kind=self.kind,task_id=str(task_id),status="queued",payload={"model":self.model},estimated_cost_cny=float(os.getenv("HUNYUAN3D_ESTIMATED_COST_CNY","10")))

    async def poll(self, task: ProviderTask) -> ProviderTask:
        body={"model":self.model,"id":task.task_id} if self.tokenhub else {"JobId":task.task_id}
        url=f"{self.base}/query" if self.tokenhub else f"{self.base}/v1/ai3d/query"
        async with httpx.AsyncClient(timeout=60) as client: response=await client.post(url,headers=self._headers(),json=body)
        response.raise_for_status(); data=response.json(); raw=str(data.get("Status") or data.get("status","")).lower(); status="completed" if raw in {"done","success","completed"} else "failed" if raw in {"failed","error"} else "queued" if raw in {"queued","pending"} else "running"
        return task.model_copy(update={"status":status,"payload":data})


class TencentMpsMusicProvider(AssetProvider):
    kind, name = "music", "tencent-mps"
    def __init__(self): self.sid,self.skey,self.region=os.getenv("TENCENT_SECRET_ID",""),os.getenv("TENCENT_SECRET_KEY",""),os.getenv("TENCENT_MPS_REGION","ap-guangzhou")
    def _client(self):
        if not self.sid or not self.skey: raise AssetProviderError("credentials_missing","未配置腾讯云 MPS 凭据")
        from tencentcloud.common import credential
        from tencentcloud.mps.v20190612 import mps_client
        return mps_client.MpsClient(credential.Credential(self.sid,self.skey),self.region)
    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request); from tencentcloud.mps.v20190612 import models
        body={"ModelName":os.getenv("TENCENT_MPS_MUSIC_MODEL",""),"ModelVersion":os.getenv("TENCENT_MPS_MUSIC_MODEL_VERSION",""),"SceneType":"MusicGeneration","Prompt":f"{request.prompt}；情绪：{request.mood}；速度：每分钟{request.tempo}拍；时长约{request.duration}秒；{'可循环' if request.loop else '不循环'}","OutputAudioFormat":"WAV"}
        body={key:value for key,value in body.items() if value}
        req=models.CreateAigcAudioTaskRequest(); req.from_json_string(json.dumps(body,ensure_ascii=False)); result=await asyncio.to_thread(self._client().CreateAigcAudioTask,req); data=json.loads(result.to_json_string())
        return ProviderTask(provider=self.name,kind=self.kind,task_id=str(data["TaskId"]),status="queued",estimated_cost_cny=float(os.getenv("TENCENT_MPS_ESTIMATED_COST_CNY","2")))
    async def poll(self, task: ProviderTask) -> ProviderTask:
        from tencentcloud.mps.v20190612 import models
        req=models.DescribeAigcAudioTaskRequest(); req.from_json_string(json.dumps({"TaskId":task.task_id})); result=await asyncio.to_thread(self._client().DescribeAigcAudioTask,req); data=json.loads(result.to_json_string()); raw=str(data.get("Status","")).lower(); status="completed" if raw in {"success","finish","completed"} else "failed" if raw in {"fail","failed"} else "running"
        return task.model_copy(update={"status":status,"payload":data})


class AceStepMusicProvider(AssetProvider):
    """通过本机 ACE-Step 服务生成可审阅、可下载的完整音乐。"""
    kind, name = "music", "ace-step-local"

    def __init__(self):
        self.base = os.getenv("ACESTEP_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
        self.model = os.getenv("ACESTEP_MODEL", "acestep-v15-turbo")
        self.timeout = float(os.getenv("ACESTEP_TIMEOUT_SECONDS", "180"))
        self.batch_size = max(1, min(int(os.getenv("ACESTEP_BATCH_SIZE", "2")), 2))

    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request)
        duration = max(10, min(request.duration, 180))
        body = {
            "prompt": f"{request.prompt}；情绪：{request.mood}；纯器乐游戏配乐，无人声，适合循环播放",
            "lyrics": "",
            "thinking": False,
            "use_format": False,
            "audio_format": "wav",
            "audio_duration": duration,
            "bpm": request.tempo,
            "model": self.model,
            "batch_size": self.batch_size,
            "use_random_seed": True,
            "inference_steps": 8,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(f"{self.base}/release_task", json=body)
                response.raise_for_status()
        except (httpx.HTTPError, OSError) as exc:
            logger.exception("[MUSIC] local generation service submit failed: base=%s", self.base)
            raise AssetProviderError("music_service_unavailable", "本地音乐生成服务尚未启动或暂时不可用", True) from exc
        data = response.json()
        if data.get("code") != 200 or not (data.get("data") or {}).get("task_id"):
            raise AssetProviderError("music_submit_failed", str(data.get("error") or "音乐任务提交失败"))
        task_id = str(data["data"]["task_id"])
        return ProviderTask(
            provider=self.name, kind=self.kind, task_id=task_id, status="queued",
            payload={"model":self.model,"duration":duration}, estimated_cost_cny=0,
        )

    async def poll(self, task: ProviderTask) -> ProviderTask:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(f"{self.base}/query_result", json={"task_id_list":[task.task_id]})
                response.raise_for_status()
        except (httpx.HTTPError, OSError) as exc:
            logger.exception("[MUSIC] local generation service query failed: base=%s task=%s", self.base, task.task_id)
            raise AssetProviderError("music_service_unavailable", "本地音乐生成服务暂时不可用", True) from exc
        envelope = response.json()
        records = envelope.get("data") or []
        if envelope.get("code") != 200 or not records:
            raise AssetProviderError("music_query_failed", str(envelope.get("error") or "音乐任务查询失败"), True)
        record = records[0]
        raw_status = int(record.get("status", 0))
        status = "completed" if raw_status == 1 else "failed" if raw_status == 2 else "running"
        payload = dict(task.payload)
        if status == "completed":
            result = record.get("result") or "[]"
            try:
                items = json.loads(result) if isinstance(result, str) else result
            except json.JSONDecodeError as exc:
                raise AssetProviderError("music_invalid_response", "音乐服务返回了无法读取的结果") from exc
            urls = []
            for item in items if isinstance(items, list) else []:
                file_url = item.get("file") if isinstance(item, dict) else None
                if file_url:
                    urls.append(file_url if file_url.startswith(("http://", "https://")) else f"{self.base}{file_url}")
            if not urls:
                raise AssetProviderError("provider_output_missing", "音乐任务完成但没有返回音频文件")
            payload.update({"urls":urls,"mime":"audio/wav","result":items})
        elif status == "failed":
            payload["error"] = record.get("error") or record.get("result") or "音乐生成失败"
        return task.model_copy(update={"status":status,"payload":payload})


class AgentDesignedAudioProvider(AssetProvider):
    """将模型给出的受约束声音设计渲染为可审阅 WAV；不生成语音，也不伪装成外部音乐模型。"""
    kind, name = "music", "agent-designed-audio"

    @staticmethod
    def _render(request: AssetGenerationRequest, variation: int) -> str:
        rate = 22050
        duration = max(8, min(request.duration, 30))
        frames = rate * duration
        layers = request.sound_layers or [{"waveform":"sine","frequency":220,"rhythm_division":1,"volume":0.25}]
        prompt = request.prompt.strip().lower()
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        tempo = max(54, min(request.tempo, 132))
        if any(word in prompt for word in ("快速", "高速", "战斗", "紧张", "激烈", "追逐", "fast", "battle")):
            tempo = max(tempo, 108)
        if any(word in prompt for word in ("缓慢", "舒缓", "宁静", "冥想", "安静", "slow", "calm", "ambient")):
            tempo = min(tempo, 70)
        beat_seconds = 60.0 / tempo
        frequencies = [max(80.0, min(float(layer.get("frequency", 220)), 1200.0)) for layer in layers]
        root = min(frequencies) if frequencies else 110.0
        while root > 180:
            root /= 2
        transpose = (digest[0] % 9) - 4
        root *= 2 ** (transpose / 12) * (1 + variation * 0.015)
        dark = any(word in prompt for word in ("阴暗", "神秘", "紧张", "危险", "悲伤", "dark", "mysterious", "minor"))
        bright = any(word in prompt for word in ("欢快", "明亮", "轻快", "胜利", "可爱", "bright", "happy", "major"))
        minor_mode = dark or (not bright and digest[1] % 2 == 1)
        progressions = ((0, 5, 8, 7), (0, 8, 5, 10), (0, 3, 7, 5)) if minor_mode else ((0, 5, 9, 7), (0, 9, 5, 7), (0, 7, 5, 9))
        melodies = ((0, 3, 5, 7, 10, 7, 5, 3), (0, 5, 7, 10, 7, 5, 3, 5), (0, 3, 7, 5, 10, 7, 3, 5)) if minor_mode else ((0, 2, 4, 7, 9, 7, 4, 2), (0, 4, 7, 9, 7, 4, 2, 4), (0, 2, 7, 4, 9, 7, 4, 2))
        pattern_index = (digest[2] + variation) % len(progressions)
        progression = progressions[pattern_index]
        melody = melodies[pattern_index]
        note_rate = 1 if any(word in prompt for word in ("缓慢", "舒缓", "宁静", "ambient", "slow")) else 4 if any(word in prompt for word in ("快速", "高速", "激烈", "fast")) else 2
        lead_waveform = "square" if any(word in prompt for word in ("电子", "像素", "街机", "electronic", "pixel")) else "triangle"
        prompt_phase = int.from_bytes(digest[4:8], "big") / 2**32 * 2 * math.pi
        rhythm_level = 0.065 if any(word in prompt for word in ("节奏", "鼓", "战斗", "rhythm", "drum")) else 0.022

        def oscillator(phase: float, waveform: str) -> float:
            if waveform == "triangle":
                return (2 / math.pi) * math.asin(math.sin(phase))
            if waveform == "square":
                return 1.0 if math.sin(phase) >= 0 else -1.0
            return math.sin(phase)

        output = io.BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(2); audio.setsampwidth(2); audio.setframerate(rate)
            for index in range(frames):
                time = index / rate
                beat = time / beat_seconds
                chord_root = root * 2 ** (progression[int(beat // 4) % len(progression)] / 12)
                chord_phase = (beat % 4) / 4
                pad_envelope = 0.72 + 0.28 * (0.5 - 0.5 * math.cos(2 * math.pi * chord_phase))
                chord_ratios = (1.0, 1.1892, 1.4983) if minor_mode else (1.0, 1.2599, 1.4983)
                pad = sum(math.sin(2 * math.pi * chord_root * ratio * time + prompt_phase * 0.08) for ratio in chord_ratios) / 3
                pad += 0.22 * math.sin(2 * math.pi * chord_root * 2.0 * time)

                melody_position = beat * note_rate
                melody_degree = melody[int(melody_position) % len(melody)] + 12
                melody_frequency = root * 2 ** (melody_degree / 12)
                note_phase = melody_position % 1
                melody_envelope = math.sin(math.pi * min(1.0, note_phase / 0.92)) ** 0.7 if note_phase < 0.92 else 0.0
                lead = oscillator(2 * math.pi * melody_frequency * time + prompt_phase, lead_waveform) * melody_envelope

                bass_phase = beat % 1
                bass_envelope = 0.55 + 0.45 * math.exp(-bass_phase * 3.2)
                bass = math.sin(2 * math.pi * (chord_root / 2) * time) * bass_envelope

                pulse_phase = beat % 1
                pulse = math.sin(2 * math.pi * (78 + digest[3] % 38) * time) * math.exp(-pulse_phase * 16) * rhythm_level
                left = pad * pad_envelope * 0.24 + bass * 0.15 + lead * 0.13 + pulse
                right = pad * pad_envelope * 0.24 + bass * 0.15 + lead * 0.17 - pulse * 0.35
                fade = min(1.0, time / 0.18, (duration - time) / 0.3)
                left_sample = int(max(-1.0, min(1.0, left * fade)) * 25000)
                right_sample = int(max(-1.0, min(1.0, right * fade)) * 25000)
                audio.writeframesraw(struct.pack("<hh", left_sample, right_sample))
        return "data:audio/wav;base64," + base64.b64encode(output.getvalue()).decode("ascii")

    async def submit(self, request: AssetGenerationRequest) -> ProviderTask:
        self.validate(request)
        urls = [await asyncio.to_thread(self._render, request, variation) for variation in (0, 1)]
        return ProviderTask(
            provider=self.name, kind=self.kind, task_id="agent-audio-sync", status="completed",
            payload={"urls":urls,"mime":"audio/wav","duration":min(request.duration,30),"cue_names":request.cue_names,"arrangement":["持续和弦","主旋律","低音线","轻量节奏"],"provenance":"llm_sound_design_local_render"},
            estimated_cost_cny=0,
        )

    async def poll(self, task: ProviderTask) -> ProviderTask:
        return task


def get_asset_provider(kind: str) -> AssetProvider:
    if kind=="image" and (os.getenv("MICU_IMAGE_API_KEY") or settings.micu_image_api_key): return MicuImageProvider()
    if kind=="image" and os.getenv("VOLC_ACCESSKEY") and os.getenv("VOLC_SECRETKEY"): return JimengImageProvider()
    if kind=="3d" and (os.getenv("HUNYUAN3D_API_KEY") or settings.hunyuan3d_api_key): return HunyuanThreeDProvider()
    if kind=="music" and os.getenv("ACESTEP_BASE_URL"): return AceStepMusicProvider()
    if kind=="music" and os.getenv("TENCENT_SECRET_ID") and os.getenv("TENCENT_SECRET_KEY"): return TencentMpsMusicProvider()
    if kind=="music" and (os.getenv("MICU_LLM_API_KEY") or settings.micu_llm_api_key): return AgentDesignedAudioProvider()
    return MockAssetProvider(kind)


async def run_asset_provider(provider: AssetProvider, request: AssetGenerationRequest, *, max_polls: int = 60) -> ProviderTask:
    task = await provider.submit(request)
    for attempt in range(max_polls):
        if task.status in {"completed", "failed", "cancelled"}: break
        await asyncio.sleep(min(1 + attempt // 10, 5))
        task = await provider.poll(task)
    if task.status not in {"completed", "failed", "cancelled"}: raise AssetProviderError("provider_timeout", f"{provider.name} 任务超时", True)
    if task.status != "completed": raise AssetProviderError("provider_task_failed", f"{provider.name} 任务状态：{task.status}")
    return task


def extract_provider_urls(kind: str, payload: dict[str, Any]) -> list[str]:
    def collect(value: Any) -> list[str]:
        if isinstance(value, str):
            if value.startswith(("/demo/", "/curated/", "https://", "http://", "data:image/", "data:audio/")): return [value]
            try: return collect(json.loads(value))
            except (json.JSONDecodeError, TypeError): return []
        if isinstance(value, list): return [url for item in value for url in collect(item)]
        if isinstance(value, dict): return [url for item in value.values() for url in collect(item)]
        return []
    urls = list(dict.fromkeys(collect(payload)))
    suffixes={"visual":(".png",".jpg",".jpeg",".webp"),"2d":(".png",".jpg",".jpeg",".webp"),"3d":(".glb",),"music":(".wav",".mp3",".m4a",".aac",".flac")}[kind]
    matching=[url for url in urls if url.lower().split("?")[0].endswith(suffixes)]
    return matching or urls


def task_to_artifact(kind: str, task: ProviderTask, request: AssetGenerationRequest) -> dict[str, Any]:
    payload = task.payload
    urls = extract_provider_urls(kind, payload)
    if kind == "visual":
        variants=[{"id":f"image-{i+1}","title":f"视觉方案 {i+1}","url":url} for i,url in enumerate(urls)]
        if not variants: raise AssetProviderError("provider_output_missing", "图像任务没有返回图片")
        return {"prompt":request.prompt,"variants":variants,"selected":variants[0]["id"],"provider":task.provider,"provider_task_id":task.task_id,"ingested":payload.get("ingested",[]),"estimated_cost_cny":task.estimated_cost_cny}
    if kind == "2d":
        variants=[{"id":f"sprite-{i+1}","title":f"二维素材 {i+1}","url":url} for i,url in enumerate(urls)]
        if not variants: raise AssetProviderError("provider_output_missing", "二维素材任务没有返回图片")
        return {"mode":"2d","prompt":request.prompt,"variants":variants,"selected":variants[0]["id"],"provider":task.provider,"provider_task_id":task.task_id,"ingested":payload.get("ingested",[]),"estimated_cost_cny":task.estimated_cost_cny}
    if kind == "3d":
        if not urls: raise AssetProviderError("provider_output_missing", "三维任务没有返回模型")
        inspected=(payload.get("ingested") or [{}])[0]
        return {"name":"漆艺三维模型","file":urls[0],"format":"GLB","polygon_count":int(payload.get("polygon_count") or inspected.get("polygon_count",0)),"texture":"PBR 材质","version":1,"provider":task.provider,"provider_task_id":task.task_id,"ingested":payload.get("ingested",[]),"estimated_cost_cny":task.estimated_cost_cny}
    if kind == "music":
        if not urls: raise AssetProviderError("provider_output_missing", "音乐任务没有返回音频")
        tracks=[{"id":f"bgm-v{i+1}","title":f"音乐版本 {i+1}","url":url} for i,url in enumerate(urls)]
        return {"prompt":request.prompt,"mood":request.mood,"tempo":request.tempo,"duration":request.duration,"loop":request.loop,"tracks":tracks,"selected":tracks[0]["id"],"provider":task.provider,"provider_task_id":task.task_id,"ingested":payload.get("ingested",[]),"estimated_cost_cny":task.estimated_cost_cny}
    raise AssetProviderError("unsupported_kind", kind)
