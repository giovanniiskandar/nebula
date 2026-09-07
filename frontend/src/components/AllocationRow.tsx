import { formatDuration, formatLeft, formatPercent } from '../format'
import type { AllocationView } from '../types'
import styles from './AllocationRow.module.css'

const BADGE: Record<AllocationView['state'], string> = {
  ACTIVE: 'ACTIVE',
  STALE: 'STALE',
  NOT_STARTED: 'NOT STARTED',
}

interface Props {
  allocation: AllocationView
  onActivate: (id: string) => void
}

export function AllocationRow({ allocation, onActivate }: Props) {
  const over = allocation.remainingSeconds < 0
  // The bar clamps, the percentage does not: going past the target is the
  // point, and the row turns amber instead (PRD §8).
  const width = Math.min(100, Math.max(0, allocation.percentage))

  return (
    <button
      type="button"
      className={`${styles.row} ${styles[allocation.state]} ${over ? styles.over : ''}`}
      onClick={() => onActivate(allocation.id)}
    >
      <span className={styles.line}>
        <span className={styles.name} data-allocation-name>
          {allocation.name}
        </span>
        <span className={styles.badge}>{BADGE[allocation.state]}</span>
      </span>
      <span className={styles.line}>
        <span className={styles.numbers}>
          {formatDuration(allocation.trackedSeconds)}{' '}
          <span className={styles.target}>
            / {formatDuration(allocation.dailyTargetSeconds)}
          </span>
        </span>
        <span className={styles.percent}>
          {formatPercent(allocation.percentage)}
        </span>
      </span>
      <span className={styles.track}>
        <span className={styles.fill} style={{ width: `${width}%` }} />
      </span>
      <span className={styles.captionLine}>
        <span className={styles.caption}>
          {formatLeft(allocation.remainingSeconds)}
        </span>
        {over && (
          <span className={styles.marker}>
            target {formatDuration(allocation.dailyTargetSeconds)} ↑
          </span>
        )}
      </span>
    </button>
  )
}
