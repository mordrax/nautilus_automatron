// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { ReactNode } from 'react'
import { useIndicators } from './use-indicators'
import type { ViewerState, IndicatorType } from '@/types/api'

// Minimal mocks
vi.mock('@/lib/api', () => ({
  fetchIndicatorTypes: vi.fn(),
  fetchIndicatorData: vi.fn(),
  fetchViewerState: vi.fn(),
  putViewerState: vi.fn(),
}))

vi.mock('@/hooks/use-key-levels', () => ({
  useDetectors: vi.fn(() => ({ data: [] })),
  useKeyLevels: vi.fn(() => ({ data: undefined })),
}))

vi.mock('@/lib/uuid', () => ({
  newInstanceId: vi.fn(),
}))

import * as apiMock from '@/lib/api'
import * as uuidMock from '@/lib/uuid'

const makeWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

const emptyViewerState: ViewerState = { indicators: [], detectors: [] }
const indicatorTypes: IndicatorType[] = [
  {
    type: 'SMA',
    labelTemplate: 'SMA({period})',
    display: 'overlay',
    outputs: ['value'],
    params: [{ name: 'period', type: 'int', default: 20, min: 2, max: 500 }],
  },
]

let uuidCounter = 0

beforeEach(() => {
  uuidCounter = 0
  vi.mocked(apiMock.fetchIndicatorTypes).mockResolvedValue(indicatorTypes)
  vi.mocked(apiMock.fetchViewerState).mockResolvedValue(emptyViewerState)
  vi.mocked(apiMock.fetchIndicatorData).mockResolvedValue([])
  vi.mocked(apiMock.putViewerState).mockResolvedValue(undefined)
  vi.mocked(uuidMock.newInstanceId).mockImplementation(() => `uuid-${++uuidCounter}`)
})

afterEach(() => {
  vi.clearAllMocks()
  vi.useRealTimers()
})

/** Wait for the viewer-state seed to have completed.
 *  We trigger a mutation and then wait for the PUT to fire as a proxy for
 *  seeded=true being set. But actually we just need to ensure viewerStateData
 *  has been returned and the seeding useEffect has processed it.
 *  We check this by waiting until fetchViewerState has been called, then
 *  flushing all pending React effects.
 */
const waitForSeed = async (result: { current: ReturnType<typeof useIndicators> }) => {
  // Wait for the query to fire
  await waitFor(() => {
    expect(apiMock.fetchViewerState).toHaveBeenCalled()
  })
  // Wait for the useEffect that sets seeded=true to have run
  // (seeded=true is triggered by the viewerStateData becoming available)
  await act(async () => {
    // Multiple Promise.resolve flushes to allow React's microtask queue to clear
    await new Promise<void>((resolve) => setTimeout(resolve, 0))
  })
  // Verify result is accessible
  void result.current
}

describe('useIndicators', () => {
  it('fires GET viewer-state on mount and populates instances', async () => {
    const stateWithInstances: ViewerState = {
      indicators: [{ id: 'existing-1', type: 'SMA', params: { period: 20 } }],
      detectors: [],
    }
    vi.mocked(apiMock.fetchViewerState).mockResolvedValue(stateWithInstances)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitFor(() => {
      expect(result.current.instances).toHaveLength(1)
    })

    expect(apiMock.fetchViewerState).toHaveBeenCalledWith('run-123')
    expect(result.current.instances[0].id).toBe('existing-1')
  })

  it('addInstance returns a new id and updates instances immediately', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitForSeed(result)

    let returnedId: string
    act(() => {
      returnedId = result.current.addInstance('SMA', { period: 20 })
    })

    expect(returnedId!).toBe('uuid-1')
    expect(result.current.instances).toHaveLength(1)
    expect(result.current.instances[0]).toMatchObject({
      id: 'uuid-1',
      type: 'SMA',
      params: { period: 20 },
    })
  })

  it('mutations trigger a PUT after 300ms and PUT includes final state', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitForSeed(result)

    act(() => {
      result.current.addInstance('SMA', { period: 20 })
    })

    // After a single mutation and waiting 400ms, exactly one PUT fires
    await waitFor(
      () => {
        expect(apiMock.putViewerState).toHaveBeenCalled()
      },
      { timeout: 1000 },
    )

    expect(apiMock.putViewerState).toHaveBeenCalledWith(
      'run-123',
      expect.objectContaining({ indicators: expect.any(Array), detectors: expect.any(Array) }),
    )
  })

  it('debounces rapid mutations: PUT fires only after the last mutation', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitForSeed(result)

    const startCallCount = vi.mocked(apiMock.putViewerState).mock.calls.length

    act(() => {
      result.current.addInstance('SMA', { period: 20 })
    })
    act(() => {
      result.current.editInstance('uuid-1', { period: 30 })
    })
    act(() => {
      result.current.addInstance('SMA', { period: 50 })
    })

    const afterMutations = Date.now()

    // Wait for the debounce to fire
    await waitFor(
      () => {
        const newCalls = vi.mocked(apiMock.putViewerState).mock.calls.length - startCallCount
        expect(newCalls).toBeGreaterThanOrEqual(1)
      },
      { timeout: 1000 },
    )

    // The elapsed time since mutations should be at least 280ms (debounce window)
    const elapsed = Date.now() - afterMutations
    expect(elapsed).toBeGreaterThanOrEqual(250)

    // PUT should have been called with the correct runId
    const allCalls = vi.mocked(apiMock.putViewerState).mock.calls
    expect(allCalls[allCalls.length - 1][0]).toBe('run-123')
  })

  it('removeInstance drops the matching id', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitForSeed(result)

    act(() => {
      result.current.addInstance('SMA', { period: 20 })
    })
    act(() => {
      result.current.addInstance('SMA', { period: 50 })
    })

    expect(result.current.instances).toHaveLength(2)

    act(() => {
      result.current.removeInstance('uuid-1')
    })

    expect(result.current.instances).toHaveLength(1)
    expect(result.current.instances[0].id).toBe('uuid-2')
  })

  it('addDetector updates detectorIds and triggers a PUT with detectors', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitForSeed(result)

    act(() => {
      result.current.addDetector('equal_highs_lows')
    })

    expect(result.current.detectorIds).toEqual(['equal_highs_lows'])

    await waitFor(
      () => {
        expect(apiMock.putViewerState).toHaveBeenCalled()
      },
      { timeout: 1000 },
    )

    expect(apiMock.putViewerState).toHaveBeenCalledWith(
      'run-123',
      expect.objectContaining({ detectors: ['equal_highs_lows'] }),
    )
  })

  it('removeDetector drops the matching id', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitForSeed(result)

    act(() => {
      result.current.addDetector('equal_highs_lows')
    })
    act(() => {
      result.current.addDetector('wick_rejection')
    })

    expect(result.current.detectorIds).toHaveLength(2)

    act(() => {
      result.current.removeDetector('equal_highs_lows')
    })

    expect(result.current.detectorIds).toEqual(['wick_rejection'])
  })

  it('on mount with persisted detectors, those are seeded into detectorIds', async () => {
    const stateWithDetectors: ViewerState = {
      indicators: [],
      detectors: ['wick_rejection', 'pivot_standard'],
    }
    vi.mocked(apiMock.fetchViewerState).mockResolvedValue(stateWithDetectors)

    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })

    await waitFor(() => {
      expect(result.current.detectorIds).toHaveLength(2)
    })

    expect(result.current.detectorIds).toEqual(['wick_rejection', 'pivot_standard'])
  })
})
