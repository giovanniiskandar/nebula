# Dashboard — Design

Date: 2026-09-07
Phase: 3b (see [ROADMAP](../../ROADMAP.md))
Status: Approved design, pending implementation plan

## 1. Purpose

Give `tracker.py` its first caller and replace "Hello world" with the real
widget: allocations with their progress, the activity states, Break and
Complete, and the day-completion recap.

Covers the PRD's **Dashboard** and **Day Completion** checklists.

## 2. Source of truth

The design comes from the mock in `Daily Time Allocation - Widget.dc.html`
(PRD §27), which is design-canvas markup and not embeddable — it is a visual
reference that gets reproduced in React.

The mock predates PRD V1.1 and conflicts with it in three places. The PRD wins
each time, because Day Completion was added deliberately during the grilling
session that produced V1.1:

| Conflict | Mock | Resolution |
|---|---|---|
| Complete control | absent; only `BREAK` | PRD §11 requires both, always visible. Added beside Break. |
| Completion popup | absent | PRD §18.2 requires it. Designed here in the mock's language. |
| Empty state | absent | PRD §10.1 requires it. Designed here. |

The mock also supersedes a phase 1 decision: it specifies **320 × 520**, while
phase 1 shipped 360 × 560 — a size chosen from options when this file could not
be found. The mock's paddings and type sizes are drawn against 320, so the
mock's size wins.

## 3. Decisions

| Decision | Choice | Why |
|---|---|---|
| Card width | 320 | The mock's measurements assume it. |
| Card height | 620 | The mock's 520 was too short in use; see §4. |
| Shadow margin | 32px, window 384 × 684 | See §4. |
| Controls | Break and Complete side by side | One row, equal weight, no extra height. |
| Empty state | Copy with a disabled Add button | Adding allocations is 3c. |
| Completed day | Popup is transient React state | See §7. |
| Break timer | New `break_started_at` field | See §6. |
| Font | Bundled, not CDN | See §4. |
| Ticking | Local, no polling | See §8. |

## 4. Visual system

The mock's palette and JetBrains Mono replace the phase 1 system-font card.
Tokens are CSS custom properties on `:root` in `index.css`, so 3c and 3d
inherit them rather than re-deriving colours.

```
ground        #0b0910   card          #131019   card border   #241f31
row active    #1b1626   border        #34294f
row stale     #161220   border        #221d2e
text primary  #efeaf7   secondary     #a79dbe   muted         #5f5875
dim           #4a4460
accent        #c9b6f5   over-target   #e08a63   break         #7fe3b8
track         #251f33
```

Card: `border-radius: 14px`, `padding: 20px 18px`, `1px` border, column layout
with `18px` gaps. Type: `TODAY` at 700/10.5px with `.22em` tracking; the date at
10.5px; the summary figure at 500/28px; allocation names at 500/13.5px; numbers
at 11.5px; captions at 10.5px; badges at 700/9px with `.16em` tracking.

### Two problems the mock creates

**The shadow does not fit.** The mock specifies
`0 24px 60px -20px rgba(0,0,0,.9)`, which paints roughly 64px below the card.
Anything outside the *window* is clipped by the OS — the phase 1 finding — so
containing it exactly would need a 448 × 648 window, leaving a 64px transparent
ring that still swallows clicks. **The shadow is tightened to fit a 32px
margin** (`0 12px 28px -8px rgba(0,0,0,.9)`), giving a 384 × 684 window.
`SHADOW_PADDING` becomes 32 and must stay in sync with the `body` padding.

**The height outgrew the mock.** The mock's 520 fits its own three allocations
and nothing else: in use, three rows already pushed the controls' hint text off
the bottom edge. The card is **620** tall, the allocation list scrolls, and the
header, summary and controls stay put however many allocations exist. The
width stays at the mock's 320, which its type and spacing are drawn against.

**The font is loaded from a CDN.** The mock links Google Fonts. A bundled `.app`
may have no network, and the link would fail silently to Menlo — a change of
character with no error. `@fontsource/jetbrains-mono` is installed instead so
Vite emits the font files into `dist/`. Weights 400, 500 and 700 are used.

## 5. The bridge

`Api` exposes these, each returning the dashboard as a JSON-serialisable dict:

```
ui_ready()            -> dict     binds close, resume point, first view
resume()              -> dict     the Start control (PRD §18.3)
activate(id: str)     -> dict     PRD §10.3, §10.4
toggle_break()        -> dict     PRD §6.4
complete_day()        -> dict     PRD §10.6
```

`ui_ready` changes return type from `bool` to the view dict. It keeps binding
the close button — that job does not move — and additionally performs the
resume point, so the first paint needs one call rather than two.

There is deliberately no `get_view()`. Every method returns the current view, so
nothing would call it.

Every one returns the *whole* view rather than a delta, so the frontend never
maintains a second copy of the truth; React renders what it is handed.

**This is where real time enters the program.** Each method calls
`datetime.now().astimezone()` and passes it down, preserving the property 3a was
built for: rules take `now` as an argument and are tested against real
timestamps with nothing patched. `Api` is the only new place that reads a clock.

`app.py` constructs one `Tracker` over `store.data_path(dev)`, so `--dev` writes
`data.dev.json` and development cannot corrupt real history.

`model.py` gains `view_to_dict(DashboardView) -> dict`, camelCase like the
existing `to_dict`. It lives beside the other serialisation rather than in
`app.py`, so the window shell stays about windows.

Both `ui_ready` and `resume` call `Tracker.open`, which is the resume point
(PRD §17): it runs the date check and recovers a session left open by a crash.

### Failure

A `DataFileCorrupt` from `store.load` must not produce a blank card. The bridge
lets it propagate: pywebview catches an exception raised in a `js_api` method
and rejects the JavaScript promise with the message, so the frontend renders an
error state naming the file path. A corrupt file is then recoverable by a person
rather than mysterious.

This is safe only because none of these methods destroys the window. A `js_api`
method that called `window.destroy()` would deadlock the app — the phase 2
finding, recorded in `_bind_close`.

## 6. Data layer addition

One field, for the Break timer the mock shows as `ON BREAK · 12m`:

- `CurrentState.break_started_at: datetime | None` — set entering Break,
  cleared leaving it.
- `DashboardView.break_started_at: str | None` — ISO, ticked by React.

Deriving it from the last session's `ended_at` was rejected: it shows nothing
when Break is entered from Neutral (PRD §6.4), where no session exists.

**`from_dict` must read it with `.get()`.** The existing fields are indexed
directly, so a plain `raw["current"]["breakStartedAt"]` would raise `KeyError`
on every data file written before this phase.

## 7. Screens

### Dashboard

Header `TODAY` with the date at right (`MON 31 AUG`). Summary: tracked figure at
28px, `tracked of 7h planned` beneath, overall percentage at right, separated by
a bottom border. Then the allocation rows, then the controls pinned to the
bottom with `margin-top: auto`.

Each row shows name, state badge, `2h 24m / 3h`, percentage, a 5px progress bar,
and a caption (`36m left`). The Active row has a distinct background, a lighter
border, and a 2px accent bar down its left edge. Not Started rows use the dim
text colour and an empty track.

Clicking a row calls `activate` (PRD §10.4) — no confirmation.

### Over allocation

At or past 100% the row's bar fills completely and turns amber, the caption
becomes `45m over allocation`, and a `target 3h ↑` marker appears. Tracking is
never capped or stopped (PRD §8).

### Break

Badge `ON BREAK · 12m` in the header, ticking. The Break button renders in its
engaged state reading `ON BREAK`, and the helper text becomes `pick an
allocation to resume`. Every allocation with time shows `STALE`. Clicking Break
again resumes the pre-break allocation; clicking any allocation activates that
one and exits Break (PRD §6.4).

### Completion popup

Shown immediately after `complete_day()` returns. Per-allocation breakdown —
name, `actual / target`, percentage — frozen from the returned view, then
`Good work today!`. PRD §18.2 personalises this with the Name from Settings,
which does not exist until 3c; the PRD specifies this generic fallback, so 3b
ships it and 3c adds the name.

Closing the popup reveals a `Start` control. Clicking Start calls `resume()` —
a resume point, so the date check runs (PRD §18.3) — and returns to the
dashboard.

The popup is **transient React state**, not persisted. Reopening the app on the
same date shows the ordinary dashboard with totals intact, which is what PRD §17
specifies for a same-date resume. This is why no `day_completed` field is added:
`resume()` does not clear completions, so a persisted flag would re-trigger the
popup after Start on the same day.

### Empty state

When there are no visible allocations: `Plan your day`, `Create your first time
allocation.`, and a visibly disabled `+ Add Allocation` button. 3c enables it.
Seeding allocations for development is a script, not app behaviour.

## 8. Live ticking

React ticks once a second. It adds `now - active_since` to the single Active
allocation and `now - break_started_at` to the Break badge, then recomputes
percentage, remaining, the overall total and the bar widths from that ticked
value.

No polling. Python derives every figure from timestamps and shares the machine
clock, so a local tick and a Python recomputation agree; authoritative values
arrive again with every action's return value. Nothing else can change the data
while the app runs — there is no background process and only one instance.

The tick must not accumulate: it recomputes from `active_since` on each frame
rather than incrementing a counter, so a missed interval cannot drift.

## 9. Component structure

```
App               state, tick, calls the bridge
├── Header        TODAY, date, ON BREAK badge
├── Summary       tracked / planned / percentage
├── AllocationList
│   └── AllocationRow    one allocation, all states
├── Controls      Break, Complete, helper text
├── CompletionPopup
└── EmptyState
```

`format.ts` holds duration formatting — `2h 24m`, `36m`, `45m over allocation`,
`MON 31 AUG` — as pure functions. It is the only real logic in the frontend and
is unit-tested on its own.

## 10. Testing

Python:

- `view_to_dict` produces the expected shape, including `null` for absent
  `active_since` and `break_started_at`.
- Each `Api` method returns a dict and applies the right rule.
- `break_started_at` is set entering Break, cleared leaving it, and round-trips
  through `to_dict`/`from_dict`.
- `from_dict` still reads a data file written before this phase.

Frontend — **vitest arrives in this phase**, because there is now logic worth
testing:

- `format.ts` against real values, including zero, over-target and exact-target.
- The tick arithmetic: given a fixed `active_since` and a fixed `now`, the
  derived tracked seconds, percentage and remaining are correct. Real inputs,
  not a patched clock.

The existing GUI test extends: seed a data file with known allocations, launch,
and assert the rendered rows match — the close-button test proved that driving
the real app catches what mocked tests miss.

## 11. Out of scope

Add, edit and delete allocations, the duration parser, and the Name field (3c).
Notifications (3d). `sys._MEIPASS`, the single-instance lock and packaging (4).
Sleep/wake detection, which V1 deliberately omits.

## 12. Definition of done

1. `uv run nebula` shows the real dashboard against `data.json`.
2. Clicking an allocation activates it; the previous one becomes Stale.
3. The Active allocation ticks once a second without drift.
4. Break pauses tracking, shows the ticking badge, and toggles back to the
   previous allocation.
5. Complete shows the recap; Start returns to the dashboard.
6. Past 100% the row goes amber and keeps counting.
7. With no allocations, the empty state renders.
8. The card is 320 × 620 in a 384 × 684 window, with the shadow fully visible.
9. The font renders from bundled files with the network off.
10. Python and frontend test suites pass.
