import pytest
from pydantic import BaseModel
from sqlmodel import Session, select
from tests.fakes import scripted_api_fn

from findmyjob.db import get_engine
from findmyjob.llm.client import LlmClient, LlmError
from findmyjob.models.enums import LlmPurpose
from findmyjob.models.run import LlmCall
from findmyjob.services.cost import current_month_cost_eur

pytestmark = pytest.mark.usefixtures("seeded_session")


class Shape(BaseModel):
    name: str
    score: int


def test_complete_records_call_and_cost():
    client = LlmClient(api_fn=scripted_api_fn("hello", in_tokens=1_000_000, out_tokens=0))
    res = client.complete(purpose=LlmPurpose.ANALYZE, system="s", user="u", tier="cheap")
    assert res.text == "hello"
    assert res.cost_eur == pytest.approx(0.80, rel=1e-3)  # 1M input tokens @ cheap_in
    with Session(get_engine()) as s:
        call = s.exec(select(LlmCall)).one()
        assert call.purpose == LlmPurpose.ANALYZE
        assert call.cache_hit is False


def test_offline_mode_returns_canned_schema_valid_json(monkeypatch):
    from findmyjob.config import get_settings
    from findmyjob.llm.analyzer import JobAnalysisResult
    from findmyjob.llm.judge import JudgeResult

    monkeypatch.setattr(get_settings(), "llm_offline", True)
    client = LlmClient()  # no api_fn -> offline stub

    analysis, res = client.complete_json(
        purpose=LlmPurpose.ANALYZE, system="s", user="u", schema=JobAnalysisResult
    )
    assert res.cost_eur == 0.0 and res.model.startswith("offline/")
    assert analysis.contract_type == "werkstudent" and analysis.weekly_hours == 20

    judged, _ = client.complete_json(
        purpose=LlmPurpose.JUDGE, system="s", user="u", schema=JudgeResult, tier="smart"
    )
    assert 0 <= judged.holistic_fit <= 100

    with Session(get_engine()) as s:
        assert all(c.cost_eur == 0.0 for c in s.exec(select(LlmCall)).all())


def test_openai_compatible_provider(monkeypatch):
    import httpx
    import respx

    from findmyjob.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "openai")
    monkeypatch.setattr(s, "llm_openai_base_url", "https://api.groq.test/openai/v1")
    monkeypatch.setattr(s, "llm_openai_api_key", "gsk_x")
    monkeypatch.setattr(s, "llm_model_cheap", "llama-3.1-8b-instant")

    with respx.mock:
        route = respx.post("https://api.groq.test/openai/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"name": "x", "score": 3}'}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                },
            )
        )
        client = LlmClient()
        shape, res = client.complete_json(
            purpose=LlmPurpose.ANALYZE, system="s", user="u", schema=Shape
        )

    assert route.called
    assert shape.name == "x" and shape.score == 3
    assert res.cost_eur == 0.0  # non-anthropic provider is billed elsewhere
    assert res.model == "llama-3.1-8b-instant"
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer gsk_x"


def test_injected_api_fn_overrides_offline(monkeypatch):
    from findmyjob.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_offline", True)
    client = LlmClient(api_fn=scripted_api_fn("real", in_tokens=10, out_tokens=5))
    assert client.complete(purpose=LlmPurpose.ANALYZE, system="s", user="u").text == "real"


def test_identical_prompt_is_served_from_cache():
    client = LlmClient(api_fn=scripted_api_fn("once", in_tokens=500, out_tokens=100))
    first = client.complete(purpose=LlmPurpose.ANALYZE, system="s", user="u")
    second = client.complete(purpose=LlmPurpose.ANALYZE, system="s", user="u")
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.cost_eur == 0.0
    with Session(get_engine()) as s:
        calls = s.exec(select(LlmCall)).all()
        assert len(calls) == 2
        assert sum(c.cost_eur for c in calls) == first.cost_eur


def test_complete_json_parses_fenced_output():
    client = LlmClient(api_fn=scripted_api_fn('```json\n{"name": "x", "score": 7}\n```'))
    obj, _ = client.complete_json(purpose=LlmPurpose.ANALYZE, system="s", user="u", schema=Shape)
    assert obj == Shape(name="x", score=7)


def test_complete_json_repairs_once():
    client = LlmClient(api_fn=scripted_api_fn("not json at all", '{"name": "y", "score": 3}'))
    obj, _ = client.complete_json(purpose=LlmPurpose.ANALYZE, system="s", user="u", schema=Shape)
    assert obj.name == "y"


def test_complete_json_raises_after_failed_repair():
    client = LlmClient(api_fn=scripted_api_fn("garbage", "still garbage"))
    with pytest.raises(LlmError, match="invalid JSON"):
        client.complete_json(purpose=LlmPurpose.ANALYZE, system="s", user="u", schema=Shape)


def test_current_month_cost_sums_calls():
    client = LlmClient(api_fn=scripted_api_fn("a", "b", in_tokens=1_000_000, out_tokens=0))
    client.complete(purpose=LlmPurpose.ANALYZE, system="s", user="u1")
    client.complete(purpose=LlmPurpose.JUDGE, system="s", user="u2", tier="smart")
    with Session(get_engine()) as s:
        assert current_month_cost_eur(s) == pytest.approx(0.80 + 2.80, rel=1e-3)
