import { formatDuration, formatPercent } from '../format'
import type { DashboardView } from '../types'
import styles from './CompletionPopup.module.css'

interface Props {
  view: DashboardView
  onStart: () => void
}

export function CompletionPopup({ view, onStart }: Props) {
  return (
    <div className={styles.popup} data-completion>
      <span className={styles.title}>TODAY&apos;S RESULT</span>
      <div className={styles.rows}>
        {view.allocations.map((allocation) => (
          <div key={allocation.id} className={styles.row}>
            <span className={styles.name}>{allocation.name}</span>
            <span className={styles.figures}>
              {formatDuration(allocation.trackedSeconds)} /{' '}
              {formatDuration(allocation.dailyTargetSeconds)}
            </span>
            <span className={styles.percent}>
              {formatPercent(allocation.percentage)}
            </span>
          </div>
        ))}
      </div>
      {/* PRD §18.2 personalises this with the Name from Settings, which does
          not exist until 3c. The PRD specifies this generic fallback. */}
      <span className={styles.message}>Good work today!</span>
      <button type="button" className={styles.start} data-start onClick={onStart}>
        Start
      </button>
    </div>
  )
}
