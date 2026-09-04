"""Path resolution and atomic JSON persistence."""

import json
from datetime import datetime, timezone

import pytest

from nebula import model, store


def utc(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_production_path_is_in_application_support():
    path = store.data_path(dev=False)
    assert path.parent.name == "Nebula"
    assert "Application Support" in str(path)
    assert path.name == "data.json"


def test_dev_path_is_a_separate_file_beside_it():
    """Hacking on the app must not be able to destroy real tracked time."""
    assert store.data_path(dev=True).name == "data.dev.json"
    assert store.data_path(dev=True).parent == store.data_path(dev=False).parent


def test_load_of_a_missing_file_returns_the_empty_state(tmp_path):
    data = store.load(tmp_path / "absent.json", utc(2026, 9, 1, 12))
    assert data.allocations == ()
    assert data.current.status == "NEUTRAL"


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "data.json"
    original = model.empty_data(utc(2026, 9, 1, 12))
    original = model.replace(
        original,
        allocations=(model.Allocation("a1", "Work", 10800, utc(2026, 9, 1, 8)),),
    )
    store.save(original, path)
    assert store.load(path, utc(2026, 9, 1, 13)) == original


def test_save_creates_the_directory(tmp_path):
    path = tmp_path / "nested" / "deeper" / "data.json"
    store.save(model.empty_data(utc(2026, 9, 1, 12)), path)
    assert path.exists()


def test_a_corrupt_file_raises_rather_than_starting_fresh(tmp_path):
    """Silently discarding a user's history is worse than refusing to start."""
    path = tmp_path / "data.json"
    path.write_text("{ this is not json")
    with pytest.raises(store.DataFileCorrupt):
        store.load(path, utc(2026, 9, 1, 12))


def test_the_previous_file_survives_a_failed_write(tmp_path):
    """A crash mid-write must not truncate the one irreplaceable file."""
    path = tmp_path / "data.json"
    good = model.empty_data(utc(2026, 9, 1, 12))
    store.save(good, path)

    class Unserialisable:
        pass

    broken = model.replace(good, preferences=model.Preferences(name=Unserialisable()))
    with pytest.raises(TypeError):
        store.save(broken, path)

    assert store.load(path, utc(2026, 9, 1, 13)) == good


def test_no_temp_files_are_left_behind(tmp_path):
    path = tmp_path / "data.json"
    store.save(model.empty_data(utc(2026, 9, 1, 12)), path)
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_the_file_records_its_schema_version(tmp_path):
    path = tmp_path / "data.json"
    store.save(model.empty_data(utc(2026, 9, 1, 12)), path)
    assert json.loads(path.read_text())["version"] == 1
