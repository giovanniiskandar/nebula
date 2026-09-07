import styles from './Controls.module.css'

interface Props {
  onBreakNow: boolean
  onToggleBreak: () => void
  onComplete: () => void
}

export function Controls({ onBreakNow, onToggleBreak, onComplete }: Props) {
  return (
    <div className={styles.controls}>
      <div className={styles.row}>
        <button
          type="button"
          data-break
          className={`${styles.button} ${onBreakNow ? styles.engaged : ''}`}
          onClick={onToggleBreak}
        >
          {onBreakNow ? 'ON BREAK' : 'BREAK'}
        </button>
        <button
          type="button"
          data-complete
          className={styles.button}
          onClick={onComplete}
        >
          COMPLETE
        </button>
      </div>
      <span className={styles.hint}>
        {onBreakNow
          ? 'pick an allocation to resume'
          : 'click any allocation to switch'}
      </span>
    </div>
  )
}
