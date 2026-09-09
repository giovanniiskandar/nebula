"""Collapsing the window to the bar, and restoring it."""

import pytest

from nebula import app as nebula_app
from nebula.tracker import Tracker


class _FakeWindow:
    """Records resizes. The real one is only reachable from a GUI test."""

    def __init__(self) -> None:
        self.sizes: list[tuple[int, int]] = []

    def resize(self, width: int, height: int) -> None:
        self.sizes.append((width, height))


def _api(tmp_path) -> tuple[nebula_app.Api, _FakeWindow]:
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    window = _FakeWindow()
    api.bind(window)
    return api, window


def test_the_bar_is_the_card_height_plus_the_shadow_margin():
    assert nebula_app.MINI_CARD_HEIGHT == 86
    assert (
        nebula_app.WINDOW_MINI_HEIGHT
        == nebula_app.MINI_CARD_HEIGHT + nebula_app.SHADOW_PADDING * 2
    )


def test_set_minimized_collapses_and_restores(tmp_path):
    api, window = _api(tmp_path)

    api.set_minimized(True)
    api.set_minimized(False)

    assert window.sizes == [
        (nebula_app.WINDOW_WIDTH, nebula_app.WINDOW_MINI_HEIGHT),
        (nebula_app.WINDOW_WIDTH, nebula_app.WINDOW_HEIGHT),
    ]


def test_set_minimized_keeps_the_width(tmp_path):
    """Only the height moves: the card's width is the same in both modes."""
    api, window = _api(tmp_path)
    api.set_minimized(True)
    assert window.sizes[0][0] == nebula_app.WINDOW_WIDTH


def test_set_minimized_before_binding_is_an_error(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    with pytest.raises(RuntimeError):
        api.set_minimized(True)
