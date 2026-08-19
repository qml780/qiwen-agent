import pytest

from app.domain import AgentRequest
from app.providers import MicuLLMProvider, _redact_provider_message
from app.domain import Approval, KnowledgeEntry, Project


def test_provider_errors_redact_api_keys():
    assert _redact_provider_message("Incorrect API key: sk-secretvalue123") == "Incorrect API key: sk-***"


def test_micu_uses_flat_cost_estimate_when_token_prices_are_unset():
    provider = MicuLLMProvider()
    assert provider._price(provider.chat_model, 100, 20) == 0.1


@pytest.mark.asyncio
async def test_micu_responses_contract(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        text = ""
        def raise_for_status(self): pass
        def json(self):
            return {"id": "resp-1", "choices": [{"message": {"content": "保留你的想法。"}}], "usage": {"prompt_tokens": 12, "completion_tokens": 5}}

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return Response()

    monkeypatch.setenv("MICU_LLM_API_KEY", "llm-key")
    monkeypatch.setattr("app.providers.httpx.AsyncClient", Client)
    provider = MicuLLMProvider()
    data = await provider._post({"model": "gpt-5.6-terra", "messages": [{"role": "system", "content": "中文"}, {"role": "user", "content": "你好"}], "max_tokens": 30})
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["json"]["messages"] == [{"role": "system", "content": "中文"}, {"role": "user", "content": "你好"}]
    assert data["choices"][0]["message"]["content"] == "保留你的想法。"


def test_concept_generation_context_excludes_later_artifacts():
    provider = MicuLLMProvider()
    project = Project(
        selected_knowledge_id="thin-layers",
        player_idea="测试",
        original_player_idea="测试",
        artifacts={
            "concept": {"version": 1, "data": {"game_name": "旧概念"}},
            "visual": {"version": 1, "data": {"variants": ["很大的视觉内容"]}},
            "logic": {"version": 1, "data": {"acceptance": ["很大的逻辑内容"]}},
        },
        approvals={
            "concept": Approval(artifact="concept", version=1),
            "visual": Approval(artifact="visual", version=1),
            "logic": Approval(artifact="logic", version=1),
        },
    )
    knowledge = KnowledgeEntry(id="thin-layers", category="工艺", title="薄髹", summary="知识", core_facts=[], cause_effect_relations=[], key_actions=[])

    context = provider._context(project, knowledge, kind="concept")

    assert "很大的视觉内容" not in context
    assert "很大的逻辑内容" not in context
