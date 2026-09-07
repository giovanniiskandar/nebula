import type { DashboardView } from './types'

/**
 * The view as of `nowMs`, with the one Active allocation advanced.
 *
 * The advance is `nowMs - fetchedAtMs`, NOT `nowMs - activeSince`.
 * `trackedSeconds` already counts the open session up to the moment Python
 * built the view, so measuring from `activeSince` would count that stretch
 * twice and the figure would jump on every refetch.
 *
 * A pure function of its three arguments, recomputed rather than incremented,
 * so a missed interval cannot drift. The caller must always tick the raw view
 * from the bridge, never a previously ticked one.
 */
export function tickView(
  view: DashboardView,
  nowMs: number,
  fetchedAtMs: number,
): DashboardView {
  const elapsed = Math.max(0, Math.floor((nowMs - fetchedAtMs) / 1000))
  if (elapsed === 0) return view

  let delta = 0
  const allocations = view.allocations.map((allocation) => {
    if (allocation.state !== 'ACTIVE' || allocation.activeSince === null) {
      return allocation
    }
    const tracked = allocation.trackedSeconds + elapsed
    delta += elapsed
    return {
      ...allocation,
      trackedSeconds: tracked,
      remainingSeconds: allocation.dailyTargetSeconds - tracked,
      percentage:
        allocation.dailyTargetSeconds > 0
          ? (tracked / allocation.dailyTargetSeconds) * 100
          : 0,
    }
  })

  return {
    ...view,
    allocations,
    totalTrackedSeconds: view.totalTrackedSeconds + delta,
  }
}

/** Seconds since Break began, or null when not on Break. */
export function breakSeconds(view: DashboardView, nowMs: number): number | null {
  if (view.status !== 'BREAK' || view.breakStartedAt === null) return null
  return Math.max(0, Math.floor((nowMs - Date.parse(view.breakStartedAt)) / 1000))
}
