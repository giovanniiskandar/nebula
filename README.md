# Nebula

A floating, always-on-top macOS widget for planning and tracking daily time
allocation. See [PRD.md](PRD.md) for the full product spec.

**Status:** Phase 1 — project scaffolding and window shell only. No tracking
logic yet.

## Requirements

- macOS
- [uv](https://docs.astral.sh/uv/) — `brew install uv`

uv fetches its own Python (3.13, pinned in `.python-version`), so the system
Python is left alone.

## Run

```sh
uv run nebula
```

The first run creates `.venv/` and installs dependencies from `uv.lock`. There
is no virtualenv to activate.

## Layout

```
src/nebula/
├── __main__.py   entry point
├── app.py        window shell + JS/Python bridge
└── web/          the UI (plain HTML/CSS/JS)
```

The window is frameless, transparent and always-on-top (PRD §27), so the card's
rounded corners and shadow are drawn in CSS. Because there are no traffic
lights, the UI provides its own close button, which calls Python through
`window.pywebview.api`. Drag the card anywhere to move it.
