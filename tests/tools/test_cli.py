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
