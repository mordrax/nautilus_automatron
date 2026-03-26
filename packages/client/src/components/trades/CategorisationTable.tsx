import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { TradeCategory } from '@/types/api'

type CategorisationTableProps = {
  readonly categories: readonly TradeCategory[]
  readonly onUpdateDescription: (categoryId: number, description: string) => void
}

const EditableDescription = ({
  category,
  onUpdateDescription,
}: {
  readonly category: TradeCategory
  readonly onUpdateDescription: (categoryId: number, description: string) => void
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [draft, setDraft] = useState(category.description)
  const [isOverflowing, setIsOverflowing] = useState(false)
  const spanRef = useRef<HTMLSpanElement>(null)

  const checkOverflow = useCallback(() => {
    if (spanRef.current) {
      setIsOverflowing(spanRef.current.scrollWidth > spanRef.current.clientWidth)
    }
  }, [])

  useEffect(() => {
    checkOverflow()
  }, [category.description, checkOverflow])

  const commit = () => {
    setIsEditing(false)
    if (draft.trim() !== category.description) {
      onUpdateDescription(category.id, draft.trim())
    }
  }

  if (isEditing) {
    return (
      <input
        className="w-full bg-transparent border-b border-border outline-none text-sm px-0 py-0.5"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => {
          if (e.key === 'Enter') commit()
          if (e.key === 'Escape') {
            setDraft(category.description)
            setIsEditing(false)
          }
        }}
        autoFocus
      />
    )
  }

  const descriptionSpan = (
    <span
      ref={spanRef}
      className="block truncate max-w-[300px] cursor-pointer hover:text-foreground/80"
      onDoubleClick={() => {
        setDraft(category.description)
        setIsEditing(true)
      }}
    >
      {category.description}
    </span>
  )

  if (!isOverflowing) return descriptionSpan

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          {descriptionSpan}
        </TooltipTrigger>
        <TooltipContent>
          <p>{category.description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export const CategorisationTable = ({
  categories,
  onUpdateDescription,
}: CategorisationTableProps) => (
  <Table data-testid="categorisation-table">
    <TableHeader>
      <TableRow>
        <TableHead className="w-12">Key</TableHead>
        <TableHead>Description</TableHead>
        <TableHead className="w-20 text-right">Count</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {categories.map(cat => (
        <TableRow key={cat.id} data-testid={`category-row-${cat.id}`}>
          <TableCell className="font-mono font-semibold">{cat.id}</TableCell>
          <TableCell>
            <EditableDescription
              category={cat}
              onUpdateDescription={onUpdateDescription}
            />
          </TableCell>
          <TableCell className="text-right font-mono" data-testid={`category-count-${cat.id}`}>
            {cat.tradeIds.size}
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
)
