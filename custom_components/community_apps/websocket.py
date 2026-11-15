"""WebSocket commands used by the panel (administrators only)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .catalog import can_add, merge_state, normalize_repo_url, repo_url
from .const import DOMAIN
from .coordinator import CommunityAppsCoordinator
from .supervisor import SupervisorError


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_refresh)
    websocket_api.async_register_command(hass, ws_add_repository)


def _coordinator(hass: HomeAssistant) -> CommunityAppsCoordinator | None:
    return hass.data.get(DOMAIN, {}).get("coordinator")


@websocket_api.websocket_command({vol.Required("type"): "community_apps/list"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_list(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    if coordinator is None or not coordinator.data:
        connection.send_error(msg["id"], "not_ready", "Community Apps is not ready")
        return
    client = coordinator.client
    try:
        store_repos = await client.repositories()
        installed = await client.installed_addons()
        store_addons = await client.store_addons()
        archs = await client.host_archs()
    except SupervisorError as err:
        connection.send_error(msg["id"], "supervisor_error", str(err))
        return
    data = coordinator.data
    connection.send_result(
        msg["id"],
        {
            "repositories": merge_state(data["repos"], store_repos, installed, store_addons, archs),
            "catalog_error": data["catalog_error"],
            "fetched_at": data["fetched_at"],
        },
    )


@websocket_api.websocket_command({vol.Required("type"): "community_apps/refresh"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_refresh(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_ready", "Community Apps is not ready")
        return
    await coordinator.async_refresh()
    connection.send_result(msg["id"], {"catalog_error": (coordinator.data or {}).get("catalog_error")})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "community_apps/add_repository",
        vol.Required("repository"): str,
        vol.Optional("confirm_high_risk", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_add_repository(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    coordinator = _coordinator(hass)
    if coordinator is None or not coordinator.data:
        connection.send_error(msg["id"], "not_ready", "Community Apps is not ready")
        return
    wanted = msg["repository"].lower()
    repo = next((r for r in coordinator.data["repos"] if r["repository"].lower() == wanted), None)
    if repo is None:
        connection.send_error(msg["id"], "not_in_catalog", "This repository is not in the catalog")
        return
    refusal = can_add(repo, msg["confirm_high_risk"])
    if refusal == "not_approved":
        connection.send_error(msg["id"], refusal, "Only repositories currently approved in the catalog can be added")
        return
    if refusal == "confirmation_required":
        connection.send_error(msg["id"], refusal, "This repository has high-risk apps; confirm to add it")
        return
    client = coordinator.client

    async def store_slug() -> str | None:
        for store_repo in await client.repositories():
            if normalize_repo_url(str(store_repo.get("source") or "")) == wanted:
                return str(store_repo.get("slug"))
        return None

    try:
        slug = await store_slug()
        if slug is None:
            await client.add_repository(repo_url(repo["repository"]))
            await client.reload_store()
            slug = await store_slug()
        apps = [a["slug"] for a in await client.store_addons() if slug and a.get("repository") == slug]
    except SupervisorError as err:
        connection.send_error(msg["id"], "supervisor_error", str(err))
        return
    connection.send_result(msg["id"], {"apps": apps})
