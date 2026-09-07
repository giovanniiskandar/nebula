export type Status = 'ACTIVE' | 'BREAK' | 'NEUTRAL'
export type AllocationState = 'NOT_STARTED' | 'ACTIVE' | 'STALE'

export interface AllocationView {
  id: string
  name: string
  dailyTargetSeconds: number
  trackedSeconds: number
  state: AllocationState
  percentage: number
  remainingSeconds: number
  /** ISO instant the open session started, or null when not Active. */
  activeSince: string | null
}

export interface DashboardView {
  status: Status
  dayAnchor: string
  dayEndDate: string
  allocations: AllocationView[]
  totalTrackedSeconds: number
  totalTargetSeconds: number
  /** ISO instant the Break began, or null when not on Break. */
  breakStartedAt: string | null
}
