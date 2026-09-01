"""The close button must close the window AND let the process exit.

Asserting on process exit is the point. In the phase 1 deadlock the window
closed correctly but a non-daemon pywebview bridge thread blocked forever on a
semaphore, so the process never exited. A test that only checked the window
would have passed while the app beachballed.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DRIVER = textwrap.dedent(
    """
    import threading
    import time

    import webview

    from nebula.app import create_window

    window = create_window(dev=False)


    def click_close():
        # Wait for the handshake to COMPLETE, not for the button to exist.
        # React renders the button a full round trip before Python binds the
        # click handler, so clicking on element-existence alone is a race that
        # hangs whenever the click lands first.
        for _ in range(100):
            ready = window.evaluate_js(
                "document.documentElement.dataset.nebulaReady === 'true'"
            )
            if ready:
                break
            time.sleep(0.1)
        else:
            raise SystemExit("ui_ready handshake never completed")
        window.evaluate_js("document.querySelector('[data-close]').click()")


    threading.Thread(target=click_close, daemon=True).start()
    webview.start()
    print("CLEAN_EXIT")
    """
)


def test_close_button_exits_the_process():
    build = PROJECT_ROOT / "dist" / "index.html"
    assert build.exists(), "run 'pnpm build' in frontend/ before this test"

    result = subprocess.run(
        [sys.executable, "-c", DRIVER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        # pytest's `pythonpath` setting is not inherited by a subprocess, and
        # this must not depend on the project happening to be installed
        # editable into the venv.
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )

    assert "CLEAN_EXIT" in result.stdout, result.stderr
    assert result.returncode == 0, result.stderr
