import { describe, expect, it } from 'vitest'
import { newInstanceId } from './uuid'

describe('newInstanceId', () => {
  it('returns a non-empty string', () => {
    const id = newInstanceId()
    expect(typeof id).toBe('string')
    expect(id.length).toBeGreaterThan(0)
  })

  it('generates distinct IDs', () => {
    const ids = new Set(Array.from({ length: 100 }, () => newInstanceId()))
    expect(ids.size).toBe(100)
  })

  it('UUID-ish format (crypto.randomUUID available in Node 19+)', () => {
    const id = newInstanceId()
    // Either a standard UUID or our fallback format — both have at least one '-'
    expect(id).toContain('-')
  })
})
