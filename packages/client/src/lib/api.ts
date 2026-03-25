import { Effect, pipe } from 'effect'
import type { RunsResponse, RunDetail, Trade, OhlcData, EquityPoint, Position, IndicatorMeta, IndicatorResult } from '@/types/api'

export type ApiError = {
  readonly _tag: 'ApiError'
  readonly url: string
  readonly cause: unknown
}

const makeApiError = (url: string, cause: unknown): ApiError => ({
  _tag: 'ApiError',
  url,
  cause,
})

const fetchJson = <T>(url: string): Effect.Effect<T, ApiError> =>
  Effect.tryPromise({
    try: () => fetch(url).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json() as Promise<T>
    }),
    catch: (e) => makeApiError(url, e),
  })

export const getVersion = () =>
  fetchJson<{ readonly version: string }>('/api/version')

export const getRuns = (page: number = 1) =>
  fetchJson<RunsResponse>(`/api/runs?page=${page}`)

export const getRunDetail = (runId: string) =>
  fetchJson<RunDetail>(`/api/runs/${runId}`)

export const getTrades = (runId: string) =>
  fetchJson<readonly Trade[]>(`/api/runs/${runId}/trades`)

export const getBars = (runId: string, barType: string) =>
  fetchJson<OhlcData>(`/api/runs/${runId}/bars/${encodeURIComponent(barType)}`)

export const getEquity = (runId: string) =>
  fetchJson<readonly EquityPoint[]>(`/api/runs/${runId}/equity`)

export const getPositions = (runId: string) =>
  fetchJson<readonly Position[]>(`/api/runs/${runId}/positions`)

export const getBarTypes = (runId: string) =>
  fetchJson<readonly string[]>(`/api/runs/${runId}/bars`)

export const getIndicators = () =>
  fetchJson<readonly IndicatorMeta[]>('/api/indicators')

export const getIndicatorResult = (runId: string, barType: string, ids: readonly string[]) =>
  fetchJson<readonly IndicatorResult[]>(
    `/api/runs/${runId}/bars/${encodeURIComponent(barType)}/indicators?ids=${ids.join(',')}`
  )

export const runEffect = <T>(effect: Effect.Effect<T, ApiError>): Promise<T> =>
  Effect.runPromise(
    pipe(
      effect,
      Effect.catchAll((e) => {
        console.error(`API Error [${e.url}]:`, e.cause)
        return Effect.fail(e)
      }),
    ),
  )
