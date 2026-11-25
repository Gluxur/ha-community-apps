"""Dynamic scan: start an app in an isolated Docker network and log its DNS lookups.

Only names resolved through DNS are seen; connections to hard-coded IP
addresses are not. The app runs without Supervisor, configuration, volumes or
environment, so many apps stop early: that is reported as "failed", which is
a normal outcome and not a rejection.
"""

from __future__ import annotations

import json
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from .static_scan import filter_domains

DNS_IMAGE = "alpine:3.22"
DNS_COMMAND = (
    "apk add --no-cache dnsmasq >/dev/null 2>&1 && "
    "exec dnsmasq -k --no-resolv --server=1.1.1.1 --log-queries --log-facility=-"
)
MIN_RUNNING_SECONDS = 20
BUILD_FILES = ("build.yaml", "build.yml", "build.json")

_QUERY = re.compile(r"query\[[A-Z]+\]\s+(\S+)\s+from\s")


# Supervisor-internal hostnames: outside the Supervisor the resolver appends the
# host's search domain (supervisor.home, homeassistant.<cloud>.net...).
_INTERNAL_FIRST_LABELS = {"supervisor", "homeassistant", "hassio"}
# Search domain of the GitHub-hosted (Azure) runner: the container's own
# hostname, a container id or "default_server", resolved with it appended.
_RUNNER_SEARCH_SUFFIXES = (".internal.cloudapp.net",)


def _is_noise(name: str) -> bool:
    name = name.lower().rstrip(".")
    return name.split(".", 1)[0] in _INTERNAL_FIRST_LABELS or name.endswith(_RUNNER_SEARCH_SUFFIXES)


def parse_dnsmasq_log(text: str) -> list[str]:
    """Names queried in a dnsmasq log, noise removed."""
    return filter_domains({n for n in _QUERY.findall(text) if not _is_noise(n)})


def image_for(app_dir: Path, config: dict[str, Any], arch: str = "amd64") -> tuple[str, str] | None:
    """How to obtain the app image for `arch`: ("pull", ref), ("build", base) or None."""
    if arch not in (config.get("arch") or []):
        return None
    image = config.get("image")
    if image:
        return ("pull", f"{str(image).replace('{arch}', arch)}:{config.get('version')}")
    for name in BUILD_FILES:
        path = app_dir / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
                data = json.loads(text) if name.endswith(".json") else yaml.safe_load(text)
                build_from = data.get("build_from") if isinstance(data, dict) else None
                base = build_from.get(arch) if isinstance(build_from, dict) else None
            except (OSError, ValueError, yaml.YAMLError):
                base = None
            return ("build", str(base or ""))
    return ("build", "")


def _docker(*args: str, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=check)


def _cleanup(*args: str) -> None:
    """Best-effort removal; never masks the scan result."""
    try:
        _docker(*args, timeout=120, check=False)
    except (subprocess.SubprocessError, OSError):
        pass


def run_app(app_dir: Path, config: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    """Run the app for `timeout` seconds and return {status, domains}."""
    how = image_for(app_dir, config)
    if how is None:
        return {"status": "skipped", "domains": []}
    tag = secrets.token_hex(4)
    network, dns, app, image = f"cascan-{tag}", f"cascan-dns-{tag}", f"cascan-app-{tag}", how[1]
    built = False
    try:
        _docker("network", "create", network)
        _docker("run", "-d", "--name", dns, "--network", network, DNS_IMAGE, "sh", "-c", DNS_COMMAND)
        dns_ip = _docker(
            "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", dns
        ).stdout.strip()
        if how[0] == "pull":
            if _docker("pull", image, check=False).returncode != 0:
                return {"status": "failed", "domains": []}
        else:
            image = f"cascan-img-{tag}"
            args = ["build", "-t", image, "--build-arg", f"BUILD_FROM={how[1]}", "--build-arg", "BUILD_ARCH=amd64"]
            if _docker(*args, str(app_dir), check=False).returncode != 0:
                return {"status": "failed", "domains": []}
            built = True
        time.sleep(5)  # let dnsmasq finish installing
        _docker("run", "-d", "--name", app, "--network", network, "--dns", dns_ip, "--memory", "512m", image)
        started = time.monotonic()
        running_for = 0.0
        while time.monotonic() - started < timeout:
            state = _docker("inspect", "-f", "{{.State.Running}}", app, check=False).stdout.strip()
            if state != "true":
                break
            running_for = time.monotonic() - started
            time.sleep(5)
        log = _docker("logs", dns, check=False)
        status = "started" if running_for >= MIN_RUNNING_SECONDS else "failed"
        return {"status": status, "domains": parse_dnsmasq_log(log.stdout + log.stderr)}
    except (subprocess.SubprocessError, OSError):
        return {"status": "failed", "domains": []}
    finally:
        _cleanup("rm", "-f", app, dns)
        if built:
            _cleanup("rmi", "-f", image)
        _cleanup("network", "rm", network)
