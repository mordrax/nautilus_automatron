import { useEffect } from 'react'

type HotkeyActions = {
  readonly onPrevTrade: () => void
  readonly onNextTrade: () => void
  readonly onPrevTradeFast: () => void
  readonly onNextTradeFast: () => void
  readonly onCategoryAssign?: (categoryId: number) => void
}

export const useHotkeys = ({ onPrevTrade, onNextTrade, onPrevTradeFast, onNextTradeFast, onCategoryAssign }: HotkeyActions) => {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const caps = e.getModifierState?.('CapsLock')
      if (!caps) return

      // Skip hotkeys when typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        if (e.shiftKey) { onPrevTradeFast() } else { onPrevTrade() }
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        if (e.shiftKey) { onNextTradeFast() } else { onNextTrade() }
      } else if (onCategoryAssign && e.key >= '1' && e.key <= '7') {
        e.preventDefault()
        onCategoryAssign(Number(e.key))
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onPrevTrade, onNextTrade, onPrevTradeFast, onNextTradeFast, onCategoryAssign])
}
