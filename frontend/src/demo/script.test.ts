import { describe, expect, it } from 'vitest'
import { BEATS, DEMO_MS } from './script'

describe('the demo beat sheet', () => {
  it('runs in order, without a beat overlapping the next', () => {
    for (const [index, beat] of BEATS.slice(0, -1).entries()) {
      const next = BEATS[index + 1]
      expect(
        beat.at + beat.dur,
        `beat ${index} (${beat.kind}) runs into the next one`,
      ).toBeLessThanOrEqual(next.at)
    }
  })

  it('fits the budget the README recording is allowed', () => {
    const last = BEATS[BEATS.length - 1]
    expect(last.at + last.dur).toBeLessThanOrEqual(DEMO_MS)
  })

  it('leaves every beat long enough to be seen', () => {
    for (const beat of BEATS) expect(beat.dur).toBeGreaterThanOrEqual(400)
  })

  it('aims every click and every keystroke at a selector', () => {
    for (const beat of BEATS) {
      if (beat.kind === 'click' || beat.kind === 'type') {
        expect(beat.target).not.toBe('')
      }
    }
  })
})
