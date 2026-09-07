import { useCallback, useEffect, useMemo, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  Archive,
  ArrowLeft,
  ArrowRight,
  Beaker,
  BrainCircuit,
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
import { Button, DataTable, IconButton, Modal, SegmentedControl, StatusBadge, Surface } from './components/primitives'
import { FormalDocumentViewer, LLMConfigurationPage, NewEvaluationPage, OverviewPage, ProductDatasetsPage, ProductSystemsPage } from './components/ProductPages'
import type { MessageKey } from './i18n'
import { useLocale } from './i18n/LocaleProvider'
import type {
  AnswerJudgment,
  AnswerSupportVerdict,
  CaseListItem,
  CaseResult,
  ComparisonResponse,
  DatasetSummary,
  FormalDatasetsResponse,
  ExperimentSpec,
  JobRecord,
  RunManifest,
  RunSummary,
  SystemSummary,
  ProductSystemSummary,
  EvidenceJudgment,
  FormalDocumentView,
} from './types'

type NavigationPage = 'overview' | 'new-evaluation' | 'datasets' | 'systems' | 'llm' | 'experiments' | 'runs' | 'compare'
type Page = NavigationPage | 'cases' | 'run-detail'

type NavigationGroupId = 'overview' | 'evaluation' | 'resources' | 'advanced'
const nav: Array<{ id: NavigationPage; labelKey: MessageKey; icon: LucideIcon; group: NavigationGroupId; product?: boolean }> = [
  { id: 'overview', labelKey: 'nav.overview', icon: Boxes, group: 'overview', product: true },
  { id: 'new-evaluation', labelKey: 'nav.newEvaluation', icon: Play, group: 'evaluation', product: true },
  { id: 'runs', labelKey: 'nav.runs', icon: Activity, group: 'evaluation' },
  { id: 'compare', labelKey: 'nav.compare', icon: GitCompareArrows, group: 'evaluation' },
  { id: 'datasets', labelKey: 'nav.datasets', icon: Database, group: 'resources' },
  { id: 'systems', labelKey: 'nav.systems', icon: ServerCog, group: 'resources' },
  { id: 'llm', labelKey: 'nav.llm', icon: BrainCircuit, group: 'resources', product: true },
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
  const [formalDatasets, setFormalDatasets] = useState<FormalDatasetsResponse>({ releases: [], bundles_v3: [] })
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
      const [health, nextDatasets, nextFormalDatasets, nextSystems, nextExperiments, nextRuns, nextJobs] = await Promise.all([
        api.health(), api.datasets(), api.formalDatasets(), api.systems(), api.experiments(), api.runs(), api.jobs(),
      ])
      setConnected(health.status === 'ok')
      setProductEnabled(health.product_layer_enabled === true)
      setDatasets(nextDatasets)
      setFormalDatasets(nextFormalDatasets)
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
  }, [refresh])

  // Published datasets and completed runs are immutable. Polling the whole
  // application every three seconds used to compete with the on-demand reader
  // requests even when there was nothing active to observe.
  const hasActiveJobs = jobs.some((job) => ['queued', 'running', 'cancelling'].includes(job.status))
  useEffect(() => {
    if (!hasActiveJobs) return
    const timer = window.setInterval(() => void refresh(), 3000)
    return () => window.clearInterval(timer)
  }, [hasActiveJobs, refresh])

  return { datasets, formalDatasets, systems, experiments, runs, jobs, error, connected, productEnabled, loading, refresh }
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
        <div><strong>{t('app.product')}</strong></div>
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
      {route.page === 'overview' && data.productEnabled && <OverviewPage datasets={data.datasets} formalDatasets={data.formalDatasets} systems={productSystems} runs={data.runs.length} onNewEvaluation={() => route.go('new-evaluation')} onAddDataset={() => route.go('datasets')} onAddSystem={() => route.go('systems')} />}
      {route.page === 'new-evaluation' && data.productEnabled && <NewEvaluationPage datasets={data.datasets} formalDatasets={data.formalDatasets} onQueued={() => { void data.refresh(); route.go('runs') }} />}
      {route.page === 'datasets' && (data.productEnabled ? <ProductDatasetsPage datasets={data.datasets} formalDatasets={data.formalDatasets} refresh={data.refresh} /> : <DatasetsPage datasets={data.datasets} refresh={data.refresh} />)}
      {route.page === 'systems' && (data.productEnabled ? <ProductSystemsPage legacy={data.systems} /> : <SystemsPage systems={data.systems} />)}
      {route.page === 'llm' && data.productEnabled && <LLMConfigurationPage />}
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

function PageIntro({ titleKey, descriptionKey: _descriptionKey, actions }: { titleKey: MessageKey; descriptionKey?: MessageKey; actions?: React.ReactNode }) {
  const { t } = useLocale()
  return <PageHeader title={t(titleKey)} actions={actions} />
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
  return <><PageIntro titleKey="page.experiments.title" descriptionKey="page.experiments.description" /><div className="section-tools"><Button variant="primary" onClick={() => setShowEditor(!showEditor)}><Braces size={16} /> {t('page.experiments.new')}</Button><span>{message}</span></div>{showEditor && <Surface className="json-editor" tone="inset"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} spellCheck={false} /><Button variant="primary" onClick={() => void create()}>{t('page.experiments.validate')}</Button></Surface>}<div className="experiment-list">{experiments.map((experiment) => { const repetitions = experiment.repetitions === 1 ? t('page.experiments.repetitions', { count: experiment.repetitions }) : t('page.experiments.repetitionsPlural', { count: experiment.repetitions }); return <Surface key={experiment.experiment_id}><div><span className="eyebrow">{experiment.adapter_id} / {t('page.experiments.seed', { value: experiment.seed })}</span><h3>{experiment.display_name?.trim() || experiment.experiment_id}</h3><p>{t('page.experiments.bundleSummary', { id: experiment.bundle_id.slice(0, 12), repetitions })}</p></div><code>{JSON.stringify({ query: experiment.query_config, metrics: experiment.metric_config }, null, 2)}</code><Button onClick={() => void queue(experiment.experiment_id)}><Play size={16} /> {t('page.experiments.queue')}</Button></Surface> })}</div>{!experiments.length && <Empty>{t('page.experiments.empty')}</Empty>}</>
}

function runTitle(run: Pick<RunManifest, 'display_name' | 'experiment_id'>): string {
  return run.display_name?.trim() || run.experiment_id
}

function RunsPage({ runs, jobs, go }: { runs: RunManifest[]; jobs: JobRecord[]; go: (page: Page, params?: Record<string, string>) => void }) {
  const { t, formatDate } = useLocale()
  return <>
    <PageIntro titleKey="page.runs.title" descriptionKey="page.runs.description" />
    {!!jobs.length && <Surface className="job-tape" tone="inset">{jobs.slice(0, 5).map((job) => <div key={job.job_id}><StateMark state={job.status} /><span>{job.experiment.display_name?.trim() || job.experiment.experiment_id}</span>{['queued', 'running', 'cancelling'].includes(job.status) && <Button variant="quiet" onClick={() => void api.cancelJob(job.job_id)}>{t('common.cancel')}</Button>}{job.error && <small>{job.error}</small>}</div>)}</Surface>}
    <Surface className="runs-navigator">{runs.map((run) => <button key={run.run_id} className="runs-navigator__row" onClick={() => go('run-detail', { run: run.run_id })}><span><StateMark state={run.status} /><span><strong>{runTitle(run)}</strong><small>{run.adapter_id} · {formatDate(run.started_at)}</small></span></span><span className="runs-navigator__cases">{run.execution_counts.completed || 0} 已完成 · {run.execution_counts.timeout || 0} 超时</span><ExternalLink size={15} aria-hidden="true" /></button>)}</Surface>
    {!runs.length && <Empty>{t('page.runs.empty')}</Empty>}
  </>
}

function RunDetailPage({ runId, runs, go }: { runId: string; runs: RunManifest[]; go: (page: Page, params?: Record<string, string>) => void }) {
  const { t, formatDate } = useLocale()
  const [summary, setSummary] = useState<RunSummary | null>(null)
  const [verified, setVerified] = useState<boolean | null>(null)
  const [presentedName, setPresentedName] = useState('')
  const [nameDraft, setNameDraft] = useState('')
  const [nameBusy, setNameBusy] = useState(false)
  const [nameError, setNameError] = useState('')
  const run = runs.find((item) => item.run_id === runId)
  const presentationNote = (note: string) => ({
    'answer verdicts use the current deterministic rule and append-only adjudications': '答案判定使用当前确定性规则与追加的裁决记录。',
    'source localization and answer grounding are reported separately': '原文证据定位与答案的最终上下文依据是两个独立结论，不会相互替代。',
    'unverifiable retrieval metrics are excluded rather than shown as zero': '原文定位不可验证的检索指标会排除在统计外，不会显示为 0。',
  }[note] || note)
  useEffect(() => {
    if (!runId || !run) return
    Promise.all([api.summary(runId), api.verify(runId)]).then(([nextSummary, integrity]) => { setSummary(nextSummary); setVerified(integrity.valid) }).catch(() => { setSummary(null); setVerified(false) })
  }, [runId, run])

  useEffect(() => {
    const nextName = run ? runTitle(run) : ''
    setPresentedName(nextName)
    setNameDraft(nextName)
    setNameError('')
  }, [runId, run?.display_name, run?.experiment_id])

  if (!run) return <><PageIntro titleKey="page.runDetail.title" descriptionKey="page.runDetail.description" actions={<Button onClick={() => go('runs')}><ArrowLeft size={16} /> {t('page.runDetail.back')}</Button>} /><Empty>{t('page.runDetail.notFound', { id: runId || '—' })}</Empty></>

  const dataset = summary?.dataset
  const matrix = summary?.historical_rescore?.diagnostic_matrix
  const matrixStatus = matrix?.status_counts
  const semanticReview = summary?.semantic_review
  const semanticSupportReview = summary?.semantic_support_review
  const answerSupport = summary?.judgments?.answer_support
  const coreMetricIds = new Set([
    'answer_accuracy',
    'answer_groundedness',
    'answer_hallucination',
    'segment_ranked_recall@5',
    'segment_ranked_mrr',
    'segment_context_complete_evidence_coverage@5',
  ])
  const coreMetrics = summary ? Object.entries(summary.metrics).filter(([id]) => coreMetricIds.has(id)) : []
  const technicalMetrics = summary ? Object.entries(summary.metrics).filter(([id]) => !coreMetricIds.has(id)) : []
  const semanticReviewLabel: Record<string, string> = {
    not_configured: '未自动启动（请在模型配置中启用本机语义复核）',
    queued: '排队中',
    running: '正在进行',
    completed: '已完成',
    completed_with_errors: '完成但有待人工确认的项',
    skipped: '无需复核',
  }
  const saveName = async () => {
    if (!run || !nameDraft.trim()) { setNameError('运行名称不能为空。'); return }
    setNameBusy(true); setNameError('')
    try {
      const result = await api.renameRun(run.run_id, { display_name: nameDraft.trim() })
      setPresentedName(runTitle(result.run))
      setNameDraft(runTitle(result.run))
    } catch (cause) {
      setNameError(cause instanceof Error ? cause.message : String(cause))
    } finally { setNameBusy(false) }
  }

  return <>
    <PageIntro titleKey="page.runDetail.title" descriptionKey="page.runDetail.description" actions={<Button onClick={() => go('runs')}><ArrowLeft size={16} /> {t('page.runDetail.back')}</Button>} />
    <Surface className="run-detail-overview" tone="inspector">
      <header><div><span className="eyebrow">{run.adapter_id} · {formatDate(run.started_at)}</span><h2>{presentedName || runTitle(run)}</h2></div><div><StatusBadge state={run.status} />{verified !== null && <span className={verified ? 'integrity integrity--ok' : 'integrity'} title="只校验原始运行文件是否被改动，不代表答案或检索指标正确。"><ShieldCheck size={16} />{verified ? '原始文件完整' : t('page.runs.integrityFailure')}</span>}</div></header>
      <details className="run-name-editor"><summary>重命名运行</summary><div><input value={nameDraft} maxLength={160} onChange={(event) => setNameDraft(event.target.value)} aria-label="运行名称" /><Button disabled={nameBusy} onClick={() => void saveName()}>{nameBusy ? '正在保存…' : '保存名称'}</Button></div>{nameError && <ErrorBanner message={nameError} />}</details>
      <div className="run-detail-facts"><span><small>{t('page.runDetail.system')}</small><b>{run.system_id}</b></span><span className="run-detail-facts__dataset"><small>数据集</small><b title={dataset?.name}>{dataset?.name || '正在读取数据集信息…'}</b><small>{dataset?.version ? `版本 ${dataset.version} · ` : ''}{dataset ? `数据集 ${dataset.case_count ?? '—'} 题 · 本次 ${dataset.selected_case_count} 题` : '—'}</small></span><span><small>{t('page.runDetail.created')}</small><b>{formatDate(run.started_at)}</b></span><span><small>{t('page.runDetail.repetitions')}</small><b>{run.repetitions}</b></span></div>
      <div className="run-facts"><span><b>{run.execution_counts.completed || 0}</b>{t('page.runs.completed')}</span><span><b>{run.execution_counts.timeout || 0}</b>{t('page.runs.timeout')}</span><span><b>{run.execution_counts.system_error || 0}</b>{t('page.runs.systemError')}</span><span><b>{run.execution_counts.expected || dataset?.selected_case_count || '—'}</b>计划题数</span></div>
      {summary?.judgments && <section className="run-judgment-summary"><div><span>答案正确性</span><b>{summary.judgments.answer.correct} 正确</b><small>{summary.judgments.answer.incorrect} 不正确 · {summary.judgments.answer.needs_review} 待确认</small></div><div><span>答案依据 / 幻觉</span><b>{answerSupport ? `${answerSupport.supported || 0} 有依据` : '等待复核'}</b><small>{answerSupport ? `${answerSupport.unsupported || 0} 无依据 · ${answerSupport.needs_review || 0} 待确认` : '独立于检索命中与答案正确性。'}</small></div><div><span>检索验收</span><b>{coreMetrics.find(([id]) => id === 'segment_ranked_recall@5')?.[1].status === 'observed' ? '可统计' : '等待可观测 trace'}</b><small>严格 Retrieval 指标与答案评判分开统计。</small></div></section>}
      {summary && !!coreMetrics.length && <section className="run-core-metrics"><h3>核心结果</h3><div className="metric-grid">{coreMetrics.map(([id, metric]) => <MetricCell key={id} id={id} metric={metric} />)}</div></section>}
      <Button variant="primary" onClick={() => go('cases', { run: run.run_id })}>{t('page.runs.inspectCases')} <ArrowRight size={16} /></Button>
      <details className="run-technical-details"><summary>技术详情与审计记录</summary><div className="run-technical-details__body"><section className="run-technical-identifiers"><span><small>Run ID</small><code>{run.run_id}</code></span><span><small>Experiment ID</small><code>{run.experiment_id}</code></span><span><small>名称来源</small><b>{run.display_name_source || '历史兼容默认值'}</b></span><span><small>Adapter</small><b>{run.adapter_id} {run.adapter_version}</b></span><span><small>执行视图</small><b>{run.execution_view || 'legacy / unknown'}{run.diagnostic_only ? ' · diagnostic only' : ''}</b></span>{dataset && <><span><small>Release</small><code>{dataset.release_id || '—'}</code></span><span><small>Bundle</small><code>{dataset.bundle_id}</code></span></>}<span><small>原始封存文件</small><b>{Object.keys(run.artifact_checksums).length}</b></span></section>
        {summary?.localization && <details className="run-localization-details"><summary>原文证据定位（选定证据路径）</summary><p>每个阶段只统计该题满足标准答案所需的一条证据路径；“未检索到”与“坐标不可验证”是不同问题。</p><div>{(['raw', 'ranked', 'context'] as const).map((stage) => { const value = summary.localization!.stages[stage]; const label = { raw: '原始检索', ranked: '重排结果', context: '最终上下文' }[stage]; return <span key={stage}><b>{label}</b><small>{value.matched}/{value.denominator} 已定位 · {value.retrieval_missed} 未检索到 · {value.partial} 部分覆盖 · {value.provenance_missing} 坐标不可验证</small></span> })}</div></details>}
        {summary?.historical_rescore && <p className="historical-metric-note">历史派生复核：{summary.historical_rescore.status}（原始离线复算状态：{summary.historical_rescore.source_rescore_status || '—'}）。原始运行未被改写，也不是新 Worker 运行。{matrixStatus && <><br />完整 Gold 定位诊断：{matrix?.decision_count || 0} 次判断，其中 {matrixStatus.matched || 0} 命中、{matrixStatus.retrieval_missed || 0} 未检索到、{matrixStatus.provenance_missing || 0} 坐标不可验证。</>}</p>}
        {semanticReview && semanticReview.state !== 'not_started' && <p className="semantic-review-note">答案语义复核：{semanticReviewLabel[semanticReview.state] || semanticReview.state}。已处理 {semanticReview.processed_count}/{semanticReview.candidate_count} 项，LLM 已裁决 {semanticReview.adjudicated_count} 项，仍需人工确认 {semanticReview.needs_human_count} 项。{semanticReview.detail && <><br /><small>状态说明：{semanticReview.detail}</small></>}</p>}
        {semanticSupportReview && semanticSupportReview.state !== 'not_started' && <p className="semantic-review-note">答案依据复核：{semanticReviewLabel[semanticSupportReview.state] || semanticSupportReview.state}。已处理 {semanticSupportReview.processed_count}/{semanticSupportReview.candidate_count} 项，LLM 已裁决 {semanticSupportReview.adjudicated_count} 项，仍需人工确认 {semanticSupportReview.needs_human_count} 项。{semanticSupportReview.detail && <><br /><small>状态说明：{semanticSupportReview.detail}</small></>}</p>}
        {summary?.presentation?.notes.map((note) => <p className="historical-metric-note" key={note}>{presentationNote(note)}</p>)}
        {!!technicalMetrics.length && <section className="metric-breakdown"><h4>完整指标与阶段 trace</h4><div className="metric-grid">{technicalMetrics.map(([id, metric]) => <MetricCell key={id} id={id} metric={metric} />)}</div></section>}
      </div></details>
    </Surface>
  </>
}

function CasesPage({ runs, initialRun, go }: { runs: RunManifest[]; initialRun: string; go: (page: Page, params?: Record<string, string>) => void }) {
  const { t } = useLocale()
  const [runId, setRunId] = useState(initialRun || runs[0]?.run_id || '')
  const [cases, setCases] = useState<CaseListItem[]>([])
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<CaseResult | null>(null)
  const [loadingIndex, setLoadingIndex] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState('')
  const [detailError, setDetailError] = useState('')
  const [detailRevision, setDetailRevision] = useState(0)

  useEffect(() => {
    if (initialRun && initialRun !== runId) { setRunId(initialRun); return }
    if (!runId && runs[0]) setRunId(runs[0].run_id)
  }, [initialRun, runId, runs])

  useEffect(() => {
    if (!runId) return
    let active = true
    setLoadingIndex(true)
    setCases([])
    setDetail(null)
    setSelected('')
    setError('')
    void api.caseIndex(runId)
      .then((value) => {
        if (!active) return
        setCases(value)
        setSelected(value[0] ? `${value[0].repetition}:${value[0].case_id}` : '')
      })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : String(cause)) })
      .finally(() => { if (active) setLoadingIndex(false) })
    return () => { active = false }
  }, [runId])

  const selectedCase = cases.find((item) => `${item.repetition}:${item.case_id}` === selected)
  useEffect(() => {
    if (!runId || !selectedCase) return
    let active = true
    setLoadingDetail(true)
    setDetail(null)
    setDetailError('')
    void api.case(runId, selectedCase.case_id, selectedCase.repetition)
      .then((value) => { if (active) setDetail(value) })
      .catch((cause) => { if (active) setDetailError(cause instanceof Error ? cause.message : String(cause)) })
      .finally(() => { if (active) setLoadingDetail(false) })
    return () => { active = false }
  }, [runId, selectedCase?.case_id, selectedCase?.repetition, detailRevision])

  const run = runs.find((item) => item.run_id === runId)
  return <><PageIntro titleKey="page.cases.title" descriptionKey="page.cases.description" actions={runId ? <Button onClick={() => go('run-detail', { run: runId })}><ArrowLeft size={16} /> {t('page.cases.backToRun')}</Button> : undefined} />
    {run && <Surface className="case-run-context" tone="inset"><span>{t('page.cases.runScope')}</span><div><StatusBadge state={run.status} /><code>{runTitle(run)}</code></div></Surface>}
    {error && <ErrorBanner message={error} />}
    {!runId ? <Empty>{t('page.cases.select')}</Empty> : loadingIndex ? <div className="case-loading"><i /><span>{t('page.cases.loadingIndex')}</span></div> : !cases.length ? <Empty>{t('page.cases.noneSelected')}</Empty> : <div className="case-layout"><aside className="case-index">{cases.map((item) => <button key={`${item.repetition}:${item.case_id}`} className={selected === `${item.repetition}:${item.case_id}` ? 'active' : ''} onClick={() => setSelected(`${item.repetition}:${item.case_id}`)}><span>R{item.repetition}</span><b>{item.question}</b>{item.status === 'completed' ? <CaseJudgmentBadge kind="answer" value={item.answer_judgment} compact /> : <StateMark state={item.status} />}</button>)}</aside><div className="case-detail">{loadingDetail ? <div className="case-loading"><i /><span>{t('page.cases.loadingDetail')}</span></div> : detailError ? <ErrorBanner message={detailError} /> : detail ? <CaseDetail value={detail} run={run} onUpdated={() => { void api.caseIndex(runId).then(setCases); setDetailRevision((current) => current + 1) }} /> : <Empty>{t('page.cases.noneSelected')}</Empty>}</div></div>}</>
}

function CaseJudgmentBadge({ kind, value, compact = false }: { kind: 'answer'; value: AnswerJudgment; compact?: boolean } | { kind: 'evidence'; value: EvidenceJudgment; compact?: boolean }) {
  const { t } = useLocale()
  const labels: Record<string, MessageKey> = {
    correct: 'page.cases.answerCorrect',
    incorrect: 'page.cases.answerIncorrect',
    grounded: 'page.cases.evidenceGrounded',
    missing: 'page.cases.evidenceMissing',
    ungrounded: 'page.cases.evidenceUngrounded',
    unverifiable: 'page.cases.evidenceUnverifiable',
    needs_review: kind === 'answer' ? 'page.cases.answerNeedsReview' : 'page.cases.evidenceNeedsReview',
    unavailable: kind === 'answer' ? 'page.cases.answerUnavailable' : 'page.cases.evidenceUnavailable',
  }
  return <span className={`case-judgment case-judgment--${value}${compact ? ' case-judgment--compact' : ''}`}>{t(labels[value])}</span>
}

function CaseDetail({ value, run, onUpdated }: { value: CaseResult; run?: RunManifest; onUpdated: () => void }) {
  const { t } = useLocale()
  const answer = value.gold_answer?.canonical
  const [reviewer, setReviewer] = useState('本地评审员')
  const [reviewNote, setReviewNote] = useState('')
  const [reviewBusy, setReviewBusy] = useState<'human' | 'llm' | ''>('')
  const [supportReviewBusy, setSupportReviewBusy] = useState<'human' | 'llm' | ''>('')
  const [reviewError, setReviewError] = useState('')
  const [sourceBusy, setSourceBusy] = useState(false)
  const [sourceError, setSourceError] = useState('')
  const [source, setSource] = useState<{ document: FormalDocumentView; evidenceIds: string[] } | null>(null)
  const knownFailureLabels = ['provenance_unavailable', 'retrieval_missing', 'ranking_failure', 'context_selection_loss', 'generation_failure', 'unsupported_answer', 'timeout', 'adapter_error', 'needs_review']
  const failureLabel = (label: string) => knownFailureLabels.includes(label) ? t(`failure.${label}` as MessageKey) : label
  const diagnosticReason = (reason: string) => {
    const known: Record<string, MessageKey> = {
      'a required evidence group is absent from raw retrieval': 'page.cases.reason.rawEvidenceMissing',
      'raw evidence was present but ranked retrieval lost a required group': 'page.cases.reason.rankingLostEvidence',
      'ranked evidence was present but final context lost a required group': 'page.cases.reason.contextLostEvidence',
      'completed answer is not deterministically grounded': 'page.cases.reason.answerNotGrounded',
      'final context covered Gold Evidence but answer scorer failed': 'page.cases.reason.answerDidNotMatch',
      'raw retrieval is not observable': 'page.cases.reason.rawRetrievalUnavailable',
      'ranked retrieval is not observable': 'page.cases.reason.rankedRetrievalUnavailable',
      'final context is not observable': 'page.cases.reason.finalContextUnavailable',
    }
    return known[reason] ? t(known[reason]) : reason
  }
  const submitHumanReview = async (verdict: 'correct' | 'incorrect' | 'needs_review') => {
    if (!run) return
    setReviewBusy('human'); setReviewError('')
    try { await api.reviewCase(run.run_id, value.case_id, value.repetition, { verdict, reviewer, note: reviewNote }); setReviewNote(''); onUpdated() }
    catch (cause) { setReviewError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setReviewBusy('') }
  }
  const submitSemanticReview = async () => {
    if (!run) return
    setReviewBusy('llm'); setReviewError('')
    try { await api.semanticReviewCase(run.run_id, value.case_id, value.repetition); onUpdated() }
    catch (cause) { setReviewError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setReviewBusy('') }
  }
  const submitHumanSupportReview = async (verdict: AnswerSupportVerdict) => {
    if (!run) return
    setSupportReviewBusy('human'); setReviewError('')
    try { await api.reviewAnswerSupport(run.run_id, value.case_id, value.repetition, { verdict, reviewer, note: reviewNote }); setReviewNote(''); onUpdated() }
    catch (cause) { setReviewError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setSupportReviewBusy('') }
  }
  const submitSemanticSupportReview = async () => {
    if (!run) return
    setSupportReviewBusy('llm'); setReviewError('')
    try { await api.semanticReviewAnswerSupport(run.run_id, value.case_id, value.repetition); onUpdated() }
    catch (cause) { setReviewError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setSupportReviewBusy('') }
  }
  const openSource = async () => {
    if (!run?.dataset_release_id) { setSourceError('该运行没有关联可阅读的数据集版本，无法定位原文。'); return }
    setSourceBusy(true); setSourceError('')
    try {
      const [caseContent, document] = await Promise.all([api.formalDatasetCase(run.dataset_release_id, value.case_id), api.formalDatasetDocument(run.dataset_release_id)])
      setSource({ document, evidenceIds: caseContent.gold.evidence.filter((item) => item.canonical && item.reachable && !['near_miss', 'conflicting'].includes(item.role)).map((item) => item.canonical_object_id) })
    } catch (cause) { setSourceError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setSourceBusy(false) }
  }
  return <>
    <section className="question-block"><span>{t('page.cases.question', { repetition: value.repetition, seed: value.seed })}</span><h2>{value.question}</h2></section>
    {value.error && <ErrorBanner message={`${value.error.code}: ${value.error.message}`} />}
    <section className="case-judgments">
      <Surface className="case-judgment-card case-judgment-card--answer"><span>{t('page.cases.answerJudgment')}</span><CaseJudgmentBadge kind="answer" value={value.answer_judgment} /><p>{t('page.cases.answerJudgmentNote')}</p></Surface>
      <Surface className="case-judgment-card case-judgment-card--evidence"><span>{t('page.cases.evidenceJudgment')}</span><CaseJudgmentBadge kind="evidence" value={value.evidence_judgment} /><p>{value.evidence_judgment === 'unverifiable' ? '本次运行未返回可验证的原文定位；这不是检索失败，也不会计入检索评分。' : t('page.cases.evidenceJudgmentNote')}</p></Surface>
      <Surface className="case-judgment-card case-judgment-card--support"><span>答案依据 / 幻觉</span><StateMark state={value.answer_support_review?.latest?.verdict || 'needs_review'} /><p>{value.answer_support_review?.latest ? `${value.answer_support_review.latest.source === 'human' ? '人工' : 'LLM'}判定：${value.answer_support_review.latest.verdict === 'supported' ? '答案可由最终上下文支撑' : value.answer_support_review.latest.verdict === 'unsupported' ? '答案包含最终上下文无法支撑的主张' : '仍需人工判断'}` : '独立检查生成答案是否可由最终上下文支撑。'}</p></Surface>
    </section>
    <div className="answer-pair"><Surface tone="inset"><span>{t('page.cases.goldAnswer')}</span><p>{Array.isArray(answer) ? answer.join(' · ') : answer ?? '—'} {value.gold_answer?.unit || ''}</p></Surface><Surface><span>{t('page.cases.generatedAnswer')}</span><p>{value.rag_result?.answer === '' ? t('page.cases.emptyAnswer') : value.rag_result?.answer ?? t('common.unavailable')}</p></Surface></div>
    <details className="case-audit-details"><summary>查看原文证据、裁决与技术详情</summary><div className="case-audit-details__body"><Surface className="case-answer-evidence"><header><div><span className="eyebrow">标准答案原文证据</span><h4>直接打开正式数据集中的原文位置</h4><p>以阅读器打开段落、表格或单元格，并高亮可核验的正式数据集位置。</p></div><Button variant="primary" disabled={sourceBusy || !run?.dataset_release_id} onClick={() => void openSource()}>{sourceBusy ? '正在打开原文…' : '查看原文证据'}</Button></header>{sourceError && <ErrorBanner message={sourceError} />}<div className="case-answer-evidence__items">{value.gold_evidence_set?.evidence.map((evidence, index) => <article key={evidence.evidence_id}><span>{String(index + 1).padStart(2, '0')}</span><p>{evidence.quote_anchor || evidence.canonical_value || '原文证据'}</p></article>) || <p>{t('common.unavailable')}</p>}</div></Surface>
      {run && <><Surface className="case-review-panel" tone="inset"><header><div><span className="eyebrow">答案正确性裁决</span><h4>{value.review?.latest ? `已由${value.review.latest.source === 'human' ? '人工' : 'LLM'}裁决：${value.review.latest.verdict === 'correct' ? '正确' : value.review.latest.verdict === 'incorrect' ? '不正确' : '待人工确认'}` : '规则无法确定时，可用 LLM 或人工确认'}</h4>{value.review?.latest?.note && <p>{value.review.latest.note}</p>}</div></header><div className="case-review-panel__form"><label>评审人<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label><label>备注（可选）<input value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="说明判定依据" /></label></div><div className="case-review-panel__actions"><Button variant="quiet" disabled={!!reviewBusy} onClick={() => void submitSemanticReview()}>{reviewBusy === 'llm' ? 'LLM 正在复核…' : '使用 LLM 语义复核'}</Button><Button disabled={!!reviewBusy} onClick={() => void submitHumanReview('correct')}>人工确认正确</Button><Button disabled={!!reviewBusy} onClick={() => void submitHumanReview('incorrect')}>人工确认不正确</Button><Button variant="quiet" disabled={!!reviewBusy} onClick={() => void submitHumanReview('needs_review')}>暂无法判断</Button></div></Surface>
      <Surface className="case-review-panel" tone="inset"><header><div><span className="eyebrow">答案依据 / 幻觉裁决</span><h4>{value.answer_support_review?.latest ? `已由${value.answer_support_review.latest.source === 'human' ? '人工' : 'LLM'}裁决：${value.answer_support_review.latest.verdict === 'supported' ? '有依据' : value.answer_support_review.latest.verdict === 'unsupported' ? '无依据' : '待人工确认'}` : '检查最终上下文能否支撑生成答案'}</h4>{value.answer_support_review?.latest?.note && <p>{value.answer_support_review.latest.note}</p>}</div></header><div className="case-review-panel__actions"><Button variant="quiet" disabled={!!supportReviewBusy} onClick={() => void submitSemanticSupportReview()}>{supportReviewBusy === 'llm' ? 'LLM 正在复核…' : '使用 LLM 依据复核'}</Button><Button disabled={!!supportReviewBusy} onClick={() => void submitHumanSupportReview('supported')}>人工确认有依据</Button><Button disabled={!!supportReviewBusy} onClick={() => void submitHumanSupportReview('unsupported')}>人工确认无依据</Button><Button variant="quiet" disabled={!!supportReviewBusy} onClick={() => void submitHumanSupportReview('needs_review')}>暂无法判断</Button></div></Surface>{reviewError && <ErrorBanner message={reviewError} />}</>}
      <EvidenceList titleKey="page.cases.rawEvidence" items={value.rag_result?.raw_retrieval ?? null} />
      <EvidenceList titleKey="page.cases.rankedEvidence" items={value.rag_result?.ranked_retrieval ?? null} />
      <EvidenceList titleKey="page.cases.finalContext" items={value.rag_result?.final_context ?? null} />
      {value.failure_assessment && <details className="case-diagnostics"><summary>{t('page.cases.evidenceDiagnostics')}</summary><p>{t('page.cases.evidenceDiagnosticsNote')}</p>{value.failure_assessment.labels.length ? <div>{value.failure_assessment.labels.map((label) => <span key={label}>{failureLabel(label)}</span>)}</div> : <small>{t('page.cases.noFailureLabel')}</small>}{value.failure_assessment.reasons.map((reason) => <small key={reason}>{diagnosticReason(reason)}</small>)}</details>}
      <section className="metric-breakdown"><h4>{t('page.cases.metricBreakdown')}</h4>{value.evidence_judgment === 'unverifiable' && <p className="historical-metric-note">证据映射不可验证时，检索和依据指标不应解读为 0 分；重新运行或完成原文映射后会恢复统计。</p>}<div className="metric-grid">{value.metrics.map((metric) => <MetricCell key={metric.metric_id} id={metric.metric_id} metric={metric} />)}</div></section>
      <div className="telemetry"><span>{t('page.cases.latency')} <code>{JSON.stringify(value.rag_result?.latency ?? null)}</code></span><span>{t('page.cases.tokenUsage')} <code>{JSON.stringify(value.rag_result?.token_usage ?? null)}</code></span></div>
    </div></details>
    {source && run?.dataset_release_id && <Modal className="case-evidence-modal" title="标准答案原文证据" eyebrow="原文定位" closeLabel="关闭原文阅读器" onClose={() => setSource(null)}><FormalDocumentViewer view={source.document} evidenceIds={source.evidenceIds} onBack={() => setSource(null)} sourceUrl={api.formalDatasetSourceUrl(run.dataset_release_id)} nativeUrl={api.formalDatasetNativeDocumentUrl(run.dataset_release_id)} /></Modal>}
  </>
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
  return <><PageIntro titleKey="page.compare.title" descriptionKey="page.compare.description" /><Surface className="compare-controls"><label>{t('page.compare.tier')}<select value={tier} onChange={(event) => setTier(event.target.value)}><option value="task_comparable">{t('page.compare.taskComparable')}</option><option value="strict_controlled">{t('page.compare.strictControlled')}</option><option value="exploratory">{t('page.compare.exploratory')}</option></select></label><Button variant="primary" disabled={selected.length < 2} onClick={() => void compare()}><GitCompareArrows size={16} /> {t('page.compare.validate')}</Button></Surface><div className="run-picker">{runs.map((run) => <label key={run.run_id}><input type="checkbox" checked={selected.includes(run.run_id)} onChange={(event) => setSelected(event.target.checked ? [...selected, run.run_id] : selected.filter((id) => id !== run.run_id))} /><span><b>{runTitle(run)}</b><small>{run.adapter_id} · 技术 ID {run.run_id.slice(0, 8)}</small></span></label>)}</div>{error && <ErrorBanner message={error} />}{result && <section className="comparison-result"><header className={result.compatible ? 'comparison-contract comparison-contract--ok' : 'comparison-contract'}><div>{result.compatible ? <CheckCircle2 /> : <Archive />}<span><b>{result.compatible ? t('page.compare.satisfied') : t('page.compare.rejected')}</b><small>{t(tierKey[result.tier] || 'page.compare.exploratory')}</small></span></div><strong>{result.may_declare_winner ? t('page.compare.winnerEligible') : t('page.compare.noWinner')}</strong></header>{!!result.reasons.length && <ul className="reason-list">{result.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}<div className="comparison-table"><div className="comparison-row comparison-row--head"><span>{t('page.compare.metricContract')}</span>{result.runs.map((entry) => <span key={entry.run.run_id}>{runTitle(entry.run)}<small>{entry.run.adapter_id} · {entry.run.run_id.slice(0, 8)}</small></span>)}</div>{metricIds.map((id) => { const decision = result.metric_decisions.find((item) => item.metric_id === id); return <div className="comparison-row" key={id}><span className="comparison-metric-label"><b>{id}</b><StateMark state={decision?.comparable ? 'comparable' : 'not_comparable'} /><small>{decision?.winner_eligible ? t('page.compare.winnerEligibleShort') : t('page.compare.notWinnerEligible')}</small>{decision && Object.entries(decision.coverage_by_run).map(([runId, coverage]) => <small key={runId}>{runId.slice(0, 8)} · {t('common.coverage', { value: formatPercent(coverage) })}</small>)}{!!decision?.reasons.length && <details><summary>{t('page.compare.whyUnavailable')}</summary><ul>{decision.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></details>}</span>{result.runs.map((entry) => <span key={entry.run.run_id}>{entry.summary.metrics[id] ? <MetricCell id={id} metric={entry.summary.metrics[id]} /> : <StateMark state="not_applicable" />}</span>)}</div> })}</div></section>}</>
}

function Loading() { const { t } = useLocale(); return <div className="loading"><Boxes size={22} /><span>{t('loading.artifacts')}</span><i /></div> }
