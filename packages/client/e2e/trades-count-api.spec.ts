import { test, expect, request } from '@playwright/test'

/**
 * Happy-path regression test for the /trades API endpoint.
 *
 * For every run in the catalog, asserts:
 *   GET /api/runs/{id}/trades length === GET /api/runs/{id}.total_positions
 *
 * NOTE: the e2e test catalog uses HEDGING-OMS (each round-trip has a unique
 * position_id), so this test will pass even under the pre-fix transform that
 * grouped fills by position_id. The NETTING-OMS regression (multiple closed
 * positions sharing one position_id collapsing to a single trade) is covered
 * in packages/server/tests/test_transforms.py::test_positions_to_trades_one_per_closed_position.
 *
 * This spec guards the high-level shape contract: count parity + non-empty + JSON keys.
 */

const API_PORT = Number(process.env.TEST_API_PORT ?? 8000)
const API_BASE = `http://localhost:${API_PORT}`

const REQUIRED_TRADE_KEYS = [
  'relative_id',
  'position_id',
  'instrument_id',
  'direction',
  'entry_datetime',
  'entry_price',
  'exit_datetime',
  'exit_price',
  'quantity',
  'pnl',
  'currency',
] as const

type RunSummary = { run_id: string; total_positions: number }
type RunsPage = { runs: RunSummary[]; total: number; page: number; per_page: number }

test.describe('/api/runs/{id}/trades — count parity with closed positions', () => {
  test('every non-empty run returns one trade per closed position with the expected shape', async () => {
    const api = await request.newContext({ baseURL: API_BASE })

    const runsResp = await api.get('/api/runs')
    expect(runsResp.ok(), `GET /api/runs failed: ${runsResp.status()}`).toBe(true)
    const page = (await runsResp.json()) as RunsPage
    expect(page.runs.length, 'expected at least one run in the catalog').toBeGreaterThan(0)

    const nonEmptyRuns = page.runs.filter((r) => r.total_positions > 0)
    expect(
      nonEmptyRuns.length,
      'expected at least one run with >0 closed positions for the regression to be meaningful',
    ).toBeGreaterThan(0)

    for (const { run_id, total_positions } of nonEmptyRuns) {
      const tradesResp = await api.get(`/api/runs/${run_id}/trades`)
      expect(tradesResp.ok(), `GET /api/runs/${run_id}/trades failed`).toBe(true)
      const trades = (await tradesResp.json()) as Array<Record<string, unknown>>

      expect(
        trades.length,
        `run ${run_id}: trades count must equal total_positions (${total_positions})`,
      ).toBe(total_positions)

      const firstTrade = trades[0]
      for (const key of REQUIRED_TRADE_KEYS) {
        expect(
          firstTrade,
          `run ${run_id}: trade row missing required key '${key}'`,
        ).toHaveProperty(key)
      }

      const relativeIds = trades.map((t) => t.relative_id as number)
      const expectedIds = Array.from({ length: trades.length }, (_, i) => i + 1)
      expect(
        relativeIds,
        `run ${run_id}: relative_id should be 1..N in ts_opened ascending order`,
      ).toEqual(expectedIds)

      const directions = new Set(trades.map((t) => t.direction))
      const allowed = new Set(['Long', 'Short'])
      for (const d of directions) {
        expect(allowed.has(d as string), `run ${run_id}: unexpected direction '${d}'`).toBe(true)
      }
    }

    await api.dispose()
  })

  test('empty run (0 closed positions) returns 0 trades', async () => {
    const api = await request.newContext({ baseURL: API_BASE })

    const runsResp = await api.get('/api/runs')
    const page = (await runsResp.json()) as RunsPage
    const emptyRun = page.runs.find((r) => r.total_positions === 0)
    test.skip(!emptyRun, 'no empty run in catalog — coverage for this case lives in unit tests')

    const tradesResp = await api.get(`/api/runs/${emptyRun!.run_id}/trades`)
    // Empty collection: either 200 with [] or 404. Both are acceptable provided
    // no fabricated trade is returned.
    if (tradesResp.ok()) {
      const trades = (await tradesResp.json()) as unknown[]
      expect(trades.length, `empty run ${emptyRun!.run_id}: trades must be empty`).toBe(0)
    } else {
      expect(tradesResp.status(), `empty run ${emptyRun!.run_id}: expected 200 or 404`).toBe(404)
    }

    await api.dispose()
  })
})
