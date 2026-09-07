# Notifications — Design

Date: 2026-09-07
Phase: 3d (see [ROADMAP](../../ROADMAP.md))
Status: Approved design, pending implementation plan

## 1. Purpose

Tell the user when an allocation is nearly done and when it is done, once each
per day, without ever interrupting what they are doing.

Covers the PRD's **Notifications** checklist.

## 2. What fires

Two milestones per allocation per day, each once (PRD §13.1–13.3). The copy is
fixed by the PRD:

| Milestone | Message |
|---|---|
| 95% | `Work is almost complete — 9 minutes remaining.` |
| 100% | `Work allocation completed — you've reached your 3h goal. Keep going if you want.` |

The remaining time is `daily_target_seconds - tracked_seconds` at the moment the
milestone fires, and the goal is the allocation's target.

The remaining time in the 95% message and the target in the 100% message are
formatted the same way the dashboard formats them, so a banner and the card
never disagree.

After 100% nothing more fires: no per-percentage spam, no overage warnings
(PRD §13.3).

### Only accumulating time fires a milestone

A percentage can cross 95% with no time tracked at all — editing Work's target
from 3h down to 1h while it holds 2h jumps it to 200%. That must not notify.
The user just made that change and is looking at the number.

So a milestone fires only when the **Active** allocation ticks past it, which is
what PRD §13.1 describes ("when an active allocation reaches 95%"). A milestone
crossed any other way is recorded as passed *silently*, so it cannot fire later
either.

## 3. Who notices the crossing

Nothing in Python ticks. It acts only when the frontend calls, so **React
notices and Python decides.**

React already recomputes the Active allocation every second (3b, `tick.ts`).
When its ticked percentage reaches a threshold it calls `check_milestones()`.
Python re-derives the percentage from timestamps and fires only what is
genuinely due.

React is a trigger, never an authority. The call is idempotent — asking twice
fires once — because Python records what it has fired before returning.

### Bounding the calls

React's ticked percentage runs slightly ahead of the last figure Python
returned, so React can reach 95% a moment before Python agrees. If React simply
asked whenever its own number was past a threshold, Python would decline, React
would ask again on the next tick, and the two would loop once a second until
they converged.

So **the view carries which milestones have already fired**:
`AllocationView.notified_milestones`. React asks only when its ticked percentage
is past a threshold *and* that milestone is absent from the list. Once Python
fires and records it, the returned view closes the loop.

That bounds the traffic to a handful of calls around each crossing, rather than
one per second, and it needs no timer or throttle to reason about.

A Python-side timer thread was rejected: it would duplicate a tick that already
exists and introduce concurrent access to `Tracker`, which is currently only
ever touched from the bridge.

## 4. Data

```
NotifiedMilestone
├── allocation_id
├── day_anchor
└── milestone        // 95 or 100
```

Appended to `AppData.notified`, serialised alongside sessions and completions,
and surfaced per allocation as `AllocationView.notified_milestones` so the
frontend knows what not to ask about again (§3).

Keyed by `day_anchor`, so a new day re-arms every milestone with no cleanup
step — the same mechanism `tracked_seconds` already uses to make a day "reset"
without deleting anything.

## 5. Delivery

A new `src/nebula/notify.py`, shelling out to `osascript`. The banner is
attributed to "Script Editor" rather than Nebula, which PRD §27 accepts for V1;
native attribution needs `pyobjc` and a signed app (§24).

**Verified before designing around it:** an `osascript` banner does appear on
this machine. `osascript` exits 0 whether or not macOS actually shows anything,
so the exit code proves nothing and a human confirmed the banner.

### Allocation names are user input inside an AppleScript

An allocation named `" & (do shell script "…") & "` would execute if the message
were interpolated into the script text. The message is therefore **passed as
`argv`**, never interpolated:

```
osascript - <title> <message> <<'EOF'
on run argv
  display notification (item 2 of argv) with title (item 1 of argv)
end run
EOF
```

Confirmed by running that payload: nothing executed. It also removes ordinary
quoting problems with names like `Client "A"`.

### Failure must not disturb tracking

Notifying is a side effect of a bridge call that also returns the dashboard. A
failure to notify is logged and swallowed, never raised, so a missing banner can
never cost the user their tracking state. The subprocess gets a short timeout so
a hung `osascript` cannot wedge the bridge thread.

## 6. Silent catch-up at a resume point

After a crash, `resume()` closes the still-open session at the current time, so
an allocation can be past 95% on reopen having never notified.

At a resume point, every milestone already exceeded is recorded as notified
**without firing**. No banner arrives about something that happened while the
app was closed, and it cannot fire later either. Notifications stay a live
signal rather than a backlog.

## 7. Testing

Python:

- Which milestones are due for a given percentage, and that 95 and 100 are
  independent.
- Firing records the milestone; a second check fires nothing.
- A new day re-arms both milestones.
- Editing a target past a threshold records it silently and never fires.
- A resume point records exceeded milestones silently.
- The view reports fired milestones, so the frontend stops asking.
- The message text matches the PRD, with durations formatted as the dashboard
  formats them.
- **Escaping**: an allocation name containing quotes and a `do shell script`
  payload is passed through `argv` and does not execute.
- An `osascript` failure is swallowed rather than raised.

### What cannot be tested

**That a banner actually appeared.** `osascript` exits 0 either way, so a test
asserting on the exit code would pass even with notifications switched off at
the system level — the same shape of false confidence that let the type scale
silently fail for two phases. The suite covers command construction and failure
handling; the banner itself stays a manual check, recorded here as a known gap.

## 8. Out of scope

No on/off toggle and no configurable thresholds: PRD §13 fixes both and §24
backlogs custom ones to P1. 3c already omitted the mock's Notifications section
for this reason.

Notifications fire only while the app is open. There is no background process
and no menu-bar item in V1 (PRD §15, §27), so nothing can notify a user who has
closed the window.

## 9. Definition of done

1. Tracking an allocation past 95% shows a banner naming it and the time left.
2. Tracking it past 100% shows the completion banner.
3. Neither fires twice in a day, and nothing fires after 100%.
4. Both fire again the next day.
5. Editing a target past a threshold fires nothing, then and thereafter.
6. Reopening after a crash that crossed a milestone fires nothing.
7. An allocation whose name contains an AppleScript payload does not execute it.
8. Both test suites pass.
