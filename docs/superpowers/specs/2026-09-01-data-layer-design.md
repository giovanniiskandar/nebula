# Data Layer — Design

Date: 2026-09-01
Phase: 3a of the Daily Time Allocation widget (see [PRD.md](../../../PRD.md))
Status: Approved design, pending implementation plan

## 1. Purpose

Build the tracking core: allocations, sessions, persistence, and every rule that
turns stored timestamps into what the dashboard displays. No UI.

This is the first phase that produces product behavior rather than scaffolding.
It is deliberately headless so that the hard, time-dependent rules are settled
and tested before any UI depends on them.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Derived state | Python computes; React ticks the live one | One implementation of the state machine, in the language where it is tested. React adds `now - active_since` for the single Active allocation — one addition, not the rules. |
| Storage path | `~/Library/Application Support/Nebula/` | Survives bundling. The spike found a bundled app's cwd is `/`, so any relative path breaks there. |
| Dev data | Separate `data.dev.json` | Development cannot destroy real tracked history. |
| Structure | Pure functions over immutable data, I/O at the edge | See §4. |
| Scope | Store, model, and all tracking rules | Excludes the 15s timer that drives the sleep-gap rule. |

## 3. Modules

```
src/nebula/
├── model.py     dataclasses: Allocation, TimeSession, CurrentState, Preferences, views
├── rules.py     pure functions: totals, derived state, day rollover, sleep-gap, break
├── store.py     JSON load/save, path resolution, atomic write
└── tracker.py   thin façade composing store + rules; the UI's entry point
```

Each file has one responsibility. `rules.py` imports only `model.py` and the
standard library — it never touches the filesystem or the clock, which is what
makes it testable without stubs.

`app.py` and `__main__.py` are unchanged this phase.

## 4. Time is a parameter, never ambient

**Every function that needs the current time takes `now: datetime` explicitly.**
Only `__main__` calls `datetime.now()`.

This is the central design decision and it is a direct response to how the
previous phases went. Six bugs shipped in phase 2, every one at a boundary that
was asserted about rather than exercised — most starkly a Dock-icon check that
read back the value it had just written and reported success.

An ambient clock reproduces that failure. If `rules.py` called
`datetime.now()` internally, tests would have to patch it, and a patched clock
returns whatever the test says — so the test passes whether or not the rule is
correct. With time as a parameter, tests pass **real `datetime` values as
ordinary data**. Nothing is stubbed, so nothing can lie about what it observed.

### Timestamp representation

- Instants (`startedAt`, `endedAt`) are timezone-aware UTC, serialised ISO-8601.
- `dayAnchor` is a **local** date string, `YYYY-MM-DD`.

The split is deliberate: an instant is absolute, but a "day" is a human, local
concept. Anchoring on a local date is what makes "the day I started this in"
mean what the user expects.

## 5. Totals are derived, never stored

A day's total for an allocation is the sum of sessions whose `dayAnchor` equals
the currently open `dayAnchor`. No running counter is persisted.

Three PRD requirements then fall out of the data model rather than needing
separate code:

- **§14, midnight crossing.** A session keeps the `dayAnchor` it started with.
  It is never split, and its full duration counts toward the day it began in,
  however long it runs.
- **§17, day rollover.** A new day means a new anchor; the previous day's
  sessions stop matching the filter. Nothing is mutated or deleted.
- **§19, historical data.** Preserved automatically, because resetting a day is
  a filter rather than a delete.

An open session (`endedAt is None`) contributes `now - startedAt` when totals
are computed.

## 6. Storage

`~/Library/Application Support/Nebula/data.json`, or `data.dev.json` when the
app runs with `--dev`. The directory is created on first write.

**Atomic writes.** Serialise to a temporary file in the same directory, then
`os.replace()` onto the target. `os.replace` is atomic on POSIX, so a crash
mid-write leaves the previous file intact rather than truncated JSON. The data
file is the only irreplaceable thing in the product; a partial write would
destroy all history.

**Schema version.** The document carries `"version": 1` at the top level. It
costs nothing now and cannot be added retroactively to files already written.

**A missing file is not an error.** First launch produces the documented empty
state (no allocations, `NEUTRAL`, `dayAnchor` of today), not an exception.

**Unclean shutdown.** If a session is still open at load, the app did not exit
cleanly — a crash, a force quit, or a power loss, none of which get the chance
to write `ended_at`. How long it actually ran is unknowable.

Such a session is closed at its own `started_at` and contributes nothing.

The alternative is to close it at the current time, which would credit the user
for every hour the machine spent switched off: crash at 9am, reopen at 6pm, nine
fabricated hours. Counting zero loses at most the one session in progress, since
every session that ended normally is already on disk. This is the same principle
as sleep detection (§16) — when the app does not know, it counts nothing rather
than guessing high.

**A corrupt file is an error.** If JSON parsing fails, raise rather than
silently starting fresh — silently discarding a user's history is worse than
refusing to start. Recovery UI is out of scope; the failure must be loud.

## 7. Data model

Following PRD §20, with names in Python conventions:

```
Allocation      id, name, daily_target_seconds, created_at, archived_at
TimeSession     id, allocation_id, started_at, ended_at, day_anchor
CurrentState    active_allocation_id, status, pre_break_allocation_id, day_anchor
Completion      day_anchor, completed_at
Preferences     name
```

`Completion` is the one addition to PRD §20. Each press of Complete appends a
record. It exists because a day is **filed under the date it was completed**,
not the date it began (§7.1), and that date cannot be known until the user
presses the button.

A `last_tick_at` field was considered, to close an open session at the last
heartbeat after a crash, and rejected: it would mean rewriting the data file
every 15 seconds for the app's entire life, purely to record liveness. That is
continuous write churn against the one irreplaceable file, in exchange for
recovering a rare case. §6 handles crashes without it.

`status` is `ACTIVE | BREAK | NEUTRAL`. `archived_at` is set on delete; the
record is retained so historical sessions keep resolving (PRD §12, §21).

### 7.1 A day is filed under its completion date

Sessions anchor to the date they start, because a day in progress needs an
identity before anyone knows when it will end. That anchor is what live totals
are summed by (§5).

The **historical** date of a day is different: it is the local date of the last
`Completion` recorded for that anchor. A day begun at 11pm on Sep 1 and
completed at 5am on Sep 2 is filed under **Sep 2**.

This overrides PRD §14/§17, which file such a day under Sep 1. Overnight work
belongs to the day you finished it, not the one you happened to start in.

A day that is never completed — the app is simply reopened the next day (§17) —
has no `Completion`, and falls back to its anchor date.

Completing twice in one day appends two records and changes nothing about the
totals (§9). The later one wins for filing.

Nothing in V1 displays historical dates. This is recorded now because the
filing date is unrecoverable after the fact if it is not captured at
completion.

`daily_target_seconds` is stored in seconds as an integer. The PRD writes
targets as `3h`; parsing human input belongs to the settings UI, not here.

## 8. The view handed to React

```
AllocationView   id, name, daily_target_seconds, tracked_seconds,
                 state (NOT_STARTED | ACTIVE | STALE), percentage,
                 remaining_seconds (negative means overage),
                 active_since (ISO-8601, present only when state is ACTIVE)

DashboardView    status (ACTIVE | BREAK | NEUTRAL), day_anchor, allocations[],
                 total_tracked_seconds, total_target_seconds
```

`active_since` is the only field React needs in order to tick the live timer: it
adds `now - active_since` to that one allocation. Everything else is computed in
Python.

`percentage` is not capped (PRD §8). `remaining_seconds` goes negative past the
target, and the sign is the overage.

## 9. Rules covered

- **Start / switch** (§10.3, §10.4). Activating an allocation ends any open
  session and opens a new one. Switching exits Break.
- **Break toggle** (§6.4). Entering Break ends the open session and records
  `pre_break_allocation_id`. Toggling Break off resumes that allocation if there
  was one, and returns to `NEUTRAL` if Break was entered from `NEUTRAL`.
- **Neutral** (§6.5) is distinct from Break: no Break session is recorded, and
  nothing is remembered for resumption.
- **Day rollover at resume points** (§17, §18.3). Given a resume point and
  `now`: if `day_anchor` equals today's local date, totals are untouched and no
  allocation is Active; if it is earlier, the anchor becomes today and no
  allocation is Active. Rollover is never automatic mid-session.
- **Sleep-gap** (§16), as a pure function: given the previous tick, `now`, and a
  threshold, if the gap exceeds the threshold, close the open session at the
  previous tick and open a new one at `now`. The unaccounted span is simply not
  covered by any session, so it is never counted. The threshold is **120
  seconds**, matching the PRD's "~2 minutes" against its ~15 second tick. The
  value is a module constant and a parameter with that default, so tests state
  the gap they mean rather than depending on the constant.
- **Day completion** (§10.6, §18.1). Completing ends any open session with a
  real `ended_at`, moves to `NEUTRAL`, and appends a `Completion`.

  It **zeroes nothing**. Complete at 3pm, carry on working, Complete again at
  6pm: the second recap shows the accumulated day, not just 3pm to 6pm. Only a
  date check at a resume point (§17) starts a fresh day. Completion is manual
  only; reaching 100% never triggers it (PRD §9).
- **Progress past 100%** (§8). No cap, no automatic stop.

## 10. Testing

Real `datetime` values passed as data. No clock patching anywhere.

Rules, table-driven:
- a session that starts before and ends after local midnight counts entirely
  toward its starting day, and is not split
- resume with the same local date leaves totals intact and sets no Active
- resume with an earlier local date rolls the anchor and zeroes today's totals
  while prior sessions remain in the file
- a heartbeat gap beyond the threshold closes and reopens the session, and the
  gap counts toward nothing
- a gap within the threshold changes nothing
- tracked time beyond the target yields percentage above 100 and negative
  remaining
- Break entered from Active resumes that allocation on toggle off
- Break entered from Neutral returns to Neutral on toggle off
- every derived state: NOT_STARTED, ACTIVE, STALE

Recovery and completion:
- a session left open at load contributes zero, and never extends to `now`
- completing ends the open session and leaves the day's totals intact
- completing twice in one day leaves totals accumulated across both
- a day begun at 11pm and completed at 5am the next morning is filed under the
  completion date, while its totals stay summed by the start anchor
- a day that is never completed falls back to its anchor date

Store:
- write then read in `tmp_path` round-trips every field
- a missing file yields the documented empty state
- a corrupt file raises
- the previous file survives a write that fails midway

## 11. Out of scope

All UI. Notifications (§13). The 15-second timer that calls the sleep-gap rule.
The single-instance lock (§15). Parsing human duration input such as `3h`.
Packaging changes, including the `PROJECT_ROOT` fix, which belongs with the
packaging phase and its bundle-building test.

## 12. Definition of done

1. `tracker.py` exposes: load state, add/edit/delete an allocation, activate an
   allocation, toggle Break, complete the day, apply a heartbeat tick, and build
   a `DashboardView` — each taking `now` explicitly where time matters.
2. Data persists to `~/Library/Application Support/Nebula/data.json`, with
   `--dev` writing `data.dev.json`.
3. Every rule in §9 is covered by tests in §10, passing with real timestamps and
   no patched clock.
4. `rules.py` imports nothing from `store.py` and never reads the clock.
5. The full suite still passes, including the phase 2 GUI regression test.
