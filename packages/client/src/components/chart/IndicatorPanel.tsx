import { Switch } from '@/components/ui/switch'
import type { IndicatorMeta } from '@/types/api'

type IndicatorPanelProps = {
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onToggle: (id: string) => void
}

export const IndicatorPanel = ({ indicators, enabledIds, onToggle }: IndicatorPanelProps) => {
  const overlays = indicators.filter(i => i.display === 'overlay')
  const panels = indicators.filter(i => i.display === 'panel')

  return (
    <div className="space-y-4 text-sm">
      {overlays.length > 0 && (
        <div>
          <h4 className="font-semibold mb-2 text-muted-foreground">Overlays</h4>
          <div className="space-y-2">
            {overlays.map(ind => (
              <label key={ind.id} className="flex items-center justify-between gap-2 cursor-pointer">
                <span>{ind.label}</span>
                <Switch
                  checked={enabledIds.has(ind.id)}
                  onCheckedChange={() => onToggle(ind.id)}
                />
              </label>
            ))}
          </div>
        </div>
      )}
      {panels.length > 0 && (
        <div>
          <h4 className="font-semibold mb-2 text-muted-foreground">Panels</h4>
          <div className="space-y-2">
            {panels.map(ind => (
              <label key={ind.id} className="flex items-center justify-between gap-2 cursor-pointer">
                <span>{ind.label}</span>
                <Switch
                  checked={enabledIds.has(ind.id)}
                  onCheckedChange={() => onToggle(ind.id)}
                />
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
