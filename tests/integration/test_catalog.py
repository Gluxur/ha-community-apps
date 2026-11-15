import pytest


def _repo(name="A/B", status="approved", apps=None, **extra):
    return {
        "repository": name,
        "added_by": "author",
        "status": status,
        "reviewed": {"by": "Gluxur", "at": "2026-11-15", "commit": "abc"},
        "scan": {"commit": "abc", "at": "2026-11-15T03:00:00Z", "apps": apps if apps is not None else [_app()]},
        **extra,
    }


def _app(slug="x", risk="low", arch=("amd64",)):
    return {"slug": slug, "name": slug.upper(), "risk": risk, "arch": list(arch), "permissions": [], "domains": []}


def test_parse_rejects_unknown_schema(catalog):
    with pytest.raises(catalog.CatalogError):
        catalog.parse_catalog({"schema_version": 2, "repositories": []}, 1)
    with pytest.raises(catalog.CatalogError):
        catalog.parse_catalog("x", 1)
    with pytest.raises(catalog.CatalogError):
        catalog.parse_catalog({"schema_version": 1}, 1)
    assert catalog.parse_catalog({"schema_version": 1, "repositories": [_repo(), "junk"]}, 1) == [_repo()]


def test_normalize_repo_url_variants(catalog):
    for url in ("https://github.com/Owner/Repo.git/", "http://github.com/owner/repo", "https://github.com/owner/repo"):
        assert catalog.normalize_repo_url(url) == "owner/repo"
    assert catalog.normalize_repo_url("https://gitlab.com/a/b") is None
    assert catalog.normalize_repo_url("https://github.com/a") is None
    assert catalog.normalize_repo_url("local") is None


def test_repo_url(catalog):
    assert catalog.repo_url("Owner/Repo") == "https://github.com/Owner/Repo"


STORE = [{"slug": "abc123", "source": "https://github.com/A/B"}, {"slug": "core", "source": "core"}]
STORE_ADDONS = [{"slug": "abc123_x", "repository": "abc123"}, {"slug": "abc123_y", "repository": "abc123"}]
INSTALLED = [{"slug": "abc123_x", "repository": "abc123", "name": "X"}]


def test_merge_state_marks_added_installed_compatible(catalog):
    repos = [_repo(apps=[_app("x"), _app("y", arch=("aarch64",))]), _repo("c/d", apps=[_app("z")])]
    merged = catalog.merge_state(repos, STORE, INSTALLED, STORE_ADDONS, ["amd64", "i386"])
    ab, cd = merged
    assert ab["added"] is True and ab["store_slug"] == "abc123"
    x, y = ab["scan"]["apps"]
    assert (x["installed"], x["compatible"], x["store_slug"]) == (True, True, "abc123_x")
    assert (y["installed"], y["compatible"], y["store_slug"]) == (False, False, "abc123_y")
    assert cd["added"] is False and cd["store_slug"] is None
    assert cd["scan"]["apps"][0] == {**_app("z"), "installed": False, "compatible": True, "store_slug": None}
    assert repos[0]["scan"]["apps"][0].get("installed") is None  # input not mutated


def test_merge_state_removed_entry(catalog):
    merged = catalog.merge_state([{"repository": "a/b", "status": "removed", "removed_reason": "r"}], STORE, INSTALLED, STORE_ADDONS, ["amd64"])
    assert merged[0]["added"] is True and merged[0]["status"] == "removed"


def test_issues_for_flagged_and_removed(catalog):
    flagged = catalog.issues_for([_repo(status="flagged")], STORE, INSTALLED)
    assert flagged == [{"id": "flagged_abc123_x", "status": "flagged", "app": "X", "repository": "A/B", "reason": "signals changed since review"}]
    removed = catalog.issues_for([{"repository": "a/b", "status": "removed", "removed_reason": "asked by author"}], STORE, INSTALLED)
    assert removed == [{"id": "removed_abc123_x", "status": "removed", "app": "X", "repository": "a/b", "reason": "asked by author"}]
    assert catalog.issues_for([_repo()], STORE, INSTALLED) == []
    assert catalog.issues_for([_repo("c/d", status="flagged")], STORE, INSTALLED) == []


def test_can_add(catalog):
    for status in ("pending", "flagged", "removed"):
        assert catalog.can_add(_repo(status=status), False) == "not_approved"
    high = _repo(apps=[_app(risk="high")])
    assert catalog.can_add(high, False) == "confirmation_required"
    assert catalog.can_add(high, True) is None
    assert catalog.can_add(_repo(), False) is None
