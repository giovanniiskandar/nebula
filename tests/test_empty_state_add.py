"""Adding a first allocation from the empty state.

The empty state is the first thing a new user sees, and its Add button was
shipped disabled: the only working route was the gear, which nothing on that
screen points to. The existing GUI test asserted the empty state *rendered*,
which it did, perfectly, while being unusable.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

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

    def q(js):
        return window.evaluate_js(js)

    def set_value(selector, value):
        # React tracks an input's value internally; a direct assignment is
        # not seen.
        q(
            "(function(){var el=document.querySelector('%s');"
            "var proto=Object.getPrototypeOf(el);"
            "var setter=Object.getOwnPropertyDescriptor(proto,'value').set;"
            "setter.call(el,'%s');"
            "el.dispatchEvent(new Event('input',{bubbles:true}));})()"
            % (selector, value)
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

        print("EMPTY:" + str(q("!!document.querySelector('[data-empty]')")), flush=True)
        print("DISABLED:" + str(
            q("document.querySelector('[data-empty-add]') === null"
              " || document.querySelector('[data-empty-add]').disabled")
        ), flush=True)

        if not q("!!document.querySelector('[data-empty-add]')"):
            # Report rather than throw: an exception here kills this thread and
            # the window never closes, turning a clear failure into a timeout.
            print("FORM:False", flush=True)
            print('NAMES:[]', flush=True)
            window.destroy()
            return

        q("document.querySelector('[data-empty-add]').click()")
        time.sleep(0.4)
        print("FORM:" + str(q("!!document.querySelector('[data-form]')")), flush=True)

        set_value("[data-form-name]", "Work")
        q("document.querySelectorAll('[data-preset]')[3].click()")   # 3h
        time.sleep(0.3)
        q("document.querySelector('[data-form-save]').click()")
        time.sleep(0.6)

        print("NAMES:" + q(
            "JSON.stringify(Array.from("
            "document.querySelectorAll('[data-allocation-name]'))"
            ".map(function (n) { return n.textContent; }))"
        ), flush=True)
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
def test_a_first_allocation_can_be_added_from_the_empty_state(tmp_path):
    assert (PROJECT_ROOT / "dist" / "index.html").exists(), (
        "run 'pnpm build' in frontend/ before this test"
    )

    result = subprocess.run(
        [sys.executable, "-c", DRIVER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "NEBULA_DATA": str(tmp_path / "data.json"),
        },
    )

    assert _line(result.stdout, "EMPTY:") == "True", result.stdout + result.stderr
    # The button must exist and be usable -- this is the bug.
    assert _line(result.stdout, "DISABLED:") == "False", result.stdout + result.stderr
    assert _line(result.stdout, "FORM:") == "True", result.stdout + result.stderr

    names = _line(result.stdout, "NAMES:")
    assert names is not None, result.stdout + result.stderr
    assert json.loads(names) == ["Work"]
