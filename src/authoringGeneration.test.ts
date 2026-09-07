import { describe, expect, it } from 'vitest'
import { generationJobProgress, latestResumableAuthoringDataset, visibleDiscoveryJob, visibleGenerationJob } from './authoringGeneration'
import type { AuthoringDataset, AuthoringDiscoveryJob, AuthoringGenerationJob } from './types'

const dataset = (id: string, state: string, updatedAt: string, releaseIds: string[] = []): AuthoringDataset => ({
  authoring_dataset_id: id,
  state,
  created_at: updatedAt,
  updated_at: updatedAt,
  source: { original_filename: `${id}.docx`, sha256: 'a'.repeat(64), size_bytes: 1 },
  document_id: null,
  canonical_digest: null,
  analysis: {},
  failure: null,
  formal_release_ids: releaseIds,
})

const job = (id: string, state: AuthoringGenerationJob['state']): AuthoringGenerationJob => ({
  job_id: id,
  authoring_dataset_id: 'source',
  provider: 'ollama',
  seed: 0,
  remote_consent: false,
  state,
  requested_at: '2026-09-01T00:00:00Z',
  started_at: null,
  completed_at: null,
  cancel_requested: false,
  items: [
    { target_id: 'target-a', state: 'succeeded', attempts: 1, candidate_id: 'candidate-a', error_code: null, error_detail: null, started_at: null, completed_at: null },
    { target_id: 'target-b', state: 'failed', attempts: 1, candidate_id: null, error_code: 'provider_unavailable', error_detail: 'timed out', started_at: null, completed_at: null },
    { target_id: 'target-c', state: 'cancelled', attempts: 0, candidate_id: null, error_code: null, error_detail: null, started_at: null, completed_at: null },
  ],
})

const discoveryJob = (id: string, state: AuthoringDiscoveryJob['state']): AuthoringDiscoveryJob => ({
  job_id: id,
  authoring_dataset_id: 'source',
  provider: 'ollama',
  seed: 0,
  remote_consent: false,
  state,
  phase: state === 'failed' ? 'failed' : state === 'completed' ? 'completed' : 'awaiting_model',
  phase_detail: 'waiting',
  requested_at: '2026-09-01T00:00:00Z',
  started_at: '2026-09-01T00:00:01Z',
  completed_at: null,
  total_source_records: 42,
  model_source_records: 28,
  rule_target_count: 18,
  target_count: 0,
  error_code: null,
  error_detail: null,
})

describe('DOCX authoring recovery rules', () => {
  it('never resumes an authoring record already published as a formal dataset', () => {
    expect(latestResumableAuthoringDataset([
      dataset('published-state', 'formal_released', '2026-09-01T10:00:00Z'),
      dataset('published-link', 'approved', '2026-09-01T09:00:00Z', ['dataset-release-1']),
      dataset('unfinished', 'review_required', '2026-09-01T08:00:00Z'),
    ])?.authoring_dataset_id).toBe('unfinished')
  })

  it('keeps a live job visible over an older completed job and counts all settled work', () => {
    const active = job('generation-live', 'running')
    expect(visibleGenerationJob([job('generation-old', 'completed'), active])?.job_id).toBe('generation-live')
    expect(generationJobProgress(active)).toEqual({ completed: 3, succeeded: 1, failed: 1, total: 3 })
  })

  it('keeps the live target-discovery checkpoint visible after a reopen', () => {
    expect(visibleDiscoveryJob([discoveryJob('discovery-old', 'completed'), discoveryJob('discovery-live', 'running')])?.job_id).toBe('discovery-live')
  })
})
