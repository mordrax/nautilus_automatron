import { useDetectors } from '@/hooks/use-key-levels'

type KeyLevelsPanelProps = {
  readonly selectedDetectors: readonly string[]
  readonly onChange: (next: readonly string[]) => void
}

export const KeyLevelsPanel = ({ selectedDetectors, onChange }: KeyLevelsPanelProps) => {
  const { data: detectors } = useDetectors()

  const toggle = (id: string) => {
    const has = selectedDetectors.includes(id)
    const next = has
      ? selectedDetectors.filter((d) => d !== id)
      : [...selectedDetectors, id]
    onChange(next)
  }

  if (!detectors || detectors.length === 0) {
    return (
      <div className="space-y-2 text-sm">
        <h4 className="font-semibold text-muted-foreground">Key Levels</h4>
        <p className="text-xs text-muted-foreground">No detectors available</p>
      </div>
    )
  }

  return (
    <div className="space-y-2 text-sm" data-testid="key-levels-panel">
      <h4 className="font-semibold text-muted-foreground">Key Levels</h4>
      <div className="space-y-1">
        {detectors.map((det) => (
          <div key={det.id} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="w-4 h-4 rounded-sm border border-border shrink-0"
              style={{ backgroundColor: det.color }}
              title={det.color}
            />
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedDetectors.includes(det.id)}
                onChange={() => toggle(det.id)}
                className="rounded"
                data-testid={`key-level-toggle-${det.id}`}
              />
              <span>{det.label}</span>
            </label>
          </div>
        ))}
      </div>
    </div>
  )
}
