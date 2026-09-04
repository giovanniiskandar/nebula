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
