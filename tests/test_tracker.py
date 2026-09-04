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
