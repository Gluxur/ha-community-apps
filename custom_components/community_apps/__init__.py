"""Community Apps: browse a community catalog of apps and add their repositories."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from . import websocket
from .catalog import issues_for
from .const import DOMAIN, PANEL_COMPONENT, PANEL_URL_PATH, STATIC_PATH
from .coordinator import CommunityAppsCoordinator
from .repairs_sync import sync_issues
from .supervisor import SupervisorClient, SupervisorError

_REGISTERED = f"{DOMAIN}_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    try:
        client = SupervisorClient(async_get_clientsession(hass))
    except SupervisorError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = CommunityAppsCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator

    @callback
    def _update_issues() -> None:
        data = coordinator.data
        if data and data.get("catalog_error") is None:
            sync_issues(hass, issues_for(data["repos"], data["store_repos"], data["installed"]))

    entry.async_on_unload(coordinator.async_add_listener(_update_issues))
    _update_issues()

    # Static path and WebSocket commands survive entry reloads: register once.
    if not hass.data.get(_REGISTERED):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_PATH, str(Path(__file__).parent / "frontend"), cache_headers=False)]
        )
        websocket.async_register(hass)
        hass.data[_REGISTERED] = True

    version = (await async_get_integration(hass, DOMAIN)).version
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        module_url=f"{STATIC_PATH}/panel.js?v={version}",
        sidebar_title="Community Apps",
        sidebar_icon="mdi:store-search-outline",
        require_admin=True,
        config={},
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    hass.data.get(DOMAIN, {}).pop("coordinator", None)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    sync_issues(hass, [])
