from datetime import datetime, timezone

from tools.catalog.build import build_catalog

REVIEWED = {"by": "Gluxur", "at": "2026-11-15", "commit": "abc"}
SCAN = {"commit": "abc", "at": "2026-11-15T03:00:00Z", "apps": [{"slug": "x", "path": "x", "risk": "low"}]}


def test_build_filters_and_shapes():
    entries = [
        {"repository": "z/approved", "added_by": "catalog", "status": "approved", "reviewed": REVIEWED, "scan": SCAN},
        {"repository": "a/flagged", "status": "flagged", "reviewed": REVIEWED, "scan": SCAN, "pending_scan": SCAN},
        {"repository": "m/removed", "status": "removed", "removed_reason": "asked by author", "reviewed": REVIEWED, "scan": SCAN},
        {"repository": "p/pending", "status": "pending"},
        {"repository": "q/new"},
    ]
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    data = build_catalog(entries, now)
    assert data["schema_version"] == 1
    assert data["generated_at"] == "2026-11-15T12:00:00Z"
    repos = data["repositories"]
    assert [r["repository"] for r in repos] == ["a/flagged", "m/removed", "z/approved"]
    assert set(repos[0]) == {"repository", "added_by", "status", "reviewed", "scan"}
    assert repos[0]["added_by"] == "author"
    assert repos[1] == {"repository": "m/removed", "status": "removed", "removed_reason": "asked by author"}
    assert repos[2]["added_by"] == "catalog"
    assert "path" not in repos[2]["scan"]["apps"][0]
