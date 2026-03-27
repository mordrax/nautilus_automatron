import { useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '@/lib/api'
import type { CreateBacktestRequest } from '@/types/api'

export const useCreateBacktest = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: CreateBacktestRequest) =>
      api.runEffect(api.createBacktest(request)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}

export const useRerunBacktest = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) =>
      api.runEffect(api.rerunBacktest(runId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}

export const useDeleteBacktest = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) =>
      api.runEffect(api.deleteBacktest(runId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}
