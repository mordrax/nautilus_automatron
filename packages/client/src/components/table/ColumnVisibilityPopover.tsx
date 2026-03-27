import { Settings } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'

type ColumnInfo = {
  readonly field: string
  readonly title: string
}

type ColumnVisibilityPopoverProps = {
  readonly columns: readonly ColumnInfo[]
  readonly hiddenColumns: ReadonlySet<string>
  readonly onToggle: (field: string) => void
}

export const ColumnVisibilityPopover = ({
  columns,
  hiddenColumns,
  onToggle,
}: ColumnVisibilityPopoverProps) => (
  <Popover>
    <PopoverTrigger asChild>
      <button
        className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        aria-label="Configure columns"
      >
        <Settings className="size-4" />
      </button>
    </PopoverTrigger>
    <PopoverContent className="w-52">
      <div className="space-y-1">
        <p className="text-sm font-medium mb-2">Columns</p>
        {columns.map(({ field, title }) => (
          <label
            key={field}
            className="flex items-center gap-2 text-sm py-0.5 cursor-pointer hover:text-foreground text-muted-foreground has-[:checked]:text-foreground"
          >
            <input
              type="checkbox"
              checked={!hiddenColumns.has(field)}
              onChange={() => onToggle(field)}
              className="accent-primary"
            />
            {title}
          </label>
        ))}
      </div>
    </PopoverContent>
  </Popover>
)
