# Daily Time Allocation Widget

Status: Draft (refined after grilling session)
Version: V1.2
Platform: macOS
Product Type: Desktop widget / lightweight time tracker
Implementation: Python + [pywebview](https://pywebview.flowrl.com/) (native window shell, HTML/CSS/JS UI), local-only, no accounts, no cloud

---

## 1. Product Overview

Daily Time Allocation is a lightweight macOS widget that helps users plan and monitor how they allocate their time throughout the day.

Users define daily time allocations such as:
- Work — 3 hours
- Learning — 2 hours
- Entertainment — 2 hours

During the day, the user simply selects what they are currently doing. The application automatically tracks the elapsed time against that activity's daily allocation.

The product is not a productivity enforcement tool. It does not prevent users from exceeding their allocations or force them to follow their plan. It also never forces an artificial cutoff on real work — if you're still going at 1am, it keeps counting rather than silently splitting your evening in two.

Its purpose is to answer:

> "How am I actually spending my time compared with how I planned to spend it?"

The app is a floating, always-on-top panel window (not a real macOS system widget — see §26, Technical Implementation Notes, for why), shared as a standalone `.app` with friends, running entirely on their own Mac with their own local data.

---

## 2. Product Philosophy

**Plan** — Users decide how much time they want to allocate to different activities.

**Track** — The application automatically tracks time based on the activity the user selects.

**Inform, Don't Restrict** — The application provides visual feedback and notifications but never prevents the user from continuing an activity, and never forces a boundary (like midnight) onto an activity that's still genuinely running.

For example, if the user allocates 2 hours to Entertainment but spends 3 hours, the application should show:

```
Entertainment — 3h / 2h — 150%
```

It should not stop the timer at 2 hours.

---

## 3. Goals

**Primary Goals**
1. Make daily time allocation visible at a glance.
2. Make switching between activities extremely easy.
3. Automatically track time without requiring manual timers.
4. Show planned time versus actual time.
5. Help users notice when they are approaching or exceeding an allocation.
6. Keep the interface lightweight enough to remain useful as a desktop widget.
7. Never impose an artificial time boundary (e.g. midnight) on work that's genuinely still happening.

**Secondary Goals**
1. Preserve historical time data.
2. Make the system reliable across application restarts.
3. Keep configuration simple.
4. Be easy to hand to another person and have it just work on their Mac.

---

## 4. Non-Goals

The V1 product is not intended to be:
- A task manager
- A project management tool
- A Pomodoro timer
- An automatic activity-monitoring system
- An application blocker
- A website blocker
- A calendar
- A scheduling system
- A productivity scoring system
- A tool that forces users to follow their allocations
- An accounts/cloud-sync product — all data is local to the machine it runs on

The user remains completely free to spend their time however they want.

---

## 5. Core Concept

Users create Daily Allocations. Each allocation consists of:
- Name
- Daily target duration

Example:

| Allocation | Daily Target |
|---|---|
| Work | 3h |
| Learning | 2h |
| Entertainment | 2h |

The application tracks actual time spent against each allocation.

| Allocation | Actual | Target | Progress |
|---|---|---|---|
| Work | 2h 24m | 3h | 80% |
| Learning | 36m | 2h | 30% |
| Entertainment | 0m | 2h | 0% |

---

## 6. Activity States

Activity state and progress percentage are separate concepts.

### 6.1 Not Started
The allocation has no tracked time today. Actual = 0.

```
Entertainment — 0m / 2h — Not Started
```

### 6.2 Active
The allocation is currently selected and accumulating time.

```
Work — 2h 24m / 3h — Active
```

Only one allocation can be Active at any time.

### 6.3 Stale
The allocation has tracked time today but is not currently active.

```
Learning — 36m / 2h — Stale
```

"Stale" means the user has spent time on this allocation today, but they are currently doing something else.

### 6.4 Break

Break is a special global state, toggled by a single Break control.

**Entering Break** (clicking Break while an allocation is Active, or while nothing is active):
- No allocation accumulates time.
- If an allocation was Active, it becomes Stale and its id is remembered as "the one paused by Break."
- The user can resume an allocation directly at any time (see 10.4), which exits Break immediately.

**Exiting Break by clicking Break again** (a toggle, not just an "on" switch):
- If an allocation was Active immediately before Break was entered, that allocation resumes and becomes Active again — Break behaves like a pause/resume button, not a full deselect.
- If nothing was Active before Break was entered (Break was toggled on from the neutral state), toggling off returns to the neutral state — nothing becomes Active.

Example:

```
Work             2h 24m / 3h    Stale
Learning         36m / 2h       Stale
Entertainment    0m / 2h        Not Started

                 ☕ Break (tap again to resume Work)
```

### 6.5 Neutral (no active allocation, not on Break)

This is a distinct state from Break. It occurs at the start of a fresh day, at first launch, and any time nothing has been explicitly selected. It is *not* visually or behaviorally the same as Break — no Break session is logged, no "ON BREAK" badge is shown, until the user actually presses the Break control.

---

## 7. Progress

Each allocation displays:
1. Actual time spent
2. Daily target
3. Percentage completed
4. Remaining time
5. Progress bar
6. Current state

```
Work

2h 24m / 3h
████████████████░░░░  80%

36m left
ACTIVE
```

---

## 8. Progress Beyond 100%

Progress is not capped at 100%. If the user continues after reaching the allocation:

```
Target: 3h
Actual: 3h 45m
Progress: 125%
```

```
Work

3h 45m / 3h
█████████████████████████  125%

45m over allocation
ACTIVE
```

The allocation continues tracking normally. The application must never automatically stop an activity because it reached its target.

---

## 9. Completion (per-allocation milestone)

Reaching 100% on a single allocation is a milestone, not an activity state, and is unrelated to the whole-day "Day Completion" flow in §18.

```
Work
3h / 3h
100%
ACTIVE
```

The user may continue working:

```
Work
3h 30m / 3h
117%
ACTIVE
```

"Completed" (this section) describes one allocation reaching its target. "Active/Stale/Not Started/Break/Neutral" (§6) describes the current activity state. "Day Completed" (§18) describes the user ending the whole day. These three concepts remain separate — there is deliberately no automatic Day Completion trigger just because every allocation happens to hit 100% (real days rarely max out every allocation at once, so building for that case isn't worth the added rule).

---

## 10. User Flow

### 10.1 First Launch
If no allocations exist, the application guides the user to create their first allocation.

```
Plan your day

Create your first time allocation.

[ + Add Allocation ]
```

### 10.2 Add Allocation

```
Name
[ Work                 ]

Daily target
[ 3h                   ]

[ Cancel ]   [ Save ]
```

Required fields: Name, Daily target duration.

### 10.3 Start an Activity
User clicks an allocation. It becomes Active immediately; tracking begins. If another allocation was Active, it becomes Stale.

### 10.4 Switch Activities
The user can click any allocation at any time. No confirmation dialog required. The transition feels instantaneous. Clicking any allocation also exits Break, per §6.4.

### 10.5 Take a Break
User clicks Break. See §6.4 for full toggle/resume semantics: entering pauses tracking and marks the previous allocation Stale; clicking Break again resumes that same allocation (or returns to neutral if nothing was active before).

### 10.6 Complete the Day

User clicks the Complete control (always visible alongside Break, see §11). This is the *only* way a day ends — there is no automatic completion trigger.

On Complete:
1. Any Active session is ended (its `endedAt` is recorded).
2. A result popup is shown (see §18.2).
3. Closing the popup reveals a Start control.
4. Clicking Start re-evaluates the day per §18.3 and returns to the dashboard.

---

## 11. Dashboard

The dashboard is the primary product experience.

**Header** — `TODAY`, with an optional overall summary (e.g. `4h 10m tracked of 7h planned`).

**Allocation List** — as in §7; clicking an allocation activates it.

**Controls** — Break and Complete are both always visible and reachable with a single click.

---

## 12. Settings

Settings allow users to manage their allocations.

```
TIME ALLOCATIONS

Work
3h / day                    Edit   Delete

Learning
2h / day                    Edit   Delete
```

- **Add** — create a new allocation.
- **Edit** — change name and/or daily target. A target change applies immediately, including to *today's* already-in-progress percentage (today isn't "historical" yet — only days that have actually completed keep the target that was configured for them, per §19).
- **Delete** — removes the allocation from Settings and from future daily tracking entirely. This is the *only* place an allocation can be deleted. There is no confirmation step and no "archived" view in V1 — the allocation simply disappears from Settings. Its historical sessions remain in the local data file, untouched, available to any future history feature, but are not exposed anywhere in V1.
- No upper bound is enforced on the sum of all daily targets — a user can configure more hours than exist in a day; the app does not warn about this in V1.
- **Name** — a single free-text field (e.g. "Your name"), used only to personalize the Day Completion message (§18.2). Not an account or login — just a local preference string, optional, defaults to unset.

All configuration and history is stored in a local JSON file (§20) — there is no database, no account, and no cloud sync.

---

## 13. Notifications

Notifications are informational only and must never block the user's activity.

### 13.1 Near Completion Notification
Trigger when an active allocation reaches 95% of its daily target. Includes remaining time. Fires once per allocation per day.

```
Work is almost complete — 9 minutes remaining.
```

### 13.2 Completion Notification
Trigger when an allocation reaches 100%.

```
Work allocation completed — you've reached your 3h goal. Keep going if you want.
```

### 13.3 No Repeated Notifications
After the 100% notification: no repeats, no per-percentage spam, no overage warnings.

See §26 for how notifications are actually delivered on macOS in V1 (a real product/technical tradeoff worth knowing about).

---

## 14. Time Tracking

The application tracks time using timestamps/sessions rather than an incrementing timer.

```
Work
09:00 → 10:30
11:15 → 12:45

Learning
14:00 → 14:45
```

Total time is derived, not accumulated live: Work = 3h, Learning = 45m.

A session is **not** force-split at midnight. If a session is still open when the wall clock crosses midnight, it keeps running uninterrupted and its elapsed time keeps counting toward the day it started in (see §17–18 for how a "day" is actually bounded). This makes tracking reliable across app restarts, computer restarts, and legitimate overtime.

Note that the day a session *accumulates into* while it is running, and the date that day is eventually *filed under* in history, are two different things — see §17.1.

---

## 15. Application Restart

If an allocation was Active before the application closed (deliberately, via the window close, or unexpectedly), the app determines the correct state from persisted timestamps on reopen — never from an in-memory timer.

**Closing the window** ends the current Active session (records `endedAt`) and fully quits the application. There is no background process and no menu-bar/tray icon in V1 (see §26 on why), so nothing continues running once the window is closed. Reopening the app is itself a resume point (see §18.3) — it shows the same day's accumulated totals if it's still the same calendar day, or starts a fresh day if it isn't.

**Single instance**: launching the app while it's already running does not open a second copy — it focuses the existing window. This avoids two processes writing to the same local data file at once, which could otherwise corrupt "which allocation is Active."

---

## 16. Mac Sleep / Wake (not handled in V1)

**V1 does not detect sleep.** An active allocation keeps counting while the Mac
is asleep, exactly as it does while the Mac is awake.

```
Work active        10:00
Mac sleeps          10:30
Mac wakes           12:00
Work still active   12:00  ← the 1h30m counts
```

The rule is simply: **an allocation counts wall-clock time from the moment you
select it until you select something else, press Break, or Complete the day.**
Nothing pauses it automatically.

If a user does not want sleep counted, they press Break before closing the lid.
That is a deliberate V1 tradeoff, consistent with §2: the app informs rather
than second-guesses, and one obvious manual control beats an inference that can
be wrong in both directions.

Automatic detection is backlogged (§24). It was previously specified as
heartbeat-gap detection — a ~15 second tick, treating a gap beyond ~2 minutes as
unaccounted time. That design still stands if it is ever built; it was dropped
from V1 for simplicity, not because it does not work.

---

## 17. Day Boundaries (replaces the old "silent midnight reset")

A calendar-date "day" boundary is **not** enforced automatically while the app is actively tracking — see §14 and the Product Philosophy in §2: real overtime should never be artificially cut off. Instead, the currently open day is anchored to the date it started on, and that anchor only changes at a **resume point**:

- Reopening the app after it was closed, or
- Clicking Start after closing the Complete-day result popup (§18.3).

At a resume point, the app compares the date the current day is anchored to against today's actual date:
- **Same date** → nothing resets; the dashboard shows today's already-accumulated totals, with no allocation Active (neutral, per §6.5).
- **Earlier date** → a new day begins: all allocations reset to 0 tracked time, daily targets/configuration are unchanged, and no allocation is Active.

```
Day anchored to August 31, still 3h/3h Work at day's end
→ app reopened on September 1 →
Work       0m / 3h
Learning   0m / 2h
```

Historical tracking data from prior days is always retained (§19), regardless of how a day ended.

### 17.1 Which date a day is filed under

While a day is open, its sessions accumulate against the date it *started* —
a day in progress needs an identity before anyone knows when it will end.

In history, a day is filed under the date it was **completed**, not the date it
began. A day started at 11pm on September 1 and completed at 5am on September 2
is September 2's record. Overnight work belongs to the day you finished it.

A day that is never completed — the app is simply reopened on a later date — has
no completion, and is filed under the date it started.

Completing twice in one day changes nothing about the totals (§18.3); the later
completion is the one the day is filed under.

V1 does not display historical dates. The completion timestamp is recorded
anyway, because it cannot be reconstructed afterwards.

---

## 18. Day Completion (new in V1.1)

### 18.1 Trigger
Day Completion is manual only, via the Complete control (§10.6, §11). There is no automatic trigger tied to allocations reaching 100% — see §9 for why that was deliberately left out.

### 18.2 Result Popup
On Complete, the popup shows:
- A per-allocation breakdown: name, actual/target, percentage — the same numbers already computed for the live dashboard, just frozen at the moment of completion.
- A static encouragement line, personalized with the Name field from Settings (§12) when set: `Good work today, {name}!`. If no name is configured, it falls back to a generic `Good work today!`. The message text itself is still static/hard-coded for V1 — only the name is a variable — richer, varied messaging is a future improvement.

```
TODAY'S RESULT

Work           3h 45m / 3h    125%
Learning       1h 06m / 2h     55%
Entertainment    40m  / 2h     33%

Good work today, Alex!

[ Start ]
```

### 18.3 After Closing the Popup
Closing the popup reveals a Start control. Clicking Start is itself a resume point and follows the exact same date-check logic as §17 — same date, continue today unchanged (Complete doesn't erase today's numbers by itself, it just stops tracking and shows the recap); earlier date (e.g. completed right before midnight, started right after), begin a fresh day.

---

## 19. Historical Data

The application retains historical time data even though V1 does not expose a detailed history interface. This enables future features such as daily history, weekly summaries, allocation accuracy, trends, and charts.

Historical data is not destroyed when the user edits or removes an allocation. When a target is edited, the new target applies immediately to the current, still-open day; a day that has already rolled over (per §17) permanently keeps the target that was configured while it was open.

---

## 20. Data Model

Stored as a local JSON file — no database, no server, no account.

```
Allocation
├── id
├── name
├── dailyTarget
├── createdAt
└── archivedAt        // set on delete; record kept for historical sessions, hidden from Settings/dashboard

TimeSession
├── id
├── allocationId
├── startedAt
├── endedAt
└── dayAnchor          // the date this session's day was anchored to when the session started — not recomputed from endedAt, since a session can cross midnight uninterrupted (§14)

CurrentState
├── activeAllocationId       // null when Neutral or on Break
├── status                   // ACTIVE | BREAK | NEUTRAL
├── preBreakAllocationId     // remembered for Break's resume-toggle (§6.4); null if Break was entered from Neutral
└── dayAnchor                 // the date the currently open day started on (§17)

Completion
├── dayAnchor                // the day this completion closed
└── completedAt              // when Complete was pressed; its local date is the date the day is filed under (§17.1)

Preferences
└── name       // optional free-text string, set in Settings (§12); used only to personalize the Day Completion message (§18.2)
```

Derived UI state for an allocation:

```
if trackedTime == 0
    NOT_STARTED
else if allocationId == activeAllocationId
    ACTIVE
else
    STALE
```

Derived progress:

```
progress   = trackedTime / dailyTarget
percentage = progress × 100
remaining  = dailyTarget - trackedTime      // negative => overage = trackedTime - dailyTarget
```

---

## 21. Edge Cases

- **Rapid activity switching** — each transition accurately creates/ends a `TimeSession`.
- **Exceeding 100% / 200%+** — tracking continues normally; no cap, no cutoff.
- **Deleting an allocation** — future tracking removed; historical sessions remain in the JSON file, unreferenced from Settings/dashboard.
- **Editing a target mid-day** — applies immediately to the currently open day (§19).
- **No active allocation** — this is the Neutral state (§6.5), distinct from Break; it is not "effectively Break," and no Break session is logged for it.
- **Activity running across midnight** — not split; keeps accumulating under the day it started in, until the user completes or the app is reopened on a later date (§17–18).
- **Closing the app** — ends the active session with a real `endedAt`; the app fully quits (no background process, no tray icon in V1).
- **Crash or force quit** — no `endedAt` is written. On the next launch the still-open session is closed at that moment, consistent with §16: an allocation counts until something stops it. If the crash went unnoticed for days, that session carries its original `dayAnchor`, so it lands in that old day's history rather than today's dashboard.
- **Two launches at once** — the second launch focuses the existing window instead of starting a second process (§15).
- **Sleep/wake** — not detected in V1; an active allocation keeps counting through sleep (§16). The user presses Break if they do not want that.

---

## 22. Success Criteria

V1 is successful if a user can:
1. Create several daily allocations in under a minute.
2. Understand their current time allocation immediately upon looking at the widget.
3. Switch activities with a single click.
4. Take a break (and resume from it) with a single click each way.
5. See actual time, target time, percentage, and remaining time.
6. Receive useful 95% and 100% notifications.
7. Continue beyond 100%, and across midnight, without interruption.
8. Close/reopen the application without losing tracking data.
9. Deliberately complete a day on their own schedule and see a clear recap.
10. Understand what happened during the day without manually maintaining a timesheet.
11. Receive the app from a friend and get it running on their own Mac without a Developer account.

---

## 23. V1 Feature Checklist

**Dashboard**
- [ ] Display today's allocations, target, tracked duration, percentage, remaining time, progress bar
- [ ] Display Active / Stale / Not Started / Neutral states
- [ ] Display Break state, with toggle-to-resume behavior
- [ ] Click allocation to activate
- [ ] Break control
- [ ] Complete control

**Allocation Management**
- [ ] Add / Edit / Delete allocation
- [ ] Configure daily target
- [ ] Optional Name field in Settings, used for Day Completion personalization

**Time Tracking**
- [ ] Start tracking / stop previous activity when switching
- [ ] Break pause + resume-previous-allocation toggle
- [ ] Persist sessions with `dayAnchor`
- [ ] Persist a `Completion` per Complete, for the §17.1 filing date
- [ ] Handle application restart (single-instance guarded)
- [ ] Day rollover via date-check at resume points (app open, post-Complete Start) — not silent midnight

**Day Completion**
- [ ] Complete control, manual only
- [ ] Result popup: per-allocation breakdown + static encouragement line
- [ ] Start control resumes per date-check logic

**Notifications**
- [ ] 95% notification with remaining time
- [ ] 100% notification
- [ ] One notification per milestone per allocation per day
- [ ] Continue tracking after 100%, no repeats

**Data**
- [ ] Local JSON storage (allocations, sessions, current state)
- [ ] Preserve historical sessions after allocation edits/deletes

**Distribution**
- [ ] Unsigned `.app` build
- [ ] Bundled first-run instructions for the Gatekeeper override (§26)

---

## 24. Backlog / Future Improvements

Unchanged from the original draft — still deliberately excluded from V1:

**P1** — Weekly/Historical Dashboard, Weekly Trends, Different Allocations by Day, Custom Notification Thresholds, Menu Bar Integration (would require a tray-icon library like `rumps`/`pystray`, not something pywebview provides natively).

**P2** — Keyboard Shortcuts, Allocation Icons, Custom Colors, Better Overspending Visualization (target marker), Daily Notes, Activity History (session-level log view).

**P3** — Calendar Integration, Automatic Activity Detection (opt-in, privacy-conscious), Smart Allocation Suggestions, Focus/DND Integration, Goals/Streaks, Multiple Schedules, Allocation Groups.

**New backlog items from this grilling session:**
- Automatic sleep/wake handling, so sleep time is not counted (dropped from V1 in §16). Heartbeat-gap detection remains the intended design.
- Signed + notarized distribution (Apple Developer Program) once informal sharing outgrows the manual Gatekeeper-override workaround.
- Richer/varied Day Completion messaging (V1 has one static line personalized only by name, per §18.2) — e.g. messages that vary by how the day went.
- Native-branded notifications (`pyobjc` + `UNUserNotificationCenter`) if the "Script Editor" attribution from `osascript` (see §26) becomes annoying.

---

## 25. Product Principles for Future Features

Unchanged: does it help users understand their time? Does it make tracking easier? Does it reduce unnecessary interaction? Prefer those. Does it restrict the user's behavior, or create guilt/pressure? Avoid or be cautious. The application remains a time-awareness tool, not a productivity enforcement system.

---

## 26. Distribution & Installation (new in V1.1)

The app ships as an unsigned macOS `.app` for V1 — no Apple Developer Program membership, no notarization. This is a deliberate cost/complexity tradeoff for a friends-and-family-scale release, not an oversight.

**Consequence**: on first launch, Gatekeeper will block the app ("can't be opened because Apple cannot check it for malicious software"). This is resolved with either:
1. **System Settings → Privacy & Security → scroll down → "Open Anyway"** (appears after the first blocked attempt), confirm once. Works permanently afterward. This is the path on current macOS (Sequoia+).
2. A one-time Terminal command: `xattr -cr /path/to/AppName.app`, which strips the quarantine flag entirely — after that, it opens with no warnings at all, like a signed app.

Either is free and requires no code-signing pipeline. A short first-run instructions note (covering both options) ships alongside the app. Proper Developer ID signing + notarization is backlogged (§24) for if/when this needs to reach people beyond direct friends.

---

## 27. Technical Implementation Notes (new in V1.1)

Captured from the grilling session so implementation decisions aren't re-litigated later:

- **Shell**: pywebview, `create_window(..., frameless=True, transparent=True, on_top=True)`. All three are confirmed working in pywebview's macOS (cocoa) backend from source inspection — `on_top`'s docstring misleadingly says "required OS: Windows," but the implementation is real on macOS. `frameless` + `transparent` let the CSS-drawn rounded corners and shadow from the mock render as an actual floating card, with no square native window frame visible behind them.
- **No real macOS system widget**: an actual Notification Center/desktop widget requires a native Swift WidgetKit extension, which pywebview cannot produce. "Widget" in this PRD means a floating always-on-top panel window, not a system widget.
- **No menu-bar/tray icon in V1**: pywebview has no built-in system-tray API. Combined with "closing the window quits the app" (§15), there is no way to interact with a backgrounded instance in V1 — this is consistent with the backlog deferring Menu Bar Integration (§24).
- **Sleep/wake**: not handled in V1 (§16). Tracking counts through sleep, and Break is the manual control. This removes the need for any periodic heartbeat in V1.
- **Notifications**: delivered via shelling out to `osascript -e 'display notification ...'`. Zero dependencies, zero signing requirement — but the banner is attributed to "Script Editor" in Notification Center, not the app's own name/icon. Accepted as a cosmetic tradeoff for V1 since notifications are informational-only by design (§13); native-branded notifications via `pyobjc`'s `UNUserNotificationCenter` are backlogged (§24) and would want a properly signed `.app` to be reliable anyway.
- **Persistence**: a local JSON file (allocations, sessions, current state) — explicitly not SQLite/a database, per product decision. Acceptable at this scale; a future history/analytics feature (§24) may warrant revisiting this, but is not a V1 concern.
- **Single instance**: guarded via a lock file/socket check on startup; a second launch attempt focuses the existing window instead of starting a second process.
- **Mock file caveat**: the existing UI mock (`Daily Time Allocation - Widget.dc.html`) is authored in design-canvas-only markup (`<x-dc>`, `sc-if`, a `support.js` runtime) — it is a visual reference, not embeddable HTML. The production UI reproduces its look in plain HTML/CSS/JS.

---

## 28. V1 Definition of Done

V1 is ready when a user can install the application (even via the manual Gatekeeper override, §26), configure their daily allocations, and use the widget throughout a complete day — including one that runs past midnight without interruption — without needing to manually maintain their time records.

The complete experience should feel like:

> Set your intended allocations once → select what you're doing → let the application track reality → complete the day on your own terms and see how it went.

At any point during the day, glancing at the widget should immediately answer:
1. What am I doing right now?
2. How much time have I spent on it?
3. How much was I planning to spend?
4. How much time is left?
5. Am I already over my allocation?
6. What else have I spent time on today?
