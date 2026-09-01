"""Dev and production URL resolution, and the failure messages for each."""

import socket

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


def _listen(family, address):
    server = socket.socket(family, socket.SOCK_STREAM)
    server.bind(address)
    server.listen(1)
    return server, server.getsockname()[1]


def test_port_probe_detects_an_ipv6_only_listener():
    """Vite binds to [::1] only, so an IPv4-only probe reports it as down."""
    server, port = _listen(socket.AF_INET6, ("::1", 0))
    try:
        assert app._port_is_open("localhost", port) is True
    finally:
        server.close()


def test_port_probe_detects_an_ipv4_only_listener():
    server, port = _listen(socket.AF_INET, ("127.0.0.1", 0))
    try:
        assert app._port_is_open("localhost", port) is True
    finally:
        server.close()


def test_port_probe_reports_a_closed_port():
    server, port = _listen(socket.AF_INET, ("127.0.0.1", 0))
    server.close()
    assert app._port_is_open("localhost", port) is False
