"""Command line used by the catalog workflows: python -m tools.catalog <command>."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .build import build_catalog
from .compare import signal_changes
from .model import ENTRY_DIR, check_pr_paths, is_allowed_submitter, load_entry, validate_entry
from .report import render_report
from .static_scan import load_config, scan_repository

DYNAMIC_BUDGET = 45 * 60  # seconds of dynamic runs per repository
_RISK_ORDER = {"high": 0, "medium": 1, "low": 2}

KEY_ORDER = ("repository", "added_by", "status", "reviewed", "removed_reason", "scan", "pending_scan")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def reviewers(codeowners: Path = Path("CODEOWNERS")) -> set[str]:
    """Owners of /catalog/ in CODEOWNERS."""
    for line in codeowners.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and parts[0].rstrip("/") in ("/catalog", "catalog"):
            return {p.lstrip("@") for p in parts[1:] if p.startswith("@")}
    return set()


def write_entry(path: Path, entry: dict[str, Any]) -> None:
    ordered = {k: entry[k] for k in KEY_ORDER if k in entry}
    path.write_text(yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def remote_head(full_name: str) -> str | None:
    """Commit of the default branch, or None if the repository is unavailable."""
    try:
        out = _git("ls-remote", f"https://github.com/{full_name}", "HEAD")
    except subprocess.CalledProcessError:
        return None
    return out.split()[0] if out else None


def is_archived(full_name: str) -> bool:
    request = urllib.request.Request(f"https://api.github.com/repos/{full_name}")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return bool(json.load(resp).get("archived"))
    except (urllib.error.URLError, ValueError, TimeoutError):
        return False


def scan(
    full_name: str,
    ref: str | None = None,
    dynamic: bool = False,
    only: str | None = None,
    dynamic_budget: float = DYNAMIC_BUDGET,
) -> dict[str, Any]:
    """Clone and scan a repository; with `dynamic`, also run apps, riskiest first, within a time budget."""
    with tempfile.TemporaryDirectory(prefix="cascan-") as tmp:
        root = Path(tmp) / "repo"
        url = f"https://github.com/{full_name}"
        try:
            if ref:
                root.mkdir()
                _git("init", "-q", cwd=root)
                _git("fetch", "-q", "--depth", "1", url, ref, cwd=root)
                _git("checkout", "-q", "FETCH_HEAD", cwd=root)
            else:
                _git("clone", "-q", "--depth", "1", url, str(root))
            commit = _git("rev-parse", "HEAD", cwd=root)
        except subprocess.CalledProcessError as err:
            return {
                "repository": full_name,
                "commit": "",
                "at": _now(),
                "errors": [f"could not fetch {url} (git exit {err.returncode})"],
                "apps": [],
            }
        result = scan_repository(root)
        if only:
            result["apps"] = [a for a in result["apps"] if a["slug"] == only]
        for app in result["apps"]:
            app["dynamic"] = "skipped"
        if dynamic:
            from . import dynamic_scan

            started = time.monotonic()
            for app in sorted(result["apps"], key=lambda a: _RISK_ORDER.get(a["risk"], 3)):
                if app["error"] or time.monotonic() - started >= dynamic_budget:
                    continue
                run = dynamic_scan.run_app(root / app["path"], load_config(root / app["path"]))
                app["dynamic"] = run["status"]
                app["domains"] = sorted(set(app["domains"]) | set(run["domains"]))
    return {"repository": full_name, "commit": commit, "at": _now(), "errors": result["errors"], "apps": result["apps"]}


def _stored_scan(scan_result: dict[str, Any]) -> dict[str, Any]:
    return {k: scan_result[k] for k in ("commit", "at", "apps")}


def cmd_validate(args: argparse.Namespace) -> int:
    errors = check_pr_paths(args.changed)
    owners = reviewers()
    for changed in args.changed:
        path = Path(changed)
        if not changed.startswith(f"{ENTRY_DIR}/") or not path.is_file():
            continue
        try:
            entry = load_entry(path)
        except (ValueError, yaml.YAMLError) as err:
            errors.append(f"{changed}: {type(err).__name__}")
            continue
        is_reviewer = args.author.lower() in {o.lower() for o in owners}
        # Reviewers may edit full entries (re-approve, remove); others only submit.
        submitted = not (is_reviewer and "status" in entry)
        errors += [f"{changed}: {e}" for e in validate_entry(entry, changed, submitted=submitted)]
        repository = entry.get("repository")
        permission = None if args.permission in ("", "none") else args.permission
        if isinstance(repository, str) and "/" in repository and submitted:
            if not is_allowed_submitter(repository, args.author, permission, owners, entry.get("added_by", "author")):
                errors.append(
                    f"{changed}: @{args.author} is not the owner or a maintainer of {repository}"
                    + (" (added_by: catalog is reserved to reviewers)" if entry.get("added_by") == "catalog" else "")
                )
    for error in errors:
        print(error, file=sys.stderr)
    if args.errors_out:
        Path(args.errors_out).write_text(json.dumps(errors), encoding="utf-8")
    return 1 if errors else 0


def cmd_scan(args: argparse.Namespace) -> int:
    result = scan(args.repository, args.ref, args.dynamic, args.only)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    result = json.loads(Path(args.scan).read_text(encoding="utf-8"))
    errors = list(result.get("errors") or [])
    if args.errors:
        errors += json.loads(Path(args.errors).read_text(encoding="utf-8"))
    Path(args.out).write_text(render_report(result["repository"], result["commit"], result, errors), encoding="utf-8")
    return 0


def cmd_apply_review(args: argparse.Namespace) -> int:
    path = Path(args.file)
    entry = load_entry(path)
    result = json.loads(Path(args.scan).read_text(encoding="utf-8"))
    entry.setdefault("added_by", "author")
    entry["status"] = "approved"
    entry["reviewed"] = {"by": args.reviewer, "at": _today(), "commit": result["commit"]}
    entry["scan"] = _stored_scan(result)
    entry.pop("pending_scan", None)
    write_entry(path, entry)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    """Re-approve a flagged entry: its pending scan becomes the reviewed scan."""
    path = Path(args.file)
    entry = load_entry(path)
    pending = entry.pop("pending_scan", None) or entry.get("scan")
    entry["status"] = "approved"
    entry["scan"] = pending
    entry["reviewed"] = {"by": args.reviewer, "at": _today(), "commit": pending["commit"]}
    write_entry(path, entry)
    return 0


def cmd_nightly(args: argparse.Namespace) -> int:
    flagged: list[dict[str, Any]] = []
    for path in sorted(Path(ENTRY_DIR).glob("*/*.yaml")):
        entry = load_entry(path)
        if entry.get("status") != "approved":
            continue
        name = entry["repository"]
        head = remote_head(name)
        if head is None or is_archived(name):
            flagged.append({"repository": name, "file": path.as_posix(), "changes": ["repository unavailable"]})
            continue
        if head == (entry.get("scan") or {}).get("commit"):
            continue
        result = scan(name, head, args.dynamic)
        if not result["commit"]:
            # Fetch failed: keep the recorded scan, tell the reviewer.
            flagged.append({"repository": name, "file": path.as_posix(), "changes": ["repository unavailable"]})
            continue
        changes = signal_changes(entry.get("scan") or {}, result)
        if not changes:
            entry["scan"] = _stored_scan(result)
        else:
            entry["status"] = "flagged"
            entry["pending_scan"] = _stored_scan(result)
            flagged.append({"repository": name, "file": path.as_posix(), "changes": changes})
        write_entry(path, entry)
    Path(args.flagged_out).write_text(json.dumps(flagged, indent=2), encoding="utf-8")
    return 0


def cmd_pending(args: argparse.Namespace) -> int:
    """Entry files merged but not yet recorded as reviewed (no status)."""
    for path in sorted(Path(ENTRY_DIR).glob("*/*.yaml")):
        if "status" not in load_entry(path):
            print(path.as_posix())
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    entries = [load_entry(p) for p in sorted(Path(ENTRY_DIR).glob("*/*.yaml"))]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_catalog(entries, datetime.now(timezone.utc)), indent=2), encoding="utf-8")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m tools.catalog")
    sub = p.add_subparsers(dest="command", required=True, metavar="{validate,scan,report,apply-review,approve,nightly,pending,build}")

    s = sub.add_parser("validate", help="check a catalog pull request")
    s.add_argument("--author", required=True)
    s.add_argument("--permission", default="none")
    s.add_argument("--changed", nargs="+", required=True)
    s.add_argument("--errors-out")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("scan", help="clone and scan a repository")
    s.add_argument("repository", type=lambda v: v if re.match(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", v) else sys.exit("bad repository"))
    s.add_argument("--ref")
    s.add_argument("--dynamic", action="store_true")
    s.add_argument("--only")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("report", help="render the pull request report")
    s.add_argument("--scan", required=True)
    s.add_argument("--errors")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("apply-review", help="record the review of a merged submission")
    s.add_argument("file")
    s.add_argument("--reviewer", required=True)
    s.add_argument("--scan", required=True)
    s.set_defaults(func=cmd_apply_review)

    s = sub.add_parser("approve", help="re-approve a flagged entry")
    s.add_argument("file")
    s.add_argument("--reviewer", required=True)
    s.set_defaults(func=cmd_approve)

    s = sub.add_parser("nightly", help="rescan approved entries whose repository changed")
    s.add_argument("--dynamic", action="store_true")
    s.add_argument("--flagged-out", required=True)
    s.set_defaults(func=cmd_nightly)

    s = sub.add_parser("pending", help="list merged entries not yet recorded")
    s.set_defaults(func=cmd_pending)

    s = sub.add_parser("build", help="write catalog.json")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_build)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
