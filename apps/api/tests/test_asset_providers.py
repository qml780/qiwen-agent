import json
import struct
import pytest

from app.asset_providers import (
    AceStepMusicProvider,
    AssetGenerationRequest,
    AgentDesignedAudioProvider,
    AssetProviderError,
    CuratedImageFallbackProvider,
    HunyuanThreeDProvider,
    JimengImageProvider,
    MicuImageProvider,
    MockAssetProvider,
    ProviderTask,
    TencentMpsMusicProvider,
    get_asset_provider,
    run_asset_provider,
    task_to_artifact,
)
from app.object_storage import ObjectValidationError, _inspect, _safe_remote, ingest_url


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected", [("image","image/png"),("3d","model/gltf-binary"),("music","audio/wav")])
async def test_mock_provider_contract(kind, expected):
    provider=MockAssetProvider(kind)
    task=await run_asset_provider(provider,AssetGenerationRequest(prompt="漆艺测试提示词"))
    assert task.status == "completed"
    assert task.payload["mime"] == expected
    assert task.payload["rights"] == "internal_demo_only"


@pytest.mark.asyncio
async def test_curated_image_fallback_returns_colored_game_candidates():
    task = await CuratedImageFallbackProvider().submit(AssetGenerationRequest(prompt="彩色卡通漆艺游戏"))
    assert task.status == "completed"
    assert task.provider == "curated-image-fallback"
    assert len(task.payload["urls"]) == 4
    assert all(url.startswith("/curated/") for url in task.payload["urls"])
    artifact = task_to_artifact("visual", task, AssetGenerationRequest(prompt="彩色卡通漆艺游戏"))
    assert len(artifact["variants"]) == 4


def test_provider_selection_falls_back_without_keys(monkeypatch):
    for key in ("MICU_IMAGE_API_KEY","VOLC_ACCESSKEY","VOLC_SECRETKEY","HUNYUAN3D_API_KEY","TENCENT_SECRET_ID","TENCENT_SECRET_KEY","ACESTEP_BASE_URL"):
        monkeypatch.delenv(key,raising=False)
    assert get_asset_provider("image").name == "mock-image"
    assert get_asset_provider("3d").name == "mock-3d"
    assert get_asset_provider("music").name == "mock-music"


@pytest.mark.asyncio
async def test_acestep_music_contract(monkeypatch):
    calls = []

    class Response:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json):
            calls.append((url, json))
            if url.endswith("/release_task"):
                return Response({"code":200,"data":{"task_id":"ace-1","status":"queued"}})
            result = json_module.dumps([{"file":"/v1/audio?path=output/test.wav","status":1}])
            return Response({"code":200,"data":[{"task_id":"ace-1","status":1,"result":result}]})

    json_module = json
    monkeypatch.setenv("ACESTEP_BASE_URL", "http://127.0.0.1:8001")
    monkeypatch.setattr("app.asset_providers.httpx.AsyncClient", Client)
    provider = AceStepMusicProvider()
    request = AssetGenerationRequest(prompt="彩色卡通漆艺工坊的轻快探索音乐", duration=20, tempo=84)
    task = await provider.poll(await provider.submit(request))
    assert calls[0][1]["thinking"] is False
    assert calls[0][1]["lyrics"] == ""
    assert calls[0][1]["batch_size"] == 2
    assert task.status == "completed"
    assert task.payload["urls"] == ["http://127.0.0.1:8001/v1/audio?path=output/test.wav"]
    assert task_to_artifact("music", task, request)["tracks"][0]["url"].endswith("output/test.wav")


@pytest.mark.asyncio
async def test_micu_image_openai_compatible_contract(monkeypatch):
    class Response:
        status_code = 200
        text = ""
        def raise_for_status(self): pass
        def json(self): return {"created": 1, "data": [{"url": "https://example.com/lacquer.png"}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers, json):
            assert url.endswith("/v1/images/generations")
            assert json["model"] == "gpt-image-2-pro"
            assert headers["Authorization"] == "Bearer image-key"
            return Response()
    monkeypatch.setenv("MICU_IMAGE_API_KEY", "image-key")
    monkeypatch.setattr("app.asset_providers.httpx.AsyncClient", Client)
    task = await MicuImageProvider().submit(AssetGenerationRequest(prompt="黑白漆艺作坊"))
    assert task.provider == "micu-image"
    assert task.status == "completed"
    assert task.payload["urls"] == ["https://example.com/lacquer.png"]


@pytest.mark.asyncio
async def test_image_content_check_returns_short_chinese_message(monkeypatch):
    class Response:
        status_code = 400
        text = '{"error":{"type":"content_policy_violation","message":"raw provider detail"}}'
        def raise_for_status(self): raise AssertionError("内容检查应先转换为友好错误")
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response()
    monkeypatch.setenv("MICU_IMAGE_API_KEY", "image-key")
    monkeypatch.setattr("app.asset_providers.httpx.AsyncClient", Client)
    with pytest.raises(AssetProviderError, match="请修改容易误解的词语") as error:
        await MicuImageProvider().submit(AssetGenerationRequest(prompt="二维游戏素材"))
    assert error.value.code == "content_requires_revision"


@pytest.mark.asyncio
async def test_jimeng_submit_and_poll_contract(monkeypatch):
    class Service:
        def cv_sync2async_submit_task(self, body):
            assert body["req_key"] == "t2i_v40_jimeng"
            return {"code":10000,"data":{"task_id":"j-1"}}
        def cv_sync2async_get_result(self, body):
            return {"code":10000,"data":{"status":"done","image_urls":["https://example.com/a.png"]}}
    monkeypatch.setenv("VOLC_ACCESSKEY","ak"); monkeypatch.setenv("VOLC_SECRETKEY","sk")
    provider=JimengImageProvider(); monkeypatch.setattr(provider,"_service",lambda:Service())
    task=await provider.poll(await provider.submit(AssetGenerationRequest(prompt="黑白漆艺作坊")))
    artifact=task_to_artifact("visual",task,AssetGenerationRequest(prompt="黑白漆艺作坊"))
    assert task.status == "completed"
    assert artifact["provider"] == "jimeng"
    assert artifact["variants"][0]["url"].endswith("a.png")


@pytest.mark.asyncio
async def test_hunyuan_openai_compatible_contract(monkeypatch):
    calls=[]
    class Response:
        def __init__(self,data): self.data=data
        def raise_for_status(self): pass
        def json(self): return self.data
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,headers,json):
            calls.append((url,headers,json))
            return Response({"JobId":"h-1"} if url.endswith("submit") else {"Status":"success","ResultFile3Ds":[{"Url":"https://example.com/bowl.glb"}]})
    monkeypatch.setenv("HUNYUAN3D_API_KEY","sk-test")
    monkeypatch.setenv("HUNYUAN3D_BASE_URL","https://api.ai3d.cloud.tencent.com")
    monkeypatch.setattr("app.asset_providers.httpx.AsyncClient",Client)
    provider=HunyuanThreeDProvider(); request=AssetGenerationRequest(prompt="低面数漆碗")
    task=await provider.poll(await provider.submit(request))
    assert calls[0][0].endswith("/v1/ai3d/submit")
    assert calls[0][2]["Model"] == "3.1"
    assert task_to_artifact("3d",task,request)["file"].endswith("bowl.glb")


@pytest.mark.asyncio
async def test_hunyuan_tokenhub_contract(monkeypatch):
    calls=[]
    class Response:
        def __init__(self,data): self.data=data
        def raise_for_status(self): pass
        def json(self): return self.data
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,headers,json):
            calls.append((url,headers,json))
            return Response({"id":"th-1","status":"queued"} if url.endswith("submit") else {"status":"completed","data":[{"type":"glb","url":"https://example.com/bowl.glb"}]})
    monkeypatch.setenv("HUNYUAN3D_API_KEY","sk-test")
    monkeypatch.setenv("HUNYUAN3D_BASE_URL","https://tokenhub.tencentmaas.com/v1/api/3d")
    monkeypatch.setenv("HUNYUAN3D_MODEL","hy-3d-3.1")
    monkeypatch.setattr("app.asset_providers.httpx.AsyncClient",Client)
    provider=HunyuanThreeDProvider(); request=AssetGenerationRequest(prompt="低面数漆碗")
    task=await provider.poll(await provider.submit(request))
    assert calls[0][0].endswith("/v1/api/3d/submit")
    assert calls[0][1]["Authorization"] == "Bearer sk-test"
    assert calls[0][2] == {"model":"hy-3d-3.1","prompt":"低面数漆碗"}
    assert calls[1][2] == {"model":"hy-3d-3.1","id":"th-1"}
    assert task_to_artifact("3d",task,request)["file"].endswith("bowl.glb")


@pytest.mark.asyncio
async def test_tencent_mps_request_contract(monkeypatch):
    captured={}
    class Result:
        def __init__(self,data): self.data=data
        def to_json_string(self): return json.dumps(self.data)
    class Client:
        def CreateAigcAudioTask(self,request):
            captured.update(json.loads(request.to_json_string())); return Result({"TaskId":"m-1"})
        def DescribeAigcAudioTask(self,request):
            return Result({"Status":"success","AudioInfos":[{"Url":"https://example.com/music.wav"}]})
    monkeypatch.setenv("TENCENT_SECRET_ID","id"); monkeypatch.setenv("TENCENT_SECRET_KEY","key")
    provider=TencentMpsMusicProvider(); monkeypatch.setattr(provider,"_client",lambda:Client())
    request=AssetGenerationRequest(prompt="层积音乐",duration=45)
    task=await provider.poll(await provider.submit(request))
    assert captured["SceneType"] == "MusicGeneration"
    assert "45秒" in captured["Prompt"]
    assert task_to_artifact("music",task,request)["tracks"][0]["url"].endswith("music.wav")


@pytest.mark.asyncio
async def test_cancel_is_idempotent():
    provider=MockAssetProvider("image")
    task=ProviderTask(provider="mock-image",kind="image",task_id="x",status="running")
    cancelled=await provider.cancel(task)
    assert (await provider.cancel(cancelled)).status == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,url", [("visual","/demo/lacquer-bowl.png"),("3d","/demo/lacquer-bowl-v1.glb"),("music","/demo/main-theme.wav")])
async def test_demo_outputs_are_signature_checked_and_hashed(kind,url):
    item=await ingest_url(kind,url)
    assert item["sha256"]
    assert item["bytes"] > 0


@pytest.mark.asyncio
async def test_wrong_asset_signature_is_rejected():
    with pytest.raises(ObjectValidationError):
        await ingest_url("music","/demo/lacquer-bowl.png")


def test_only_fixed_local_music_service_is_allowed_over_http():
    _safe_remote("http://127.0.0.1:8001/v1/audio?path=output/test.wav")
    with pytest.raises(ObjectValidationError):
        _safe_remote("http://127.0.0.1:9000/private")


def test_float_wav_metadata_is_readable():
    payload = bytes(384000)
    fmt = struct.pack("<HHIIHH", 3, 2, 48000, 384000, 8, 32)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(payload)) + payload
    wav = b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body
    assert _inspect("music", wav) == {"duration":1.0,"sample_rate":48000,"channels":2}


@pytest.mark.asyncio
async def test_agent_sound_design_renders_real_reviewable_wav():
    request = AssetGenerationRequest(
        prompt="根据薄髹层积生成简单循环声音", duration=8, tempo=72,
        sound_layers=[{"waveform":"sine","frequency":220,"rhythm_division":1,"volume":0.2}],
        cue_names=["完成一层", "出现缺陷"],
    )
    task = await AgentDesignedAudioProvider().submit(request)
    assert task.status == "completed"
    assert task.payload["provenance"] == "llm_sound_design_local_render"
    assert task.payload["arrangement"] == ["持续和弦", "主旋律", "低音线", "轻量节奏"]
    saved = await ingest_url("music", task.payload["urls"][0])
    assert saved["mime"] == "audio/wav"
    artifact = task_to_artifact("music", task, request)
    assert len(artifact["tracks"]) == 2
    assert artifact["tracks"][0]["url"].startswith("data:audio/wav;base64,")
    assert saved["duration"] == 8
    assert saved["channels"] == 2


def test_different_music_prompts_produce_different_audio() -> None:
    calm = AssetGenerationRequest(prompt="缓慢宁静的漆艺工坊环境配乐，柔和、舒缓", duration=8, tempo=76)
    battle = AssetGenerationRequest(prompt="快速紧张的机关追逐战斗音乐，强烈节奏与电子音色", duration=8, tempo=76)
    calm_audio = AgentDesignedAudioProvider._render(calm, 0)
    battle_audio = AgentDesignedAudioProvider._render(battle, 0)
    assert calm_audio != battle_audio
