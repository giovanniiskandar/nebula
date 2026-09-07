import { describe, expect, it } from 'vitest'
import { breakSeconds, tickView } from './tick'
import type { DashboardView } from './types'

const STARTED = '2026-09-07T10:00:00+00:00'
/** When Python built the view: 10 minutes of the open session already counted. */
const FETCHED = Date.parse('2026-09-07T10:10:00+00:00')
const NOW = Date.parse('2026-09-07T10:40:00+00:00')

function view(overrides: Partial<DashboardView> = {}): DashboardView {
  return {
    status: 'ACTIVE',
    dayAnchor: '2026-09-07',
    dayEndDate: '2026-09-07',
    totalTrackedSeconds: 600,
    totalTargetSeconds: 10800,
    breakStartedAt: null,
    userName: null,
    allocations: [
      {
        id: 'a',
        name: 'Work',
        dailyTargetSeconds: 10800,
        trackedSeconds: 600,
        state: 'ACTIVE',
        percentage: (600 / 10800) * 100,
        remainingSeconds: 10200,
        activeSince: STARTED,
        daysTracked: 0,
      },
    ],
    ...overrides,
  }
}

describe('tickView', () => {
  it('advances by time since the view was fetched, not since the session began', () => {
    // trackedSeconds already counts 10:00 to 10:10. Only the 30 minutes since
    // the fetch may be added; measuring from activeSince would give 2400.
    const ticked = tickView(view(), NOW, FETCHED)
    expect(ticked.allocations[0].trackedSeconds).toBe(600 + 1800)
  })

  it('changes nothing when no time has passed', () => {
    expect(tickView(view(), FETCHED, FETCHED)).toEqual(view())
  })

  it('recomputes percentage and remaining from the advanced value', () => {
    const allocation = tickView(view(), NOW, FETCHED).allocations[0]
    expect(allocation.remainingSeconds).toBe(10800 - 2400)
    expect(allocation.percentage).toBeCloseTo((2400 / 10800) * 100)
  })

  it('updates the overall total', () => {
    expect(tickView(view(), NOW, FETCHED).totalTrackedSeconds).toBe(2400)
  })

  it('leaves Stale and Not Started allocations alone', () => {
    const stale = view({
      status: 'NEUTRAL',
      allocations: [
        {
          id: 'b',
          name: 'Learning',
          dailyTargetSeconds: 7200,
          trackedSeconds: 2160,
          state: 'STALE',
          percentage: 30,
          remainingSeconds: 5040,
          activeSince: null,
          daysTracked: 0,
        },
      ],
    })
    expect(tickView(stale, NOW, FETCHED).allocations[0].trackedSeconds).toBe(2160)
  })

  it('goes past the target rather than capping (PRD §8)', () => {
    const over = view({
      allocations: [
        {
          id: 'a',
          name: 'Work',
          dailyTargetSeconds: 3600,
          trackedSeconds: 3000,
          state: 'ACTIVE',
          percentage: (3000 / 3600) * 100,
          remainingSeconds: 600,
          activeSince: STARTED,
          daysTracked: 0,
        },
      ],
    })
    const ticked = tickView(over, NOW, FETCHED).allocations[0]
    expect(ticked.percentage).toBeCloseTo((4800 / 3600) * 100)
    expect(ticked.remainingSeconds).toBe(-1200)
  })

  it('is a pure function of its arguments', () => {
    const raw = view()
    expect(tickView(raw, NOW, FETCHED)).toEqual(tickView(raw, NOW, FETCHED))
    expect(raw.allocations[0].trackedSeconds).toBe(600)
  })
})

describe('breakSeconds', () => {
  it('measures from breakStartedAt, which counts nothing beforehand', () => {
    const onBreak = view({ status: 'BREAK', breakStartedAt: STARTED })
    expect(breakSeconds(onBreak, NOW)).toBe(2400)
  })

  it('is null when not on Break', () => {
    expect(breakSeconds(view(), NOW)).toBeNull()
  })
})
