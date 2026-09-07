"""The data layer's public surface.

This is the only module that generates ids. `now` still arrives from the
caller, so the layer stays testable end to end without patching a clock —
`__main__` is where real time enters the program.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from nebula import rules, store
from nebula.model import AppData, DashboardView


class Tracker:
    """Loads, applies a rule, saves, and returns what the UI should render."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: AppData | None = None

    def _load(self, now: datetime) -> AppData:
        if self._data is None:
            self._data = store.load(self._path, now)
        return self._data

    def _commit(self, data: AppData, now: datetime) -> DashboardView:
        self._data = data
        store.save(data, self._path)
        return rules.build_dashboard(data, now)

    def open(self, now: datetime) -> DashboardView:
        """A resume point (PRD §17): date check, and recover a crashed session."""
        return self._commit(rules.resume(self._load(now), now), now)

    def view(self, now: datetime) -> DashboardView:
        return rules.build_dashboard(self._load(now), now)

    def activate(self, allocation_id: str, now: datetime) -> DashboardView:
        data = rules.activate(self._load(now), allocation_id, now, uuid4().hex)
        return self._commit(data, now)

    def toggle_break(self, now: datetime) -> DashboardView:
        data = rules.toggle_break(self._load(now), now, uuid4().hex)
        return self._commit(data, now)

    def complete_day(self, now: datetime) -> DashboardView:
        return self._commit(rules.complete_day(self._load(now), now), now)

    def set_name(self, name: str, now: datetime) -> DashboardView:
        """The *user's* name, for the recap (PRD §12, §18.2)."""
        return self._commit(rules.set_name(self._load(now), name), now)

    def add_allocation(
        self, name: str, target_seconds: int, now: datetime
    ) -> DashboardView:
        data = rules.add_allocation(
            self._load(now), name, target_seconds, now, uuid4().hex
        )
        return self._commit(data, now)

    def edit_allocation(
        self, allocation_id: str, name: str, target_seconds: int, now: datetime
    ) -> DashboardView:
        data = rules.edit_allocation(
            self._load(now), allocation_id, name, target_seconds
        )
        return self._commit(data, now)

    def delete_allocation(self, allocation_id: str, now: datetime) -> DashboardView:
        data = rules.delete_allocation(self._load(now), allocation_id, now)
        return self._commit(data, now)
