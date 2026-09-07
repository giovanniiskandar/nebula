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
  /** Distinct days this allocation has been worked on. */
  daysTracked: number
  /** Milestones already announced today. Empty until Python fires one. */
  notifiedMilestones: number[]
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
  /** The user's name (PRD §12), or null. Not an allocation's name. */
  userName: string | null
}
