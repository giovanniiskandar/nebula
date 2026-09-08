import styles from './EmptyState.module.css'

interface Props {
  onAdd: () => void
}

export function EmptyState({ onAdd }: Props) {
  return (
    <div className={styles.empty} data-empty>
      <span className={styles.title}>Plan your day</span>
      <span className={styles.body}>Create your first time allocation.</span>
      {/* The first thing a new user sees. It opens the same form the Settings
          panel does -- nothing on this screen points at the gear, so leaving
          this inert made the app look broken on first run. */}
      <button type="button" className={styles.add} data-empty-add onClick={onAdd}>
        + Add Allocation
      </button>
    </div>
  )
}
