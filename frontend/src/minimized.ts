import { formatDuration, formatPercent } from './format'
import { breakSeconds } from './tick'
import type { DashboardView } from './types'

/** Which of the palette's roles the bar wears: dot, figures and bar fill. */
export type Tone = 'active' | 'break' | 'over' | 'idle'

export interface MinimizedView {
  tone: Tone
  title: string
  subtitle: string
  /** Clamped to the track, like the full card's row (PRD §8). */
  barPercent: number
  /** The day as a whole, shown in every state. */
  dayFigures: string
}

const figures = (tracked: number, target: number, percentage: number): string =>
  `${formatDuration(tracked)} / ${formatDuration(target)} · ${formatPercent(percentage)}`

/**
 * The bar's contents, derived rather than rendered.
 *
 * A component would hide this branching from vitest -- the repo tests modules,
 * not components -- and the four states are the whole feature.
 */
export function minimizedView(view: DashboardView, nowMs: number): MinimizedView {
  const dayPercentage =
    view.totalTargetSeconds > 0
      ? (view.totalTrackedSeconds / view.totalTargetSeconds) * 100
      : 0
  const dayFigures = figures(
    view.totalTrackedSeconds,
    view.totalTargetSeconds,
    dayPercentage,
  )

  const onBreak = breakSeconds(view, nowMs)
  if (onBreak !== null) {
    return {
      tone: 'break',
      title: `On break · ${formatDuration(onBreak)}`,
      subtitle: 'nothing accumulating',
      barPercent: Math.min(100, dayPercentage),
      dayFigures,
    }
  }

  const active = view.allocations.find((allocation) => allocation.state === 'ACTIVE')
  if (active === undefined) {
    // A day not yet started, or one already completed. It still has totals, so
    // the bar says something true rather than disabling the control.
    return {
      tone: 'idle',
      title: 'Nothing tracking',
      subtitle: '',
      barPercent: Math.min(100, dayPercentage),
      dayFigures,
    }
  }

  return {
    tone: active.percentage > 100 ? 'over' : 'active',
    title: active.name,
    subtitle: figures(
      active.trackedSeconds,
      active.dailyTargetSeconds,
      active.percentage,
    ),
    barPercent: Math.min(100, Math.max(0, active.percentage)),
    dayFigures,
  }
}
