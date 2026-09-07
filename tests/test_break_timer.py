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


def test_completing_the_day_while_on_break_clears_the_start_time():
    """complete_day leaves BREAK, so the timer must not survive it."""
    data = rules.toggle_break(_data(), NOW, "sess-1")
    data = rules.complete_day(data, NOW + timedelta(minutes=5))
    assert data.current.status == "NEUTRAL"
    assert data.current.break_started_at is None


def test_reopening_while_on_break_clears_the_start_time():
    """A resume point leaves BREAK too (PRD §17)."""
    data = rules.toggle_break(_data(), NOW, "sess-1")
    data = rules.resume(data, NOW + timedelta(minutes=5))
    assert data.current.status == "NEUTRAL"
    assert data.current.break_started_at is None
