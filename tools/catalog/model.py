"""Catalog entry model and the rules a submission must follow."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

STATUSES = ("pending", "approved", "flagged", "removed")
ADDED_BY = ("author", "catalog")
ENTRY_DIR = "catalog/repositories"

_REPOSITORY = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
_SUBMITTED_KEYS = {"repository", "added_by"}
_KNOWN_KEYS = {"repository", "added_by", "status", "reviewed", "removed_reason", "scan", "pending_scan"}
_SUBMITTER_PERMISSIONS = {"admin", "maintain", "write"}


def entry_path(full_name: str) -> str:
    """Path of the catalog file for a repository."""
    owner, repo = full_name.lower().split("/", 1)
    return f"{ENTRY_DIR}/{owner}/{repo}.yaml"


def load_entry(path: Path) -> dict[str, Any]:
    """Read one catalog file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: not a mapping")
    return data


def validate_entry(entry: dict[str, Any], path: str, *, submitted: bool) -> list[str]:
    """Return the problems with an entry (empty list when valid).

    A submitted entry (from a pull request) may only name the repository and
    who added it; everything else is written by the automation.
    """
    errors: list[str] = []
    repository = entry.get("repository")
    if not isinstance(repository, str) or not _REPOSITORY.match(repository):
        errors.append("repository: must be 'owner/repo'")
    elif path.replace("\\", "/") != entry_path(repository):
        errors.append(f"repository: file must be {entry_path(repository)}")

    allowed = _SUBMITTED_KEYS if submitted else _KNOWN_KEYS
    for key in entry:
        if key not in allowed:
            errors.append(f"{key}: not allowed in a {'submission' if submitted else 'catalog entry'}")

    added_by = entry.get("added_by", "author")
    if added_by not in ADDED_BY:
        errors.append(f"added_by: must be one of {', '.join(ADDED_BY)}")

    if not submitted:
        status = entry.get("status")
        if status not in STATUSES:
            errors.append(f"status: must be one of {', '.join(STATUSES)}")
        if status == "removed" and not entry.get("removed_reason"):
            errors.append("removed_reason: required when status is removed")
        if status in ("approved", "flagged"):
            reviewed = entry.get("reviewed")
            if not isinstance(reviewed, dict) or not all(reviewed.get(k) for k in ("by", "at", "commit")):
                errors.append("reviewed: needs by, at and commit")
            if not isinstance(entry.get("scan"), dict):
                errors.append("scan: missing")
    return errors


def check_pr_paths(paths: list[str]) -> list[str]:
    """A catalog pull request changes exactly one entry file and nothing else."""
    errors: list[str] = []
    entries = [p for p in paths if p.startswith(f"{ENTRY_DIR}/") and p.endswith(".yaml")]
    others = [p for p in paths if p not in entries]
    if others:
        errors.append("a catalog pull request may only change catalog/repositories/: " + ", ".join(others))
    if len(entries) != 1:
        errors.append("a catalog pull request adds or changes exactly one repository")
    return errors


def is_allowed_submitter(
    full_name: str,
    author: str,
    permission: str | None,
    reviewers: set[str],
    added_by: str,
) -> bool:
    """Owner or maintainer submits for themselves; reviewers seed `added_by: catalog`."""
    if added_by == "catalog":
        return author.lower() in {r.lower() for r in reviewers}
    owner = full_name.split("/", 1)[0]
    return author.lower() == owner.lower() or permission in _SUBMITTER_PERMISSIONS
