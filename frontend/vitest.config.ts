import { defineConfig } from 'vitest/config'

// No jsdom: the tested units are pure functions over numbers and strings.
// Components are covered by the GUI test, which drives the real app.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
