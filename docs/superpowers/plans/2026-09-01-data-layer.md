# Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the headless tracking core — allocations, sessions, persistence, and every rule that turns stored timestamps into what the dashboard will display.

**Architecture:** Immutable frozen dataclasses in `model.py`; pure functions in `rules.py` that take `now` and any new id as explicit arguments and return new state; `store.py` for path resolution and atomic JSON I/O; `tracker.py` as the thin façade that generates ids, calls rules, persists, and returns a view. No UI.

**Tech Stack:** Python 3.13, stdlib only (`dataclasses`, `datetime`, `json`, `uuid`, `pathlib`, `os`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-data-layer-design.md`

## Global Constraints

- **Nothing ambient.** Every function needing the current time takes `now: datetime`. Every function creating an id takes it as an argument. Only `tracker.py` calls `datetime.now()` or `uuid4()`. Tests never patch either.
- **`rules.py` imports only `model.py` and the standard library.** It never touches the filesystem and never reads a clock.
- Instants are timezone-aware UTC `datetime`; serialised with `.isoformat()`.
- `day_anchor` is a `datetime.date` — a **local** calendar date, from `moment.astimezone().date()`.
- Totals are derived from sessions, never stored.
- Storage: `~/Library/Application Support/Nebula/data.json`, or `data.dev.json` when `--dev`.
- Data file carries `"version": 1`.
- Writes are atomic: temp file in the same directory, then `os.replace()`.
- V1 does **not** detect sleep. No heartbeat, no tick, no gap threshold (PRD §16).
- A day has a start date (its anchor) and an end date (the local date of its last finished session or completion). The end date is what the rollover check compares against, and it counts finished sessions only (PRD §17.1).
- Percentage is never capped; `remaining_seconds` goes negative past the target.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/nebula/model.py` | Frozen dataclasses, view types, and `to_dict`/`from_dict` |
| `src/nebula/rules.py` | Pure functions: totals, derived state, transitions, rollover |
| `src/nebula/store.py` | Path resolution, atomic write, load/save |
| `src/nebula/tracker.py` | Façade: generates ids and `now`, calls rules, persists, returns views |
| `tests/test_model.py` | Serialisation round-trip |
| `tests/test_rules_totals.py` | Totals, derived state, views |
| `tests/test_rules_transitions.py` | Activate, Break, Complete, rollover, recovery |
| `tests/test_store.py` | Paths, atomic write, missing and corrupt files |
| `tests/test_tracker.py` | End-to-end through the façade against a real file |

---

### Task 1: Model and serialisation

**Files:**
- Create: `src/nebula/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Allocation`, `TimeSession`, `Completion`, `CurrentState`, `Preferences`, `AppData`, `AllocationView`, `DashboardView`, `empty_data(now)`, `to_dict(data)`, `from_dict(raw)`, and the `Status` / `AllocationState` literal types.

- [x] **Step 1: Write the failing test**

Create `tests/test_model.py`:

```python
"""The data model and its JSON representation."""

from datetime import date, datetime, timedelta, timezone

from nebula import model


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_empty_data_starts_neutral_with_todays_anchor():
    now = utc(2026, 9, 1, 12)
    data = model.empty_data(now)
    assert data.version == 1
    assert data.current.status == "NEUTRAL"
    assert data.current.active_allocation_id is None
    assert data.current.day_anchor == now.astimezone().date()
    assert data.allocations == ()
    assert data.sessions == ()
    assert data.completions == ()


def test_round_trip_preserves_every_field():
    data = model.AppData(
        version=1,
        current=model.CurrentState(
            status="BREAK",
            day_anchor=date(2026, 9, 1),
            active_allocation_id=None,
            pre_break_allocation_id="a1",
        ),
        allocations=(
            model.Allocation(
                id="a1",
                name="Work",
                daily_target_seconds=10800,
                created_at=utc(2026, 9, 1, 8),
                archived_at=None,
            ),
            model.Allocation(
                id="a2",
                name="Learning",
                daily_target_seconds=7200,
                created_at=utc(2026, 9, 1, 8),
                archived_at=utc(2026, 9, 1, 9),
            ),
        ),
        sessions=(
            model.TimeSession(
                id="s1",
                allocation_id="a1",
                started_at=utc(2026, 9, 1, 9),
                ended_at=utc(2026, 9, 1, 10, 30),
                day_anchor=date(2026, 9, 1),
            ),
            model.TimeSession(
                id="s2",
                allocation_id="a1",
                started_at=utc(2026, 9, 1, 11),
                ended_at=None,
                day_anchor=date(2026, 9, 1),
            ),
        ),
        completions=(
            model.Completion(
                day_anchor=date(2026, 8, 31),
                completed_at=utc(2026, 9, 1, 5),
            ),
        ),
        preferences=model.Preferences(name="Gio"),
    )

    assert model.from_dict(model.to_dict(data)) == data


def test_to_dict_is_json_serialisable():
    import json

    data = model.empty_data(utc(2026, 9, 1, 12))
    assert json.loads(json.dumps(model.to_dict(data))) == model.to_dict(data)


def test_timestamps_survive_as_aware_utc():
    data = model.empty_data(utc(2026, 9, 1, 12))
    data = model.AppData(
        version=data.version,
        current=data.current,
        allocations=(
            model.Allocation(
                id="a1",
                name="Work",
                daily_target_seconds=60,
                created_at=utc(2026, 9, 1, 8),
            ),
        ),
        sessions=(),
        completions=(),
        preferences=data.preferences,
    )
    restored = model.from_dict(model.to_dict(data))
    created = restored.allocations[0].created_at
    assert created.tzinfo is not None
    assert created.utcoffset() == timedelta(0)
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_model.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nebula.model'`.

- [x] **Step 3: Write the model**

Create `src/nebula/model.py`:

```python
"""The persisted data model and its JSON representation.

Every dataclass here is frozen. Rules return new instances rather than
mutating, which is what lets a rule be tested by comparing values.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any, Literal

SCHEMA_VERSION = 1

Status = Literal["ACTIVE", "BREAK", "NEUTRAL"]
AllocationState = Literal["NOT_STARTED", "ACTIVE", "STALE"]


@dataclass(frozen=True)
class Allocation:
    id: str
    name: str
    daily_target_seconds: int
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True)
class TimeSession:
    id: str
    allocation_id: str
    started_at: datetime
    day_anchor: date
    ended_at: datetime | None = None


@dataclass(frozen=True)
class Completion:
    day_anchor: date
    completed_at: datetime


@dataclass(frozen=True)
class CurrentState:
    status: Status
    day_anchor: date
    active_allocation_id: str | None = None
    pre_break_allocation_id: str | None = None


@dataclass(frozen=True)
class Preferences:
    name: str | None = None


@dataclass(frozen=True)
class AppData:
    version: int
    current: CurrentState
    allocations: tuple[Allocation, ...]
    sessions: tuple[TimeSession, ...]
    completions: tuple[Completion, ...]
    preferences: Preferences


@dataclass(frozen=True)
class AllocationView:
    id: str
    name: str
    daily_target_seconds: int
    tracked_seconds: int
    state: AllocationState
    percentage: float
    remaining_seconds: int
    active_since: str | None


@dataclass(frozen=True)
class DashboardView:
    status: Status
    day_anchor: str
    day_end_date: str
    allocations: tuple[AllocationView, ...]
    total_tracked_seconds: int
    total_target_seconds: int


def local_date(moment: datetime) -> date:
    """The local calendar date of an instant.

    A "day" is a human, local concept even though instants are absolute.
    """
    return moment.astimezone().date()


def empty_data(now: datetime) -> AppData:
    """The documented first-launch state: no allocations, neutral, today."""
    return AppData(
        version=SCHEMA_VERSION,
        current=CurrentState(status="NEUTRAL", day_anchor=local_date(now)),
        allocations=(),
        sessions=(),
        completions=(),
        preferences=Preferences(),
    )


def _dt(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def to_dict(data: AppData) -> dict[str, Any]:
    return {
        "version": data.version,
        "current": {
            "status": data.current.status,
            "dayAnchor": data.current.day_anchor.isoformat(),
            "activeAllocationId": data.current.active_allocation_id,
            "preBreakAllocationId": data.current.pre_break_allocation_id,
        },
        "allocations": [
            {
                "id": a.id,
                "name": a.name,
                "dailyTargetSeconds": a.daily_target_seconds,
                "createdAt": _dt(a.created_at),
                "archivedAt": _dt(a.archived_at),
            }
            for a in data.allocations
        ],
        "sessions": [
            {
                "id": s.id,
                "allocationId": s.allocation_id,
                "startedAt": _dt(s.started_at),
                "endedAt": _dt(s.ended_at),
                "dayAnchor": s.day_anchor.isoformat(),
            }
            for s in data.sessions
        ],
        "completions": [
            {
                "dayAnchor": c.day_anchor.isoformat(),
                "completedAt": _dt(c.completed_at),
            }
            for c in data.completions
        ],
        "preferences": {"name": data.preferences.name},
    }


def from_dict(raw: dict[str, Any]) -> AppData:
    current = raw["current"]
    return AppData(
        version=raw["version"],
        current=CurrentState(
            status=current["status"],
            day_anchor=date.fromisoformat(current["dayAnchor"]),
            active_allocation_id=current["activeAllocationId"],
            pre_break_allocation_id=current["preBreakAllocationId"],
        ),
        allocations=tuple(
            Allocation(
                id=a["id"],
                name=a["name"],
                daily_target_seconds=a["dailyTargetSeconds"],
                created_at=_parse_dt(a["createdAt"]),
                archived_at=_parse_dt(a["archivedAt"]),
            )
            for a in raw["allocations"]
        ),
        sessions=tuple(
            TimeSession(
                id=s["id"],
                allocation_id=s["allocationId"],
                started_at=_parse_dt(s["startedAt"]),
                ended_at=_parse_dt(s["endedAt"]),
                day_anchor=date.fromisoformat(s["dayAnchor"]),
            )
            for s in raw["sessions"]
        ),
        completions=tuple(
            Completion(
                day_anchor=date.fromisoformat(c["dayAnchor"]),
                completed_at=_parse_dt(c["completedAt"]),
            )
            for c in raw["completions"]
        ),
        preferences=Preferences(name=raw["preferences"]["name"]),
    )


__all__ = [
    "SCHEMA_VERSION",
    "Allocation",
    "AllocationState",
    "AllocationView",
    "AppData",
    "Completion",
    "CurrentState",
    "DashboardView",
    "Preferences",
    "Status",
    "TimeSession",
    "empty_data",
    "from_dict",
    "local_date",
    "replace",
    "to_dict",
]
```

- [x] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_model.py -v
```

Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add src/nebula/model.py tests/test_model.py
git commit -m "Add the data model and its JSON representation

Frozen dataclasses so rules return new values rather than mutating,
which is what lets a rule be tested by comparing results.

Instants serialise as timezone-aware UTC; dayAnchor serialises as a
local calendar date, because a day is a human concept while an instant
is absolute.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AAryYrW135ucc4MyN4W6jD"
```

---

### Task 2: Totals and derived state

**Files:**
- Create: `src/nebula/rules.py`
- Test: `tests/test_rules_totals.py`

**Interfaces:**
- Consumes: everything from Task 1.
- Produces: `session_seconds(session, now)`, `tracked_seconds(data, allocation_id, now)`, `allocation_state(allocation_id, tracked, current)`, `day_end_date(data, day_anchor)`, `build_dashboard(data, now)`.

- [x] **Step 1: Write the failing test**

Create `tests/test_rules_totals.py`:

```python
"""Totals, derived state and the dashboard view.

Real datetimes are passed as data. Nothing is patched, so nothing can
report success without the rule actually being right.
"""

from datetime import date, datetime, timezone

from nebula import model, rules


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def allocation(id_, name="Work", target=10800):
    return model.Allocation(
        id=id_, name=name, daily_target_seconds=target, created_at=utc(2026, 9, 1)
    )


def session(id_, allocation_id, start, end, anchor):
    return model.TimeSession(
        id=id_,
        allocation_id=allocation_id,
        started_at=start,
        ended_at=end,
        day_anchor=anchor,
    )


def data_with(sessions=(), allocations=(), current=None, anchor=date(2026, 9, 1)):
    return model.AppData(
        version=1,
        current=current or model.CurrentState(status="NEUTRAL", day_anchor=anchor),
        allocations=tuple(allocations),
        sessions=tuple(sessions),
        completions=(),
        preferences=model.Preferences(),
    )


def test_closed_session_counts_its_own_span():
    s = session("s1", "a1", utc(2026, 9, 1, 9), utc(2026, 9, 1, 10, 30), date(2026, 9, 1))
    assert rules.session_seconds(s, utc(2026, 9, 1, 23)) == 5400


def test_open_session_counts_up_to_now():
    s = session("s1", "a1", utc(2026, 9, 1, 9), None, date(2026, 9, 1))
    assert rules.session_seconds(s, utc(2026, 9, 1, 9, 30)) == 1800


def test_totals_sum_only_the_current_anchor():
    yesterday = session("s1", "a1", utc(2026, 8, 31, 9), utc(2026, 8, 31, 12), date(2026, 8, 31))
    today = session("s2", "a1", utc(2026, 9, 1, 9), utc(2026, 9, 1, 10), date(2026, 9, 1))
    data = data_with(sessions=[yesterday, today], allocations=[allocation("a1")])
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 1, 12)) == 3600


def test_session_crossing_midnight_counts_wholly_toward_its_start_day():
    """PRD §14: never split, and it keeps counting into the day it began."""
    overnight = session(
        "s1", "a1", utc(2026, 9, 1, 23), utc(2026, 9, 2, 5), date(2026, 9, 1)
    )
    data = data_with(sessions=[overnight], allocations=[allocation("a1")])
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 2, 6)) == 6 * 3600


def test_state_is_not_started_when_nothing_tracked():
    current = model.CurrentState(status="NEUTRAL", day_anchor=date(2026, 9, 1))
    assert rules.allocation_state("a1", 0, current) == "NOT_STARTED"


def test_state_is_active_for_the_active_allocation():
    current = model.CurrentState(
        status="ACTIVE", day_anchor=date(2026, 9, 1), active_allocation_id="a1"
    )
    assert rules.allocation_state("a1", 60, current) == "ACTIVE"


def test_state_is_stale_when_tracked_but_not_active():
    current = model.CurrentState(
        status="ACTIVE", day_anchor=date(2026, 9, 1), active_allocation_id="a2"
    )
    assert rules.allocation_state("a1", 60, current) == "STALE"


def test_dashboard_reports_percentage_and_remaining():
    s = session("s1", "a1", utc(2026, 9, 1, 9), utc(2026, 9, 1, 11, 24), date(2026, 9, 1))
    data = data_with(sessions=[s], allocations=[allocation("a1", target=10800)])
    view = rules.build_dashboard(data, utc(2026, 9, 1, 12))
    a = view.allocations[0]
    assert a.tracked_seconds == 8640
    assert a.percentage == 80.0
    assert a.remaining_seconds == 2160
    assert a.state == "STALE"


def test_progress_past_the_target_is_not_capped():
    """PRD §8: 3h45m against a 3h target is 125%, with negative remaining."""
    s = session("s1", "a1", utc(2026, 9, 1, 9), utc(2026, 9, 1, 12, 45), date(2026, 9, 1))
    data = data_with(sessions=[s], allocations=[allocation("a1", target=10800)])
    a = rules.build_dashboard(data, utc(2026, 9, 1, 13)).allocations[0]
    assert a.percentage == 125.0
    assert a.remaining_seconds == -2700


def test_active_since_is_present_only_for_the_active_allocation():
    current = model.CurrentState(
        status="ACTIVE", day_anchor=date(2026, 9, 1), active_allocation_id="a1"
    )
    open_session = session("s1", "a1", utc(2026, 9, 1, 9), None, date(2026, 9, 1))
    data = data_with(
        sessions=[open_session],
        allocations=[allocation("a1"), allocation("a2", name="Learning")],
        current=current,
    )
    views = {a.id: a for a in rules.build_dashboard(data, utc(2026, 9, 1, 10)).allocations}
    assert views["a1"].active_since == utc(2026, 9, 1, 9).isoformat()
    assert views["a2"].active_since is None


def test_archived_allocations_are_hidden_but_their_sessions_remain():
    """PRD §12: delete removes it from view; history is untouched."""
    archived = model.Allocation(
        id="a2",
        name="Gone",
        daily_target_seconds=3600,
        created_at=utc(2026, 9, 1),
        archived_at=utc(2026, 9, 1, 10),
    )
    s = session("s1", "a2", utc(2026, 9, 1, 9), utc(2026, 9, 1, 10), date(2026, 9, 1))
    data = data_with(sessions=[s], allocations=[allocation("a1"), archived])
    view = rules.build_dashboard(data, utc(2026, 9, 1, 12))
    assert [a.id for a in view.allocations] == ["a1"]
    assert data.sessions[0].allocation_id == "a2"


def test_dashboard_totals_cover_visible_allocations():
    s = session("s1", "a1", utc(2026, 9, 1, 9), utc(2026, 9, 1, 10), date(2026, 9, 1))
    data = data_with(
        sessions=[s],
        allocations=[allocation("a1", target=10800), allocation("a2", "Learning", 7200)],
    )
    view = rules.build_dashboard(data, utc(2026, 9, 1, 12))
    assert view.total_tracked_seconds == 3600
    assert view.total_target_seconds == 18000
    assert view.day_anchor == "2026-09-01"


def test_day_end_date_defaults_to_the_start_date():
    data = data_with(allocations=[allocation("a1")])
    view = rules.build_dashboard(data, utc(2026, 9, 1, 12))
    assert view.day_anchor == "2026-09-01"
    assert view.day_end_date == "2026-09-01"


def test_day_end_date_follows_an_overnight_session():
    """PRD §17.1: 11pm to 5am is a day that starts and ends on different dates."""
    overnight = session(
        "s1", "a1", utc(2026, 9, 1, 23), utc(2026, 9, 2, 5), date(2026, 9, 1)
    )
    data = data_with(sessions=[overnight], allocations=[allocation("a1")])
    view = rules.build_dashboard(data, utc(2026, 9, 2, 6))
    assert view.day_anchor == "2026-09-01"
    assert view.day_end_date == model.local_date(utc(2026, 9, 2, 5)).isoformat()


def test_day_end_date_ignores_open_sessions():
    """Otherwise crash recovery would make every day look like it ended today."""
    open_session = session("s1", "a1", utc(2026, 9, 1, 23), None, date(2026, 9, 1))
    data = data_with(sessions=[open_session], allocations=[allocation("a1")])
    assert rules.day_end_date(data, date(2026, 9, 1)) == date(2026, 9, 1)


def test_percentage_is_zero_when_the_target_is_zero():
    """Guards division. The settings UI forbids zero, but the rule cannot assume it."""
    s = session("s1", "a1", utc(2026, 9, 1, 9), utc(2026, 9, 1, 10), date(2026, 9, 1))
    data = data_with(sessions=[s], allocations=[allocation("a1", target=0)])
    a = rules.build_dashboard(data, utc(2026, 9, 1, 12)).allocations[0]
    assert a.percentage == 0.0
    assert a.remaining_seconds == -3600
```

- [x] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_rules_totals.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nebula.rules'`.

- [x] **Step 3: Write the totals half of `rules.py`**

Create `src/nebula/rules.py`:

```python
"""Pure tracking rules.

Imports only `model` and the standard library. Never touches the filesystem
and never reads a clock: `now` and any new id arrive as arguments, so a test
passes real values rather than patching a source of truth that would then
report whatever the test told it to.
"""

from __future__ import annotations

from datetime import date, datetime

from nebula import model
from nebula.model import (
    Allocation,
    AllocationState,
    AllocationView,
    AppData,
    CurrentState,
    DashboardView,
    TimeSession,
)


def session_seconds(session: TimeSession, now: datetime) -> int:
    """Elapsed seconds. An open session counts up to `now`."""
    end = session.ended_at if session.ended_at is not None else now
    return max(0, int((end - session.started_at).total_seconds()))


def visible_allocations(data: AppData) -> tuple[Allocation, ...]:
    """Allocations not deleted. Their sessions stay in the file (PRD §12)."""
    return tuple(a for a in data.allocations if a.archived_at is None)


def tracked_seconds(data: AppData, allocation_id: str, now: datetime) -> int:
    """Seconds tracked for one allocation within the currently open day.

    Filtering by anchor is what makes a day "reset" without deleting
    anything, and what keeps a session that crossed midnight counting
    toward the day it began in.
    """
    return sum(
        session_seconds(s, now)
        for s in data.sessions
        if s.allocation_id == allocation_id and s.day_anchor == data.current.day_anchor
    )


def allocation_state(
    allocation_id: str, tracked: int, current: CurrentState
) -> AllocationState:
    if current.active_allocation_id == allocation_id:
        return "ACTIVE"
    if tracked == 0:
        return "NOT_STARTED"
    return "STALE"


def open_session_for(data: AppData, allocation_id: str) -> TimeSession | None:
    for s in data.sessions:
        if s.allocation_id == allocation_id and s.ended_at is None:
            return s
    return None


def build_allocation_view(
    data: AppData, allocation: Allocation, now: datetime
) -> AllocationView:
    tracked = tracked_seconds(data, allocation.id, now)
    state = allocation_state(allocation.id, tracked, data.current)

    target = allocation.daily_target_seconds
    percentage = (tracked / target * 100) if target > 0 else 0.0

    active_since = None
    if state == "ACTIVE":
        open_session = open_session_for(data, allocation.id)
        if open_session is not None:
            active_since = open_session.started_at.isoformat()

    return AllocationView(
        id=allocation.id,
        name=allocation.name,
        daily_target_seconds=target,
        tracked_seconds=tracked,
        state=state,
        percentage=percentage,
        remaining_seconds=target - tracked,
        active_since=active_since,
    )


def day_end_date(data: AppData, day_anchor: date) -> date:
    """The last local date on which anything *finished* in this day (PRD §17.1).

    Both displayed and used as the rollover reference. Open sessions are
    excluded deliberately: crash recovery closes an orphan at the current
    moment, so counting open sessions would make every day look like it ended
    today and no day could ever roll over.
    """
    moments = [
        s.ended_at
        for s in data.sessions
        if s.day_anchor == day_anchor and s.ended_at is not None
    ]
    moments += [c.completed_at for c in data.completions if c.day_anchor == day_anchor]
    if not moments:
        return day_anchor
    return max(model.local_date(max(moments)), day_anchor)


def build_dashboard(data: AppData, now: datetime) -> DashboardView:
    views = tuple(
        build_allocation_view(data, a, now) for a in visible_allocations(data)
    )
    return DashboardView(
        status=data.current.status,
        day_anchor=data.current.day_anchor.isoformat(),
        day_end_date=day_end_date(data, data.current.day_anchor).isoformat(),
        allocations=views,
        total_tracked_seconds=sum(v.tracked_seconds for v in views),
        total_target_seconds=sum(v.daily_target_seconds for v in views),
    )
```

- [x] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_rules_totals.py -v
```

Expected: 16 passed.

- [x] **Step 5: Commit**

```bash
git add src/nebula/rules.py tests/test_rules_totals.py
git commit -m "Derive totals and dashboard state from sessions

Totals are summed from sessions filtered by the open day's anchor rather
than stored as a counter. Three PRD requirements then fall out of the
data model instead of needing their own code: a session crossing midnight
counts wholly toward the day it began, a day resets by changing the
anchor rather than deleting anything, and history survives untouched.

Tests pass real datetimes as data, with nothing patched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AAryYrW135ucc4MyN4W6jD"
```

---

### Task 3: Transitions — activate, Break, Complete, rollover

**Files:**
- Modify: `src/nebula/rules.py`
- Test: `tests/test_rules_transitions.py`

**Interfaces:**
- Consumes: Task 2's `rules.py`.
- Produces: `end_open_sessions(data, at)`, `activate(data, allocation_id, now, session_id)`, `toggle_break(data, now, session_id)`, `complete_day(data, now)`, `resume(data, now)`, `add_allocation(data, name, target_seconds, now, allocation_id)`, `edit_allocation(data, allocation_id, name, target_seconds)`, `delete_allocation(data, allocation_id, now)`.

- [x] **Step 1: Write the failing test**

Create `tests/test_rules_transitions.py`:

```python
"""State transitions: activate, Break, Complete, day rollover, recovery."""

from datetime import date, datetime, timezone

from nebula import model, rules


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def base(anchor=date(2026, 9, 1)):
    data = model.empty_data(utc(2026, 9, 1, 8))
    data = model.replace(
        data, current=model.CurrentState(status="NEUTRAL", day_anchor=anchor)
    )
    return model.replace(
        data,
        allocations=(
            model.Allocation("a1", "Work", 10800, utc(2026, 9, 1, 8)),
            model.Allocation("a2", "Learning", 7200, utc(2026, 9, 1, 8)),
        ),
    )


def test_activate_opens_a_session_and_sets_active():
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    assert data.current.status == "ACTIVE"
    assert data.current.active_allocation_id == "a1"
    assert len(data.sessions) == 1
    assert data.sessions[0].ended_at is None
    assert data.sessions[0].day_anchor == date(2026, 9, 1)


def test_switching_closes_the_previous_session():
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.activate(data, "a2", utc(2026, 9, 1, 10), "s2")
    first = [s for s in data.sessions if s.id == "s1"][0]
    assert first.ended_at == utc(2026, 9, 1, 10)
    assert data.current.active_allocation_id == "a2"
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 1, 11)) == 3600


def test_activating_exits_break():
    """PRD §10.4: clicking an allocation exits Break immediately."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.toggle_break(data, utc(2026, 9, 1, 10), "unused")
    data = rules.activate(data, "a2", utc(2026, 9, 1, 10, 30), "s2")
    assert data.current.status == "ACTIVE"
    assert data.current.pre_break_allocation_id is None


def test_break_from_active_pauses_and_remembers():
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.toggle_break(data, utc(2026, 9, 1, 10), "unused")
    assert data.current.status == "BREAK"
    assert data.current.active_allocation_id is None
    assert data.current.pre_break_allocation_id == "a1"
    assert data.sessions[0].ended_at == utc(2026, 9, 1, 10)


def test_break_toggled_off_resumes_the_same_allocation():
    """PRD §6.4: Break is pause/resume, not deselect."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.toggle_break(data, utc(2026, 9, 1, 10), "unused")
    data = rules.toggle_break(data, utc(2026, 9, 1, 10, 30), "s2")
    assert data.current.status == "ACTIVE"
    assert data.current.active_allocation_id == "a1"
    assert data.current.pre_break_allocation_id is None
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 1, 11)) == 3600 + 1800


def test_break_from_neutral_returns_to_neutral():
    """PRD §6.4/§6.5: Neutral is distinct, and nothing is remembered."""
    data = rules.toggle_break(base(), utc(2026, 9, 1, 9), "unused")
    assert data.current.status == "BREAK"
    assert data.current.pre_break_allocation_id is None
    data = rules.toggle_break(data, utc(2026, 9, 1, 10), "unused")
    assert data.current.status == "NEUTRAL"
    assert data.current.active_allocation_id is None
    assert data.sessions == ()


def test_complete_ends_the_session_and_records_a_completion():
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.complete_day(data, utc(2026, 9, 1, 12))
    assert data.current.status == "NEUTRAL"
    assert data.current.active_allocation_id is None
    assert data.sessions[0].ended_at == utc(2026, 9, 1, 12)
    assert len(data.completions) == 1
    assert data.completions[0].day_anchor == date(2026, 9, 1)


def test_complete_zeroes_nothing():
    """Complete at 3pm, work on, Complete at 6pm: the day accumulates."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.complete_day(data, utc(2026, 9, 1, 12))
    data = rules.activate(data, "a1", utc(2026, 9, 1, 13), "s2")
    data = rules.complete_day(data, utc(2026, 9, 1, 14))
    assert len(data.completions) == 2
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 1, 15)) == 4 * 3600


def test_resume_on_the_same_date_keeps_totals_and_clears_active():
    """Nothing has finished yet, so the day ends on its start date."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.resume(data, utc(2026, 9, 1, 12))
    assert data.current.day_anchor == date(2026, 9, 1)
    assert data.current.status == "NEUTRAL"
    assert data.current.active_allocation_id is None
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 1, 12)) == 3 * 3600


def test_resume_on_a_later_date_starts_a_fresh_day():
    """PRD §17: totals reset by anchor change; prior sessions stay in the file."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.complete_day(data, utc(2026, 9, 1, 17))
    data = rules.resume(data, utc(2026, 9, 3, 9))
    assert data.current.day_anchor == model.local_date(utc(2026, 9, 3, 9))
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 3, 10)) == 0
    assert len(data.sessions) == 1


def test_resume_closes_a_session_left_open_by_a_crash():
    """Spec §6: no ended_at means the app died. Close it at now."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.resume(data, utc(2026, 9, 1, 11))
    assert data.sessions[0].ended_at == utc(2026, 9, 1, 11)
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 1, 11)) == 2 * 3600


def test_a_crash_unnoticed_for_days_does_not_pollute_today():
    """The stale session keeps its old anchor, so it lands in that day."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.resume(data, utc(2026, 9, 4, 9))
    assert data.sessions[0].ended_at == utc(2026, 9, 4, 9)
    assert data.sessions[0].day_anchor == date(2026, 9, 1)
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 4, 10)) == 0


def test_an_overnight_day_continues_when_resumed_the_same_morning():
    """PRD §17.1: finished at 5am, back at 9am — you carried on, same day."""
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 23), "s1")
    data = rules.complete_day(data, utc(2026, 9, 2, 5))
    data = rules.resume(data, utc(2026, 9, 2, 9))
    assert data.current.day_anchor == date(2026, 9, 1)
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 2, 9)) == 6 * 3600


def test_an_overnight_day_still_rolls_over_the_following_day():
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 23), "s1")
    data = rules.complete_day(data, utc(2026, 9, 2, 5))
    data = rules.resume(data, utc(2026, 9, 3, 9))
    assert data.current.day_anchor == model.local_date(utc(2026, 9, 3, 9))
    assert rules.tracked_seconds(data, "a1", utc(2026, 9, 3, 10)) == 0


def test_an_overnight_day_reports_both_dates():
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 23), "s1")
    data = rules.complete_day(data, utc(2026, 9, 2, 5))
    view = rules.build_dashboard(data, utc(2026, 9, 2, 6))
    assert view.day_anchor == "2026-09-01"
    assert view.day_end_date == model.local_date(utc(2026, 9, 2, 5)).isoformat()


def test_add_edit_and_delete_an_allocation():
    data = rules.add_allocation(base(), "Reading", 3600, utc(2026, 9, 1, 9), "a3")
    assert [a.id for a in rules.visible_allocations(data)] == ["a1", "a2", "a3"]

    data = rules.edit_allocation(data, "a3", name="Reading More", target_seconds=5400)
    a3 = [a for a in data.allocations if a.id == "a3"][0]
    assert (a3.name, a3.daily_target_seconds) == ("Reading More", 5400)

    data = rules.delete_allocation(data, "a3", utc(2026, 9, 1, 10))
    assert [a.id for a in rules.visible_allocations(data)] == ["a1", "a2"]
    assert len(data.allocations) == 3


def test_deleting_the_active_allocation_stops_tracking():
    data = rules.activate(base(), "a1", utc(2026, 9, 1, 9), "s1")
    data = rules.delete_allocation(data, "a1", utc(2026, 9, 1, 10))
    assert data.current.status == "NEUTRAL"
    assert data.current.active_allocation_id is None
    assert data.sessions[0].ended_at == utc(2026, 9, 1, 10)
```

- [x] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_rules_transitions.py -v
```

Expected: FAIL — `AttributeError: module 'nebula.rules' has no attribute 'activate'`.

- [x] **Step 3: Append the transitions to `rules.py`**

Add to the end of `src/nebula/rules.py`:

```python
def end_open_sessions(data: AppData, at: datetime) -> AppData:
    """Close every open session at `at`. Closing an already-closed one is a no-op."""
    return model.replace(
        data,
        sessions=tuple(
            s if s.ended_at is not None else model.replace(s, ended_at=at)
            for s in data.sessions
        ),
    )


def activate(
    data: AppData, allocation_id: str, now: datetime, session_id: str
) -> AppData:
    """Make an allocation Active, ending whatever was running (PRD §10.3, §10.4).

    Activating always exits Break, and clears what Break remembered: the user
    has chosen directly, so there is nothing left to resume.
    """
    data = end_open_sessions(data, now)
    session = TimeSession(
        id=session_id,
        allocation_id=allocation_id,
        started_at=now,
        ended_at=None,
        day_anchor=data.current.day_anchor,
    )
    return model.replace(
        data,
        sessions=data.sessions + (session,),
        current=model.replace(
            data.current,
            status="ACTIVE",
            active_allocation_id=allocation_id,
            pre_break_allocation_id=None,
        ),
    )


def toggle_break(data: AppData, now: datetime, session_id: str) -> AppData:
    """Break is a pause/resume toggle, not a deselect (PRD §6.4)."""
    if data.current.status == "BREAK":
        resuming = data.current.pre_break_allocation_id
        if resuming is None:
            return model.replace(
                data,
                current=model.replace(
                    data.current, status="NEUTRAL", pre_break_allocation_id=None
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
        ),
    )


def complete_day(data: AppData, now: datetime) -> AppData:
    """End the day and record it (PRD §10.6, §18.1).

    Records a Completion and stops tracking. It clears no totals: only a date
    check at a resume point begins a fresh day.
    """
    data = end_open_sessions(data, now)
    completion = model.Completion(day_anchor=data.current.day_anchor, completed_at=now)
    return model.replace(
        data,
        completions=data.completions + (completion,),
        current=model.replace(
            data.current,
            status="NEUTRAL",
            active_allocation_id=None,
            pre_break_allocation_id=None,
        ),
    )


def resume(data: AppData, now: datetime) -> AppData:
    """A resume point: app open, or Start after Complete (PRD §17, §18.3).

    The date check compares today against the day's *end* date, not its start
    (PRD §17.1). Finishing at 5am and starting again at 9am the same morning
    continues that day; finishing at 5pm and returning tomorrow starts a new
    one.

    The reference is computed **before** recovery closes anything. Any session
    still open here means the app did not exit cleanly, and it is closed at
    `now` — an allocation counts until something stops it, and a crash stopped
    nothing (PRD §16). If that freshly closed session counted toward the end
    date, every day would look like it ended today and no day could ever roll
    over. It keeps its original anchor, so a crash noticed days later lands in
    that old day rather than on today's dashboard.
    """
    reference = day_end_date(data, data.current.day_anchor)
    data = end_open_sessions(data, now)
    today = model.local_date(now)
    current = model.replace(
        data.current,
        status="NEUTRAL",
        active_allocation_id=None,
        pre_break_allocation_id=None,
    )
    if reference != today:
        current = model.replace(current, day_anchor=today)
    return model.replace(data, current=current)


def add_allocation(
    data: AppData, name: str, target_seconds: int, now: datetime, allocation_id: str
) -> AppData:
    allocation = Allocation(
        id=allocation_id,
        name=name,
        daily_target_seconds=target_seconds,
        created_at=now,
    )
    return model.replace(data, allocations=data.allocations + (allocation,))


def edit_allocation(
    data: AppData, allocation_id: str, name: str, target_seconds: int
) -> AppData:
    """A target change applies to today immediately (PRD §12, §19)."""
    return model.replace(
        data,
        allocations=tuple(
            model.replace(a, name=name, daily_target_seconds=target_seconds)
            if a.id == allocation_id
            else a
            for a in data.allocations
        ),
    )


def delete_allocation(data: AppData, allocation_id: str, now: datetime) -> AppData:
    """Archive rather than remove, so historical sessions still resolve (PRD §12)."""
    if data.current.active_allocation_id == allocation_id:
        data = end_open_sessions(data, now)
        data = model.replace(
            data,
            current=model.replace(
                data.current,
                status="NEUTRAL",
                active_allocation_id=None,
                pre_break_allocation_id=None,
            ),
        )
    return model.replace(
        data,
        allocations=tuple(
            model.replace(a, archived_at=now) if a.id == allocation_id else a
            for a in data.allocations
        ),
    )
```

- [x] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_rules_transitions.py -v
```

Expected: 17 passed.

- [x] **Step 5: Run the whole suite**

```bash
uv run pytest -q
```

Expected: 46 passed (9 from phases 1-2, plus 37 new: 4 model, 16 totals, 17 transitions).

- [x] **Step 6: Commit**

```bash
git add src/nebula/rules.py tests/test_rules_transitions.py
git commit -m "Add tracking transitions: activate, Break, Complete, rollover

Break is a pause/resume toggle rather than a deselect, so toggling off
resumes the allocation it paused, and returns to Neutral when Break was
entered from Neutral. Activating anything exits Break and forgets what
it remembered, since the user has chosen directly.

Complete records a Completion and stops tracking but clears no totals:
completing twice in one day shows the accumulated day, not the span
since the last recap. Only a date check at a resume point starts a fresh
day.

A session still open at a resume point means the app did not exit
cleanly, so it closes at now. It keeps its original anchor, so a crash
noticed days later lands in that old day rather than on today's
dashboard.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AAryYrW135ucc4MyN4W6jD"
```

---

### Task 4: Store — paths and atomic JSON I/O

**Files:**
- Create: `src/nebula/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `model.to_dict`, `model.from_dict`, `model.empty_data`.
- Produces: `data_path(dev=False)`, `load(path, now)`, `save(data, path)`, `DataFileCorrupt`.

- [x] **Step 1: Write the failing test**

Create `tests/test_store.py`:

```python
"""Path resolution and atomic JSON persistence."""

import json
from datetime import datetime, timezone

import pytest

from nebula import model, store


def utc(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_production_path_is_in_application_support():
    path = store.data_path(dev=False)
    assert path.parent.name == "Nebula"
    assert "Application Support" in str(path)
    assert path.name == "data.json"


def test_dev_path_is_a_separate_file_beside_it():
    """Hacking on the app must not be able to destroy real tracked time."""
    assert store.data_path(dev=True).name == "data.dev.json"
    assert store.data_path(dev=True).parent == store.data_path(dev=False).parent


def test_load_of_a_missing_file_returns_the_empty_state(tmp_path):
    data = store.load(tmp_path / "absent.json", utc(2026, 9, 1, 12))
    assert data.allocations == ()
    assert data.current.status == "NEUTRAL"


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "data.json"
    original = model.empty_data(utc(2026, 9, 1, 12))
    original = model.replace(
        original,
        allocations=(model.Allocation("a1", "Work", 10800, utc(2026, 9, 1, 8)),),
    )
    store.save(original, path)
    assert store.load(path, utc(2026, 9, 1, 13)) == original


def test_save_creates_the_directory(tmp_path):
    path = tmp_path / "nested" / "deeper" / "data.json"
    store.save(model.empty_data(utc(2026, 9, 1, 12)), path)
    assert path.exists()


def test_a_corrupt_file_raises_rather_than_starting_fresh(tmp_path):
    """Silently discarding a user's history is worse than refusing to start."""
    path = tmp_path / "data.json"
    path.write_text("{ this is not json")
    with pytest.raises(store.DataFileCorrupt):
        store.load(path, utc(2026, 9, 1, 12))


def test_the_previous_file_survives_a_failed_write(tmp_path):
    """A crash mid-write must not truncate the one irreplaceable file."""
    path = tmp_path / "data.json"
    good = model.empty_data(utc(2026, 9, 1, 12))
    store.save(good, path)

    class Unserialisable:
        pass

    broken = model.replace(good, preferences=model.Preferences(name=Unserialisable()))
    with pytest.raises(TypeError):
        store.save(broken, path)

    assert store.load(path, utc(2026, 9, 1, 13)) == good


def test_no_temp_files_are_left_behind(tmp_path):
    path = tmp_path / "data.json"
    store.save(model.empty_data(utc(2026, 9, 1, 12)), path)
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_the_file_records_its_schema_version(tmp_path):
    path = tmp_path / "data.json"
    store.save(model.empty_data(utc(2026, 9, 1, 12)), path)
    assert json.loads(path.read_text())["version"] == 1
```

- [x] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_store.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nebula.store'`.

- [x] **Step 3: Write the store**

Create `src/nebula/store.py`:

```python
"""Where the data file lives, and how it is read and written.

The data file is the only irreplaceable thing in the product, so writes are
atomic: a crash leaves the previous file intact rather than truncated JSON.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from nebula import model
from nebula.model import AppData

APP_DIR = Path.home() / "Library" / "Application Support" / "Nebula"


class DataFileCorrupt(RuntimeError):
    """The data file exists but could not be parsed."""


def data_path(dev: bool = False) -> Path:
    """The data file.

    Absolute, because a bundled app's working directory is `/` — a relative
    path works from a source checkout and silently breaks in the .app.

    Development writes a separate file so that working on the app cannot
    corrupt or wipe real tracked history.
    """
    return APP_DIR / ("data.dev.json" if dev else "data.json")


def load(path: Path, now: datetime) -> AppData:
    """Read the data file, or return the first-launch state if absent."""
    if not path.exists():
        return model.empty_data(now)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return model.from_dict(raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise DataFileCorrupt(f"Could not read {path}: {error}") from error


def save(data: AppData, path: Path) -> None:
    """Write atomically: serialise to a temp file, then replace.

    `os.replace` is atomic on POSIX, so a reader never sees a half-written
    file and a crash mid-write cannot destroy the previous one. Serialising
    before the replace means a serialisation error leaves the old file alone.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(model.to_dict(data), indent=2)

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
```

- [x] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_store.py -v
```

Expected: 9 passed.

Note: `test_the_previous_file_survives_a_failed_write` relies on `json.dumps`
raising **before** the temp file is replaced. That ordering is the point of the
test — if serialisation moved after the replace, it would fail.

- [x] **Step 5: Commit**

```bash
git add src/nebula/store.py tests/test_store.py
git commit -m "Persist to Application Support with atomic writes

The path is absolute because a bundled app's working directory is /,
which the packaging spike confirmed: a relative path works from a source
checkout and silently breaks in the .app. Development writes a separate
data.dev.json so working on the app cannot destroy real tracked history.

Writes serialise to a temp file and os.replace onto the target, so a
crash mid-write leaves the previous file intact rather than truncated
JSON. Serialising before the replace means even a serialisation failure
leaves the old file untouched, which is covered by a test.

A missing file yields the first-launch state; a corrupt one raises rather
than silently starting fresh, since discarding a user's history without
telling them is worse than refusing to start.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AAryYrW135ucc4MyN4W6jD"
```

---

### Task 5: Tracker façade

**Files:**
- Create: `src/nebula/tracker.py`
- Test: `tests/test_tracker.py`

**Interfaces:**
- Consumes: `rules`, `store`, `model`.
- Produces: `Tracker(path)` with `open(now)`, `activate(allocation_id, now)`, `toggle_break(now)`, `complete_day(now)`, `add_allocation(name, target_seconds, now)`, `edit_allocation(allocation_id, name, target_seconds, now)`, `delete_allocation(allocation_id, now)`, `view(now)` — each returning a `DashboardView`.

- [x] **Step 1: Write the failing test**

Create `tests/test_tracker.py`:

```python
"""The façade, exercised against a real file on disk."""

from datetime import datetime, timedelta, timezone

from nebula import store, tracker


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_a_day_of_use_survives_being_reopened(tmp_path):
    """The whole point: close the app, reopen it, and the day is still there."""
    path = tmp_path / "data.json"

    first = tracker.Tracker(path)
    first.open(utc(2026, 9, 1, 8))
    first.add_allocation("Work", 10800, utc(2026, 9, 1, 8))
    first.add_allocation("Learning", 7200, utc(2026, 9, 1, 8))
    view = first.view(utc(2026, 9, 1, 8))
    work = view.allocations[0].id

    first.activate(work, utc(2026, 9, 1, 9))
    first.toggle_break(utc(2026, 9, 1, 10, 30))

    reopened = tracker.Tracker(path)
    view = reopened.open(utc(2026, 9, 1, 11))

    assert view.status == "NEUTRAL"
    assert view.allocations[0].tracked_seconds == 5400
    assert view.allocations[0].state == "STALE"
    assert view.allocations[0].percentage == 50.0
    assert view.total_target_seconds == 18000


def test_ids_are_unique_across_calls(tmp_path):
    t = tracker.Tracker(tmp_path / "data.json")
    t.open(utc(2026, 9, 1, 8))
    t.add_allocation("Work", 3600, utc(2026, 9, 1, 8))
    t.add_allocation("Learning", 3600, utc(2026, 9, 1, 8))
    ids = [a.id for a in t.view(utc(2026, 9, 1, 9)).allocations]
    assert len(set(ids)) == 2


def test_every_call_persists(tmp_path):
    path = tmp_path / "data.json"
    t = tracker.Tracker(path)
    t.open(utc(2026, 9, 1, 8))
    t.add_allocation("Work", 3600, utc(2026, 9, 1, 8))
    on_disk = store.load(path, utc(2026, 9, 1, 9))
    assert len(on_disk.allocations) == 1


def test_reopening_on_a_later_day_starts_fresh_and_keeps_history(tmp_path):
    path = tmp_path / "data.json"
    t = tracker.Tracker(path)
    t.open(utc(2026, 9, 1, 8))
    t.add_allocation("Work", 10800, utc(2026, 9, 1, 8))
    work = t.view(utc(2026, 9, 1, 8)).allocations[0].id
    t.activate(work, utc(2026, 9, 1, 9))
    t.complete_day(utc(2026, 9, 1, 12))

    later = tracker.Tracker(path)
    view = later.open(utc(2026, 9, 3, 9))
    assert view.allocations[0].tracked_seconds == 0
    assert view.allocations[0].state == "NOT_STARTED"
    assert len(store.load(path, utc(2026, 9, 3, 9)).sessions) == 1


def test_elapsed_time_is_real_not_simulated(tmp_path):
    """Passes wall-clock datetimes an hour apart, computed rather than stated."""
    path = tmp_path / "data.json"
    t = tracker.Tracker(path)
    started = utc(2026, 9, 1, 9)
    t.open(started)
    t.add_allocation("Work", 10800, started)
    work = t.view(started).allocations[0].id
    t.activate(work, started)
    view = t.view(started + timedelta(hours=1, minutes=15))
    assert view.allocations[0].tracked_seconds == 4500
    assert view.allocations[0].active_since == started.isoformat()
```

- [x] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_tracker.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nebula.tracker'`.

- [x] **Step 3: Write the façade**

Create `src/nebula/tracker.py`:

```python
"""The data layer's public surface.

This is the only module that generates ids. `now` still arrives from the
caller, so the layer stays testable end to end without patching a clock —
`__main__` is where real time enters the program.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from nebula import rules, store
from nebula.model import AppData, DashboardView


class Tracker:
    """Loads, applies a rule, saves, and returns what the UI should render."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: AppData | None = None

    def _load(self, now: datetime) -> AppData:
        if self._data is None:
            self._data = store.load(self._path, now)
        return self._data

    def _commit(self, data: AppData, now: datetime) -> DashboardView:
        self._data = data
        store.save(data, self._path)
        return rules.build_dashboard(data, now)

    def open(self, now: datetime) -> DashboardView:
        """A resume point (PRD §17): date check, and recover a crashed session."""
        return self._commit(rules.resume(self._load(now), now), now)

    def view(self, now: datetime) -> DashboardView:
        return rules.build_dashboard(self._load(now), now)

    def activate(self, allocation_id: str, now: datetime) -> DashboardView:
        data = rules.activate(self._load(now), allocation_id, now, uuid4().hex)
        return self._commit(data, now)

    def toggle_break(self, now: datetime) -> DashboardView:
        data = rules.toggle_break(self._load(now), now, uuid4().hex)
        return self._commit(data, now)

    def complete_day(self, now: datetime) -> DashboardView:
        return self._commit(rules.complete_day(self._load(now), now), now)

    def add_allocation(
        self, name: str, target_seconds: int, now: datetime
    ) -> DashboardView:
        data = rules.add_allocation(
            self._load(now), name, target_seconds, now, uuid4().hex
        )
        return self._commit(data, now)

    def edit_allocation(
        self, allocation_id: str, name: str, target_seconds: int, now: datetime
    ) -> DashboardView:
        data = rules.edit_allocation(
            self._load(now), allocation_id, name, target_seconds
        )
        return self._commit(data, now)

    def delete_allocation(self, allocation_id: str, now: datetime) -> DashboardView:
        data = rules.delete_allocation(self._load(now), allocation_id, now)
        return self._commit(data, now)
```

- [x] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_tracker.py -v
```

Expected: 5 passed.

- [x] **Step 5: Run the whole suite**

```bash
uv run pytest -q
```

Expected: 60 passed (9 from phases 1-2, plus 51 new).

- [x] **Step 6: Verify the constraint that keeps the rules testable**

```bash
grep -nE "datetime\.now|uuid4|from nebula import store|^import (os|json|pathlib)" src/nebula/rules.py \
  || echo "clean: rules.py has no clock, no id source, no storage import"
```

Expected: the "clean" message.

This is not decoration. The entire testing strategy rests on `rules.py` having
no ambient dependencies: the moment it can read a clock or generate an id
itself, its tests have to patch that source, and a patched source returns
whatever the test told it to — passing whether or not the rule is correct. The
grep is the guard on that property.

- [x] **Step 7: Commit**

```bash
git add src/nebula/tracker.py tests/test_tracker.py
git commit -m "Add the tracker façade over rules and storage

Loads, applies one rule, persists, and returns the view the dashboard
will render. This is the only module that generates ids; now still
arrives from the caller, so the whole layer can be exercised end to end
against a real file without patching a clock.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AAryYrW135ucc4MyN4W6jD"
```

---

## Definition of Done

Against spec §12:

1. `tracker.py` exposes load, add/edit/delete allocation, activate, toggle Break, complete the day, and build a `DashboardView`, each taking `now` explicitly — Task 5.
2. Data persists to `~/Library/Application Support/Nebula/data.json`, `--dev` to `data.dev.json` — Task 4. (Wiring `--dev` through `app.py` belongs to the dashboard phase, which is the first caller.)
3. Every rule in spec §9 is covered by tests in spec §10, with real timestamps and no patched clock — Tasks 2, 3, 5.
4. `rules.py` imports nothing from `store.py` and never reads the clock — Task 5, Step 6.
5. The full suite passes, including the phase 2 GUI regression test — Task 5, Step 5.
