"""Minimal Supervisor REST client.

Talks to the Supervisor with the credentials Home Assistant Core already
has (SUPERVISOR / SUPERVISOR_TOKEN environment variables), so it does not
depend on internal helpers of the hassio integration that change between
Core releases.
"""

from __future__ import annotations

import os
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout


class SupervisorError(Exception):
    """Supervisor API call failed."""


class SupervisorClient:
    """Calls the few Supervisor endpoints Community Apps needs."""

    def __init__(self, session: ClientSession) -> None:
        host = os.environ.get("SUPERVISOR")
        token = os.environ.get("SUPERVISOR_TOKEN")
        if not host or not token:
            raise SupervisorError("No Supervisor available")
        self._base = f"http://{host}"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._session = session

    async def _call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                self._base + path,
                json=payload,
                headers=self._headers,
                timeout=ClientTimeout(total=300),
            ) as resp:
                body = await resp.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise SupervisorError(f"{method} {path} failed: {type(err).__name__}") from err
        if not isinstance(body, dict) or body.get("result") != "ok":
            message = body.get("message") if isinstance(body, dict) else None
            raise SupervisorError(message or f"{method} {path} failed")
        return body.get("data")

    async def _get_dict(self, path: str) -> dict[str, Any]:
        data = await self._call("get", path)
        if not isinstance(data, dict):
            raise SupervisorError(f"GET {path} returned no data")
        return data

    async def repositories(self) -> list[dict[str, Any]]:
        """Return store repositories (slug, source, name...)."""
        data = await self._call("get", "/store/repositories")
        if not isinstance(data, list):
            raise SupervisorError("GET /store/repositories returned no list")
        return [repo for repo in data if isinstance(repo, dict)]

    async def add_repository(self, url: str) -> None:
        """Add a repository to the store (clones it)."""
        await self._call("post", "/store/repositories", {"repository": url})

    async def installed_addons(self) -> list[dict[str, Any]]:
        """Return installed apps (each has 'slug' and 'repository')."""
        addons = (await self._get_dict("/addons")).get("addons") or []
        return [a for a in addons if isinstance(a, dict)]

    async def reload_store(self) -> None:
        """Reload the store so a newly added repository's apps are listed."""
        await self._call("post", "/store/reload")

    async def store_addons(self) -> list[dict[str, Any]]:
        """Return every app known to the store (slug, repository...)."""
        addons = (await self._get_dict("/store/addons")).get("addons") or []
        return [a for a in addons if isinstance(a, dict)]

    async def host_archs(self) -> list[str]:
        """Return the architectures this system can run."""
        archs = (await self._get_dict("/info")).get("supported_arch") or []
        return [str(a) for a in archs]
