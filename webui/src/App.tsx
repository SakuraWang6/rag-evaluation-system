import { useCallback, useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  ArrowRight,
  Beaker,
  BrainCircuit,
  Boxes,
  Database,
  ExternalLink,
  FileSearch,
  GitCompareArrows,
  Menu,
  Play,
  RefreshCw,
  ServerCog,
  X,
} from 'lucide-react'
import { api } from './api'
import { Empty, ErrorBanner, StateMark } from './components'
import { AppShell, PageHeader, Sidebar, Toolbar } from './components/AppShell'
import {
  ArtifactCasesPage as CasesPage,
  ArtifactComparePage as ComparePage,
  ArtifactRunDetailPage as RunDetailPage,
} from './components/ArtifactPages'
import { Button, DataTable, IconButton, SegmentedControl, StatusBadge, Surface } from './components/primitives'
import { LLMConfigurationPage, NewEvaluationPage, OverviewPage, ProductDatasetsPage, ProductSystemsPage } from './components/ProductPages'
import type { MessageKey } from './i18n'
import { useLocale } from './i18n/LocaleProvider'
import type {
  DatasetSummary,
  FormalDatasetsResponse,
  ExperimentSpec,
  JobRecord,
  RunManifest,
  SystemSummary,
  ProductSystemSummary,
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
      {route.page === 'overview' && data.productEnabled && <OverviewPage formalDatasets={data.formalDatasets} systems={productSystems} runs={data.runs.length} onNewEvaluation={() => route.go('new-evaluation')} onAddDataset={() => route.go('datasets')} onAddSystem={() => route.go('systems')} />}
      {route.page === 'new-evaluation' && data.productEnabled && <NewEvaluationPage formalDatasets={data.formalDatasets} onQueued={() => { void data.refresh(); route.go('runs') }} />}
      {route.page === 'datasets' && (data.productEnabled ? <ProductDatasetsPage datasets={data.datasets} formalDatasets={data.formalDatasets} refresh={data.refresh} /> : <DatasetsPage datasets={data.datasets} refresh={data.refresh} />)}
      {route.page === 'systems' && (data.productEnabled ? <ProductSystemsPage legacy={data.systems} /> : <SystemsPage systems={data.systems} />)}
      {route.page === 'llm' && data.productEnabled && <LLMConfigurationPage />}
      {route.page === 'experiments' && <ExperimentsPage experiments={data.experiments} />}
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

function ExperimentsPage({ experiments }: { experiments: ExperimentSpec[] }) {
  const { t } = useLocale()
  return <><PageIntro titleKey="page.experiments.title" descriptionKey="page.experiments.description" /><Surface tone="inset"><p>{t('page.experiments.readOnly')}</p></Surface><div className="experiment-list">{experiments.map((experiment) => { const repetitions = experiment.repetitions === 1 ? t('page.experiments.repetitions', { count: experiment.repetitions }) : t('page.experiments.repetitionsPlural', { count: experiment.repetitions }); return <Surface key={experiment.experiment_id}><div><span className="eyebrow">{experiment.adapter_id} / {t('page.experiments.seed', { value: experiment.seed })}</span><h3>{experiment.display_name?.trim() || experiment.experiment_id}</h3><p>{t('page.experiments.bundleSummary', { id: experiment.bundle_id.slice(0, 12), repetitions })}</p></div><code>{JSON.stringify({ query: experiment.query_config, metrics: experiment.metric_config }, null, 2)}</code></Surface> })}</div>{!experiments.length && <Empty>{t('page.experiments.empty')}</Empty>}</>
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

function Loading() { const { t } = useLocale(); return <div className="loading"><Boxes size={22} /><span>{t('loading.artifacts')}</span><i /></div> }
