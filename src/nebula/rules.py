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
