"""Catalog logic, independent of Home Assistant (tested by loading this file directly).

Keep this module free of Home Assistant and relative imports.
"""

from __future__ import annotations

import copy
import re
from typing import Any

_GITHUB = re.compile(r"^https?://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$", re.IGNORECASE)


class CatalogError(Exception):
    """The catalog could not be used."""


def parse_catalog(data: object, schema_version: int) -> list[dict[str, Any]]:
    """Repositories of a catalog.json document."""
    if not isinstance(data, dict):
        raise CatalogError("catalog is not an object")
    if data.get("schema_version") != schema_version:
        raise CatalogError(f"unsupported schema_version {data.get('schema_version')!r}")
    repositories = data.get("repositories")
    if not isinstance(repositories, list):
        raise CatalogError("catalog has no repositories")
    return [r for r in repositories if isinstance(r, dict) and isinstance(r.get("repository"), str)]


def keep_last_good(
    previous: dict[str, Any] | None,
    repos: list[dict[str, Any]] | None,
    error: str | None,
    fetched_at: str,
) -> dict[str, Any]:
    """Coordinator data: new repositories, or the previous ones with the error."""
    if error is None and repos is not None:
        return {"repos": repos, "catalog_error": None, "fetched_at": fetched_at}
    if not previous:
        raise CatalogError(error or "catalog unavailable")
    return {**previous, "catalog_error": error or "catalog unavailable"}


def normalize_repo_url(url: str) -> str | None:
    """'owner/repo' (lowercase) for a GitHub URL, else None."""
    match = _GITHUB.match(url.strip())
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}".lower()


def repo_url(full_name: str) -> str:
    """URL given to the Supervisor: identical to a manual add."""
    return f"https://github.com/{full_name}"


def _store_index(store_repos: list[dict[str, Any]]) -> dict[str, str]:
    """{owner/repo: store slug} for GitHub repositories in the store."""
    index: dict[str, str] = {}
    for repo in store_repos:
        name = normalize_repo_url(str(repo.get("source") or ""))
        if name and repo.get("slug"):
            index[name] = str(repo["slug"])
    return index


def _apps(repo: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((repo.get("scan") or {}).get("apps")) or [])


def merge_state(
    repos: list[dict[str, Any]],
    store_repos: list[dict[str, Any]],
    installed: list[dict[str, Any]],
    store_addons: list[dict[str, Any]],
    host_archs: list[str],
) -> list[dict[str, Any]]:
    """Catalog repositories annotated with this system's state."""
    index = _store_index(store_repos)
    installed_slugs = {str(a.get("slug")) for a in installed}
    result: list[dict[str, Any]] = []
    for repo in repos:
        merged = copy.deepcopy(repo)
        store_slug = index.get(repo["repository"].lower())
        merged["added"] = store_slug is not None
        merged["store_slug"] = store_slug
        repo_addons = {str(a.get("slug")) for a in store_addons if store_slug and a.get("repository") == store_slug}
        for app in _apps(merged):
            slug = next((s for s in repo_addons if s.endswith(f"_{app.get('slug')}")), None)
            app["installed"] = slug in installed_slugs if slug else False
            app["compatible"] = bool(set(app.get("arch") or []) & set(host_archs))
            app["store_slug"] = slug
        result.append(merged)
    return result


def issues_for(
    repos: list[dict[str, Any]],
    store_repos: list[dict[str, Any]],
    installed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One issue per installed app whose catalog repository is flagged or removed."""
    index = _store_index(store_repos)
    issues: list[dict[str, Any]] = []
    for repo in repos:
        status = repo.get("status")
        if status not in ("flagged", "removed"):
            continue
        store_slug = index.get(repo["repository"].lower())
        if not store_slug:
            continue
        reason = "signals changed since review" if status == "flagged" else str(repo.get("removed_reason") or "")
        for addon in installed:
            if addon.get("repository") != store_slug:
                continue
            issues.append(
                {
                    "id": f"{status}_{addon['slug']}",
                    "status": status,
                    "app": str(addon.get("name") or addon["slug"]),
                    "repository": repo["repository"],
                    "reason": reason,
                }
            )
    return issues


def can_add(repo: dict[str, Any], confirm_high_risk: bool) -> str | None:
    """None when the repository may be added, else an error code."""
    if repo.get("status") != "approved":
        return "not_approved"
    if not confirm_high_risk and any(app.get("risk") == "high" for app in _apps(repo)):
        return "confirmation_required"
    return None
