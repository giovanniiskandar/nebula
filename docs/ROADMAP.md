# Roadmap

How the [PRD](../PRD.md) gets built, and what is finished.

Each phase produces something that works on its own. Specs live in
`docs/superpowers/specs/`, plans in `docs/superpowers/plans/`, and
investigations in `docs/superpowers/spikes/`.

## Status

| Phase | What it delivers | State |
|---|---|---|
| 1 | pywebview window shell | **Done** |
| 2 | React + Vite + TypeScript frontend | **Done** |
| — | Packaging spike (investigation) | **Done** |
| 3a | Data layer — the tracking engine | **Done** |
| 3b | Dashboard | **Done** |
| 3c | Settings | **Done** |
| 3d | Notifications | **Done** |
| 4 | Packaging and distribution | **Done** |
| 5 | Break theme and minimize | **Done** |

---

## Phase 1 — Window shell · Done

A frameless, transparent, always-on-top card: 360 × 560 visible inside a
408 × 608 window, the extra 24px being the transparent margin the drop shadow
casts into. Close button, and the Dock icon set through pywebview.

Confirmed two PRD §27 claims that had only been checked by reading pywebview's
source: `on_top` works on macOS, and `transparent` renders the CSS card without
a native frame.

## Phase 2 — React frontend · Done

Vite building `frontend/` to `dist/`, CSS Modules, TypeScript. `uv run nebula`
loads the build; `--dev` loads the Vite dev server for hot reload inside the
native window. Both fail with an actionable message rather than a blank window.

The close button binds through a `ui_ready` handshake, because React mounts
after pywebview's `loaded` event and the button does not exist yet at that
point.

- Spec: `specs/2026-09-01-react-vite-scaffold-design.md`
- Plan: `plans/2026-09-01-react-vite-scaffold.md`

## Packaging spike · Done

Not a phase — a timeboxed investigation whose output was an answer, not code.

Built a working 28MB `Nebula.app` and threw it away. Two of the four predicted
problems did not exist, including the runtime JS glob that was the main argument
for spiking at all. What it did find: `PROJECT_ROOT` needs `sys._MEIPASS`
handling, `--add-data` resolves relative to `--specpath`, and three `Info.plist`
values need setting.

- Findings: `spikes/2026-09-01-packaging-spike-findings.md`

## Phase 3a — Data layer · Done

The tracking engine, headless. `model.py`, `rules.py`, `store.py`,
`tracker.py` — allocations, sessions, Break, Complete, day rollover, start and
end dates, and atomic JSON persistence to
`~/Library/Application Support/Nebula/`.

Time and ids arrive as arguments rather than being read from the environment,
so the rules are tested against real timestamps with nothing patched.

Closes the PRD's **Time Tracking** and **Data** checklists apart from the
single-instance guard.

- Spec: `specs/2026-09-01-data-layer-design.md`
- Plan: `plans/2026-09-01-data-layer.md`

---

## Phase 3b — Dashboard · Done

`tracker.py` got its first caller and the widget stopped saying "Hello world".
Allocations with their progress and states, Break and Complete side by side,
the day-completion recap, the empty state, and a named error when the data file
is corrupt. React ticks the Active allocation and the Break badge once a second.

Adopted the mock's 320 width, superseding phase 1's 360, which had been picked
from options because the mock could not be found at the time. The height went
to 620 rather than the mock's 520, which in use was too short to hold three
allocations and the controls at once; the list scrolls instead. The mock's
shadow was tightened to fit the 32px margin rather than paying for a 64px
transparent ring that still swallows clicks, and its font is bundled rather
than fetched from a CDN a packaged `.app` may not reach.

Added one data-layer field, `break_started_at`, for the timer the mock shows.

Closes the PRD's **Dashboard** and **Day Completion** checklists.

- Spec: `specs/2026-09-07-dashboard-design.md`
- Plan: `plans/2026-09-07-dashboard.md`

## Phase 3c — Settings · Done

A gear left of the close button opens Settings over the card. Add, edit and
delete allocations; an optional name that personalises the Day Completion
message.

The mock had no settings entry point and no back control, so navigation is new
in both directions. It also had no Name field, and a Notifications section with
a 95% chip and a toggle that V1 does not support — omitted rather than faked,
since PRD §13 fixes both thresholds.

The target is entered as `hh`/`mm` with preset chips rather than parsed from
free text. **There is no duration parser**: nothing invalid can be expressed, so
there is no validation rule, no error state and no edge cases. Minutes above 59
carry into hours instead of being rejected.

`Preferences.name` turned out to be write-only in theory and never written — no
rule, no `Tracker` method, absent from `DashboardView`. 3b's generic recap
fallback was waiting on a data path that was never built.

Closes the PRD's **Allocation Management** checklist.

- Spec: `specs/2026-09-07-settings-design.md`
- Plan: `plans/2026-09-07-settings.md`

## Phase 3d — Notifications · Done

Banners at 95% and 100%, once per allocation per day, delivered by shelling out
to `osascript`. Nothing in Python ticks, so React notices a crossing during the
tick it already runs and Python decides from timestamps whether it is real.

Only accumulating time fires a milestone. Crossing a threshold any other way --
a target edit, or crash recovery closing a session at the current time --
records it silently, so no banner ever announces a number the user just typed
or something that happened while the app was closed.

The message is passed as `argv` against a fixed script template. Allocation
names are user input that ends up inside an AppleScript, so interpolating them
would be a shell-injection hole.

Closes the PRD's **Notifications** checklist.

- Spec: `specs/2026-09-07-notifications-design.md`
- Plan: `plans/2026-09-07-notifications.md`

## Phase 4 — Packaging and distribution · Done

`scripts/build.sh` produces `release/Nebula.app` and a 17MB
`release/Nebula-0.1.0.dmg` carrying the app, a symlink to `/Applications` and
the first-run instructions.

PRD §15's single-instance guard needed no code. With PyInstaller's default
bare-name `CFBundleIdentifier`, opening the app three times produced three
processes; with `com.giovanniiskandar.nebula`, the second `open` leaves one.
LaunchServices keys single-instancing off that identifier.

The version is read from `pyproject.toml` into the `Info.plist`, so the two
cannot drift — the spike found them already disagreeing.

Output goes to `release/`, not `dist/`: PyInstaller defaults to `dist/`, which
is Vite's output and is emptied by every frontend build.

`tests/test_bundle.py` builds the real artifact and launches it, rather than
asserting on the spec file. Every packaging bug found so far appeared only in a
real bundle. It is marked `slow` and excluded from the pre-commit hook.

**Closes every remaining item on the PRD's V1 checklist.**

- Spec: `specs/2026-09-07-packaging-design.md`
- Plan: `plans/2026-09-07-packaging.md`

## Phase 5 — Break theme and minimize · Done

Break recolours the whole widget rather than flagging itself with a badge, and
a minimize control collapses the card to a 320x86 bar.

Neither is in the PRD; both are post-V1 product surface. See the
[design](superpowers/specs/2026-09-09-break-theme-and-minimize-design.md).

The recolour is a block of token overrides keyed off `data-status`, which
needed the 23 colours hardcoded across eight stylesheets promoted to tokens
first. Minimize resizes the native window through a new `js_api` method;
pywebview's `resize()` works on a `resizable=False` window and pins the
top-left by default.

---

## Deliberately not in V1

Sleep/wake detection (PRD §16) — an allocation counts through sleep, and Break
is the manual control. Signed and notarised distribution (§26). Everything in
the backlog at §24.

## Verification gaps

Two things the spike could not close, both belonging to phase 4:

- The bundle has never run on **another Mac**, which is the only test that
  matters for handing it to a friend.
- **Notifications depend on a macOS setting the app cannot see.** Banners are
  delivered by `osascript` and therefore attributed to Script Editor, so
  whether one appears live, goes quietly to Notification Center, or is dropped
  entirely is governed by Script Editor's alert style in System Settings. On
  this machine they arrive but do not flash as banners. A recipient whose
  Script Editor notifications are off gets nothing, and neither the app nor
  `osascript`'s exit code can tell. The first-run instructions (PRD §26) should
  say so.
- The Gatekeeper first-run dialog has never been triggered. Its policy is
  confirmed (`spctl -a` reports `rejected`) but the prompt itself needs a human,
  on a machine that did not build the app.
