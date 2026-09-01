"""Window shell for the Nebula widget.

The window is frameless, transparent and always-on-top (PRD §27), so the
rounded card and its shadow are drawn in CSS rather than by the native frame.
"""

from pathlib import Path

import webview

# The visible card is the widget size requirement. The window itself is larger:
# `box-shadow` paints outside the card's box, and anything outside the *window*
# is clipped by the OS, so the card needs a transparent margin to cast into.
CARD_WIDTH = 360
CARD_HEIGHT = 560
SHADOW_PADDING = 24  # keep in sync with `body` padding in style.css

WINDOW_WIDTH = CARD_WIDTH + SHADOW_PADDING * 2
WINDOW_HEIGHT = CARD_HEIGHT + SHADOW_PADDING * 2

UI_ROOT = Path(__file__).parent / "web"


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


def create_window() -> webview.Window:
    window = webview.create_window(
        "Nebula",
        url=str(UI_ROOT / "index.html"),
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


def run() -> None:
    create_window()
    webview.start()
