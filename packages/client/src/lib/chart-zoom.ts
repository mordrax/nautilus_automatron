export const DEFAULT_VISIBLE_BARS = 50

export const computeDefaultStart = (
  totalBars: number,
  visible: number = DEFAULT_VISIBLE_BARS,
): number => {
  if (totalBars <= visible) return 0
  return ((totalBars - visible) / totalBars) * 100
}
