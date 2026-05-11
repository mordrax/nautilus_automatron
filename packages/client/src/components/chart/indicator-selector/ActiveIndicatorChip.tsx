import { useState } from 'react'
import { X } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { INDICATOR_COLORS } from '@/lib/chart-config'

type ColorPickerProps = {
  readonly color: string
  readonly onChange: (color: string) => void
}

const ColorPicker = ({ color, onChange }: ColorPickerProps) => {
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
            type="button"
            aria-label={`Use color ${c}`}
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

type ActiveIndicatorChipProps = {
  readonly id: string
  readonly label: string
  readonly color: string
  readonly onColorChange: (id: string, color: string) => void
  readonly onRemove: (id: string) => void
}

export const ActiveIndicatorChip = ({
  id,
  label,
  color,
  onColorChange,
  onRemove,
}: ActiveIndicatorChipProps) => (
  <div className="inline-flex items-center gap-1.5 pl-1 pr-1.5 py-0.5 rounded-md border border-border bg-background text-xs">
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Change color for ${label}`}
          className="w-3 h-3 rounded-sm border border-border cursor-pointer shrink-0 hover:scale-110 transition-transform"
          style={{ backgroundColor: color }}
          title="Change color"
        />
      </PopoverTrigger>
      <PopoverContent className="w-auto p-2" side="bottom" align="start">
        <ColorPicker color={color} onChange={c => onColorChange(id, c)} />
      </PopoverContent>
    </Popover>
    <span className="whitespace-nowrap">{label}</span>
    <button
      type="button"
      aria-label={`Disable ${label}`}
      onClick={() => onRemove(id)}
      className="ml-0.5 rounded-sm hover:bg-muted p-0.5 cursor-pointer"
    >
      <X className="w-3 h-3" />
    </button>
  </div>
)
