"""``/api/sources`` — list + toggle."""

import pytest

pytestmark = pytest.mark.usefixtures("seeded_session")


def test_list_sources_reports_enabled_and_configured(client):
    rows = client.get("/api/sources").json()
    keys = {r["key"] for r in rows}
    assert {"ba", "adzuna", "arbeitnow", "themuse", "greenhouse", "jsonld"} <= keys

    adzuna = next(r for r in rows if r["key"] == "adzuna")
    assert isinstance(adzuna["enabled"], bool)
    assert adzuna["configured"] is False  # no creds in the test env
    assert "adzuna_app_id" in adzuna["requires_secrets"]

    ba = next(r for r in rows if r["key"] == "ba")
    assert ba["configured"] is True  # needs no secret


def test_toggle_source_persists(client):
    on = client.put("/api/sources/arbeitnow", json={"enabled": True}).json()
    assert next(r for r in on if r["key"] == "arbeitnow")["enabled"] is True

    off = client.put("/api/sources/arbeitnow", json={"enabled": False}).json()
    assert next(r for r in off if r["key"] == "arbeitnow")["enabled"] is False

    settings = client.get("/api/settings").json()
    assert settings["sources_enabled"]["arbeitnow"] is False


def test_toggle_unknown_source_404(client):
    assert client.put("/api/sources/nope", json={"enabled": True}).status_code == 404


def test_sources_requires_auth(unauth_client):
    assert unauth_client.get("/api/sources").status_code == 401
