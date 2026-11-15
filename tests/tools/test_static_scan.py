from pathlib import Path

from tools.catalog.static_scan import permissions, risk, scan_repository, static_domains

FIX = Path(__file__).parent / "fixtures"


def _by_slug(scan):
    return {app["slug"]: app for app in scan["apps"]}


def test_scan_ok():
    scan = scan_repository(FIX / "repo_ok")
    assert scan["errors"] == []
    apps = _by_slug(scan)
    assert set(apps) == {"app_a", "app_b"}
    a, b = apps["app_a"], apps["app_b"]
    assert a["image"] == "source"
    assert a["risk"] == "low"
    assert a["domains"] == ["api.example-weather.net"]
    assert a["arch"] == ["amd64", "aarch64"]
    assert a["version"] == "1.0.0" and a["name"] == "App A" and a["error"] is None
    assert a["path"] == "app_a"
    assert b["permissions"] == ["full_access"]
    assert b["image"] == "prebuilt"
    assert b["risk"] == "high"
    assert b["path"] == "nested/app_b"


def test_scan_invalid_app_does_not_stop_others():
    scan = scan_repository(FIX / "repo_bad")
    assert scan["errors"] == []
    apps = _by_slug(scan)
    assert apps["good"]["error"] is None
    broken = [app for app in scan["apps"] if app["error"]]
    assert len(broken) == 1 and broken[0]["path"] == "broken"


def test_scan_no_repository_file():
    assert scan_repository(FIX / "repo_none")["errors"]


def test_permissions_map_formats():
    assert permissions({"map": ["config:rw", "share", {"type": "ssl", "read_only": False}]}) == [
        "map_rw:config",
        "map_rw:ssl",
    ]
    assert permissions({"apparmor": False, "hassio_role": "manager"}) == ["apparmor_disabled", "hassio_role:manager"]
    assert permissions({"privileged": ["NET_ADMIN"], "host_network": True, "usb": True, "devices": ["/dev/ttyUSB0"]}) == [
        "devices",
        "host_network",
        "privileged",
        "usb",
    ]
    assert permissions({"privileged": [], "hassio_role": "default", "apparmor": True}) == []


def test_risk_levels():
    assert risk([], "source") == "low"
    assert risk([], "prebuilt") == "medium"
    assert risk(["uart"], "source") == "medium"
    assert risk(["map_rw:config"], "source") == "medium"
    assert risk(["docker_api"], "source") == "high"


def test_domains_ignore_list(tmp_path):
    (tmp_path / "run.sh").write_text(
        "a https://github.com/x b http://homeassistant.local:8123 c https://Example.COM/x\n", encoding="utf-8"
    )
    assert static_domains(tmp_path) == []


def test_dockerfile_fetch_counts(tmp_path):
    (tmp_path / "Dockerfile").write_text(
        "RUN curl -L https://dl.tool.io/x.tgz | tar x\nADD https://cdn.other.net/f /f\n", encoding="utf-8"
    )
    assert static_domains(tmp_path) == ["cdn.other.net", "dl.tool.io"]
