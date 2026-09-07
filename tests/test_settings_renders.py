"""Adding an allocation through the real form."""

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
        # React tracks an input's value internally; assigning .value directly
        # is not seen. Use the native setter, then dispatch an input event.
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

        q("document.querySelector('[data-gear]').click()")
        time.sleep(0.4)
        q("document.querySelector('[data-add]').click()")
        time.sleep(0.4)

        print("SAVE_BLANK:" + str(
            q("document.querySelector('[data-form-save]').disabled")
        ), flush=True)

        set_value("[data-form-name]", "Reading")
        # Index rather than an attribute-value selector: the quotes would have
        # to survive a heredoc, a Python string and a JS string. PRESETS order
        # is 30m, 1h, 2h, 3h, 4h, so index 1 is 1h.
        q("document.querySelectorAll('[data-preset]')[1].click()")
        time.sleep(0.3)
        print("PLANNED:" + q(
            "document.querySelector('[data-form]')"
            ".querySelectorAll('span')[document.querySelector('[data-form]')"
            ".querySelectorAll('span').length - 1].textContent"
        ), flush=True)
        print("SAVE_ENABLED:" + str(
            not q("document.querySelector('[data-form-save]').disabled")
        ), flush=True)
        q("document.querySelector('[data-form-save]').click()")
        time.sleep(0.6)
        q("document.querySelector('[data-settings-close]').click()")
        time.sleep(0.4)

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
def test_adding_an_allocation_through_the_form(tmp_path):
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

    # SAVE must be unavailable before anything is typed.
    assert _line(result.stdout, "SAVE_BLANK:") == "True", result.stdout + result.stderr
    assert _line(result.stdout, "SAVE_ENABLED:") == "True", result.stdout + result.stderr

    names = _line(result.stdout, "NAMES:")
    assert names is not None, result.stdout + result.stderr
    assert json.loads(names) == ["Reading"]
