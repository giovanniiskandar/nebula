import { describe, expect, it } from 'vitest'
import { minimizedView } from './minimized'
import type { AllocationView, DashboardView } from './types'

const NOW = Date.parse('2026-09-09T10:00:00Z')

function allocation(over: Partial<AllocationView> = {}): AllocationView {
  return {
    id: 'a1',
    name: 'Work',
    dailyTargetSeconds: 10800,
    trackedSeconds: 8640,
    state: 'ACTIVE',
    percentage: 80,
    remainingSeconds: 2160,
    activeSince: '2026-09-09T08:00:00Z',
    daysTracked: 3,
    notifiedMilestones: [],
    ...over,
  }
}

function view(over: Partial<DashboardView> = {}): DashboardView {
  return {
    status: 'ACTIVE',
    dayAnchor: '2026-09-09',
    dayEndDate: '2026-09-10',
    allocations: [allocation()],
    totalTrackedSeconds: 15000,
    totalTargetSeconds: 25200,
    breakStartedAt: null,
    userName: null,
    ...over,
  }
}

describe('the minimized bar', () => {
  it('names the Active allocation and its figures', () => {
    const bar = minimizedView(view(), NOW)
    expect(bar.tone).toBe('active')
    expect(bar.title).toBe('Work')
    expect(bar.subtitle).toBe('2h 24m / 3h · 80%')
    expect(bar.barPercent).toBe(80)
  })

  it('always reports the day as a whole', () => {
    expect(minimizedView(view(), NOW).dayFigures).toBe('4h 10m / 7h · 60%')
  })

  it('counts the break rather than an allocation', () => {
    const bar = minimizedView(
      view({
        status: 'BREAK',
        breakStartedAt: '2026-09-09T09:48:00Z',
        allocations: [allocation({ state: 'STALE', activeSince: null })],
      }),
      NOW,
    )
    expect(bar.tone).toBe('break')
    expect(bar.title).toBe('On break · 12m')
    expect(bar.subtitle).toBe('nothing accumulating')
  })

  it('turns over-allocation amber and keeps the bar inside the track', () => {
    const bar = minimizedView(
      view({
        allocations: [
          allocation({ trackedSeconds: 13500, percentage: 125, remainingSeconds: -2700 }),
        ],
      }),
      NOW,
    )
    expect(bar.tone).toBe('over')
    expect(bar.subtitle).toBe('3h 45m / 3h · 125%')
    // The percentage is honest; the bar is clamped, as the full card does.
    expect(bar.barPercent).toBe(100)
  })

  it('says so when nothing is being tracked', () => {
    const bar = minimizedView(
      view({
        status: 'NEUTRAL',
        allocations: [allocation({ state: 'STALE', activeSince: null })],
      }),
      NOW,
    )
    expect(bar.tone).toBe('idle')
    expect(bar.title).toBe('Nothing tracking')
    expect(bar.subtitle).toBe('')
  })

  it('still reports the day on an empty one', () => {
    const bar = minimizedView(
      view({ status: 'NEUTRAL', allocations: [], totalTrackedSeconds: 0, totalTargetSeconds: 0 }),
      NOW,
    )
    expect(bar.tone).toBe('idle')
    expect(bar.dayFigures).toBe('0m / 0m · 0%')
  })
})
