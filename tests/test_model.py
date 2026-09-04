"""The data model and its JSON representation."""

from datetime import date, datetime, timedelta, timezone

from nebula import model


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_empty_data_starts_neutral_with_todays_anchor():
    now = utc(2026, 9, 1, 12)
    data = model.empty_data(now)
    assert data.version == 1
    assert data.current.status == "NEUTRAL"
    assert data.current.active_allocation_id is None
    assert data.current.day_anchor == now.astimezone().date()
    assert data.allocations == ()
    assert data.sessions == ()
    assert data.completions == ()


def test_round_trip_preserves_every_field():
    data = model.AppData(
        version=1,
        current=model.CurrentState(
            status="BREAK",
            day_anchor=date(2026, 9, 1),
            active_allocation_id=None,
            pre_break_allocation_id="a1",
        ),
        allocations=(
            model.Allocation(
                id="a1",
                name="Work",
                daily_target_seconds=10800,
                created_at=utc(2026, 9, 1, 8),
                archived_at=None,
            ),
            model.Allocation(
                id="a2",
                name="Learning",
                daily_target_seconds=7200,
                created_at=utc(2026, 9, 1, 8),
                archived_at=utc(2026, 9, 1, 9),
            ),
        ),
        sessions=(
            model.TimeSession(
                id="s1",
                allocation_id="a1",
                started_at=utc(2026, 9, 1, 9),
                ended_at=utc(2026, 9, 1, 10, 30),
                day_anchor=date(2026, 9, 1),
            ),
            model.TimeSession(
                id="s2",
                allocation_id="a1",
                started_at=utc(2026, 9, 1, 11),
                ended_at=None,
                day_anchor=date(2026, 9, 1),
            ),
        ),
        completions=(
            model.Completion(
                day_anchor=date(2026, 8, 31),
                completed_at=utc(2026, 9, 1, 5),
            ),
        ),
        preferences=model.Preferences(name="Gio"),
    )

    assert model.from_dict(model.to_dict(data)) == data


def test_to_dict_is_json_serialisable():
    import json

    data = model.empty_data(utc(2026, 9, 1, 12))
    assert json.loads(json.dumps(model.to_dict(data))) == model.to_dict(data)


def test_timestamps_survive_as_aware_utc():
    data = model.empty_data(utc(2026, 9, 1, 12))
    data = model.AppData(
        version=data.version,
        current=data.current,
        allocations=(
            model.Allocation(
                id="a1",
                name="Work",
                daily_target_seconds=60,
                created_at=utc(2026, 9, 1, 8),
            ),
        ),
        sessions=(),
        completions=(),
        preferences=data.preferences,
    )
    restored = model.from_dict(model.to_dict(data))
    created = restored.allocations[0].created_at
    assert created.tzinfo is not None
    assert created.utcoffset() == timedelta(0)
