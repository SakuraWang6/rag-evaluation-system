import type { MetricResult, SummaryMetric } from './types'

export const metricLabel = (id: string): string => {
  const labels: Record<string, string> = {
    answer_accuracy: 'Answer accuracy',
    answer_groundedness: 'Groundedness (deterministic)',
    unsupported_answer_rate: 'Unsupported answer rate',
    raw_mrr: 'Raw MRR',
    ranked_mrr: 'Ranked MRR',
  }
  if (labels[id]) return labels[id]
  return id
    .replace(/^raw_recall/, 'Raw recall')
    .replace(/^ranked_recall/, 'Ranked recall')
    .replace(/^context_recall/, 'Context recall')
    .replace(/^retrieval_stage_delta/, 'Retrieval stage delta')
    .replace(/^context_selection_loss/, 'Context selection loss')
}

export const stageOfMetric = (id: string): 'raw' | 'ranked' | 'context' | 'answer' | 'derived' => {
  if (id.startsWith('raw_')) return 'raw'
  if (id.startsWith('ranked_')) return 'ranked'
  if (id.startsWith('context_')) return 'context'
  if (id.startsWith('answer_') || id === 'unsupported_answer_rate') return 'answer'
  return 'derived'
}

export interface MetricPresentation {
  text: string
  state: 'value' | 'unavailable' | 'not-applicable' | 'error' | 'needs-review'
}

export const presentMetric = (metric: MetricResult | SummaryMetric): MetricPresentation => {
  if (metric.status === 'unavailable') return { text: 'Unavailable', state: 'unavailable' }
  if (metric.status === 'not_applicable') return { text: 'Not applicable', state: 'not-applicable' }
  if (metric.status === 'error') return { text: 'Error', state: 'error' }
  if (metric.status === 'needs_review') return { text: 'Needs review', state: 'needs-review' }
  if (metric.value === null || metric.value === undefined) return { text: 'Unavailable', state: 'unavailable' }
  return { text: metric.value.toFixed(3), state: 'value' }
}

export const evidenceState = (items: unknown[] | null): 'unavailable' | 'empty' | 'observed' => {
  if (items === null) return 'unavailable'
  return items.length === 0 ? 'empty' : 'observed'
}
