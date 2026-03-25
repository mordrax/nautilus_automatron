import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useIndicators = (runId: string, barType: string) => {
  const [enabledIds, setEnabledIds] = useState<ReadonlySet<string>>(new Set())

  const { data: available } = useQuery({
    queryKey: ['indicators'],
    queryFn: () => api.runEffect(api.getIndicators()),
  })

  const sortedIds = [...enabledIds].sort()

  const { data } = useQuery({
    queryKey: ['indicator-data', runId, barType, sortedIds],
    queryFn: () => api.runEffect(api.getIndicatorResult(runId, barType, sortedIds)),
    enabled: !!runId && !!barType && sortedIds.length > 0,
  })

  const toggle = useCallback((id: string) => {
    setEnabledIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  return { available: available ?? [], data: data ?? [], enabledIds, toggle }
}
