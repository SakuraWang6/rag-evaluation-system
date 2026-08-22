import { describe, expect, it } from 'vitest'
import { evidenceState, metricLabel, presentMetric } from './semantics'

describe('evaluation semantics', () => {
  it('does not conflate zero, unavailable, and error', () => {
    expect(presentMetric({ status: 'observed', value: 0, denominator: 1 }).text).toBe('0.000')
    expect(presentMetric({ status: 'unavailable', value: null, denominator: 0 }).state).toBe('unavailable')
    expect(presentMetric({ status: 'error', value: null, denominator: 1 }).state).toBe('error')
  })

  it('uses stage-specific names and deterministic groundedness', () => {
    expect(metricLabel('raw_recall@5')).toBe('Raw recall@5')
    expect(metricLabel('retrieval_stage_delta@5')).toBe('Retrieval stage delta@5')
    expect(metricLabel('answer_groundedness')).toBe('Groundedness (deterministic)')
  })

  it('distinguishes unobservable and observed-empty evidence', () => {
    expect(evidenceState(null)).toBe('unavailable')
    expect(evidenceState([])).toBe('empty')
    expect(evidenceState([{}])).toBe('observed')
  })
})
