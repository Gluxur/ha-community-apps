"""Markdown report posted on catalog pull requests."""

from __future__ import annotations

from typing import Any

DISCLAIMER = "This report lists signals; it does not prove an app is harmless."


def _cell(values: list[str]) -> str:
    return ", ".join(f"`{v}`" for v in values) if values else "—"


def render_report(full_name: str, commit: str, scan: dict[str, Any], errors: list[str]) -> str:
    lines = [f"## Scan of `{full_name}` at `{commit[:7]}`", ""]
    if errors:
        lines += ["### Blocking", ""] + [f"- {e}" for e in errors] + [""]
    lines += [
        "| App | Version | Risk | Image | Permissions | Domains | Dynamic run |",
        "|---|---|---|---|---|---|---|",
    ]
    for app in scan.get("apps") or []:
        if app.get("error"):
            lines.append(f"| `{app.get('path', app.get('slug'))}` | — | — | — | config error: {app['error']} | — | — |")
            continue
        lines.append(
            f"| {app['name']} (`{app['slug']}`) | {app.get('version') or '—'} | **{app['risk']}** | "
            f"{app.get('image', '—')} | {_cell(app.get('permissions') or [])} | "
            f"{_cell(app.get('domains') or [])} | {app.get('dynamic', 'skipped')} |"
        )
    lines += [
        "",
        "Dynamic run: the app is started for a few minutes in an isolated network without configuration; "
        "only DNS lookups are recorded. `failed` usually means the app needs the Supervisor or its options.",
        "",
        f"_{DISCLAIMER}_",
    ]
    return "\n".join(lines) + "\n"
