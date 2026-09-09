import { minimizedView } from '../minimized'
import type { DashboardView } from '../types'
import styles from './MinimizedCard.module.css'

interface Props {
  view: DashboardView
  nowMs: number
  onToggleBreak: () => void
  onComplete: () => void
  onExpand: () => void
}

/* Inline, because the app has no icon dependency and this is not the change
   that should add one. */
const Pause = () => (
  <svg width="11" height="11" viewBox="0 0 11 11" aria-hidden="true">
    <rect x="1.5" y="1" width="2.8" height="9" rx="1" fill="currentColor" />
    <rect x="6.7" y="1" width="2.8" height="9" rx="1" fill="currentColor" />
  </svg>
)

const Check = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <path
      d="M2 6.2 L4.6 8.8 L10 3.4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const Expand = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <path
      d="M7 1.6h3.4V5 M5 10.4H1.6V7"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

export function MinimizedCard({
  view,
  nowMs,
  onToggleBreak,
  onComplete,
  onExpand,
}: Props) {
  const bar = minimizedView(view, nowMs)

  return (
    <div className={`${styles.bar} ${styles[bar.tone]}`} data-minimized>
      <div className={styles.body}>
        <span className={styles.dot} />
        <div className={styles.text}>
          <span className={styles.title}>{bar.title}</span>
          <span className={styles.subtitle}>{bar.subtitle}</span>
        </div>
      </div>

      <div className={styles.controls}>
        <button
          type="button"
          data-mini-break
          aria-label="Break"
          className={`${styles.control} ${bar.tone === 'break' ? styles.engaged : ''}`}
          onClick={onToggleBreak}
        >
          <Pause />
        </button>
        <button
          type="button"
          data-mini-complete
          aria-label="Complete the day"
          className={`${styles.control} ${bar.tone === 'over' ? styles.urgent : ''}`}
          onClick={onComplete}
        >
          <Check />
        </button>
        <button
          type="button"
          data-expand
          aria-label="Expand"
          className={styles.control}
          onClick={onExpand}
        >
          <Expand />
        </button>
      </div>

      <span className={styles.track}>
        <span className={styles.fill} style={{ width: `${bar.barPercent}%` }} />
      </span>
      <span className={styles.day}>{bar.dayFigures}</span>
    </div>
  )
}
