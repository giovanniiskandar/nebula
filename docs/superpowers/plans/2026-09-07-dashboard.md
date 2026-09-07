# Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace "Hello world" with the real widget — allocations, progress, activity states, Break, Complete and the day recap — driven by `tracker.py`.

**Architecture:** `Api` gains bridge methods that each return the whole `DashboardView` as a dict; React renders what it is handed and never keeps a second copy of the truth. Real time enters the program in `Api`, preserving 3a's property that rules take `now` as an argument. React ticks locally once a second for the one Active allocation and the Break badge.

**Tech Stack:** Python 3.13, pywebview 6.2.1, React 19, TypeScript, CSS Modules, Vite, vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-dashboard-design.md`

## Global Constraints

- Node `>=24 <25`. Every frontend command must be preceded by
  `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use`.
- Visible card is **320 × 520**; window is **384 × 584**; `SHADOW_PADDING = 32`,
  which must equal the `body` padding in `frontend/src/index.css`.
- Card shadow is `0 12px 28px -8px rgba(0,0,0,.9)` — tightened from the mock so
  it fits the 32px margin.
- Font is JetBrains Mono, **bundled** via `@fontsource`, never a CDN. Weights
  400, 500, 700.
- Palette (CSS custom properties on `:root`):
  `--ground #0b0910`, `--card #131019`, `--card-border #241f31`,
  `--row-active #1b1626`, `--row-active-border #34294f`,
  `--row-stale #161220`, `--row-stale-border #221d2e`,
  `--text #efeaf7`, `--text-2 #a79dbe`, `--muted #5f5875`, `--dim #4a4460`,
  `--accent #c9b6f5`, `--over #e08a63`, `--break #7fe3b8`, `--track #251f33`.
- No `js_api` method may destroy the window (phase 2 deadlock; see `_bind_close`).
- Progress is never capped and tracking is never auto-stopped (PRD §8).
- Out of scope: add/edit/delete allocations, the duration parser, the Name
  field, notifications, `sys._MEIPASS`, the single-instance lock.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/nebula/model.py` | `break_started_at` on `CurrentState`/`DashboardView`; `view_to_dict` |
| `src/nebula/rules.py` | set/clear `break_started_at` in `toggle_break` |
| `src/nebula/app.py` | `Tracker` wiring, bridge methods, window size |
| `frontend/src/types.ts` | TypeScript mirror of the view dicts |
| `frontend/src/bridge.ts` | typed wrappers over `window.pywebview.api` |
| `frontend/src/format.ts` | duration and date formatting |
| `frontend/src/tick.ts` | pure `tickView(view, nowMs)` |
| `frontend/src/App.tsx` | state, tick loop, screen selection |
| `frontend/src/components/*` | Header, Summary, AllocationRow, Controls, CompletionPopup, EmptyState, ErrorState |
| `tests/test_break_timer.py` | `break_started_at` transitions and round-trip |
| `tests/test_bridge.py` | `view_to_dict` shape and `Api` methods |
| `frontend/src/*.test.ts` | `format.ts` and `tick.ts` |

---

### Task 1: `break_started_at` through the data layer

**Files:**
- Modify: `src/nebula/model.py`, `src/nebula/rules.py`
- Test: `tests/test_break_timer.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CurrentState.break_started_at: datetime | None`,
  `DashboardView.break_started_at: str | None` (ISO), serialised as
  `breakStartedAt`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_break_timer.py`:

```python
"""break_started_at: the mock's ON BREAK timer needs a real start time."""

from datetime import datetime, timedelta, timezone

from nebula import model, rules

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _data() -> model.AppData:
    data = model.empty_data(NOW)
    return rules.add_allocation(data, "Work", 3 * 3600, NOW, "alloc-1")


def test_entering_break_records_when_it_started():
    data = rules.toggle_break(_data(), NOW, "sess-1")
    assert data.current.status == "BREAK"
    assert data.current.break_started_at == NOW


def test_leaving_break_clears_the_start_time():
    data = rules.toggle_break(_data(), NOW, "sess-1")
    later = NOW + timedelta(minutes=12)
    data = rules.toggle_break(data, later, "sess-2")
    assert data.current.break_started_at is None


def test_break_from_neutral_still_records_a_start_time():
    """PRD §6.4: Break entered with nothing active still shows a timer."""
    data = rules.toggle_break(_data(), NOW, "sess-1")
    assert data.current.active_allocation_id is None
    assert data.current.break_started_at == NOW


def test_dashboard_exposes_the_break_start_as_iso():
    data = rules.toggle_break(_data(), NOW, "sess-1")
    view = rules.build_dashboard(data, NOW)
    assert view.break_started_at == NOW.isoformat()


def test_dashboard_break_start_is_none_when_not_on_break():
    view = rules.build_dashboard(_data(), NOW)
    assert view.break_started_at is None


def test_break_start_round_trips_through_json():
    data = rules.toggle_break(_data(), NOW, "sess-1")
    restored = model.from_dict(model.to_dict(data))
    assert restored.current.break_started_at == NOW


def test_data_files_written_before_this_field_still_load():
    """Existing data.json has no breakStartedAt key."""
    raw = model.to_dict(_data())
    del raw["current"]["breakStartedAt"]
    restored = model.from_dict(raw)
    assert restored.current.break_started_at is None
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_break_timer.py -v
```

Expected: FAIL — `TypeError: CurrentState.__init__() got an unexpected keyword argument` or `AttributeError: 'CurrentState' object has no attribute 'break_started_at'`.

- [ ] **Step 3: Add the field to the model**

In `src/nebula/model.py`, add to `CurrentState`:

```python
@dataclass(frozen=True)
class CurrentState:
    status: Status
    day_anchor: date
    active_allocation_id: str | None = None
    pre_break_allocation_id: str | None = None
    break_started_at: datetime | None = None
```

Add to `DashboardView`:

```python
@dataclass(frozen=True)
class DashboardView:
    status: Status
    day_anchor: str
    day_end_date: str
    allocations: tuple[AllocationView, ...]
    total_tracked_seconds: int
    total_target_seconds: int
    break_started_at: str | None = None
```

In `to_dict`, add to the `"current"` dict:

```python
            "breakStartedAt": _dt(data.current.break_started_at),
```

In `from_dict`, read it with `.get()` — data files written before this field
have no such key, and direct indexing would raise `KeyError`:

```python
            break_started_at=_parse_dt(current.get("breakStartedAt")),
```

- [ ] **Step 4: Set and clear it in the Break rule**

In `src/nebula/rules.py`, `toggle_break` currently leaves the field untouched in
all three branches. Set it entering Break and clear it on both exits:

```python
def toggle_break(data: AppData, now: datetime, session_id: str) -> AppData:
    """Break is a pause/resume toggle, not a deselect (PRD §6.4)."""
    if data.current.status == "BREAK":
        resuming = data.current.pre_break_allocation_id
        if resuming is None:
            return model.replace(
                data,
                current=model.replace(
                    data.current,
                    status="NEUTRAL",
                    pre_break_allocation_id=None,
                    break_started_at=None,
                ),
            )
        return activate(data, resuming, now, session_id)

    paused = data.current.active_allocation_id
    data = end_open_sessions(data, now)
    return model.replace(
        data,
        current=model.replace(
            data.current,
            status="BREAK",
            active_allocation_id=None,
            pre_break_allocation_id=paused,
            break_started_at=now,
        ),
    )
```

`activate` also has to clear it, since resuming from Break goes through that
path. In `rules.activate`, include `break_started_at=None` in the
`model.replace(data.current, ...)` call that sets `status="ACTIVE"`.

- [ ] **Step 5: Expose it on the dashboard**

In `rules.build_dashboard`, add the field:

```python
    return DashboardView(
        status=data.current.status,
        day_anchor=data.current.day_anchor.isoformat(),
        day_end_date=day_end_date(data, data.current.day_anchor).isoformat(),
        allocations=views,
        total_tracked_seconds=sum(v.tracked_seconds for v in views),
        total_target_seconds=sum(v.daily_target_seconds for v in views),
        break_started_at=(
            data.current.break_started_at.isoformat()
            if data.current.break_started_at is not None
            else None
        ),
    )
```

- [ ] **Step 6: Run the new tests**

```bash
uv run pytest tests/test_break_timer.py -v
```

Expected: 7 passed.

- [ ] **Step 7: Run the whole suite**

```bash
uv run pytest -q
```

Expected: all pass. If an existing test constructs `CurrentState` positionally
and now breaks, fix the call rather than reordering the dataclass fields.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Record when a Break started

The mock shows a running ON BREAK timer, and nothing in the data said
when the break began. Deriving it from the last session's ended_at was
rejected: it shows nothing when Break is entered from Neutral, where no
session exists.

from_dict reads the key with .get() so data files written before this
field still load."
```

---

### Task 2: The bridge

**Files:**
- Modify: `src/nebula/model.py`, `src/nebula/app.py`
- Test: `tests/test_bridge.py`

**Interfaces:**
- Consumes: `DashboardView` with `break_started_at` from Task 1.
- Produces: `model.view_to_dict(view) -> dict`; `Api.ui_ready() -> dict`,
  `Api.resume() -> dict`, `Api.activate(allocation_id: str) -> dict`,
  `Api.toggle_break() -> dict`, `Api.complete_day() -> dict`. Keys are
  camelCase: `status`, `dayAnchor`, `dayEndDate`, `allocations`,
  `totalTrackedSeconds`, `totalTargetSeconds`, `breakStartedAt`; each
  allocation has `id`, `name`, `dailyTargetSeconds`, `trackedSeconds`,
  `state`, `percentage`, `remainingSeconds`, `activeSince`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bridge.py`:

```python
"""Serialising the dashboard, and the methods the frontend calls."""

from datetime import datetime, timezone

from nebula import app as nebula_app
from nebula import model, rules
from nebula.tracker import Tracker

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _view() -> model.DashboardView:
    data = model.empty_data(NOW)
    data = rules.add_allocation(data, "Work", 3 * 3600, NOW, "alloc-1")
    return rules.build_dashboard(data, NOW)


def test_view_to_dict_uses_camel_case_keys():
    payload = model.view_to_dict(_view())
    assert set(payload) == {
        "status",
        "dayAnchor",
        "dayEndDate",
        "allocations",
        "totalTrackedSeconds",
        "totalTargetSeconds",
        "breakStartedAt",
    }


def test_view_to_dict_serialises_an_allocation():
    payload = model.view_to_dict(_view())
    allocation = payload["allocations"][0]
    assert allocation == {
        "id": "alloc-1",
        "name": "Work",
        "dailyTargetSeconds": 10800,
        "trackedSeconds": 0,
        "state": "NOT_STARTED",
        "percentage": 0.0,
        "remainingSeconds": 10800,
        "activeSince": None,
    }


def test_view_to_dict_is_json_serialisable():
    """js_api return values cross the bridge as JSON."""
    import json

    json.dumps(model.view_to_dict(_view()))


def test_activate_returns_the_updated_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    api.tracker.add_allocation("Work", 3600, NOW)
    # Tracker generates the id, so read it back rather than inventing one.
    created = model.view_to_dict(api.tracker.view(NOW))["allocations"][0]
    payload = api.activate(created["id"])
    assert payload["allocations"][0]["state"] == "ACTIVE"
    assert payload["status"] == "ACTIVE"


def test_toggle_break_returns_a_break_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    api.tracker.add_allocation("Work", 3600, NOW)
    payload = api.toggle_break()
    assert payload["status"] == "BREAK"
    assert payload["breakStartedAt"] is not None


def test_complete_day_returns_a_neutral_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    api.tracker.add_allocation("Work", 3600, NOW)
    payload = api.complete_day()
    assert payload["status"] == "NEUTRAL"


def test_resume_returns_a_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    payload = api.resume()
    assert payload["status"] == "NEUTRAL"
    assert payload["allocations"] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_bridge.py -v
```

Expected: FAIL — `AttributeError: module 'nebula.model' has no attribute 'view_to_dict'`.

- [ ] **Step 3: Write the serialiser**

In `src/nebula/model.py`, beside `to_dict`:

```python
def view_to_dict(view: DashboardView) -> dict[str, Any]:
    """The dashboard as JSON for the frontend.

    camelCase to match `to_dict` and ordinary JavaScript naming. Kept here
    rather than in `app.py` so the window shell stays about windows.
    """
    return {
        "status": view.status,
        "dayAnchor": view.day_anchor,
        "dayEndDate": view.day_end_date,
        "breakStartedAt": view.break_started_at,
        "totalTrackedSeconds": view.total_tracked_seconds,
        "totalTargetSeconds": view.total_target_seconds,
        "allocations": [
            {
                "id": a.id,
                "name": a.name,
                "dailyTargetSeconds": a.daily_target_seconds,
                "trackedSeconds": a.tracked_seconds,
                "state": a.state,
                "percentage": a.percentage,
                "remainingSeconds": a.remaining_seconds,
                "activeSince": a.active_since,
            }
            for a in view.allocations
        ],
    }
```

Add `"view_to_dict"` to `__all__`.

- [ ] **Step 4: Give `Api` a tracker and the bridge methods**

In `src/nebula/app.py`, add the imports:

```python
from datetime import datetime

from nebula import model, store
from nebula.tracker import Tracker
```

Replace the `Api` class:

```python
class Api:
    """Methods exposed to the page as `window.pywebview.api.*`.

    No method here may destroy the window; see `_bind_close` for why. That is
    also what makes raising safe: pywebview catches an exception from a
    `js_api` method and rejects the JavaScript promise with its message, so a
    corrupt data file reaches the UI as an error state rather than a blank card.

    This is where real time enters the program. The data layer takes `now` as
    an argument so its rules can be tested against real timestamps; `Api` is
    the only new place that reads a clock.
    """

    def __init__(self, tracker: Tracker) -> None:
        self.tracker = tracker
        self._window: webview.Window | None = None

    def bind(self, window: webview.Window) -> None:
        self._window = window

    @staticmethod
    def _now() -> datetime:
        return datetime.now().astimezone()

    def ui_ready(self) -> dict:
        """Called by the frontend once React has mounted.

        `window.events.loaded` is too early: the DOM is only `<div id="root">`
        at that point, so the close button does not exist yet.

        Opening the app is a resume point (PRD §17), so this performs the date
        check and recovers a session left open by a crash, then hands back the
        first view — one call rather than two.
        """
        if self._window is None:
            raise RuntimeError("ui_ready called before the window was bound")
        _bind_close(self._window)
        return model.view_to_dict(self.tracker.open(self._now()))

    def resume(self) -> dict:
        """The Start control after a completed day (PRD §18.3)."""
        return model.view_to_dict(self.tracker.open(self._now()))

    def activate(self, allocation_id: str) -> dict:
        """PRD §10.3, §10.4 — no confirmation, exits Break."""
        return model.view_to_dict(
            self.tracker.activate(allocation_id, self._now())
        )

    def toggle_break(self) -> dict:
        """PRD §6.4 — a pause/resume toggle, not a deselect."""
        return model.view_to_dict(self.tracker.toggle_break(self._now()))

    def complete_day(self) -> dict:
        """PRD §10.6 — the only way a day ends."""
        return model.view_to_dict(self.tracker.complete_day(self._now()))
```

- [ ] **Step 5: Construct the tracker in `create_window`**

`--dev` must write `data.dev.json` so development cannot corrupt real history:

```python
def create_window(dev: bool = False) -> webview.Window:
    api = Api(Tracker(store.data_path(dev)))
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

- [ ] **Step 6: Run the tests**

```bash
uv run pytest tests/test_bridge.py -v
```

Expected: 7 passed.

- [ ] **Step 7: Run the whole suite**

```bash
uv run pytest -q
```

Expected: all pass except the GUI close-button test, which is deselected by the
hook but run here. It calls `ui_ready` expecting a bool; it should still pass,
since it only checks that the close button works. If it fails, fix it in Task 7
where the GUI test is extended, not here.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Give the frontend a dashboard to render

Api gains resume, activate, toggle_break and complete_day, each
returning the whole view rather than a delta so React never keeps a
second copy of the truth. ui_ready now returns the first view too: it
is already the 'React has mounted' hook, and opening the app is a
resume point, so first paint needs one call instead of two.

Real time enters here. The data layer keeps taking now as an argument,
which is what lets its rules be tested against real timestamps.

--dev writes data.dev.json, so working on the app cannot corrupt real
tracked history."
```

---

### Task 3: Frontend foundation

**Files:**
- Modify: `src/nebula/app.py`, `frontend/package.json`, `frontend/src/index.css`
- Create: `frontend/src/types.ts`, `frontend/src/format.ts`,
  `frontend/src/format.test.ts`, `frontend/vitest.config.ts`

**Interfaces:**
- Consumes: the camelCase keys from Task 2.
- Produces: `DashboardView` / `AllocationView` TypeScript types;
  `formatDuration(seconds: number): string`,
  `formatLeft(remainingSeconds: number): string`,
  `formatDayLabel(isoDate: string): string`,
  `formatPercent(percentage: number): string`.

- [ ] **Step 1: Resize the window**

In `src/nebula/app.py`:

```python
CARD_WIDTH = 320
CARD_HEIGHT = 520
SHADOW_PADDING = 32  # keep in sync with `body` padding in frontend/src/index.css
```

- [ ] **Step 2: Install the font and vitest**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm add @fontsource/jetbrains-mono
pnpm add -D vitest
```

`@fontsource` is a dependency, not a devDependency: Vite emits the font files
into `dist/`, and a bundled `.app` with no network must still render correctly.

- [ ] **Step 3: Add the test script and vitest config**

Add to `frontend/package.json` scripts:

```json
    "test": "vitest run",
```

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'

// No jsdom: the tested units are pure functions over numbers and strings.
// Components are covered by the GUI test, which drives the real app.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
```

- [ ] **Step 4: Write the design tokens and font**

Replace `frontend/src/index.css`:

```css
@import '@fontsource/jetbrains-mono/400.css';
@import '@fontsource/jetbrains-mono/500.css';
@import '@fontsource/jetbrains-mono/700.css';

/* The native window is frameless and transparent, so the card is the only
   thing the user sees -- its rounded corners and drop shadow stand in for the
   native window frame. */

:root {
  --ground: #0b0910;
  --card: #131019;
  --card-border: #241f31;
  --row-active: #1b1626;
  --row-active-border: #34294f;
  --row-stale: #161220;
  --row-stale-border: #221d2e;
  --text: #efeaf7;
  --text-2: #a79dbe;
  --muted: #5f5875;
  --dim: #4a4460;
  --accent: #c9b6f5;
  --over: #e08a63;
  --break: #7fe3b8;
  --track: #251f33;
}

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
  font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace;
  -webkit-font-smoothing: antialiased;
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
  overflow: hidden;
  /* The window is larger than the card by SHADOW_PADDING on every side (see
     app.py) -- this padding is the transparent margin the shadow casts into. */
  padding: 32px;
}
```

- [ ] **Step 5: Write the view types**

Create `frontend/src/types.ts`:

```ts
export type Status = 'ACTIVE' | 'BREAK' | 'NEUTRAL'
export type AllocationState = 'NOT_STARTED' | 'ACTIVE' | 'STALE'

export interface AllocationView {
  id: string
  name: string
  dailyTargetSeconds: number
  trackedSeconds: number
  state: AllocationState
  percentage: number
  remainingSeconds: number
  /** ISO instant the open session started, or null when not Active. */
  activeSince: string | null
}

export interface DashboardView {
  status: Status
  dayAnchor: string
  dayEndDate: string
  allocations: AllocationView[]
  totalTrackedSeconds: number
  totalTargetSeconds: number
  /** ISO instant the Break began, or null when not on Break. */
  breakStartedAt: string | null
}
```

- [ ] **Step 6: Write the failing formatter tests**

Create `frontend/src/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { formatDayLabel, formatDuration, formatLeft, formatPercent } from './format'

describe('formatDuration', () => {
  it('shows hours and minutes', () => {
    expect(formatDuration(2 * 3600 + 24 * 60)).toBe('2h 24m')
  })

  it('drops the hour part below an hour', () => {
    expect(formatDuration(36 * 60)).toBe('36m')
  })

  it('shows whole hours without minutes', () => {
    expect(formatDuration(3 * 3600)).toBe('3h')
  })

  it('shows zero as 0m', () => {
    expect(formatDuration(0)).toBe('0m')
  })

  it('truncates seconds rather than rounding up', () => {
    expect(formatDuration(59)).toBe('0m')
  })
})

describe('formatLeft', () => {
  it('describes time remaining', () => {
    expect(formatLeft(36 * 60)).toBe('36m left')
  })

  it('describes overage when negative', () => {
    expect(formatLeft(-45 * 60)).toBe('45m over allocation')
  })

  it('treats exactly on target as no time left', () => {
    expect(formatLeft(0)).toBe('0m left')
  })
})

describe('formatPercent', () => {
  it('rounds to a whole number', () => {
    expect(formatPercent(79.6)).toBe('80%')
  })

  it('does not cap above 100', () => {
    expect(formatPercent(125)).toBe('125%')
  })
})

describe('formatDayLabel', () => {
  it('renders the mock format', () => {
    expect(formatDayLabel('2026-08-31')).toBe('MON 31 AUG')
  })
})
```

- [ ] **Step 7: Run them to verify they fail**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm test
```

Expected: FAIL — cannot resolve `./format`.

- [ ] **Step 8: Write the formatters**

Create `frontend/src/format.ts`:

```ts
/** Duration and date formatting. The only real logic in the frontend. */

const HOUR = 3600
const MINUTE = 60

/** `2h 24m`, `36m`, `3h`, `0m`. Seconds are truncated, never rounded up. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(total / HOUR)
  const minutes = Math.floor((total % HOUR) / MINUTE)

  if (hours === 0) return `${minutes}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

/** `36m left`, or `45m over allocation` past the target (PRD §8). */
export function formatLeft(remainingSeconds: number): string {
  if (remainingSeconds < 0) {
    return `${formatDuration(-remainingSeconds)} over allocation`
  }
  return `${formatDuration(remainingSeconds)} left`
}

/** Never capped: going past 100% is the point (PRD §8). */
export function formatPercent(percentage: number): string {
  return `${Math.round(percentage)}%`
}

/** `MON 31 AUG`, from a `YYYY-MM-DD` date. */
export function formatDayLabel(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  // Construct locally: `new Date('2026-08-31')` parses as UTC and can land on
  // the previous day west of Greenwich.
  const date = new Date(year, month - 1, day)
  const weekday = date.toLocaleDateString('en-GB', { weekday: 'short' })
  const monthName = date.toLocaleDateString('en-GB', { month: 'short' })
  return `${weekday} ${day} ${monthName}`.toUpperCase()
}
```

- [ ] **Step 9: Run them to verify they pass**

```bash
pnpm test
```

Expected: 11 passed.

- [ ] **Step 10: Verify the window and font**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
pnpm build
cd .. && uv run nebula
```

Expected: the card is visibly narrower and shorter than before. Confirm the
font files shipped:

```bash
ls dist/assets | grep -i jetbrains | head -3
```

Expected: at least one `.woff2`. If empty, the `@import` lines did not resolve
and the app will silently fall back to Menlo.

Close the window with the `×`.

- [ ] **Step 11: Add vitest to the pre-commit hook**

In `.githooks/pre-commit`, inside the existing `if` that runs when `frontend/`
is touched, after the `pnpm lint` line:

```sh
  (cd frontend && pnpm test)
```

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "Adopt the mock's size and visual language

The card becomes 320x520 in a 384x584 window. The mock's measurements
are drawn against 320 wide; phase 1's 360x560 was picked from options
because this file could not be found at the time.

The mock's shadow paints ~64px below the card and the OS clips anything
outside the window, so containing it exactly would mean a 64px
transparent ring that still swallows clicks. It is tightened to fit a
32px margin instead.

The font is bundled through @fontsource rather than the mock's CDN link:
a packaged .app may have no network, and the link would fall back to
Menlo silently.

vitest arrives with format.ts, which is real logic worth testing."
```

---

### Task 4: Rendering the dashboard

**Files:**
- Create: `frontend/src/bridge.ts`, `frontend/src/components/Header.tsx`,
  `Summary.tsx`, `AllocationRow.tsx`, and their `.module.css`
- Modify: `frontend/src/App.tsx`, `frontend/src/App.module.css`

**Interfaces:**
- Consumes: `DashboardView` from `types.ts`; the formatters from Task 3.
- Produces: `bridge.ts` exporting `uiReady()`, `resume()`, `activate(id)`,
  `toggleBreak()`, `completeDay()`, each `Promise<DashboardView>`.

- [ ] **Step 1: Write the bridge wrapper**

Create `frontend/src/bridge.ts`:

```ts
import type { DashboardView } from './types'

declare global {
  interface Window {
    // Both levels are optional: pywebview creates `window.pywebview` as soon
    // as its own api.js runs, but attaches the api methods later.
    pywebview?: {
      api?: {
        ui_ready?: () => Promise<DashboardView>
        resume?: () => Promise<DashboardView>
        activate?: (allocationId: string) => Promise<DashboardView>
        toggle_break?: () => Promise<DashboardView>
        complete_day?: () => Promise<DashboardView>
      }
    }
  }
}

function api() {
  const bridge = window.pywebview?.api
  if (!bridge) throw new Error('pywebview bridge is not available')
  return bridge
}

export const uiReady = (): Promise<DashboardView> => api().ui_ready!()
export const resume = (): Promise<DashboardView> => api().resume!()
export const activate = (id: string): Promise<DashboardView> =>
  api().activate!(id)
export const toggleBreak = (): Promise<DashboardView> => api().toggle_break!()
export const completeDay = (): Promise<DashboardView> => api().complete_day!()
```

- [ ] **Step 2: Write the Header**

Create `frontend/src/components/Header.tsx`:

```tsx
import { formatDayLabel, formatDuration } from '../format'
import styles from './Header.module.css'

interface Props {
  dayAnchor: string
  breakSeconds: number | null
}

export function Header({ dayAnchor, breakSeconds }: Props) {
  return (
    <header className={styles.header}>
      <span className={styles.today}>TODAY</span>
      {breakSeconds === null ? (
        <span className={styles.date}>{formatDayLabel(dayAnchor)}</span>
      ) : (
        <span className={styles.onBreak}>
          ON BREAK · {formatDuration(breakSeconds)}
        </span>
      )}
    </header>
  )
}
```

Create `frontend/src/components/Header.module.css`:

```css
.header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.today {
  font: 700 10.5px/1 inherit;
  letter-spacing: 0.22em;
  color: #7d7496;
}

.date {
  font: 400 10.5px/1 inherit;
  color: var(--dim);
}

.onBreak {
  font: 700 9px/1 inherit;
  letter-spacing: 0.16em;
  color: var(--ground);
  background: var(--break);
  padding: 4px 6px;
  border-radius: 3px;
}
```

- [ ] **Step 3: Write the Summary**

Create `frontend/src/components/Summary.tsx`:

```tsx
import { formatDuration, formatPercent } from '../format'
import styles from './Summary.module.css'

interface Props {
  trackedSeconds: number
  targetSeconds: number
}

export function Summary({ trackedSeconds, targetSeconds }: Props) {
  const percentage = targetSeconds > 0 ? (trackedSeconds / targetSeconds) * 100 : 0
  return (
    <div className={styles.summary}>
      <div className={styles.figures}>
        <span className={styles.tracked}>{formatDuration(trackedSeconds)}</span>
        <span className={styles.caption}>
          tracked of {formatDuration(targetSeconds)} planned
        </span>
      </div>
      <span className={styles.percent}>{formatPercent(percentage)}</span>
    </div>
  )
}
```

Create `frontend/src/components/Summary.module.css`:

```css
.summary {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid #201b2b;
}

.figures {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.tracked {
  font: 500 28px/1 inherit;
  color: var(--text);
  letter-spacing: -0.01em;
}

.caption {
  font: 400 11px/1 inherit;
  color: var(--muted);
}

.percent {
  font: 500 12px/1 inherit;
  color: var(--accent);
}
```

- [ ] **Step 4: Write the AllocationRow**

Create `frontend/src/components/AllocationRow.tsx`:

```tsx
import { formatDuration, formatLeft, formatPercent } from '../format'
import type { AllocationView } from '../types'
import styles from './AllocationRow.module.css'

const BADGE: Record<AllocationView['state'], string> = {
  ACTIVE: 'ACTIVE',
  STALE: 'STALE',
  NOT_STARTED: 'NOT STARTED',
}

interface Props {
  allocation: AllocationView
  onActivate: (id: string) => void
}

export function AllocationRow({ allocation, onActivate }: Props) {
  const over = allocation.remainingSeconds < 0
  // Never capped past 100% (PRD §8); the bar fills and turns amber instead.
  const width = Math.min(100, Math.max(0, allocation.percentage))

  return (
    <button
      type="button"
      className={`${styles.row} ${styles[allocation.state]} ${over ? styles.over : ''}`}
      onClick={() => onActivate(allocation.id)}
    >
      <span className={styles.line}>
        <span className={styles.name}>{allocation.name}</span>
        <span className={styles.badge}>{BADGE[allocation.state]}</span>
      </span>
      <span className={styles.line}>
        <span className={styles.numbers}>
          {formatDuration(allocation.trackedSeconds)}{' '}
          <span className={styles.target}>
            / {formatDuration(allocation.dailyTargetSeconds)}
          </span>
        </span>
        <span className={styles.percent}>
          {formatPercent(allocation.percentage)}
        </span>
      </span>
      <span className={styles.track}>
        <span className={styles.fill} style={{ width: `${width}%` }} />
      </span>
      <span className={styles.captionLine}>
        <span className={styles.caption}>
          {formatLeft(allocation.remainingSeconds)}
        </span>
        {over && (
          <span className={styles.marker}>
            target {formatDuration(allocation.dailyTargetSeconds)} ↑
          </span>
        )}
      </span>
    </button>
  )
}
```

Create `frontend/src/components/AllocationRow.module.css`:

```css
.row {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 9px;
  width: 100%;
  padding: 12px 13px 13px;
  border-radius: 10px;
  border: 1px solid var(--row-stale-border);
  background: var(--row-stale);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
}

.ACTIVE {
  background: var(--row-active);
  border-color: var(--row-active-border);
}

/* The 2px accent bar down the Active row's left edge. */
.ACTIVE::before {
  content: '';
  position: absolute;
  left: 0;
  top: 13px;
  bottom: 13px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--accent);
}

.line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.name {
  font: 500 13.5px/1 inherit;
  color: var(--text);
}

.NOT_STARTED .name {
  color: #cfc7de;
}

.badge {
  font: 700 9px/1 inherit;
  letter-spacing: 0.16em;
  padding: 3px 6px;
  border-radius: 3px;
  border: 1px solid #322a44;
  color: #7f7699;
}

.ACTIVE .badge {
  color: var(--ground);
  background: var(--accent);
  border-color: var(--accent);
}

.numbers {
  font: 400 11.5px/1 inherit;
  color: var(--text-2);
}

.target {
  color: #5a5372;
}

.percent {
  font: 500 11.5px/1 inherit;
  color: var(--accent);
}

.STALE .percent,
.NOT_STARTED .percent {
  color: #8d84a4;
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

.STALE .fill {
  background: #6a5f88;
}

.caption {
  font: 400 10.5px/1 inherit;
  color: var(--muted);
}

.captionLine {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.marker {
  font: 400 10.5px/1 inherit;
  color: var(--over);
}

.over .fill {
  background: var(--over);
}

.over .percent,
.over .caption {
  color: var(--over);
}
```

- [ ] **Step 5: Rewrite App to render the dashboard**

Replace `frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from 'react'
import styles from './App.module.css'
import { AllocationRow } from './components/AllocationRow'
import { Header } from './components/Header'
import { Summary } from './components/Summary'
import * as bridge from './bridge'
import type { DashboardView } from './types'

export default function App() {
  const [view, setView] = useState<DashboardView | null>(null)

  useEffect(() => {
    // pywebview injects window.pywebview asynchronously and fires
    // `pywebviewready` when it lands. React may mount either side of that,
    // so handle both orders.
    const start = () => {
      void bridge.uiReady().then((next) => {
        setView(next)
        document.documentElement.dataset.nebulaReady = 'true'
      })
    }

    if (window.pywebview?.api?.ui_ready) {
      start()
      return
    }
    window.addEventListener('pywebviewready', start, { once: true })
    return () => window.removeEventListener('pywebviewready', start)
  }, [])

  if (view === null) return <main className={styles.card} />

  return (
    <main className={styles.card}>
      <button className={styles.close} type="button" aria-label="Close" data-close>
        &times;
      </button>
      <Header dayAnchor={view.dayAnchor} breakSeconds={null} />
      <Summary
        trackedSeconds={view.totalTrackedSeconds}
        targetSeconds={view.totalTargetSeconds}
      />
      <div className={styles.list}>
        {view.allocations.map((allocation) => (
          <AllocationRow
            key={allocation.id}
            allocation={allocation}
            onActivate={(id) => void bridge.activate(id).then(setView)}
          />
        ))}
      </div>
    </main>
  )
}
```

- [ ] **Step 6: Restyle the card**

Replace `frontend/src/App.module.css`:

```css
.card {
  position: relative;
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 18px;
  padding: 20px 18px;
  border-radius: 14px;
  border: 1px solid var(--card-border);
  background: var(--card);
  /* Tightened from the mock so it fits SHADOW_PADDING; see app.py. */
  box-shadow: 0 12px 28px -8px rgb(0 0 0 / 90%);
  color: var(--text);
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  color: var(--muted);
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
}

.close:hover {
  background: rgb(255 255 255 / 16%);
  color: var(--text);
}
```

- [ ] **Step 7: Seed data and look at it**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run python -c "
from datetime import datetime
from nebula import store
from nebula.tracker import Tracker
now = datetime.now().astimezone()
t = Tracker(store.data_path(dev=True))
t.add_allocation('Work', 3*3600, now)
t.add_allocation('Learning', 2*3600, now)
t.add_allocation('Entertainment', 2*3600, now)
print('seeded', store.data_path(dev=True))
"
cd frontend && pnpm build && cd ..
uv run nebula --dev
```

`--dev` needs the Vite server; run `pnpm dev` in another terminal first, or drop
`--dev` and seed `store.data_path(dev=False)` instead.

Expected: three rows, all `NOT STARTED`, `0m / 3h`, empty bars. Clicking a row
turns it `ACTIVE` with the accent bar, and clicking another moves the state.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Render the real dashboard

App calls ui_ready on mount and renders whatever view comes back:
header, summary, and a row per allocation with its state badge,
figures, bar and caption. Clicking a row activates it and the returned
view replaces the old one, so the frontend never derives state Python
already computed.

The progress bar clamps its width at 100% while the percentage text
does not: going past the target is the point, and the row turns amber
instead."
```

---

### Task 5: Controls and the Break state

**Files:**
- Create: `frontend/src/components/Controls.tsx`, `Controls.module.css`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `bridge.toggleBreak()`, `bridge.completeDay()`.
- Produces: `Controls` taking `{ onBreak, onComplete, onBreak: boolean }`.

- [ ] **Step 1: Write the Controls**

Create `frontend/src/components/Controls.tsx`:

```tsx
import styles from './Controls.module.css'

interface Props {
  onBreakNow: boolean
  onToggleBreak: () => void
  onComplete: () => void
}

export function Controls({ onBreakNow, onToggleBreak, onComplete }: Props) {
  return (
    <div className={styles.controls}>
      <div className={styles.row}>
        <button
          type="button"
          className={`${styles.button} ${onBreakNow ? styles.engaged : ''}`}
          onClick={onToggleBreak}
        >
          {onBreakNow ? 'ON BREAK' : 'BREAK'}
        </button>
        <button type="button" className={styles.button} onClick={onComplete}>
          COMPLETE
        </button>
      </div>
      <span className={styles.hint}>
        {onBreakNow
          ? 'pick an allocation to resume'
          : 'click any allocation to switch'}
      </span>
    </div>
  )
}
```

Create `frontend/src/components/Controls.module.css`:

```css
.controls {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.row {
  display: flex;
  gap: 9px;
}

.button {
  flex: 1;
  padding: 11px 0;
  background: transparent;
  border: 1px solid #2b2439;
  border-radius: 9px;
  cursor: pointer;
  font: 500 12px/1 inherit;
  letter-spacing: 0.1em;
  color: #8d84a4;
}

.button:hover {
  border-color: var(--break);
  color: var(--break);
}

.engaged {
  border-color: var(--break);
  color: var(--break);
}

.hint {
  text-align: center;
  font: 400 10px/1 inherit;
  color: #3f3a53;
}
```

- [ ] **Step 2: Wire the controls into App**

In `frontend/src/App.tsx`, import `Controls` and render it after the list, and
pass the Break state into `Header`:

```tsx
      <Header
        dayAnchor={view.dayAnchor}
        breakSeconds={view.status === 'BREAK' ? 0 : null}
      />
```

```tsx
      <Controls
        onBreakNow={view.status === 'BREAK'}
        onToggleBreak={() => void bridge.toggleBreak().then(setView)}
        onComplete={() => void bridge.completeDay().then(setView)}
      />
```

The `breakSeconds={0}` is a placeholder until Task 6 ticks it; the badge shows
`ON BREAK · 0m` for now, which is visibly wrong and gets fixed there.

- [ ] **Step 3: Check it by hand**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend && pnpm build && cd ..
uv run nebula
```

Expected: BREAK and COMPLETE side by side above the hint. Activate an
allocation, then press BREAK: every row with time shows `STALE`, the button
reads `ON BREAK` in the break colour, the hint changes, and the header shows the
badge. Press it again and the previous allocation returns to `ACTIVE`.

Press COMPLETE: tracking stops and every row goes `STALE`. The recap popup is
Task 7.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Add the Break and Complete controls

Side by side in one row, both always visible and one click each as
PRD §11 requires. The mock has only a full-width BREAK button and no
Complete at all -- it predates the V1.1 grilling session that added Day
Completion -- so this keeps the mock's rhythm while following the PRD.

Break renders engaged rather than as a separate screen, and the hint
switches to 'pick an allocation to resume'."
```

---

### Task 6: Live ticking

**Files:**
- Create: `frontend/src/tick.ts`, `frontend/src/tick.test.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `DashboardView`.
- Produces: `tickView(view: DashboardView, nowMs: number): DashboardView`, and
  `breakSeconds(view: DashboardView, nowMs: number): number | null`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/tick.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { breakSeconds, tickView } from './tick'
import type { DashboardView } from './types'

const STARTED = '2026-09-07T10:00:00+00:00'
/** When Python built the view: 10 minutes of the open session already counted. */
const FETCHED = Date.parse('2026-09-07T10:10:00+00:00')
const NOW = Date.parse('2026-09-07T10:40:00+00:00')

function view(overrides: Partial<DashboardView> = {}): DashboardView {
  return {
    status: 'ACTIVE',
    dayAnchor: '2026-09-07',
    dayEndDate: '2026-09-07',
    totalTrackedSeconds: 600,
    totalTargetSeconds: 10800,
    breakStartedAt: null,
    allocations: [
      {
        id: 'a',
        name: 'Work',
        dailyTargetSeconds: 10800,
        trackedSeconds: 600,
        state: 'ACTIVE',
        percentage: (600 / 10800) * 100,
        remainingSeconds: 10200,
        activeSince: STARTED,
      },
    ],
    ...overrides,
  }
}

describe('tickView', () => {
  it('advances by time since the view was fetched, not since the session began', () => {
    // trackedSeconds already counts 10:00 to 10:10. Only the 30 minutes since
    // the fetch may be added; measuring from activeSince would give 2400.
    const ticked = tickView(view(), NOW, FETCHED)
    expect(ticked.allocations[0].trackedSeconds).toBe(600 + 1800)
  })

  it('changes nothing when no time has passed', () => {
    expect(tickView(view(), FETCHED, FETCHED)).toEqual(view())
  })

  it('recomputes percentage and remaining from the advanced value', () => {
    const allocation = tickView(view(), NOW, FETCHED).allocations[0]
    expect(allocation.remainingSeconds).toBe(10800 - 2400)
    expect(allocation.percentage).toBeCloseTo((2400 / 10800) * 100)
  })

  it('updates the overall total', () => {
    expect(tickView(view(), NOW, FETCHED).totalTrackedSeconds).toBe(2400)
  })

  it('leaves Stale and Not Started allocations alone', () => {
    const stale = view({
      status: 'NEUTRAL',
      allocations: [
        {
          id: 'b',
          name: 'Learning',
          dailyTargetSeconds: 7200,
          trackedSeconds: 2160,
          state: 'STALE',
          percentage: 30,
          remainingSeconds: 5040,
          activeSince: null,
        },
      ],
    })
    expect(tickView(stale, NOW, FETCHED).allocations[0].trackedSeconds).toBe(2160)
  })

  it('goes past the target rather than capping (PRD §8)', () => {
    const over = view({
      allocations: [
        {
          id: 'a',
          name: 'Work',
          dailyTargetSeconds: 3600,
          trackedSeconds: 3000,
          state: 'ACTIVE',
          percentage: (3000 / 3600) * 100,
          remainingSeconds: 600,
          activeSince: STARTED,
        },
      ],
    })
    const ticked = tickView(over, NOW, FETCHED).allocations[0]
    expect(ticked.percentage).toBeCloseTo((4800 / 3600) * 100)
    expect(ticked.remainingSeconds).toBe(-1200)
  })

  it('is a pure function of its arguments', () => {
    const raw = view()
    expect(tickView(raw, NOW, FETCHED)).toEqual(tickView(raw, NOW, FETCHED))
    expect(raw.allocations[0].trackedSeconds).toBe(600)
  })
})

describe('breakSeconds', () => {
  it('measures from breakStartedAt, which counts nothing beforehand', () => {
    const onBreak = view({ status: 'BREAK', breakStartedAt: STARTED })
    expect(breakSeconds(onBreak, NOW)).toBe(2400)
  })

  it('is null when not on Break', () => {
    expect(breakSeconds(view(), NOW)).toBeNull()
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm test
```

Expected: FAIL — cannot resolve `./tick`.

- [ ] **Step 3: Write the tick**

Create `frontend/src/tick.ts`:

```ts
import type { DashboardView } from './types'

/**
 * The view as of `nowMs`, with the one Active allocation advanced.
 *
 * The advance is `nowMs - fetchedAtMs`, NOT `nowMs - activeSince`.
 * `trackedSeconds` already counts the open session up to the moment Python
 * built the view, so measuring from `activeSince` would count that stretch
 * twice and the figure would jump on every refetch.
 *
 * A pure function of its three arguments, recomputed rather than incremented,
 * so a missed interval cannot drift. The caller must always tick the raw view
 * from the bridge, never a previously ticked one.
 */
export function tickView(
  view: DashboardView,
  nowMs: number,
  fetchedAtMs: number,
): DashboardView {
  const elapsed = Math.max(0, Math.floor((nowMs - fetchedAtMs) / 1000))
  if (elapsed === 0) return view

  let delta = 0
  const allocations = view.allocations.map((allocation) => {
    if (allocation.state !== 'ACTIVE' || allocation.activeSince === null) {
      return allocation
    }
    const tracked = allocation.trackedSeconds + elapsed
    delta += elapsed
    return {
      ...allocation,
      trackedSeconds: tracked,
      remainingSeconds: allocation.dailyTargetSeconds - tracked,
      percentage:
        allocation.dailyTargetSeconds > 0
          ? (tracked / allocation.dailyTargetSeconds) * 100
          : 0,
    }
  })

  return {
    ...view,
    allocations,
    totalTrackedSeconds: view.totalTrackedSeconds + delta,
  }
}

/** Seconds since Break began, or null when not on Break. */
export function breakSeconds(
  view: DashboardView,
  nowMs: number,
): number | null {
  if (view.status !== 'BREAK' || view.breakStartedAt === null) return null
  return Math.max(0, Math.floor((nowMs - Date.parse(view.breakStartedAt)) / 1000))
}
```

- [ ] **Step 4: Run them to verify they pass**

```bash
pnpm test
```

Expected: 20 passed (11 from `format`, 9 here).

- [ ] **Step 5: Drive the tick from App**

In `frontend/src/App.tsx`, add a second effect and derive what is rendered:

```tsx
  const [nowMs, setNowMs] = useState(() => Date.now())
  const [fetchedAtMs, setFetchedAtMs] = useState(() => Date.now())

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
```

Every view that arrives must stamp when it arrived, since the tick advances
from that moment. Replace the bare `setView` used as a promise handler with:

```tsx
  const receive = (next: DashboardView) => {
    setView(next)
    setFetchedAtMs(Date.now())
  }
```

Use `receive` everywhere `setView` was passed to a `.then(...)`.

Then, after the null check:

```tsx
  const ticked = tickView(view, nowMs, fetchedAtMs)
```

Render `ticked` rather than `view` for the header, summary and rows, and pass
`breakSeconds(ticked, nowMs)` to `Header`. Store only the raw view — the tick
is a rendering concern, and ticking an already-ticked view would double count.

- [ ] **Step 6: Watch it tick**

```bash
cd frontend && pnpm build && cd ..
uv run nebula
```

Expected: activate an allocation and its minutes climb once a minute while the
seconds-level percentage moves each second. Press BREAK and the badge counts up.
Leave it a few minutes and confirm the figure matches the wall clock rather than
drifting.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Tick the Active allocation and the Break badge

React recomputes elapsed time from activeSince once a second rather
than incrementing a counter, so a missed interval cannot drift and
re-applying is idempotent. Python and the browser share the machine
clock and both derive from timestamps, so the local tick agrees with
whatever the next bridge call returns.

No polling: nothing else can change the data while the app runs."
```

---

### Task 7: Popup, empty state, error state, and the GUI test

**Files:**
- Create: `frontend/src/components/CompletionPopup.tsx`, `EmptyState.tsx`,
  `ErrorState.tsx` and their `.module.css`
- Modify: `frontend/src/App.tsx`, `tests/test_close_button.py`,
  `README.md`, `docs/ROADMAP.md`
- Test: `tests/test_dashboard_renders.py`

**Interfaces:**
- Consumes: everything above.
- Produces: the finished dashboard.

- [ ] **Step 1: Write the CompletionPopup**

Create `frontend/src/components/CompletionPopup.tsx`:

```tsx
import { formatDuration, formatPercent } from '../format'
import type { DashboardView } from '../types'
import styles from './CompletionPopup.module.css'

interface Props {
  view: DashboardView
  onStart: () => void
}

export function CompletionPopup({ view, onStart }: Props) {
  return (
    <div className={styles.popup}>
      <span className={styles.title}>TODAY&apos;S RESULT</span>
      <div className={styles.rows}>
        {view.allocations.map((allocation) => (
          <div key={allocation.id} className={styles.row}>
            <span className={styles.name}>{allocation.name}</span>
            <span className={styles.figures}>
              {formatDuration(allocation.trackedSeconds)} /{' '}
              {formatDuration(allocation.dailyTargetSeconds)}
            </span>
            <span className={styles.percent}>
              {formatPercent(allocation.percentage)}
            </span>
          </div>
        ))}
      </div>
      {/* PRD §18.2 personalises this with the Name from Settings, which does
          not exist until 3c. The PRD specifies this generic fallback. */}
      <span className={styles.message}>Good work today!</span>
      <button type="button" className={styles.start} onClick={onStart}>
        Start
      </button>
    </div>
  )
}
```

Create `frontend/src/components/CompletionPopup.module.css`:

```css
.popup {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 18px;
  border-radius: 14px;
  background: var(--card);
}

.title {
  font: 700 10.5px/1 inherit;
  letter-spacing: 0.22em;
  color: #7d7496;
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.name {
  flex: 1;
  font: 500 12px/1 inherit;
  color: var(--text);
}

.figures {
  font: 400 11px/1 inherit;
  color: var(--text-2);
}

.percent {
  min-width: 42px;
  text-align: right;
  font: 500 11px/1 inherit;
  color: var(--accent);
}

.message {
  margin-top: auto;
  text-align: center;
  font: 400 12px/1 inherit;
  color: var(--text-2);
}

.start {
  padding: 11px 0;
  background: transparent;
  border: 1px solid var(--accent);
  border-radius: 9px;
  cursor: pointer;
  font: 500 12px/1 inherit;
  letter-spacing: 0.1em;
  color: var(--accent);
}
```

- [ ] **Step 2: Write the EmptyState and ErrorState**

Create `frontend/src/components/EmptyState.tsx`:

```tsx
import styles from './EmptyState.module.css'

export function EmptyState() {
  return (
    <div className={styles.empty}>
      <span className={styles.title}>Plan your day</span>
      <span className={styles.body}>Create your first time allocation.</span>
      {/* Enabled in 3c, which adds allocation management. */}
      <button type="button" className={styles.add} disabled>
        + Add Allocation
      </button>
    </div>
  )
}
```

Create `frontend/src/components/EmptyState.module.css`:

```css
.empty {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.title {
  font: 500 15px/1 inherit;
  color: var(--text);
}

.body {
  font: 400 11px/1 inherit;
  color: var(--muted);
}

.add {
  margin-top: 8px;
  padding: 10px 16px;
  background: transparent;
  border: 1px solid #2b2439;
  border-radius: 9px;
  font: 500 11px/1 inherit;
  letter-spacing: 0.1em;
  color: var(--dim);
  cursor: not-allowed;
}
```

Create `frontend/src/components/ErrorState.tsx`:

```tsx
import styles from './EmptyState.module.css'

export function ErrorState({ message }: { message: string }) {
  return (
    <div className={styles.empty}>
      <span className={styles.title}>Something went wrong</span>
      <span className={styles.body}>{message}</span>
    </div>
  )
}
```

- [ ] **Step 3: Compose them in App**

In `frontend/src/App.tsx`, add state and rendering:

```tsx
  const [error, setError] = useState<string | null>(null)
  const [completed, setCompleted] = useState<DashboardView | null>(null)
```

Give every bridge call a rejection handler, since a `DataFileCorrupt` reaches
the frontend as a rejected promise:

```tsx
  const apply = (next: Promise<DashboardView>) =>
    void next.then(setView).catch((reason: Error) => setError(String(reason)))
```

Use `apply(bridge.activate(id))` and `apply(bridge.toggleBreak())`. Complete
keeps the returned view for the popup:

```tsx
        onComplete={() =>
          void bridge
            .completeDay()
            .then((next) => {
              setView(next)
              setCompleted(next)
            })
            .catch((reason: Error) => setError(String(reason)))
        }
```

Render the branches:

```tsx
  if (error !== null) {
    return (
      <main className={styles.card}>
        <button className={styles.close} type="button" aria-label="Close" data-close>
          &times;
        </button>
        <ErrorState message={error} />
      </main>
    )
  }
```

Inside the card, after the close button:

```tsx
      {completed !== null && (
        <CompletionPopup
          view={completed}
          onStart={() => {
            setCompleted(null)
            apply(bridge.resume())
          }}
        />
      )}
```

And swap the list for the empty state when there is nothing to show:

```tsx
      {ticked.allocations.length === 0 ? (
        <EmptyState />
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
```

- [ ] **Step 4: Write the failing GUI test**

Create `tests/test_dashboard_renders.py`:

```python
"""The dashboard renders real data in the real app.

Driving the built app is what caught the phase 2 bugs that unit tests
passed straight over, so the dashboard gets the same treatment.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DRIVER = textwrap.dedent(
    """
    import json, os, sys, threading, time
    import webview
    from nebula import app as napp
    from nebula.tracker import Tracker
    from pathlib import Path

    api = napp.Api(Tracker(Path(os.environ["NEBULA_DATA"])))
    window = webview.create_window(
        "Nebula", url=napp.resolve_url(False), js_api=api,
        width=napp.WINDOW_WIDTH, height=napp.WINDOW_HEIGHT,
        frameless=True, transparent=True, easy_drag=True, on_top=True,
    )
    api.bind(window)

    def check():
        for _ in range(100):
            if window.evaluate_js(
                "document.documentElement.dataset.nebulaReady === 'true'"
            ):
                break
            time.sleep(0.1)
        else:
            print("FAIL: handshake never completed", flush=True)
            window.destroy()
            return
        names = window.evaluate_js(
            "JSON.stringify(Array.from("
            "document.querySelectorAll('[data-allocation-name]'))"
            ".map(function (n) { return n.textContent; }))"
        )
        print("NAMES:" + names, flush=True)
        window.destroy()

    threading.Thread(target=check, daemon=True).start()
    webview.start()
    """
)


@pytest.mark.gui
def test_dashboard_renders_seeded_allocations(tmp_path):
    assert (PROJECT_ROOT / "dist" / "index.html").exists(), (
        "run 'pnpm build' in frontend/ before this test"
    )

    from datetime import datetime

    from nebula.tracker import Tracker

    data_file = tmp_path / "data.json"
    now = datetime.now().astimezone()
    tracker = Tracker(data_file)
    tracker.add_allocation("Work", 3 * 3600, now)
    tracker.add_allocation("Learning", 2 * 3600, now)

    result = subprocess.run(
        [sys.executable, "-c", DRIVER],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=40,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "NEBULA_DATA": str(data_file),
        },
    )

    line = next(
        (l for l in result.stdout.splitlines() if l.startswith("NAMES:")), None
    )
    assert line is not None, result.stdout + result.stderr
    assert json.loads(line.removeprefix("NAMES:")) == ["Work", "Learning"]
```

- [ ] **Step 5: Add the hook the test selects on**

In `frontend/src/components/AllocationRow.tsx`, mark the name:

```tsx
        <span className={styles.name} data-allocation-name>
          {allocation.name}
        </span>
```

A data attribute, not a class name — CSS Modules rewrites class names into
hashes that Python cannot predict, the phase 2 finding.

- [ ] **Step 6: Run both GUI tests**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm build
cd ..
uv run pytest -m gui -v
```

Expected: 2 passed. If the close-button test fails because `ui_ready` now
returns a dict rather than `True`, fix that test — it should assert the process
exits, not the return value.

- [ ] **Step 7: Run everything**

```bash
uv run pytest -q
cd frontend && pnpm test && pnpm lint && cd ..
```

Expected: all pass.

- [ ] **Step 8: Check the three new screens by hand**

```bash
uv run nebula
```

Press COMPLETE: the recap covers the card with each allocation's figures and
`Good work today!`. Press Start: back to the dashboard.

Then move the data file aside to see the empty state, and corrupt it to see the
error state:

```bash
mv ~/Library/Application\ Support/Nebula/data.json /tmp/nebula-data-backup.json
uv run nebula      # expect: Plan your day, with a disabled button
echo 'not json' > ~/Library/Application\ Support/Nebula/data.json
uv run nebula      # expect: Something went wrong, naming the file
mv /tmp/nebula-data-backup.json ~/Library/Application\ Support/Nebula/data.json
```

- [ ] **Step 9: Update the docs**

In `docs/ROADMAP.md`, move 3b from `Next` to `**Done**` in the status table,
set 3c to `Next`, and replace the "Phase 3b — Dashboard · Next" section heading
with "Phase 3b — Dashboard · Done", adding the spec and plan paths beneath it in
the style of the other done phases.

In `README.md`, add to the Layout block that `frontend/src/components/` holds
the UI and `frontend/src/{format,tick}.ts` the frontend logic, and note under
Tests that `pnpm test` runs vitest.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "Add the completion popup, empty state and error state

The popup is transient React state rather than a persisted flag.
resume() does not clear completions, so a day_completed field would
re-trigger the popup after Start on the same date; PRD §17 says a
same-date resume simply continues the day.

The empty state ships a disabled Add button, since allocation
management is 3c. A corrupt data file now reaches the UI as a named
error rather than a blank card: pywebview rejects the JS promise with
the exception message.

The GUI test seeds a data file and asserts the rendered rows, selecting
on a data attribute because CSS Modules hashes class names."
```

---

## Definition of Done

Verified against spec §12:

1. `uv run nebula` shows the real dashboard — Task 4, Step 7.
2. Clicking an allocation activates it; the previous becomes Stale — Task 4, Step 7.
3. The Active allocation ticks once a second without drift — Task 6, Step 6.
4. Break pauses, shows the ticking badge, and toggles back — Tasks 5 and 6.
5. Complete shows the recap; Start returns to the dashboard — Task 7, Step 8.
6. Past 100% the row goes amber and keeps counting — Task 4, Step 4 and Task 6, Step 1.
7. The empty state renders with no allocations — Task 7, Step 8.
8. The card is 320 × 520 in a 384 × 584 window — Task 3, Steps 1 and 10.
9. The font renders from bundled files — Task 3, Step 10.
10. Both suites pass — Task 7, Step 7.
