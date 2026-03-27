import type { IndicatorMeta } from '@/types/api'

type IndicatorTogglesProps = {
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onToggle: (id: string) => void
}

export const IndicatorToggles = ({ indicators, enabledIds, onToggle }: IndicatorTogglesProps) => {
  const overlays = indicators.filter(i => i.display === 'overlay')
  const panels = indicators.filter(i => i.display === 'panel')

  const renderGroup = (label: string, items: readonly IndicatorMeta[]) =>
    items.length > 0 && (
      <div>
        <h4 className="font-semibold mb-2 text-muted-foreground">{label}</h4>
        <div className="space-y-1">
          {items.map(ind => (
            <label key={ind.id} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabledIds.has(ind.id)}
                onChange={() => onToggle(ind.id)}
                className="rounded"
              />
              <span>{ind.label}</span>
            </label>
          ))}
        </div>
      </div>
    )

  return (
    <div className="space-y-4 text-sm">
      {renderGroup('Overlays', overlays)}
      {renderGroup('Panels', panels)}
    </div>
  )
}
