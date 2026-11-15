from tools.catalog.model import (
    check_pr_paths,
    entry_path,
    is_allowed_submitter,
    validate_entry,
)


def test_entry_path():
    assert entry_path("Hassio-Addons/Repository") == "catalog/repositories/hassio-addons/repository.yaml"


def test_submitted_entry_only_repository():
    path = entry_path("a/b")
    assert validate_entry({"repository": "a/b"}, path, submitted=True) == []
    for key, value in (
        ("status", "approved"),
        ("reviewed", {"by": "x"}),
        ("scan", {}),
        ("removed_reason", "x"),
    ):
        errors = validate_entry({"repository": "a/b", key: value}, path, submitted=True)
        assert len(errors) == 1 and key in errors[0]
    assert validate_entry({"repository": "a/b", "added_by": "catalog"}, path, submitted=True) == []
    assert validate_entry({"repository": "a/b", "added_by": "author"}, path, submitted=True) == []
    assert len(validate_entry({"repository": "a/b", "added_by": "x"}, path, submitted=True)) == 1


def test_repository_format():
    for bad in ("a/b c", "a", "https://github.com/a/b"):
        assert validate_entry({"repository": bad}, "catalog/repositories/a/b.yaml", submitted=True)
    assert validate_entry({"repository": "a/b"}, "catalog/repositories/a/c.yaml", submitted=True)
    assert validate_entry({}, "catalog/repositories/a/b.yaml", submitted=True)


def _full(**over):
    entry = {
        "repository": "a/b",
        "added_by": "author",
        "status": "approved",
        "reviewed": {"by": "Gluxur", "at": "2026-11-15", "commit": "abc"},
        "scan": {"commit": "abc", "at": "2026-11-15T03:00Z", "apps": []},
    }
    entry.update(over)
    return entry


def test_full_entry_valid():
    path = entry_path("a/b")
    assert validate_entry(_full(), path, submitted=False) == []
    assert validate_entry(_full(status="ok"), path, submitted=False)
    assert validate_entry(_full(status="removed"), path, submitted=False)
    assert validate_entry(_full(status="removed", removed_reason="asked"), path, submitted=False) == []


def test_check_pr_paths():
    assert check_pr_paths(["catalog/repositories/a/b.yaml"]) == []
    assert len(check_pr_paths(["catalog/repositories/a/b.yaml", "tools/catalog/model.py"])) == 1
    assert len(check_pr_paths(["catalog/repositories/a/b.yaml", "catalog/repositories/c/d.yaml"])) == 1
    assert check_pr_paths([".github/workflows/x.yml"])
    assert check_pr_paths([])


def test_is_allowed_submitter():
    reviewers = {"Gluxur"}
    assert is_allowed_submitter("A/b", "a", None, reviewers, "author")
    for perm in ("admin", "maintain", "write"):
        assert is_allowed_submitter("a/b", "z", perm, reviewers, "author")
    for perm in ("read", "triage", None):
        assert not is_allowed_submitter("a/b", "z", perm, reviewers, "author")
    assert is_allowed_submitter("a/b", "gluxur", None, reviewers, "catalog")
    assert not is_allowed_submitter("a/b", "z", "admin", reviewers, "catalog")
