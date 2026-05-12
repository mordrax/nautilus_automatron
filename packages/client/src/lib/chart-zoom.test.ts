import { describe, expect, it } from 'vitest'
import { computeDefaultStart } from './chart-zoom'

describe('computeDefaultStart', () => {
  it('returns 0 when the dataset is empty', () => {
    expect(computeDefaultStart(0)).toBe(0)
  })

  it('returns 0 when the dataset is smaller than the default window', () => {
    expect(computeDefaultStart(30)).toBe(0)
  })

  it('returns 0 when the dataset is exactly the default window', () => {
    expect(computeDefaultStart(50)).toBe(0)
  })

  it('returns a small positive percentage when one bar past the default', () => {
    expect(computeDefaultStart(51)).toBeCloseTo((1 / 51) * 100, 10)
  })

  it('returns 95 for 1000 bars with the 50-bar default', () => {
    expect(computeDefaultStart(1000)).toBe(95)
  })

  it('respects a custom visible-window override', () => {
    expect(computeDefaultStart(1000, 100)).toBe(90)
  })
})
