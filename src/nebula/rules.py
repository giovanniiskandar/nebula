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
