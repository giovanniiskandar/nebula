"""Firing milestones, and the exact copy the PRD specifies."""

from datetime import datetime, timedelta, timezone

from nebula import app as nebula_app
from nebula import model, rules
from nebula.tracker import Tracker

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _allocation(name: str = "Work", target: int = 3 * 3600) -> model.Allocation:
    return model.Allocation(
        id="alloc-1", name=name, daily_target_seconds=target, created_at=NOW
    )


def test_the_95_message_matches_the_prd():
    # 2h51m of 3h leaves 9 minutes.
    message = rules.milestone_message(_allocation(), 95, 2 * 3600 + 51 * 60)
    assert message == "Work is almost complete — 9m remaining."


def test_the_100_message_matches_the_prd():
    message = rules.milestone_message(_allocation(), 100, 3 * 3600)
    assert message == (
        "Work allocation completed — you've reached your 3h goal. "
        "Keep going if you want."
    )


def _tracker_at(tmp_path, seconds: int) -> tuple[Tracker, str, datetime]:
    """A tracker whose only allocation holds `seconds` of a one-hour target."""
    tracker = Tracker(tmp_path / "data.json")
    view = tracker.add_allocation("Work", 3600, NOW)
    allocation_id = view.allocations[0].id
    tracker.activate(allocation_id, NOW)
    at = NOW + timedelta(seconds=seconds)
    return tracker, allocation_id, at


def test_crossing_95_sends_one_notification(tmp_path):
    tracker, allocation_id, at = _tracker_at(tmp_path, 57 * 60)
    sent: list[tuple[str, str]] = []
    tracker.check_milestones(allocation_id, at, send=lambda t, m: sent.append((t, m)))
    assert len(sent) == 1
    assert "almost complete" in sent[0][1]


def test_checking_again_sends_nothing(tmp_path):
    tracker, allocation_id, at = _tracker_at(tmp_path, 57 * 60)
    sent: list[tuple[str, str]] = []

    def record(title, message):
        sent.append((title, message))
        return True

    tracker.check_milestones(allocation_id, at, send=record)
    tracker.check_milestones(allocation_id, at, send=record)
    assert len(sent) == 1


def test_crossing_100_sends_both_once(tmp_path):
    tracker, allocation_id, at = _tracker_at(tmp_path, 3600)
    sent: list[tuple[str, str]] = []
    tracker.check_milestones(allocation_id, at, send=lambda t, m: sent.append((t, m)))
    assert len(sent) == 2


def test_a_failed_send_still_records(tmp_path):
    """A milestone announced into a void is still announced."""
    tracker, allocation_id, at = _tracker_at(tmp_path, 3600)
    view = tracker.check_milestones(allocation_id, at, send=lambda t, m: False)
    assert view.allocations[0].notified_milestones == (95, 100)


def test_editing_a_target_past_a_milestone_never_fires(tmp_path):
    """Only accumulating time fires; a target edit must be silent."""
    tracker, allocation_id, at = _tracker_at(tmp_path, 30 * 60)  # 50% of an hour
    tracker.edit_allocation(allocation_id, "Work", 1800, at)  # now 100%

    sent: list[tuple[str, str]] = []
    view = tracker.check_milestones(
        allocation_id, at, send=lambda t, m: sent.append((t, m))
    )
    assert sent == []
    assert view.allocations[0].notified_milestones == (95, 100)


def test_the_bridge_method_returns_a_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    created = api.add_allocation("Work", 3600)["allocations"][0]
    payload = api.check_milestones(created["id"])
    assert payload["allocations"][0]["notifiedMilestones"] == []
