# React + Vite Frontend Scaffold — Design

Date: 2026-09-01
Phase: 2 of the Daily Time Allocation widget (see [PRD.md](../../../PRD.md))
Status: Approved design, pending implementation plan

## 1. Purpose

Replace the hand-written HTML/CSS in `src/nebula/web/` with a React + TypeScript
frontend built by Vite, without changing what the user sees: the same hello-world
card at 360 × 560 in a frameless, transparent, always-on-top window.

This phase adds no product behavior. It exists so that phase 3 — the domain model
from PRD §20 — has a component model and type system to be built in.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Language | TypeScript | PRD §20 has a real state machine (ACTIVE / STALE / NOT_STARTED / BREAK / NEUTRAL). Types make illegal states hard to express and mirror the Python-side shapes across the bridge. |
| Styling | CSS Modules | Built into Vite, no extra dependency. The existing card CSS ports over nearly unchanged, and scoping prevents collisions once allocation rows, popups, and settings exist. |
| Dev loading | Vite dev server | HMR inside the real native window. Production loads the built output. |
| Dev workflow | Two terminals | `pnpm dev` and `uv run nebula --dev` run separately. No orchestration code; Vite's output stays readable. |
| Package manager | pnpm 11.17.0 | Already installed and in use on this machine. |
| Node | 24 LTS (Krypton) | Node 26 is the current line, not LTS. Pinned per §6. |

## 3. Layout

```
nebula/
├── .nvmrc                    # 24
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx          # React root
│       ├── App.tsx           # the card
│       └── App.module.css
├── dist/                     # Vite build output — gitignored
├── src/nebula/
│   ├── app.py
│   └── __main__.py
└── pyproject.toml
```

Frontend source and build output both live at the repo root. `src/nebula/web/`
disappears entirely.

An earlier draft put the build output inside the Python package, on the theory that
a bundler would then collect it as package data for free. That reasoning does not
hold: PyInstaller relocates data at build time and the app reads it from
`sys._MEIPASS`, so bundle-aware path resolution is required wherever Vite writes.
The benefit was illusory, and the cost was real -- `emptyOutDir: true` would aim a
recursive delete inside the source tree. A throwaway `dist/` carries no such risk.

## 4. Loading modes

`src/nebula/app.py` gains a mode switch:

- `uv run nebula --dev` loads `http://localhost:5173`.
- `uv run nebula` loads `dist/index.html` at the repo root.

Both modes must fail with a readable message rather than a blank window:

- **Dev**: if nothing is listening on 5173, exit with `Vite dev server not running on
  http://localhost:5173 — start it with 'pnpm dev' in frontend/`.
- **Production**: if `dist/index.html` is absent, exit with
  `Frontend not built — run 'pnpm build' in frontend/`.

This is the cost of the two-terminal workflow being paid down: a forgotten `pnpm dev`
produces an error, not a mystery.

### Two configuration details that fail silently if missed

1. **`base: './'` in `vite.config.ts`.** Production loads over `file://`, where Vite's
   default absolute `/assets/...` paths resolve against the filesystem root. Without
   this the production window is blank with no error.
2. **`#root` must be transparent.** React introduces a wrapper element that `html, body`
   transparency does not cover. If it keeps its default background the transparent
   window renders as an opaque rectangle, silently undoing PRD §27's frameless card.

`vite.config.ts` sets `build.outDir` to `../dist` with `emptyOutDir: true`.

`app.py` resolves the production path as `Path(__file__).parents[2] / "dist"`, which
is correct when running from a source checkout. A frozen `.app` reads from
`sys._MEIPASS` instead; that resolution belongs to the packaging phase and is out of
scope here.

## 5. The close button

### The problem

`_bind_close` currently runs on `window.events.loaded` and calls
`window.dom.get_element(".close")`. Under React the DOM at that moment is only
`<div id="root"></div>` — React has not mounted. The lookup returns `None` and the
existing `if close_button is not None` guard swallows it. The result is a dead close
button on a frameless window, with no error anywhere.

This regresses the fix from phase 1, where a `js_api` close deadlocked the app.

### The design

A readiness handshake:

1. After mount, React calls `window.pywebview.api.ui_ready()` from a `useEffect`.
2. `ui_ready` binds the click handler via `window.dom.get_element("[data-close]")`.
3. The handler calls `window.destroy()` — still from a **DOM event**, never from
   inside a `js_api` call.

The button is selected by a `data-close` attribute rather than by its class name.
This decision is forced by the CSS Modules choice in §2: CSS Modules rewrites class
names at build time into hashes such as `_close_1a2b3_4`, which the Python side
cannot predict. Selecting on `.close` would return `None` on every launch and
reproduce exactly the dead-button failure this section exists to prevent. The
attribute is styling-independent and stable across builds.

The distinction that makes this safe: a `js_api` method may not *destroy the window*,
because after it returns pywebview evaluates JS in the webview to deliver the return
value (`webview/util.py`, `js_bridge_call`). If the webview is gone, cocoa's
`evaluate_js` blocks forever on a semaphore in a non-daemon thread and the process
never exits. `ui_ready` returns normally, so it never reaches that state.

`ui_ready` is also the natural hook for Python to push initial state to the UI in
phase 3.

### Failure must be loud

The `if close_button is not None` guard is replaced by an explicit failure — log an
error and raise — if the element is missing at handshake time. A close button that
does nothing must not fail quietly a second time.

*Rejected alternative*: place the `×` in `index.html` outside `#root`, so it exists
at `loaded` and needs no handshake. Simpler, but it splits UI ownership between React
and raw HTML for a control that must later end the active tracking session (PRD §15).

## 6. Node version pinning

`node --version` in a non-interactive shell on this machine resolves to the **system
Node v26.8.1**, not nvm's v24.18.0. Build commands would therefore run on a non-LTS
runtime by default.

Mitigations, all three:

- `.nvmrc` containing `24` at the repo root.
- `"engines": { "node": ">=24 <25" }` in `frontend/package.json`, plus
  `engine-strict=true` in `frontend/.npmrc`. Without the `.npmrc`, pnpm only warns on
  a mismatched runtime; with it, running on the system's Node 26 fails immediately.
- `"packageManager": "pnpm@11.17.0"` in `frontend/package.json`.

## 7. Files changed

**Added**: `.nvmrc`; the whole `frontend/` tree.

**Deleted**: `src/nebula/web/index.html`, `src/nebula/web/style.css`, and the now
empty `src/nebula/web/` directory. Their content
moves to `frontend/index.html`, `App.tsx`, and `App.module.css`. The card styling,
the 24px shadow padding, and the transparent background carry over unchanged.

**Modified**:
- `src/nebula/app.py` — `--dev` flag, mode-dependent URL, loud close binding, and a
  re-introduced `js_api` object exposing `ui_ready`. Phase 1 removed the `Api` class
  when the close button moved off `js_api`; this phase brings it back for the
  handshake only. `create_window` must pass `js_api=` again.
- `src/nebula/__main__.py` — argument parsing for `--dev`.
- `.gitignore` — `node_modules/`, `dist/`, Vite caches.
- `README.md` — the two-terminal dev workflow, and that a fresh clone must run
  `pnpm build` before `uv run nebula` works.

`SHADOW_PADDING` in `app.py` and the `body` padding in CSS must stay in sync; the
existing comment saying so moves with the CSS.

## 8. Testing

One behavior in this phase has a proven failure mode and gets a real test:

- **Close-button regression test.** Requires `pnpm build` to have run. Launches the
  app against the built frontend, waits for the `ui_ready` handshake rather than
  `loaded` (under React the button does not exist at `loaded`), clicks `×`
  programmatically, and asserts the process exits within a timeout. Asserting on
  *process exit* is what catches the phase 1 deadlock, where the window closed but a
  non-daemon bridge thread kept the process alive; asserting only that the window
  closed would have passed. It also catches the phase 2 mount-timing break, where the
  button is never bound. Promoted from the throwaway repro script used to diagnose
  the original bug.

Explicitly not tested in this phase:

- Frontend unit tests. There is no logic yet, only a card. Vitest earns its place in
  phase 3 alongside the domain model.
- Visual/transparency correctness, which needs human eyes; `screencapture` is blocked
  because the terminal lacks Screen Recording permission.

## 9. Definition of done

1. `pnpm build` in `frontend/` produces `dist/index.html` plus assets at the repo root.
2. `uv run nebula` opens the same hello-world card as phase 1 — 360 × 560 visible
   card, 408 × 608 window, rounded corners, drop shadow, no native frame.
3. `uv run nebula --dev` loads the Vite dev server, and editing `App.tsx` hot-reloads
   inside the native window.
4. The `×` button closes the window and the process exits.
5. The close-button regression test passes.
6. Both failure modes produce their intended message instead of a blank window.

## 10. Distribution decisions recorded here (not implemented in this phase)

Settled while reviewing this spec, so they are not re-litigated when the packaging
phase arrives (PRD §26):

- **Target arm64 only.** No intended recipient has an Intel Mac. pyobjc already ships
  universal2 binaries (verified: `_WebKit...so` reports `x86_64 arm64`), so the sole
  blocker would be uv's interpreter, which is `macos-aarch64` only with no universal2
  build on offer. Going universal means building against a universal2 Python from
  python.org rather than uv's. Revisit only if an Intel recipient appears.
- **Recipients install nothing.** The frozen bundle carries its own interpreter. The
  system Python at `/usr/bin/python3` is 3.9.6, below this project's `>=3.13`
  requirement, so it could not have been used regardless. WebKit comes from macOS.
- **Expect roughly 25-40MB.** `PyObjCTest` is 16MB of the 37MB virtualenv and is never
  imported by `objc`; excluding it is the single biggest win. This is an estimate from
  measuring inputs, not from a build.
- **Known freezing hazard.** `webview/util.py:352` globs `webview/js/**/*.js` at
  runtime. Static analysis cannot see those files, so they must be declared as bundle
  data or the app fails at runtime rather than at build time. This is why packaging
  warrants a spike.

## 11. Out of scope

Any product behavior from the PRD: allocations, sessions, the JSON store, day
anchoring, notifications, Break/Complete controls, `.app` packaging. Phase 2 ends
with a hello-world card rendered by React.
