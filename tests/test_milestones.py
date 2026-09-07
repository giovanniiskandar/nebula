"""Which milestones are due, and making sure each fires only once."""

from datetime import datetime, timedelta, timezone

from nebula import model, rules

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _data() -> model.AppData:
    data = model.empty_data(NOW)
    return rules.add_allocation(data, "Work", 3600, NOW, "alloc-1")


def _tracked(minutes: int) -> model.AppData:
    """An allocation holding `minutes` of its one-hour target, not Active."""
    data = rules.activate(_data(), "alloc-1", NOW, "s1")
    return rules.toggle_break(data, NOW + timedelta(minutes=minutes), "s2")


def test_no_milestones_below_95_percent():
    assert rules.milestones_reached(94.9) == ()


def test_95_at_the_threshold():
    assert rules.milestones_reached(95.0) == (95,)


def test_both_at_100():
    assert rules.milestones_reached(100.0) == (95, 100)


def test_both_when_past_100():
    assert rules.milestones_reached(240.0) == (95, 100)


def test_pending_reports_what_has_not_fired():
    data = _tracked(57)  # 57 of 60 minutes = 95%
    assert rules.pending_milestones(data, "alloc-1", NOW + timedelta(minutes=57)) == (95,)


def test_recording_stops_it_pending():
    at = NOW + timedelta(minutes=57)
    data = rules.record_milestones(_tracked(57), "alloc-1", (95,))
    assert rules.pending_milestones(data, "alloc-1", at) == ()


def test_a_new_day_re_arms_both():
    """Milestones are keyed by day anchor, so a rollover re-arms them."""
    data = rules.record_milestones(_tracked(60), "alloc-1", (95, 100))
    tomorrow = NOW + timedelta(days=1)
    data = rules.resume(data, tomorrow)
    data = rules.activate(data, "alloc-1", tomorrow, "s3")
    data = rules.toggle_break(data, tomorrow + timedelta(minutes=60), "s4")
    assert rules.pending_milestones(data, "alloc-1", tomorrow + timedelta(minutes=60)) == (95, 100)


def test_milestones_round_trip_through_json():
    data = rules.record_milestones(_tracked(60), "alloc-1", (95, 100))
    restored = model.from_dict(model.to_dict(data))
    assert restored.notified == data.notified


def test_data_files_written_before_this_field_still_load():
    raw = model.to_dict(_data())
    del raw["notified"]
    assert model.from_dict(raw).notified == ()


def test_the_view_reports_fired_milestones():
    at = NOW + timedelta(minutes=57)
    data = rules.record_milestones(_tracked(57), "alloc-1", (95,))
    view = rules.build_dashboard(data, at)
    assert view.allocations[0].notified_milestones == (95,)


def test_settle_records_crossed_milestones_without_firing():
    """Unit test of the helper. Wiring it to an edit is Task 3."""
    at = NOW + timedelta(minutes=30)
    data = _tracked(30)  # 30 of 60 minutes = 50%
    # Halving the target takes it straight to 100%.
    data = rules.edit_allocation(data, "alloc-1", "Work", 1800)
    data = rules.settle_milestones(data, at)
    assert rules.pending_milestones(data, "alloc-1", at) == ()


def test_a_resume_point_settles_milestones_silently():
    """Crash recovery can push past a threshold while the app was closed."""
    at = NOW + timedelta(minutes=57)
    data = rules.activate(_data(), "alloc-1", NOW, "s1")
    data = rules.resume(data, at)
    assert rules.pending_milestones(data, "alloc-1", at) == ()
