import { describe, expect, it } from 'vitest'
import { formatDayLabel, formatDuration, formatLeft, formatPercent } from './format'

describe('formatDuration', () => {
  it('shows hours and minutes', () => {
    expect(formatDuration(2 * 3600 + 24 * 60)).toBe('2h 24m')
  })

  it('drops the hour part below an hour', () => {
    expect(formatDuration(36 * 60)).toBe('36m')
  })

  it('shows whole hours without minutes', () => {
    expect(formatDuration(3 * 3600)).toBe('3h')
  })

  it('shows zero as 0m', () => {
    expect(formatDuration(0)).toBe('0m')
  })

  it('truncates seconds rather than rounding up', () => {
    expect(formatDuration(59)).toBe('0m')
  })
})

describe('formatLeft', () => {
  it('describes time remaining', () => {
    expect(formatLeft(36 * 60)).toBe('36m left')
  })

  it('describes overage when negative', () => {
    expect(formatLeft(-45 * 60)).toBe('45m over allocation')
  })

  it('treats exactly on target as no time left', () => {
    expect(formatLeft(0)).toBe('0m left')
  })
})

describe('formatPercent', () => {
  it('rounds to a whole number', () => {
    expect(formatPercent(79.6)).toBe('80%')
  })

  it('does not cap above 100', () => {
    expect(formatPercent(125)).toBe('125%')
  })
})

describe('formatDayLabel', () => {
  it('renders the mock format', () => {
    expect(formatDayLabel('2026-08-31')).toBe('MON 31 AUG')
  })
})
