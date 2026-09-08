/**
 * A time-lapse clock for the demo recording.
 *
 * The dashboard's figures are not faked: they come from the app's own tick,
 * which advances the Active allocation from `Date.now()` (see `tick.ts`).
 * Making an hour of tracking visible inside a twelve-second recording therefore
 * means speeding up time itself rather than writing numbers into the view.
 *
 * Demo-only. `demo.html` is not an input to `vite build`, so none of this
 * reaches the shipped bundle.
 */

const realNow = Date.now.bind(Date)
const realSetInterval = window.setInterval.bind(window)
export const realSetTimeout = window.setTimeout.bind(window)

/**
 * What the app's one-second poll actually waits.
 *
 * Left at 1000, a warp would land in a frame or two and the progress bar would
 * jump; at 40ms the figures and the bar climb instead.
 */
const TICK_MS = 40

let virtualMs = realNow()
let lastRealMs = realNow()
let rate = 1

/** Virtual time now, accruing whatever rate has been in force since the last read. */
function advance(): number {
  const real = realNow()
  virtualMs += (real - lastRealMs) * rate
  lastRealMs = real
  return virtualMs
}

export const now = (): number => advance()

/** Must run before React mounts: the app reads the clock in its first render. */
export function installClock(): void {
  Date.now = advance
  window.setInterval = ((
    handler: TimerHandler,
    ms?: number,
    ...args: unknown[]
  ) =>
    realSetInterval(
      handler,
      ms === 1000 ? TICK_MS : ms,
      ...args,
    )) as typeof window.setInterval
}

/** Let `seconds` of virtual time pass over `durationMs` of real time. */
export function warp(seconds: number, durationMs: number): Promise<void> {
  advance()
  rate = (seconds * 1000) / durationMs
  return new Promise((resolve) => {
    realSetTimeout(() => {
      advance()
      rate = 1
      resolve()
    }, durationMs)
  })
}
