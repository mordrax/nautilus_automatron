import type { Effect } from 'effect'
import { fetchJson, type ApiError } from '@/lib/api'
import type { DetectorMeta, KeyLevelDto } from '@/types/key-levels'

export const getKeyLevels = (
  barType: string,
  detectors: readonly string[],
): Effect.Effect<readonly KeyLevelDto[], ApiError> =>
  fetchJson<readonly KeyLevelDto[]>(
    `/api/bars/${encodeURIComponent(barType)}/key-levels?detectors=${detectors.join(',')}`,
  )

export const getDetectors = (): Effect.Effect<readonly DetectorMeta[], ApiError> =>
  fetchJson<readonly DetectorMeta[]>('/api/key-levels/detectors')
