import { useCallback, useEffect, useMemo, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  Archive,
  ArrowLeft,
  ArrowRight,
  Beaker,
  Boxes,
  Braces,
  CheckCircle2,
  Database,
  ExternalLink,
  FileSearch,
  GitCompareArrows,
  Menu,
  Play,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  X,
} from 'lucide-react'
import { api } from './api'
import { Empty, ErrorBanner, EvidenceList, MetricCell, StateMark } from './components'
import { AppShell, PageHeader, Sidebar, Toolbar } from './components/AppShell'
import { Button, DataTable, IconButton, SegmentedControl, StatusBadge, Surface } from './components/primitives'
import { NewEvaluationPage, OverviewPage, ProductDatasetsPage, ProductSystemsPage } from './components/ProductPages'
import type { MessageKey } from './i18n'
import { useLocale } from './i18n/LocaleProvider'
import type {
  CaseResult,
  ComparisonResponse,
  DatasetSummary,
  ExperimentSpec,
  JobRecord,
  RunManifest,
  RunSummary,
  SystemSummary,
  ProductSystemSummary,
} from './types'

type NavigationPage = 'overview' | 'new-evaluation' | 'datasets' | 'systems' | 'experiments' | 'runs' | 'compare'
type Page = NavigationPage | 'cases' | 'run-detail'

type NavigationGroupId = 'overview' | 'evaluation' | 'resources' | 'advanced'
const nav: Array<{ id: NavigationPage; labelKey: MessageKey; icon: LucideIcon; group: NavigationGroupId; product?: boolean }> = [
  { id: 'overview', labelKey: 'nav.overview', icon: Boxes, group: 'overview', product: true },
  { id: 'new-evaluation', labelKey: 'nav.newEvaluation', icon: Play, group: 'evaluation', product: true },
  { id: 'runs', labelKey: 'nav.runs', icon: Activity, group: 'evaluation' },
  { id: 'compare', labelKey: 'nav.compare', icon: GitCompareArrows, group: 'evaluation' },
  { id: 'datasets', labelKey: 'nav.datasets', icon: Database, group: 'resources' },
  { id: 'systems', labelKey: 'nav.systems', icon: ServerCog, group: 'resources' },
  { id: 'experiments', labelKey: 'nav.experiments', icon: Beaker, group: 'advanced' },
]

function useHashRoute() {
  const read = () => {
    const raw = window.location.hash.replace(/^#\/?/, '')
    const [path, query = ''] = raw.split('?')
    const params = new URLSearchParams(query)
    if (path === 'runs' && params.get('run')) return { page: 'run-detail' as const, params }
    const page = [...nav.map((item) => item.id), 'cases'].includes(path) ? path as NavigationPage | 'cases' : 'overview'
    return { page, params }
  }
  const [route, setRoute] = useState(read)

  useEffect(() => {
    const update = () => setRoute(read())
    window.addEventListener('hashchange', update)
    if (!window.location.hash) window.location.hash = '#/overview'
    return () => window.removeEventListener('hashchange', update)
  }, [])

  const go = (page: Page, params?: Record<string, string>) => {
    const pathname = page === 'run-detail' ? 'runs' : page
    const query = params ? `?${new URLSearchParams(params)}` : ''
    window.location.hash = `#/${pathname}${query}`
  }
  return { ...route, go }
}

function usePlatformData() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [systems, setSystems] = useState<SystemSummary[]>([])
  const [experiments, setExperiments] = useState<ExperimentSpec[]>([])
  const [runs, setRuns] = useState<RunManifest[]>([])
  const [jobs, setJobs] = useState<JobRecord[]>([])
  const [error, setError] = useState('')
  const [connected, setConnected] = useState(false)
  const [productEnabled, setProductEnabled] = useState(false)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [health, nextDatasets, nextSystems, nextExperiments, nextRuns, nextJobs] = await Promise.all([
        api.health(), api.datasets(), api.systems(), api.experiments(), api.runs(), api.jobs(),
      ])
      setConnected(health.status === 'ok')
      setProductEnabled(health.product_layer_enabled === true)
      setDatasets(nextDatasets)
      setSystems(nextSystems)
      setExperiments(nextExperiments)
      setRuns(nextRuns.sort((a, b) => b.started_at.localeCompare(a.started_at)))
      setJobs(nextJobs.sort((a, b) => b.updated_at.localeCompare(a.updated_at)))
      setError('')
    } catch (cause) {
      setConnected(false)
      setProductEnabled(false)
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 3000)
    return () => window.clearInterval(timer)
  }, [refresh])

  return { datasets, systems, experiments, runs, jobs, error, connected, productEnabled, loading, refresh }
}

export default function App() {
  const route = useHashRoute()
  const data = usePlatformData()
  const { locale, setLocale, t } = useLocale()
  const [mobileNav, setMobileNav] = useState(false)
  const [productSystems, setProductSystems] = useState<ProductSystemSummary[]>([])
  const activeJobs = data.jobs.filter((job) => ['queued', 'running', 'cancelling'].includes(job.status)).length
  const activePage: NavigationPage = route.page === 'run-detail' || route.page === 'cases' ? 'runs' : route.page
  const activeItem = nav.find((item) => item.id === activePage)!
  const pageTitle = route.page === 'run-detail'
    ? t('page.runDetail.title')
    : route.page === 'cases'
      ? t('nav.cases')
      : t(activeItem.labelKey)

  useEffect(() => {
    if (!data.productEnabled) { setProductSystems([]); return }
    void api.productSystems().then(setProductSystems).catch(() => setProductSystems([]))
  }, [data.productEnabled, data.runs.length, data.datasets.length])

  useEffect(() => {
    if (!data.loading && !data.productEnabled && (route.page === 'overview' || route.page === 'new-evaluation')) route.go('runs')
  }, [data.loading, data.productEnabled, route.page])

  return <AppShell
    sidebar={<Sidebar open={mobileNav}>
      <div className="sidebar__top">
        <div className="app-mark" aria-hidden="true">R/E</div>
        <div><strong>{t('app.product')}</strong><small>{t('app.protocol')}</small></div>
        <IconButton className="sidebar__close" label={t('toolbar.closeNavigation')} onClick={() => setMobileNav(false)}><X size={16} /></IconButton>
      </div>
      <nav aria-label={t('toolbar.openNavigation')}>
        <NavigationGroup group="overview" label={t('nav.overview')} activePage={activePage} go={route.go} close={() => setMobileNav(false)} productEnabled={data.productEnabled} />
        <NavigationGroup group="evaluation" label={t('nav.evaluation')} activePage={activePage} go={route.go} close={() => setMobileNav(false)} productEnabled={data.productEnabled} />
        <NavigationGroup group="resources" label={t('nav.resources')} activePage={activePage} go={route.go} close={() => setMobileNav(false)} productEnabled={data.productEnabled} />
        <NavigationGroup group="advanced" label={t('nav.advanced')} activePage={activePage} go={route.go} close={() => setMobileNav(false)} productEnabled={data.productEnabled} />
      </nav>
      <div className="sidebar__footer"><StatusBadge state={data.connected ? 'ok' : 'unavailable'} /><span>{data.connected ? t('connection.online') : t('connection.offline')}</span></div>
    </Sidebar>}
    toolbar={<Toolbar>
      <IconButton className="toolbar__menu" label={t('toolbar.openNavigation')} onClick={() => setMobileNav(true)}><Menu size={18} /></IconButton>
      <div className="toolbar__title">
        <span className="toolbar__crumb">{t('app.product')}<span aria-hidden="true">/</span>{t(activeItem.labelKey)}{route.page === 'run-detail' && <><span aria-hidden="true">/</span>{t('page.runDetail.title')}</>}</span>
        <h1>{pageTitle}</h1>
      </div>
      <div className="toolbar__actions">
        <span className="toolbar-stat">{t('toolbar.runs', { count: data.runs.length })}</span>
        <span className="toolbar-stat">{t('toolbar.activeJobs', { count: activeJobs })}</span>
        <IconButton label={t('toolbar.refresh')} onClick={() => void data.refresh()}><RefreshCw size={16} /></IconButton>
        <SegmentedControl label={t('toolbar.language')} value={locale} onChange={setLocale} options={[
          { value: 'zh-CN', label: t('toolbar.chinese') },
          { value: 'en-US', label: t('toolbar.english') },
        ]} />
      </div>
    </Toolbar>}
  >
    {data.error && <ErrorBanner message={t('common.platformApi', { message: data.error })} />}
    {data.loading ? <Loading /> : <div className="page-content">
      {route.page === 'overview' && data.productEnabled && <OverviewPage datasets={data.datasets} systems={productSystems} runs={data.runs.length} onNewEvaluation={() => route.go('new-evaluation')} onAddDataset={() => route.go('datasets')} onAddSystem={() => route.go('systems')} />}
      {route.page === 'new-evaluation' && data.productEnabled && <NewEvaluationPage datasets={data.datasets} onQueued={() => { void data.refresh(); route.go('runs') }} />}
      {route.page === 'datasets' && (data.productEnabled ? <ProductDatasetsPage datasets={data.datasets} refresh={data.refresh} /> : <DatasetsPage datasets={data.datasets} refresh={data.refresh} />)}
      {route.page === 'systems' && (data.productEnabled ? <ProductSystemsPage legacy={data.systems} /> : <SystemsPage systems={data.systems} />)}
      {route.page === 'experiments' && <ExperimentsPage experiments={data.experiments} refresh={data.refresh} />}
      {route.page === 'runs' && <RunsPage runs={data.runs} jobs={data.jobs} go={route.go} />}
      {route.page === 'run-detail' && <RunDetailPage runId={route.params.get('run') || ''} runs={data.runs} go={route.go} />}
      {route.page === 'cases' && <CasesPage runs={data.runs} initialRun={route.params.get('run') || ''} go={route.go} />}
      {route.page === 'compare' && <ComparePage runs={data.runs} />}
    </div>}
  </AppShell>
}

function NavigationGroup({ group, label, activePage, go, close, productEnabled }: {
  group: NavigationGroupId
  label: string
  activePage: NavigationPage
  go: (page: Page, params?: Record<string, string>) => void
  close: () => void
  productEnabled: boolean
}) {
  const { t } = useLocale()
  const items = nav.filter((item) => item.group === group && (productEnabled || !item.product))
  if (!items.length) return null
  return <div className="sidebar__group">
    <span className="sidebar__label">{label}</span>
    {items.map((item) => {
      const Icon = item.icon
      return <button key={item.id} className={activePage === item.id ? 'sidebar-item sidebar-item--active' : 'sidebar-item'} onClick={() => { go(item.id); close() }}><Icon size={16} aria-hidden="true" /><span>{t(item.labelKey)}</span></button>
    })}
  </div>
}

function PageIntro({ titleKey, descriptionKey, actions }: { titleKey: MessageKey; descriptionKey: MessageKey; actions?: React.ReactNode }) {
  const { t } = useLocale()
  return <PageHeader title={t(titleKey)} description={t(descriptionKey)} actions={actions} />
}

function DatasetsPage({ datasets, refresh }: { datasets: DatasetSummary[]; refresh: () => Promise<void> }) {
  const { t } = useLocale()
  const [path, setPath] = useState('')
  const [error, setError] = useState('')
  const register = async () => {
    try { await api.registerDataset(path); setPath(''); setError(''); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  return <>
    <PageIntro titleKey="page.datasets.title" descriptionKey="page.datasets.description" />
    <Surface className="action-strip"><label><span>{t('page.datasets.path')}</span><input value={path} onChange={(event) => setPath(event.target.value)} placeholder={t('page.datasets.placeholder')} /></label><Button variant="primary" disabled={!path} onClick={() => void register()}>{t('page.datasets.register')} <ArrowRight size={16} /></Button></Surface>
    {error && <ErrorBanner message={error} />}
    <DataTable><thead><tr><th>{t('page.datasets.bundleVersion')}</th><th>{t('page.datasets.cases')}</th><th>{t('page.datasets.contentAddress')}</th><th>{t('page.datasets.state')}</th></tr></thead><tbody>{datasets.map((dataset) => <tr key={dataset.bundle_id}><td><strong>{dataset.name}</strong><small>{t('common.version', { version: dataset.version })}</small></td><td className="table-number">{dataset.cases}</td><td><code title={dataset.bundle_id}>{dataset.bundle_id.slice(0, 16)}…</code></td><td><StateMark state="immutable" /></td></tr>)}</tbody></DataTable>
    {!datasets.length && <Empty>{t('page.datasets.empty')}</Empty>}
  </>
}

function SystemsPage({ systems }: { systems: SystemSummary[] }) {
  const { t } = useLocale()
  return <><PageIntro titleKey="page.systems.title" descriptionKey="page.systems.description" /><div className="system-grid">{systems.map((system) => <Surface className="system-card" key={system.system_id}><div className="system-card__mark"><ServerCog size={17} /><span>{system.adapter_id}</span></div><h3>{system.system_id}</h3><p>{system.description || t('page.systems.defaultDescription')}</p><dl><dt>{t('page.systems.factory')}</dt><dd>{system.adapter_factory}</dd><dt>{t('page.systems.python')}</dt><dd>{system.python_executable}</dd><dt>{t('page.systems.timeout')}</dt><dd>{t('page.systems.seconds', { value: system.request_timeout_seconds })}</dd><dt>{t('page.systems.environmentKeys')}</dt><dd>{system.environment_keys.join(', ') || t('page.systems.none')}</dd></dl></Surface>)}</div>{!systems.length && <Empty>{t('page.systems.empty')}</Empty>}</>
}

function ExperimentsPage({ experiments, refresh }: { experiments: ExperimentSpec[]; refresh: () => Promise<void> }) {
  const { t } = useLocale()
  const [showEditor, setShowEditor] = useState(false)
  const [draft, setDraft] = useState('{\n  "experiment_id": "",\n  "bundle_id": "",\n  "system_id": "",\n  "adapter_id": "",\n  "adapter_config": {},\n  "query_config": {"generate_answer": true},\n  "metric_config": {"k_values": [1, 3, 5]},\n  "case_ids": null,\n  "case_selection_id": "",\n  "seed": 0,\n  "repetitions": 1\n}')
  const [message, setMessage] = useState('')
  const create = async () => {
    try { await api.createExperiment(JSON.parse(draft)); setMessage(t('page.experiments.frozen')); setShowEditor(false); await refresh() }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : String(cause)) }
  }
  const queue = async (id: string) => {
    try { await api.queueRun(id); setMessage(t('page.experiments.queued', { id })); await refresh() }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : String(cause)) }
  }
  return <><PageIntro titleKey="page.experiments.title" descriptionKey="page.experiments.description" /><div className="section-tools"><Button variant="primary" onClick={() => setShowEditor(!showEditor)}><Braces size={16} /> {t('page.experiments.new')}</Button><span>{message}</span></div>{showEditor && <Surface className="json-editor" tone="inset"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} spellCheck={false} /><Button variant="primary" onClick={() => void create()}>{t('page.experiments.validate')}</Button></Surface>}<div className="experiment-list">{experiments.map((experiment) => { const repetitions = experiment.repetitions === 1 ? t('page.experiments.repetitions', { count: experiment.repetitions }) : t('page.experiments.repetitionsPlural', { count: experiment.repetitions }); return <Surface key={experiment.experiment_id}><div><span className="eyebrow">{experiment.adapter_id} / {t('page.experiments.seed', { value: experiment.seed })}</span><h3>{experiment.experiment_id}</h3><p>{t('page.experiments.bundleSummary', { id: experiment.bundle_id.slice(0, 12), repetitions })}</p></div><code>{JSON.stringify({ query: experiment.query_config, metrics: experiment.metric_config }, null, 2)}</code><Button onClick={() => void queue(experiment.experiment_id)}><Play size={16} /> {t('page.experiments.queue')}</Button></Surface> })}</div>{!experiments.length && <Empty>{t('page.experiments.empty')}</Empty>}</>
}

function RunsPage({ runs, jobs, go }: { runs: RunManifest[]; jobs: JobRecord[]; go: (page: Page, params?: Record<string, string>) => void }) {
  const { t, formatDate } = useLocale()
  return <>
    <PageIntro titleKey="page.runs.title" descriptionKey="page.runs.description" />
    {!!jobs.length && <Surface className="job-tape" tone="inset">{jobs.slice(0, 5).map((job) => <div key={job.job_id}><StateMark state={job.status} /><span>{job.experiment.experiment_id}</span>{['queued', 'running', 'cancelling'].includes(job.status) && <Button variant="quiet" onClick={() => void api.cancelJob(job.job_id)}>{t('common.cancel')}</Button>}{job.error && <small>{job.error}</small>}</div>)}</Surface>}
    <Surface className="runs-navigator">{runs.map((run) => <button key={run.run_id} className="runs-navigator__row" onClick={() => go('run-detail', { run: run.run_id })}><span><StateMark state={run.status} /><strong>{run.experiment_id}</strong></span><code>{run.run_id}</code><span>{run.adapter_id} · {formatDate(run.started_at)}</span><ExternalLink size={15} aria-hidden="true" /></button>)}</Surface>
    {!runs.length && <Empty>{t('page.runs.empty')}</Empty>}
  </>
}

function RunDetailPage({ runId, runs, go }: { runId: string; runs: RunManifest[]; go: (page: Page, params?: Record<string, string>) => void }) {
  const { t, formatDate } = useLocale()
  const [summary, setSummary] = useState<RunSummary | null>(null)
  const [verified, setVerified] = useState<boolean | null>(null)
  const run = runs.find((item) => item.run_id === runId)
  useEffect(() => {
    if (!runId || !run) return
    Promise.all([api.summary(runId), api.verify(runId)]).then(([nextSummary, integrity]) => { setSummary(nextSummary); setVerified(integrity.valid) }).catch(() => { setSummary(null); setVerified(false) })
  }, [runId, run])

  if (!run) return <><PageIntro titleKey="page.runDetail.title" descriptionKey="page.runDetail.description" actions={<Button onClick={() => go('runs')}><ArrowLeft size={16} /> {t('page.runDetail.back')}</Button>} /><Empty>{t('page.runDetail.notFound', { id: runId || '—' })}</Empty></>

  return <>
    <PageIntro titleKey="page.runDetail.title" descriptionKey="page.runDetail.description" actions={<Button onClick={() => go('runs')}><ArrowLeft size={16} /> {t('page.runDetail.back')}</Button>} />
    <Surface className="run-detail-overview" tone="inspector">
      <header><div><span className="eyebrow">{run.adapter_id} {run.adapter_version}</span><h2>{run.experiment_id}</h2><code>{run.run_id}</code></div><div><StatusBadge state={run.status} /><span className={verified ? 'integrity integrity--ok' : 'integrity'}><ShieldCheck size={16} />{verified === null ? t('common.checking') : verified ? t('page.runs.verified') : t('page.runs.integrityFailure')}</span></div></header>
      <div className="run-detail-facts"><span><small>{t('page.runDetail.system')}</small><b>{run.system_id}</b></span><span><small>{t('page.runDetail.bundle')}</small><code>{run.bundle_id.slice(0, 16)}…</code></span><span><small>{t('page.runDetail.created')}</small><b>{formatDate(run.started_at)}</b></span><span><small>{t('page.runDetail.repetitions')}</small><b>{run.repetitions}</b></span></div>
      <div className="run-facts"><span><b>{run.execution_counts.completed || 0}</b>{t('page.runs.completed')}</span><span><b>{run.execution_counts.timeout || 0}</b>{t('page.runs.timeout')}</span><span><b>{run.execution_counts.system_error || 0}</b>{t('page.runs.systemError')}</span><span><b>{Object.keys(run.artifact_checksums).length}</b>{t('page.runDetail.checksums')}</span></div>
      {summary && <div className="metric-grid">{Object.entries(summary.metrics).map(([id, metric]) => <MetricCell key={id} id={id} metric={metric} />)}</div>}
      <Button variant="primary" onClick={() => go('cases', { run: run.run_id })}>{t('page.runs.inspectCases')} <ArrowRight size={16} /></Button>
    </Surface>
  </>
}

function CasesPage({ runs, initialRun, go }: { runs: RunManifest[]; initialRun: string; go: (page: Page, params?: Record<string, string>) => void }) {
  const { t } = useLocale()
  const [runId, setRunId] = useState(initialRun || runs[0]?.run_id || '')
  const [cases, setCases] = useState<CaseResult[]>([])
  const [selected, setSelected] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    if (!runId && runs[0]) { setRunId(runs[0].run_id); return }
    if (!runId) return
    api.cases(runId).then((value) => { setCases(value); setSelected(value[0] ? `${value[0].repetition}:${value[0].case_id}` : ''); setError('') }).catch((cause) => setError(String(cause)))
  }, [runId, runs])
  const detail = cases.find((item) => `${item.repetition}:${item.case_id}` === selected)
  return <><PageIntro titleKey="page.cases.title" descriptionKey="page.cases.description" actions={runId ? <Button onClick={() => go('run-detail', { run: runId })}><ArrowLeft size={16} /> {t('page.cases.backToRun')}</Button> : undefined} /><div className="case-selector"><label>{t('page.cases.run')}<select value={runId} onChange={(event) => setRunId(event.target.value)}>{runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.experiment_id} · {run.run_id.slice(0, 8)}</option>)}</select></label></div>{error && <ErrorBanner message={error} />}<div className="case-layout"><aside className="case-index">{cases.map((item) => <button key={`${item.repetition}:${item.case_id}`} className={selected === `${item.repetition}:${item.case_id}` ? 'active' : ''} onClick={() => setSelected(`${item.repetition}:${item.case_id}`)}><span>R{item.repetition}</span><b>{item.case_id}</b><StateMark state={item.status} /></button>)}</aside><div className="case-detail">{detail ? <CaseDetail value={detail} /> : <Empty>{t('page.cases.noneSelected')}</Empty>}</div></div></>
}

function CaseDetail({ value }: { value: CaseResult }) {
  const { t } = useLocale()
  const answer = value.gold_answer?.canonical
  const knownFailureLabels = ['retrieval_missing', 'ranking_failure', 'context_selection_loss', 'generation_failure', 'unsupported_answer', 'timeout', 'adapter_error', 'needs_review']
  const failureLabel = (label: string) => knownFailureLabels.includes(label) ? t(`failure.${label}` as MessageKey) : label
  return <><section className="question-block"><span>{t('page.cases.question', { repetition: value.repetition, seed: value.seed })}</span><h2>{value.question}</h2></section>{value.error && <ErrorBanner message={`${value.error.code}: ${value.error.message}`} />}{value.failure_assessment && <Surface className={value.failure_assessment.review_required ? 'failure-assessment failure-assessment--review' : 'failure-assessment'}><header><span>{t('page.cases.failureAssessment')}</span><StateMark state={value.failure_assessment.review_required ? 'needs_review' : value.failure_assessment.certainty} /></header><p>{value.failure_assessment.labels.length ? value.failure_assessment.labels.map(failureLabel).join(' · ') : t('page.cases.noFailureLabel')}</p>{value.failure_assessment.reasons.map((reason) => <small key={reason}>{reason}</small>)}</Surface>}<div className="answer-pair"><Surface tone="inset"><span>{t('page.cases.goldAnswer')}</span><p>{Array.isArray(answer) ? answer.join(' · ') : answer ?? '—'} {value.gold_answer?.unit || ''}</p></Surface><Surface><span>{t('page.cases.generatedAnswer')}</span><p>{value.rag_result?.answer === '' ? t('page.cases.emptyAnswer') : value.rag_result?.answer ?? t('common.unavailable')}</p></Surface></div><Surface className="gold-evidence"><header><h4>{t('page.cases.goldEvidence')}</h4><span>{t('page.cases.goldEvidenceRule')}</span></header>{value.gold_evidence_set?.required_groups.map((group, index) => <div key={index}><b>G{index + 1}</b><span>{group.join(' OR ')}</span></div>) || <p>{t('common.unavailable')}</p>}{value.gold_evidence_set?.evidence.map((evidence) => <article key={evidence.evidence_id}><code>{evidence.evidence_id}</code><p>{evidence.quote_anchor || evidence.canonical_value}</p><small>{evidence.document_id} · {JSON.stringify(evidence.locator)}</small></article>)}</Surface><EvidenceList titleKey="page.cases.rawEvidence" items={value.rag_result?.raw_retrieval ?? null} /><EvidenceList titleKey="page.cases.rankedEvidence" items={value.rag_result?.ranked_retrieval ?? null} /><EvidenceList titleKey="page.cases.finalContext" items={value.rag_result?.final_context ?? null} /><section className="metric-breakdown"><h4>{t('page.cases.metricBreakdown')}</h4><div className="metric-grid">{value.metrics.map((metric) => <MetricCell key={metric.metric_id} id={metric.metric_id} metric={metric} />)}</div></section><div className="telemetry"><span>{t('page.cases.latency')} <code>{JSON.stringify(value.rag_result?.latency ?? null)}</code></span><span>{t('page.cases.tokenUsage')} <code>{JSON.stringify(value.rag_result?.token_usage ?? null)}</code></span></div><p className="semantic-note">{t('page.cases.latencyNote')}</p></>
}

function ComparePage({ runs }: { runs: RunManifest[] }) {
  const { t, formatPercent } = useLocale()
  const [selected, setSelected] = useState<string[]>([])
  const [tier, setTier] = useState('task_comparable')
  const [result, setResult] = useState<ComparisonResponse | null>(null)
  const [error, setError] = useState('')
  const compare = async () => { try { setResult(await api.compare(selected, tier)); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } }
  const metricIds = useMemo(() => Array.from(new Set(result?.runs.flatMap((entry) => Object.keys(entry.summary.metrics)) || [])).sort(), [result])
  const tierKey: Record<string, MessageKey> = { task_comparable: 'page.compare.tierTaskComparable', strict_controlled: 'page.compare.tierStrictControlled', exploratory: 'page.compare.tierExploratory' }
  return <><PageIntro titleKey="page.compare.title" descriptionKey="page.compare.description" /><Surface className="compare-controls"><label>{t('page.compare.tier')}<select value={tier} onChange={(event) => setTier(event.target.value)}><option value="task_comparable">{t('page.compare.taskComparable')}</option><option value="strict_controlled">{t('page.compare.strictControlled')}</option><option value="exploratory">{t('page.compare.exploratory')}</option></select></label><Button variant="primary" disabled={selected.length < 2} onClick={() => void compare()}><GitCompareArrows size={16} /> {t('page.compare.validate')}</Button></Surface><div className="run-picker">{runs.map((run) => <label key={run.run_id}><input type="checkbox" checked={selected.includes(run.run_id)} onChange={(event) => setSelected(event.target.checked ? [...selected, run.run_id] : selected.filter((id) => id !== run.run_id))} /><span><b>{run.experiment_id}</b><small>{run.adapter_id} · {run.run_id}</small></span></label>)}</div>{error && <ErrorBanner message={error} />}{result && <section className="comparison-result"><header className={result.compatible ? 'comparison-contract comparison-contract--ok' : 'comparison-contract'}><div>{result.compatible ? <CheckCircle2 /> : <Archive />}<span><b>{result.compatible ? t('page.compare.satisfied') : t('page.compare.rejected')}</b><small>{t(tierKey[result.tier] || 'page.compare.exploratory')}</small></span></div><strong>{result.may_declare_winner ? t('page.compare.winnerEligible') : t('page.compare.noWinner')}</strong></header>{!!result.reasons.length && <ul className="reason-list">{result.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}<div className="comparison-table"><div className="comparison-row comparison-row--head"><span>{t('page.compare.metricContract')}</span>{result.runs.map((entry) => <span key={entry.run.run_id}>{entry.run.adapter_id}<small>{entry.run.run_id.slice(0, 8)}</small></span>)}</div>{metricIds.map((id) => { const decision = result.metric_decisions.find((item) => item.metric_id === id); return <div className="comparison-row" key={id}><span className="comparison-metric-label"><b>{id}</b><StateMark state={decision?.comparable ? 'comparable' : 'not_comparable'} /><small>{decision?.winner_eligible ? t('page.compare.winnerEligibleShort') : t('page.compare.notWinnerEligible')}</small>{decision && Object.entries(decision.coverage_by_run).map(([runId, coverage]) => <small key={runId}>{runId.slice(0, 8)} · {t('common.coverage', { value: formatPercent(coverage) })}</small>)}{!!decision?.reasons.length && <details><summary>{t('page.compare.whyUnavailable')}</summary><ul>{decision.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></details>}</span>{result.runs.map((entry) => <span key={entry.run.run_id}>{entry.summary.metrics[id] ? <MetricCell id={id} metric={entry.summary.metrics[id]} /> : <StateMark state="not_applicable" />}</span>)}</div> })}</div></section>}</>
}

function Loading() { const { t } = useLocale(); return <div className="loading"><Boxes size={22} /><span>{t('loading.artifacts')}</span><i /></div> }
