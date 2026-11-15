"""Config flow for Community Apps: one confirmation step, no credentials."""

from __future__ import annotations

import os
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class CommunityAppsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if not os.environ.get("SUPERVISOR") or not os.environ.get("SUPERVISOR_TOKEN"):
            return self.async_abort(reason="no_supervisor")
        if user_input is not None:
            return self.async_create_entry(title="Community Apps", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
