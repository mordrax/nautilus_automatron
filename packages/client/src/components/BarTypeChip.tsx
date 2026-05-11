import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { CatalogTooltipContent } from '@/components/CatalogTooltipContent'
import type { CatalogEntry } from '@/types/api'

type Props = {
  readonly barType: string
  readonly entry: CatalogEntry | undefined
}

export const BarTypeChip = ({ barType, entry }: Props) => {
  const [pinned, setPinned] = useState(false)
  const [hovered, setHovered] = useState(false)
  const open = pinned || hovered

  return (
    <Tooltip open={open} onOpenChange={setHovered}>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          className="cursor-pointer select-none"
          onClick={() => setPinned((p) => !p)}
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
          setPinned(false)
        }}
      >
        <CatalogTooltipContent barType={barType} entry={entry} />
      </TooltipContent>
    </Tooltip>
  )
}
