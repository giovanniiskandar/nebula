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
