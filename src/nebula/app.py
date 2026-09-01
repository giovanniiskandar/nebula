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
ICON_PATH = PROJECT_ROOT / "assets" / "Nebula.icns"


class FrontendNotReady(RuntimeError):
    """The frontend is not available in the mode the app was started in."""


def _port_is_open(host: str, port: int) -> bool:
    """Whether anything is listening, on either address family.

    `create_connection` walks every address `getaddrinfo` returns rather than
    committing to one family. That matters: Vite binds to `[::1]` only, so an
    AF_INET probe of `localhost` hits 127.0.0.1 and reports a running dev
    server as down.
    """
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _set_dock_icon() -> bool:
    """Give the Dock entry the app's icon.

    An unbundled Python process shows a generic document icon labelled
    "python3.13". The icon is settable at runtime; the *name* is not -- that
    comes from the .app bundle's Info.plist, so it stays "python3.13" until
    the app is bundled (PRD §26).

    Returns whether it was applied. A missing or unreadable icon degrades to
    the default rather than stopping the app from starting.
    """
    if not ICON_PATH.exists():
        return False

    from AppKit import NSApplication, NSImage

    image = NSImage.alloc().initByReferencingFile_(str(ICON_PATH))
    if image is None or not image.isValid():
        return False

    NSApplication.sharedApplication().setApplicationIconImage_(image)
    return True


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

    This uses a DOM event handler rather than a `js_api` method. A `js_api`
    call cannot destroy the window: after the handler returns, pywebview
    evaluates JS in the webview to hand the return value back
    (`webview/util.py`, `js_bridge_call`). By then the webview is gone, the
    completion handler never fires, and the *non-daemon* bridge thread blocks
    forever on a semaphore -- the app beachballs and never exits.

    Selects on `data-close` rather than a class name because CSS Modules
    rewrites class names into hashes that cannot be predicted from here.

    Later this is where the open session gets its `endedAt` before the window
    goes away.
    """
    close_button = window.dom.get_element("[data-close]")
    if close_button is None:
        raise RuntimeError(
            "Close button [data-close] not found. The window is frameless, so "
            "it cannot be closed without it."
        )
    close_button.events.click += lambda _event: window.destroy()


class Api:
    """Methods exposed to the page as `window.pywebview.api.*`.

    No method here may destroy the window; see `_bind_close` for why.
    """

    def __init__(self) -> None:
        self._window: webview.Window | None = None

    def bind(self, window: webview.Window) -> None:
        self._window = window

    def ui_ready(self) -> bool:
        """Called by the frontend once React has mounted.

        `window.events.loaded` is too early: the DOM is only `<div id="root">`
        at that point, so the close button does not exist yet.
        """
        if self._window is None:
            raise RuntimeError("ui_ready called before the window was bound")
        _bind_close(self._window)
        return True


def create_window(dev: bool = False) -> webview.Window:
    api = Api()
    window = webview.create_window(
        "Nebula",
        url=resolve_url(dev),
        js_api=api,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        resizable=False,
        frameless=True,
        transparent=True,
        easy_drag=True,
        on_top=True,
    )
    api.bind(window)
    return window


def run(dev: bool = False) -> None:
    try:
        create_window(dev)
    except FrontendNotReady as error:
        print(f"nebula: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    _set_dock_icon()
    webview.start()
