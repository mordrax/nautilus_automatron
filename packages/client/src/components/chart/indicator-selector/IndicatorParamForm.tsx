import { useState, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { IndicatorType } from '@/types/api'
import {
  coerceParams,
  defaultParams,
  validateParams,
} from '@/lib/indicator-params'

type IndicatorParamFormProps = {
  readonly type: IndicatorType
  readonly initialParams?: Record<string, number>
  readonly submitLabel: string
  readonly onSubmit: (params: Record<string, number>) => void
  readonly onCancel: () => void
}

export const IndicatorParamForm = ({
  type,
  initialParams,
  submitLabel,
  onSubmit,
  onCancel,
}: IndicatorParamFormProps) => {
  const buildSeed = (t: typeof type, ip: typeof initialParams) => {
    const base = ip ?? defaultParams(t.params)
    return Object.fromEntries(t.params.map(s => [s.name, String(base[s.name] ?? s.default)]))
  }

  const [lastTypeKey, setLastTypeKey] = useState(type.type)
  const [rawValues, setRawValues] = useState<Record<string, string>>(() => buildSeed(type, initialParams))

  // Re-seed when type changes (during render, not in an effect)
  if (type.type !== lastTypeKey) {
    setLastTypeKey(type.type)
    setRawValues(buildSeed(type, initialParams))
  }

  const validation = useMemo(() => {
    const coerced = coerceParams(type.params, rawValues)
    return validateParams(type.params, coerced)
  }, [type.params, rawValues])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const coerced = coerceParams(type.params, rawValues)
    const result = validateParams(type.params, coerced)
    if (!result.ok) return
    onSubmit(coerced)
  }

  const errors = !validation.ok ? validation.errors : {}

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <p className="text-sm font-semibold">{type.type}</p>
      {type.params.map(param => {
        const fieldLabel = param.label ?? param.name
        const error = errors[param.name]
        return (
          <div key={param.name} className="space-y-1">
            <Label htmlFor={`param-${param.name}`} className="text-xs">
              {fieldLabel}
            </Label>
            <Input
              id={`param-${param.name}`}
              data-testid={`param-input-${param.name}`}
              type="number"
              value={rawValues[param.name] ?? ''}
              min={param.min}
              max={param.max}
              step={param.step ?? (param.type === 'int' ? 1 : 'any')}
              onChange={e =>
                setRawValues(prev => ({ ...prev, [param.name]: e.target.value }))
              }
              className="h-7 text-xs"
              aria-invalid={!!error}
            />
            {error && (
              <p className="text-xs text-destructive" role="alert">
                {error}
              </p>
            )}
          </div>
        )
      })}
      <div className="flex gap-2 pt-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCancel}
          className="flex-1"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          disabled={!validation.ok}
          data-testid="param-form-submit"
          className="flex-1"
        >
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
