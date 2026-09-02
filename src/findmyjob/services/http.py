"""Shared async HTTP client for job-source connectors.

Adds three things over a bare ``httpx.AsyncClient``:

* a **per-host minimum interval** between requests (polite rate limiting);
* **retry with backoff** on 429 / 5xx / transport errors;
* a **stable User-Agent** identifying the tool.

One instance is created per pipeline run and shared by every connector.
"""

from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = "FindMyJob/0.1 (+https://github.com/; personal job search)"

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


class HttpClient:
    def __init__(
        self,
        *,
        min_interval_s: float = 1.5,
        timeout: float = 15.0,
        max_attempts: int = 3,
        retry_max_wait_s: float = 8.0,
        user_agent: str = USER_AGENT,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )
        self._min_interval = min_interval_s
        self._max_attempts = max_attempts
        self._retry_max_wait = retry_max_wait_s
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _throttle(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            elapsed = time.monotonic() - self._last_request.get(host, 0.0)
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request[host] = time.monotonic()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        host = httpx.URL(url).host
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=0.5, max=self._retry_max_wait),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        ):
            with attempt:
                await self._throttle(host)
                response = await self._client.request(method, url, params=params, headers=headers)
                response.raise_for_status()
                return response
        raise AssertionError("unreachable")  # pragma: no cover

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.request("GET", url, params=params, headers=headers)
        return response.json()

    async def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        response = await self.request("GET", url, params=params, headers=headers)
        return response.text
