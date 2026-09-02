"""Minimal, cached robots.txt gate for HTML fetches.

Used by connectors that read company career pages directly (JSON-LD). API
endpoints are not subject to this. A missing / unfetchable robots.txt is
treated as "allowed".
"""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

import httpx

from findmyjob.services.http import USER_AGENT, HttpClient

_UA_TOKEN = "FindMyJob"


class RobotsCache:
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._parsers: dict[str, RobotFileParser | None] = {}

    async def allowed(self, url: str) -> bool:
        parsed = httpx.URL(url)
        host = f"{parsed.scheme}://{parsed.host}"
        if host not in self._parsers:
            self._parsers[host] = await self._load(host)
        parser = self._parsers[host]
        if parser is None:
            return True
        return parser.can_fetch(_UA_TOKEN, url) or parser.can_fetch(USER_AGENT, url)

    async def _load(self, host: str) -> RobotFileParser | None:
        try:
            text = await self._http.get_text(f"{host}/robots.txt")
        except Exception:
            return None
        parser = RobotFileParser()
        parser.parse(text.splitlines())
        return parser
