"""Keep one repair issue per installed app whose repository is flagged or removed."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ENTRY_URL


@callback
def sync_issues(hass: HomeAssistant, issues: list[dict[str, Any]]) -> None:
    wanted = {issue["id"] for issue in issues}
    for issue in issues:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue["id"],
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING if issue["status"] == "flagged" else ir.IssueSeverity.ERROR,
            translation_key=f"app_{issue['status']}",
            translation_placeholders={
                "app": issue["app"],
                "repository": issue["repository"],
                "reason": issue["reason"],
            },
            learn_more_url=ENTRY_URL.format(path=issue["repository"].lower()),
        )
    registry = ir.async_get(hass)
    for domain, issue_id in list(registry.issues):
        if domain == DOMAIN and issue_id not in wanted:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
