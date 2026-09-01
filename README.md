# Nebula

A floating, always-on-top macOS widget for planning and tracking daily time
allocation. See [PRD.md](PRD.md) for the full product spec.

**Status:** Phase 1 — project scaffolding and window shell only. No tracking
logic yet.

## Requirements

- macOS
- [uv](https://docs.astral.sh/uv/) — `brew install uv`
- Node 24 LTS (pinned in `.nvmrc`) and pnpm

uv fetches its own Python (3.13, pinned in `.python-version`), so the system
Python is left alone. Node is not managed for you: run `nvm use` before any
`pnpm` command, since a shell that has not done so may resolve to a different
Node version.

## Run

Build the frontend once, then start the app:

```sh
cd frontend && pnpm install && pnpm build && cd ..
uv run nebula
```

The first run creates `.venv/` and installs dependencies from `uv.lock`. There
is no virtualenv to activate.

A fresh clone must run `pnpm build` before `uv run nebula` works — `dist/` is
generated, not committed.

## Develop

Two terminals:

```sh
# terminal 1
cd frontend && pnpm dev

# terminal 2
uv run nebula --dev
```

The window loads the Vite dev server, so edits to `frontend/src/` hot-reload
inside the native window. Node 24 is required (`nvm use` reads `.nvmrc`).

## Tests and linting

```sh
uv run pytest                 # everything, including the GUI close-button test
uv run pytest -m "not gui"    # fast; skips the test that opens a window
cd frontend && pnpm lint      # oxlint
```

A pre-commit hook runs oxlint (when `frontend/` is touched) and the non-GUI
tests. Hooks are not cloned, so enable it once per checkout:

```sh
git config core.hooksPath .githooks
```

It skips the GUI test deliberately: that test opens a real always-on-top
window, which would steal focus on every commit. Run the full suite before
merging.

## Layout

```
frontend/         React + TypeScript UI, built by Vite
└── src/
dist/             build output (generated, gitignored)
src/nebula/
├── __main__.py   entry point
└── app.py        window shell + JS/Python bridge
```

The window is frameless, transparent and always-on-top (PRD §27), so the card's
rounded corners and shadow are drawn in CSS. Because there are no traffic
lights, the UI provides its own close button, which calls Python through
`window.pywebview.api`. Drag the card anywhere to move it.
