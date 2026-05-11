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

export type MenuItemGroup = 'overlay' | 'panel' | 'key-level'

export type MenuItem = {
  readonly id: string
  readonly label: string
  readonly group: MenuItemGroup
}

const GROUP_ORDER: readonly MenuItemGroup[] = ['overlay', 'panel', 'key-level']
const GROUP_LABELS: Record<MenuItemGroup, string> = {
  overlay: 'Overlays',
  panel: 'Panels',
  'key-level': 'Key Levels',
}

type AddIndicatorMenuProps = {
  readonly items: readonly MenuItem[]
  readonly enabledKey: (item: MenuItem) => boolean
  readonly onAdd: (item: MenuItem) => void
}

export const AddIndicatorMenu = ({
  items,
  enabledKey,
  onAdd,
}: AddIndicatorMenuProps) => {
  const [open, setOpen] = useState(false)

  const groups = useMemo(() => {
    const buckets = Object.fromEntries(
      GROUP_ORDER.map(g => [g, [] as MenuItem[]]),
    ) as Record<MenuItemGroup, MenuItem[]>
    for (const item of items) {
      if (enabledKey(item)) continue
      buckets[item.group].push(item)
    }
    return GROUP_ORDER
      .map(group => ({ group, label: GROUP_LABELS[group], items: buckets[group] }))
      .filter(g => g.items.length > 0)
  }, [items, enabledKey])

  const handleSelect = (item: MenuItem) => {
    onAdd(item)
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
              <CommandGroup key={group.group} heading={group.label}>
                {group.items.map(item => (
                  <CommandItem
                    key={item.id}
                    value={item.label}
                    onSelect={() => handleSelect(item)}
                  >
                    {item.label}
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
