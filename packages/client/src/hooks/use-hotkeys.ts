import { useEffect } from 'react'

type HotkeyActions = {
  readonly onPrevTrade: () => void
  readonly onNextTrade: () => void
  readonly onPrevTradeFast: () => void
  readonly onNextTradeFast: () => void
}

export const useHotkeys = ({ onPrevTrade, onNextTrade, onPrevTradeFast, onNextTradeFast }: HotkeyActions) => {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const caps = e.getModifierState?.('CapsLock')
      if (!caps) return

      e.preventDefault()

      if (e.key === 'ArrowLeft') {
        e.shiftKey ? onPrevTradeFast() : onPrevTrade()
      } else if (e.key === 'ArrowRight') {
        e.shiftKey ? onNextTradeFast() : onNextTrade()
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onPrevTrade, onNextTrade, onPrevTradeFast, onNextTradeFast])
}
