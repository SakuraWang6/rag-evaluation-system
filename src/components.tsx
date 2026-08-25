import { AlertTriangle } from 'lucide-react'
import type { EvidenceItem, MetricResult, SummaryMetric } from './types'
import { evidenceState, metricLabel, presentMetric, stageOfMetric } from './semantics'
import { useLocale } from './i18n/LocaleProvider'
import type { MessageKey } from './i18n'
import { StatusBadge } from './components/primitives'

export function StateMark({ state }: { state: string }) {
  return <StatusBadge state={state} />
}

export function MetricCell({ id, metric }: { id: string; metric: MetricResult | SummaryMetric }) {
  const { t, formatPercent } = useLocale()
  const presentation = presentMetric(metric)
  const descriptor = metricLabel(id)
  const text = presentation.value ?? t(({
    unavailable: 'metric.valueUnavailable',
    'not-applicable': 'metric.valueNotApplicable',
    error: 'metric.valueError',
    'needs-review': 'metric.valueNeedsReview',
  } as const)[presentation.state === 'value' ? 'unavailable' : presentation.state])
  return (
    <div className={`metric metric--${presentation.state}`}>
      <div className="metric__head">
        <span className={`stage stage--${stageOfMetric(id)}`}>{t(`metric.stage.${stageOfMetric(id)}` as MessageKey)}</span>
        <span>{descriptor.translationKey ? `${t(descriptor.translationKey as MessageKey)}${descriptor.suffix}` : descriptor.suffix}</span>
      </div>
      <strong>{text}</strong>
      {'standard_deviation' in metric && metric.standard_deviation !== undefined && (
        <small>{t('metric.sampleSummary', { deviation: metric.standard_deviation.toFixed(3), count: metric.denominator, coverage: metric.coverage !== undefined ? formatPercent(metric.coverage) : '—' })}</small>
      )}
      {'status_counts' in metric && metric.status_counts && metric.status_counts.needs_review ? <small>{t('metric.needsReview', { count: metric.status_counts.needs_review })}</small> : null}
      {'reason' in metric && metric.reason && <small>{metric.reason}</small>}
    </div>
  )
}

export function EvidenceList({ titleKey, items }: { titleKey: MessageKey; items: EvidenceItem[] | null }) {
  const { t } = useLocale()
  const state = evidenceState(items)
  return (
    <section className={`evidence evidence--${state}`}>
      <header>
        <h4>{t(titleKey)}</h4>
        <span>{state === 'empty' ? t('evidence.observedEmpty') : state === 'unavailable' ? t('evidence.notObservable') : t('common.items', { count: items!.length })}</span>
      </header>
      {state === 'unavailable' && <p className="semantic-note">{t('evidence.unavailableNote')}</p>}
      {state === 'empty' && <p className="semantic-note">{t('evidence.emptyNote')}</p>}
      {items?.map((item) => (
        <article className="evidence__item" key={item.item_id}>
          <div className="evidence__rank">#{item.rank}</div>
          <div>
            <div className="evidence__meta">
              <span>{item.document_id || t('evidence.unknownDocument')}</span>
              <span>{item.score === null ? t('evidence.score', { value: '—' }) : t('evidence.score', { value: item.score.toFixed(4) })}</span>
              <span>{item.locator ? JSON.stringify(item.locator) : t('evidence.noLocator')}</span>
            </div>
            <p>{item.content || t('evidence.emptyContent')}</p>
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
  const { t } = useLocale()
  const detail = unwrapApiError(message)
  const remediation = errorRemediation(detail)
  return <div className="error-banner" role="alert">
    <AlertTriangle size={18} />
    <div>
      <strong>{t(remediation.title)}</strong>
      <p>{t(remediation.action)}</p>
      {detail && <details><summary>{t('error.details')}</summary><pre>{detail}</pre></details>}
    </div>
  </div>
}

function unwrapApiError(message: string): string {
  try {
    const parsed = JSON.parse(message) as { detail?: unknown }
    if (typeof parsed.detail === 'string') return parsed.detail
  } catch { /* The platform can also return plain-text errors. */ }
  return message
}

function errorRemediation(detail: string): { title: MessageKey; action: MessageKey } {
  const lower = detail.toLowerCase()
  if (lower.includes('docker') || lower.includes('orbstack')) return { title: 'error.dockerTitle', action: 'error.dockerAction' }
  if (lower.includes('ollama') || lower.includes('logical endpoint')) return { title: 'error.runtimeTitle', action: 'error.runtimeAction' }
  if (lower.includes('model') && (lower.includes('not found') || lower.includes('missing'))) return { title: 'error.modelTitle', action: 'error.modelAction' }
  if (lower.includes('zip') || lower.includes('bundle') || lower.includes('symlink') || lower.includes('archive')) return { title: 'error.datasetTitle', action: 'error.datasetAction' }
  if (lower.includes('secret') || lower.includes('keychain') || lower.includes('credential')) return { title: 'error.secretTitle', action: 'error.secretAction' }
  if (lower.includes('timeout') || lower.includes('timed out')) return { title: 'error.timeoutTitle', action: 'error.timeoutAction' }
  if (lower.includes('worker') || lower.includes('handshake') || lower.includes('adapter')) return { title: 'error.connectionTitle', action: 'error.connectionAction' }
  return { title: 'error.genericTitle', action: 'error.genericAction' }
}
