import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'
import { getDefaultIndicatorColor } from '@/lib/chart-config'

const COLORS_STORAGE_KEY = 'indicator-colors'

const loadColors = (): Record<string, string> => {
  try {
    const stored = localStorage.getItem(COLORS_STORAGE_KEY)
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

const saveColors = (colors: Record<string, string>) => {
  localStorage.setItem(COLORS_STORAGE_KEY, JSON.stringify(colors))
}

export const useIndicators = (barType: string) => {
  const [enabledIds, setEnabledIds] = useState<ReadonlySet<string>>(new Set())
  const [colors, setColors] = useState<Record<string, string>>(loadColors)

  const { data: available } = useQuery({
    queryKey: ['indicators'],
    queryFn: () => api.runEffect(api.getIndicators()),
  })

  const sortedIds = [...enabledIds].sort()

  const { data } = useQuery({
    queryKey: ['indicator-data', barType, sortedIds],
    queryFn: () => api.runEffect(api.getIndicatorResult(barType, sortedIds)),
    enabled: !!barType && sortedIds.length > 0,
  })

  const toggle = useCallback((id: string) => {
    setEnabledIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const getColor = useCallback((id: string): string =>
    colors[id] ?? getDefaultIndicatorColor(id),
  [colors])

  const setColor = useCallback((id: string, color: string) => {
    setColors(prev => {
      const next = { ...prev, [id]: color }
      saveColors(next)
      return next
    })
  }, [])

  return { available: available ?? [], data: data ?? [], enabledIds, toggle, getColor, setColor }
}
