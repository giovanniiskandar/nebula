# React + Vite Frontend Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-written HTML/CSS in `src/nebula/web/` with a React + TypeScript frontend built by Vite, with no visible change to the running app.

**Architecture:** Vite builds `frontend/` to a root `dist/`. `app.py` loads the Vite dev server with `--dev` and the built `dist/index.html` otherwise, failing loudly in both modes. Because React mounts after pywebview's `loaded` event, the close button is bound through a `ui_ready` handshake the frontend initiates.

**Tech Stack:** React 19 + TypeScript, Vite, CSS Modules, pnpm, pywebview 6.2.1, Python 3.13, pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-react-vite-scaffold-design.md`

## Global Constraints

- Node `>=24 <25` (LTS Krypton). The system Node on this machine is v26.8.1 and a non-interactive shell resolves to it, so **every** frontend command must be preceded by `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use`.
- pnpm `11.17.0`, pinned via `packageManager`.
- Python `>=3.13`.
- Visible card is exactly **360 × 560**; window is **408 × 608**.
- `SHADOW_PADDING = 24` in `app.py` must equal the `body` padding in CSS.
- `base: './'` in `vite.config.ts`. Without it, production loads blank over `file://`.
- `#root` must be transparent, or the frameless window renders as an opaque rectangle.
- Vite dev server on port **5173** with `strictPort: true`, so it fails rather than silently moving to 5174 where Python is not looking.
- No product behavior from the PRD. This phase ends with a hello-world card rendered by React.

---

## File Structure

| File | Responsibility |
|---|---|
| `.nvmrc` | Pins Node 24 for the repo |
| `frontend/package.json` | Deps, scripts, Node/pnpm pinning |
| `frontend/.npmrc` | `engine-strict=true`, so a wrong Node fails instead of warning |
| `frontend/vite.config.ts` | `base`, `outDir`, dev server port |
| `frontend/index.html` | Vite entry template, holds `#root` |
| `frontend/src/main.tsx` | React root |
| `frontend/src/App.tsx` | The card; initiates the `ui_ready` handshake |
| `frontend/src/App.module.css` | Card, title, subtitle, close button |
| `frontend/src/index.css` | Global reset, transparency, `body` padding |
| `src/nebula/app.py` | Window shell, URL resolution, close binding |
| `src/nebula/__main__.py` | `--dev` argument parsing |
| `tests/test_url_resolution.py` | Dev/prod URL and failure messages |
| `tests/test_close_button.py` | Close-button regression test |

---

### Task 1: React frontend renders the card and builds to `dist/`

**Files:**
- Create: `.nvmrc`, `frontend/` (scaffolded), `frontend/.npmrc`, `frontend/vite.config.ts`, `frontend/src/App.tsx`, `frontend/src/App.module.css`, `frontend/src/index.css`, `frontend/src/main.tsx`, `frontend/index.html`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `dist/index.html` plus `dist/assets/*` at the repo root, with **relative** asset paths. The card markup exposes a `data-close` attribute on the close button, which Task 3 selects on.

- [x] **Step 1: Pin Node and confirm the right runtime is active**

```bash
cd /Users/macbook/Documents/Projects/nebula
echo "24" > .nvmrc
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
node --version
```

Expected: `v24.x.x`. If it prints `v26.x.x`, stop — the rest of this task will install against the wrong runtime.

- [x] **Step 2: Scaffold the Vite project**

```bash
cd /Users/macbook/Documents/Projects/nebula
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm create vite frontend --template react-ts
```

Use the official scaffolder rather than hand-writing `package.json` so React, Vite, and TypeScript versions are current rather than guessed.

- [x] **Step 3: Pin the toolchain in `frontend/package.json`**

Add these three keys alongside the generated ones (keep the generated `dependencies`, `devDependencies`, and `scripts` exactly as they are):

```json
{
  "packageManager": "pnpm@11.17.0",
  "engines": {
    "node": ">=24 <25"
  },
  "private": true
}
```

- [x] **Step 4: Make a wrong Node version fail rather than warn**

Create `frontend/.npmrc`:

```
engine-strict=true
```

- [x] **Step 5: Install dependencies**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm install
```

Expected: completes without an `Unsupported engine` error.

- [x] **Step 6: Configure Vite**

Replace `frontend/vite.config.ts` entirely:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Production loads over file://, where Vite's default absolute /assets/...
  // paths resolve against the filesystem root and the window renders blank.
  base: './',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    // Fail instead of hopping to 5174, which app.py would not be watching.
    strictPort: true,
  },
})
```

- [x] **Step 7: Write the global stylesheet**

Replace `frontend/src/index.css` entirely. CSS Modules scope every class, so the reset and the transparency rules must live in a plain stylesheet:

```css
/* The native window is frameless and transparent, so the card is the only
   thing the user sees -- its rounded corners and drop shadow stand in for the
   native window frame. */

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body,
#root {
  height: 100%;
  background: transparent;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui,
    sans-serif;
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
  overflow: hidden;
  /* The window is larger than the card by SHADOW_PADDING on every side (see
     app.py) -- this padding is the transparent margin the shadow casts into. */
  padding: 24px;
}
```

`#root` is listed alongside `html, body` deliberately: it is a React-only element, and if it keeps a default background the transparent window becomes an opaque rectangle.

- [x] **Step 8: Write the card stylesheet**

Replace `frontend/src/App.module.css` entirely (the scaffolder generates `App.css`; delete that file):

```css
.card {
  position: relative;
  display: flex;
  height: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 18px;
  background: #16161a;
  box-shadow: 0 12px 40px rgb(0 0 0 / 45%), inset 0 0 0 1px rgb(255 255 255 / 8%);
  color: #f4f4f5;
}

.title {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.sub {
  font-size: 12px;
  color: #8a8a94;
}

.close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgb(255 255 255 / 8%);
  color: #8a8a94;
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
}

.close:hover {
  background: rgb(255 255 255 / 16%);
  color: #f4f4f5;
}
```

- [x] **Step 9: Write the card component**

Replace `frontend/src/App.tsx` entirely. The `data-close` attribute is the binding hook for Task 3 — **not** the `className`, because CSS Modules rewrites `close` into a hashed name like `_close_1a2b3_4` that Python cannot predict:

```tsx
import styles from './App.module.css'

export default function App() {
  return (
    <main className={styles.card}>
      <button
        className={styles.close}
        type="button"
        aria-label="Close"
        data-close
      >
        &times;
      </button>
      <h1 className={styles.title}>Hello world</h1>
      <p className={styles.sub}>Nebula &middot; 360 &times; 560</p>
    </main>
  )
}
```

- [x] **Step 10: Simplify the React root**

Replace `frontend/src/main.tsx` entirely:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [x] **Step 11: Set the page title**

In `frontend/index.html`, change the `<title>` to `Nebula`. Leave the rest of the generated file as-is.

- [x] **Step 12: Build and verify the output**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm build
ls ../dist
grep -o 'src="[^"]*"' ../dist/index.html
```

Expected: `ls` shows `index.html` and `assets/`. The `grep` prints a path beginning `./assets/` — **not** `/assets/`. A leading slash means `base: './'` did not take effect and production will render blank.

- [x] **Step 13: Ignore build and dependency output**

`.gitignore` already contains `dist/`, added in phase 1 for Python build artifacts; it now also covers Vite's output. Replace the file entirely so there is no duplicated entry. Note the comment sits on its own line: git only honours `#` at the start of a line, so a trailing comment would become part of the pattern and silently fail to ignore anything:

```
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
build/

# Frontend
node_modules/
# Vite build output; also covers Python build artifacts
dist/
*.tsbuildinfo

# Nebula local data (PRD §20)
data.json

# macOS
.DS_Store
```

- [x] **Step 14: Commit**

```bash
cd /Users/macbook/Documents/Projects/nebula
git add -A
git commit -m "Add React + Vite frontend rendering the card

Scaffolds frontend/ with React 19 and TypeScript, building to a root
dist/. The card markup and styling are ported from the hand-written
web/ files unchanged.

base: './' is required because production loads over file://, where
Vite's default absolute asset paths resolve against the filesystem
root and the window renders blank. #root is made transparent
alongside html and body, since it is a React-only element that would
otherwise turn the frameless window into an opaque rectangle.

The close button carries a data-close attribute rather than relying on
its class name, because CSS Modules rewrites class names into hashes
that the Python side cannot predict."
```

---

### Task 2: `app.py` loads dev or production, failing loudly

**Files:**
- Modify: `src/nebula/app.py`, `src/nebula/__main__.py`, `pyproject.toml`, `README.md`
- Delete: `src/nebula/web/index.html`, `src/nebula/web/style.css`
- Test: `tests/test_url_resolution.py`

**Interfaces:**
- Consumes: `dist/index.html` from Task 1.
- Produces: `resolve_url(dev: bool) -> str`, raising `FrontendNotReady` (a `RuntimeError` subclass); `create_window(dev: bool = False) -> webview.Window`; `run(dev: bool = False) -> None`. Task 3 calls `create_window` and adds `js_api`.

- [x] **Step 1: Add pytest as a dev dependency**

Append to `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Then sync:

```bash
cd /Users/macbook/Documents/Projects/nebula
uv sync
```

- [x] **Step 2: Write the failing tests**

Create `tests/test_url_resolution.py`:

```python
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
```

- [x] **Step 3: Run the tests to verify they fail**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_url_resolution.py -v
```

Expected: FAIL — `AttributeError: module 'nebula.app' has no attribute '_port_is_open'`.

- [x] **Step 4: Implement URL resolution**

In `src/nebula/app.py`, replace the imports and the `UI_ROOT` constant:

```python
import socket
import sys
from pathlib import Path

import webview

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
```

- [x] **Step 5: Run the tests to verify they pass**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_url_resolution.py -v
```

Expected: 4 passed.

- [x] **Step 6: Wire the mode through the window and entry point**

In `src/nebula/app.py`, change `create_window` and `run`:

```python
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
```

Replace `src/nebula/__main__.py` entirely:

```python
"""Entry point: `uv run nebula` or `python -m nebula`."""

import argparse

from nebula.app import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="nebula")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="load the Vite dev server instead of the built frontend",
    )
    args = parser.parse_args()
    run(dev=args.dev)


if __name__ == "__main__":
    main()
```

- [x] **Step 7: Delete the superseded hand-written frontend**

```bash
cd /Users/macbook/Documents/Projects/nebula
git rm -r src/nebula/web
```

- [x] **Step 8: Verify both failure messages by hand**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run nebula --dev; echo "exit=$?"
```

Expected (with no Vite running): `nebula: Vite dev server not running on http://localhost:5173 — start it with 'pnpm dev' in frontend/` and `exit=1`.

```bash
mv dist /tmp/nebula-dist-backup && uv run nebula; echo "exit=$?"; mv /tmp/nebula-dist-backup dist
```

Expected: `nebula: Frontend not built — run 'pnpm build' in frontend/` and `exit=1`.

- [x] **Step 9: Verify production mode renders**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run nebula
```

Expected: the same card as phase 1 — dark rounded card, drop shadow, no native frame. The `×` button will **not** work yet; Task 3 fixes that. Close the window with `pkill -f "nebula/.venv/bin"`.

- [x] **Step 10: Document the workflow in `README.md`**

Replace the `## Run` section with:

```markdown
## Run

Build the frontend once, then start the app:

```sh
cd frontend && pnpm install && pnpm build && cd ..
uv run nebula
```

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
```

- [x] **Step 11: Commit**

```bash
cd /Users/macbook/Documents/Projects/nebula
git add -A
git commit -m "Load the Vite frontend in dev or production mode

uv run nebula loads the built dist/index.html; --dev loads the Vite
dev server on port 5173. Both modes fail with an actionable message
rather than opening a blank window, which is the cost of the
two-terminal workflow being paid down.

Deletes the hand-written src/nebula/web/ files, now superseded by the
React frontend."
```

---

### Task 3: `ui_ready` handshake binds the close button

**Files:**
- Modify: `src/nebula/app.py`, `frontend/src/App.tsx`
- Test: `tests/test_close_button.py`

**Interfaces:**
- Consumes: `create_window(dev)` from Task 2; the `data-close` attribute from Task 1.
- Produces: `Api.ui_ready() -> bool` exposed to the frontend as `window.pywebview.api.ui_ready()`.

- [x] **Step 1: Write the failing regression test**

Create `tests/test_close_button.py`:

```python
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
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_close_button.py -v
```

Expected: FAIL by timeout — React mounts after `loaded`, so `_bind_close` finds nothing, the click does nothing, and `subprocess.run` raises `TimeoutExpired` after 30s.

- [x] **Step 3: Replace the silent close binding with a loud one**

In `src/nebula/app.py`, replace `_bind_close` entirely:

```python
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
```

- [x] **Step 4: Add the `ui_ready` handshake on the Python side**

In `src/nebula/app.py`, add above `create_window`:

```python
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
```

Then change `create_window` to pass and bind the API, and drop the `loaded` hook:

```python
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
```

- [x] **Step 5: Call the handshake from React**

Replace `frontend/src/App.tsx` entirely:

```tsx
import { useEffect } from 'react'
import styles from './App.module.css'

declare global {
  interface Window {
    // Both levels are optional: pywebview creates `window.pywebview` as soon
    // as its own api.js runs, but attaches the api methods later.
    pywebview?: {
      api?: {
        ui_ready?: () => Promise<boolean>
      }
    }
  }
}

export default function App() {
  useEffect(() => {
    // pywebview injects window.pywebview asynchronously and fires
    // `pywebviewready` when it lands. React may mount either side of that,
    // so handle both orders.
    const notify = () => {
      // The flag is set only once Python has returned, meaning the close
      // handler is actually bound. The element existing is not the same
      // thing: React renders it a round trip before the binding lands.
      void window.pywebview?.api?.ui_ready?.().then(() => {
        document.documentElement.dataset.nebulaReady = 'true'
      })
    }

    // Test for the method, not for `window.pywebview`. The object exists long
    // before its methods do, so checking the container fires too early and
    // throws a TypeError -- which React treats as a render failure and
    // responds to by unmounting the entire tree.
    if (window.pywebview?.api?.ui_ready) {
      notify()
      return
    }

    window.addEventListener('pywebviewready', notify, { once: true })
    return () => window.removeEventListener('pywebviewready', notify)
  }, [])

  return (
    <main className={styles.card}>
      <button
        className={styles.close}
        type="button"
        aria-label="Close"
        data-close
      >
        &times;
      </button>
      <h1 className={styles.title}>Hello world</h1>
      <p className={styles.sub}>Nebula &middot; 360 &times; 560</p>
    </main>
  )
}
```

- [x] **Step 6: Rebuild the frontend**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm build
```

- [x] **Step 7: Run the test to verify it passes**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_close_button.py -v
```

Expected: 1 passed, in roughly 3-6 seconds.

- [x] **Step 8: Run the whole suite**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest -v
```

Expected: 5 passed.

- [x] **Step 9: Verify by hand in both modes**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run nebula
```

Click `×`. Expected: the window closes and the process exits. Confirm with `pgrep -f "nebula/.venv/bin"` printing nothing.

Then, in two terminals:

```bash
# terminal 1
cd frontend && pnpm dev

# terminal 2
uv run nebula --dev
```

Edit the `<h1>` text in `frontend/src/App.tsx`. Expected: the native window hot-reloads. Click `×`. Expected: it closes.

- [x] **Step 10: Commit**

```bash
cd /Users/macbook/Documents/Projects/nebula
git add -A
git commit -m "Bind the close button through a ui_ready handshake

React mounts after pywebview's loaded event, so the previous DOM
lookup found nothing and the existing None guard swallowed it --
a dead close button on a frameless window, with no error anywhere.

The frontend now calls ui_ready() once mounted, and Python binds the
handler then. ui_ready is a normal js_api method: it returns a value
and never destroys the window, so it does not hit the bridge deadlock
that forced the DOM-event approach in phase 1. The destroy call still
happens from a DOM event.

A missing button now raises instead of failing silently, and a
regression test asserts the process actually exits after a click --
in the phase 1 deadlock the window closed while a non-daemon bridge
thread kept the process alive."
```

---

## Definition of Done

Verified against spec §9:

1. `pnpm build` in `frontend/` produces `dist/index.html` plus assets at the repo root — Task 1, Step 12.
2. `uv run nebula` opens the phase 1 card at 360 × 560 visible, 408 × 608 window — Task 2, Step 9.
3. `uv run nebula --dev` loads the dev server and hot-reloads — Task 3, Step 9.
4. `×` closes the window and the process exits — Task 3, Step 9.
5. The close-button regression test passes — Task 3, Step 7.
6. Both failure modes print their message instead of opening blank — Task 2, Step 8.
