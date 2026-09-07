# Settings — Design

Date: 2026-09-07
Phase: 3c (see [ROADMAP](../../ROADMAP.md))
Status: Approved design, pending implementation plan

## 1. Purpose

Make allocations manageable from inside the app. After this phase, creating one
no longer requires a script, and the Day Completion message can carry the user's
name.

Covers the PRD's **Allocation Management** checklist.

## 2. Source of truth

The mock (`Daily Time Allocation - Widget.dc.html`, PRD §27) supplies screens 4
(Add / edit) and 5 (Settings). As in 3b it predates PRD V1.1, and it is thinner
here than it first appears:

| Gap | Resolution |
|---|---|
| No settings entry point on the dashboard | A gear left of the close button (§3). |
| No back control in Settings | Settings is an overlay; it closes back to the dashboard. |
| No Name field, which PRD §12 requires | Added (§5). |
| A Notifications section V1 does not support | Omitted (§8). |

The mock is *better* than the PRD in two places, and both are adopted: a
structured `hh`/`mm` target with preset chips rather than free text, and a live
preview of the day's new planned total.

## 3. Screens

Three layers over one card, using the overlay mechanism the completion recap
already established in 3b — one pattern rather than two, and the dashboard
keeps ticking underneath.

```
Dashboard  --gear-->  Settings  --Add / Edit-->  Form
           <--x-----            <--Cancel/Save--
```

**Entry point.** A gear button sits left of the `×`, as window chrome. It costs
no vertical space, which matters in a card that already had to grow to 620 and
scroll (3b §4).

**Settings** shows `TIME ALLOCATIONS` with the daily total at right, a row per
visible allocation, `+ ADD ALLOCATION`, and the **Your name** field. Rows use
the card palette: `#1b1626` on hover against `#161220`, `1px solid #241f31`.

Two different things are called a name in this phase, and they are kept
distinct throughout: an **allocation's name** ("Work"), edited in the form
(§4), and the **user's name** (PRD §12's optional free-text field), edited in
Settings and used only to personalise the recap (§7).

**Your name saves on blur.** It is a single optional field with nothing to
validate, so a Save button would be ceremony; leaving the field commits it.
Clearing it is meaningful — it reverts the recap to the generic line.

**Delete acts immediately.** PRD §12 specifies no confirmation step and no
archived view. `rules.delete_allocation` already archives rather than removes,
so historical sessions still resolve.

## 4. The form

`NEW ALLOCATION` or the allocation's name as the title, with `×` to cancel.

- **NAME** — a text field.
- **DAILY TARGET** — two number inputs hinted `hh` and `mm`, with
  `30m / 1h / 2h / 3h / 4h` preset chips that fill them.
- **DAY AFTER THIS** — `7h planned → 10h planned`, recomputed as the fields
  change. Pure client-side arithmetic over the other allocations' targets.
- `CANCEL` and `SAVE`.

### Validation without an error state

`SAVE` is disabled unless the **allocation's** name is non-empty after trimming
and the target is greater than zero. This does not apply to the user's name in
Settings, which is optional and may be blank.

This is the point of the structured input: nothing is unparseable, so there is
no error copy to write, no invalid-input state to design, and no set of edge
cases (`3 hours`, `3.5h`, `""`) to decide. The roadmap's line about parsing
human input such as `3h` into seconds is dropped — it predates this mock, and
the input it describes no longer exists.

Minutes above 59 are clamped into hours on blur rather than rejected, so
`0h 90m` becomes `1h 30m` instead of a scolding.

## 5. Data layer additions

More than 3b required, because the name has no path at all.

**`Preferences.name` is never written.** It exists on the model and round-trips
through `to_dict`/`from_dict`, but no rule sets it, no `Tracker` method reaches
it, and `DashboardView` does not expose it. 3b's `Good work today!` fallback is
not waiting on a UI — it is waiting on a data path that was never built.

- `rules.set_name(data, name) -> AppData` — new; sets the *user's* name, not an
  allocation's. An empty string stores `None`, so "cleared" and "never set" are
  one state rather than two.
- `Tracker.set_name(name, now) -> DashboardView` — new.
- `DashboardView.user_name: str | None` — named to avoid colliding with an
  allocation's `name` in the same payload. Settings shows the current value and
  the recap uses it.
- `AllocationView.days_tracked: int` — the mock's `42 days tracked`, counted as
  distinct `day_anchor`s among that allocation's sessions.

`days_tracked` counts anchors rather than sessions: switching away and back
three times in one day is one day, not three.

## 6. The bridge

Four methods, the same shape as 3b — each applies a rule and returns the whole
view:

```
add_allocation(name: str, target_seconds: int)     -> dict
edit_allocation(id: str, name: str, target_seconds: int) -> dict
delete_allocation(id: str)                          -> dict
set_name(name: str)                                 -> dict
```

`Tracker` already has the first three from 3a; only `set_name` is new. As in 3b,
`Api` supplies `now` and no method may destroy the window.

## 7. What 3c finishes in 3b

The completion recap's static `Good work today!` becomes
`Good work today, {name}!` when a name is set, falling back to the generic line
when it is not. That completes PRD §18.2, and it is the only place 3c reaches
back into 3b.

## 8. Out of scope

**Notifications entirely.** The mock's Settings shows a `95%` chip and an on/off
toggle, but PRD §13 fixes both thresholds and §24 backlogs custom ones to P1.
Until 3d exists there is nothing for a toggle to control, so adding one now
means either a fake control or a preference the app ignores.

Also out: the duration parser (§4), reordering allocations, an archived view
(PRD §12 excludes it from V1), and anything in phase 4.

## 9. Testing

Python:

- `set_name` stores a name, and stores `None` for an empty string.
- `days_tracked` counts distinct day anchors, not sessions, and is zero for an
  allocation with no history.
- Each new `Api` method applies its rule and returns a serialisable view.
- Deleting the Active allocation ends its session and leaves the day coherent.

Frontend, in vitest as pure functions:

- The preset chips map to the right `hh`/`mm` values.
- The planned-total preview: current total, the edited allocation excluded, the
  new target added.
- Minute clamping: `0h 90m` becomes `1h 30m`.

A GUI test drives the real app: open Settings, add an allocation through the
form, and assert it appears on the dashboard.

## 10. Definition of done

1. The gear opens Settings; `×` returns to the dashboard.
2. `+ ADD ALLOCATION` creates one, and it appears on the dashboard.
3. `Edit` changes a name and target, and today's percentage moves immediately
   (PRD §12, §19).
4. `Delete` removes an allocation with no confirmation, and its sessions remain
   in the data file.
5. A user name set in Settings appears in the completion recap, and clearing
   it returns the generic line.
6. `SAVE` is unavailable for an empty name or a zero target.
7. The planned-total preview matches what the dashboard shows afterwards.
8. Both test suites pass.
