"""Sort order of the panel, run under Node with minimal DOM stubs."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PANEL = Path(__file__).resolve().parents[2] / "custom_components/community_apps/frontend/panel.js"

ROWS = [
    {"repo": {"repository": "a/recent", "stars": 10, "updated_at": "2026-11-12T00:00:00Z"}, "app": {"name": "alpha", "risk": "low"}},
    {"repo": {"repository": "b/popular", "stars": 500, "updated_at": "2026-01-01T00:00:00Z"}, "app": {"name": "Zeta", "risk": "high"}},
    {"repo": {"repository": "c/none"}, "app": {"name": "Gamma", "risk": "medium"}},
]


def _sorted(mode):
    if not shutil.which("node"):
        pytest.skip("node not installed")
    script = (
        "globalThis.HTMLElement = class {}; globalThis.customElements = { define() {}, get() {} };\n"
        + PANEL.read_text(encoding="utf-8")
        + f"\nconsole.log(JSON.stringify(sortRows({json.dumps(ROWS)}, {json.dumps(mode)}).map(r => r.app.name)));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_sort_by_stars_default_missing_last():
    assert _sorted("stars") == ["Zeta", "alpha", "Gamma"]


def test_sort_by_recent_activity():
    assert _sorted("updated") == ["alpha", "Zeta", "Gamma"]


def test_sort_by_name_case_insensitive():
    assert _sorted("name") == ["alpha", "Gamma", "Zeta"]


def test_sort_by_risk_highest_first():
    assert _sorted("risk") == ["Zeta", "Gamma", "alpha"]
