import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "community_apps"


def load(name: str):
    """Load a Home Assistant-free module of the integration by file path."""
    spec = importlib.util.spec_from_file_location(f"community_apps_{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def catalog():
    return load("catalog")
