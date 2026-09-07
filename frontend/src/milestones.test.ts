import { describe, expect, it } from 'vitest'
import { milestonesToAsk } from './milestones'
import type { AllocationView, DashboardView } from './types'

function allocation(over: Partial<AllocationView> = {}): AllocationView {
  return {
    id: 'a',
    name: 'Work',
    dailyTargetSeconds: 3600,
    trackedSeconds: 1800,
    state: 'ACTIVE',
    percentage: 50,
    remainingSeconds: 1800,
    activeSince: '2026-09-07T10:00:00+00:00',
    daysTracked: 1,
    notifiedMilestones: [],
    ...over,
  }
}

function view(allocations: AllocationView[]): DashboardView {
  return {
    status: 'ACTIVE',
    dayAnchor: '2026-09-07',
    dayEndDate: '2026-09-07',
    totalTrackedSeconds: 1800,
    totalTargetSeconds: 3600,
    breakStartedAt: null,
    userName: null,
    allocations,
  }
}

describe('milestonesToAsk', () => {
  it('asks nothing below 95%', () => {
    expect(milestonesToAsk(view([allocation({ percentage: 94.9 })]))).toBeNull()
  })

  it('asks once 95% is reached', () => {
    expect(milestonesToAsk(view([allocation({ percentage: 95 })]))).toBe('a')
  })

  it('stops asking once the milestone is recorded', () => {
    // Python has fired it; the view says so, which is what closes the loop.
    const done = allocation({ percentage: 96, notifiedMilestones: [95] })
    expect(milestonesToAsk(view([done]))).toBeNull()
  })

  it('asks again at 100% even though 95 was recorded', () => {
    const done = allocation({ percentage: 100, notifiedMilestones: [95] })
    expect(milestonesToAsk(view([done]))).toBe('a')
  })

  it('stops entirely once both are recorded', () => {
    const done = allocation({ percentage: 240, notifiedMilestones: [95, 100] })
    expect(milestonesToAsk(view([done]))).toBeNull()
  })

  it('ignores allocations that are not Active', () => {
    // Only accumulating time fires a milestone.
    const stale = allocation({ state: 'STALE', percentage: 100, activeSince: null })
    expect(milestonesToAsk(view([stale]))).toBeNull()
  })

  it('picks the Active allocation out of several', () => {
    const stale = allocation({ id: 'x', state: 'STALE', percentage: 100, activeSince: null })
    const active = allocation({ id: 'y', percentage: 99 })
    expect(milestonesToAsk(view([stale, active]))).toBe('y')
  })
})
