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


SHIFT_DRIVER = textwrap.dedent(
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

    TITLE = (
        "document.querySelector('[data-minimized] > div > div > span')"
        ".getBoundingClientRect().y"
    )

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
        print("IDLE_TITLE_Y:" + str(q(TITLE)), flush=True)

        # The controls share a grid column with the day's figures. When those
        # figures are the wider of the two -- which needs a day long enough to
        # print, hence this fixture's 12h 45m -- a left-aligned row trails a
        # gap against the card's edge. Both share the column, so both must
        # end on the same pixel -- which sidesteps the bar's own border.
        print(
            "FLUSH:"
            + str(
                q(
                    "(() => {"
                    "const bar = document.querySelector('[data-minimized]');"
                    "const expand = bar.querySelector('[data-expand]')"
                    ".getBoundingClientRect();"
                    "const spans = bar.querySelectorAll('span');"
                    "const day = spans[spans.length - 1].getBoundingClientRect();"
                    "return Math.round(day.right - expand.right);"
                    "})()"
                )
            ),
            flush=True,
        )

        q("document.querySelector('[data-mini-break]').click()")
        time.sleep(0.8)
        print("BREAK_TITLE_Y:" + str(q(TITLE)), flush=True)
        print("BREAK_SUBTITLE:" + str(q(
            "document.querySelectorAll("
            "'[data-minimized] > div > div > span')[1].textContent"
        )), flush=True)
        window.destroy()

    threading.Thread(target=check, daemon=True).start()
    webview.start()
    """
)


@pytest.mark.gui
def test_the_bar_does_not_shift_when_a_break_starts(tmp_path):
    """Idle has no subtitle; break has one.

    The row is centred, so an empty subtitle that draws no line collapsed the
    text block and shoved the title 5.5px up the moment a break began. The
    line is reserved now, and only geometry can prove it -- both states render
    the same element with different text.
    """
    assert (PROJECT_ROOT / "dist" / "index.html").exists(), (
        "run 'pnpm build' in frontend/ before this test"
    )

    data = tmp_path / "data.json"
    tracker = Tracker(data)
    tracker.open(NOW)
    # Deliberately not activated: an allocation exists, nothing is tracking.
    # The target is large so the day's figures print wide enough to be the
    # widest thing in their grid column -- a short day hides the gap the
    # FLUSH assertion looks for.
    tracker.add_allocation("Work", 12 * 3600 + 45 * 60, NOW)

    result = subprocess.run(
        [sys.executable, "-c", SHIFT_DRIVER],
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

    assert _line(result.stdout, "FLUSH:") == "0", out

    idle = _line(result.stdout, "IDLE_TITLE_Y:")
    broke = _line(result.stdout, "BREAK_TITLE_Y:")
    assert idle is not None and broke is not None, out
    assert idle == broke, f"title moved {idle} -> {broke} entering break\n{out}"
    # Guards the guard: if the break state stopped rendering a subtitle, the
    # heights would match for the wrong reason.
    assert _line(result.stdout, "BREAK_SUBTITLE:") == "nothing accumulating", out
