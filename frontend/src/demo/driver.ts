/**
 * Plays the beat sheet against the running app.
 *
 * Every beat acts on the real DOM -- a real click on the real button, a real
 * `input` event React will hear -- so the recording shows the app working
 * rather than a reconstruction of it. Only the clock and the data are ours.
 */

import { realSetTimeout, warp } from './clock'
import { createCursor, type Cursor } from './cursor'
import { BEATS, DEMO_MS, type Beat } from './script'

/** Kept in step with `PRESS_MS` in cursor.ts: the tail of every click beat. */
const PRESS_MS = 220
/** The cursor's travel to an input before the first character lands. */
const REACH_MS = 150
/**
 * Throwaway frames before the first beat.
 *
 * VP8 spends its first fraction of a second finding a bitrate, so the opening
 * frames of a capture are soft. The recorder keeps the last twelve seconds
 * (`record-demo.mjs`), which is exactly the pre-roll it discards.
 */
const PREROLL_MS = 700

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => realSetTimeout(resolve, Math.max(0, ms)))

/**
 * React renders in response to the beat before this one, so the element may be
 * a frame away. Missing it outright is a broken beat sheet, and saying which
 * beat beats debugging a recording that silently stops moving.
 */
async function find(selector: string): Promise<HTMLElement> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const element = document.querySelector<HTMLElement>(selector)
    if (element !== null) return element
    await sleep(10)
  }
  throw new Error(`demo: nothing matched ${selector}`)
}

async function reach(
  cursor: Cursor,
  selector: string,
  travelMs: number,
): Promise<HTMLElement> {
  const element = await find(selector)
  const box = element.getBoundingClientRect()
  await cursor.moveTo(box.left + box.width / 2, box.top + box.height / 2, travelMs)
  return element
}

async function click(cursor: Cursor, beat: Beat & { kind: 'click' }): Promise<void> {
  const element = await reach(cursor, beat.target, beat.dur - PRESS_MS)
  // Not a synthetic MouseEvent: `.click()` is what the button's own handler
  // would receive from a real pointer, and it bubbles out of the label spans
  // an allocation row is made of.
  element.click()
  await cursor.press()
}

async function type(cursor: Cursor, beat: Beat & { kind: 'type' }): Promise<void> {
  const field = (await reach(cursor, beat.target, REACH_MS)) as HTMLInputElement
  field.focus()

  // React installs its own value setter on the element, so assigning `.value`
  // updates the DOM behind React's back and the next render wipes it. The
  // prototype's setter plus an `input` event is the path React listens on.
  const setValue = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    'value',
  )?.set
  const perCharacter = (beat.dur - REACH_MS) / beat.text.length

  for (const [index] of [...beat.text].entries()) {
    setValue?.call(field, beat.text.slice(0, index + 1))
    field.dispatchEvent(new Event('input', { bubbles: true }))
    await sleep(perCharacter)
  }
}

async function play(cursor: Cursor, beat: Beat): Promise<void> {
  switch (beat.kind) {
    case 'click':
      return click(cursor, beat)
    case 'type':
      return type(cursor, beat)
    case 'warp':
      return warp(beat.seconds, beat.dur)
    case 'hold':
      return sleep(beat.dur)
  }
}

/** Resolves when the last frame worth recording has been on screen. */
export async function runDemo(): Promise<void> {
  const cursor = createCursor()
  await sleep(PREROLL_MS)
  const start = performance.now()

  for (const beat of BEATS) {
    await sleep(beat.at - (performance.now() - start))
    await play(cursor, beat)
  }

  await sleep(DEMO_MS - (performance.now() - start))
  // The recorder waits on this rather than on a fixed duration, so a slow
  // frame lengthens the recording instead of truncating the last beat.
  document.documentElement.dataset.demoDone = 'true'
}
