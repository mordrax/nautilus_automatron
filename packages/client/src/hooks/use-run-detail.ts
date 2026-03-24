import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useRunDetail = (runId: string) =>
  useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.runEffect(api.getRunDetail(runId)),
    enabled: !!runId,
  })

export const useTrades = (runId: string) =>
  useQuery({
    queryKey: ['trades', runId],
    queryFn: () => api.runEffect(api.getTrades(runId)),
    enabled: !!runId,
  })

export const useBars = (runId: string, barType: string) =>
  useQuery({
    queryKey: ['bars', runId, barType],
    queryFn: () => api.runEffect(api.getBars(runId, barType)),
    enabled: !!runId && !!barType,
  })

export const useEquity = (runId: string) =>
  useQuery({
    queryKey: ['equity', runId],
    queryFn: () => api.runEffect(api.getEquity(runId)),
    enabled: !!runId,
  })

export const usePositions = (runId: string) =>
  useQuery({
    queryKey: ['positions', runId],
    queryFn: () => api.runEffect(api.getPositions(runId)),
    enabled: !!runId,
  })
