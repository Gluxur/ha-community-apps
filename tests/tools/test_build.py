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


def test_build_adds_repository_stats():
    entries = [
        {"repository": "a/one", "status": "approved", "reviewed": REVIEWED, "scan": SCAN},
        {"repository": "b/two", "status": "approved", "reviewed": REVIEWED, "scan": SCAN},
        {"repository": "c/gone", "status": "removed", "removed_reason": "r"},
    ]
    stats = {"a/one": {"stars": 42, "updated_at": "2026-11-10T08:00:00Z"}, "c/gone": {"stars": 1, "updated_at": "x"}}
    repos = build_catalog(entries, datetime(2026, 11, 15, tzinfo=timezone.utc), stats)["repositories"]
    assert repos[0]["stars"] == 42 and repos[0]["updated_at"] == "2026-11-10T08:00:00Z"
    assert "stars" not in repos[1] and "updated_at" not in repos[1]
    assert set(repos[2]) == {"repository", "status", "removed_reason"}
