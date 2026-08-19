from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor
import pytest

from app.main import app
from app.domain import AgentRequest, Project
from app.providers import DeepSeekLLMProvider, MockLLMProvider
from app.mock_data import KNOWLEDGE


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_project(client: TestClient) -> str:
    response = client.post("/projects", json={"knowledge_id": "thin-layers"})
    assert response.status_code == 200
    return response.json()["id"]


@pytest.mark.asyncio
async def test_unity_plan_obeys_explicit_approved_gameplay_over_knowledge_expansion():
    project = Project(
        selected_knowledge_id="thin-layers",
        player_idea="把清理胎体、髹涂底漆、阴干、打磨按正确先后排列",
        original_player_idea="把清理胎体、髹涂底漆、阴干、打磨按正确先后排列",
        artifacts={
            "concept":{"version":1,"data":{"game_name":"漆艺工序挑战","genre":"顺序谜题"}},
            "logic":{"version":1,"data":{"player":"点击工序卡片","painting":["按正确先后"],"rounds":"四步","win":"四步全部正确","fail":"错三次","audio_cues":["正确","错误"],"acceptance":["顺序可验证"]}},
        },
    )
    plan = await MockLLMProvider().generate_unity_plan(project, KNOWLEDGE[0])
    assert plan.data["template_id"] == "puzzle-process"
    assert plan.data["game_title"] == "漆艺工序挑战"
    assert plan.data["player_instructions"] == "点击工序卡片"
    assert plan.data["sequence_steps"] == ["清理胎体", "髹涂底漆", "阴干", "打磨"]


@pytest.mark.asyncio
async def test_unity_plan_recovers_after_two_invalid_model_results(monkeypatch):
    project = Project(
        selected_knowledge_id="thin-layers",
        player_idea="控制小工匠躲避漆滴",
        original_player_idea="控制小工匠躲避漆滴",
        artifacts={
            "concept": {"version": 1, "data": {"game_name": "漆滴避险", "genre": "俯视角闪避"}},
            "logic": {"version": 1, "data": {
                "player": "使用方向键移动小工匠",
                "painting": ["彩色卡通工坊"],
                "rounds": "45秒",
                "win": "坚持到计时结束",
                "fail": "沾染值达到上限",
                "audio_cues": ["预警", "命中", "闪避"],
                "acceptance": ["能够移动和结算"],
            }},
        },
    )
    provider = DeepSeekLLMProvider()
    responses = iter([
        {"choices": [{"message": {"content": "不是 JSON"}}], "usage": {}},
        {"choices": [{"message": {"content": '{"template_id":"错误模板"}'}}], "usage": {}},
    ])

    async def fake_post(_payload):
        return next(responses)

    monkeypatch.setattr(provider, "_post", fake_post)
    plan = await provider.generate_unity_plan(project, KNOWLEDGE[0])

    assert plan.demo_mode is False
    assert plan.data["game_title"] == "漆滴避险"
    assert plan.data["player_instructions"] == "使用方向键移动小工匠"
    assert plan.data["template_id"] == "topdown-dodge"


@pytest.mark.asyncio
async def test_unity_plan_limits_approved_text_and_lists_to_schema():
    project = Project(
        selected_knowledge_id="thin-layers",
        player_idea="长内容边界测试",
        original_player_idea="长内容边界测试",
        artifacts={
            "concept": {"version": 1, "data": {"game_name": "漆" * 80}},
            "logic": {"version": 1, "data": {
                "player": "移动" * 200,
                "painting": ["画面"],
                "rounds": "一轮",
                "win": "完成" * 200,
                "fail": "失败",
                "audio_cues": [f"声音{i}" for i in range(20)],
                "acceptance": ["可运行"],
            }},
        },
    )

    plan = await MockLLMProvider().generate_unity_plan(project, KNOWLEDGE[0])

    assert len(plan.data["game_title"]) == 60
    assert len(plan.data["objective"]) == 240
    assert len(plan.data["player_instructions"]) == 240
    assert len(plan.data["audio_cues"]) == 12


def create_ready_project(client: TestClient) -> str:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea": "建立可撤销的 Unity 共创测试"})
    for kind in ["concept", "visual", "3d", "music", "logic"]:
        assert client.post(f"/projects/{project_id}/generate/{kind}").status_code == 200
        assert client.post(f"/projects/{project_id}/approve/{kind}").status_code == 200
    return project_id


def test_full_mock_workflow_reaches_ready_to_build(client: TestClient) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/projects/{project_id}/idea",
        json={"idea": "我想让每一层髹漆增加一层音乐。"},
    )
    assert response.json()["current_stage"] == "concept_drafting"

    for kind, review_stage, next_stage in [
        ("concept", "concept_review", "visual_drafting"),
        ("visual", "visual_review", "3d_drafting"),
        ("3d", "3d_review", "music_drafting"),
        ("music", "music_review", "logic_drafting"),
        ("logic", "logic_review", "ready_to_build"),
    ]:
        generated = client.post(f"/projects/{project_id}/generate/{kind}")
        assert generated.status_code == 200
        assert generated.json()["current_stage"] == review_stage
        approved = client.post(f"/projects/{project_id}/approve/{kind}")
        assert approved.status_code == 200
        assert approved.json()["current_stage"] == next_stage


@pytest.mark.parametrize("mode", ["2d", "3d"])
def test_project_keeps_selected_2d_or_3d_route(client: TestClient, mode: str) -> None:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea": "制作彩色卡通漆艺游戏"})
    client.post(f"/projects/{project_id}/generate/concept")
    client.post(f"/projects/{project_id}/approve/concept")

    selected = client.post(f"/projects/{project_id}/production-mode", json={"mode": mode})
    assert selected.status_code == 200
    assert selected.json()["artifacts"]["production_mode"]["data"]["mode"] == mode

    visual = client.post(f"/projects/{project_id}/generate/visual")
    assert visual.status_code == 200
    prompt = visual.json()["artifacts"]["visual"]["data"]["prompt"]
    assert ("3D" in prompt) is (mode == "3d")

    client.post(f"/projects/{project_id}/approve/visual")
    asset = client.post(f"/projects/{project_id}/generate/3d")
    assert asset.status_code == 200
    data = asset.json()["artifacts"]["3d"]["data"]
    assert (data.get("mode") == "2d") is (mode == "2d")


def test_named_2d_assets_are_generated_approved_and_finalized_individually(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea":"制作包含角色、移动物件与提示特效的二维游戏"})
    client.post(f"/projects/{project_id}/generate/concept")
    client.post(f"/projects/{project_id}/approve/concept")
    client.post(f"/projects/{project_id}/production-mode", json={"mode":"2d"})
    client.post(f"/projects/{project_id}/generate/visual")
    approved_visual = client.post(f"/projects/{project_id}/approve/visual")
    plan = approved_visual.json()["artifacts"]["game_asset_plan"]["data"]
    assert len(plan["items"]) >= 5
    assert len({item["id"] for item in plan["items"]}) == len(plan["items"])
    assert all(item["name"] and item["prompt"] and item["status"] == "pending" for item in plan["items"])

    for item in plan["items"]:
        generated = client.post(f"/projects/{project_id}/game-assets/generate", json={"item_id":item["id"]})
        assert generated.status_code == 200
        generated_item = next(entry for entry in generated.json()["artifacts"]["game_asset_plan"]["data"]["items"] if entry["id"] == item["id"])
        assert generated_item["status"] == "generated"
        approved = client.post(f"/projects/{project_id}/game-assets/{generated_item['asset_id']}/approve")
        approved_item = next(entry for entry in approved.json()["artifacts"]["game_asset_plan"]["data"]["items"] if entry["id"] == item["id"])
        assert approved_item["status"] == "approved"

    finalized = client.post(f"/projects/{project_id}/game-assets/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["current_stage"] == "3d_review"
    variants = finalized.json()["artifacts"]["3d"]["data"]["variants"]
    assert len(variants) == len(plan["items"])
    assert all(item.get("asset_id") for item in variants)


def test_backend_rejects_skipping_approval_gate(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea": "做一个节奏游戏"})
    response = client.post(f"/projects/{project_id}/generate/visual")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_stage"
    after = client.get(f"/projects/{project_id}").json()
    assert after["current_stage"] == "concept_drafting"
    assert after["revision"] == 2


def test_project_can_be_created_independently_and_deleted(client: TestClient) -> None:
    first = create_project(client)
    second = create_project(client)
    assert first != second
    assert client.get(f"/projects/{first}").status_code == 200
    deleted = client.delete(f"/projects/{first}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert client.get(f"/projects/{first}").status_code == 404
    assert client.get(f"/projects/{second}").status_code == 200


def test_music_prompt_versions_can_be_selected_and_deleted(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea":"制作有旋律的漆艺游戏配乐"})
    for kind in ("concept", "visual", "3d"):
        assert client.post(f"/projects/{project_id}/generate/{kind}").status_code == 200
        assert client.post(f"/projects/{project_id}/approve/{kind}").status_code == 200
    generated = client.post(f"/projects/{project_id}/generate/music", json={"prompt":"持续和弦、旋律、低音，不要只有敲击声"})
    assert generated.status_code == 200
    music = generated.json()["artifacts"]["music"]["data"]
    assert music["prompt"] == "持续和弦、旋律、低音，不要只有敲击声"
    assert len(music["tracks"]) == 2
    second_id = music["tracks"][1]["id"]
    selected = client.post(f"/projects/{project_id}/music/tracks/{second_id}/select")
    assert selected.json()["artifacts"]["music"]["data"]["selected"] == second_id
    removed = client.delete(f"/projects/{project_id}/music/tracks/{second_id}")
    remaining = removed.json()["artifacts"]["music"]["data"]["tracks"]
    assert len(remaining) == 1
    emptied = client.delete(f"/projects/{project_id}/music/tracks/{remaining[0]['id']}")
    assert emptied.json()["current_stage"] == "music_drafting"
    assert emptied.json()["artifacts"]["music"]["data"]["tracks"] == []


def test_any_completed_stage_can_return_for_local_revision_without_invalidating_later_approvals(client: TestClient) -> None:
    project_id = create_ready_project(client)
    revised = client.post(f"/projects/{project_id}/revise/visual")
    assert revised.status_code == 200
    assert revised.json()["current_stage"] == "visual_drafting"
    assert set(revised.json()["approvals"]) == {"concept", "3d", "music", "logic"}
    assert "visual" in revised.json()["artifacts"]
    reloaded = client.get(f"/projects/{project_id}").json()
    assert reloaded["current_stage"] == "visual_drafting"
    assert set(reloaded["approvals"]) == {"concept", "3d", "music", "logic"}


def test_rework_game_assets_removes_only_stale_asset_approval(client: TestClient) -> None:
    project_id = create_ready_project(client)
    revised = client.post(f"/projects/{project_id}/game-assets/rework", json={"mode":"2d"})
    assert revised.status_code == 200
    assert revised.json()["current_stage"] == "3d_drafting"
    reloaded = client.get(f"/projects/{project_id}").json()
    assert "3d" not in reloaded["approvals"]
    assert set(reloaded["approvals"]) == {"concept", "visual", "music", "logic"}
    assert all(item["status"] == "pending" for item in reloaded["artifacts"]["game_asset_plan"]["data"]["items"])


def test_knowledge_can_be_revised_from_a_later_stage_without_requiring_an_approval_record(client: TestClient) -> None:
    project_id = create_ready_project(client)

    revised = client.post(f"/projects/{project_id}/revise/knowledge")

    assert revised.status_code == 200
    assert revised.json()["current_stage"] == "knowledge_selection"
    assert set(revised.json()["approvals"]) == {"concept", "visual", "3d", "music", "logic"}
    assert revised.json()["artifacts"]["local_revision_resume"]["data"]["stage"] == "ready_to_build"


def test_local_revision_returns_to_the_original_working_stage_after_reapproval(client: TestClient) -> None:
    project_id = create_ready_project(client)
    assert client.post(f"/projects/{project_id}/revise/visual").status_code == 200
    assert client.post(f"/projects/{project_id}/generate/visual").status_code == 200
    returned = client.post(f"/projects/{project_id}/approve/visual")
    assert returned.status_code == 200
    assert returned.json()["current_stage"] == "ready_to_build"
    assert set(returned.json()["approvals"]) == {"concept", "visual", "3d", "music", "logic"}


def test_revision_started_from_its_review_stage_continues_to_the_next_stage(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea": "概念修改后继续视觉"})
    assert client.post(f"/projects/{project_id}/generate/concept").status_code == 200
    assert client.post(f"/projects/{project_id}/revise/concept").status_code == 200
    assert client.post(f"/projects/{project_id}/generate/concept").status_code == 200
    approved = client.post(f"/projects/{project_id}/approve/concept")
    assert approved.status_code == 200
    assert approved.json()["current_stage"] == "visual_drafting"


def test_music_version_can_be_deleted_while_reviewing_it_from_build_stage(client: TestClient) -> None:
    project_id = create_ready_project(client)
    before = client.get(f"/projects/{project_id}").json()
    tracks = before["artifacts"]["music"]["data"]["tracks"]
    assert tracks
    response = client.delete(f"/projects/{project_id}/music/tracks/{tracks[-1]['id']}")
    assert response.status_code == 200
    changed = response.json()
    assert changed["current_stage"] in {"music_review", "music_drafting"}
    assert "music" not in changed["approvals"]
    assert "logic" not in changed["approvals"]
    reloaded = client.get(f"/projects/{project_id}").json()
    assert "music" not in reloaded["approvals"]
    assert "logic" not in reloaded["approvals"]


def test_curated_asset_can_be_added_selected_and_persisted(client: TestClient) -> None:
    project_id = create_project(client)
    assets = client.get(f"/assets?project_id={project_id}").json()
    source = next(asset for asset in assets if asset["id"] == "curated-color-forest")
    assert source["scope"] == "LIBRARY"

    used = client.post(f"/projects/{project_id}/assets/{source['id']}/use")
    assert used.status_code == 200
    selected_id = used.json()["selected_assets"]["IMAGE"]
    assert selected_id == f"{project_id}:library:{source['id']}"

    persisted = client.get(f"/projects/{project_id}").json()
    assert persisted["selected_assets"]["IMAGE"] == selected_id
    project_assets = client.get(f"/assets?project_id={project_id}").json()
    selected = next(asset for asset in project_assets if asset["id"] == selected_id)
    assert selected["scope"] == "PROJECT"
    assert selected["metadata"]["selected"] is True


def test_concurrent_approval_is_serialized(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea": "测试并发审批门"})
    client.post(f"/projects/{project_id}/generate/concept")

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _: client.post(f"/projects/{project_id}/approve/concept").status_code, range(2)))

    assert statuses == [200, 409]
    persisted = client.get(f"/projects/{project_id}").json()
    assert persisted["current_stage"] == "visual_drafting"
    assert list(persisted["approvals"]) == ["concept"]


def test_agent_uses_mock_without_key(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    project_id = create_project(client)
    response = client.post(
        "/agent/respond",
        json={"project_id": project_id, "message": "帮我分析核心机制", "mode": "chat"},
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "mock"
    assert response.json()["demo_mode"] is True


def test_unity_change_requires_valid_asset_and_can_be_rejected(client: TestClient) -> None:
    project_id = create_ready_project(client)
    invalid = client.post(f"/projects/{project_id}/unity/changes/preview", json={"action": "add_asset", "asset_id": "asset-3", "object_name": "错误图片"})
    assert invalid.status_code == 400
    assets = client.get(f"/assets?project_id={project_id}").json()
    model = next(asset for asset in assets if asset["type"] == "3D")
    preview = client.post(f"/projects/{project_id}/unity/changes/preview", json={"action": "add_asset", "asset_id": model["id"], "object_name": "玩家资产_测试漆碗"})
    assert preview.status_code == 201
    assert preview.json()["status"] == "preview"
    rejected = client.post(f"/unity/changes/{preview.json()['id']}/decision", json={"decision": "reject"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_unity_change_approval_and_undo_persist_receipts(monkeypatch, client: TestClient) -> None:
    async def fake_apply(payload: dict) -> dict:
        return {"success": True, "id": payload["id"], "checkpointPath": "Assets/QIWEN/Checkpoints/test.unity", "originalScenePath": "Assets/QIWEN/Scenes/test.unity", "generatedScriptPath": ""}

    monkeypatch.setattr("app.main.apply_co_creation", fake_apply)
    project_id = create_ready_project(client)
    preview = client.post(f"/projects/{project_id}/unity/changes/preview", json={"action": "request_interaction", "object_name": "玩家资产_测试漆碗", "template_id": "simulation-layering", "interaction": "点击增加薄髹层"})
    approved = client.post(f"/unity/changes/{preview.json()['id']}/decision", json={"decision": "approve"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "applied"
    assert approved.json()["checkpoint_path"].endswith("test.unity")
    undone = client.post(f"/unity/changes/{preview.json()['id']}/undo", json={})
    assert undone.status_code == 200
    assert undone.json()["status"] == "undone"
    assert undone.json()["receipt"]["undo_receipt"]["success"] is True


def test_playtest_revision_invalidates_then_refreshes_logic_approval(monkeypatch, client: TestClient) -> None:
    async def fake_play() -> dict:
        return {"success": True, "playMode": True, "message": "测试试玩"}

    async def fake_apply(payload: dict) -> dict:
        return {"success": True, "id": payload["id"], "checkpointPath": "Assets/QIWEN/Checkpoints/playtest.unity", "originalScenePath": "Assets/QIWEN/Scenes/playtest.unity", "generatedScriptPath": "Assets/QIWEN/Generated/CoCreation/test.cs", "compilerErrors": 0, "playMode": True}

    monkeypatch.setattr("app.main.start_playtest_in_unity", fake_play)
    monkeypatch.setattr("app.main.apply_co_creation", fake_apply)
    project_id = create_ready_project(client)
    before = client.get(f"/projects/{project_id}").json()
    original_logic_version = before["versions"]["logic"]
    started = client.post(f"/projects/{project_id}/playtests/start", json={})
    assert started.status_code == 201
    playtest_id = started.json()["id"]
    feedback = client.post(f"/playtests/{playtest_id}/feedback", json={"feedback": "层积反馈太快，需要更清晰节奏", "rating": 3})
    assert feedback.json()["status"] == "feedback"
    proposed = client.post(f"/playtests/{playtest_id}/propose-revision", json={"object_name": "玩家资产_测试", "template_id": "timing-polish"})
    assert proposed.status_code == 200
    stale = proposed.json()["project"]
    assert stale["current_stage"] == "logic_review"
    assert "logic" not in stale["approvals"]
    assert stale["versions"]["logic"] == original_logic_version + 1
    approved = client.post(f"/playtests/{playtest_id}/approve-revision", json={})
    assert approved.status_code == 200
    assert approved.json()["playtest"]["status"] == "replaying"
    fresh = approved.json()["project"]
    assert fresh["current_stage"] == "playtesting"
    assert fresh["approvals"]["logic"]["version"] == original_logic_version + 1
    completed = client.post(f"/playtests/{playtest_id}/complete", json={"feedback": "节奏已清晰", "rating": 5})
    assert completed.status_code == 200
    assert completed.json()["status"] == "awaiting_final_approval"
    assert completed.json()["final_rating"] == 5
    waiting = client.get(f"/projects/{project_id}").json()
    assert waiting["current_stage"] == "playtesting"
    assert "final" not in waiting["approvals"]
    finished = client.post(f"/projects/{project_id}/finish")
    assert finished.status_code == 200
    assert finished.json()["current_stage"] == "completed"
    assert finished.json()["approvals"]["final"]["comment"] == "玩家明确确认完成项目"


def test_research_timeline_metrics_and_anonymous_exports(client: TestClient) -> None:
    project_id = create_ready_project(client)
    research = client.get(f"/projects/{project_id}/research")
    assert research.status_code == 200
    payload = research.json()
    assert payload["anonymized_project_id"] != project_id
    assert payload["metrics"]["timeline_events"] > 0
    assert payload["metrics"]["approval_events"] == 5
    assert payload["metrics"]["version_counts"]["logic"] == 1
    assert all(item["approved_by"] == "player" for item in payload["approval_history"])

    exported_json = client.post(f"/projects/{project_id}/research/export?format=json")
    assert exported_json.status_code == 200
    assert exported_json.headers["content-type"].startswith("application/json")
    text = exported_json.content.decode("utf-8")
    assert project_id not in text
    assert "DEEPSEEK_API_KEY" not in text
    assert "generated_script" not in text
    assert "建立可撤销的 Unity 共创测试" not in text

    exported_csv = client.post(f"/projects/{project_id}/research/export?format=csv")
    assert exported_csv.status_code == 200
    assert exported_csv.content.startswith(b"\xef\xbb\xbf")
    assert b"anonymized_project_id" in exported_csv.content


def test_project_and_related_records_reload_from_database(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea": "保存这个跨重启项目"})
    client.post(f"/projects/{project_id}/generate/concept")
    client.post(f"/projects/{project_id}/approve/concept")
    first = client.get(f"/projects/{project_id}").json()
    second = client.get(f"/projects/{project_id}").json()
    diagnostic = client.get(f"/projects/{project_id}/persistence").json()

    assert second == first
    assert second["current_stage"] == "visual_drafting"
    assert second["progress"] == 20
    assert diagnostic["counts"]["versions"] == 1
    assert diagnostic["counts"]["approvals"] == 1
    assert diagnostic["counts"]["chat"] == 1
    assert diagnostic["counts"]["assets"] == 4
    assert diagnostic["counts"]["outbox"] == diagnostic["counts"]["activity"]


@pytest.mark.asyncio
async def test_deepseek_routes_code_to_pro(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {}

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": [{"message": {"content": "安全的代码结构提议"}}], "usage":{"prompt_tokens":100,"completion_tokens":20}}

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            captured["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-secret")
    monkeypatch.setattr("app.providers.httpx.AsyncClient", FakeClient)
    project = Project(selected_knowledge_id="thin-layers", player_idea="节奏髹漆")
    result = await DeepSeekLLMProvider().respond(
        AgentRequest(project_id=project.id, message="提出代码结构", mode="code"),
        project,
        KNOWLEDGE[0],
    )
    assert result.provider == "deepseek"
    assert result.model == "deepseek-v4-pro"
    assert captured["json"]["model"] == "deepseek-v4-pro"
    assert captured["json"]["thinking"] == {"type": "enabled"}
    assert captured["headers"]["Authorization"] == "Bearer test-only-secret"
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.cost_cny > 0


def test_multi_round_history_original_idea_and_suggestion_decision(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea":"我想做等待与节奏结合的游戏"})
    client.post(f"/projects/{project_id}/idea", json={"idea":"再加入逐层显现"})
    first = client.post("/agent/respond", json={"project_id":project_id,"message":"先分析等待","mode":"chat"})
    second = client.post("/agent/respond", json={"project_id":project_id,"message":"我不喜欢太快的节奏","mode":"chat"})
    assert first.status_code == second.status_code == 200
    assert first.json()["suggestion_id"]
    project = client.get(f"/projects/{project_id}").json()
    assert project["original_player_idea"] == "我想做等待与节奏结合的游戏"
    assert len(project["conversation_history"]) == 6
    assert project["conversation_history"][-2]["content"] == "我不喜欢太快的节奏"
    decision = client.post(f"/agent/suggestions/{first.json()['suggestion_id']}/respond", json={"action":"rejected","note":"保持缓慢"})
    assert decision.status_code == 200
    duplicate = client.post(f"/agent/suggestions/{first.json()['suggestion_id']}/respond", json={"action":"accepted","note":""})
    assert duplicate.status_code == 409
    diagnostic = client.get(f"/projects/{project_id}/persistence").json()["counts"]
    assert diagnostic["suggestions"] == 2
    assert diagnostic["llm_calls"] == 2


def test_mock_structured_concept_has_explained_alignment(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea":"把薄髹做成精度游戏"})
    generated = client.post(f"/projects/{project_id}/generate/concept")
    assert generated.status_code == 200
    alignment = generated.json()["artifacts"]["concept"]["data"]["alignment"]
    assert alignment["score"] in {"Strong", "Moderate", "Weak"}
    assert alignment["mechanic_mapping"]
    assert alignment["explanation"]


def test_budget_gate_requires_explicit_choice(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-secret")
    monkeypatch.setattr("app.main.settings.api_monthly_budget_cny", 0)
    project_id = create_project(client)
    response = client.post("/agent/respond", json={"project_id":project_id,"message":"不要产生付费请求","mode":"chat"})
    assert response.status_code == 402
    detail = response.json()["detail"]
    assert detail["code"] == "monthly_budget_requires_choice"
    assert "改用模拟服务" in detail["choices"]


def test_agent_sse_emits_status_and_persists_completion(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    project_id = create_project(client)
    with client.stream("POST", "/agent/respond/stream", json={"project_id":project_id,"message":"流式讨论","mode":"chat"}) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "event: status" in body
    assert "event: complete" in body
    project = client.get(f"/projects/{project_id}").json()
    assert project["conversation_history"][-1]["role"] == "assistant"


def test_asset_regeneration_preserves_versions_and_generated_asset_hashes(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    for key in ("VOLC_ACCESSKEY","VOLC_SECRETKEY","HUNYUAN3D_API_KEY","TENCENT_SECRET_ID","TENCENT_SECRET_KEY"):
        monkeypatch.delenv(key,raising=False)
    project_id=create_project(client)
    client.post(f"/projects/{project_id}/idea",json={"idea":"测试图像版本保留"})
    client.post(f"/projects/{project_id}/generate/concept")
    client.post(f"/projects/{project_id}/approve/concept")
    first=client.post(f"/projects/{project_id}/generate/visual")
    assert first.status_code == 200
    assert first.json()["artifacts"]["visual"]["data"]["provider"] == "mock-image"
    reopened=client.post(f"/projects/{project_id}/reopen/visual")
    assert reopened.json()["current_stage"] == "visual_drafting"
    second=client.post(f"/projects/{project_id}/generate/visual")
    assert second.json()["versions"]["visual"] == 2
    assert all(item["sha256"] for item in second.json()["artifacts"]["visual"]["data"]["ingested"])
    counts=client.get(f"/projects/{project_id}/persistence").json()["counts"]
    assert counts["versions"] == 3
    assert counts["assets"] == 12


def test_player_started_unity_build_uses_generated_safe_code(monkeypatch, client: TestClient) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    captured = {}

    async def fake_start(payload):
        captured.update(payload)
        return {"id": "mock-unity-job", "projectId": payload["projectId"], "status": "排队中", "adapter": "测试桥接", "events": []}

    monkeypatch.setattr("app.main.start_unity_build", fake_start)
    project_id = create_project(client)
    client.post(f"/projects/{project_id}/idea", json={"idea": "让漆碗旋转并播放已批准音乐"})
    for kind in ("concept", "visual", "3d", "music", "logic"):
        assert client.post(f"/projects/{project_id}/generate/{kind}").status_code == 200
        assert client.post(f"/projects/{project_id}/approve/{kind}").status_code == 200

    response = client.post(f"/projects/{project_id}/unity/build")
    assert response.status_code == 202
    assert response.json()["id"] == "mock-unity-job"
    assert "namespace QIWEN.Runtime" in captured["runtimeScript"]
    assert "class LacquerBowlExperience" in captured["runtimeScript"]
    assert "System.IO" not in captured["runtimeScript"]
    assert captured["buildPlan"]["template_id"] in {"simulation-layering", "timing-polish", "collection-materials", "puzzle-process", "target-lacquer-drops", "topdown-dodge"}
    assert captured["buildPlan"]["game_title"]
    project = client.get(f"/projects/{project_id}").json()
    assert "代码来源 mock/mock-unity-code-v1" in project["activity_log"][-1]
