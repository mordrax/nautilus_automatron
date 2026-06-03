import { useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { IndicatorInstance, IndicatorType } from '@/types/api'
import type { DetectorMeta } from '@/types/key-levels'
import { IndicatorChip } from './IndicatorChip'
import { ActiveIndicatorChip } from './ActiveIndicatorChip'
import { AddIndicatorPopover } from './AddIndicatorPopover'
import { IndicatorParamForm } from './IndicatorParamForm'

type EditState = {
  readonly instanceId: string
  readonly type: IndicatorType
}

type IndicatorInstanceSelectorProps = {
  // indicators
  readonly types: readonly IndicatorType[]
  readonly instances: readonly IndicatorInstance[]
  readonly getColor: (id: string) => string
  readonly onSetColor: (id: string, color: string) => void
  readonly isEnabled: (id: string) => boolean
  readonly onToggle: (id: string) => void
  readonly onAdd: (type: string, params: Record<string, number | string>) => void
  readonly onEdit: (id: string, params: Record<string, number | string>) => void
  readonly onRemove: (id: string) => void
  // detectors
  readonly detectorTypes: readonly DetectorMeta[]
  readonly selectedDetectorIds: readonly string[]
  readonly onAddDetector: (id: string) => void
  readonly onRemoveDetector: (id: string) => void
}

export const IndicatorInstanceSelector = ({
  types,
  instances,
  getColor,
  onSetColor,
  isEnabled,
  onToggle,
  onAdd,
  onEdit,
  onRemove,
  detectorTypes,
  selectedDetectorIds,
  onAddDetector,
  onRemoveDetector,
}: IndicatorInstanceSelectorProps) => {
  const [editState, setEditState] = useState<EditState | null>(null)

  const handleAdd = (type: IndicatorType, params: Record<string, number | string>) => {
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

  const handleEditSubmit = (params: Record<string, number | string>) => {
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
                  enabled={isEnabled(instance.id)}
                  onToggle={() => onToggle(instance.id)}
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
      {selectedDetectorIds.map(detId => {
        const det = detectorTypes.find(d => d.id === detId)
        if (!det) {
          console.warn(`IndicatorInstanceSelector: skipping detector with unknown id "${detId}"`)
          return null
        }
        return (
          <ActiveIndicatorChip
            key={det.id}
            id={det.id}
            label={det.label}
            color={det.color}
            onRemove={onRemoveDetector}
          />
        )
      })}
      <AddIndicatorPopover
        types={types}
        detectorTypes={detectorTypes}
        selectedDetectorIds={selectedDetectorIds}
        onAddIndicator={handleAdd}
        onAddDetector={onAddDetector}
      />
    </div>
  )
}
