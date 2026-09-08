/**
 * An in-memory stand-in for the Python tracker, for the demo recording.
 *
 * It implements the same `window.pywebview.api` surface `bridge.ts` declares,
 * so the recording drives the real components down the real code path -- only
 * the day's data is invented. Where behaviour could differ, it follows
 * `rules.py`: Break is a pause/resume toggle rather than a deselect, and an
 * open session is folded into `trackedSeconds` when it closes.
 */

import type { AllocationView, DashboardView, Status } from '../types'
import { now } from './clock'

interface Row {
  id: string
  name: string
  targetSeconds: number
  /** Closed sessions only; the open one is added when the view is built. */
  trackedSeconds: number
  daysTracked: number
}

const rows: Row[] = []
let status: Status = 'NEUTRAL'
let activeId: string | null = null
let activeSince: string | null = null
let preBreakId: string | null = null
let breakStartedAt: string | null = null
let userName: string | null = null
let seq = 0

const iso = (): string => new Date(now()).toISOString()
const date = (offsetDays = 0): string =>
  new Date(now() + offsetDays * 86_400_000).toISOString().slice(0, 10)

/** Seconds on the open session, or 0 when this row is not the Active one. */
function openSeconds(row: Row): number {
  if (row.id !== activeId || activeSince === null) return 0
  return Math.max(0, Math.floor((now() - Date.parse(activeSince)) / 1000))
}

/** Close the open session, keeping the seconds it earned. */
function settle(): void {
  const row = rows.find((candidate) => candidate.id === activeId)
  if (row !== undefined) row.trackedSeconds += openSeconds(row)
  activeSince = null
}

function toView(row: Row): AllocationView {
  const tracked = row.trackedSeconds + openSeconds(row)
  const isActive = row.id === activeId && status === 'ACTIVE'
  return {
    id: row.id,
    name: row.name,
    dailyTargetSeconds: row.targetSeconds,
    trackedSeconds: tracked,
    state: isActive ? 'ACTIVE' : tracked > 0 ? 'STALE' : 'NOT_STARTED',
    percentage:
      row.targetSeconds > 0 ? (tracked / row.targetSeconds) * 100 : 0,
    remainingSeconds: row.targetSeconds - tracked,
    activeSince: isActive ? activeSince : null,
    daysTracked: row.daysTracked,
    notifiedMilestones: [],
  }
}

function view(): DashboardView {
  const allocations = rows.map(toView)
  return {
    status,
    dayAnchor: date(),
    dayEndDate: date(1),
    allocations,
    totalTrackedSeconds: allocations.reduce((t, a) => t + a.trackedSeconds, 0),
    totalTargetSeconds: allocations.reduce((t, a) => t + a.dailyTargetSeconds, 0),
    breakStartedAt,
    userName,
  }
}

/** Every method resolves, matching pywebview's promise-returning bridge. */
export const api = {
  ui_ready: () => Promise.resolve(view()),

  resume: () => {
    if (preBreakId !== null) {
      activeId = preBreakId
      activeSince = iso()
      status = 'ACTIVE'
    }
    return Promise.resolve(view())
  },

  activate: (allocationId: string) => {
    settle()
    activeId = allocationId
    activeSince = iso()
    status = 'ACTIVE'
    breakStartedAt = null
    return Promise.resolve(view())
  },

  toggle_break: () => {
    if (status === 'BREAK') {
      activeId = preBreakId
      activeSince = preBreakId === null ? null : iso()
      status = preBreakId === null ? 'NEUTRAL' : 'ACTIVE'
      breakStartedAt = null
    } else {
      settle()
      preBreakId = activeId
      status = 'BREAK'
      breakStartedAt = iso()
    }
    return Promise.resolve(view())
  },

  complete_day: () => {
    settle()
    preBreakId = activeId
    activeId = null
    status = 'NEUTRAL'
    breakStartedAt = null
    return Promise.resolve(view())
  },

  add_allocation: (name: string, targetSeconds: number) => {
    seq += 1
    rows.push({
      id: `demo-${seq}`,
      name,
      targetSeconds,
      trackedSeconds: 0,
      daysTracked: 0,
    })
    return Promise.resolve(view())
  },

  edit_allocation: (allocationId: string, name: string, targetSeconds: number) => {
    const row = rows.find((candidate) => candidate.id === allocationId)
    if (row !== undefined) {
      row.name = name
      row.targetSeconds = targetSeconds
    }
    return Promise.resolve(view())
  },

  delete_allocation: (allocationId: string) => {
    const index = rows.findIndex((candidate) => candidate.id === allocationId)
    if (index !== -1) rows.splice(index, 1)
    if (activeId === allocationId) {
      activeId = null
      activeSince = null
      status = 'NEUTRAL'
    }
    return Promise.resolve(view())
  },

  set_name: (name: string) => {
    userName = name.trim() === '' ? null : name.trim()
    return Promise.resolve(view())
  },

  // Nothing to announce: the demo never crosses a milestone.
  check_milestones: () => Promise.resolve(view()),
}

/** Hand the app its bridge, then let it start (App.tsx listens for this). */
export function installBridge(): void {
  window.pywebview = { api }
  window.dispatchEvent(new Event('pywebviewready'))
}
