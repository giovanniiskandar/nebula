import styles from './App.module.css'

export default function App() {
  return (
    <main className={styles.card}>
      <button
        className={styles.close}
        type="button"
        aria-label="Close"
        data-close
      >
        &times;
      </button>
      <h1 className={styles.title}>Hello world</h1>
      <p className={styles.sub}>Nebula &middot; 360 &times; 560</p>
    </main>
  )
}
