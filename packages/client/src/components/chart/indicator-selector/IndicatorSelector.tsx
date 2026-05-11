import { useMemo } from 'react'
import type { IndicatorMeta } from '@/types/api'
import type { DetectorMeta } from '@/types/key-levels'
import { ActiveIndicatorChip } from './ActiveIndicatorChip'
import { AddIndicatorMenu } from './AddIndicatorMenu'
import type { MenuItem } from './AddIndicatorMenu'

type IndicatorSelectorProps = {
  // Indicators
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onToggle: (id: string) => void
  readonly getColor: (id: string) => string
  readonly onColorChange: (id: string, color: string) => void
  // Key-level detectors
  readonly detectors: readonly DetectorMeta[]
  readonly selectedDetectorIds: readonly string[]
  readonly onToggleDetector: (id: string) => void
}

export const IndicatorSelector = ({
  indicators,
  enabledIds,
  onToggle,
  getColor,
  onColorChange,
  detectors,
  selectedDetectorIds,
  onToggleDetector,
}: IndicatorSelectorProps) => {
  const indicatorById = new Map(indicators.map(i => [i.id, i]))
  const detectorById = new Map(detectors.map(d => [d.id, d]))

  const enabledIndicators = [...enabledIds]
    .map(id => indicatorById.get(id))
    .filter((i): i is IndicatorMeta => i !== undefined)

  const enabledDetectors = selectedDetectorIds
    .map(id => detectorById.get(id))
    .filter((d): d is DetectorMeta => d !== undefined)

  const menuItems: readonly MenuItem[] = useMemo(() => [
    ...indicators.map(i => ({
      id: i.id,
      label: i.label,
      group: i.display as 'overlay' | 'panel',
    })),
    ...detectors.map(d => ({
      id: d.id,
      label: d.label,
      group: 'key-level' as const,
    })),
  ], [indicators, detectors])

  const selectedDetectorSet = useMemo(
    () => new Set(selectedDetectorIds),
    [selectedDetectorIds],
  )

  const handleAdd = (item: MenuItem) => {
    if (item.group === 'key-level') {
      onToggleDetector(item.id)
    } else {
      onToggle(item.id)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="indicator-selector">
      {enabledIndicators.map(ind => (
        <ActiveIndicatorChip
          key={ind.id}
          id={ind.id}
          label={ind.label}
          color={getColor(ind.id)}
          onColorChange={onColorChange}
          onRemove={onToggle}
        />
      ))}
      {enabledDetectors.map(det => (
        <ActiveIndicatorChip
          key={det.id}
          id={det.id}
          label={det.label}
          color={det.color}
          onRemove={onToggleDetector}
        />
      ))}
      <AddIndicatorMenu
        items={menuItems}
        enabledKey={item =>
          item.group === 'key-level'
            ? selectedDetectorSet.has(item.id)
            : enabledIds.has(item.id)
        }
        onAdd={handleAdd}
      />
    </div>
  )
}
