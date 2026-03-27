import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useCatalogBars = (barType: string) =>
  useQuery({
    queryKey: ['catalog-bars', barType],
    queryFn: () => api.runEffect(api.getCatalogBars(barType)),
    enabled: !!barType,
  })
