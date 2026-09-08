import { describe, expect, it } from 'vitest'
import {
  metricDescriptorSummary,
  observationPresentation,
  resolveMetricDescriptor,
} from './artifactPresentation'
import type {
  AggregateMetricV2,
  MetricDescriptorBindingV2,
  StageObservationV2,
} from './types'

const descriptor = {
  metric_id: 'ranked_metric@5',
  scorer_id: 'unified',
  scorer_version: '2.0',
  scorer_digest: `sha256:${'0'.repeat(64)}`,
  aggregation: 'canonical_extent_union',
  stage: 'ranked' as const,
  cutoff: 5,
  candidate_cutoff: 20,
  ranked_cutoff: 5,
  context_budget: 4096,
}

const metric: AggregateMetricV2 = {
  metric_id: descriptor.metric_id,
  status: 'observed',
  value: 1,
  case_count: 1,
  observed_case_count: 1,
  unavailable_case_count: 0,
  descriptor_digests: [`sha256:${'1'.repeat(64)}`],
  reason: null,
}

const binding: MetricDescriptorBindingV2 = {
  metric_id: descriptor.metric_id,
  descriptor_digest: metric.descriptor_digests[0],
  descriptor,
}

const stage = (
  observation_status: StageObservationV2['observation_status'],
  completeness: StageObservationV2['completeness'],
): StageObservationV2 => ({
  stage: 'ranked',
  observation_status,
  completeness,
  configured_cutoff: completeness === 'truncated' ? 20 : null,
  proven_prefix_depth: completeness === 'truncated' ? 5 : null,
  items: completeness === 'truncated' ? Array.from({ length: 5 }, (_, index) => ({
    native_chunk_id: `chunk-${index}`,
    native_rank: index + 1,
    runtime_score: null,
    content_sha256: '0'.repeat(64),
    content: null,
    provenance_edge_ids: [],
    metadata: {},
  })) : [],
  reason: observation_status === 'observed' ? null : 'not available',
  diagnostics: {},
})

describe('Artifact 2.0 presentation semantics', () => {
  it('resolves descriptors by persisted digest instead of metric-name parsing', () => {
    const resolved = resolveMetricDescriptor(metric, [binding])
    expect(resolved).toEqual({ descriptor, conflict: false })
    expect(metricDescriptorSummary(resolved.descriptor)).toContain('candidate C=20')
    expect(resolveMetricDescriptor(
      { ...metric, descriptor_digests: [...metric.descriptor_digests, `sha256:${'2'.repeat(64)}`] },
      [binding],
    ).conflict).toBe(true)
  })

  it.each(['unsupported', 'unobserved', 'failed', 'corrupted'] as const)(
    'keeps non-observed status %s distinct from completeness',
    (status) => {
      expect(observationPresentation(stage(status, 'unknown'))).toEqual({
        status,
        scope: 'unknown',
        scoreablePrefix: null,
      })
    },
  )

  it.each(['partial', 'unknown'] as const)(
    'does not invent a scoreable prefix for observed %s data',
    (completeness) => {
      expect(observationPresentation(stage('observed', completeness)).scoreablePrefix).toBeNull()
    },
  )

  it('preserves a verified truncated prefix without requiring global completeness', () => {
    expect(observationPresentation(stage('observed', 'truncated'))).toEqual({
      status: 'observed',
      scope: 'verified-prefix:5',
      scoreablePrefix: 5,
    })
  })
})
