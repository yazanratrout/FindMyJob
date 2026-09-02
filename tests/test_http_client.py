import httpx
import pytest
import respx

from findmyjob.services.http import HttpClient


@pytest.fixture
def http() -> HttpClient:
    return HttpClient(min_interval_s=0.0, max_attempts=3, retry_max_wait_s=0.0)


@respx.mock
async def test_get_json_returns_payload(http: HttpClient):
    respx.get("https://example.test/api").mock(return_value=httpx.Response(200, json={"ok": True}))
    assert await http.get_json("https://example.test/api") == {"ok": True}
    await http.aclose()


@respx.mock
async def test_retries_then_succeeds(http: HttpClient):
    route = respx.get("https://flaky.test/x")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"n": 1}),
    ]
    assert await http.get_json("https://flaky.test/x") == {"n": 1}
    assert route.call_count == 2
    await http.aclose()


@respx.mock
async def test_gives_up_after_max_attempts(http: HttpClient):
    respx.get("https://down.test/x").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await http.get_json("https://down.test/x")
    await http.aclose()


@respx.mock
async def test_does_not_retry_client_error(http: HttpClient):
    route = respx.get("https://nope.test/x").mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await http.get_json("https://nope.test/x")
    assert route.call_count == 1
    await http.aclose()
