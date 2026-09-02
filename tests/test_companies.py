import pytest
from sqlmodel import Session

from findmyjob.models.enums import AtsType
from findmyjob.services.companies import (
    CompanyError,
    add_company,
    company_refs,
    detect_ats,
    update_company,
)

pytestmark = pytest.mark.usefixtures("seeded_session")


def test_company_refs_only_returns_queryable(db_session: Session):
    add_company(db_session, {"name": "HasSlug", "ats_type": "greenhouse", "ats_slug": "hasslug"})
    add_company(db_session, {"name": "NoSlug", "ats_type": "greenhouse"})
    add_company(db_session, {"name": "JsonLd", "careers_url": "https://x.test/jobs"})
    add_company(db_session, {"name": "Nothing"})
    db_session.commit()

    names = {r.name for r in company_refs(db_session)}
    assert "HasSlug" in names
    assert "JsonLd" in names
    assert "NoSlug" not in names
    assert "Nothing" not in names


def test_add_company_rejects_duplicate(db_session: Session):
    add_company(db_session, {"name": "Zeta Test Labs GmbH"})
    db_session.commit()
    with pytest.raises(CompanyError, match="already exists"):
        add_company(db_session, {"name": "Zeta Test Labs"})  # normalizes to same key


def test_update_company_changes_ats(db_session: Session):
    c = add_company(db_session, {"name": "Foo"})
    db_session.commit()
    update_company(db_session, c.id, {"ats_type": "lever", "ats_slug": "foo"})
    db_session.commit()
    db_session.refresh(c)
    assert c.ats_type == AtsType.LEVER


@pytest.mark.parametrize(
    ("url", "expected_type", "expected_slug"),
    [
        ("https://boards.greenhouse.io/celonis", "greenhouse", "celonis"),
        ("https://jobs.lever.co/flixbus/", "lever", "flixbus"),
        ("https://inovex.jobs.personio.de/", "personio", "inovex"),
        ("https://jobs.ashbyhq.com/scalablecapital", "ashby", "scalablecapital"),
        ("https://www.example.com/careers", "none", None),
    ],
)
async def test_detect_ats_from_url(url, expected_type, expected_slug):
    result = await detect_ats(url)
    assert result["ats_type"] == expected_type
    assert result["ats_slug"] == expected_slug


async def test_detect_ats_falls_back_to_html():
    async def fake_fetch(_url: str) -> str:
        return '<a href="https://boards.greenhouse.io/hiddenco/jobs">Careers</a>'

    result = await detect_ats("https://hiddenco.com/jobs", fetch_text=fake_fetch)
    assert result == {"ats_type": "greenhouse", "ats_slug": "hiddenco"}


def test_company_api_crud(client):
    created = client.post(
        "/api/companies",
        json={"name": "My Startup", "ats_type": "lever", "ats_slug": "mystartup"},
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    assert client.put(f"/api/companies/{cid}", json={"is_favorite": True}).json()["is_favorite"]
    assert client.post("/api/companies", json={"name": "My Startup"}).status_code == 409
    assert client.delete(f"/api/companies/{cid}").status_code == 204


def test_company_detect_endpoint(client):
    resp = client.post("/api/companies/detect", json={"careers_url": "https://jobs.lever.co/acme"})
    assert resp.json() == {"ats_type": "lever", "ats_slug": "acme"}
