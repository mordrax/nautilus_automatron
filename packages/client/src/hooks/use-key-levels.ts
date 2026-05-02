import { useQuery } from '@tanstack/react-query'
import { runEffect } from '@/lib/api'
import { getDetectors, getKeyLevels } from '@/lib/key-levels-api'

export const useDetectors = () =>
  useQuery({
    queryKey: ['key-levels', 'detectors'],
    queryFn: () => runEffect(getDetectors()),
  })

export const useKeyLevels = (barType: string, detectors: readonly string[]) => {
  // Sort for stable cache keys irrespective of caller's selection order.
  const sortedDetectors = [...detectors].sort()
  const cacheKey = sortedDetectors.join(',')

  return useQuery({
    queryKey: ['key-levels', barType, cacheKey],
    queryFn: () => runEffect(getKeyLevels(barType, sortedDetectors)),
    enabled: !!barType && sortedDetectors.length > 0,
  })
}
