# Break Theme and Minimize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Break recolours the entire widget green, and a minimize control collapses the card to a 320×86 bar with pause, complete and expand.

**Architecture:** The palette already lives in CSS custom properties on `:root`, so Break is one override block keyed off a `data-status` attribute — once the 23 colours still hardcoded in component stylesheets are promoted to tokens. Minimize is a React state flag that swaps the card's contents for a `MinimizedCard`, plus one new `js_api` method that resizes the native window. All branching logic lives in a pure `minimized.ts` because this repo unit-tests modules, not components.

**Tech Stack:** React 19 + TypeScript + Vite (CSS Modules), vitest for frontend tests, Python 3.13 + pywebview, pytest with a `gui` marker for tests that open a real window.

**Spec:** `docs/superpowers/specs/2026-09-09-break-theme-and-minimize-design.md`

## Global Constraints

- Branch: `feat-break-and-minimize`. Squash-merged to `main` when complete.
- Card geometry: `CARD_WIDTH = 320`, `CARD_HEIGHT = 620`, `SHADOW_PADDING = 32`, so `WINDOW_WIDTH = 384` and `WINDOW_HEIGHT = 684`. The bar is `MINI_CARD_HEIGHT = 86`, so `WINDOW_MINI_HEIGHT = 150`.
- Every new control carries a `data-` hook: `[data-minimize]`, `[data-minimized]`, `[data-mini-break]`, `[data-mini-complete]`, `[data-expand]`. CSS Modules hashes class names, so nothing else can be selected from Python or a test.
- Break's sampled values, verbatim: card `#111418`, card border `#212a2a`, row background `#151a1a`, row border and track `#212a29`, stale fill `#627972`, text `#e1e9e4`, row name `#c9d3ce`, caption `#58625d`, engaged control fill `#18221f`.
- The existing tokens `--break: #7fe3b8`, `--accent: #c9b6f5` and `--over: #e08a63` are reused, not replaced. The mock's near-identical `#98e1bb` / `#c6b7f1` / `#d48e6a` must not enter the palette.
- Button placement on the full card does not change: `BREAK` and `COMPLETE` stay side by side.
- No new npm or Python dependencies. Icons are inline SVG.
- Run `cd frontend && pnpm build` before any `gui`-marked test; they load `dist/`.

---

### Task 1: Promote hardcoded colours to tokens

The Break override can only reach declarations that read a token. Twenty-three colours are hardcoded across eight stylesheets, so this lands first, on its own, with no visual change whatsoever.

**Files:**
- Modify: `frontend/src/index.css:12-27` (the `:root` block)
- Modify: `frontend/src/components/AllocationRow.module.css`, `Controls.module.css`, `Header.module.css`, `Summary.module.css`, `EmptyState.module.css`, `AllocationForm.module.css`, `SettingsPanel.module.css`, `CompletionPopup.module.css`
- Test: `frontend/src/theme.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: the tokens `--hairline`, `--label`, `--text-3`, `--text-strong`, `--target`, `--badge-border`, `--badge-text`, `--fill-stale`, `--rule`, `--hint`, `--control-engaged`. Task 2 overrides exactly these names.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/theme.test.ts`:

```ts
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The Break theme is a block of token overrides, so it only reaches
 * declarations that read a token. A colour written into a component is
 * invisible to it, and the card renders green with purple-grey parts.
 */
const COMPONENTS = fileURLToPath(new URL('./components', import.meta.url))

describe('the palette', () => {
  it('lives in index.css, not in component stylesheets', () => {
    const offenders = readdirSync(COMPONENTS)
      .filter((name) => name.endsWith('.css'))
      .flatMap((name) => {
        const hexes = readFileSync(`${COMPONENTS}/${name}`, 'utf8').match(
          /#[0-9a-fA-F]{3,8}\b/g,
        )
        return hexes === null ? [] : [`${name}: ${hexes.join(', ')}`]
      })

    expect(offenders).toEqual([])
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm exec vitest run src/theme.test.ts`
Expected: FAIL, listing all eight files — `AllocationForm.module.css: #2b2439, #2b2439, …` and so on.

- [ ] **Step 3: Add the tokens**

In `frontend/src/index.css`, extend the `:root` block. Keep the existing fifteen tokens exactly as they are and append:

```css
  /* Promoted out of the component stylesheets so the Break override in
     `[data-status='BREAK']` can reach them. The values are unchanged. */
  --hairline: #2b2439;
  --label: #7d7496;
  --text-3: #8d84a4;
  --text-strong: #cfc7de;
  --target: #5a5372;
  --badge-border: #322a44;
  --badge-text: #7f7699;
  --fill-stale: #6a5f88;
  --rule: #201b2b;
  --hint: #3f3a53;
  /* Break gives the engaged control a fill; nothing else does. */
  --control-engaged: transparent;
```

- [ ] **Step 4: Replace every hardcoded colour**

Exact substitutions, all of them value-preserving:

| File | From | To |
|---|---|---|
| `AllocationRow.module.css` | `#cfc7de` | `var(--text-strong)` |
| `AllocationRow.module.css` | `#322a44` | `var(--badge-border)` |
| `AllocationRow.module.css` | `#7f7699` | `var(--badge-text)` |
| `AllocationRow.module.css` | `#5a5372` | `var(--target)` |
| `AllocationRow.module.css` | `#8d84a4` | `var(--text-3)` |
| `AllocationRow.module.css` | `#6a5f88` | `var(--fill-stale)` |
| `Controls.module.css` | `#2b2439` | `var(--hairline)` |
| `Controls.module.css` | `#8d84a4` | `var(--text-3)` |
| `Controls.module.css` | `#3f3a53` | `var(--hint)` |
| `Header.module.css` | `#7d7496` | `var(--label)` |
| `Summary.module.css` | `#201b2b` | `var(--rule)` |
| `EmptyState.module.css` | `#2b2439` | `var(--hairline)` |
| `AllocationForm.module.css` | `#2b2439` (×4) | `var(--hairline)` |
| `AllocationForm.module.css` | `#7d7496` (×2) | `var(--label)` |
| `AllocationForm.module.css` | `#8d84a4` | `var(--text-3)` |
| `SettingsPanel.module.css` | `#7d7496` | `var(--label)` |
| `SettingsPanel.module.css` | `#2b2439` (×2) | `var(--hairline)` |
| `CompletionPopup.module.css` | `#7d7496` | `var(--label)` |

Then give the engaged control its fill. In `Controls.module.css`, the `.engaged` rule becomes:

```css
.engaged {
  border-color: var(--break);
  color: var(--break);
  background: var(--control-engaged);
}
```

- [ ] **Step 5: Run the tests**

Run: `cd frontend && pnpm test`
Expected: PASS, including the new `theme.test.ts`.

- [ ] **Step 6: Confirm nothing moved visually**

Run: `cd frontend && pnpm build && cd .. && node scripts/record-demo.mjs --out /tmp/token-check.gif`
Expected: it writes the GIF and the padding guard stays quiet. Open `/tmp/token-check.gif`; it must look identical to `assets/demo.gif`. This step is a pure-refactor check — every value above was substituted, not changed.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/index.css frontend/src/components/*.css frontend/src/theme.test.ts
git commit -m "Promote the hardcoded colours to tokens

The Break theme is a block of token overrides, which can only reach
declarations that read a token. Twenty-three colours were written
directly into eight component stylesheets, #2b2439 alone in seven
places, and would have rendered a green card with purple-grey buttons,
hints and hairlines.

Every value is unchanged; a test now keeps them in index.css."
```

---

### Task 2: Break recolours the whole card

**Files:**
- Modify: `frontend/src/App.tsx` (the `<main>` in both the error branch and the normal branch)
- Modify: `frontend/src/index.css` (append the override block)
- Test: `tests/test_break_theme.py`

**Interfaces:**
- Consumes: the tokens from Task 1.
- Produces: `data-status` on the card root, carrying `'ACTIVE' | 'BREAK' | 'NEUTRAL'`. Task 6's bar sits inside this element and inherits the override.

- [ ] **Step 1: Write the failing test**

Create `tests/test_break_theme.py`:

```python
"""Break recolours the whole widget, not just the header badge.

The state was legible only by reading a label; a glance at the card said
nothing. This drives the real app into Break and reads the computed
background, because the failure this can ship is a token the override
misses, which no unit test would see.
"""

import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nebula.tracker import Tracker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)

DRIVER = textwrap.dedent(
    """
    import os, time, threading
    from pathlib import Path

    import webview

    from nebula import app as napp
    from nebula.tracker import Tracker

    api = napp.Api(Tracker(Path(os.environ["NEBULA_DATA"])))
    window = webview.create_window(
        "Nebula", url=napp.resolve_url(False), js_api=api,
        width=napp.WINDOW_WIDTH, height=napp.WINDOW_HEIGHT,
        resizable=False, frameless=True, transparent=True, easy_drag=True,
        on_top=True,
    )
    api.bind(window)

    def q(js):
        return window.evaluate_js(js)

    def check():
        for _ in range(100):
            if q("document.documentElement.dataset.nebulaReady === 'true'"):
                break
            time.sleep(0.1)
        else:
            print("FAIL: handshake never completed", flush=True)
            window.destroy()
            return

        q("document.querySelector('[data-break]').click()")
        time.sleep(0.5)

        print("STATUS:" + str(q("document.querySelector('main').dataset.status")), flush=True)
        print("CARD:" + str(q(
            "getComputedStyle(document.querySelector('main')).backgroundColor"
        )), flush=True)
        print("ROW:" + str(q(
            "getComputedStyle(document.querySelector('[data-allocation-name]')"
            ".closest('button')).backgroundColor"
        )), flush=True)
        print("HINT:" + str(q(
            "getComputedStyle(document.querySelector('[data-break]')).borderTopColor"
        )), flush=True)
        window.destroy()

    threading.Thread(target=check, daemon=True).start()
    webview.start()
    """
)


def _line(stdout: str, prefix: str) -> str | None:
    return next(
        (l.removeprefix(prefix) for l in stdout.splitlines() if l.startswith(prefix)),
        None,
    )


@pytest.mark.gui
def test_break_recolours_the_card_and_its_rows(tmp_path):
    assert (PROJECT_ROOT / "dist" / "index.html").exists(), (
        "run 'pnpm build' in frontend/ before this test"
    )

    data = tmp_path / "data.json"
    tracker = Tracker(data)
    tracker.open(NOW)
    view = tracker.add_allocation("Work", 3 * 3600, NOW)
    tracker.activate(view.allocations[0].id, NOW)

    result = subprocess.run(
        [sys.executable, "-c", DRIVER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "NEBULA_DATA": str(data),
        },
    )
    out = result.stdout + result.stderr

    assert _line(result.stdout, "STATUS:") == "BREAK", out
    # #111418, #151a1a: the card and its rows, not just a badge.
    assert _line(result.stdout, "CARD:") == "rgb(17, 20, 24)", out
    assert _line(result.stdout, "ROW:") == "rgb(21, 26, 26)", out
    # The engaged BREAK button keeps the green it already had.
    assert _line(result.stdout, "HINT:") == "rgb(127, 227, 184)", out
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm build && cd .. && uv run pytest tests/test_break_theme.py -v`
Expected: FAIL. `STATUS:` is `None` — the attribute does not exist yet.

- [ ] **Step 3: Put the status on the card root**

In `frontend/src/App.tsx`, the normal-branch `<main>` becomes:

```tsx
    <main
      className={styles.card}
      data-status={ticked === null ? undefined : ticked.status}
    >
```

Leave the error-branch `<main>` alone: it renders before any view exists, so it has no status to report.

- [ ] **Step 4: Add the override block**

Append to `frontend/src/index.css`, after the `:root` block:

```css
/* Break recolours the whole widget rather than flagging itself with a badge.
   Every component reads the palette through custom properties, so the state is
   a different set of values, not a different set of rules -- and the overlays
   (Settings, the form, the recap) are inside the card, so they cannot end up
   half-purple.

   The card, rows, borders, track and stale fill are sampled from the mock. The
   remaining greens are hue-matched to them: the mock has no Settings panel or
   form in Break to sample. */
[data-status='BREAK'] {
  --card: #111418;
  --card-border: #212a2a;
  --row-active: #151a1a;
  --row-active-border: #212a29;
  --row-stale: #151a1a;
  --row-stale-border: #212a29;
  --text: #e1e9e4;
  --text-2: #58625d;
  --text-strong: #c9d3ce;
  --text-3: #7d968a;
  --muted: #58625d;
  --dim: #4a5d54;
  --accent: var(--break);
  --track: #212a29;
  --fill-stale: #627972;
  --hairline: #23302b;
  --label: #6f8579;
  --hint: #3c4a44;
  --target: #58625d;
  --badge-border: #2a3a33;
  --badge-text: #7d968a;
  --rule: #1b2422;
  --control-engaged: #18221f;
}
```

- [ ] **Step 5: Run the test**

Run: `cd frontend && pnpm build && cd .. && uv run pytest tests/test_break_theme.py -v`
Expected: PASS.

- [ ] **Step 6: Look at it**

Run: `cd frontend && pnpm dev` in one terminal, `uv run nebula --dev` in another. Add an allocation, start it, press `BREAK`.
Expected: card, rows, borders, buttons, hints and the summary rule all green. Nothing purple survives. Press `BREAK` again and everything returns.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/index.css tests/test_break_theme.py
git commit -m "Turn the whole widget green on Break

Break was legible only by reading the header badge. It now recolours the
card, its rows, the controls and the hints, so the state reads at a
glance from across the room.

One override block keyed off data-status on the card root -- the
overlays are inside it, so Settings and the recap cannot end up
half-purple. Button placement is unchanged."
```

---

### Task 3: The minimized bar's view model

**Files:**
- Create: `frontend/src/minimized.ts`
- Test: `frontend/src/minimized.test.ts`

**Interfaces:**
- Consumes: `DashboardView` from `./types`, `formatDuration` and `formatPercent` from `./format`, `breakSeconds` from `./tick`.
- Produces: `export type Tone = 'active' | 'break' | 'over' | 'idle'`, `export interface MinimizedView { tone: Tone; title: string; subtitle: string; barPercent: number; dayFigures: string }`, and `export function minimizedView(view: DashboardView, nowMs: number): MinimizedView`. Task 4 renders exactly these five fields.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/minimized.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { minimizedView } from './minimized'
import type { AllocationView, DashboardView } from './types'

const NOW = Date.parse('2026-09-09T10:00:00Z')

function allocation(over: Partial<AllocationView> = {}): AllocationView {
  return {
    id: 'a1',
    name: 'Work',
    dailyTargetSeconds: 10800,
    trackedSeconds: 8640,
    state: 'ACTIVE',
    percentage: 80,
    remainingSeconds: 2160,
    activeSince: '2026-09-09T08:00:00Z',
    daysTracked: 3,
    notifiedMilestones: [],
    ...over,
  }
}

function view(over: Partial<DashboardView> = {}): DashboardView {
  return {
    status: 'ACTIVE',
    dayAnchor: '2026-09-09',
    dayEndDate: '2026-09-10',
    allocations: [allocation()],
    totalTrackedSeconds: 15000,
    totalTargetSeconds: 25200,
    breakStartedAt: null,
    userName: null,
    ...over,
  }
}

describe('the minimized bar', () => {
  it('names the Active allocation and its figures', () => {
    const bar = minimizedView(view(), NOW)
    expect(bar.tone).toBe('active')
    expect(bar.title).toBe('Work')
    expect(bar.subtitle).toBe('2h 24m / 3h · 80%')
    expect(bar.barPercent).toBe(80)
  })

  it('always reports the day as a whole', () => {
    expect(minimizedView(view(), NOW).dayFigures).toBe('4h 10m / 7h · 60%')
  })

  it('counts the break rather than an allocation', () => {
    const bar = minimizedView(
      view({
        status: 'BREAK',
        breakStartedAt: '2026-09-09T09:48:00Z',
        allocations: [allocation({ state: 'STALE', activeSince: null })],
      }),
      NOW,
    )
    expect(bar.tone).toBe('break')
    expect(bar.title).toBe('On break · 12m')
    expect(bar.subtitle).toBe('nothing accumulating')
  })

  it('turns over-allocation amber and keeps the bar inside the track', () => {
    const bar = minimizedView(
      view({
        allocations: [
          allocation({ trackedSeconds: 13500, percentage: 125, remainingSeconds: -2700 }),
        ],
      }),
      NOW,
    )
    expect(bar.tone).toBe('over')
    expect(bar.subtitle).toBe('3h 45m / 3h · 125%')
    // The percentage is honest; the bar is clamped, as the full card does.
    expect(bar.barPercent).toBe(100)
  })

  it('says so when nothing is being tracked', () => {
    const bar = minimizedView(
      view({
        status: 'NEUTRAL',
        allocations: [allocation({ state: 'STALE', activeSince: null })],
      }),
      NOW,
    )
    expect(bar.tone).toBe('idle')
    expect(bar.title).toBe('Nothing tracking')
    expect(bar.subtitle).toBe('')
  })

  it('still reports the day on an empty one', () => {
    const bar = minimizedView(
      view({ status: 'NEUTRAL', allocations: [], totalTrackedSeconds: 0, totalTargetSeconds: 0 }),
      NOW,
    )
    expect(bar.tone).toBe('idle')
    expect(bar.dayFigures).toBe('0m / 0m · 0%')
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm exec vitest run src/minimized.test.ts`
Expected: FAIL — `Failed to resolve import "./minimized"`.

- [ ] **Step 3: Write the module**

Create `frontend/src/minimized.ts`:

```ts
import { formatDuration, formatPercent } from './format'
import { breakSeconds } from './tick'
import type { DashboardView } from './types'

/** Which of the palette's roles the bar wears: dot, figures and bar fill. */
export type Tone = 'active' | 'break' | 'over' | 'idle'

export interface MinimizedView {
  tone: Tone
  title: string
  subtitle: string
  /** Clamped to the track, like the full card's row (PRD §8). */
  barPercent: number
  /** The day as a whole, shown in every state. */
  dayFigures: string
}

const figures = (tracked: number, target: number, percentage: number): string =>
  `${formatDuration(tracked)} / ${formatDuration(target)} · ${formatPercent(percentage)}`

/**
 * The bar's contents, derived rather than rendered.
 *
 * A component would hide this branching from vitest -- the repo tests modules,
 * not components -- and the four states are the whole feature.
 */
export function minimizedView(view: DashboardView, nowMs: number): MinimizedView {
  const dayPercentage =
    view.totalTargetSeconds > 0
      ? (view.totalTrackedSeconds / view.totalTargetSeconds) * 100
      : 0
  const dayFigures = figures(
    view.totalTrackedSeconds,
    view.totalTargetSeconds,
    dayPercentage,
  )

  const onBreak = breakSeconds(view, nowMs)
  if (onBreak !== null) {
    return {
      tone: 'break',
      title: `On break · ${formatDuration(onBreak)}`,
      subtitle: 'nothing accumulating',
      barPercent: Math.min(100, dayPercentage),
      dayFigures,
    }
  }

  const active = view.allocations.find((allocation) => allocation.state === 'ACTIVE')
  if (active === undefined) {
    // A day not yet started, or one already completed. It still has totals, so
    // the bar says something true rather than disabling the control.
    return {
      tone: 'idle',
      title: 'Nothing tracking',
      subtitle: '',
      barPercent: Math.min(100, dayPercentage),
      dayFigures,
    }
  }

  return {
    tone: active.percentage > 100 ? 'over' : 'active',
    title: active.name,
    subtitle: figures(
      active.trackedSeconds,
      active.dailyTargetSeconds,
      active.percentage,
    ),
    barPercent: Math.min(100, Math.max(0, active.percentage)),
    dayFigures,
  }
}
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && pnpm exec vitest run src/minimized.test.ts`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/minimized.ts frontend/src/minimized.test.ts
git commit -m "Derive the minimized bar's contents

Four states -- active, break, over allocation, idle -- and the day's
totals in all of them. A component would put this branching where vitest
cannot reach it; the repo tests modules, not components, and the
branching is the whole feature."
```

---

### Task 4: The MinimizedCard component

**Files:**
- Create: `frontend/src/components/MinimizedCard.tsx`
- Create: `frontend/src/components/MinimizedCard.module.css`

**Interfaces:**
- Consumes: `minimizedView`, `MinimizedView` and `Tone` from `../minimized`.
- Produces: `export function MinimizedCard(props: { view: DashboardView; nowMs: number; onToggleBreak: () => void; onComplete: () => void; onExpand: () => void })`. Task 6 renders it.

- [ ] **Step 1: Write the component**

Create `frontend/src/components/MinimizedCard.tsx`:

```tsx
import { minimizedView } from '../minimized'
import type { DashboardView } from '../types'
import styles from './MinimizedCard.module.css'

interface Props {
  view: DashboardView
  nowMs: number
  onToggleBreak: () => void
  onComplete: () => void
  onExpand: () => void
}

/* Inline, because the app has no icon dependency and this is not the change
   that should add one. */
const Pause = () => (
  <svg width="11" height="11" viewBox="0 0 11 11" aria-hidden="true">
    <rect x="1.5" y="1" width="2.8" height="9" rx="1" fill="currentColor" />
    <rect x="6.7" y="1" width="2.8" height="9" rx="1" fill="currentColor" />
  </svg>
)

const Check = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <path
      d="M2 6.2 L4.6 8.8 L10 3.4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const Expand = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <path
      d="M7 1.6h3.4V5 M5 10.4H1.6V7"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

export function MinimizedCard({
  view,
  nowMs,
  onToggleBreak,
  onComplete,
  onExpand,
}: Props) {
  const bar = minimizedView(view, nowMs)

  return (
    <div className={`${styles.bar} ${styles[bar.tone]}`} data-minimized>
      <div className={styles.body}>
        <span className={styles.dot} />
        <div className={styles.text}>
          <span className={styles.title}>{bar.title}</span>
          <span className={styles.subtitle}>{bar.subtitle}</span>
        </div>
      </div>

      <div className={styles.controls}>
        <button
          type="button"
          data-mini-break
          aria-label="Break"
          className={`${styles.control} ${bar.tone === 'break' ? styles.engaged : ''}`}
          onClick={onToggleBreak}
        >
          <Pause />
        </button>
        <button
          type="button"
          data-mini-complete
          aria-label="Complete the day"
          className={`${styles.control} ${bar.tone === 'over' ? styles.urgent : ''}`}
          onClick={onComplete}
        >
          <Check />
        </button>
        <button
          type="button"
          data-expand
          aria-label="Expand"
          className={styles.control}
          onClick={onExpand}
        >
          <Expand />
        </button>
      </div>

      <span className={styles.track}>
        <span className={styles.fill} style={{ width: `${bar.barPercent}%` }} />
      </span>
      <span className={styles.day}>{bar.dayFigures}</span>
    </div>
  )
}
```

- [ ] **Step 2: Write the stylesheet**

Create `frontend/src/components/MinimizedCard.module.css`:

```css
/* 320 x 86 (MINI_CARD_HEIGHT in app.py). Two columns -- what is being tracked,
   and the day plus its controls -- over a bar that spans the card. */
.bar {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  align-items: center;
  gap: 10px 12px;
  height: 100%;
  padding: 14px 14px 13px;
  border-radius: 14px;
  border: 1px solid var(--card-border);
  background: var(--card);
  box-shadow: 0 12px 28px -8px rgb(0 0 0 / 90%);
  color: var(--text);
}

.body {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.dot {
  flex: none;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
}

/* Every tone needs a rule, empty or not: `styles[tone]` is undefined for a
   class CSS Modules never saw, and the bar would render `bar undefined`. */
.active .dot {
  background: var(--accent);
}

.break .dot {
  background: var(--break);
}

.over .dot {
  background: var(--over);
}

.idle .dot {
  background: var(--muted);
}

.text {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.title {
  overflow: hidden;
  font-weight: 500;
  font-size: 13.5px;
  line-height: 1;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: var(--text);
}

.subtitle {
  font-weight: 400;
  font-size: 11px;
  line-height: 1;
  color: var(--text-2);
}

.over .subtitle {
  color: var(--over);
}

.controls {
  display: flex;
  gap: 7px;
}

.control {
  display: flex;
  width: 30px;
  height: 30px;
  align-items: center;
  justify-content: center;
  padding: 0;
  background: transparent;
  border: 1px solid var(--hairline);
  border-radius: 8px;
  color: var(--text-3);
  cursor: pointer;
}

.control:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.engaged {
  border-color: var(--break);
  background: var(--control-engaged);
  color: var(--break);
}

/* Past the target, completing is the action being suggested (PRD §8). */
.urgent {
  border-color: var(--over);
  background: var(--over);
  color: var(--ground);
}

.urgent:hover {
  border-color: var(--over);
  color: var(--ground);
}

.track {
  display: block;
  height: 5px;
  border-radius: 3px;
  background: var(--track);
  overflow: hidden;
}

.fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--accent);
}

.break .fill {
  background: var(--fill-stale);
}

.over .fill {
  background: var(--over);
}

.idle .fill {
  background: var(--fill-stale);
}

.day {
  justify-self: end;
  font-weight: 400;
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
  color: var(--text-2);
}
```

- [ ] **Step 3: Type-check and lint**

Run: `cd frontend && pnpm exec tsc -b && pnpm exec oxlint`
Expected: both clean. Nothing renders the component yet — Task 6 wires it in.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/MinimizedCard.tsx frontend/src/components/MinimizedCard.module.css
git commit -m "Add the minimized bar

Renders the view model from minimized.ts and nothing else: a dot, the
title and figures, three controls, a progress bar and the day's totals
in 320x86. Icons are inline SVG rather than a new dependency.

Not wired in yet."
```

---

### Task 5: Resizing the window from the bridge

**Files:**
- Modify: `src/nebula/app.py:20-26` (constants) and the `Api` class
- Test: `tests/test_minimize_bridge.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `MINI_CARD_HEIGHT = 86`, `WINDOW_MINI_HEIGHT = 150`, and `Api.set_minimized(self, minimized: bool) -> None`. Task 6 calls it as `window.pywebview.api.set_minimized(true)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_minimize_bridge.py`:

```python
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
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_minimize_bridge.py -v`
Expected: FAIL — `AttributeError: module 'nebula.app' has no attribute 'MINI_CARD_HEIGHT'`.

- [ ] **Step 3: Add the constants**

In `src/nebula/app.py`, directly below `WINDOW_HEIGHT`:

```python
# The minimized bar. Only the height changes: the card keeps its width in both
# modes, so nothing reflows across the collapse.
MINI_CARD_HEIGHT = 86
WINDOW_MINI_HEIGHT = MINI_CARD_HEIGHT + SHADOW_PADDING * 2
```

- [ ] **Step 4: Add the method**

In the `Api` class, after `complete_day`:

```python
    def set_minimized(self, minimized: bool) -> None:
        """Collapse the window to the bar, or restore it.

        Resizing from a js_api method is safe; destroying is not (see
        `_bind_close`). pywebview returns a value by evaluating JS in the
        webview, so a method that tears the webview down hangs the bridge
        thread forever -- a resize leaves it alive to answer.

        `resize()` defaults to `FixPoint.NORTH | FixPoint.WEST`, so the card's
        top-left stays put and the window collapses upward from the bottom.
        """
        if self._window is None:
            raise RuntimeError("set_minimized called before the window was bound")
        height = WINDOW_MINI_HEIGHT if minimized else WINDOW_HEIGHT
        self._window.resize(WINDOW_WIDTH, height)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_minimize_bridge.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 6: Commit**

```bash
git add src/nebula/app.py tests/test_minimize_bridge.py
git commit -m "Resize the window for the minimized bar

set_minimized collapses the window to 384x150 and restores it to
384x684. Only the height moves, so nothing reflows across the collapse.

Resizing from a js_api method is safe, unlike destroying: pywebview
returns a value by evaluating JS in the webview, so a method that tears
it down hangs the bridge thread. resize() also defaults to
FixPoint.NORTH | WEST, which pins the card's top-left."
```

---

### Task 6: Wire minimize into the app

**Files:**
- Modify: `frontend/src/bridge.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.module.css`
- Modify: `frontend/src/demo/store.ts`
- Test: `tests/test_minimize.py`

**Interfaces:**
- Consumes: `MinimizedCard` (Task 4), `Api.set_minimized` (Task 5), `data-status` (Task 2).
- Produces: the finished feature. Nothing later depends on it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_minimize.py`:

```python
"""Minimizing collapses the real window, and expanding restores it.

The failure this feature can ship is a resize that works in isolation but
not through the bridge, which the unit tests cannot see.
"""

import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nebula.tracker import Tracker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)

DRIVER = textwrap.dedent(
    """
    import os, time, threading
    from pathlib import Path

    import webview

    from nebula import app as napp
    from nebula.tracker import Tracker

    api = napp.Api(Tracker(Path(os.environ["NEBULA_DATA"])))
    window = webview.create_window(
        "Nebula", url=napp.resolve_url(False), js_api=api,
        width=napp.WINDOW_WIDTH, height=napp.WINDOW_HEIGHT,
        resizable=False, frameless=True, transparent=True, easy_drag=True,
        on_top=True,
    )
    api.bind(window)

    def q(js):
        return window.evaluate_js(js)

    def check():
        for _ in range(100):
            if q("document.documentElement.dataset.nebulaReady === 'true'"):
                break
            time.sleep(0.1)
        else:
            print("FAIL: handshake never completed", flush=True)
            window.destroy()
            return

        q("document.querySelector('[data-minimize]').click()")
        time.sleep(0.8)
        print("BAR:" + str(q("!!document.querySelector('[data-minimized]')")), flush=True)
        print("MINI_H:" + str(q("window.innerHeight")), flush=True)

        q("document.querySelector('[data-expand]').click()")
        time.sleep(0.8)
        print("FULL_H:" + str(q("window.innerHeight")), flush=True)
        print("CARD:" + str(q("!!document.querySelector('[data-complete]')")), flush=True)
        window.destroy()

    threading.Thread(target=check, daemon=True).start()
    webview.start()
    """
)


def _line(stdout: str, prefix: str) -> str | None:
    return next(
        (l.removeprefix(prefix) for l in stdout.splitlines() if l.startswith(prefix)),
        None,
    )


@pytest.mark.gui
def test_minimize_collapses_the_window_and_expand_restores_it(tmp_path):
    assert (PROJECT_ROOT / "dist" / "index.html").exists(), (
        "run 'pnpm build' in frontend/ before this test"
    )

    data = tmp_path / "data.json"
    tracker = Tracker(data)
    tracker.open(NOW)
    view = tracker.add_allocation("Work", 3 * 3600, NOW)
    tracker.activate(view.allocations[0].id, NOW)

    result = subprocess.run(
        [sys.executable, "-c", DRIVER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "NEBULA_DATA": str(data),
        },
    )
    out = result.stdout + result.stderr

    assert _line(result.stdout, "BAR:") == "True", out
    assert _line(result.stdout, "MINI_H:") == "150", out
    assert _line(result.stdout, "FULL_H:") == "684", out
    assert _line(result.stdout, "CARD:") == "True", out
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm build && cd .. && uv run pytest tests/test_minimize.py -v`
Expected: FAIL. The driver throws on `document.querySelector('[data-minimize]').click()` — the button does not exist — and `BAR:` never prints.

- [ ] **Step 3: Add the bridge wrapper**

In `frontend/src/bridge.ts`, add to the `api` interface inside the `declare global` block, after `check_milestones`:

```ts
        set_minimized?: (minimized: boolean) => Promise<void>
```

and export the wrapper beside the others:

```ts
export const setMinimized = (minimized: boolean): Promise<void> =>
  api().set_minimized!(minimized)
```

- [ ] **Step 4: Give the demo's fake bridge the method**

In `frontend/src/demo/store.ts`, add to the `api` object, after `check_milestones`:

```ts
  // The recording runs in a browser tab; there is no native window to resize.
  set_minimized: () => Promise.resolve(),
```

Without it the demo throws the moment anything calls `setMinimized`, and the README recording dies with it.

- [ ] **Step 5: Wire the state into App.tsx**

Add the import:

```tsx
import { MinimizedCard } from './components/MinimizedCard'
```

Add the state beside the others:

```tsx
  // Session-only: reopening the app always opens the full card.
  const [minimized, setMinimized] = useState(false)
```

Add the two handlers after `apply`:

```tsx
  // React first, then the window. The window is transparent, so a bar in a
  // full-height window shows nothing in the space it has not given back yet --
  // whereas resizing first would clip the card for a frame.
  const collapse = () => {
    setMinimized(true)
    void bridge.setMinimized(true)
  }

  const expand = () => {
    setMinimized(false)
    void bridge.setMinimized(false)
  }
```

Now three exact edits to the returned tree. The overlays — `SettingsPanel`, `AllocationForm`, `CompletionPopup` — are not touched by any of them: completing from the bar expands first, so the recap always has a full card to render into.

**Edit 1 — the `<main>` tag.** Replace:

```tsx
    <main className={styles.card}>
```

with:

```tsx
    <main
      className={`${styles.card} ${minimized ? styles.collapsed : ''}`}
      data-status={ticked === null ? undefined : ticked.status}
    >
```

(Task 2 already added `data-status`; keep it and add the class.)

**Edit 2 — the chrome.** The close button stays in both modes; the gear and minimize are full-card only. Replace the existing gear button:

```tsx
      <button
        className={styles.gear}
        type="button"
        aria-label="Settings"
        data-gear
        onClick={() => setSettingsOpen(true)}
      >
        &#9881;
      </button>
```

with:

```tsx
      {!minimized && (
        <>
          <button
            className={styles.gear}
            type="button"
            aria-label="Settings"
            data-gear
            onClick={() => setSettingsOpen(true)}
          >
            &#9881;
          </button>
          <button
            className={styles.minimize}
            type="button"
            aria-label="Minimize"
            data-minimize
            onClick={collapse}
          >
            &minus;
          </button>
        </>
      )}
```

**Edit 3 — the body.** Replace the whole existing block:

```tsx
      {ticked !== null && (
        <>
          <Header
            dayAnchor={ticked.dayAnchor}
            breakSeconds={breakSeconds(ticked, nowMs)}
          />
          <Summary
            trackedSeconds={ticked.totalTrackedSeconds}
            targetSeconds={ticked.totalTargetSeconds}
          />
          {ticked.allocations.length === 0 ? (
            <EmptyState onAdd={() => setForm({ editing: null })} />
          ) : (
            <div className={styles.list}>
              {ticked.allocations.map((allocation) => (
                <AllocationRow
                  key={allocation.id}
                  allocation={allocation}
                  onActivate={(id) => apply(bridge.activate(id))}
                />
              ))}
            </div>
          )}
          <Controls
            onBreakNow={ticked.status === 'BREAK'}
            onToggleBreak={() => apply(bridge.toggleBreak())}
            onComplete={() =>
              void bridge
                .completeDay()
                .then((next) => {
                  receive(next)
                  setCompleted(next)
                })
                .catch((reason: Error) => setError(String(reason)))
            }
          />
        </>
      )}
```

with:

```tsx
      {ticked !== null &&
        (minimized ? (
          <MinimizedCard
            view={ticked}
            nowMs={nowMs}
            onToggleBreak={() => apply(bridge.toggleBreak())}
            onComplete={() =>
              void bridge
                .completeDay()
                .then((next) => {
                  receive(next)
                  setCompleted(next)
                  // The recap does not fit in 86px, and it is the payoff for
                  // ending the day rather than a detail to find later.
                  expand()
                })
                .catch((reason: Error) => setError(String(reason)))
            }
            onExpand={expand}
          />
        ) : (
          <>
            <Header
              dayAnchor={ticked.dayAnchor}
              breakSeconds={breakSeconds(ticked, nowMs)}
            />
            <Summary
              trackedSeconds={ticked.totalTrackedSeconds}
              targetSeconds={ticked.totalTargetSeconds}
            />
            {ticked.allocations.length === 0 ? (
              <EmptyState onAdd={() => setForm({ editing: null })} />
            ) : (
              <div className={styles.list}>
                {ticked.allocations.map((allocation) => (
                  <AllocationRow
                    key={allocation.id}
                    allocation={allocation}
                    onActivate={(id) => apply(bridge.activate(id))}
                  />
                ))}
              </div>
            )}
            <Controls
              onBreakNow={ticked.status === 'BREAK'}
              onToggleBreak={() => apply(bridge.toggleBreak())}
              onComplete={() =>
                void bridge
                  .completeDay()
                  .then((next) => {
                    receive(next)
                    setCompleted(next)
                  })
                  .catch((reason: Error) => setError(String(reason)))
              }
            />
          </>
        ))}
```

- [ ] **Step 6: Style the minimize button and the collapsed card**

In `frontend/src/App.module.css`, add after `.gear:hover`:

```css
/* Top-left, on the line the gear and close sit on at top-right. Window chrome,
   so it costs no vertical space in a card that already scrolls. */
.minimize {
  position: absolute;
  top: 12px;
  left: 12px;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgb(255 255 255 / 8%);
  color: var(--muted);
  font-size: 17px;
  line-height: 1;
  cursor: pointer;
}

.minimize:hover {
  background: rgb(255 255 255 / 16%);
  color: var(--text);
}
```

The collapsed card must drop the full card's padding, border and background, since the bar draws its own. Edit 1 in Step 5 already applies this class; here it gets its rule:

```css
/* The bar draws its own border, background and padding, so the card element
   becomes a bare container for it. */
.collapsed {
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
  gap: 0;
}
```

The close button is absolutely positioned against `.card`, so it stays reachable at the bar's top-right corner.

- [ ] **Step 7: Run everything**

Run: `cd frontend && pnpm exec tsc -b && pnpm exec oxlint && pnpm test && pnpm build && cd .. && uv run pytest tests/test_minimize.py tests/test_break_theme.py -v`
Expected: all pass. `MINI_H:` is `150`, `FULL_H:` is `684`.

- [ ] **Step 8: Look at it**

Run `cd frontend && pnpm dev` and `uv run nebula --dev`. Add two allocations, start one, minimize.
Expected: the window collapses to the bar with its top-left pinned; the dot is lilac; pause turns the bar green and reads `On break · 0m`; expanding restores the full card. Take an allocation past its target and confirm the ✓ fills amber.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.module.css frontend/src/bridge.ts frontend/src/demo/store.ts tests/test_minimize.py
git commit -m "Minimize the widget to a bar

A minimize button top-left collapses the card to 320x86 carrying the
Active allocation, the day's totals, and pause, complete and expand.

React swaps first and the window resizes second: the window is
transparent, so a bar in a full-height window shows nothing in the space
it has not given back, where resizing first would clip the card for a
frame. Completing from the bar expands, because the recap cannot fit in
86px and missing it is worse than a window that grows.

The demo's fake bridge grows set_minimized too, or the README recording
dies on a missing method."
```

---

### Task 7: Documentation and the recording

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `assets/demo.gif` (regenerated)

- [ ] **Step 1: Add the phase to the roadmap**

In `docs/ROADMAP.md`, add a row to the Status table after phase 4:

```markdown
| 5 | Break theme and minimize | **Done** |
```

And a section after `## Phase 4 — Packaging and distribution · Done`:

```markdown
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
```

- [ ] **Step 2: Re-record the demo**

Run: `cd frontend && pnpm build && cd .. && node scripts/record-demo.mjs`
Expected: writes `assets/demo.gif` with the padding guard quiet. The recording's break beat now shows the green card, which is the point of re-running it.

- [ ] **Step 3: Check the recording**

Open `assets/demo.gif`. The break beat must show a fully green card, and the file should stay near 1.7MB. The beat sheet is unchanged, so the length is still 15.0s.

- [ ] **Step 4: Full verification**

Run: `cd frontend && pnpm exec tsc -b && pnpm exec oxlint && pnpm test && cd .. && uv run pytest -m "not slow"`
Expected: all pass, including the two new GUI tests. This is the run that opens real windows; it is the one to do before merging.

- [ ] **Step 5: Commit**

```bash
git add docs/ROADMAP.md assets/demo.gif
git commit -m "Record phase 5 and re-shoot the demo

The recording's break beat showed the old grey card, which the theme
change makes wrong. The beat sheet is unchanged."
```

---

## Done

Squash-merge to `main`:

```bash
git checkout main
git merge --squash feat-break-and-minimize
git commit
```
