import type { ParamSchema, IndicatorType } from '@/types/api'

export const defaultParams = (schema: readonly ParamSchema[]): Record<string, number> =>
  Object.fromEntries(schema.map((s) => [s.name, s.default]))

export const coerceParams = (
  schema: readonly ParamSchema[],
  raw: Record<string, string>,
): Record<string, number> =>
  Object.fromEntries(
    schema.map((s) => [
      s.name,
      s.type === 'int'
        ? Number.parseInt(raw[s.name] ?? '', 10)
        : Number.parseFloat(raw[s.name] ?? ''),
    ])
  )

export type ValidationResult = { ok: true } | { ok: false; errors: Record<string, string> }

export const validateParams = (
  schema: readonly ParamSchema[],
  params: Record<string, number>,
): ValidationResult => {
  const errors: Record<string, string> = {}

  for (const s of schema) {
    const value = params[s.name]

    if (value === undefined) {
      errors[s.name] = `${s.name} is required`
      continue
    }

    if (Number.isNaN(value)) {
      errors[s.name] = `${s.name} must be a valid number`
      continue
    }

    if (s.type === 'int' && !Number.isInteger(value)) {
      errors[s.name] = `${s.name} must be an integer`
      continue
    }

    if (s.min !== undefined && value < s.min) {
      errors[s.name] = `${s.name} must be at least ${s.min}`
      continue
    }

    if (s.max !== undefined && value > s.max) {
      errors[s.name] = `${s.name} must be at most ${s.max}`
      continue
    }
  }

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors }
  }
  return { ok: true }
}

/**
 * Mirror backend format_label: replace {paramName} placeholders with param values.
 */
export const formatLabel = (
  type: IndicatorType,
  params: Record<string, number>,
): string =>
  type.labelTemplate.replace(/\{(\w+)\}/g, (_, key) => {
    const val = params[key]
    return val !== undefined ? String(val) : `{${key}}`
  })
