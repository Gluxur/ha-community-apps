from tools.catalog.dynamic_scan import image_for, parse_dnsmasq_log

LOG = """\
dnsmasq[1]: started, version 2.90 cachesize 150
dnsmasq[1]: query[A] API.Weather.net from 172.18.0.3
dnsmasq[1]: forwarded api.weather.net to 1.1.1.1
dnsmasq[1]: query[AAAA] api.weather.net from 172.18.0.3
dnsmasq[1]: query[A] github.com from 172.18.0.3
dnsmasq[1]: query[A] ntp.pool.org. from 172.18.0.3
"""


def test_parse_dnsmasq_log():
    assert parse_dnsmasq_log(LOG) == ["api.weather.net", "ntp.pool.org"]


def test_image_for_prebuilt(tmp_path):
    config = {"image": "ghcr.io/x/{arch}-b", "version": 1.2, "arch": ["amd64", "aarch64"]}
    assert image_for(tmp_path, config) == ("pull", "ghcr.io/x/amd64-b:1.2")


def test_image_for_build(tmp_path):
    (tmp_path / "build.yaml").write_text("build_from:\n  amd64: ghcr.io/hassio-addons/base:18.0.0\n", encoding="utf-8")
    assert image_for(tmp_path, {"arch": ["amd64"]}) == ("build", "ghcr.io/hassio-addons/base:18.0.0")


def test_image_for_build_without_build_file(tmp_path):
    assert image_for(tmp_path, {"arch": ["amd64"]}) == ("build", "")


def test_image_for_unsupported_arch(tmp_path):
    assert image_for(tmp_path, {"arch": ["aarch64"], "image": "x/{arch}"}) is None


def test_run_app_without_docker_reports_failed(tmp_path, monkeypatch):
    import subprocess

    from tools.catalog import dynamic_scan

    def missing(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", missing)
    config = {"arch": ["amd64"], "image": "x/{arch}", "version": "1"}
    assert dynamic_scan.run_app(tmp_path, config, timeout=1) == {"status": "failed", "domains": []}


def test_parse_ignores_supervisor_internal_names():
    log = (
        "dnsmasq[1]: query[A] supervisor.home from 10.0.0.2\n"
        "dnsmasq[1]: query[A] homeassistant.internal.cloudapp.net from 10.0.0.2\n"
        "dnsmasq[1]: query[A] hassio.lan from 10.0.0.2\n"
        "dnsmasq[1]: query[A] supervisor.example.net from 10.0.0.2\n"
    )
    assert parse_dnsmasq_log(log) == []
