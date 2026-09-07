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


def days_tracked(data: AppData, allocation_id: str) -> int:
    """How many distinct days this allocation has been worked on.

    Counts day anchors rather than sessions: switching away and back three
    times in one day is one day, not three.
    """
    return len(
        {s.day_anchor for s in data.sessions if s.allocation_id == allocation_id}
    )


def set_name(data: AppData, name: str) -> AppData:
    """Set the *user's* name, used only to personalise the recap (PRD §12, §18.2).

    A blank name stores `None`, so "cleared" and "never set" are one state.
    """
    trimmed = name.strip()
    return model.replace(
        data, preferences=model.replace(data.preferences, name=trimmed or None)
    )


MILESTONES = (95, 100)


def milestones_reached(percentage: float) -> tuple[int, ...]:
    """Every milestone this percentage has reached.

    At 100% both are reached: an allocation that jumps straight past 95 should
    not leave it armed to fire later.
    """
    return tuple(m for m in MILESTONES if percentage >= m)


def notified_for(data: AppData, allocation_id: str) -> tuple[int, ...]:
    """Milestones already announced for this allocation, today."""
    return tuple(
        sorted(
            n.milestone
            for n in data.notified
            if n.allocation_id == allocation_id
            and n.day_anchor == data.current.day_anchor
        )
    )


def pending_milestones(
    data: AppData, allocation_id: str, now: datetime
) -> tuple[int, ...]:
    """Milestones reached but not yet announced."""
    allocation = next(
        (a for a in visible_allocations(data) if a.id == allocation_id), None
    )
    if allocation is None:
        return ()

    target = allocation.daily_target_seconds
    if target <= 0:
        return ()

    tracked = tracked_seconds(data, allocation_id, now)
    reached = milestones_reached(tracked / target * 100)
    already = notified_for(data, allocation_id)
    return tuple(m for m in reached if m not in already)


def record_milestones(
    data: AppData, allocation_id: str, milestones: tuple[int, ...]
) -> AppData:
    """Mark milestones announced, so they never fire again today."""
    new = tuple(
        model.NotifiedMilestone(
            allocation_id=allocation_id,
            day_anchor=data.current.day_anchor,
            milestone=m,
        )
        for m in milestones
    )
    return model.replace(data, notified=data.notified + new)


def _duration(seconds: int) -> str:
    """`3h`, `2h 24m`, `9m` — the same shape the dashboard shows."""
    total = max(0, seconds)
    hours, minutes = divmod(total // 60, 60)
    if hours == 0:
        return f"{minutes}m"
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"


def milestone_message(allocation: Allocation, milestone: int, tracked: int) -> str:
    """The banner text for a milestone (PRD §13.1, §13.2)."""
    if milestone == 100:
        return (
            f"{allocation.name} allocation completed — you've reached your "
            f"{_duration(allocation.daily_target_seconds)} goal. "
            "Keep going if you want."
        )
    remaining = allocation.daily_target_seconds - tracked
    return f"{allocation.name} is almost complete — {_duration(remaining)} remaining."


def settle_milestones(data: AppData, now: datetime) -> AppData:
    """Record every reached milestone without announcing any of them.

    Used where a threshold was crossed by something other than accumulating
    time -- a target edit, or crash recovery closing a session at `now`. The
    user either just made that change or was not there to see it, so a banner
    would be noise (PRD §13).
    """
    for allocation in visible_allocations(data):
        pending = pending_milestones(data, allocation.id, now)
        if pending:
            data = record_milestones(data, allocation.id, pending)
    return data


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
        days_tracked=days_tracked(data, allocation.id),
        notified_milestones=notified_for(data, allocation.id),
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
        break_started_at=(
            data.current.break_started_at.isoformat()
            if data.current.break_started_at is not None
            else None
        ),
        user_name=data.preferences.name,
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
            break_started_at=None,
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
            break_started_at=None,
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
        break_started_at=None,
    )
    if reference != today:
        current = model.replace(current, day_anchor=today)

    # Crash recovery just closed any open session at `now`, which can push an
    # allocation past a threshold while the app was not running. Record those
    # silently: a banner about something that happened hours ago is noise.
    return settle_milestones(model.replace(data, current=current), now)


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
    # Break remembers what to resume. Left pointing at an archived allocation,
    # toggling Break would activate something the dashboard filters out --
    # Active, accumulating, and invisible.
    current = data.current
    if current.pre_break_allocation_id == allocation_id:
        current = model.replace(current, pre_break_allocation_id=None)

    return model.replace(
        data,
        current=current,
        allocations=tuple(
            model.replace(a, archived_at=now) if a.id == allocation_id else a
            for a in data.allocations
        ),
    )
