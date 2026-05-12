import { useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { IndicatorInstance, IndicatorType } from '@/types/api'
import { IndicatorChip } from './IndicatorChip'
import { AddIndicatorPopover } from './AddIndicatorPopover'
import { IndicatorParamForm } from './IndicatorParamForm'

type EditState = {
  readonly instanceId: string
  readonly type: IndicatorType
}

type IndicatorInstanceSelectorProps = {
  readonly types: readonly IndicatorType[]
  readonly instances: readonly IndicatorInstance[]
  readonly getColor: (id: string) => string
  readonly onSetColor: (id: string, color: string) => void
  readonly onAdd: (type: string, params: Record<string, number>) => void
  readonly onEdit: (id: string, params: Record<string, number>) => void
  readonly onRemove: (id: string) => void
}

export const IndicatorInstanceSelector = ({
  types,
  instances,
  getColor,
  onSetColor,
  onAdd,
  onEdit,
  onRemove,
}: IndicatorInstanceSelectorProps) => {
  const [editState, setEditState] = useState<EditState | null>(null)

  const handleAdd = (type: IndicatorType, params: Record<string, number>) => {
    onAdd(type.type, params)
  }

  const handleEditOpen = (instance: IndicatorInstance) => {
    const type = types.find(t => t.type === instance.type)
    if (!type) {
      console.warn(`IndicatorInstanceSelector: unknown indicator type "${instance.type}"`)
      return
    }
    setEditState({ instanceId: instance.id, type })
  }

  const handleEditSubmit = (params: Record<string, number>) => {
    if (!editState) return
    onEdit(editState.instanceId, params)
    setEditState(null)
  }

  const handleEditCancel = () => {
    setEditState(null)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="indicator-instance-selector">
      {instances.map(instance => {
        const type = types.find(t => t.type === instance.type)
        if (!type) {
          console.warn(`IndicatorInstanceSelector: skipping instance with unknown type "${instance.type}"`)
          return null
        }
        const isEditing = editState?.instanceId === instance.id
        return (
          <Popover
            key={instance.id}
            open={isEditing}
            onOpenChange={open => {
              if (!open) setEditState(null)
            }}
          >
            <PopoverTrigger asChild>
              <span>
                <IndicatorChip
                  instance={instance}
                  type={type}
                  color={getColor(instance.id)}
                  onEdit={() => handleEditOpen(instance)}
                  onRemove={() => onRemove(instance.id)}
                  onColorChange={color => onSetColor(instance.id, color)}
                />
              </span>
            </PopoverTrigger>
            <PopoverContent className="w-56 p-3" side="bottom" align="start">
              <IndicatorParamForm
                type={type}
                initialParams={{ ...instance.params }}
                submitLabel="Save"
                onSubmit={handleEditSubmit}
                onCancel={handleEditCancel}
              />
            </PopoverContent>
          </Popover>
        )
      })}
      <AddIndicatorPopover
        types={types}
        onSubmit={handleAdd}
      />
    </div>
  )
}
