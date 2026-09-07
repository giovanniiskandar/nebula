import { formatDayLabel, formatDuration } from '../format'
import styles from './Header.module.css'

interface Props {
  dayAnchor: string
  breakSeconds: number | null
}

export function Header({ dayAnchor, breakSeconds }: Props) {
  return (
    <header className={styles.header}>
      <span className={styles.today}>TODAY</span>
      {breakSeconds === null ? (
        <span className={styles.date}>{formatDayLabel(dayAnchor)}</span>
      ) : (
        <span className={styles.onBreak}>
          ON BREAK · {formatDuration(breakSeconds)}
        </span>
      )}
    </header>
  )
}
