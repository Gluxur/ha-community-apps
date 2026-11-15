from tools.catalog.compare import signal_changes, signals


def _scan(*apps):
    return {"apps": list(apps)}


def _app(slug="x", version="1", permissions=(), risk="low", domains=()):
    return {"slug": slug, "version": version, "permissions": list(permissions), "risk": risk, "domains": list(domains)}


def test_signals_shape():
    assert signals(_scan(_app(domains=["a.net"]))) == {"x": {"permissions": [], "risk": "low", "domains": ["a.net"]}}


def test_unchanged_when_only_version_differs():
    assert signal_changes(_scan(_app(version="1")), _scan(_app(version="2"))) == []


def test_new_permission():
    old = _scan(_app())
    new = _scan(_app(permissions=["docker_api"], risk="high"))
    assert signal_changes(old, new) == ["x: new permission docker_api", "x: risk low → high"]


def test_new_domain():
    assert signal_changes(_scan(_app()), _scan(_app(domains=["t.example.net"]))) == ["x: new domain t.example.net"]
    assert signal_changes(_scan(_app(domains=["t.example.net"])), _scan(_app())) == []


def test_new_app():
    assert signal_changes(_scan(_app()), _scan(_app(), _app(slug="y", risk="medium"))) == ["new app y (risk medium)"]
    assert signal_changes(_scan(_app(), _app(slug="y")), _scan(_app())) == []
