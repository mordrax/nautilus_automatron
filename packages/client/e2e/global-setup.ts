import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/**
 * Global setup — runs once before all tests.
 * Ensures no stale viewer_state.json files exist in the test catalog
 * so tests start from a clean slate.
 */
export default async function globalSetup() {
  const catalogBacktestDir = path.resolve(
    __dirname,
    'test-data/backtest_catalog/backtest',
  )

  // Remove any viewer_state.json and .tmp files left by previous runs
  if (fs.existsSync(catalogBacktestDir)) {
    for (const runId of fs.readdirSync(catalogBacktestDir)) {
      const viewerStatePath = path.join(catalogBacktestDir, runId, 'viewer_state.json')
      if (fs.existsSync(viewerStatePath)) {
        fs.unlinkSync(viewerStatePath)
      }
      const tmpPath = viewerStatePath + '.tmp'
      if (fs.existsSync(tmpPath)) {
        fs.unlinkSync(tmpPath)
      }
    }
  }
}
