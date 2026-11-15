"""Static scan of an app repository: permissions, image provenance, domains."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_FILES = ("repository.yaml", "repository.yml", "repository.json")
CONFIG_FILES = ("config.yaml", "config.yml", "config.json")
MAX_DEPTH = 3
MAX_FILE_SIZE = 1_000_000

HIGH = {"full_access", "privileged", "docker_api", "host_pid", "hassio_role:manager", "hassio_role:admin"}
MEDIUM = {"host_network", "host_dbus", "apparmor_disabled", "devices", "uart", "usb", "gpio", "kernel_modules"}

_BOOL_PERMISSIONS = (
    "host_network",
    "full_access",
    "docker_api",
    "host_pid",
    "host_dbus",
    "uart",
    "usb",
    "gpio",
    "kernel_modules",
)
_MAP_ALIASES = {"homeassistant_config": "config"}

IGNORED_DOMAINS = {
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "ghcr.io",
    "docker.io",
    "registry-1.docker.io",
    "home-assistant.io",
    "www.home-assistant.io",
    "developers.home-assistant.io",
    "json-schema.org",
    "www.w3.org",
    "localhost",
    "example.com",
    "example.org",
    "opensource.org",
    "www.apache.org",
    "www.gnu.org",
}
_SKIP_DIRS = {".git", "docs", "tests", "translations"}
_SKIP_NAMES = {"icon.png", "logo.png"}
_URL = re.compile(r"https?://([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _app_dirs(root: Path) -> list[Path]:
    found: list[Path] = []

    def walk(directory: Path, depth: int) -> None:
        if any((directory / name).is_file() for name in CONFIG_FILES) and directory != root:
            found.append(directory)
            return
        if depth >= MAX_DEPTH:
            return
        for child in sorted(directory.iterdir()):
            if child.is_dir() and child.name != ".git":
                walk(child, depth + 1)

    walk(root, 0)
    return found


def permissions(config: dict[str, Any]) -> list[str]:
    """Sensitive permissions an app config requests."""
    perms: set[str] = {name for name in _BOOL_PERMISSIONS if config.get(name) is True}
    if config.get("privileged"):
        perms.add("privileged")
    if config.get("devices"):
        perms.add("devices")
    if config.get("apparmor") is False:
        perms.add("apparmor_disabled")
    role = config.get("hassio_role")
    if role in ("manager", "admin"):
        perms.add(f"hassio_role:{role}")
    for item in config.get("map") or []:
        if isinstance(item, str):
            kind, _, mode = item.partition(":")
            writable = mode == "rw"
        elif isinstance(item, dict):
            kind = str(item.get("type", ""))
            writable = item.get("read_only") is False
        else:
            continue
        if writable and kind:
            perms.add(f"map_rw:{_MAP_ALIASES.get(kind, kind)}")
    return sorted(perms)


def risk(perms: list[str], image: str) -> str:
    """low | medium | high, from the documented rule."""
    if HIGH.intersection(perms):
        return "high"
    if MEDIUM.intersection(perms) or any(p.startswith("map_rw:") for p in perms) or image == "prebuilt":
        return "medium"
    return "low"


def filter_domains(hosts: set[str]) -> list[str]:
    """Lowercase, drop well-known noise and local names."""
    result = set()
    for host in hosts:
        host = host.lower().rstrip(".")
        if host in IGNORED_DOMAINS or host.endswith(".local") or "." not in host:
            continue
        result.add(host)
    return sorted(result)


def static_domains(app_dir: Path) -> list[str]:
    """Hosts referenced by URLs in the app's code and Dockerfile."""
    hosts: set[str] = set()
    for path in app_dir.rglob("*"):
        rel = path.relative_to(app_dir)
        if not path.is_file() or _SKIP_DIRS.intersection(rel.parts[:-1]):
            continue
        name = path.name
        if name in _SKIP_NAMES or name.lower().endswith(".md") or name.upper().startswith("LICENSE"):
            continue
        if path.stat().st_size > MAX_FILE_SIZE:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hosts.update(_URL.findall(text))
    return filter_domains(hosts)


def scan_app(root: Path, app_dir: Path) -> dict[str, Any]:
    rel = app_dir.relative_to(root).as_posix()
    app: dict[str, Any] = {
        "path": rel,
        "slug": app_dir.name,
        "name": app_dir.name,
        "version": None,
        "arch": [],
        "image": "source",
        "permissions": [],
        "risk": "low",
        "domains": [],
        "error": None,
    }
    config_path = next(app_dir / n for n in CONFIG_FILES if (app_dir / n).is_file())
    try:
        config = _load(config_path)
        if not isinstance(config, dict):
            raise ValueError("config is not a mapping")
    except (ValueError, yaml.YAMLError, OSError) as err:
        app["error"] = f"{config_path.name}: {type(err).__name__}: {err}".splitlines()[0]
        return app
    app["slug"] = str(config.get("slug") or app_dir.name)
    app["name"] = str(config.get("name") or app["slug"])
    app["version"] = None if config.get("version") is None else str(config["version"])
    app["arch"] = [str(a) for a in config.get("arch") or []]
    app["image"] = "prebuilt" if config.get("image") else "source"
    app["permissions"] = permissions(config)
    app["risk"] = risk(app["permissions"], app["image"])
    app["domains"] = static_domains(app_dir)
    return app


def load_config(app_dir: Path) -> dict[str, Any]:
    """The parsed config of an app directory."""
    config_path = next(app_dir / n for n in CONFIG_FILES if (app_dir / n).is_file())
    return _load(config_path)


def scan_repository(root: Path) -> dict[str, Any]:
    """Scan every app of a repository checkout."""
    errors: list[str] = []
    if not any((root / name).is_file() for name in REPOSITORY_FILES):
        errors.append("no repository.yaml, repository.yml or repository.json at the repository root")
    apps = [scan_app(root, d) for d in _app_dirs(root)]
    if not apps:
        errors.append("no app found (no config.yaml/yml/json)")
    return {"errors": errors, "apps": apps}
