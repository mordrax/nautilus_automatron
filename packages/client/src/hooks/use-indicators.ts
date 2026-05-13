import { useState, useCallback, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchIndicatorTypes,
  fetchIndicatorData,
  fetchViewerState,
  putViewerState,
} from '@/lib/api'
import { getDefaultIndicatorColor } from '@/lib/chart-config'
import { newInstanceId } from '@/lib/uuid'
import type { IndicatorInstance } from '@/types/api'
import { useDetectors, useKeyLevels } from '@/hooks/use-key-levels'

const COLORS_STORAGE_KEY = 'indicator-colors-v2'

const loadColors = (): Record<string, string> => {
  try {
    const stored = localStorage.getItem(COLORS_STORAGE_KEY)
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

const saveColors = (colors: Record<string, string>) => {
  try {
    localStorage.setItem(COLORS_STORAGE_KEY, JSON.stringify(colors))
  } catch {
    // ignore storage errors
  }
}

const hashInstances = (instances: readonly IndicatorInstance[]): string =>
  JSON.stringify([...instances].sort((a, b) => a.id.localeCompare(b.id)))

export const useIndicators = (runId: string | null, barType: string) => {
  const [instances, setInstances] = useState<IndicatorInstance[]>([])
  const [detectorIds, setDetectorIds] = useState<string[]>([])
  const [colors, setColorsState] = useState<Record<string, string>>(loadColors)
  const [seeded, setSeeded] = useState(false)
  // mutationVersion increments on every user mutation; used to trigger debounced PUT
  const [mutationVersion, setMutationVersion] = useState(0)

  const { data: types } = useQuery({
    queryKey: ['indicator-types'],
    queryFn: fetchIndicatorTypes,
  })

  const { data: viewerStateData } = useQuery({
    queryKey: ['viewer-state', runId],
    queryFn: () => fetchViewerState(runId!),
    enabled: !!runId,
  })

  // Seed local state once from server on first successful load (during render)
  if (!seeded && viewerStateData) {
    setInstances([...viewerStateData.indicators])
    setDetectorIds([...(viewerStateData.detectors ?? [])])
    setSeeded(true)
  }

  // Debounced PUT triggered by mutationVersion (only after seeding)
  // Keep the latest runId, instances, and detectorIds in a ref, updated in a layout effect
  const latestRef = useRef({ runId, instances, detectorIds })
  useEffect(() => {
    latestRef.current = { runId, instances, detectorIds }
  }, [runId, instances, detectorIds])

  useEffect(() => {
    if (!seeded || mutationVersion === 0) return
    if (runId === null) return
    const timer = setTimeout(() => {
      const { runId: rid, instances: insts, detectorIds: dets } = latestRef.current
      if (rid === null) return
      putViewerState(rid, { indicators: insts, detectors: dets }).catch(console.error)
    }, 300)
    return () => clearTimeout(timer)
  }, [seeded, mutationVersion, runId])

  const addInstance = useCallback(
    (type: string, params: Record<string, number>): string => {
      const id = newInstanceId()
      const newInstance: IndicatorInstance = { id, type, params }
      setInstances((prev) => [...prev, newInstance])
      setMutationVersion((v) => v + 1)
      return id
    },
    [],
  )

  const editInstance = useCallback((id: string, params: Record<string, number>) => {
    setInstances((prev) => prev.map((inst) => (inst.id === id ? { ...inst, params } : inst)))
    setMutationVersion((v) => v + 1)
  }, [])

  const removeInstance = useCallback((id: string) => {
    setInstances((prev) => prev.filter((inst) => inst.id !== id))
    setMutationVersion((v) => v + 1)
  }, [])

  const addDetector = useCallback((id: string) => {
    setDetectorIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
    setMutationVersion((v) => v + 1)
  }, [])

  const removeDetector = useCallback((id: string) => {
    setDetectorIds((prev) => prev.filter((d) => d !== id))
    setMutationVersion((v) => v + 1)
  }, [])

  const { data: indicatorData, isLoading } = useQuery({
    queryKey: ['indicator-data', barType, hashInstances(instances)],
    queryFn: () => fetchIndicatorData(barType, instances),
    enabled: !!barType && instances.length > 0,
  })

  const { data: detectorTypes = [] } = useDetectors()
  const { data: keyLevels } = useKeyLevels(barType, detectorIds)

  const getColor = useCallback(
    (id: string): string => colors[id] ?? getDefaultIndicatorColor(id),
    [colors],
  )

  const setColor = useCallback((id: string, color: string) => {
    setColorsState((prev) => {
      const next = { ...prev, [id]: color }
      saveColors(next)
      return next
    })
  }, [])

  return {
    // indicators
    types: types ?? [],
    instances,
    data: indicatorData,
    addInstance,
    editInstance,
    removeInstance,
    getColor,
    setColor,
    // detectors
    detectorTypes,
    detectorIds,
    addDetector,
    removeDetector,
    keyLevels,
    // shared
    isLoading,
  }
}
