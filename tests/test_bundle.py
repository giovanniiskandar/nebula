"""The built .app, exercised as an artifact rather than as a recipe.

Every packaging bug found so far appeared only in a real bundle: a path that
resolves differently, a data file that was never collected, a plist value that
silently defaults. Asserting on the spec file would catch none of them.

Marked `slow` -- the build takes about a minute, so this stays out of the
pre-commit hook and runs on demand.
"""

import plistlib
import subprocess
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = PROJECT_ROOT / "release" / "Nebula.app"


def _running() -> int:
    result = subprocess.run(
        ["pgrep", "-f", "Nebula.app/Contents/MacOS"],
        capture_output=True,
        text=True,
        check=False,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def _quit() -> None:
    subprocess.run(
        ["pkill", "-f", "Nebula.app/Contents/MacOS"], check=False, capture_output=True
    )
    time.sleep(1)


@pytest.fixture(scope="module")
def built_app() -> Path:
    """Build once for the whole module; the build is the slow part."""
    subprocess.run(
        [str(PROJECT_ROOT / "scripts" / "build.sh")],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert APP.exists()
    return APP


@pytest.mark.slow
def test_the_plist_carries_the_identity_macos_needs(built_app: Path):
    plist = plistlib.loads((built_app / "Contents" / "Info.plist").read_bytes())

    # Reverse-DNS is what makes macOS single-instance the app.
    assert plist["CFBundleIdentifier"] == "com.giovanniiskandar.nebula"
    assert plist["CFBundleName"] == "Nebula"
    assert plist["CFBundleIconFile"] == "Nebula.icns"

    # The version is read from pyproject rather than repeated, so they agree.
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()
    version = next(
        line.split('"')[1]
        for line in pyproject.splitlines()
        if line.startswith("version = ")
    )
    assert plist["CFBundleShortVersionString"] == version


@pytest.mark.slow
def test_the_frontend_is_inside_the_bundle(built_app: Path):
    """A missing data file only shows up at runtime, so check it is collected."""
    frameworks = built_app / "Contents" / "Frameworks"
    assert (frameworks / "dist" / "index.html").exists()
    assert (frameworks / "assets" / "Nebula.icns").exists()
    # pywebview globs these at runtime; static analysis cannot see them.
    js = list((built_app / "Contents" / "Resources" / "webview" / "js").glob("*.js"))
    assert len(js) >= 4, [p.name for p in js]


@pytest.mark.slow
def test_it_launches_and_shows_its_window(built_app: Path):
    _quit()
    try:
        subprocess.run(["open", str(built_app)], check=True)
        time.sleep(6)

        import Quartz

        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        found = [
            dict(w["kCGWindowBounds"])
            for w in windows
            if str(w.get("kCGWindowOwnerName", "")) == "Nebula"
        ]
        assert found, "no window owned by Nebula"
        assert int(found[0]["Width"]) == 384
        assert int(found[0]["Height"]) == 684
    finally:
        _quit()


@pytest.mark.slow
def test_a_second_open_does_not_start_a_second_process(built_app: Path):
    """PRD §15, satisfied by the bundle identifier rather than by a lock."""
    _quit()
    try:
        subprocess.run(["open", str(built_app)], check=True)
        time.sleep(6)
        assert _running() == 1

        subprocess.run(["open", str(built_app)], check=True)
        time.sleep(4)
        assert _running() == 1
    finally:
        _quit()
