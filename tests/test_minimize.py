"""Minimizing collapses the real window, and expanding restores it.

The failure this feature can ship is a resize that works in isolation but
not through the bridge, which the unit tests cannot see.
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

        q("document.querySelector('[data-minimize]').click()")
        time.sleep(0.8)
        print("BAR:" + str(q("!!document.querySelector('[data-minimized]')")), flush=True)
        print("MINI_H:" + str(q("window.innerHeight")), flush=True)
        print(
            "BAR_H:"
            + str(
                q(
                    "document.querySelector('[data-minimized]')"
                    ".getBoundingClientRect().height"
                )
            ),
            flush=True,
        )

        # data-expand's centre is still clear of [data-close] even when they
        # overlap -- every prior test clicked centres, which is exactly why
        # the overlap shipped unnoticed. Check the actual boxes instead.
        print(
            "OVERLAP:"
            + str(
                q(
                    "(() => {"
                    "const c = document.querySelector('[data-close]')"
                    ".getBoundingClientRect();"
                    "const controls = document.querySelectorAll("
                    "'[data-mini-break],[data-mini-complete],[data-expand]');"
                    "return Array.from(controls).some((el) => {"
                    "const r = el.getBoundingClientRect();"
                    "const ix = Math.min(c.right, r.right) - Math.max(c.left, r.left);"
                    "const iy = Math.min(c.bottom, r.bottom) - Math.max(c.top, r.top);"
                    "return ix > 0 && iy > 0;"
                    "});"
                    "})()"
                )
            ),
            flush=True,
        )

        q("document.querySelector('[data-expand]').click()")
        time.sleep(0.8)
        print("FULL_H:" + str(q("window.innerHeight")), flush=True)
        print("CARD:" + str(q("!!document.querySelector('[data-complete]')")), flush=True)
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
def test_minimize_collapses_the_window_and_expand_restores_it(tmp_path):
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

    assert _line(result.stdout, "BAR:") == "True", out
    assert _line(result.stdout, "MINI_H:") == "150", out
    # A regression here is invisible if only the window is checked: .bar is
    # `height: 100%` of .card, and without .collapsed pinning .card itself,
    # the bar happily stretches to fill whatever the window gives it.
    assert _line(result.stdout, "BAR_H:") == "86", out
    # The close button must clear all three bar controls' boxes, not just
    # their centres -- see the OVERLAP driver code above.
    assert _line(result.stdout, "OVERLAP:") == "False", out
    assert _line(result.stdout, "FULL_H:") == "684", out
    assert _line(result.stdout, "CARD:") == "True", out
