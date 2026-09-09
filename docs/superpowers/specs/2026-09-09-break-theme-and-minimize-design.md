# Break Theme and Minimize — Design

Date: 2026-09-09
Phase: 5 (see [ROADMAP](../../ROADMAP.md))
Status: Approved design, pending implementation plan

## 1. Purpose

Two changes to the dashboard, both post-V1:

1. **Break recolours the whole widget.** Today Break shows a green chip in the
   header and a green outline on one button; everything else stays purple. The
   mock turns the entire card green, so the state is legible from across the
   room rather than by reading a label.
2. **A minimize control.** The card collapses to a 320×86 bar carrying the
   Active allocation, the day's total, and three controls — pause, complete,
   expand.

Neither is in the PRD. Both were checked against §24's backlog before starting;
minimize is not there under any name, so this phase adds product surface rather
than closing a checklist.

## 2. Source of truth

Two mocks supplied with the request: the dashboard in Break, and a minimized
bar in three variants (active, break, over allocation). Colours below are
sampled from those images, not guessed.

Where a sampled value sits within a few percent of a token the app already has,
the token wins. Three near-duplicates would otherwise enter the palette for no
visible gain:

| Sampled | Existing token | Resolution |
|---|---|---|
| `#98e1bb` (break green) | `--break: #7fe3b8` | Keep the token. |
| `#c6b7f1` (active dot, bar) | `--accent: #c9b6f5` | Keep the token. |
| `#d48e6a` (over-allocation) | `--over: #e08a63` | Keep the token. |

The genuinely new values are Break's surfaces, which have no equivalent today.
Each overrides a named token, so the implementer is never guessing which
declaration a sampled colour belongs to:

| Role | Value | Token overridden |
|---|---|---|
| Card background | `#111418` | `--card` |
| Card border | `#212a2a` | `--card-border` |
| Row background | `#151a1a` | `--row-active`, `--row-stale` |
| Row border | `#212a29` | `--row-active-border`, `--row-stale-border` |
| Progress track | `#212a29` | `--track` |
| Progress fill, stale rows | `#627972` | stale fill (`--fill-stale`, new in §3.2) |
| Primary text | `#e1e9e4` | `--text` |
| Row name | `#c9d3ce` | `--text-strong` (new in §3.2) |
| Caption | `#58625d` | `--text-2` |
| Engaged control fill | `#18221f` | `--control-engaged` (new in §3.2) |

## 3. Break theme

### 3.1 Mechanism

`index.css` already defines the palette as custom properties on `:root`, and
every component consumes them. So the whole recolour is one override block
keyed off a `data-status` attribute on the card root:

```css
[data-status='BREAK'] {
  --card: #111418;
  --card-border: #212a2a;
  --accent: var(--break);
  /* …the rest of §2's table */
}
```

No component's markup or logic changes. Overlays — Settings, the allocation
form, the recap — sit inside the card, so they inherit the same override and
cannot end up half-purple.

### 3.2 The prerequisite

The override only reaches what actually reads a token, and 23 colours are
currently hardcoded across eight module stylesheets. They collapse into a small
set of repeats:

| Hex | Occurrences | Becomes |
|---|---|---|
| `#2b2439` | 7 | `--hairline` |
| `#7d7496` | 4 | `--label` |
| `#8d84a4` | 3 | `--text-3` |
| `#3f3a53` | 1 | `--hint` |
| `#5a5372`, `#6a5f88`, `#7f7699`, `#cfc7de`, `#322a44`, `#201b2b` | 1 each | row and summary internals |

Promoting these is part of this phase, not a refactor beside it: leave them and
the Break card renders green with purple-grey buttons, hints and hairlines.

### 3.3 What does not change

Button placement stays exactly as it is — `BREAK` and `COMPLETE` side by side.
The mock shows a single full-width `ON BREAK` button instead, and that part of
it is deliberately not adopted. The header chip, the hint line, and every
layout dimension are also untouched. This is a colour change.

## 4. The minimized bar

### 4.1 Entry point

A minimize button in the card's top-left corner, on the same line as the gear
and close buttons that sit top-right. Like them it is window chrome, absolutely
positioned, and costs no vertical space in a card that already scrolls.

Every control this phase adds carries a `data-` hook, following the convention
the close button established for the same reason CSS Modules forces: hashed
class names cannot be selected from Python or from a test.

| Control | Hook |
|---|---|
| Minimize, on the full card | `[data-minimize]` |
| The bar itself | `[data-minimized]` |
| Pause, on the bar | `[data-mini-break]` |
| Complete, on the bar | `[data-mini-complete]` |
| Expand, on the bar | `[data-expand]` |

### 4.2 Geometry

```
320 x 86 card, inside a 384 x 150 window (86 + 2 x 32 shadow padding)

┌──────────────────────────────────────────────┐
│ ●  Work                      ⏸   ✓   ⤢       │
│    2h 24m / 3h · 80%                         │
│    ▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░  4h 10m / 7h · 60%   │
└──────────────────────────────────────────────┘
   dot + title + figures      controls + day total
```

The left column describes what is being tracked; the right column is the day as
a whole plus the three controls. The progress bar spans the card's width.

### 4.3 States

| State | Dot | Title | Subtitle | ✓ button |
|---|---|---|---|---|
| Active | `--accent` | allocation name | `2h 24m / 3h · 80%` | outline |
| Break | `--break` | `On break · 12m` | `nothing accumulating` | outline, break palette |
| Over allocation | `--over` | allocation name | figures in `--over`, past 100% | **filled** `--over` |
| Idle | `--muted` | `Nothing tracking` | — | outline |

Idle covers both a day not yet started and a day already completed. It shows
the day's totals like every other state, so the bar always says something true
and the minimize button never has to be disabled — a control that dies for
reasons not visible on screen reads as a bug.

### 4.4 Controls

| Control | Action |
|---|---|
| ⏸ pause | `toggle_break`, the same call the `BREAK` button makes. |
| ✓ complete | `complete_day`, then expand and show the existing recap. |
| ⤢ expand | Restores the full card. |

Completing while minimized expands deliberately: the recap cannot fit in 86px,
and it is the payoff for ending the day rather than a detail to discover later.

Icons are inline SVG. The app has no icon dependency and this is not the change
that should add one.

### 4.5 Where the logic lives

A pure `minimized.ts` derives the bar's view model — dot role, title, subtitle,
figures, over-allocation flag — from a `DashboardView`. `MinimizedCard.tsx`
renders that model and nothing else.

The split is not decoration. This repo unit-tests pure modules (`format`,
`tick`, `targets`, `milestones`) and does not test components, so every branch
in the table above is only reachable by vitest if it lives outside the
component.

## 5. The window

`Api.set_minimized(minimized: bool)` resizes the native window; React holds
whether the bar or the card is showing. Constants sit beside `CARD_HEIGHT` in
`app.py`:

```python
MINI_CARD_HEIGHT = 86
WINDOW_MINI_HEIGHT = MINI_CARD_HEIGHT + SHADOW_PADDING * 2   # 150
```

Verified before designing around it, against a window created exactly as
production creates one (`resizable=False`, frameless, transparent, on top):

| Step | Result |
|---|---|
| Before | `384 x 684` at `x=0, y=1169` |
| `window.resize(384, 150)` | `384 x 150` at `x=0, y=1169` |
| `window.resize(384, 684)` | `384 x 684` at `x=0, y=1169` |

`resizable=False` does not block a programmatic resize, and `resize()` defaults
to `FixPoint.NORTH | FixPoint.WEST`, so the card's top-left stays put and the
window collapses upward from the bottom. The position is unchanged in all three
readings above.

Resizing from a `js_api` method is safe. The prohibition documented in
`_bind_close` is specific to *destroying* the window — pywebview evaluates JS
in the webview to return a value, so a method that tears the webview down hangs
the bridge thread forever. A resize leaves the webview alive to answer.

## 6. Consequences elsewhere

| Thing | Why it is affected |
|---|---|
| `frontend/src/demo/store.ts` | The demo's fake bridge must grow `set_minimized`, or the README recording dies on a missing method. |
| `assets/demo.gif` | The recording shows the old grey Break state. Re-run `node scripts/record-demo.mjs` once this lands. |
| ROADMAP | Needs a phase 5 row; every other phase has one. |

## 7. Testing

| Test | Covers |
|---|---|
| `minimized.test.ts` | Every row of §4.3 — the state branching, the figures, the over-allocation flag. |
| Python unit test | `set_minimized` resizes to `384 x 150` and back, against a fake window. |
| GUI test | Click `[data-minimize]` in the real app; assert the window's height becomes 150 and the bar renders. |

The GUI test earns its cost here for the same reason the phase 2 and 3b ones
did: the failure this feature can actually ship is a resize that works in
isolation and not through the bridge, which no unit test would see.

## 8. Decisions taken

| Question | Decision | Why |
|---|---|---|
| What does ✓ do? | Ends the day — `complete_day`. | The data layer has no notion of finishing one allocation; adding it would mean new rules, new stored state, and a new full-card presentation. |
| ✓ while minimized? | Expand and show the recap. | The recap does not fit in 86px, and missing it entirely is worse than a window that grows. |
| Persist minimized? | No. React state only. | Keeps the stored JSON untouched. Persisting would also mean sizing the window before first paint, or the app opens big and visibly snaps small. |
| Idle bar? | Day total with a muted line. | Mirrors Break's `nothing accumulating`. Never blocks minimizing. |

## 9. Out of scope

- Per-allocation completion (§8).
- Remembering the minimized state across restarts (§8).
- Menu-bar or tray presence, still backlogged at PRD §24. Minimize makes the
  window small; it does not make it disappear.
- Any layout change to the full card beyond the minimize button itself.

## 10. Risks

**86px is tight.** Three controls, two lines of text, a progress bar and the
day's totals. If the mock's proportions do not survive at real size, the bar
grows a few pixels rather than the type shrinking below the 10px the rest of
the app already bottoms out at.

**Two themes at once.** Break and minimized can be active together, and the
mock shows exactly that — a green bar. The bar renders inside the card root, so
it inherits the Break override for free. This is intended, and the
`minimized.test.ts` cases cover the combination.
