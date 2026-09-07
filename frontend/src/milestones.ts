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
 * past 100%, and that must never notify.
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
