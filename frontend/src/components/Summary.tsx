import { formatDuration, formatPercent } from '../format'
import styles from './Summary.module.css'

interface Props {
  trackedSeconds: number
  targetSeconds: number
}

export function Summary({ trackedSeconds, targetSeconds }: Props) {
  const percentage = targetSeconds > 0 ? (trackedSeconds / targetSeconds) * 100 : 0
  return (
    <div className={styles.summary}>
      <div className={styles.figures}>
        <span className={styles.tracked}>{formatDuration(trackedSeconds)}</span>
        <span className={styles.caption}>
          tracked of {formatDuration(targetSeconds)} planned
        </span>
      </div>
      <span className={styles.percent}>{formatPercent(percentage)}</span>
    </div>
  )
}
