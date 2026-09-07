import { describe, expect, it } from 'vitest'
import {
  PRESETS,
  clampMinutes,
  joinTarget,
  plannedAfter,
  splitTarget,
} from './targets'
import type { DashboardView } from './types'

function view(): DashboardView {
  return {
    status: 'NEUTRAL',
    dayAnchor: '2026-09-07',
    dayEndDate: '2026-09-07',
    totalTrackedSeconds: 0,
    totalTargetSeconds: 5 * 3600,
    breakStartedAt: null,
    userName: null,
    allocations: [
      {
        id: 'a',
        name: 'Work',
        dailyTargetSeconds: 3 * 3600,
        trackedSeconds: 0,
        state: 'NOT_STARTED',
        percentage: 0,
        remainingSeconds: 3 * 3600,
        activeSince: null,
        daysTracked: 0,
        notifiedMilestones: [],
      },
      {
        id: 'b',
        name: 'Learning',
        dailyTargetSeconds: 2 * 3600,
        trackedSeconds: 0,
        state: 'NOT_STARTED',
        percentage: 0,
        remainingSeconds: 2 * 3600,
        activeSince: null,
        daysTracked: 0,
        notifiedMilestones: [],
      },
    ],
  }
}

describe('splitTarget / joinTarget', () => {
  it('splits seconds into hours and minutes', () => {
    expect(splitTarget(3 * 3600 + 30 * 60)).toEqual({ hours: 3, minutes: 30 })
  })

  it('splits zero', () => {
    expect(splitTarget(0)).toEqual({ hours: 0, minutes: 0 })
  })

  it('joins back to seconds', () => {
    expect(joinTarget(1, 30)).toBe(5400)
  })

  it('round-trips', () => {
    const parts = splitTarget(7830)
    expect(joinTarget(parts.hours, parts.minutes)).toBe(7800)
  })
})

describe('clampMinutes', () => {
  it('carries minutes above 59 into hours', () => {
    expect(clampMinutes({ hours: 0, minutes: 90 })).toEqual({ hours: 1, minutes: 30 })
  })

  it('leaves valid values alone', () => {
    expect(clampMinutes({ hours: 2, minutes: 15 })).toEqual({ hours: 2, minutes: 15 })
  })

  it('floors negatives at zero', () => {
    expect(clampMinutes({ hours: -1, minutes: -5 })).toEqual({ hours: 0, minutes: 0 })
  })
})

describe('PRESETS', () => {
  it('offers the five choices from the mock', () => {
    expect(PRESETS.map((p) => p.label)).toEqual(['30m', '1h', '2h', '3h', '4h'])
  })

  it('maps each label to its seconds', () => {
    expect(PRESETS.map((p) => p.seconds)).toEqual([1800, 3600, 7200, 10800, 14400])
  })
})

describe('plannedAfter', () => {
  it('adds a new allocation to the current total', () => {
    // 3h + 2h existing, plus a new 3h.
    expect(plannedAfter(view(), null, 3 * 3600)).toBe(8 * 3600)
  })

  it('replaces the edited allocation rather than adding to it', () => {
    // Editing Work from 3h to 4h: 4h + 2h, not 3h + 2h + 4h.
    expect(plannedAfter(view(), 'a', 4 * 3600)).toBe(6 * 3600)
  })

  it('handles editing down', () => {
    expect(plannedAfter(view(), 'a', 3600)).toBe(3 * 3600)
  })
})
