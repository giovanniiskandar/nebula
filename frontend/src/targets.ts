import type { DashboardView } from './types'

/** Target arithmetic: seconds to and from hh/mm, and the day's planned total. */

const HOUR = 3600
const MINUTE = 60

export const PRESETS = [
  { label: '30m', seconds: 30 * MINUTE },
  { label: '1h', seconds: HOUR },
  { label: '2h', seconds: 2 * HOUR },
  { label: '3h', seconds: 3 * HOUR },
  { label: '4h', seconds: 4 * HOUR },
] as const

export function splitTarget(seconds: number): { hours: number; minutes: number } {
  const total = Math.max(0, Math.floor(seconds))
  return {
    hours: Math.floor(total / HOUR),
    minutes: Math.floor((total % HOUR) / MINUTE),
  }
}

export function joinTarget(hours: number, minutes: number): number {
  return Math.max(0, hours) * HOUR + Math.max(0, minutes) * MINUTE
}

/**
 * Carry minutes above 59 into hours instead of rejecting them.
 *
 * The structured input exists so nothing invalid can be expressed; `0h 90m` is
 * a clear intention, so it becomes `1h 30m` rather than an error message.
 */
export function clampMinutes(parts: {
  hours: number
  minutes: number
}): { hours: number; minutes: number } {
  return splitTarget(joinTarget(parts.hours, parts.minutes))
}

/**
 * The day's planned total once this target is saved.
 *
 * `allocationId` is the allocation being edited, whose existing target is
 * replaced rather than added to; `null` when adding a new one.
 */
export function plannedAfter(
  view: DashboardView,
  allocationId: string | null,
  targetSeconds: number,
): number {
  const others = view.allocations
    .filter((a) => a.id !== allocationId)
    .reduce((total, a) => total + a.dailyTargetSeconds, 0)
  return others + targetSeconds
}
