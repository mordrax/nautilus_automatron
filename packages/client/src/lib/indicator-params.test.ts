import { describe, expect, it } from 'vitest'
import {
  defaultParams,
  coerceParams,
  validateParams,
  formatLabel,
} from './indicator-params'
import type { ParamSchema, IndicatorType } from '@/types/api'

const smaSchema: readonly ParamSchema[] = [
  { name: 'period', type: 'int', default: 20, min: 2, max: 500 },
]

const zigzagSchema: readonly ParamSchema[] = [
  { name: 'threshold', type: 'float', default: 0.05, min: 0.001, max: 0.5, step: 0.001 },
]

const macdSchema: readonly ParamSchema[] = [
  { name: 'fast_period', type: 'int', default: 12, min: 2, max: 200 },
  { name: 'slow_period', type: 'int', default: 26, min: 2, max: 200 },
  { name: 'signal_period', type: 'int', default: 9, min: 2, max: 200 },
]

const smaType: IndicatorType = {
  type: 'SMA',
  labelTemplate: 'SMA({period})',
  display: 'overlay',
  outputs: ['value'],
  params: smaSchema,
}

const macdType: IndicatorType = {
  type: 'MACD',
  labelTemplate: 'MACD({fast_period},{slow_period},{signal_period})',
  display: 'panel',
  outputs: ['macd', 'signal', 'histogram'],
  params: macdSchema,
}

describe('defaultParams', () => {
  it('populates every schema field with its default', () => {
    expect(defaultParams(smaSchema)).toEqual({ period: 20 })
  })

  it('handles multiple params', () => {
    expect(defaultParams(macdSchema)).toEqual({
      fast_period: 12,
      slow_period: 26,
      signal_period: 9,
    })
  })

  it('handles float schema', () => {
    expect(defaultParams(zigzagSchema)).toEqual({ threshold: 0.05 })
  })

  it('returns empty object for empty schema', () => {
    expect(defaultParams([])).toEqual({})
  })
})

describe('coerceParams', () => {
  it('coerces int string to integer', () => {
    const result = coerceParams(smaSchema, { period: '20' })
    expect(result.period).toBe(20)
    expect(Number.isInteger(result.period)).toBe(true)
  })

  it('coerces float string to float', () => {
    const result = coerceParams(zigzagSchema, { threshold: '0.05' })
    expect(result.threshold).toBeCloseTo(0.05)
  })

  it('produces NaN for empty string on int', () => {
    const result = coerceParams(smaSchema, { period: '' })
    expect(Number.isNaN(result.period)).toBe(true)
  })

  it('produces NaN for non-numeric string', () => {
    const result = coerceParams(smaSchema, { period: 'abc' })
    expect(Number.isNaN(result.period)).toBe(true)
  })

  it('truncates float to int for int type', () => {
    const result = coerceParams(smaSchema, { period: '20' })
    expect(result.period).toBe(20)
  })
})

describe('validateParams', () => {
  it('returns ok for valid params', () => {
    const result = validateParams(smaSchema, { period: 20 })
    expect(result.ok).toBe(true)
  })

  it('returns ok for boundary min value', () => {
    const result = validateParams(smaSchema, { period: 2 })
    expect(result.ok).toBe(true)
  })

  it('returns ok for boundary max value', () => {
    const result = validateParams(smaSchema, { period: 500 })
    expect(result.ok).toBe(true)
  })

  it('errors when value is below min', () => {
    const result = validateParams(smaSchema, { period: 1 })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.period).toContain('at least 2')
    }
  })

  it('errors when value exceeds max', () => {
    const result = validateParams(smaSchema, { period: 501 })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.period).toContain('at most 500')
    }
  })

  it('errors for NaN', () => {
    const result = validateParams(smaSchema, { period: NaN })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.period).toContain('valid number')
    }
  })

  it('errors for non-integer on int type', () => {
    const result = validateParams(smaSchema, { period: 20.5 })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.period).toContain('integer')
    }
  })

  it('errors for missing key', () => {
    const result = validateParams(smaSchema, {})
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.period).toContain('required')
    }
  })

  it('accepts float value for float type', () => {
    const result = validateParams(zigzagSchema, { threshold: 0.1 })
    expect(result.ok).toBe(true)
  })

  it('reports multiple errors', () => {
    const result = validateParams(macdSchema, { fast_period: NaN, slow_period: 26, signal_period: 300 })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.fast_period).toBeDefined()
      expect(result.errors.signal_period).toBeDefined()
      expect(result.errors.slow_period).toBeUndefined()
    }
  })
})

describe('formatLabel', () => {
  it('substitutes a single placeholder', () => {
    expect(formatLabel(smaType, { period: 20 })).toBe('SMA(20)')
  })

  it('substitutes multiple placeholders', () => {
    expect(formatLabel(macdType, { fast_period: 12, slow_period: 26, signal_period: 9 })).toBe(
      'MACD(12,26,9)'
    )
  })

  it('leaves unmatched placeholders as-is', () => {
    expect(formatLabel(smaType, {})).toBe('SMA({period})')
  })

  it('handles custom period values', () => {
    expect(formatLabel(smaType, { period: 50 })).toBe('SMA(50)')
  })
})
