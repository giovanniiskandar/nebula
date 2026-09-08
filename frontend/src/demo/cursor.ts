/**
 * The drawn pointer the recording follows.
 *
 * The real cursor cannot be filmed -- a headless page has none, and a synthetic
 * click leaves no trace on screen -- so panels would appear to open by
 * themselves. This draws one, moves it, and pulses it on the frame the click
 * is dispatched.
 */

/** Where the pointer waits before the first beat: just off the card, bottom right. */
const START = { x: 300, y: 660 }
const PRESS_MS = 220

const easeInOut = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2

export interface Cursor {
  moveTo(x: number, y: number, durationMs: number): Promise<void>
  press(): Promise<void>
  position(): { x: number; y: number }
}

/**
 * The document's zoom, which the recording sets to paint the card at 2x.
 *
 * `getBoundingClientRect()` reports the zoomed size, while the pointer's own
 * `translate` is measured before zoom is applied -- so a target's rect has to
 * come back down by this factor or the pointer lands at twice its offset.
 */
function zoomFactor(): number {
  const zoom = Number(getComputedStyle(document.documentElement).zoom)
  return Number.isFinite(zoom) && zoom > 0 ? zoom : 1
}

export function createCursor(): Cursor {
  const root = document.createElement('div')
  root.className = 'demoCursor'
  root.innerHTML = `
    <span class="demoCursorRing"></span>
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <path d="M3 2 L3 16.5 L7 12.8 L9.6 18.6 L12.4 17.3 L9.8 11.6 L15 11.4 Z"
            fill="#f6f2ff" stroke="#15111d" stroke-width="1.4"
            stroke-linejoin="round" />
    </svg>`
  document.body.append(root)

  let { x, y } = START
  const place = (): void => {
    root.style.transform = `translate(${x}px, ${y}px)`
  }
  place()

  return {
    position: () => ({ x, y }),

    /** `nextX`/`nextY` are rect coordinates: zoomed, unlike this element. */
    moveTo(visualX, visualY, durationMs) {
      const zoom = zoomFactor()
      const nextX = visualX / zoom
      const nextY = visualY / zoom
      const fromX = x
      const fromY = y
      const start = performance.now()
      return new Promise((resolve) => {
        const step = (frame: number): void => {
          const t = Math.min(1, (frame - start) / durationMs)
          const eased = easeInOut(t)
          x = fromX + (nextX - fromX) * eased
          y = fromY + (nextY - fromY) * eased
          place()
          if (t < 1) requestAnimationFrame(step)
          else resolve()
        }
        requestAnimationFrame(step)
      })
    },

    press() {
      root.classList.add('isPressing')
      return new Promise((resolve) => {
        setTimeout(() => {
          root.classList.remove('isPressing')
          resolve()
        }, PRESS_MS)
      })
    },
  }
}
