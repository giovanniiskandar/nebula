import { useEffect, useState } from 'react'
import styles from './App.module.css'
import * as bridge from './bridge'
import { AllocationRow } from './components/AllocationRow'
import { CompletionPopup } from './components/CompletionPopup'
import { Controls } from './components/Controls'
import { EmptyState } from './components/EmptyState'
import { ErrorState } from './components/ErrorState'
import { Header } from './components/Header'
import { Summary } from './components/Summary'
import { breakSeconds, tickView } from './tick'
import type { DashboardView } from './types'

export default function App() {
  const [view, setView] = useState<DashboardView | null>(null)
  const [nowMs, setNowMs] = useState(() => Date.now())
  const [fetchedAtMs, setFetchedAtMs] = useState(() => Date.now())
  const [error, setError] = useState<string | null>(null)
  const [completed, setCompleted] = useState<DashboardView | null>(null)

  // Every view must stamp when it arrived: the tick advances from that moment,
  // not from activeSince, which trackedSeconds has already counted up to.
  const receive = (next: DashboardView) => {
    setView(next)
    setFetchedAtMs(Date.now())
  }

  // A corrupt data file reaches here as a rejected promise: pywebview turns an
  // exception in a js_api method into a rejection carrying its message.
  const apply = (next: Promise<DashboardView>) =>
    void next.then(receive).catch((reason: Error) => setError(String(reason)))

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    // pywebview injects window.pywebview asynchronously and fires
    // `pywebviewready` when it lands. React may mount either side of that,
    // so handle both orders.
    const start = () => {
      void bridge
        .uiReady()
        .then((next) => {
          receive(next)
        })
        .catch((reason: Error) => setError(String(reason)))
        .finally(() => {
          document.documentElement.dataset.nebulaReady = 'true'
        })
    }

    if (window.pywebview?.api?.ui_ready) {
      start()
      return
    }
    window.addEventListener('pywebviewready', start, { once: true })
    return () => window.removeEventListener('pywebviewready', start)
  }, [])

  // Derived for rendering only. Storing a ticked view would double count on
  // the next tick.
  const ticked = view === null ? null : tickView(view, nowMs, fetchedAtMs)

  if (error !== null) {
    return (
      <main className={styles.card}>
        <button className={styles.close} type="button" aria-label="Close" data-close>
          &times;
        </button>
        <ErrorState message={error} />
      </main>
    )
  }

  return (
    <main className={styles.card}>
      {/* Always rendered, never behind the data. Python binds this during
          ui_ready, which runs before the first view arrives -- and the window
          is frameless, so without it there is no way to close the app. */}
      <button className={styles.close} type="button" aria-label="Close" data-close>
        &times;
      </button>
      {completed !== null && (
        <CompletionPopup
          view={completed}
          onStart={() => {
            setCompleted(null)
            apply(bridge.resume())
          }}
        />
      )}
      {ticked !== null && (
        <>
          <Header
            dayAnchor={ticked.dayAnchor}
            breakSeconds={breakSeconds(ticked, nowMs)}
          />
          <Summary
            trackedSeconds={ticked.totalTrackedSeconds}
            targetSeconds={ticked.totalTargetSeconds}
          />
          {ticked.allocations.length === 0 ? (
            <EmptyState />
          ) : (
            <div className={styles.list}>
              {ticked.allocations.map((allocation) => (
                <AllocationRow
                  key={allocation.id}
                  allocation={allocation}
                  onActivate={(id) => apply(bridge.activate(id))}
                />
              ))}
            </div>
          )}
          <Controls
            onBreakNow={ticked.status === 'BREAK'}
            onToggleBreak={() => apply(bridge.toggleBreak())}
            onComplete={() =>
              void bridge
                .completeDay()
                .then((next) => {
                  receive(next)
                  setCompleted(next)
                })
                .catch((reason: Error) => setError(String(reason)))
            }
          />
        </>
      )}
    </main>
  )
}
