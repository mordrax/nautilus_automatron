import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { IndicatorType } from '@/types/api'
import type { DetectorMeta } from '@/types/key-levels'
import { IndicatorParamForm } from './IndicatorParamForm'

type AddIndicatorPopoverProps = {
  readonly types: readonly IndicatorType[]
  readonly detectorTypes: readonly DetectorMeta[]
  readonly selectedDetectorIds: readonly string[]
  readonly onAddIndicator: (type: IndicatorType, params: Record<string, number>) => void
  readonly onAddDetector: (id: string) => void
}

type Mode = { kind: 'pick' } | { kind: 'form'; type: IndicatorType }

export const AddIndicatorPopover = ({
  types,
  detectorTypes,
  selectedDetectorIds,
  onAddIndicator,
  onAddDetector,
}: AddIndicatorPopoverProps) => {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<Mode>({ kind: 'pick' })

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      setMode({ kind: 'pick' })
    }
  }

  const handlePickIndicatorType = (type: IndicatorType) => {
    if (type.params.length === 0) {
      // Zero-param indicator: add immediately, close popover
      onAddIndicator(type, {})
      setOpen(false)
      setMode({ kind: 'pick' })
    } else {
      setMode({ kind: 'form', type })
    }
  }

  const handleSubmit = (type: IndicatorType, params: Record<string, number>) => {
    onAddIndicator(type, params)
    setOpen(false)
    setMode({ kind: 'pick' })
  }

  const handleCancel = () => {
    setMode({ kind: 'pick' })
  }

  const handlePickDetector = (id: string) => {
    onAddDetector(id)
    setOpen(false)
  }

  const selectedDetectorSet = new Set(selectedDetectorIds)

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="xs"
          aria-label="Add indicator"
          data-testid="add-indicator-button"
          className="h-6"
        >
          <Plus className="w-3 h-3" />
          Add
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-2 max-h-80 overflow-y-auto" side="bottom" align="start">
        {mode.kind === 'pick' ? (
          <div className="space-y-1">
            {types.length > 0 && (
              <>
                <p className="text-xs font-semibold text-muted-foreground px-1 pb-1">
                  Indicators
                </p>
                {types.map(type => (
                  <button
                    key={type.type}
                    type="button"
                    data-testid="indicator-type-option"
                    data-indicator-type={type.type}
                    onClick={() => handlePickIndicatorType(type)}
                    className="w-full text-left text-sm px-2 py-1.5 rounded hover:bg-accent hover:text-accent-foreground transition-colors"
                  >
                    {type.type}
                    <span className="ml-1 text-xs text-muted-foreground">
                      ({type.display})
                    </span>
                  </button>
                ))}
              </>
            )}
            {detectorTypes.length > 0 && (
              <>
                <p className="text-xs font-semibold text-muted-foreground px-1 pb-1 pt-2">
                  Key-level detectors
                </p>
                {detectorTypes.map(det => {
                  const isAdded = selectedDetectorSet.has(det.id)
                  return (
                    <button
                      key={det.id}
                      type="button"
                      data-testid="detector-type-option"
                      data-detector-id={det.id}
                      disabled={isAdded}
                      onClick={() => !isAdded && handlePickDetector(det.id)}
                      className="w-full text-left text-sm px-2 py-1.5 rounded hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span
                        className="inline-block w-2 h-2 rounded-sm mr-1.5 align-middle"
                        style={{ backgroundColor: det.color }}
                      />
                      {det.label}
                      {isAdded && (
                        <span className="ml-1 text-xs text-muted-foreground">(added)</span>
                      )}
                    </button>
                  )
                })}
              </>
            )}
            {types.length === 0 && detectorTypes.length === 0 && (
              <p className="text-xs text-muted-foreground px-2 py-1">
                No indicators available
              </p>
            )}
          </div>
        ) : (
          <IndicatorParamForm
            type={mode.type}
            submitLabel="Add"
            onSubmit={params => handleSubmit(mode.type, params)}
            onCancel={handleCancel}
          />
        )}
      </PopoverContent>
    </Popover>
  )
}
