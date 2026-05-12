import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { IndicatorType } from '@/types/api'
import { IndicatorParamForm } from './IndicatorParamForm'

type AddIndicatorPopoverProps = {
  readonly types: readonly IndicatorType[]
  readonly onSubmit: (type: IndicatorType, params: Record<string, number>) => void
}

type Mode = { kind: 'pick' } | { kind: 'form'; type: IndicatorType }

export const AddIndicatorPopover = ({ types, onSubmit }: AddIndicatorPopoverProps) => {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<Mode>({ kind: 'pick' })

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      setMode({ kind: 'pick' })
    }
  }

  const handlePickType = (type: IndicatorType) => {
    setMode({ kind: 'form', type })
  }

  const handleSubmit = (type: IndicatorType, params: Record<string, number>) => {
    onSubmit(type, params)
    setOpen(false)
    setMode({ kind: 'pick' })
  }

  const handleCancel = () => {
    setMode({ kind: 'pick' })
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="xs"
          aria-label="Add indicator"
          className="h-6"
        >
          <Plus className="w-3 h-3" />
          Add
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-2" side="bottom" align="start">
        {mode.kind === 'pick' ? (
          <div className="space-y-1">
            <p className="text-xs font-semibold text-muted-foreground px-1 pb-1">
              Pick indicator
            </p>
            {types.map(type => (
              <button
                key={type.type}
                type="button"
                onClick={() => handlePickType(type)}
                className="w-full text-left text-sm px-2 py-1.5 rounded hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                {type.type}
                <span className="ml-1 text-xs text-muted-foreground">
                  ({type.display})
                </span>
              </button>
            ))}
            {types.length === 0 && (
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
