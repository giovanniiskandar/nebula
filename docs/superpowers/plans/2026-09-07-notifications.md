# Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tell the user when an allocation reaches 95% and 100% of its daily target, once each per day, without ever interrupting them.

**Architecture:** Nothing in Python ticks, so React notices a crossing during its existing one-second tick and Python decides whether it is real. Fired milestones are persisted per allocation per day and surfaced on the view, which stops React asking again. Delivery shells out to `osascript` with the message passed as `argv`.

**Tech Stack:** Python 3.13, pywebview 6.2.1, React 19, TypeScript, vitest, pytest, `osascript`.

**Spec:** `docs/superpowers/specs/2026-09-07-notifications-design.md`

## Global Constraints

- Node `>=24 <25`. Every frontend command must be preceded by
  `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use`.
- Milestones are exactly `95` and `100`, per allocation per day, once each.
  Nothing fires after 100% — no per-percentage spam, no overage warnings
  (PRD §13.3).
- Copy is fixed by the PRD and must match exactly:
  - 95%: `{name} is almost complete — {remaining} remaining.`
  - 100%: `{name} allocation completed — you've reached your {target} goal. Keep going if you want.`
  - Durations are formatted by the same rules the dashboard uses.
- **Only accumulating time fires a milestone.** A target edit that crosses a
  threshold records it silently and never fires, then or later.
- **The message is passed as `argv`, never interpolated into the AppleScript.**
  Allocation names are user input; interpolation is a shell-injection hole.
- A notification failure is logged and swallowed, never raised — a missing
  banner must never cost the user their tracking state.
- No `js_api` method may destroy the window (phase 2 deadlock; see `_bind_close`).
- CSS `font` shorthand must never be written with `inherit` as the family: the
  whole declaration is invalid and silently dropped (3c finding).
- Out of scope: an on/off toggle, configurable thresholds, notifying while the
  app is closed.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/nebula/notify.py` | Delivering one banner via `osascript`, safely |
| `src/nebula/model.py` | `NotifiedMilestone`; `notified` on `AppData`; `notified_milestones` on the view |
| `src/nebula/rules.py` | Which milestones are due; recording them; silent catch-up |
| `src/nebula/tracker.py` | `check_milestones` |
| `src/nebula/app.py` | The `check_milestones` bridge method |
| `frontend/src/milestones.ts` | Which thresholds a ticked allocation has passed |
| `frontend/src/App.tsx` | Asking Python when a threshold looks crossed |
| `tests/test_notify.py` | Escaping, argv, failure handling |
| `tests/test_milestones.py` | Due, recorded, not repeated, re-armed, silent |
| `frontend/src/milestones.test.ts` | The frontend's asking rule |

---

### Task 1: Delivering a banner safely

**Files:**
- Create: `src/nebula/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `notify.send(title: str, message: str) -> bool` — True when
  `osascript` exited 0, False on any failure. Never raises.
  `notify.build_command(title: str, message: str) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notify.py`:

```python
"""Delivering a banner without letting user input reach a shell."""

import subprocess
from pathlib import Path

from nebula import notify


def test_the_message_is_passed_as_argv_not_interpolated():
    """Allocation names are user input that ends up inside an AppleScript."""
    command = notify.build_command("Nebula", 'Client " & (do shell script "x") & "')
    script = command[2]
    # The script itself must be a fixed template; the text travels separately.
    assert "do shell script" not in script
    assert command[-1] == 'Client " & (do shell script "x") & "'


def test_the_script_reads_its_arguments():
    script = notify.build_command("Nebula", "hello")[2]
    assert "on run argv" in script
    assert "display notification" in script


def test_an_injection_payload_does_not_execute(tmp_path: Path):
    """The real check: run it and confirm nothing happened."""
    marker = tmp_path / "pwned"
    payload = f'Work " & (do shell script "touch {marker}") & "'
    notify.send("Nebula", payload)
    assert not marker.exists()


def test_send_reports_success():
    assert notify.send("Nebula", "a plain message") is True


def test_a_failure_is_swallowed(monkeypatch):
    """A missing banner must never cost the user their tracking state."""

    def explode(*args, **kwargs):
        raise OSError("osascript is not here")

    monkeypatch.setattr(subprocess, "run", explode)
    assert notify.send("Nebula", "anything") is False


def test_a_timeout_is_swallowed(monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="osascript", timeout=5)

    monkeypatch.setattr(subprocess, "run", hang)
    assert notify.send("Nebula", "anything") is False


def test_a_nonzero_exit_reports_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=1),
    )
    assert notify.send("Nebula", "anything") is False
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_notify.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nebula.notify'`.

- [ ] **Step 3: Write the module**

Create `src/nebula/notify.py`:

```python
"""Delivering a notification banner on macOS.

Shelling out to `osascript` keeps this dependency-free and needs no signing,
at the cost of the banner being attributed to "Script Editor" rather than
Nebula (PRD §27). Native attribution needs pyobjc and a signed app (§24).
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5

# A fixed template. The title and message arrive as arguments, so an allocation
# named `" & (do shell script "...") & "` is text rather than code.
_SCRIPT = """
on run argv
  display notification (item 2 of argv) with title (item 1 of argv)
end run
"""


def build_command(title: str, message: str) -> list[str]:
    """The argv `osascript` is invoked with.

    Separated from `send` so the escaping can be asserted without running
    anything.
    """
    return ["osascript", "-", _SCRIPT, title, message]


def send(title: str, message: str) -> bool:
    """Show a banner. Returns whether it was delivered.

    Never raises. Notifying is a side effect of a bridge call that also returns
    the dashboard, so a failure here must not cost the user their tracking
    state -- it is logged and swallowed.
    """
    try:
        result = subprocess.run(
            build_command(title, message),
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("Could not show a notification: %s", error)
        return False

    if result.returncode != 0:
        logger.warning("osascript exited %s", result.returncode)
        return False
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_notify.py -v
```

Expected: 7 passed. Two of these actually invoke `osascript`, so **a banner
will appear on screen** during the run — that is expected, and is the only
part of this phase a machine can confirm at all.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Deliver notification banners through osascript

The message is passed as argv against a fixed script template rather
than interpolated into it. Allocation names are user input that ends up
inside an AppleScript, so interpolation is a shell-injection hole: a
name of the form \" & (do shell script \"...\") & \" would execute. A
test runs that payload and asserts the file it would create does not
exist.

Failures are logged and swallowed. Notifying is a side effect of a
bridge call that also returns the dashboard, and a missing banner must
never cost the user their tracking state."
```

---

### Task 2: Milestones in the data layer

**Files:**
- Modify: `src/nebula/model.py`, `src/nebula/rules.py`
- Test: `tests/test_milestones.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `model.NotifiedMilestone(allocation_id, day_anchor, milestone)`;
  `AppData.notified: tuple[NotifiedMilestone, ...]`;
  `AllocationView.notified_milestones: tuple[int, ...]` serialised as
  `notifiedMilestones`; `rules.MILESTONES = (95, 100)`;
  `rules.milestones_reached(percentage) -> tuple[int, ...]`;
  `rules.pending_milestones(data, allocation_id, now) -> tuple[int, ...]`;
  `rules.record_milestones(data, allocation_id, milestones) -> AppData`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_milestones.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_milestones.py -v
```

Expected: FAIL — `AttributeError: module 'nebula.rules' has no attribute 'milestones_reached'`.

- [ ] **Step 3: Add the model**

In `src/nebula/model.py`, after `Completion`:

```python
@dataclass(frozen=True)
class NotifiedMilestone:
    """A milestone already announced, so it is never announced twice.

    Keyed by day anchor, so a new day re-arms every milestone with no cleanup
    step -- the same mechanism that makes tracked time "reset" (PRD §17).
    """

    allocation_id: str
    day_anchor: date
    milestone: int
```

Add to `AppData`:

```python
    notified: tuple[NotifiedMilestone, ...] = ()
```

Add to `AllocationView`:

```python
    notified_milestones: tuple[int, ...] = ()
```

In `empty_data`, add `notified=(),` to the constructed `AppData`.

In `to_dict`, beside `"completions"`:

```python
        "notified": [
            {
                "allocationId": n.allocation_id,
                "dayAnchor": n.day_anchor.isoformat(),
                "milestone": n.milestone,
            }
            for n in data.notified
        ],
```

In `from_dict`, read it with `.get()` — files written before this phase have no
such key:

```python
        notified=tuple(
            NotifiedMilestone(
                allocation_id=n["allocationId"],
                day_anchor=date.fromisoformat(n["dayAnchor"]),
                milestone=n["milestone"],
            )
            for n in raw.get("notified", [])
        ),
```

In `view_to_dict`, inside the allocation dict:

```python
                "notifiedMilestones": list(a.notified_milestones),
```

Add `"NotifiedMilestone"` to `__all__`.

- [ ] **Step 4: Write the rules**

In `src/nebula/rules.py`, beside the other read helpers:

```python
MILESTONES = (95, 100)


def milestones_reached(percentage: float) -> tuple[int, ...]:
    """Every milestone this percentage has reached.

    At 100% both are reached: an allocation that jumps straight past 95 should
    not leave it armed to fire later.
    """
    return tuple(m for m in MILESTONES if percentage >= m)


def notified_for(data: AppData, allocation_id: str) -> tuple[int, ...]:
    """Milestones already announced for this allocation, today."""
    return tuple(
        sorted(
            n.milestone
            for n in data.notified
            if n.allocation_id == allocation_id
            and n.day_anchor == data.current.day_anchor
        )
    )


def pending_milestones(
    data: AppData, allocation_id: str, now: datetime
) -> tuple[int, ...]:
    """Milestones reached but not yet announced."""
    allocation = next(
        (a for a in visible_allocations(data) if a.id == allocation_id), None
    )
    if allocation is None:
        return ()

    target = allocation.daily_target_seconds
    if target <= 0:
        return ()

    tracked = tracked_seconds(data, allocation_id, now)
    reached = milestones_reached(tracked / target * 100)
    already = notified_for(data, allocation_id)
    return tuple(m for m in reached if m not in already)


def record_milestones(
    data: AppData, allocation_id: str, milestones: tuple[int, ...]
) -> AppData:
    """Mark milestones announced, so they never fire again today."""
    new = tuple(
        model.NotifiedMilestone(
            allocation_id=allocation_id,
            day_anchor=data.current.day_anchor,
            milestone=m,
        )
        for m in milestones
    )
    return model.replace(data, notified=data.notified + new)


def settle_milestones(data: AppData, now: datetime) -> AppData:
    """Record every reached milestone without announcing any of them.

    Used where a threshold was crossed by something other than accumulating
    time -- a target edit, or crash recovery closing a session at `now`. The
    user either just made that change or was not there to see it, so a banner
    would be noise (spec §2, §6).
    """
    for allocation in visible_allocations(data):
        pending = pending_milestones(data, allocation.id, now)
        if pending:
            data = record_milestones(data, allocation.id, pending)
    return data
```

- [ ] **Step 5: Settle at a resume point**

In `rules.resume`, immediately before the final `return`:

```python
    data = model.replace(data, current=current)
    return settle_milestones(data, now)
```

replacing `return model.replace(data, current=current)`.

- [ ] **Step 6: Populate the view**

In `build_allocation_view`, add to the returned `AllocationView`:

```python
        notified_milestones=notified_for(data, allocation.id),
```

- [ ] **Step 7: Run the tests**

```bash
uv run pytest tests/test_milestones.py -v
```

Expected: 12 passed.

- [ ] **Step 8: Run the whole suite**

```bash
uv run pytest -q
```

Expected: all pass. `tests/test_bridge.py` asserts the exact allocation payload
shape, so add `"notifiedMilestones": []` to that expected dict rather than
loosening the assertion — that strictness is what catches a changed payload.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Record which milestones have been announced

NotifiedMilestone is keyed by day anchor, so a new day re-arms both
milestones with no cleanup step -- the same mechanism that makes tracked
time reset without deleting anything.

settle_milestones records reached milestones without announcing them,
for the cases where a threshold was crossed by something other than
accumulating time: a target edit, which the user just made and can see,
and crash recovery closing a session at the current time, which happened
while the app was closed. A resume point settles.

from_dict reads the key with .get() so data files written before this
field still load."
```

---

### Task 3: Firing them

**Files:**
- Modify: `src/nebula/tracker.py`, `src/nebula/app.py`
- Test: `tests/test_notifications_bridge.py`

**Interfaces:**
- Consumes: `notify.send` from Task 1; the rules from Task 2.
- Produces: `Tracker.check_milestones(allocation_id, now, send) -> DashboardView`;
  `Api.check_milestones(allocation_id: str) -> dict`;
  `rules.milestone_message(allocation, milestone, tracked_seconds) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notifications_bridge.py`:

```python
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
    record = lambda t, m: sent.append((t, m))
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


def test_the_bridge_method_returns_a_view(tmp_path):
    api = nebula_app.Api(Tracker(tmp_path / "data.json"))
    created = api.add_allocation("Work", 3600)["allocations"][0]
    payload = api.check_milestones(created["id"])
    assert payload["allocations"][0]["notifiedMilestones"] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_notifications_bridge.py -v
```

Expected: FAIL — `AttributeError: module 'nebula.rules' has no attribute 'milestone_message'`.

- [ ] **Step 3: Write the message**

In `src/nebula/rules.py`, beside the other milestone helpers:

```python
def _duration(seconds: int) -> str:
    """`3h`, `2h 24m`, `9m` — the same shape the dashboard shows."""
    total = max(0, seconds)
    hours, minutes = divmod(total // 60, 60)
    if hours == 0:
        return f"{minutes}m"
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"


def milestone_message(
    allocation: Allocation, milestone: int, tracked: int
) -> str:
    """The banner text for a milestone (PRD §13.1, §13.2)."""
    if milestone == 100:
        return (
            f"{allocation.name} allocation completed — you've reached your "
            f"{_duration(allocation.daily_target_seconds)} goal. "
            "Keep going if you want."
        )
    remaining = allocation.daily_target_seconds - tracked
    return f"{allocation.name} is almost complete — {_duration(remaining)} remaining."
```

- [ ] **Step 4: Add the tracker method**

In `src/nebula/tracker.py`, add the imports and the method:

```python
from collections.abc import Callable

from nebula import notify, rules, store
```

```python
    def check_milestones(
        self,
        allocation_id: str,
        now: datetime,
        send: Callable[[str, str], bool] = notify.send,
    ) -> DashboardView:
        """Announce any milestone reached but not yet announced.

        `send` is injected so the rules can be tested without a banner
        appearing on someone's screen.

        The milestone is recorded whether or not the banner was delivered: a
        failed notification is not a reason to try again later and startle the
        user with something that happened an hour ago.
        """
        data = self._load(now)
        pending = rules.pending_milestones(data, allocation_id, now)
        if not pending:
            return rules.build_dashboard(data, now)

        allocation = next(
            (a for a in rules.visible_allocations(data) if a.id == allocation_id),
            None,
        )
        if allocation is None:
            return rules.build_dashboard(data, now)

        tracked = rules.tracked_seconds(data, allocation_id, now)
        for milestone in pending:
            send("Nebula", rules.milestone_message(allocation, milestone, tracked))

        return self._commit(
            rules.record_milestones(data, allocation_id, pending), now
        )
```

- [ ] **Step 5: Settle milestones after a target edit**

`resume` settles (Task 2), but an edit does not, and that is the case the spec
is most explicit about: halving a target takes an allocation straight past 100%,
and React would then ask, and Python would fire. Nothing else closes this.

`rules.edit_allocation` has no `now`, so the seam is the tracker. In
`src/nebula/tracker.py`, replace `edit_allocation`:

```python
    def edit_allocation(
        self, allocation_id: str, name: str, target_seconds: int, now: datetime
    ) -> DashboardView:
        """A target change applies to today immediately (PRD §12, §19).

        Lowering a target can take an allocation past a milestone without a
        second being tracked. That must not notify -- the user just made the
        change and is looking at the number -- so anything newly crossed is
        recorded silently.
        """
        data = rules.edit_allocation(
            self._load(now), allocation_id, name, target_seconds
        )
        return self._commit(rules.settle_milestones(data, now), now)
```

Add this test to `tests/test_notifications_bridge.py`:

```python
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
```

- [ ] **Step 6: Add the bridge method**

In `src/nebula/app.py`, inside `Api`, after `set_name`:

```python
    def check_milestones(self, allocation_id: str) -> dict:
        """Announce any milestone this allocation has reached (PRD §13).

        Called by the frontend when its tick shows a threshold crossed. React
        is the trigger; the decision is made here from timestamps, so an
        early ask fires nothing.
        """
        return model.view_to_dict(
            self.tracker.check_milestones(allocation_id, self._now())
        )
```

- [ ] **Step 7: Run the tests**

```bash
uv run pytest tests/test_notifications_bridge.py -v
```

Expected: 8 passed, with no banners on screen — every test injects `send`.

- [ ] **Step 8: Run the whole suite**

```bash
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Fire milestone notifications from the bridge

check_milestones announces anything reached but not yet announced, then
records it. React calls this when its tick shows a threshold crossed;
the decision is made here from timestamps, so asking early fires
nothing.

send is injected, so the rules are tested without banners appearing on
anyone's screen. The milestone is recorded even when delivery fails: a
failed banner is not a reason to try again later and startle the user
with something that happened an hour ago."
```

---

### Task 4: Asking from the frontend

**Files:**
- Create: `frontend/src/milestones.ts`, `frontend/src/milestones.test.ts`
- Modify: `frontend/src/types.ts`, `frontend/src/bridge.ts`, `frontend/src/App.tsx`
- Modify: `docs/ROADMAP.md`, `README.md`

**Interfaces:**
- Consumes: `check_milestones` from Task 3; `tickView` from 3b.
- Produces: `milestonesToAsk(view: DashboardView): string | null` — the id of an
  allocation worth asking about, or null.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/milestones.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { milestonesToAsk } from './milestones'
import type { AllocationView, DashboardView } from './types'

function allocation(over: Partial<AllocationView> = {}): AllocationView {
  return {
    id: 'a',
    name: 'Work',
    dailyTargetSeconds: 3600,
    trackedSeconds: 1800,
    state: 'ACTIVE',
    percentage: 50,
    remainingSeconds: 1800,
    activeSince: '2026-09-07T10:00:00+00:00',
    daysTracked: 1,
    notifiedMilestones: [],
    ...over,
  }
}

function view(allocations: AllocationView[]): DashboardView {
  return {
    status: 'ACTIVE',
    dayAnchor: '2026-09-07',
    dayEndDate: '2026-09-07',
    totalTrackedSeconds: 1800,
    totalTargetSeconds: 3600,
    breakStartedAt: null,
    userName: null,
    allocations,
  }
}

describe('milestonesToAsk', () => {
  it('asks nothing below 95%', () => {
    expect(milestonesToAsk(view([allocation({ percentage: 94.9 })]))).toBeNull()
  })

  it('asks once 95% is reached', () => {
    expect(milestonesToAsk(view([allocation({ percentage: 95 })]))).toBe('a')
  })

  it('stops asking once the milestone is recorded', () => {
    // Python has fired it; the view says so, which is what closes the loop.
    const done = allocation({ percentage: 96, notifiedMilestones: [95] })
    expect(milestonesToAsk(view([done]))).toBeNull()
  })

  it('asks again at 100% even though 95 was recorded', () => {
    const done = allocation({ percentage: 100, notifiedMilestones: [95] })
    expect(milestonesToAsk(view([done]))).toBe('a')
  })

  it('stops entirely once both are recorded', () => {
    const done = allocation({ percentage: 240, notifiedMilestones: [95, 100] })
    expect(milestonesToAsk(view([done]))).toBeNull()
  })

  it('ignores allocations that are not Active', () => {
    // Only accumulating time fires a milestone.
    const stale = allocation({ state: 'STALE', percentage: 100, activeSince: null })
    expect(milestonesToAsk(view([stale]))).toBeNull()
  })

  it('picks the Active allocation out of several', () => {
    const stale = allocation({ id: 'x', state: 'STALE', percentage: 100, activeSince: null })
    const active = allocation({ id: 'y', percentage: 99 })
    expect(milestonesToAsk(view([stale, active]))).toBe('y')
  })
})
```

- [ ] **Step 2: Add the field to the types**

In `frontend/src/types.ts`, add to `AllocationView`:

```ts
  /** Milestones already announced today. Empty until Python fires one. */
  notifiedMilestones: number[]
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm test
```

Expected: FAIL — cannot resolve `./milestones`.

- [ ] **Step 4: Write it**

Create `frontend/src/milestones.ts`:

```ts
import type { DashboardView } from './types'

/** The thresholds Python will act on (PRD §13). */
const MILESTONES = [95, 100]

/**
 * The allocation worth asking Python about, or null.
 *
 * React's ticked percentage runs ahead of the figure Python last returned, so
 * it can reach a threshold a moment before Python agrees. Asking is therefore
 * bounded by what the view says has already fired: once Python records a
 * milestone, the returned view stops React asking about it again. Without
 * that, the two would loop once a second until they converged.
 *
 * Only the Active allocation is considered: a target edit can push a Stale one
 * past 100%, and that must never notify (spec §2).
 */
export function milestonesToAsk(view: DashboardView): string | null {
  for (const allocation of view.allocations) {
    if (allocation.state !== 'ACTIVE') continue
    const unfired = MILESTONES.filter(
      (m) => allocation.percentage >= m && !allocation.notifiedMilestones.includes(m),
    )
    if (unfired.length > 0) return allocation.id
  }
  return null
}
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
pnpm test
```

Expected: 39 passed (11 format, 9 tick, 12 targets, 7 here).

- [ ] **Step 6: Extend the bridge wrapper**

In `frontend/src/bridge.ts`, add to the `api` declaration:

```ts
        check_milestones?: (allocationId: string) => Promise<DashboardView>
```

and the export:

```ts
export const checkMilestones = (id: string): Promise<DashboardView> =>
  api().check_milestones!(id)
```

- [ ] **Step 7: Ask from the tick**

In `frontend/src/App.tsx`, import the helper:

```tsx
import { milestonesToAsk } from './milestones'
```

and add an effect after the tick interval. It watches the *ticked* view, so a
crossing is noticed between bridge calls:

```tsx
  useEffect(() => {
    if (ticked === null) return
    const allocationId = milestonesToAsk(ticked)
    if (allocationId === null) return
    apply(bridge.checkMilestones(allocationId))
    // `ticked` changes every second; the guard above is what stops this
    // asking repeatedly once Python has recorded the milestone.
  }, [ticked])
```

`ticked` is computed before this effect, so move the `const ticked = ...` line
above the effects if it is not already there.

- [ ] **Step 8: Build, lint and test**

```bash
cd /Users/macbook/Documents/Projects/nebula/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
pnpm build && pnpm lint && pnpm test
cd .. && uv run pytest -q
```

Expected: all pass.

- [ ] **Step 9: See a real banner**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run python -c "
from datetime import datetime, timedelta
from nebula import store
from nebula.tracker import Tracker
now = datetime.now().astimezone()
p = store.data_path(dev=True)
p.unlink(missing_ok=True)
t = Tracker(p)
t.add_allocation('Work', 300, now)          # a five-minute target
v = t.view(now)
aid = v.allocations[0].id
t.activate(aid, now - timedelta(seconds=280))
t.toggle_break(now)   # CLOSE it: opening the app is a resume point (PRD §17)
                      # and would end an open session, leaving nothing accruing
print('seeded: 280s of a 300s target, closed. Click Work in the app to resume.')
"
uv run nebula
```

Click **Work** to start accruing — the app opens Neutral by design.
Expected: within seconds a banner reads `Work is almost complete — 0m
remaining.`, and about 20 seconds later `Work allocation completed — you've
reached your 5m goal. Keep going if you want.` Neither repeats. **This is the
only way to confirm the banner appears** — `osascript` exits 0 either way.

- [ ] **Step 10: Update the docs**

In `docs/ROADMAP.md`, move 3d to `**Done**`, set 4 to `Next`, and rewrite the
"Phase 3d — Notifications" section in the style of the finished phases, noting
that the banner itself is only ever confirmed by a human.

In `README.md`, add `milestones.ts` to the frontend layout block and
`notify.py` to the Python side if that block lists modules.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "Ask Python to check milestones from the tick

React notices a crossing during the one-second tick it already runs and
asks Python, which decides from timestamps whether the milestone is
real. Nothing in Python ticks, so this is the only place a crossing can
be noticed while the user is simply working.

The view carries which milestones have fired, and that is what stops the
asking. React's ticked percentage runs ahead of Python's, so without it
Python would decline, React would ask again next tick, and the two would
loop once a second until they converged.

Only the Active allocation is considered: a target edit can push a Stale
one past 100%, and that must never notify."
```

---

## Definition of Done

Verified against spec §9:

1. Past 95% shows a banner naming the allocation and time left — Task 4, Step 9.
2. Past 100% shows the completion banner — Task 4, Step 9.
3. Neither fires twice, nothing after 100% — Task 3, Steps 1 and 6.
4. Both fire again the next day — Task 2, Step 1.
5. A target edit fires nothing, then or later — Task 3, Step 5.
6. Reopening after a crash that crossed a milestone fires nothing — Task 2, Step 1.
7. A name carrying an AppleScript payload does not execute — Task 1, Step 1.
8. Both suites pass — Task 4, Step 8.
