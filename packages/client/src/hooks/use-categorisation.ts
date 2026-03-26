import { useState, useCallback } from 'react'
import type { TradeCategory } from '@/types/api'

const DEFAULT_CATEGORIES: readonly TradeCategory[] = [
  { id: 1, description: 'Trades to strategy, Win', tradeIds: new Set() },
  { id: 2, description: 'Trades to strategy, Loss', tradeIds: new Set() },
  { id: 3, description: 'Trades to strategy, overstays, Win', tradeIds: new Set() },
  { id: 4, description: 'Trades to strategy, overstays, Loss', tradeIds: new Set() },
  { id: 5, description: 'Does not trade to strategy: wrong entry', tradeIds: new Set() },
  { id: 6, description: 'Does not trade to strategy: wrong exit', tradeIds: new Set() },
  { id: 7, description: 'Does not trade to strategy: wrong entry and exit', tradeIds: new Set() },
]

export const useCategorisation = () => {
  const [categories, setCategories] = useState<readonly TradeCategory[]>(DEFAULT_CATEGORIES)

  const assignTrade = useCallback((categoryId: number, tradeRelativeId: number) => {
    setCategories(prev =>
      prev.map(cat => {
        const updated = new Set(cat.tradeIds)
        updated.delete(tradeRelativeId)
        if (cat.id === categoryId) updated.add(tradeRelativeId)
        return updated.size === cat.tradeIds.size ? cat : { ...cat, tradeIds: updated }
      }),
    )
  }, [])

  const updateDescription = useCallback((categoryId: number, description: string) => {
    setCategories(prev =>
      prev.map(cat =>
        cat.id === categoryId ? { ...cat, description } : cat,
      ),
    )
  }, [])

  return { categories, assignTrade, updateDescription }
}
