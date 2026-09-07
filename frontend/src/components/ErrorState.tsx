import styles from './EmptyState.module.css'

export function ErrorState({ message }: { message: string }) {
  return (
    <div className={styles.empty} data-error>
      <span className={styles.title}>Something went wrong</span>
      <span className={styles.body}>{message}</span>
    </div>
  )
}
