import type { MetricResult, SummaryMetric } from './types'

export interface MetricLabelDescriptor {
  translationKey: string | null
  suffix: string
}

export const metricLabel = (id: string): MetricLabelDescriptor => {
  const exact: Record<string, string> = {
    answer_accuracy: 'metric.answerAccuracy',
    answer_groundedness: 'metric.groundedness',
    unsupported_answer_rate: 'metric.unsupportedAnswerRate',
    raw_mrr: 'metric.rawMrr',
    ranked_mrr: 'metric.rankedMrr',
  }
  if (exact[id]) return { translationKey: exact[id], suffix: '' }
  const localization = id.match(/^(raw|ranked|context)_localization_(matched|partial|retrieval_missed|provenance_missing)$/)
  if (localization) {
    const label: Record<string, string> = {
      matched: '证据定位命中',
      partial: '证据定位部分覆盖',
      retrieval_missed: '证据未检索到',
      provenance_missing: '原文坐标不可验证',
    }
    return { translationKey: null, suffix: label[localization[2]] }
  }
  const prefixes: Array<[string, string]> = [
    ['raw_recall', 'metric.rawRecall'],
    ['ranked_recall', 'metric.rankedRecall'],
    ['context_recall', 'metric.contextRecall'],
    ['retrieval_stage_delta', 'metric.retrievalStageDelta'],
    ['context_selection_loss', 'metric.contextSelectionLoss'],
  ]
  const match = prefixes.find(([prefix]) => id.startsWith(prefix))
  return match ? { translationKey: match[1], suffix: id.slice(match[0].length) } : { translationKey: null, suffix: id }
}

export const stageOfMetric = (id: string): 'raw' | 'ranked' | 'context' | 'answer' | 'derived' => {
  if (id.startsWith('raw_')) return 'raw'
  if (id.startsWith('ranked_')) return 'ranked'
  if (id.startsWith('context_')) return 'context'
  if (id.startsWith('answer_') || id === 'unsupported_answer_rate') return 'answer'
  return 'derived'
}

export interface MetricPresentation {
  value: string | null
  state: 'value' | 'unavailable' | 'not-applicable' | 'error' | 'needs-review'
}

export const presentMetric = (metric: MetricResult | SummaryMetric): MetricPresentation => {
  if (metric.status === 'unavailable') return { value: null, state: 'unavailable' }
  if (metric.status === 'not_applicable') return { value: null, state: 'not-applicable' }
  if (metric.status === 'error') return { value: null, state: 'error' }
  if (metric.status === 'needs_review') return { value: null, state: 'needs-review' }
  if (metric.value === null || metric.value === undefined) return { value: null, state: 'unavailable' }
  return { value: metric.value.toFixed(3), state: 'value' }
}

export const evidenceState = (items: unknown[] | null): 'unavailable' | 'empty' | 'observed' => {
  if (items === null) return 'unavailable'
  return items.length === 0 ? 'empty' : 'observed'
}
