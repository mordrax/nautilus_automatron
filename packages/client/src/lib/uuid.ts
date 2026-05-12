export const newInstanceId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback (shouldn't fire in modern browsers/Node 19+; included for test safety)
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}
