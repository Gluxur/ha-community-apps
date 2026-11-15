"""What changed between two scans, in terms a reviewer cares about."""

from __future__ import annotations

from typing import Any


def signals(scan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """{slug: {permissions, risk, domains}} — everything else (version...) is ignored."""
    return {
        app["slug"]: {
            "permissions": sorted(app.get("permissions") or []),
            "risk": app.get("risk", "low"),
            "domains": sorted(app.get("domains") or []),
        }
        for app in scan.get("apps") or []
    }


def signal_changes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Human-readable lines; empty when nothing a reviewer cares about changed."""
    before, after = signals(old), signals(new)
    lines: list[str] = []
    for slug, now in after.items():
        was = before.get(slug)
        if was is None:
            lines.append(f"new app {slug} (risk {now['risk']})")
            continue
        lines += [f"{slug}: new permission {p}" for p in now["permissions"] if p not in was["permissions"]]
        if now["risk"] != was["risk"]:
            lines.append(f"{slug}: risk {was['risk']} → {now['risk']}")
        lines += [f"{slug}: new domain {d}" for d in now["domains"] if d not in was["domains"]]
    return lines
