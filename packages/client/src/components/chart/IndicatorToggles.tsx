import { useState } from 'react'
import type { IndicatorMeta } from '@/types/api'
import { INDICATOR_COLORS } from '@/lib/chart-config'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

type IndicatorTogglesProps = {
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onToggle: (id: string) => void
  readonly getColor: (id: string) => string
  readonly onColorChange: (id: string, color: string) => void
}

const ColorPicker = ({
  color,
  onChange,
}: {
  readonly color: string
  readonly onChange: (color: string) => void
}) => {
  const [hex, setHex] = useState(color)

  const handleHexChange = (value: string) => {
    setHex(value)
    if (/^#[0-9A-Fa-f]{6}$/.test(value)) {
      onChange(value)
    }
  }

  return (
    <div className="space-y-2 p-1">
      <div className="flex flex-wrap gap-1">
        {INDICATOR_COLORS.map(c => (
          <button
            key={c}
            className="w-5 h-5 rounded-sm border border-border cursor-pointer hover:scale-110 transition-transform"
            style={{ backgroundColor: c }}
            onClick={() => { onChange(c); setHex(c) }}
            title={c}
          />
        ))}
      </div>
      <input
        type="text"
        value={hex}
        onChange={e => handleHexChange(e.target.value)}
        placeholder="#FF6B6B"
        className="w-full px-2 py-1 text-xs border rounded bg-background font-mono"
      />
    </div>
  )
}

export const IndicatorToggles = ({
  indicators,
  enabledIds,
  onToggle,
  getColor,
  onColorChange,
}: IndicatorTogglesProps) => {
  const overlays = indicators.filter(i => i.display === 'overlay')
  const panels = indicators.filter(i => i.display === 'panel')

  const renderGroup = (label: string, items: readonly IndicatorMeta[]) =>
    items.length > 0 && (
      <div>
        <h4 className="font-semibold mb-2 text-muted-foreground">{label}</h4>
        <div className="space-y-1">
          {items.map(ind => (
            <div key={ind.id} className="flex items-center gap-2">
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    className="w-4 h-4 rounded-sm border border-border cursor-pointer shrink-0 hover:scale-110 transition-transform"
                    style={{ backgroundColor: getColor(ind.id) }}
                    title="Change color"
                  />
                </PopoverTrigger>
                <PopoverContent className="w-auto p-2" side="left" align="start">
                  <ColorPicker
                    color={getColor(ind.id)}
                    onChange={color => onColorChange(ind.id, color)}
                  />
                </PopoverContent>
              </Popover>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enabledIds.has(ind.id)}
                  onChange={() => onToggle(ind.id)}
                  className="rounded"
                />
                <span>{ind.label}</span>
              </label>
            </div>
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
