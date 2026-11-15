import json
import subprocess
import sys

import yaml

from tools.catalog.__main__ import main


def test_cli_validate_rejects_extra_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CODEOWNERS").write_text("/catalog/ @Gluxur\n", encoding="utf-8")
    entry = tmp_path / "catalog/repositories/a/b.yaml"
    entry.parent.mkdir(parents=True)
    entry.write_text("repository: a/b\n", encoding="utf-8")
    args = ["validate", "--author", "a", "--permission", "none", "--changed"]
    assert main(args + ["catalog/repositories/a/b.yaml"]) == 0
    assert main(args + ["catalog/repositories/a/b.yaml", "tools/x.py"]) == 1
    assert "tools/x.py" in capsys.readouterr().err


def test_cli_validate_rejects_stranger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CODEOWNERS").write_text("/catalog/ @Gluxur\n", encoding="utf-8")
    entry = tmp_path / "catalog/repositories/a/b.yaml"
    entry.parent.mkdir(parents=True)
    entry.write_text("repository: a/b\nadded_by: catalog\n", encoding="utf-8")
    base = ["validate", "--permission", "none", "--changed", "catalog/repositories/a/b.yaml"]
    assert main(base + ["--author", "someone"]) == 1
    assert main(base + ["--author", "gluxur"]) == 0


def test_apply_review_sets_fields(tmp_path):
    entry = tmp_path / "b.yaml"
    entry.write_text("repository: a/b\n", encoding="utf-8")
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"repository": "a/b", "commit": "c0ffee", "at": "2026-11-15T03:00:00Z", "errors": [], "apps": []}))
    assert main(["apply-review", str(entry), "--reviewer", "Gluxur", "--scan", str(scan)]) == 0
    data = yaml.safe_load(entry.read_text(encoding="utf-8"))
    assert list(data) == ["repository", "added_by", "status", "reviewed", "scan"]
    assert data["status"] == "approved" and data["added_by"] == "author"
    assert data["reviewed"]["by"] == "Gluxur" and data["reviewed"]["commit"] == "c0ffee"
    assert data["scan"]["commit"] == "c0ffee" and "errors" not in data["scan"] and "repository" not in data["scan"]


def test_module_runs():
    out = subprocess.run([sys.executable, "-m", "tools.catalog", "--help"], capture_output=True, text=True)
    assert out.returncode == 0 and "nightly" in out.stdout


def test_scan_reports_clone_failure(monkeypatch):
    from tools.catalog import __main__ as cli

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(128, ["git", "clone"])

    monkeypatch.setattr(cli, "_git", fail)
    result = cli.scan("owner/repo")
    assert result["apps"] == [] and result["commit"] == ""
    assert result["errors"] == ["could not fetch https://github.com/owner/repo (git exit 128)"]


def test_nightly_keeps_scan_when_fetch_fails(tmp_path, monkeypatch):
    from tools.catalog import __main__ as cli

    monkeypatch.chdir(tmp_path)
    entry = tmp_path / "catalog/repositories/a/b.yaml"
    entry.parent.mkdir(parents=True)
    old_scan = {"commit": "old", "at": "x", "apps": [{"slug": "x", "permissions": [], "risk": "low", "domains": []}]}
    cli.write_entry(entry, {"repository": "a/b", "added_by": "author", "status": "approved",
                            "reviewed": {"by": "G", "at": "d", "commit": "old"}, "scan": old_scan})
    monkeypatch.setattr(cli, "remote_head", lambda name: "new")
    monkeypatch.setattr(cli, "is_archived", lambda name: False)
    monkeypatch.setattr(cli, "scan", lambda *a, **k: {"repository": "a/b", "commit": "", "at": "y",
                                                      "errors": ["could not fetch"], "apps": []})
    assert main(["nightly", "--flagged-out", "flagged.json"]) == 0
    data = yaml.safe_load(entry.read_text(encoding="utf-8"))
    assert data["status"] == "approved" and data["scan"] == old_scan
    assert json.loads((tmp_path / "flagged.json").read_text()) == [
        {"repository": "a/b", "file": "catalog/repositories/a/b.yaml", "changes": ["repository unavailable"]}
    ]


def test_pending_lists_entries_without_status(tmp_path, monkeypatch, capsys):
    from tools.catalog import __main__ as cli

    monkeypatch.chdir(tmp_path)
    base = tmp_path / "catalog/repositories"
    (base / "a").mkdir(parents=True)
    (base / "c").mkdir()
    (base / "a/b.yaml").write_text("repository: a/b\nadded_by: catalog\n", encoding="utf-8")
    cli.write_entry(base / "c/d.yaml", {"repository": "c/d", "status": "approved"})
    assert main(["pending"]) == 0
    assert capsys.readouterr().out.split() == ["catalog/repositories/a/b.yaml"]


def test_scan_dynamic_budget_runs_high_risk_first(monkeypatch, tmp_path):
    from tools.catalog import __main__ as cli
    from tools.catalog import dynamic_scan

    repo = tmp_path / "src"
    for slug, extra in (("a_low", ""), ("b_high", "docker_api: true\n"), ("c_med", "host_network: true\n")):
        (repo / slug).mkdir(parents=True)
        (repo / slug / "config.yaml").write_text(f"slug: {slug}\nname: {slug}\nversion: '1'\narch: [amd64]\n{extra}", encoding="utf-8")
    (repo / "repository.yaml").write_text("name: x\n", encoding="utf-8")

    def fake_git(*args, cwd=None):
        if args[0] == "clone":
            import shutil
            shutil.copytree(repo, args[-1])
        return "c0ffee"

    clock = iter([0, 0, 100, 200, 300])
    ran = []
    monkeypatch.setattr(cli, "_git", fake_git)
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(dynamic_scan, "run_app", lambda d, c, timeout=180: ran.append(c["slug"]) or {"status": "started", "domains": []})
    result = cli.scan("o/r", dynamic=True, dynamic_budget=150)
    assert ran == ["b_high", "c_med"]
    status = {a["slug"]: a["dynamic"] for a in result["apps"]}
    assert status == {"a_low": "skipped", "b_high": "started", "c_med": "started"}


def test_build_uses_repository_stats(tmp_path, monkeypatch):
    from tools.catalog import __main__ as cli

    monkeypatch.chdir(tmp_path)
    entry = tmp_path / "catalog/repositories/a/b.yaml"
    entry.parent.mkdir(parents=True)
    cli.write_entry(entry, {"repository": "a/b", "status": "approved",
                            "reviewed": {"by": "G", "at": "d", "commit": "c"}, "scan": {"commit": "c", "at": "x", "apps": []}})
    seen = []
    monkeypatch.setattr(cli, "fetch_stats", lambda names: seen.append(names) or {"a/b": {"stars": 7, "updated_at": "2026-11-01T00:00:00Z"}})
    assert main(["build", "--out", "site/catalog.json"]) == 0
    repo = json.loads((tmp_path / "site/catalog.json").read_text())["repositories"][0]
    assert seen == [["a/b"]] and repo["stars"] == 7


def test_fetch_stats_skips_failures(monkeypatch):
    import urllib.error

    from tools.catalog import __main__ as cli

    class Resp:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.body

    def fake_urlopen(request, timeout=30):
        if request.full_url.endswith("/bad/repo"):
            raise urllib.error.URLError("boom")
        return Resp(b'{"stargazers_count": 5, "pushed_at": "2026-11-02T00:00:00Z"}')

    monkeypatch.setattr(cli.urllib.request, "urlopen", fake_urlopen)
    assert cli.fetch_stats(["good/repo", "bad/repo"]) == {"good/repo": {"stars": 5, "updated_at": "2026-11-02T00:00:00Z"}}
