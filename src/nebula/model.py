"""The persisted data model and its JSON representation.

Every dataclass here is frozen. Rules return new instances rather than
mutating, which is what lets a rule be tested by comparing values.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any, Literal

SCHEMA_VERSION = 1

Status = Literal["ACTIVE", "BREAK", "NEUTRAL"]
AllocationState = Literal["NOT_STARTED", "ACTIVE", "STALE"]


@dataclass(frozen=True)
class Allocation:
    id: str
    name: str
    daily_target_seconds: int
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True)
class TimeSession:
    id: str
    allocation_id: str
    started_at: datetime
    day_anchor: date
    ended_at: datetime | None = None


@dataclass(frozen=True)
class Completion:
    day_anchor: date
    completed_at: datetime


@dataclass(frozen=True)
class CurrentState:
    status: Status
    day_anchor: date
    active_allocation_id: str | None = None
    pre_break_allocation_id: str | None = None


@dataclass(frozen=True)
class Preferences:
    name: str | None = None


@dataclass(frozen=True)
class AppData:
    version: int
    current: CurrentState
    allocations: tuple[Allocation, ...]
    sessions: tuple[TimeSession, ...]
    completions: tuple[Completion, ...]
    preferences: Preferences


@dataclass(frozen=True)
class AllocationView:
    id: str
    name: str
    daily_target_seconds: int
    tracked_seconds: int
    state: AllocationState
    percentage: float
    remaining_seconds: int
    active_since: str | None


@dataclass(frozen=True)
class DashboardView:
    status: Status
    day_anchor: str
    day_end_date: str
    allocations: tuple[AllocationView, ...]
    total_tracked_seconds: int
    total_target_seconds: int


def local_date(moment: datetime) -> date:
    """The local calendar date of an instant.

    A "day" is a human, local concept even though instants are absolute.
    """
    return moment.astimezone().date()


def empty_data(now: datetime) -> AppData:
    """The documented first-launch state: no allocations, neutral, today."""
    return AppData(
        version=SCHEMA_VERSION,
        current=CurrentState(status="NEUTRAL", day_anchor=local_date(now)),
        allocations=(),
        sessions=(),
        completions=(),
        preferences=Preferences(),
    )


def _dt(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def to_dict(data: AppData) -> dict[str, Any]:
    return {
        "version": data.version,
        "current": {
            "status": data.current.status,
            "dayAnchor": data.current.day_anchor.isoformat(),
            "activeAllocationId": data.current.active_allocation_id,
            "preBreakAllocationId": data.current.pre_break_allocation_id,
        },
        "allocations": [
            {
                "id": a.id,
                "name": a.name,
                "dailyTargetSeconds": a.daily_target_seconds,
                "createdAt": _dt(a.created_at),
                "archivedAt": _dt(a.archived_at),
            }
            for a in data.allocations
        ],
        "sessions": [
            {
                "id": s.id,
                "allocationId": s.allocation_id,
                "startedAt": _dt(s.started_at),
                "endedAt": _dt(s.ended_at),
                "dayAnchor": s.day_anchor.isoformat(),
            }
            for s in data.sessions
        ],
        "completions": [
            {
                "dayAnchor": c.day_anchor.isoformat(),
                "completedAt": _dt(c.completed_at),
            }
            for c in data.completions
        ],
        "preferences": {"name": data.preferences.name},
    }


def from_dict(raw: dict[str, Any]) -> AppData:
    current = raw["current"]
    return AppData(
        version=raw["version"],
        current=CurrentState(
            status=current["status"],
            day_anchor=date.fromisoformat(current["dayAnchor"]),
            active_allocation_id=current["activeAllocationId"],
            pre_break_allocation_id=current["preBreakAllocationId"],
        ),
        allocations=tuple(
            Allocation(
                id=a["id"],
                name=a["name"],
                daily_target_seconds=a["dailyTargetSeconds"],
                created_at=_parse_dt(a["createdAt"]),
                archived_at=_parse_dt(a["archivedAt"]),
            )
            for a in raw["allocations"]
        ),
        sessions=tuple(
            TimeSession(
                id=s["id"],
                allocation_id=s["allocationId"],
                started_at=_parse_dt(s["startedAt"]),
                ended_at=_parse_dt(s["endedAt"]),
                day_anchor=date.fromisoformat(s["dayAnchor"]),
            )
            for s in raw["sessions"]
        ),
        completions=tuple(
            Completion(
                day_anchor=date.fromisoformat(c["dayAnchor"]),
                completed_at=_parse_dt(c["completedAt"]),
            )
            for c in raw["completions"]
        ),
        preferences=Preferences(name=raw["preferences"]["name"]),
    )


__all__ = [
    "SCHEMA_VERSION",
    "Allocation",
    "AllocationState",
    "AllocationView",
    "AppData",
    "Completion",
    "CurrentState",
    "DashboardView",
    "Preferences",
    "Status",
    "TimeSession",
    "empty_data",
    "from_dict",
    "local_date",
    "replace",
    "to_dict",
]
