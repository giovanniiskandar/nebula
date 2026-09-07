import styles from './EmptyState.module.css'

export function EmptyState() {
  return (
    <div className={styles.empty} data-empty>
      <span className={styles.title}>Plan your day</span>
      <span className={styles.body}>Create your first time allocation.</span>
      {/* Enabled in 3c, which adds allocation management. */}
      <button type="button" className={styles.add} disabled>
        + Add Allocation
      </button>
    </div>
  )
}
