"""Where the app looks for its frontend and icon, frozen or not."""

import sys
from pathlib import Path

from nebula import app


def test_from_a_source_checkout_the_root_is_the_repo():
    """src/nebula/app.py -> the repo containing pyproject.toml."""
    root = app.resolve_project_root()
    assert (root / "pyproject.toml").exists()


def test_inside_a_bundle_the_root_is_meipass(monkeypatch):
    """PyInstaller unpacks data next to the executable, not beside the source."""
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/nebula-bundle", raising=False)
    assert app.resolve_project_root() == Path("/tmp/nebula-bundle")


def test_the_frontend_and_icon_hang_off_the_root(monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/nebula-bundle", raising=False)
    root = app.resolve_project_root()
    assert root / "dist" / "index.html" == Path("/tmp/nebula-bundle/dist/index.html")
    assert root / "assets" / "Nebula.icns" == Path(
        "/tmp/nebula-bundle/assets/Nebula.icns"
    )
