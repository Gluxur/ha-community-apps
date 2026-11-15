"""Table logic of the panel (status, filters, groups, sorts), run under Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PANEL = Path(__file__).resolve().parents[2] / "custom_components/community_apps/frontend/panel.js"
NOW = "2026-11-20T00:00:00Z"


def run(expr):
    if not shutil.which("node"):
        pytest.skip("node not installed")
    script = (
        "globalThis.HTMLElement = class {}; globalThis.customElements = { define() {}, get() {} };\n"
        + PANEL.read_text(encoding="utf-8")
        + f"\nconst NOW = Date.parse({json.dumps(NOW)});\nconsole.log(JSON.stringify({expr}));"
    )
    out = subprocess.run(["node", "--input-type=module"], input=script, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def repo(name, status="approved", added=False, reviewed="2026-01-01", added_by="author", stars=None):
    return {"repository": name, "status": status, "added": added, "added_by": added_by, "stars": stars,
            "reviewed": {"by": "G", "at": reviewed, "commit": "c"}}


def app(name, risk="low", installed=False, compatible=True):
    return {"slug": name.lower(), "name": name, "risk": risk, "installed": installed, "compatible": compatible}


ROWS = [
    {"repo": repo("a/flag", status="flagged", added=True), "app": app("Flagged", installed=True)},
    {"repo": repo("b/inst", added=True), "app": app("Inst", risk="high", installed=True)},
    {"repo": repo("b/inst", added=True), "app": app("Added", risk="medium")},
    {"repo": repo("c/new", reviewed="2026-11-15", added_by="catalog"), "app": app("Fresh")},
    {"repo": repo("d/old"), "app": app("Old", compatible=False)},
]
R = json.dumps(ROWS)


def test_row_status_priority():
    assert run(f"{R}.map(r => rowStatus(r.repo, r.app, NOW))") == ["flagged", "installed", "added", "new", "available"]


def test_filters_or_within_and_across():
    names = lambda f: run(f"filterRows({R}, {json.dumps(f)}, '', NOW).map(r => r.app.name)")
    assert names({}) == ["Flagged", "Inst", "Added", "Fresh", "Old"]
    assert names({"status": ["installed", "flagged"]}) == ["Flagged", "Inst"]
    assert names({"status": ["installed", "added"], "risk": ["medium"]}) == ["Added"]
    assert names({"source": ["catalog"]}) == ["Fresh"]
    assert names({"compatible": True}) == ["Flagged", "Inst", "Added", "Fresh"]


def test_search_matches_name_repository_description():
    assert run(f"filterRows({R}, {{}}, 'C/NEW', NOW).map(r => r.app.name)") == ["Fresh"]


def test_group_by_status_in_marketplace_order():
    groups = run(f"groupRows({R}, 'status', NOW).map(g => [g.key, g.label, g.rows.length])")
    assert groups == [["flagged", "Back in review", 1], ["installed", "Installed", 1], ["added", "Repository added", 1],
                      ["new", "New", 1], ["available", "Available", 1]]


def test_group_by_risk_and_repository_and_none():
    assert run(f"groupRows({R}, 'risk', NOW).map(g => g.key)") == ["high", "medium", "low"]
    assert run(f"groupRows({R}, 'repository', NOW).map(g => g.key)") == ["a/flag", "b/inst", "c/new", "d/old"]
    assert run(f"groupRows({R}, 'none', NOW).map(g => [g.key, g.rows.length])") == [["all", 5]]


def test_sort_by_status_and_repository():
    assert run(f"sortRows({R}, 'status', NOW).map(r => r.app.name)") == ["Flagged", "Inst", "Added", "Fresh", "Old"]
    assert run(f"sortRows({R}, 'repository', NOW).map(r => r.app.name)") == ["Flagged", "Added", "Inst", "Fresh", "Old"]
