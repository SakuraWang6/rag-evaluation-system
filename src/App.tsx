import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  Archive,
  ArrowRight,
  Beaker,
  Boxes,
  Braces,
  CheckCircle2,
  Database,
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
import type {
  CaseResult,
  ComparisonResponse,
  DatasetSummary,
  ExperimentSpec,
  JobRecord,
  RunManifest,
  RunSummary,
  SystemSummary,
} from './types'

type Page = 'datasets' | 'systems' | 'experiments' | 'runs' | 'cases' | 'compare'

const nav: Array<{ id: Page; label: string; icon: typeof Database }> = [
  { id: 'datasets', label: 'Datasets', icon: Database },
  { id: 'systems', label: 'Systems', icon: ServerCog },
  { id: 'experiments', label: 'Experiments', icon: Beaker },
  { id: 'runs', label: 'Runs', icon: Activity },
  { id: 'cases', label: 'Cases', icon: FileSearch },
  { id: 'compare', label: 'Compare', icon: GitCompareArrows },
]

function useHashRoute() {
  const read = () => {
    const raw = window.location.hash.replace(/^#\/?/, '')
    const [path, query = ''] = raw.split('?')
    const page = nav.some((item) => item.id === path) ? path as Page : 'runs'
    return { page, params: new URLSearchParams(query) }
  }
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const update = () => setRoute(read())
    window.addEventListener('hashchange', update)
    if (!window.location.hash) window.location.hash = '#/runs'
    return () => window.removeEventListener('hashchange', update)
  }, [])
  const go = (page: Page, params?: Record<string, string>) => {
    const query = params ? `?${new URLSearchParams(params)}` : ''
    window.location.hash = `#/${page}${query}`
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
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [health, nextDatasets, nextSystems, nextExperiments, nextRuns, nextJobs] = await Promise.all([
        api.health(), api.datasets(), api.systems(), api.experiments(), api.runs(), api.jobs(),
      ])
      setConnected(health.status === 'ok')
      setDatasets(nextDatasets)
      setSystems(nextSystems)
      setExperiments(nextExperiments)
      setRuns(nextRuns.sort((a, b) => b.started_at.localeCompare(a.started_at)))
      setJobs(nextJobs.sort((a, b) => b.updated_at.localeCompare(a.updated_at)))
      setError('')
    } catch (cause) {
      setConnected(false)
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

  return { datasets, systems, experiments, runs, jobs, error, connected, loading, refresh }
}

export default function App() {
  const route = useHashRoute()
  const data = usePlatformData()
  const [mobileNav, setMobileNav] = useState(false)
  const activeJobs = data.jobs.filter((job) => ['queued', 'running', 'cancelling'].includes(job.status)).length

  return (
    <div className="shell">
      <aside className={mobileNav ? 'rail rail--open' : 'rail'}>
        <button className="rail__close" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X /></button>
        <div className="brand">
          <span className="brand__index">R/E</span>
          <div><strong>Evidence</strong><em>ledger</em></div>
        </div>
        <nav>
          {nav.map((item, index) => {
            const Icon = item.icon
            return (
              <button key={item.id} className={route.page === item.id ? 'nav-item nav-item--active' : 'nav-item'} onClick={() => { route.go(item.id); setMobileNav(false) }}>
                <span className="nav-item__num">0{index + 1}</span><Icon size={17} /><span>{item.label}</span>
              </button>
            )
          })}
        </nav>
        <div className="rail__foot">
          <span className={data.connected ? 'pulse pulse--ok' : 'pulse'} />
          <div><strong>{data.connected ? 'Platform online' : 'Disconnected'}</strong><small>schema 2 · wire 1.0</small></div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu /></button>
          <div>
            <span className="eyebrow">RAG EVALUATION PLATFORM / {route.page.toUpperCase()}</span>
            <h1>{nav.find((item) => item.id === route.page)?.label}</h1>
          </div>
          <div className="topbar__status">
            <span><b>{data.runs.length}</b> schema-v2 runs</span>
            <span><b>{activeJobs}</b> active jobs</span>
            <button className="icon-button" onClick={() => void data.refresh()} title="Refresh"><RefreshCw size={17} /></button>
          </div>
        </header>

        {data.error && <ErrorBanner message={`Platform API: ${data.error}`} />}
        {data.loading ? <Loading /> : (
          <div className="page-enter">
            {route.page === 'datasets' && <DatasetsPage datasets={data.datasets} refresh={data.refresh} />}
            {route.page === 'systems' && <SystemsPage systems={data.systems} />}
            {route.page === 'experiments' && <ExperimentsPage experiments={data.experiments} refresh={data.refresh} />}
            {route.page === 'runs' && <RunsPage runs={data.runs} jobs={data.jobs} go={route.go} />}
            {route.page === 'cases' && <CasesPage runs={data.runs} initialRun={route.params.get('run') || ''} />}
            {route.page === 'compare' && <ComparePage runs={data.runs} />}
          </div>
        )}
      </main>
    </div>
  )
}

function PageIntro({ index, title, children }: { index: string; title: string; children: string }) {
  return <section className="page-intro"><span>{index}</span><div><h2>{title}</h2><p>{children}</p></div></section>
}

function DatasetsPage({ datasets, refresh }: { datasets: DatasetSummary[]; refresh: () => Promise<void> }) {
  const [path, setPath] = useState('')
  const [error, setError] = useState('')
  const register = async () => {
    try { await api.registerDataset(path); setPath(''); setError(''); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  return <>
    <PageIntro index="01" title="Immutable dataset bundles">Gold answers and evidence remain outside every Worker sandbox. A changed byte produces a new bundle ID.</PageIntro>
    <div className="action-strip">
      <label><span>Local Bundle 2.0 path</span><input value={path} onChange={(event) => setPath(event.target.value)} placeholder="/absolute/path/to/bundle" /></label>
      <button className="primary" disabled={!path} onClick={() => void register()}>Register bundle <ArrowRight size={16} /></button>
    </div>
    {error && <ErrorBanner message={error} />}
    <div className="ledger-table">
      <div className="ledger-row ledger-row--head"><span>Bundle / version</span><span>Cases</span><span>Content address</span><span>State</span></div>
      {datasets.map((dataset) => <div className="ledger-row" key={dataset.bundle_id}>
        <span><b>{dataset.name}</b><small>version {dataset.version}</small></span>
        <span className="big-num">{dataset.cases}</span>
        <code title={dataset.bundle_id}>{dataset.bundle_id.slice(0, 16)}…</code>
        <StateMark state="immutable" />
      </div>)}
    </div>
    {!datasets.length && <Empty>No schema-v2 bundles registered.</Empty>}
  </>
}

function SystemsPage({ systems }: { systems: SystemSummary[] }) {
  return <>
    <PageIntro index="02" title="Trusted local worker registry">Systems are registered by local CLI only. Credentials never cross into API responses.</PageIntro>
    <div className="system-grid">
      {systems.map((system) => <article className="system-card" key={system.system_id}>
        <div className="system-card__mark"><ServerCog /><span>{system.adapter_id}</span></div>
        <h3>{system.system_id}</h3><p>{system.description || 'Isolated adapter worker'}</p>
        <dl><dt>Factory</dt><dd>{system.adapter_factory}</dd><dt>Python</dt><dd>{system.python_executable}</dd><dt>Timeout</dt><dd>{system.request_timeout_seconds}s</dd><dt>Environment keys</dt><dd>{system.environment_keys.join(', ') || 'none'}</dd></dl>
      </article>)}
    </div>
    {!systems.length && <Empty>Register a Worker system from the trusted local CLI.</Empty>}
  </>
}

function ExperimentsPage({ experiments, refresh }: { experiments: ExperimentSpec[]; refresh: () => Promise<void> }) {
  const [showEditor, setShowEditor] = useState(false)
  const [draft, setDraft] = useState('{\n  "experiment_id": "",\n  "bundle_id": "",\n  "system_id": "",\n  "adapter_id": "",\n  "adapter_config": {},\n  "query_config": {"generate_answer": true},\n  "metric_config": {"k_values": [1, 3, 5]},\n  "case_ids": null,\n  "case_selection_id": "",\n  "seed": 0,\n  "repetitions": 1\n}')
  const [message, setMessage] = useState('')
  const create = async () => {
    try { await api.createExperiment(JSON.parse(draft)); setMessage('Experiment frozen.'); setShowEditor(false); await refresh() }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : String(cause)) }
  }
  const queue = async (id: string) => {
    try { await api.queueRun(id); setMessage(`Queued ${id}.`); await refresh() }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : String(cause)) }
  }
  return <>
    <PageIntro index="03" title="Config, not branches">An ExperimentSpec fixes system, selection, seed, stages, metrics, and repetition policy.</PageIntro>
    <div className="section-tools"><button className="primary" onClick={() => setShowEditor(!showEditor)}><Braces size={16} /> New ExperimentSpec</button><span>{message}</span></div>
    {showEditor && <div className="json-editor"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} spellCheck={false} /><button className="primary" onClick={() => void create()}>Validate & freeze</button></div>}
    <div className="experiment-list">
      {experiments.map((experiment) => <article key={experiment.experiment_id}>
        <div><span className="eyebrow">{experiment.adapter_id} / seed {experiment.seed}</span><h3>{experiment.experiment_id}</h3><p>bundle {experiment.bundle_id.slice(0, 12)}… · {experiment.repetitions} repetition{experiment.repetitions === 1 ? '' : 's'}</p></div>
        <code>{JSON.stringify({ query: experiment.query_config, metrics: experiment.metric_config }, null, 2)}</code>
        <button className="run-button" onClick={() => void queue(experiment.experiment_id)}><Play size={16} /> Queue run</button>
      </article>)}
    </div>
    {!experiments.length && <Empty>No frozen experiments.</Empty>}
  </>
}

function RunsPage({ runs, jobs, go }: { runs: RunManifest[]; jobs: JobRecord[]; go: (page: Page, params?: Record<string, string>) => void }) {
  const [selected, setSelected] = useState(runs[0]?.run_id || '')
  const [summary, setSummary] = useState<RunSummary | null>(null)
  const [verified, setVerified] = useState<boolean | null>(null)
  useEffect(() => {
    if (!selected && runs[0]) {
      setSelected(runs[0].run_id)
      return
    }
    if (!selected) return
    Promise.all([api.summary(selected), api.verify(selected)]).then(([nextSummary, integrity]) => { setSummary(nextSummary); setVerified(integrity.valid) }).catch(() => { setSummary(null); setVerified(false) })
  }, [selected, runs])
  const run = runs.find((item) => item.run_id === selected)
  return <>
    <PageIntro index="04" title="Runs are evidence artifacts">Timeouts, crashes, empty answers, and unavailable capabilities remain visible.</PageIntro>
    {!!jobs.length && <div className="job-tape">{jobs.slice(0, 5).map((job) => <div key={job.job_id}><StateMark state={job.status} /><span>{job.experiment.experiment_id}</span>{['queued', 'running', 'cancelling'].includes(job.status) && <button onClick={() => void api.cancelJob(job.job_id)}>cancel</button>}{job.error && <small>{job.error}</small>}</div>)}</div>}
    <div className="split-view">
      <div className="run-list">
        {runs.map((item) => <button key={item.run_id} onClick={() => setSelected(item.run_id)} className={selected === item.run_id ? 'run-row run-row--active' : 'run-row'}>
          <span><StateMark state={item.status} /><b>{item.experiment_id}</b></span><code>{item.run_id}</code><span>{item.adapter_id} · {new Date(item.started_at).toLocaleString()}</span>
        </button>)}
      </div>
      <section className="run-inspector">
        {!run ? <Empty>Select a completed schema-v2 run.</Empty> : <>
          <header><div><span className="eyebrow">{run.adapter_id} {run.adapter_version}</span><h2>{run.experiment_id}</h2></div><div className={verified ? 'integrity integrity--ok' : 'integrity'}><ShieldCheck />{verified === null ? 'Checking' : verified ? 'Artifacts verified' : 'Integrity failure'}</div></header>
          <div className="run-facts"><span><b>{run.execution_counts.completed || 0}</b> completed</span><span><b>{run.execution_counts.timeout || 0}</b> timeout</span><span><b>{run.execution_counts.system_error || 0}</b> system error</span><span><b>{run.repetitions}</b> repetitions</span></div>
          {summary && <div className="metric-grid">{Object.entries(summary.metrics).map(([id, metric]) => <MetricCell key={id} id={id} metric={metric} />)}</div>}
          <button className="primary" onClick={() => go('cases', { run: run.run_id })}>Inspect cases <ArrowRight size={16} /></button>
        </>}
      </section>
    </div>
    {!runs.length && <Empty>No new-platform runs. Legacy directories are intentionally invisible.</Empty>}
  </>
}

function CasesPage({ runs, initialRun }: { runs: RunManifest[]; initialRun: string }) {
  const [runId, setRunId] = useState(initialRun || runs[0]?.run_id || '')
  const [cases, setCases] = useState<CaseResult[]>([])
  const [selected, setSelected] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    if (!runId && runs[0]) {
      setRunId(runs[0].run_id)
      return
    }
    if (!runId) return
    api.cases(runId).then((value) => { setCases(value); setSelected(value[0] ? `${value[0].repetition}:${value[0].case_id}` : ''); setError('') }).catch((cause) => setError(String(cause)))
  }, [runId, runs])
  const detail = cases.find((item) => `${item.repetition}:${item.case_id}` === selected)
  return <>
    <PageIntro index="05" title="Case-level failure anatomy">Follow evidence from native retrieval through ranking and the exact final context.</PageIntro>
    <div className="case-selector"><label>Run<select value={runId} onChange={(event) => setRunId(event.target.value)}>{runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.experiment_id} · {run.run_id.slice(0, 8)}</option>)}</select></label></div>
    {error && <ErrorBanner message={error} />}
    <div className="case-layout">
      <aside className="case-index">{cases.map((item) => <button key={`${item.repetition}:${item.case_id}`} className={selected === `${item.repetition}:${item.case_id}` ? 'active' : ''} onClick={() => setSelected(`${item.repetition}:${item.case_id}`)}><span>R{item.repetition}</span><b>{item.case_id}</b><StateMark state={item.status} /></button>)}</aside>
      <div className="case-detail">{detail ? <CaseDetail value={detail} /> : <Empty>No case selected.</Empty>}</div>
    </div>
  </>
}

function CaseDetail({ value }: { value: CaseResult }) {
  const answer = value.gold_answer?.canonical
  return <>
    <section className="question-block"><span>QUESTION / REP {value.repetition} / SEED {value.seed}</span><h2>{value.question}</h2></section>
    {value.error && <ErrorBanner message={`${value.error.code}: ${value.error.message}`} />}
    <div className="answer-pair"><article><span>Gold answer</span><p>{Array.isArray(answer) ? answer.join(' · ') : answer ?? '—'} {value.gold_answer?.unit || ''}</p></article><article><span>Generated answer</span><p>{value.rag_result?.answer === '' ? '∅ empty answer' : value.rag_result?.answer ?? 'Unavailable'}</p></article></div>
    <section className="gold-evidence"><header><h4>Gold evidence groups</h4><span>all groups required · any item within group</span></header>{value.gold_evidence_set?.required_groups.map((group, index) => <div key={index}><b>G{index + 1}</b><span>{group.join(' OR ')}</span></div>) || <p>Unavailable</p>}{value.gold_evidence_set?.evidence.map((evidence) => <article key={evidence.evidence_id}><code>{evidence.evidence_id}</code><p>{evidence.quote_anchor || evidence.canonical_value}</p><small>{evidence.document_id} · {JSON.stringify(evidence.locator)}</small></article>)}</section>
    <EvidenceList title="Raw retrieved evidence" items={value.rag_result?.raw_retrieval ?? null} />
    <EvidenceList title="Ranked evidence" items={value.rag_result?.ranked_retrieval ?? null} />
    <EvidenceList title="Final context sent to generation" items={value.rag_result?.final_context ?? null} />
    <section className="metric-breakdown"><h4>Metric breakdown</h4><div className="metric-grid">{value.metrics.map((metric) => <MetricCell key={metric.metric_id} id={metric.metric_id} metric={metric} />)}</div></section>
    <div className="telemetry"><span>Latency <code>{JSON.stringify(value.rag_result?.latency ?? null)}</code></span><span>Token usage <code>{JSON.stringify(value.rag_result?.token_usage ?? null)}</code></span></div>
  </>
}

function ComparePage({ runs }: { runs: RunManifest[] }) {
  const [selected, setSelected] = useState<string[]>([])
  const [tier, setTier] = useState('task_comparable')
  const [result, setResult] = useState<ComparisonResponse | null>(null)
  const [error, setError] = useState('')
  const compare = async () => {
    try { setResult(await api.compare(selected, tier)); setError('') }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  const metricIds = useMemo(() => Array.from(new Set(result?.runs.flatMap((entry) => Object.keys(entry.summary.metrics)) || [])).sort(), [result])
  return <>
    <PageIntro index="06" title="Comparison with an explicit contract">Exploratory analysis never declares a winner. Strict comparison refuses controlled drift.</PageIntro>
    <div className="compare-controls"><label>Comparable tier<select value={tier} onChange={(event) => setTier(event.target.value)}><option value="task_comparable">Task comparable</option><option value="strict_controlled">Strict controlled</option><option value="exploratory">Exploratory</option></select></label><button className="primary" disabled={selected.length < 2} onClick={() => void compare()}><GitCompareArrows size={16} /> Validate & compare</button></div>
    <div className="run-picker">{runs.map((run) => <label key={run.run_id}><input type="checkbox" checked={selected.includes(run.run_id)} onChange={(event) => setSelected(event.target.checked ? [...selected, run.run_id] : selected.filter((id) => id !== run.run_id))} /><span><b>{run.experiment_id}</b><small>{run.adapter_id} · {run.run_id}</small></span></label>)}</div>
    {error && <ErrorBanner message={error} />}
    {result && <section className="comparison-result">
      <header className={result.compatible ? 'comparison-contract comparison-contract--ok' : 'comparison-contract'}><div>{result.compatible ? <CheckCircle2 /> : <Archive />}<span><b>{result.compatible ? 'Comparison contract satisfied' : 'Comparison rejected'}</b><small>{result.tier.replaceAll('_', ' ')}</small></span></div><strong>{result.may_declare_winner ? 'Ranking allowed' : 'No winner declaration'}</strong></header>
      {!!result.reasons.length && <ul className="reason-list">{result.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
      <div className="comparison-table"><div className="comparison-row comparison-row--head"><span>Metric / stage</span>{result.runs.map((entry) => <span key={entry.run.run_id}>{entry.run.adapter_id}<small>{entry.run.run_id.slice(0, 8)}</small></span>)}</div>{metricIds.map((id) => <div className="comparison-row" key={id}><span>{id}</span>{result.runs.map((entry) => <span key={entry.run.run_id}>{entry.summary.metrics[id] ? <MetricCell id={id} metric={entry.summary.metrics[id]} /> : <StateMark state="not_applicable" />}</span>)}</div>)}</div>
    </section>}
  </>
}

function Loading() {
  return <div className="loading"><Boxes /><span>Reading immutable artifacts</span><i /></div>
}
