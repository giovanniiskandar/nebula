/**
 * The beat sheet for the recording: what happens, and exactly when.
 *
 * `at` is milliseconds from the first frame and `dur` is how long the beat
 * occupies, press animation included -- beats must not overlap, or each one
 * pushes the next late and the recording overruns. `script.test.ts` holds that
 * line, and the fifteen-second budget with it.
 *
 * Four allocations, not two: a row is 98px in a 358px list, so three fill the
 * card and the fourth leaves the day looking busy rather than the widget
 * looking empty. `record-demo.mjs` reads DEMO_MS off the page, so changing the
 * budget here changes what is encoded.
 *
 * A click's `dur` is its cursor travel plus the press; the button actually
 * fires when the travel ends, which is `dur` minus `PRESS_MS`.
 */

export type Beat =
  | { at: number; dur: number; kind: 'hold' }
  | { at: number; dur: number; kind: 'click'; target: string }
  | { at: number; dur: number; kind: 'type'; target: string; text: string }
  /** Let `seconds` of tracked time pass; see `clock.ts`. */
  | { at: number; dur: number; kind: 'warp'; seconds: number }

export const DEMO_MS = 15_000

const HOUR = 3600

export const BEATS: Beat[] = [
  // An empty day: "Plan your day".
  { at: 0, dur: 600, kind: 'hold' },

  // The first allocation, from the empty state's own button.
  { at: 660, dur: 500, kind: 'click', target: '[data-empty-add]' },
  { at: 1220, dur: 540, kind: 'type', target: '[data-form-name]', text: 'Working' },
  { at: 1820, dur: 440, kind: 'click', target: '[data-preset="2h"]' },
  { at: 2320, dur: 440, kind: 'click', target: '[data-form-save]' },

  // The rest the way you would add them later: through Settings, which stays
  // open between saves.
  { at: 2820, dur: 500, kind: 'click', target: '[data-gear]' },

  { at: 3380, dur: 440, kind: 'click', target: '[data-add]' },
  { at: 3880, dur: 560, kind: 'type', target: '[data-form-name]', text: 'Learning' },
  { at: 4500, dur: 440, kind: 'click', target: '[data-preset="1h"]' },
  { at: 5000, dur: 440, kind: 'click', target: '[data-form-save]' },

  { at: 5500, dur: 440, kind: 'click', target: '[data-add]' },
  { at: 6000, dur: 560, kind: 'type', target: '[data-form-name]', text: 'Exercise' },
  { at: 6620, dur: 440, kind: 'click', target: '[data-preset="30m"]' },
  { at: 7120, dur: 440, kind: 'click', target: '[data-form-save]' },

  { at: 7620, dur: 440, kind: 'click', target: '[data-add]' },
  { at: 8120, dur: 540, kind: 'type', target: '[data-form-name]', text: 'Reading' },
  { at: 8720, dur: 440, kind: 'click', target: '[data-preset="1h"]' },
  { at: 9220, dur: 440, kind: 'click', target: '[data-form-save]' },

  { at: 9720, dur: 440, kind: 'click', target: '[data-settings-close]' },

  // Start tracking the first allocation, then let an hour of it pass.
  { at: 10_220, dur: 440, kind: 'click', target: '[data-allocation-name]' },
  { at: 10_720, dur: 1200, kind: 'warp', seconds: HOUR },

  // Break pauses the day; toggling it off resumes the same allocation.
  { at: 11_980, dur: 440, kind: 'click', target: '[data-break]' },
  { at: 12_480, dur: 700, kind: 'warp', seconds: 120 },
  { at: 13_240, dur: 420, kind: 'click', target: '[data-break]' },

  // End the day and hold on the recap.
  { at: 13_720, dur: 440, kind: 'click', target: '[data-complete]' },
  { at: 14_220, dur: 780, kind: 'hold' },
]
