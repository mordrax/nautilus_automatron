import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useRuns = (page: number = 1) =>
  useQuery({
    queryKey: ['runs', page],
    queryFn: () => api.runEffect(api.getRuns(page)),
  })
