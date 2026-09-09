"""Break recolours the whole widget, not just the header badge.

The state was legible only by reading a label; a glance at the card said
nothing. This drives the real app into Break and reads the computed
background, because the failure this can ship is a token the override
misses, which no unit test would see.
"""

import os
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from nebula.tracker import Tracker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# The real system clock, not a fixture: ui_ready opens the day against
# datetime.now(), so a hardcoded NOW would silently rot once the seeded day
# rolls past midnight.
NOW = datetime.now().astimezone()

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
        resizable=False, frameless=True, transparent=True, easy_drag=True,
        on_top=True,
    )
    api.bind(window)

    def q(js):
        return window.evaluate_js(js)

    def check():
        for _ in range(100):
            if q("document.documentElement.dataset.nebulaReady === 'true'"):
                break
            time.sleep(0.1)
        else:
            print("FAIL: handshake never completed", flush=True)
            window.destroy()
            return

        q("document.querySelector('[data-break]').click()")
        time.sleep(0.5)

        print("STATUS:" + str(q("document.querySelector('main').dataset.status")), flush=True)
        print("CARD:" + str(q(
            "getComputedStyle(document.querySelector('main')).backgroundColor"
        )), flush=True)
        print("ROW:" + str(q(
            "getComputedStyle(document.querySelector('[data-allocation-name]')"
            ".closest('button')).backgroundColor"
        )), flush=True)
        print("HINT:" + str(q(
            "getComputedStyle(document.querySelector('[data-break]')).borderTopColor"
        )), flush=True)
        window.destroy()

    threading.Thread(target=check, daemon=True).start()
    webview.start()
    """
)


def _line(stdout: str, prefix: str) -> str | None:
    return next(
        (l.removeprefix(prefix) for l in stdout.splitlines() if l.startswith(prefix)),
        None,
    )


@pytest.mark.gui
def test_break_recolours_the_card_and_its_rows(tmp_path):
    assert (PROJECT_ROOT / "dist" / "index.html").exists(), (
        "run 'pnpm build' in frontend/ before this test"
    )

    data = tmp_path / "data.json"
    tracker = Tracker(data)
    tracker.open(NOW)
    view = tracker.add_allocation("Work", 3 * 3600, NOW)
    tracker.activate(view.allocations[0].id, NOW)

    result = subprocess.run(
        [sys.executable, "-c", DRIVER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "NEBULA_DATA": str(data),
        },
    )
    out = result.stdout + result.stderr

    assert _line(result.stdout, "STATUS:") == "BREAK", out
    # #111418, #151a1a: the card and its rows, not just a badge.
    assert _line(result.stdout, "CARD:") == "rgb(17, 20, 24)", out
    assert _line(result.stdout, "ROW:") == "rgb(21, 26, 26)", out
    # The engaged BREAK button keeps the green it already had.
    assert _line(result.stdout, "HINT:") == "rgb(127, 227, 184)", out
