import re

from tools.catalog.report import render_report

FORBIDDEN = re.compile(r"\b(safe|verified|secure|sûr|vérifié|sans risque)\b", re.IGNORECASE)

SCAN = {
    "apps": [
        {"slug": "a", "name": "App A", "version": "1", "risk": "high", "permissions": ["docker_api", "host_network"],
         "domains": ["api.x.net"], "dynamic": "started", "image": "prebuilt", "arch": ["amd64"], "error": None},
        {"slug": "b", "name": "App B", "version": "2", "risk": "low", "permissions": [], "domains": [],
         "dynamic": "failed", "image": "source", "arch": ["amd64"], "error": None},
    ]
}


def test_report_contents():
    text = render_report("owner/repo", "0123456789abcdef", SCAN, [])
    assert "owner/repo" in text and "0123456" in text and "01234567" not in text
    for needle in ("App A", "App B", "high", "low", "docker_api", "host_network", "api.x.net", "started", "failed"):
        assert needle in text
    assert "This report lists signals; it does not prove an app is harmless." in text
    assert "Blocking" not in text
    assert not FORBIDDEN.search(text)


def test_report_blocking_errors():
    text = render_report("owner/repo", "0123456789", SCAN, ["repository: must be 'owner/repo'"])
    assert "Blocking" in text and "repository: must be 'owner/repo'" in text
