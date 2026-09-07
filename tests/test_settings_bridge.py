"""The Settings methods the frontend calls."""

import json
from datetime import datetime, timezone

from nebula import app as nebula_app
from nebula.tracker import Tracker

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _api(tmp_path) -> nebula_app.Api:
    return nebula_app.Api(Tracker(tmp_path / "data.json"))


def test_add_allocation_returns_a_view_containing_it(tmp_path):
    payload = _api(tmp_path).add_allocation("Work", 3 * 3600)
    assert [a["name"] for a in payload["allocations"]] == ["Work"]
    assert payload["allocations"][0]["dailyTargetSeconds"] == 10800


def test_edit_allocation_changes_name_and_target(tmp_path):
    api = _api(tmp_path)
    created = api.add_allocation("Work", 3600)["allocations"][0]
    payload = api.edit_allocation(created["id"], "Deep Work", 2 * 3600)
    assert payload["allocations"][0]["name"] == "Deep Work"
    assert payload["allocations"][0]["dailyTargetSeconds"] == 7200


def test_delete_allocation_removes_it_from_the_view(tmp_path):
    api = _api(tmp_path)
    created = api.add_allocation("Work", 3600)["allocations"][0]
    payload = api.delete_allocation(created["id"])
    assert payload["allocations"] == []


def test_set_name_appears_on_the_view(tmp_path):
    payload = _api(tmp_path).set_name("Alex")
    assert payload["userName"] == "Alex"


def test_set_name_blank_clears_it(tmp_path):
    api = _api(tmp_path)
    api.set_name("Alex")
    assert api.set_name("")["userName"] is None


def test_every_settings_method_returns_json(tmp_path):
    """js_api return values cross the bridge as JSON."""
    api = _api(tmp_path)
    created = api.add_allocation("Work", 3600)["allocations"][0]
    for payload in (
        api.edit_allocation(created["id"], "Work", 7200),
        api.set_name("Alex"),
        api.delete_allocation(created["id"]),
    ):
        json.dumps(payload)


def test_the_view_carries_days_tracked(tmp_path):
    payload = _api(tmp_path).add_allocation("Work", 3600)
    assert payload["allocations"][0]["daysTracked"] == 0
