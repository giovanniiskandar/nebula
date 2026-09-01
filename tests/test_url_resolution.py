"""Dev and production URL resolution, and the failure messages for each."""

import pytest

from nebula import app


def test_dev_returns_dev_server_url_when_port_is_open(monkeypatch):
    monkeypatch.setattr(app, "_port_is_open", lambda host, port: True)
    assert app.resolve_url(dev=True) == "http://localhost:5173"


def test_dev_raises_when_dev_server_is_not_running(monkeypatch):
    monkeypatch.setattr(app, "_port_is_open", lambda host, port: False)
    with pytest.raises(app.FrontendNotReady) as excinfo:
        app.resolve_url(dev=True)
    assert "pnpm dev" in str(excinfo.value)


def test_production_returns_dist_index_when_it_exists(monkeypatch, tmp_path):
    index = tmp_path / "index.html"
    index.write_text("<html></html>")
    monkeypatch.setattr(app, "DIST_INDEX", index)
    assert app.resolve_url(dev=False) == str(index)


def test_production_raises_when_build_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DIST_INDEX", tmp_path / "index.html")
    with pytest.raises(app.FrontendNotReady) as excinfo:
        app.resolve_url(dev=False)
    assert "pnpm build" in str(excinfo.value)
