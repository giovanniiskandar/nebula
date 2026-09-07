"""The dashboard renders real data in the real app.

Driving the built app is what caught the phase 2 bugs that unit tests passed
straight over, so the dashboard gets the same treatment.
"""

import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from nebula.tracker import Tracker

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DRIVER = textwrap.dedent(
    """
    import os, time, threading
    from pathlib import Path

    import webview

    from nebula import app as napp
    from nebula.tracker import Tracker

    api = napp.Api(Tracker(Path(os.environ["NEBULA_DATA"])))
    window = webview.create_window(
        "Nebula", url=napp.resolve_url(False), js_api=api,
        width=napp.WINDOW_WIDTH, height=napp.WINDOW_HEIGHT,
        frameless=True, transparent=True, easy_drag=True, on_top=True,
    )
    api.bind(window)

    def check():
        for _ in range(100):
            if window.evaluate_js(
                "document.documentElement.dataset.nebulaReady === 'true'"
            ):
                break
            time.sleep(0.1)
        else:
            print("FAIL: handshake never completed", flush=True)
            window.destroy()
            return
        print("NAMES:" + window.evaluate_js(
            "JSON.stringify(Array.from("
            "document.querySelectorAll('[data-allocation-name]'))"
            ".map(function (n) { return n.textContent; }))"
        ), flush=True)
        print("CONTROLS:" + window.evaluate_js(
            "JSON.stringify(document.querySelector('[data-break]') ? ["
            "document.querySelector('[data-break]').textContent,"
            "document.querySelector('[data-complete]').textContent] : [])"
        ), flush=True)
        print("ERROR:" + window.evaluate_js(
            "document.querySelector('[data-error]')"
            " ? document.querySelector('[data-error]').textContent : ''"
        ), flush=True)
        window.destroy()

    threading.Thread(target=check, daemon=True).start()
    webview.start()
    """
)


def _run(data_file: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", DRIVER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        # pytest's `pythonpath` setting is not inherited by a subprocess.
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "NEBULA_DATA": str(data_file),
        },
    )


def _line(stdout: str, prefix: str) -> str | None:
    return next(
        (l.removeprefix(prefix) for l in stdout.splitlines() if l.startswith(prefix)),
        None,
    )


@pytest.mark.gui
def test_dashboard_renders_seeded_allocations(tmp_path):
    assert (PROJECT_ROOT / "dist" / "index.html").exists(), (
        "run 'pnpm build' in frontend/ before this test"
    )

    data_file = tmp_path / "data.json"
    now = datetime.now().astimezone()
    tracker = Tracker(data_file)
    tracker.add_allocation("Work", 3 * 3600, now)
    tracker.add_allocation("Learning", 2 * 3600, now)

    result = _run(data_file)

    names = _line(result.stdout, "NAMES:")
    assert names is not None, result.stdout + result.stderr
    assert json.loads(names) == ["Work", "Learning"]

    controls = _line(result.stdout, "CONTROLS:")
    assert controls is not None, result.stdout + result.stderr
    # PRD §11: both always visible.
    assert json.loads(controls) == ["BREAK", "COMPLETE"]


@pytest.mark.gui
def test_empty_state_renders_when_there_are_no_allocations(tmp_path):
    """PRD §10.1. Adding allocations is 3c, so the button is disabled."""
    result = _run(tmp_path / "data.json")

    names = _line(result.stdout, "NAMES:")
    assert names is not None, result.stdout + result.stderr
    assert json.loads(names) == []


@pytest.mark.gui
def test_a_corrupt_data_file_renders_a_named_error(tmp_path):
    """Not a blank card: pywebview rejects the promise with the message."""
    data_file = tmp_path / "data.json"
    data_file.write_text("not json at all", encoding="utf-8")

    result = _run(data_file)

    message = _line(result.stdout, "ERROR:")
    assert message is not None, result.stdout + result.stderr
    assert "Something went wrong" in message
    # The path matters: a person has to be able to go and fix the file.
    assert str(data_file) in message
