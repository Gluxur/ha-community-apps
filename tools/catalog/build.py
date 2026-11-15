"""Build the public catalog.json from the entry files."""

from __future__ import annotations

from datetime import datetime
from typing import Any

SCHEMA_VERSION = 1
_PUBLIC = ("approved", "flagged")


def _public_scan(scan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(scan, dict):
        return scan
    apps = [{k: v for k, v in app.items() if k != "path"} for app in scan.get("apps") or []]
    return {**scan, "apps": apps}


def build_catalog(
    entries: list[dict[str, Any]],
    now: datetime,
    stats: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Public catalog; `stats` adds GitHub stars and last activity per repository."""
    repositories: list[dict[str, Any]] = []
    for entry in entries:
        status = entry.get("status")
        if status in _PUBLIC:
            repositories.append(
                {
                    "repository": entry["repository"],
                    "added_by": entry.get("added_by", "author"),
                    "status": status,
                    "reviewed": entry.get("reviewed"),
                    "scan": _public_scan(entry.get("scan")),
                    **{k: v for k, v in (stats or {}).get(entry["repository"], {}).items() if k in ("stars", "updated_at")},
                }
            )
        elif status == "removed":
            repositories.append(
                {"repository": entry["repository"], "status": "removed", "removed_reason": entry.get("removed_reason")}
            )
    repositories.sort(key=lambda r: r["repository"].lower())
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repositories": repositories,
    }
