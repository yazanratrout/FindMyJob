import json

import pytest
from sqlmodel import Session, col, select

from findmyjob.llm.profile_parser import ParsedProfile
from findmyjob.models.enums import DegreeLevel, SkillCategory
from findmyjob.models.profile import ProfileSkill
from findmyjob.services.profile import (
    apply_parsed_profile,
    get_profile,
    set_skills,
    update_profile,
)

pytestmark = pytest.mark.usefixtures("seeded_session")

PARSED = ParsedProfile.model_validate(
    {
        "full_name": "Yazan R.",
        "email": "y@example.com",
        "address": {"city": "München", "country": "Germany"},
        "nationality": "Jordanian",
        "is_eu_eea": False,
        "university": "TU München",
        "program": "M.Sc. Data Engineering",
        "degree_level": "master",
        "current_semester": 2,
        "skills": [
            {"name": "Python", "category": "technical", "proficiency": 4, "evidence": "3y"},
            {"name": "dbt", "category": "tool", "proficiency": 3, "evidence": "project"},
        ],
        "languages": [{"lang": "German", "cefr": "B2"}, {"lang": "English", "cefr": "C1"}],
    }
)


def test_apply_parsed_profile_populates_fields_and_skills(db_session: Session):
    profile = apply_parsed_profile(db_session, PARSED)
    db_session.commit()

    assert profile.full_name == "Yazan R."
    assert profile.degree_level == DegreeLevel.MASTER
    assert profile.is_eu_eea is False
    assert profile.city == "München"
    assert json.loads(json.dumps(profile.structured_json))["program"] == "M.Sc. Data Engineering"

    skills = db_session.exec(select(ProfileSkill)).all()
    names = {s.name for s in skills}
    assert {"Python", "dbt", "German", "English"} <= names
    assert any(s.category == SkillCategory.LANGUAGE for s in skills)


def test_locked_fields_survive_reparse(db_session: Session):
    update_profile(db_session, {"full_name": "Custom Name", "city": "Berlin"})
    db_session.commit()

    apply_parsed_profile(db_session, PARSED)
    db_session.commit()

    profile = get_profile(db_session)
    assert profile.full_name == "Custom Name"  # locked
    assert profile.city == "Berlin"  # locked
    assert profile.university == "TU München"  # not locked -> updated


def test_manual_skills_are_preserved_on_reparse(db_session: Session):
    set_skills(db_session, [{"name": "Python", "category": "technical", "proficiency": 5}])
    db_session.commit()

    apply_parsed_profile(db_session, PARSED)
    db_session.commit()

    pythons = db_session.exec(select(ProfileSkill).where(col(ProfileSkill.name) == "Python")).all()
    assert len(pythons) == 1
    assert pythons[0].source == "manual"
    assert pythons[0].proficiency == 5


def test_update_profile_ignores_unknown_keys(db_session: Session):
    profile = update_profile(db_session, {"full_name": "A", "nonsense": "x"})
    assert profile.full_name == "A"
    assert "nonsense" not in profile.locked_fields


def test_profile_api_roundtrip(client):
    client.put("/api/profile", json={"full_name": "Yaz", "city": "München"})
    body = client.get("/api/profile").json()
    assert body["full_name"] == "Yaz"
    assert "full_name" in body["locked_fields"]

    skills = client.put(
        "/api/profile/skills",
        json=[{"name": "SQL", "category": "technical", "proficiency": 4}],
    ).json()
    assert skills[0]["name"] == "SQL"
    assert client.get("/api/profile").json()["skills"][0]["source"] == "manual"


def test_parse_endpoint_uses_service(client, monkeypatch):
    from findmyjob.llm.client import LlmResult

    def fake_parse(sections, *, client=None, run_id=None):
        return PARSED, LlmResult(
            text="{}",
            model="m",
            tier="smart",
            input_tokens=10,
            output_tokens=5,
            cost_eur=0.01,
            cache_hit=False,
        )

    monkeypatch.setattr("findmyjob.services.profile.parse_profile", fake_parse)
    # Need at least one document with text for parse_and_apply to proceed.
    client.post(
        "/api/documents",
        data={"type": "cv"},
        files={"file": ("cv.txt", b"Python, SQL", "text/plain")},
    )
    resp = client.post("/api/profile/parse")
    assert resp.status_code == 200, resp.text
    assert resp.json()["profile"]["university"] == "TU München"
    assert resp.json()["cost_eur"] == 0.01
