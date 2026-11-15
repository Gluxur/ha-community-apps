"""Make this repository's custom_components visible next to the test harness's own."""

from pathlib import Path

try:
    import custom_components
except ImportError:  # harness not installed: tests in this folder are skipped
    custom_components = None

if custom_components is not None:
    ours = str(Path(__file__).resolve().parents[2] / "custom_components")
    if ours not in list(custom_components.__path__):
        custom_components.__path__.append(ours)
