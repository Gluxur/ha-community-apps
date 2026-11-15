"""Fetches the catalog and the Supervisor state used for repair issues."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .catalog import CatalogError, keep_last_good, parse_catalog
from .const import CATALOG_URL, DOMAIN, SCHEMA_VERSION, UPDATE_INTERVAL
from .supervisor import SupervisorClient, SupervisorError

_LOGGER = logging.getLogger(__name__)


class CommunityAppsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data: repos, catalog_error, fetched_at, store_repos, installed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SupervisorClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.client = client

    async def _fetch_catalog(self) -> tuple[list[dict[str, Any]] | None, str | None]:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(CATALOG_URL, timeout=ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    return None, f"HTTP {resp.status}"
                data = await resp.json(content_type=None)
            return parse_catalog(data, SCHEMA_VERSION), None
        except (ClientError, TimeoutError, ValueError) as err:
            return None, type(err).__name__
        except CatalogError as err:
            return None, str(err)

    async def _async_update_data(self) -> dict[str, Any]:
        repos, error = await self._fetch_catalog()
        if error:
            _LOGGER.warning("Community Apps catalog not refreshed: %s", error)
        try:
            data = keep_last_good(self.data, repos, error, datetime.now(timezone.utc).isoformat())
        except CatalogError as err:
            raise UpdateFailed(f"Catalog unavailable: {err}") from err
        try:
            data["store_repos"] = await self.client.repositories()
            data["installed"] = await self.client.installed_addons()
        except SupervisorError as err:
            raise UpdateFailed(f"Supervisor unavailable: {err}") from err
        return data
