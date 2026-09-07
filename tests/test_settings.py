"""The user's name, per-allocation day counts, and deleting safely."""

from datetime import datetime, timedelta, timezone

from nebula import model, rules

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _data() -> model.AppData:
    data = model.empty_data(NOW)
    data = rules.add_allocation(data, "Work", 3 * 3600, NOW, "alloc-1")
    return rules.add_allocation(data, "Learning", 2 * 3600, NOW, "alloc-2")


def test_set_name_stores_the_users_name():
    data = rules.set_name(_data(), "Alex")
    assert data.preferences.name == "Alex"


def test_set_name_stores_none_for_a_blank_name():
    """Cleared and never-set are one state, not two."""
    data = rules.set_name(_data(), "Alex")
    data = rules.set_name(data, "   ")
    assert data.preferences.name is None


def test_set_name_trims_surrounding_space():
    data = rules.set_name(_data(), "  Alex  ")
    assert data.preferences.name == "Alex"


def test_the_dashboard_exposes_the_users_name():
    data = rules.set_name(_data(), "Alex")
    assert rules.build_dashboard(data, NOW).user_name == "Alex"


def test_the_users_name_round_trips_through_json():
    data = rules.set_name(_data(), "Alex")
    assert model.from_dict(model.to_dict(data)).preferences.name == "Alex"


def test_days_tracked_is_zero_without_history():
    assert rules.days_tracked(_data(), "alloc-1") == 0


def test_days_tracked_counts_days_not_sessions():
    """Switching away and back three times in a day is one day."""
    data = _data()
    for index in range(3):
        at = NOW + timedelta(hours=index)
        data = rules.activate(data, "alloc-1", at, f"s{index}")
        data = rules.activate(data, "alloc-2", at + timedelta(minutes=30), f"o{index}")
    assert rules.days_tracked(data, "alloc-1") == 1


def test_days_tracked_counts_each_distinct_day():
    data = _data()
    data = rules.activate(data, "alloc-1", NOW, "s1")
    data = rules.resume(data, NOW + timedelta(days=1))
    data = rules.activate(data, "alloc-1", NOW + timedelta(days=1), "s2")
    assert rules.days_tracked(data, "alloc-1") == 2


def test_the_dashboard_exposes_days_tracked():
    data = rules.activate(_data(), "alloc-1", NOW, "s1")
    view = rules.build_dashboard(data, NOW)
    assert view.allocations[0].days_tracked == 1


def test_deleting_the_pre_break_allocation_clears_the_resume_target():
    """Otherwise toggling Break resumes an archived allocation invisibly."""
    data = rules.activate(_data(), "alloc-1", NOW, "s1")
    data = rules.toggle_break(data, NOW + timedelta(minutes=5), "s2")
    assert data.current.pre_break_allocation_id == "alloc-1"

    data = rules.delete_allocation(data, "alloc-1", NOW + timedelta(minutes=6))
    assert data.current.pre_break_allocation_id is None

    data = rules.toggle_break(data, NOW + timedelta(minutes=7), "s3")
    assert data.current.active_allocation_id is None
    assert data.current.status == "NEUTRAL"
