"""Serialising the dashboard, and the methods the frontend calls."""

import json
from datetime import datetime, timezone

from nebula import app as nebula_app
from nebula import model, rules
from nebula.tracker import Tracker

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _view() -> model.DashboardView:
    data = model.empty_data(NOW)
    data = rules.add_allocation(data, "Work", 3 * 3600, NOW, "alloc-1")
    return rules.build_dashboard(data, NOW)


def test_view_to_dict_uses_camel_case_keys():
    payload = model.view_to_dict(_view())
    assert set(payload) == {
        "status",
        "dayAnchor",
        "dayEndDate",
        "allocations",
        "totalTrackedSeconds",
        "totalTargetSeconds",
        "breakStartedAt",
        "userName",
    }


def test_view_to_dict_serialises_an_allocation():
    payload = model.view_to_dict(_view())
    assert payload["allocations"][0] == {
        "id": "alloc-1",
        "name": "Work",
        "dailyTargetSeconds": 10800,
        "trackedSeconds": 0,
        "state": "NOT_STARTED",
        "percentage": 0.0,
        "remainingSeconds": 10800,
        "activeSince": None,
        "daysTracked": 0,
        "notifiedMilestones": [],
    }


def test_view_to_dict_is_json_serialisable():
    """js_api return values cross the bridge as JSON."""
    json.dumps(model.view_to_dict(_view()))


def test_activate_returns_the_updated_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    api.tracker.add_allocation("Work", 3600, NOW)
    # Tracker generates the id, so read it back rather than inventing one.
    created = model.view_to_dict(api.tracker.view(NOW))["allocations"][0]
    payload = api.activate(created["id"])
    assert payload["allocations"][0]["state"] == "ACTIVE"
    assert payload["status"] == "ACTIVE"


def test_toggle_break_returns_a_break_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    api.tracker.add_allocation("Work", 3600, NOW)
    payload = api.toggle_break()
    assert payload["status"] == "BREAK"
    assert payload["breakStartedAt"] is not None


def test_complete_day_returns_a_neutral_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    api.tracker.add_allocation("Work", 3600, NOW)
    payload = api.complete_day()
    assert payload["status"] == "NEUTRAL"


def test_resume_returns_a_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    payload = api.resume()
    assert payload["status"] == "NEUTRAL"
    assert payload["allocations"] == []
