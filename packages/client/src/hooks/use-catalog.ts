import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useCatalog = () =>
  useQuery({
    queryKey: ['catalog'],
    queryFn: () => api.runEffect(api.getCatalog()),
  })
