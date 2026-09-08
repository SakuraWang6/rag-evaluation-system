import type {
  AggregateMetricV2,
  MetricDescriptorBindingV2,
  MetricDescriptorV2,
  StageObservationV2,
} from './types'

export interface ResolvedMetricDescriptor {
  descriptor: MetricDescriptorV2 | null
  conflict: boolean
}

export function resolveMetricDescriptor(
  metric: AggregateMetricV2,
  bindings: MetricDescriptorBindingV2[],
): ResolvedMetricDescriptor {
  const expected = new Set(metric.descriptor_digests)
  const matches = bindings.filter(
    (item) => item.metric_id === metric.metric_id && expected.has(item.descriptor_digest),
  )
  return {
    descriptor: matches.length === 1 && expected.size === 1 ? matches[0].descriptor : null,
    conflict: expected.size !== 1 || matches.length !== 1,
  }
}

export function observationPresentation(observation: StageObservationV2): {
  status: string
  scope: string
  scoreablePrefix: number | null
} {
  if (observation.observation_status !== 'observed') {
    return {
      status: observation.observation_status,
      scope: 'unknown',
      scoreablePrefix: null,
    }
  }
  if (observation.completeness === 'complete') {
    return {
      status: 'observed',
      scope: 'complete',
      scoreablePrefix: observation.items.length,
    }
  }
  if (observation.completeness === 'truncated') {
    return {
      status: 'observed',
      scope: `verified-prefix:${observation.proven_prefix_depth ?? 0}`,
      scoreablePrefix: observation.proven_prefix_depth,
    }
  }
  return {
    status: 'observed',
    scope: observation.completeness,
    scoreablePrefix: null,
  }
}

export function metricDescriptorSummary(descriptor: MetricDescriptorV2 | null): string {
  if (!descriptor) return 'descriptor unavailable'
  return [
    descriptor.stage ?? 'derived',
    descriptor.cutoff === null ? null : `@${descriptor.cutoff}`,
    `candidate C=${descriptor.candidate_cutoff}`,
    `ranked K=${descriptor.ranked_cutoff}`,
    `context=${descriptor.context_budget}`,
    `scorer ${descriptor.scorer_version}`,
  ].filter(Boolean).join(' · ')
}
