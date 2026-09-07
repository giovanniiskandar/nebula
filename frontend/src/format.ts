/** Duration and date formatting. The only real logic in the frontend. */

const HOUR = 3600
const MINUTE = 60

/** `2h 24m`, `36m`, `3h`, `0m`. Seconds are truncated, never rounded up. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(total / HOUR)
  const minutes = Math.floor((total % HOUR) / MINUTE)

  if (hours === 0) return `${minutes}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

/** `36m left`, or `45m over allocation` past the target (PRD §8). */
export function formatLeft(remainingSeconds: number): string {
  if (remainingSeconds < 0) {
    return `${formatDuration(-remainingSeconds)} over allocation`
  }
  return `${formatDuration(remainingSeconds)} left`
}

/** Never capped: going past 100% is the point (PRD §8). */
export function formatPercent(percentage: number): string {
  return `${Math.round(percentage)}%`
}

/** `MON 31 AUG`, from a `YYYY-MM-DD` date. */
export function formatDayLabel(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  // Construct locally: `new Date('2026-08-31')` parses as UTC and can land on
  // the previous day west of Greenwich.
  const date = new Date(year, month - 1, day)
  const weekday = date.toLocaleDateString('en-GB', { weekday: 'short' })
  const monthName = date.toLocaleDateString('en-GB', { month: 'short' })
  return `${weekday} ${day} ${monthName}`.toUpperCase()
}
