/**
 * Entry point for the README recording (`assets/demo.gif`).
 *
 * Dev-only: `vite build` takes `index.html` as its single input, so nothing
 * under `src/demo/` reaches the shipped bundle. See `scripts/record-demo.mjs`.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import './demo.css'
import App from '../App.tsx'
import { installClock } from './clock'
import { runDemo } from './driver'
import { DEMO_MS } from './script'
import { installBridge } from './store'

// The recording wants 2x pixels, and Playwright's video is the viewport's own
// size -- asking it for a larger frame pads rather than scales. Zooming the
// document instead paints the 320px card at 640px, genuinely rendered rather
// than resampled, and leaves every coordinate in one space: `zoom` scales the
// whole CSS pixel grid, so the driver's rects and the drawn cursor still agree.
const scale = Number(new URLSearchParams(location.search).get('scale') ?? '1')
if (Number.isFinite(scale) && scale > 1) {
  document.documentElement.style.setProperty('zoom', String(scale))
}

// Both before the first render: App reads the clock and looks for the bridge as
// it mounts. Installed after, the app would sit waiting on a `pywebviewready`
// it had not yet subscribed to.
installClock()
installBridge()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Read by scripts/record-demo.mjs, so the length it encodes is the length the
// beat sheet actually plays rather than a constant kept in step by hand.
document.documentElement.dataset.demoMs = String(DEMO_MS)

// The first beats would otherwise be filmed in the fallback font: @fontsource
// serves JetBrains Mono locally, but the swap still lands after first paint.
void document.fonts.ready.then(runDemo)
