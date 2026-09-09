"""Window shell for the Nebula widget.

The window is frameless, transparent and always-on-top (PRD §27), so the
rounded card and its shadow are drawn in CSS rather than by the native frame.
"""

import socket
import sys
from datetime import datetime
from pathlib import Path

import webview

from nebula import model, store
from nebula.tracker import Tracker

# The visible card is the widget size requirement. The window itself is larger:
# `box-shadow` paints outside the card's box, and anything outside the *window*
# is clipped by the OS, so the card needs a transparent margin to cast into.
CARD_WIDTH = 320
CARD_HEIGHT = 620
SHADOW_PADDING = 32  # keep in sync with `body` padding in frontend/src/index.css

WINDOW_WIDTH = CARD_WIDTH + SHADOW_PADDING * 2
WINDOW_HEIGHT = CARD_HEIGHT + SHADOW_PADDING * 2

# The minimized bar. Only the height changes: the card keeps its width in both
# modes, so nothing reflows across the collapse.
MINI_CARD_HEIGHT = 86
WINDOW_MINI_HEIGHT = MINI_CARD_HEIGHT + SHADOW_PADDING * 2

DEV_SERVER_HOST = "localhost"
DEV_SERVER_PORT = 5173
DEV_SERVER_URL = f"http://{DEV_SERVER_HOST}:{DEV_SERVER_PORT}"

def resolve_project_root() -> Path:
    """Where `dist/` and `assets/` live.

    PyInstaller unpacks bundled data into a temporary directory and points
    `sys._MEIPASS` at it, so the frozen app must look there rather than beside
    its own source. From a source checkout the answer is the repo root:
    src/nebula/app.py -> nebula/.
    """
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled is not None:
        return Path(bundled)
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = resolve_project_root()
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

    No method here may destroy the window; see `_bind_close` for why. That is
    also what makes raising safe: pywebview catches an exception from a
    `js_api` method and rejects the JavaScript promise with its message, so a
    corrupt data file reaches the UI as an error state rather than a blank card.

    This is where real time enters the program. The data layer takes `now` as
    an argument so its rules can be tested against real timestamps; `Api` is
    the only place that reads a clock.
    """

    def __init__(self, tracker: Tracker) -> None:
        self.tracker = tracker
        self._window: webview.Window | None = None

    def bind(self, window: webview.Window) -> None:
        self._window = window

    @staticmethod
    def _now() -> datetime:
        return datetime.now().astimezone()

    def ui_ready(self) -> dict:
        """Called by the frontend once React has mounted.

        `window.events.loaded` is too early: the DOM is only `<div id="root">`
        at that point, so the close button does not exist yet.

        Opening the app is a resume point (PRD §17), so this performs the date
        check and recovers a session left open by a crash, then hands back the
        first view — one call rather than two.
        """
        if self._window is None:
            raise RuntimeError("ui_ready called before the window was bound")
        _bind_close(self._window)
        return model.view_to_dict(self.tracker.open(self._now()))

    def resume(self) -> dict:
        """The Start control after a completed day (PRD §18.3)."""
        return model.view_to_dict(self.tracker.open(self._now()))

    def activate(self, allocation_id: str) -> dict:
        """PRD §10.3, §10.4 — no confirmation, exits Break."""
        return model.view_to_dict(self.tracker.activate(allocation_id, self._now()))

    def toggle_break(self) -> dict:
        """PRD §6.4 — a pause/resume toggle, not a deselect."""
        return model.view_to_dict(self.tracker.toggle_break(self._now()))

    def complete_day(self) -> dict:
        """PRD §10.6 — the only way a day ends."""
        return model.view_to_dict(self.tracker.complete_day(self._now()))

    def set_minimized(self, minimized: bool) -> None:
        """Collapse the window to the bar, or restore it.

        Resizing from a js_api method is safe; destroying is not (see
        `_bind_close`). pywebview returns a value by evaluating JS in the
        webview, so a method that tears the webview down hangs the bridge
        thread forever -- a resize leaves it alive to answer.

        `resize()` defaults to `FixPoint.NORTH | FixPoint.WEST`, so the card's
        top-left stays put and the window collapses upward from the bottom.
        """
        if self._window is None:
            raise RuntimeError("set_minimized called before the window was bound")
        height = WINDOW_MINI_HEIGHT if minimized else WINDOW_HEIGHT
        self._window.resize(WINDOW_WIDTH, height)

    def add_allocation(self, name: str, target_seconds: int) -> dict:
        """PRD §10.2."""
        return model.view_to_dict(
            self.tracker.add_allocation(name, target_seconds, self._now())
        )

    def edit_allocation(
        self, allocation_id: str, name: str, target_seconds: int
    ) -> dict:
        """A target change applies to today immediately (PRD §12, §19)."""
        return model.view_to_dict(
            self.tracker.edit_allocation(
                allocation_id, name, target_seconds, self._now()
            )
        )

    def delete_allocation(self, allocation_id: str) -> dict:
        """No confirmation step, and sessions stay in the file (PRD §12)."""
        return model.view_to_dict(
            self.tracker.delete_allocation(allocation_id, self._now())
        )

    def set_name(self, name: str) -> dict:
        """The *user's* name, for the recap (PRD §12, §18.2)."""
        return model.view_to_dict(self.tracker.set_name(name, self._now()))

    def check_milestones(self, allocation_id: str) -> dict:
        """Announce any milestone this allocation has reached (PRD §13).

        Called by the frontend when its tick shows a threshold crossed. React
        is the trigger; the decision is made here from timestamps, so an early
        ask fires nothing.
        """
        return model.view_to_dict(
            self.tracker.check_milestones(allocation_id, self._now())
        )


def create_window(dev: bool = False) -> webview.Window:
    api = Api(Tracker(store.data_path(dev)))
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

    # pywebview applies the icon during window initialisation, once the app has
    # finished launching (`platforms/cocoa.py`). Calling
    # setApplicationIconImage_ ourselves before webview.start() is too early --
    # the Dock tile does not pick it up. Its docstring claims GTK/Qt only, but
    # the cocoa backend implements it, the same docstring error as `on_top`.
    webview.start(icon=str(ICON_PATH) if ICON_PATH.exists() else None)
