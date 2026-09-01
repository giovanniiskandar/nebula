import { useEffect } from 'react'
import styles from './App.module.css'

declare global {
  interface Window {
    // Both levels are optional: pywebview creates `window.pywebview` as soon
    // as its own api.js runs, but attaches the api methods later.
    pywebview?: {
      api?: {
        ui_ready?: () => Promise<boolean>
      }
    }
  }
}

export default function App() {
  useEffect(() => {
    // pywebview injects window.pywebview asynchronously and fires
    // `pywebviewready` when it lands. React may mount either side of that,
    // so handle both orders.
    const notify = () => {
      // The flag is set only once Python has returned, meaning the close
      // handler is actually bound. The element existing is not the same
      // thing: React renders it a round trip before the binding lands.
      void window.pywebview?.api?.ui_ready?.().then(() => {
        document.documentElement.dataset.nebulaReady = 'true'
      })
    }

    // Test for the method, not for `window.pywebview`. The object exists long
    // before its methods do, so checking the container fires too early and
    // throws a TypeError -- which React treats as a render failure and
    // responds to by unmounting the entire tree.
    if (window.pywebview?.api?.ui_ready) {
      notify()
      return
    }

    window.addEventListener('pywebviewready', notify, { once: true })
    return () => window.removeEventListener('pywebviewready', notify)
  }, [])

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
