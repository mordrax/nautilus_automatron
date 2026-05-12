import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { CatalogTooltipContent } from '@/components/CatalogTooltipContent'
import type { CatalogEntry } from '@/types/api'

type Props = {
  readonly barType: string
  readonly entry: CatalogEntry | undefined
  readonly pinned: boolean
  readonly onTogglePin: () => void
  readonly onClearPin: () => void
}

export const BarTypeChip = ({ barType, entry, pinned, onTogglePin, onClearPin }: Props) => {
  const [radixOpen, setRadixOpen] = useState(false)
  const open = pinned || radixOpen

  return (
    <Tooltip open={open} onOpenChange={setRadixOpen}>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          className="cursor-pointer select-none"
          onClick={onTogglePin}
          aria-pressed={pinned}
          data-pinned={pinned || undefined}
          data-bartype={barType}
        >
          {barType}
        </Badge>
      </TooltipTrigger>
      <TooltipContent
        className="max-w-[640px] bg-popover text-popover-foreground border border-border shadow-md"
        side="bottom"
        align="start"
        onPointerDownOutside={(e) => {
          const target = e.detail.originalEvent.target as HTMLElement | null
          if (target?.closest('[data-bartype]')) return
          onClearPin()
        }}
      >
        <CatalogTooltipContent barType={barType} entry={entry} />
      </TooltipContent>
    </Tooltip>
  )
}
