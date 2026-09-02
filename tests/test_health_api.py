def test_health_endpoint_reports_db_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db_ok"] is True
    assert body["version"]


def test_openapi_served_under_api_prefix(client):
    assert client.get("/api/openapi.json").status_code == 200
