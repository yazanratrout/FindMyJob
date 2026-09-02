from datetime import date

import pytest
from sqlmodel import Session, select

from findmyjob.models.config import AppSettings
from findmyjob.models.geo import GeocodeCache
from findmyjob.services.geocode import geocode_city
from findmyjob.services.semester import add_term, is_in_lecture_period
from findmyjob.services.settings import get_app_settings, update_app_settings

pytestmark = pytest.mark.usefixtures("seeded_session")


def _fake_geocoder(calls: list[str]):
    def _fn(city: str) -> tuple[float, float] | None:
        calls.append(city)
        return (48.137, 11.575)

    return _fn


def test_update_writes_and_geocodes(db_session: Session):
    calls: list[str] = []
    row = update_app_settings(
        db_session,
        {"target_city": "München", "radius_km": 25, "hours_max": 20},
        geocoder=_fake_geocoder(calls),
    )
    db_session.commit()
    assert row.radius_km == 25
    assert row.target_lat == pytest.approx(48.137)
    assert calls == ["München"]


def test_geocode_result_is_cached(db_session: Session):
    calls: list[str] = []
    geocoder = _fake_geocoder(calls)
    geocode_city(db_session, "Berlin", geocoder=geocoder)
    geocode_city(db_session, "Berlin", geocoder=geocoder)
    assert calls == ["Berlin"]  # second call served from cache
    assert db_session.exec(select(GeocodeCache)).one().lat == pytest.approx(48.137)


def test_validation_rejects_bad_threshold_order(db_session: Session):
    with pytest.raises(ValueError, match="score_threshold_maybe"):
        update_app_settings(
            db_session,
            {"score_threshold_maybe": 90, "score_threshold_recommend": 60},
        )


def test_validation_rejects_unknown_source(db_session: Session):
    with pytest.raises(ValueError, match="unknown sources"):
        update_app_settings(db_session, {"sources_enabled": {"linkedin": True}})


def test_unknown_keys_are_ignored(db_session: Session):
    update_app_settings(db_session, {"nonsense": 1, "radius_km": 40})
    db_session.commit()
    assert get_app_settings(db_session).radius_km == 40


def test_semester_lecture_period(db_session: Session):
    add_term(
        db_session,
        label="WS 2026/27",
        lecture_start=date(2026, 10, 13),
        lecture_end=date(2027, 2, 7),
    )
    db_session.commit()
    assert is_in_lecture_period(db_session, date(2026, 11, 1)) is True
    assert is_in_lecture_period(db_session, date(2027, 3, 1)) is False


def test_settings_api_roundtrip(client):
    resp = client.put(
        "/api/settings", json={"radius_km": 15, "target_titles": ["Werkstudent Data"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["radius_km"] == 15
    assert client.get("/api/settings").json()["target_titles"] == ["Werkstudent Data"]


def test_settings_api_rejects_extra_fields(client):
    assert client.put("/api/settings", json={"totally_unknown": 1}).status_code == 422


def test_settings_api_validation_error(client):
    resp = client.put("/api/settings", json={"blend_soft_ratio": 5})
    assert resp.status_code == 422


def test_keyword_suggest_endpoint(client, monkeypatch):
    from findmyjob.llm.client import LlmResult
    from findmyjob.llm.keyword_suggest import KeywordSuggestions

    def fake_suggest(*, target_fields, target_titles, skills, client=None, run_id=None):
        return KeywordSuggestions(core=["data science"], likely_noise=["sales"]), LlmResult(
            text="{}",
            model="m",
            tier="cheap",
            input_tokens=1,
            output_tokens=1,
            cost_eur=0.0,
            cache_hit=False,
        )

    monkeypatch.setattr("findmyjob.api.routes.settings.suggest_keywords", fake_suggest)
    resp = client.post("/api/settings/suggest-keywords", json={"target_fields": ["Data"]})
    assert resp.status_code == 200
    assert resp.json()["core"] == ["data science"]


def test_semester_term_api(client):
    created = client.post(
        "/api/semester-terms",
        json={"label": "SS 2026", "lecture_start": "2026-04-13", "lecture_end": "2026-07-18"},
    )
    assert created.status_code == 201
    term_id = created.json()["id"]
    assert len(client.get("/api/semester-terms").json()) == 1
    assert client.delete(f"/api/semester-terms/{term_id}").status_code == 204
    assert client.get("/api/semester-terms").json() == []


def test_app_settings_singleton_unchanged_count(seeded_session: Session):
    assert len(seeded_session.exec(select(AppSettings)).all()) == 1
