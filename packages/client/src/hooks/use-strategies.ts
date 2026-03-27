import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useStrategies = () =>
  useQuery({
    queryKey: ['strategies'],
    queryFn: () => api.runEffect(api.getStrategies()),
  })

export const useCatalogBarTypes = () =>
  useQuery({
    queryKey: ['catalog-bar-types'],
    queryFn: () => api.runEffect(api.getCatalogBarTypes()),
  })
