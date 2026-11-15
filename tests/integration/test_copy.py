"""User-facing text never claims an app is safe (spec anti-goal)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = re.compile(r"\b(safe|verified|secure|sûr|vérifié|sans risque)\b", re.IGNORECASE)
FILES = [
    ROOT / "custom_components/community_apps/frontend/panel.js",
    *sorted((ROOT / "custom_components/community_apps/translations").glob("*.json")),
    ROOT / "README.md",
]


def test_no_forbidden_words():
    hits = []
    for path in FILES:
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert hits == []


DISCLAIMER = "No warranty. Apps are third-party software; you install them at your own risk. Being listed is not an endorsement."


def test_disclaimer_shown_and_no_review_promise():
    panel = (ROOT / "custom_components/community_apps/frontend/panel.js").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    en = (ROOT / "custom_components/community_apps/translations/en.json").read_text(encoding="utf-8")
    for text in (panel, readme, en):
        assert DISCLAIMER in text
        assert "reviewed by a person" not in text.lower()
    fr = (ROOT / "custom_components/community_apps/translations/fr.json").read_text(encoding="utf-8")
    assert "Aucune garantie" in fr and "relu par une personne" not in fr
