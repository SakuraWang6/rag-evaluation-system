import { AlertTriangle, Check, CircleDashed, Minus, X } from 'lucide-react'
import type { EvidenceItem, MetricResult, SummaryMetric } from './types'
import { evidenceState, metricLabel, presentMetric, stageOfMetric } from './semantics'

export function StateMark({ state }: { state: string }) {
  const normalized = state.toLowerCase()
  const icon = normalized === 'completed' || normalized === 'observed' || normalized === 'ok'
    ? <Check size={13} />
    : normalized === 'failed' || normalized === 'error' || normalized === 'system_error'
      ? <X size={13} />
      : normalized === 'timeout' || normalized === 'interrupted'
        ? <AlertTriangle size={13} />
        : normalized === 'unavailable' || normalized === 'not_applicable'
          ? <Minus size={13} />
          : <CircleDashed size={13} />
  return <span className={`state state--${normalized.replace('_', '-')}`}>{icon}{normalized.replaceAll('_', ' ')}</span>
}

export function MetricCell({ id, metric }: { id: string; metric: MetricResult | SummaryMetric }) {
  const presentation = presentMetric(metric)
  return (
    <div className={`metric metric--${presentation.state}`}>
      <div className="metric__head">
        <span className={`stage stage--${stageOfMetric(id)}`}>{stageOfMetric(id)}</span>
        <span>{metricLabel(id)}</span>
      </div>
      <strong>{presentation.text}</strong>
      {'standard_deviation' in metric && metric.standard_deviation !== undefined && (
        <small>σ {metric.standard_deviation.toFixed(3)} · n {metric.denominator}{metric.coverage !== undefined ? ` · coverage ${(metric.coverage * 100).toFixed(0)}%` : ''}</small>
      )}
      {'status_counts' in metric && metric.status_counts && metric.status_counts.needs_review ? <small>{metric.status_counts.needs_review} needs review</small> : null}
      {'reason' in metric && metric.reason && <small>{metric.reason}</small>}
    </div>
  )
}

export function EvidenceList({ title, items }: { title: string; items: EvidenceItem[] | null }) {
  const state = evidenceState(items)
  return (
    <section className={`evidence evidence--${state}`}>
      <header>
        <h4>{title}</h4>
        <span>{state === 'empty' ? 'Observed · 0 items' : state === 'unavailable' ? 'Not observable' : `${items!.length} items`}</span>
      </header>
      {state === 'unavailable' && <p className="semantic-note">Adapter capability is unavailable. This is not a zero score.</p>}
      {state === 'empty' && <p className="semantic-note">The stage ran and returned an empty result.</p>}
      {items?.map((item) => (
        <article className="evidence__item" key={item.item_id}>
          <div className="evidence__rank">#{item.rank}</div>
          <div>
            <div className="evidence__meta">
              <span>{item.document_id || 'unknown document'}</span>
              <span>{item.score === null ? 'score —' : `score ${item.score.toFixed(4)}`}</span>
              <span>{item.locator ? JSON.stringify(item.locator) : 'no locator'}</span>
            </div>
            <p>{item.content || '∅ empty content'}</p>
          </div>
        </article>
      ))}
    </section>
  )
}

export function Empty({ children }: { children: string }) {
  return <div className="empty"><span>∅</span><p>{children}</p></div>
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner"><AlertTriangle size={18} /><span>{message}</span></div>
}
