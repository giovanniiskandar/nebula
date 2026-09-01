"""Window shell for the Nebula widget.

The window is frameless, transparent and always-on-top (PRD §27), so the
rounded card and its shadow are drawn in CSS rather than by the native frame.
"""

import socket
import sys
from pathlib import Path

import webview

# The visible card is the widget size requirement. The window itself is larger:
# `box-shadow` paints outside the card's box, and anything outside the *window*
# is clipped by the OS, so the card needs a transparent margin to cast into.
CARD_WIDTH = 360
CARD_HEIGHT = 560
SHADOW_PADDING = 24  # keep in sync with `body` padding in frontend/src/index.css

WINDOW_WIDTH = CARD_WIDTH + SHADOW_PADDING * 2
WINDOW_HEIGHT = CARD_HEIGHT + SHADOW_PADDING * 2

DEV_SERVER_HOST = "localhost"
DEV_SERVER_PORT = 5173
DEV_SERVER_URL = f"http://{DEV_SERVER_HOST}:{DEV_SERVER_PORT}"

# Repo root when running from a source checkout: src/nebula/app.py -> nebula/
# A frozen .app reads from sys._MEIPASS instead; that belongs to the packaging
# phase and is deliberately not handled here.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_INDEX = PROJECT_ROOT / "dist" / "index.html"


class FrontendNotReady(RuntimeError):
    """The frontend is not available in the mode the app was started in."""


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) == 0


def resolve_url(dev: bool) -> str:
    """Return the URL to load, or explain what the user needs to start first."""
    if dev:
        if not _port_is_open(DEV_SERVER_HOST, DEV_SERVER_PORT):
            raise FrontendNotReady(
                f"Vite dev server not running on {DEV_SERVER_URL} — "
                "start it with 'pnpm dev' in frontend/"
            )
        return DEV_SERVER_URL

    if not DIST_INDEX.exists():
        raise FrontendNotReady("Frontend not built — run 'pnpm build' in frontend/")
    return str(DIST_INDEX)


def _bind_close(window: webview.Window) -> None:
    """Wire the close button, which quits the app (PRD §15).

    This deliberately uses a DOM event handler rather than a `js_api` method.
    A `js_api` call cannot destroy the window: after the handler returns,
    pywebview always evaluates JS in the webview to hand the return value back
    (`webview/util.py`, `js_bridge_call`). By then the webview is gone, so the
    completion handler never fires and the *non-daemon* bridge thread blocks
    forever on a semaphore -- the app beachballs and never exits. DOM event
    handlers return early without that round trip.

    Later this is where the open session gets its `endedAt` before the window
    goes away.
    """
    close_button = window.dom.get_element(".close")
    if close_button is not None:
        close_button.events.click += lambda _event: window.destroy()


def create_window(dev: bool = False) -> webview.Window:
    window = webview.create_window(
        "Nebula",
        url=resolve_url(dev),
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        resizable=False,
        frameless=True,
        transparent=True,
        easy_drag=True,
        on_top=True,
    )
    window.events.loaded += _bind_close
    return window


def run(dev: bool = False) -> None:
    try:
        create_window(dev)
    except FrontendNotReady as error:
        print(f"nebula: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    webview.start()
