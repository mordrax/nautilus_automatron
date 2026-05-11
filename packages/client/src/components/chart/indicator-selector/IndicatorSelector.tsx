import type { IndicatorMeta } from '@/types/api'
import { ActiveIndicatorChip } from './ActiveIndicatorChip'
import { AddIndicatorMenu } from './AddIndicatorMenu'

type IndicatorSelectorProps = {
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onToggle: (id: string) => void
  readonly getColor: (id: string) => string
  readonly onColorChange: (id: string, color: string) => void
}

export const IndicatorSelector = ({
  indicators,
  enabledIds,
  onToggle,
  getColor,
  onColorChange,
}: IndicatorSelectorProps) => {
  const indicatorById = new Map(indicators.map(i => [i.id, i]))
  const enabled = [...enabledIds]
    .map(id => indicatorById.get(id))
    .filter((i): i is IndicatorMeta => i !== undefined)

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="indicator-selector">
      {enabled.map(ind => (
        <ActiveIndicatorChip
          key={ind.id}
          id={ind.id}
          label={ind.label}
          color={getColor(ind.id)}
          onColorChange={onColorChange}
          onRemove={onToggle}
        />
      ))}
      <AddIndicatorMenu
        indicators={indicators}
        enabledIds={enabledIds}
        onAdd={onToggle}
      />
    </div>
  )
}
