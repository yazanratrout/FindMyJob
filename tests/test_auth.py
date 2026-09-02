import pytest

pytestmark = pytest.mark.usefixtures("seeded_session")


def test_status_starts_unconfigured(unauth_client):
    body = unauth_client.get("/api/auth/status").json()
    assert body == {"configured": False, "authenticated": False}


def test_setup_then_authenticated(unauth_client):
    resp = unauth_client.post("/api/auth/setup", json={"passphrase": "hunter2-long"})
    assert resp.status_code == 201
    assert resp.json() == {"configured": True, "authenticated": True}
    assert unauth_client.get("/api/auth/status").json()["authenticated"] is True


def test_setup_rejects_short_passphrase(unauth_client):
    assert unauth_client.post("/api/auth/setup", json={"passphrase": "short"}).status_code == 422


def test_setup_twice_conflicts(unauth_client):
    unauth_client.post("/api/auth/setup", json={"passphrase": "first-passphrase"})
    assert (
        unauth_client.post("/api/auth/setup", json={"passphrase": "second-passphrase"}).status_code
        == 409
    )


def test_login_logout_cycle(unauth_client):
    unauth_client.post("/api/auth/setup", json={"passphrase": "correct-horse"})
    unauth_client.post("/api/auth/logout")
    assert unauth_client.get("/api/auth/status").json()["authenticated"] is False

    assert unauth_client.post("/api/auth/login", json={"passphrase": "wrong"}).status_code == 401
    ok = unauth_client.post("/api/auth/login", json={"passphrase": "correct-horse"})
    assert ok.status_code == 200
    assert unauth_client.get("/api/auth/status").json()["authenticated"] is True


def test_guarded_routes_require_auth(unauth_client):
    assert unauth_client.get("/api/profile").status_code == 401
    assert unauth_client.get("/api/settings").status_code == 401
    assert unauth_client.get("/api/health").status_code == 200  # health is open

    unauth_client.post("/api/auth/setup", json={"passphrase": "let-me-in-please"})
    assert unauth_client.get("/api/profile").status_code == 200
