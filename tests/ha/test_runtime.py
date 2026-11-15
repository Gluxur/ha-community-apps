"""Runtime tests against a real Home Assistant core.

Need pytest-homeassistant-custom-component (Linux, Python matching HA):
    pip install pytest-homeassistant-custom-component && pytest tests/ha
Skipped when it is not installed (plain `pytest` on the catalog tools).
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from unittest.mock import patch  # noqa: E402

from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from homeassistant.helpers import issue_registry as ir  # noqa: E402

DOMAIN = "community_apps"
CATALOG_URL = "https://gluxur.github.io/ha-community-apps/catalog.json"
SUP = "http://supervisor"


def _catalog(status="approved", risk="low"):
    return {
        "schema_version": 1,
        "generated_at": "2026-11-15T00:00:00Z",
        "repositories": [
            {
                "repository": "Owner/Repo",
                "added_by": "author",
                "status": status,
                "reviewed": {"by": "Gluxur", "at": "2026-11-15", "commit": "abc"},
                "scan": {"commit": "abc", "at": "x", "apps": [
                    {"slug": "x", "name": "X", "risk": risk, "arch": ["amd64"], "permissions": [], "domains": []}
                ]},
            }
        ],
    }


def _ok(data):
    return {"result": "ok", "data": data}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def supervisor_env(monkeypatch):
    monkeypatch.setenv("SUPERVISOR", "supervisor")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "t")


def _mock_supervisor(aioclient_mock, added: bool, installed: bool):
    repos = [{"slug": "core", "source": "core"}]
    store_addons = []
    if added:
        repos.append({"slug": "abc123", "source": "https://github.com/owner/repo.git"})
        store_addons.append({"slug": "abc123_x", "repository": "abc123"})
    aioclient_mock.get(f"{SUP}/store/repositories", json=_ok(repos))
    aioclient_mock.get(f"{SUP}/addons", json=_ok({"addons": [
        {"slug": "abc123_x", "repository": "abc123", "name": "X"}] if installed else []}))
    aioclient_mock.get(f"{SUP}/store/addons", json=_ok({"addons": store_addons}))
    aioclient_mock.get(f"{SUP}/info", json=_ok({"supported_arch": ["amd64"]}))
    aioclient_mock.post(f"{SUP}/store/repositories", json=_ok(None))
    aioclient_mock.post(f"{SUP}/store/reload", json=_ok(None))


async def _setup(hass):
    for dep in ("hassio", "frontend", "panel_custom"):
        hass.config.components.add(dep)
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    with patch("homeassistant.components.panel_custom.async_register_panel") as panel:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, panel


async def test_setup_registers_admin_panel(hass, aioclient_mock, supervisor_env):
    aioclient_mock.get(CATALOG_URL, json=_catalog())
    _mock_supervisor(aioclient_mock, added=False, installed=False)
    _, panel = await _setup(hass)
    kwargs = panel.call_args.kwargs
    assert kwargs["require_admin"] is True
    assert kwargs["frontend_url_path"] == "community-apps"
    assert kwargs["module_url"].startswith("/community_apps_static/panel.js?v=")


async def test_list_and_add_repository(hass, aioclient_mock, supervisor_env, hass_ws_client):
    aioclient_mock.get(CATALOG_URL, json=_catalog())
    _mock_supervisor(aioclient_mock, added=False, installed=False)
    await _setup(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "community_apps/list"})
    msg = await client.receive_json()
    assert msg["success"], msg
    repo = msg["result"]["repositories"][0]
    assert repo["repository"] == "Owner/Repo" and repo["added"] is False
    assert repo["scan"]["apps"][0]["compatible"] is True

    await client.send_json_auto_id({"type": "community_apps/add_repository", "repository": "owner/repo"})
    msg = await client.receive_json()
    assert msg["success"], msg
    posts = [c for c in aioclient_mock.mock_calls if c[0].upper() == "POST" and str(c[1]).endswith("/store/repositories")]
    assert posts and posts[0][2] == {"repository": "https://github.com/Owner/Repo"}


async def test_add_refuses_unapproved_and_unconfirmed_high_risk(hass, aioclient_mock, supervisor_env, hass_ws_client):
    aioclient_mock.get(CATALOG_URL, json=_catalog(risk="high"))
    _mock_supervisor(aioclient_mock, added=False, installed=False)
    await _setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "community_apps/add_repository", "repository": "Owner/Repo"})
    msg = await client.receive_json()
    assert not msg["success"] and msg["error"]["code"] == "confirmation_required"
    await client.send_json_auto_id({"type": "community_apps/add_repository", "repository": "other/repo"})
    msg = await client.receive_json()
    assert not msg["success"] and msg["error"]["code"] == "not_in_catalog"


async def test_flagged_installed_app_creates_issue(hass, aioclient_mock, supervisor_env):
    aioclient_mock.get(CATALOG_URL, json=_catalog(status="flagged"))
    _mock_supervisor(aioclient_mock, added=True, installed=True)
    await _setup(hass)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "flagged_abc123_x")
    assert issue is not None
    assert issue.translation_key == "app_flagged"
    assert issue.translation_placeholders["repository"] == "Owner/Repo"


async def test_catalog_error_keeps_data_and_issues(hass, aioclient_mock, supervisor_env, hass_ws_client):
    aioclient_mock.get(CATALOG_URL, json=_catalog(status="flagged"))
    _mock_supervisor(aioclient_mock, added=True, installed=True)
    await _setup(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.get(CATALOG_URL, status=500)
    _mock_supervisor(aioclient_mock, added=True, installed=True)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "community_apps/refresh"})
    msg = await client.receive_json()
    assert msg["result"]["catalog_error"] == "HTTP 500"
    await client.send_json_auto_id({"type": "community_apps/list"})
    msg = await client.receive_json()
    assert msg["result"]["repositories"][0]["repository"] == "Owner/Repo"
    assert ir.async_get(hass).async_get_issue(DOMAIN, "flagged_abc123_x") is not None


async def test_list_requires_admin(hass, aioclient_mock, supervisor_env, hass_ws_client, hass_read_only_access_token):
    aioclient_mock.get(CATALOG_URL, json=_catalog())
    _mock_supervisor(aioclient_mock, added=False, installed=False)
    await _setup(hass)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "community_apps/list"})
    msg = await client.receive_json()
    assert not msg["success"] and msg["error"]["code"] == "unauthorized"
