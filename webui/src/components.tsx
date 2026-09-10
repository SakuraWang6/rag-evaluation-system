import { AlertTriangle } from 'lucide-react'
import type {
  AggregateMetricV2,
  EvaluationMetricV2,
  MetricDescriptorV2,
  StageObservationV2,
} from './types'
import { metricDescriptorSummary, observationPresentation } from './artifactPresentation'
import { useLocale } from './i18n/LocaleProvider'
import type { MessageKey } from './i18n'
import { StatusBadge } from './components/primitives'

export function StateMark({ state }: { state: string }) {
  return <StatusBadge state={state} />
}

export function ArtifactMetricCell({
  metric,
  descriptor,
  descriptorConflict = false,
}: {
  metric: AggregateMetricV2 | EvaluationMetricV2
  descriptor: MetricDescriptorV2 | null
  descriptorConflict?: boolean
}) {
  const { formatPercent } = useLocale()
  const aggregate = 'case_count' in metric
  const observed = metric.status === 'observed' && metric.value !== null
  return (
    <div className={`metric metric--${observed ? 'value' : 'unavailable'}`}>
      <div className="metric__head">
        <span className={`stage stage--${descriptor?.stage ?? 'derived'}`}>{descriptor?.stage ?? 'derived'}</span>
        <span>{metric.metric_id}</span>
      </div>
      <strong>{observed ? formatPercent(metric.value as number) : 'UNAVAILABLE'}</strong>
      {aggregate
        ? <small>{metric.observed_case_count}/{metric.case_count} cases observed</small>
        : <small>proved bounds {metric.lower_bound.toFixed(3)}–{metric.upper_bound.toFixed(3)}</small>}
      <small>{metricDescriptorSummary(descriptor)}</small>
      {descriptorConflict && <small>Persisted descriptor digests are missing or inconsistent.</small>}
      {metric.reason && <small>{metric.reason}</small>}
    </div>
  )
}

export function StageObservationPanel({
  title,
  observation,
}: {
  title: string
  observation: StageObservationV2
}) {
  const presentation = observationPresentation(observation)
  return (
    <section className={`evidence evidence--${observation.observation_status}`}>
      <header>
        <h4>{title}</h4>
        <span>{presentation.status} · {presentation.scope}</span>
      </header>
      <p className="semantic-note">
        completeness={observation.completeness}
        {observation.configured_cutoff === null ? '' : ` · configured cutoff=${observation.configured_cutoff}`}
        {observation.proven_prefix_depth === null ? '' : ` · proven prefix=${observation.proven_prefix_depth}`}
      </p>
      {observation.reason && <p className="semantic-note">{observation.reason}</p>}
      {observation.observation_status === 'observed' && observation.items.length === 0 && (
        <p className="semantic-note">Observed empty result.</p>
      )}
      {observation.items.map((item) => (
        <article className="evidence__item" key={`${item.native_rank}:${item.native_chunk_id}`}>
          <div className="evidence__rank">#{item.native_rank}</div>
          <div>
            <div className="evidence__meta">
              <code>{item.native_chunk_id}</code>
              <span>{item.runtime_score === null ? 'score —' : `score ${item.runtime_score.toFixed(4)}`}</span>
              <span>{item.provenance_edge_ids.length} provenance edge(s)</span>
            </div>
            <p>{item.content ?? 'Content was not persisted for this item.'}</p>
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

export function errorRemediation(detail: string): { title: MessageKey; action: MessageKey } {
  const lower = detail.toLowerCase()
  // The request wrapper appends the endpoint to transport failures.  Match
  // authoring discovery before the broad “Failed to fetch” branch so the
  // person sees the operation that needs attention, not a misleading claim
  // that the entire Platform is offline.
  if (lower.includes('/targets/discover')) return { title: 'error.targetDiscoveryTitle', action: 'error.targetDiscoveryAction' }
  if (lower.includes('failed to fetch') || lower.includes('networkerror') || lower.includes('platform api')) return { title: 'error.platformTitle', action: 'error.platformAction' }
  if (lower.includes('docker') || lower.includes('orbstack')) return { title: 'error.dockerTitle', action: 'error.dockerAction' }
  if (lower.includes('ollama') || lower.includes('logical endpoint')) return { title: 'error.runtimeTitle', action: 'error.runtimeAction' }
  if (lower.includes('model') && (lower.includes('not found') || lower.includes('missing'))) return { title: 'error.modelTitle', action: 'error.modelAction' }
  if (lower.includes('formal dataset release')) return { title: 'error.datasetTitle', action: 'error.datasetAction' }
  if (lower.includes('zip') || lower.includes('symlink') || lower.includes('archive')) return { title: 'error.datasetTitle', action: 'error.datasetAction' }
  if (lower.includes('secret') || lower.includes('keychain') || lower.includes('credential')) return { title: 'error.secretTitle', action: 'error.secretAction' }
  if (lower.includes('timeout') || lower.includes('timed out')) return { title: 'error.timeoutTitle', action: 'error.timeoutAction' }
  if (lower.includes('worker') || lower.includes('handshake') || lower.includes('adapter')) return { title: 'error.connectionTitle', action: 'error.connectionAction' }
  return { title: 'error.genericTitle', action: 'error.genericAction' }
}
