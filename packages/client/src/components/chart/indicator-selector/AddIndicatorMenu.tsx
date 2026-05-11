import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { IndicatorMeta } from '@/types/api'

const GROUP_ORDER: readonly IndicatorMeta['display'][] = ['overlay', 'panel']
const GROUP_LABELS: Record<IndicatorMeta['display'], string> = {
  overlay: 'Overlays',
  panel: 'Panels',
}

type AddIndicatorMenuProps = {
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onAdd: (id: string) => void
}

export const AddIndicatorMenu = ({
  indicators,
  enabledIds,
  onAdd,
}: AddIndicatorMenuProps) => {
  const [open, setOpen] = useState(false)

  const groups = useMemo(() => {
    const buckets = Object.fromEntries(
      GROUP_ORDER.map(d => [d, [] as IndicatorMeta[]]),
    ) as Record<IndicatorMeta['display'], IndicatorMeta[]>
    for (const ind of indicators) {
      if (enabledIds.has(ind.id)) continue
      buckets[ind.display].push(ind)
    }
    return GROUP_ORDER
      .map(display => ({ display, label: GROUP_LABELS[display], items: buckets[display] }))
      .filter(g => g.items.length > 0)
  }, [indicators, enabledIds])

  const handleSelect = (id: string) => {
    onAdd(id)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          aria-label="Add indicator"
        >
          <Plus className="w-3 h-3 mr-1" />
          Add indicator
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0 w-64" side="bottom" align="start">
        <Command>
          <CommandInput placeholder="Search indicators…" autoFocus />
          <CommandList>
            <CommandEmpty>No indicators found.</CommandEmpty>
            {groups.map(group => (
              <CommandGroup key={group.display} heading={group.label}>
                {group.items.map(ind => (
                  <CommandItem
                    key={ind.id}
                    value={ind.label}
                    onSelect={() => handleSelect(ind.id)}
                  >
                    {ind.label}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
