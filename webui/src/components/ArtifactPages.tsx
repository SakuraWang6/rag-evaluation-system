import { useEffect, useMemo, useState } from 'react'
import { Archive, ArrowLeft, ArrowRight, CheckCircle2, GitCompareArrows, ShieldCheck } from 'lucide-react'

import { api } from '../api'
import { resolveMetricDescriptor } from '../artifactPresentation'
import { ArtifactMetricCell, Empty, ErrorBanner, StageObservationPanel, StateMark } from '../components'
import { useLocale } from '../i18n/LocaleProvider'
import type {
  ArtifactCaseIndexViewV2,
  ArtifactCaseViewV2,
  ArtifactOverviewV2,
  ComparisonResponse,
  RunArtifactCaseV2,
  RunCaseIndexEntryV2,
  RunManifest,
} from '../types'
import { Button, StatusBadge, Surface } from './primitives'

type ResultPage = 'runs' | 'cases' | 'run-detail'
type Go = (page: ResultPage, params?: Record<string, string>) => void

const displayRunTitle = (run: Pick<RunManifest, 'display_name' | 'experiment_id'>) =>
  run.display_name?.trim() || run.experiment_id

function ResultPageIntro({ title, description, actions }: { title: string; description: string; actions?: React.ReactNode }) {
  return <header className="page-intro"><div><h1>{title}</h1><p>{description}</p></div>{actions}</header>
}

function AvailabilityNotice({ value }: { value: Pick<ArtifactOverviewV2, 'availability' | 'reason' | 'artifact_contract_version'> }) {
  if (value.availability === 'available') return null
  return <div className="error-banner" role="status"><Archive size={18} /><div><strong>{value.availability === 'corrupted' ? 'Artifact 2.0 已损坏' : '历史结果不可用于 v2 指标'}</strong><p>{value.reason}</p><small>Artifact contract {value.artifact_contract_version}</small></div></div>
}

export function ArtifactRunDetailPage({ runId, runs, go }: { runId: string; runs: RunManifest[]; go: Go }) {
  const { formatDate } = useLocale()
  const [overview, setOverview] = useState<ArtifactOverviewV2 | null>(null)
  const [loadError, setLoadError] = useState('')
  const [presentedName, setPresentedName] = useState('')
  const [nameDraft, setNameDraft] = useState('')
  const [nameBusy, setNameBusy] = useState(false)
  const run = runs.find((item) => item.run_id === runId)

  useEffect(() => {
    if (!runId || !run) return
    let active = true
    void api.summary(runId)
      .then((value) => { if (active) { setOverview(value); setLoadError('') } })
      .catch((cause) => { if (active) setLoadError(cause instanceof Error ? cause.message : String(cause)) })
    return () => { active = false }
  }, [runId, run])

  useEffect(() => {
    const name = run ? displayRunTitle(run) : ''
    setPresentedName(name)
    setNameDraft(name)
  }, [runId, run?.display_name, run?.experiment_id])

  if (!run) return <><ResultPageIntro title="运行结果" description="查看持久化的评测结果。" actions={<Button onClick={() => go('runs')}><ArrowLeft size={16} />返回</Button>} /><Empty>未找到该运行。</Empty></>

  const summary = overview?.summary
  const required = new Set(summary?.leaderboard_eligibility.required_metric_ids ?? [])
  const coreMetrics = summary?.metrics.filter((metric) => required.has(metric.metric_id)) ?? []
  const diagnosticMetrics = summary?.metrics.filter((metric) => !required.has(metric.metric_id)) ?? []
  const saveName = async () => {
    if (!nameDraft.trim()) return
    setNameBusy(true)
    try {
      const result = await api.renameRun(run.run_id, { display_name: nameDraft.trim() })
      setPresentedName(displayRunTitle(result.run))
      setNameDraft(displayRunTitle(result.run))
    } finally {
      setNameBusy(false)
    }
  }
  const metricCard = (metric: NonNullable<typeof summary>['metrics'][number]) => {
    const resolved = resolveMetricDescriptor(metric, overview?.metric_descriptors ?? [])
    return <ArtifactMetricCell key={metric.metric_id} metric={metric} descriptor={resolved.descriptor} descriptorConflict={resolved.conflict} />
  }

  return <>
    <ResultPageIntro title="运行结果" description="页面只呈现已持久化的 Artifact 2.0，不在读取时重新定位证据或评分。" actions={<Button onClick={() => go('runs')}><ArrowLeft size={16} />返回</Button>} />
    {loadError && <ErrorBanner message={loadError} />}
    <Surface className="run-detail-overview" tone="inspector">
      <header><div><span className="eyebrow">{run.adapter_id} · {formatDate(run.started_at)}</span><h2>{presentedName}</h2></div><div><StatusBadge state={run.status} />{overview?.verification && <span className={overview.verification.valid ? 'integrity integrity--ok' : 'integrity'}><ShieldCheck size={16} />{overview.verification.valid ? 'Artifact 完整' : 'Artifact 校验失败'}</span>}</div></header>
      <details className="run-name-editor"><summary>重命名运行</summary><div><input value={nameDraft} maxLength={160} onChange={(event) => setNameDraft(event.target.value)} /><Button disabled={nameBusy || !nameDraft.trim()} onClick={() => void saveName()}>{nameBusy ? '正在保存…' : '保存名称'}</Button></div></details>
      {overview && <AvailabilityNotice value={overview} />}
      <div className="run-detail-facts">
        <span><small>系统</small><b>{run.system_id}</b></span>
        <span><small>Benchmark Release</small><b>{overview?.manifest?.benchmark_identity.dataset_release_id ?? run.dataset_release_id ?? '—'}</b></span>
        <span><small>创建时间</small><b>{formatDate(run.started_at)}</b></span>
        <span><small>Artifact Contract</small><b>{overview?.artifact_contract_version ?? '—'}</b></span>
      </div>
      {summary && <section className="run-judgment-summary"><div><span>排行榜资格</span><b>{summary.leaderboard_eligibility.eligible ? 'Eligible' : 'Ineligible'}</b><small>{summary.leaderboard_eligibility.reasons.join(' · ') || '所有正式核心指标均可用且 descriptor 一致。'}</small></div><div><span>Case</span><b>{summary.case_count}</b><small>{Object.entries(summary.execution_status_counts).map(([status, count]) => `${status} ${count}`).join(' · ')}</small></div><div><span>核心指标</span><b>{coreMetrics.filter((metric) => metric.status === 'observed').length}/{coreMetrics.length}</b><small>由 Artifact 的 required_metric_ids 定义。</small></div></section>}
      {!!coreMetrics.length && <section className="run-core-metrics"><h3>正式核心指标</h3><div className="metric-grid">{coreMetrics.map(metricCard)}</div></section>}
      <Button variant="primary" onClick={() => go('cases', { run: run.run_id })}>查看 Case <ArrowRight size={16} /></Button>
      <details className="run-technical-details"><summary>Artifact 描述符与诊断指标</summary><div className="run-technical-details__body"><section className="run-technical-identifiers">
        <span><small>Run ID</small><code>{run.run_id}</code></span>
        <span><small>Artifact digest</small><code>{overview?.manifest?.artifact_digest ?? '—'}</code></span>
        <span><small>Runtime profiles</small><b>{overview?.manifest?.runtime_profiles.length ?? 0}</b></span>
        <span><small>Observation profiles</small><b>{overview?.manifest?.observation_profiles.length ?? 0}</b></span>
      </section>{!!diagnosticMetrics.length && <section className="metric-breakdown"><h4>诊断指标</h4><div className="metric-grid">{diagnosticMetrics.map(metricCard)}</div></section>}</div></details>
    </Surface>
  </>
}

export function ArtifactCasesPage({ runs, initialRun, go }: { runs: RunManifest[]; initialRun: string; go: Go }) {
  const [runId, setRunId] = useState(initialRun || runs[0]?.run_id || '')
  const [index, setIndex] = useState<ArtifactCaseIndexViewV2 | null>(null)
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<ArtifactCaseViewV2 | null>(null)
  const [error, setError] = useState('')
  const selectedCase = index?.cases.find((item) => `${item.repetition}:${item.case_id}` === selected)

  useEffect(() => {
    if (initialRun && initialRun !== runId) setRunId(initialRun)
  }, [initialRun, runId])

  useEffect(() => {
    if (!runId) return
    let active = true
    setIndex(null); setDetail(null); setSelected(''); setError('')
    void api.caseIndex(runId).then((value) => {
      if (!active) return
      setIndex(value)
      setSelected(value.cases[0] ? `${value.cases[0].repetition}:${value.cases[0].case_id}` : '')
    }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : String(cause)) })
    return () => { active = false }
  }, [runId])

  useEffect(() => {
    if (!runId || !selectedCase) return
    let active = true
    setDetail(null)
    void api.case(runId, selectedCase.case_id, selectedCase.repetition)
      .then((value) => { if (active) setDetail(value) })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : String(cause)) })
    return () => { active = false }
  }, [runId, selectedCase?.case_id, selectedCase?.repetition])

  const run = runs.find((item) => item.run_id === runId)
  return <>
    <ResultPageIntro title="Case 结果" description="逐题检查持久化的 Unified Trace、证据定位和指标。" actions={runId ? <Button onClick={() => go('run-detail', { run: runId })}><ArrowLeft size={16} />返回运行</Button> : undefined} />
    {error && <ErrorBanner message={error} />}
    {!runId ? <Empty>请选择运行。</Empty> : !index ? <p>正在读取 Artifact…</p> : !index.cases.length ? <Empty>该 Artifact 没有可显示的 Case。</Empty> : <div className="case-layout">
      <aside className="case-index">{index.cases.map((item) => <CaseIndexButton key={`${item.repetition}:${item.case_id}`} item={item} active={selected === `${item.repetition}:${item.case_id}`} onClick={() => setSelected(`${item.repetition}:${item.case_id}`)} />)}</aside>
      <div className="case-detail">{detail ? <ArtifactCaseDetail value={detail} run={run} /> : <p>正在读取 Case Artifact…</p>}</div>
    </div>}
  </>
}

function CaseIndexButton({ item, active, onClick }: { item: RunCaseIndexEntryV2; active: boolean; onClick: () => void }) {
  const judgment = item.answer_judgment.value ?? item.answer_judgment.status
  return <button className={active ? 'active' : ''} onClick={onClick}><span>R{item.repetition}</span><b>{item.question}</b>{item.status === 'completed' ? <StateMark state={judgment} /> : <StateMark state={item.status} />}</button>
}

function ArtifactCaseDetail({ value, run }: { value: ArtifactCaseViewV2; run?: RunManifest }) {
  if (value.availability !== 'available' || !value.artifact_case) {
    return <><AvailabilityNotice value={value} />{value.legacy_case && <Surface><span className="eyebrow">Persisted legacy execution</span><h2>{value.legacy_case.question}</h2><p>{value.legacy_case.answer ?? 'Answer was not persisted.'}</p><small>Metrics, provenance, and failure attribution are legacy unavailable.</small></Surface>}</>
  }
  return <PersistedCaseDetail value={value.artifact_case} run={run} />
}

function PersistedCaseDetail({ value, run }: { value: RunArtifactCaseV2; run?: RunManifest }) {
  const answer = value.gold_answer.canonical
  const trace = value.adapter_result?.trace
  return <>
    <section className="question-block"><span>Repetition {value.repetition} · seed {value.seed}</span><h2>{value.question}</h2></section>
    {value.error && <ErrorBanner message={`${value.error.code}: ${value.error.message}`} />}
    <section className="case-judgments">
      <Surface className="case-judgment-card"><span>答案判断</span><StateMark state={value.answer_judgment.value ?? value.answer_judgment.status} /><p>{value.answer_judgment.reason ?? 'Persisted Artifact judgment.'}</p></Surface>
      <Surface className="case-judgment-card"><span>证据覆盖</span><StateMark state={value.evidence_judgment.value ?? value.evidence_judgment.status} /><p>{value.evidence_judgment.reason ?? 'Persisted Artifact judgment.'}</p></Surface>
      <Surface className="case-judgment-card"><span>Failure attribution</span><StateMark state={value.evaluation.failure?.kind ?? 'none'} /><p>{value.evaluation.failure?.reason ?? 'No proof-gated failure was persisted.'}</p></Surface>
    </section>
    <div className="answer-pair"><Surface tone="inset"><span>Gold answer</span><p>{Array.isArray(answer) ? answer.join(' · ') : answer ?? '—'} {value.gold_answer.unit ?? ''}</p></Surface><Surface><span>Generated answer</span><p>{trace?.answer.content ?? 'UNAVAILABLE'}</p><small>{trace ? `${trace.answer.observation_status} · ${trace.answer.completeness}` : value.trace_validation.status}</small></Surface></div>
    <details className="case-audit-details" open><summary>Unified Trace 与证明</summary><div className="case-audit-details__body">
      {!trace && <p className="historical-metric-note">{value.trace_validation.reason ?? 'Unified Trace is unavailable.'}</p>}
      {trace && <>
        <Surface tone="inset"><span className="eyebrow">Ingestion catalog</span><p>{trace.ingestion_catalog.observation_status} · {trace.ingestion_catalog.completeness} · {trace.ingestion_catalog.items.length} runtime item(s)</p>{trace.ingestion_catalog.reason && <small>{trace.ingestion_catalog.reason}</small>}</Surface>
        <StageObservationPanel title="Candidate" observation={trace.raw_retrieval} />
        <StageObservationPanel title="Ranking" observation={trace.ranked_retrieval} />
        <StageObservationPanel title="Final Context" observation={trace.final_context} />
        <Surface tone="inset"><span className="eyebrow">Transformation lineage</span><p>{trace.transformations.length} transformation record(s) · {trace.mapping_diagnostics.length} mapping diagnostic(s)</p><small>Trace digest {trace.trace_digest}</small></Surface>
      </>}
      <Surface className="case-answer-evidence"><header><div><span className="eyebrow">Canonical Gold Evidence</span><h4>{value.gold_evidence_set.gold_evidence_set_id}</h4><p>这些位置来自 Artifact 中冻结的 Benchmark Snapshot。</p></div></header><div className="case-answer-evidence__items">{value.gold_evidence_set.evidence.map((evidence, index) => <article key={evidence.evidence_id}><span>{String(index + 1).padStart(2, '0')}</span><p>{evidence.quote_anchor ?? evidence.canonical_value ?? evidence.evidence_id}</p></article>)}</div></Surface>
      <section className="metric-breakdown"><h4>Persisted metrics</h4><div className="metric-grid">{value.evaluation.metrics.map((metric) => <ArtifactMetricCell key={metric.metric_id} metric={metric} descriptor={metric.descriptor} />)}</div></section>
      <details><summary>Localization / pipeline records</summary><pre>{JSON.stringify({ localizations: value.evaluation.localizations, pipeline_deltas: value.evaluation.pipeline_deltas, runtime_profile: trace?.runtime_profile, observation_profile: trace?.observation_profile, run_id: run?.run_id }, null, 2)}</pre></details>
    </div></details>
  </>
}

export function ArtifactComparePage({ runs }: { runs: RunManifest[] }) {
  const { t, formatPercent } = useLocale()
  const [selected, setSelected] = useState<string[]>([])
  const [tier, setTier] = useState('task_comparable')
  const [result, setResult] = useState<ComparisonResponse | null>(null)
  const [error, setError] = useState('')
  const compare = async () => { try { setResult(await api.compare(selected, tier)); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } }
  const metricIds = useMemo(() => Array.from(new Set(result?.runs.flatMap((entry) => entry.summary.summary?.metrics.map((metric) => metric.metric_id) ?? []) ?? [])).sort(), [result])
  return <>
    <ResultPageIntro title="比较运行" description="只比较 Artifact 2.0 中 descriptor 完全一致且可用的指标。" />
    <Surface className="compare-controls"><label>比较等级<select value={tier} onChange={(event) => setTier(event.target.value)}><option value="task_comparable">Task comparable</option><option value="strict_controlled">Strict controlled</option><option value="exploratory">Exploratory</option></select></label><Button variant="primary" disabled={selected.length < 2} onClick={() => void compare()}><GitCompareArrows size={16} />验证比较</Button></Surface>
    <div className="run-picker">{runs.map((run) => <label key={run.run_id}><input type="checkbox" checked={selected.includes(run.run_id)} onChange={(event) => setSelected(event.target.checked ? [...selected, run.run_id] : selected.filter((id) => id !== run.run_id))} /><span><b>{displayRunTitle(run)}</b><small>{run.adapter_id} · {run.run_id.slice(0, 8)}</small></span></label>)}</div>
    {error && <ErrorBanner message={error} />}
    {result && <section className="comparison-result"><header className={result.compatible ? 'comparison-contract comparison-contract--ok' : 'comparison-contract'}><div>{result.compatible ? <CheckCircle2 /> : <Archive />}<span><b>{result.compatible ? '比较契约满足' : '比较契约不满足'}</b><small>{result.tier}</small></span></div><strong>{result.may_declare_winner ? '可声明胜者' : '不可声明胜者'}</strong></header>
      {!!result.reasons.length && <ul className="reason-list">{result.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
      <div className="comparison-table"><div className="comparison-row comparison-row--head"><span>Metric contract</span>{result.runs.map((entry) => <span key={entry.run.run_id}>{displayRunTitle(entry.run)}</span>)}</div>{metricIds.map((id) => { const decision = result.metric_decisions.find((item) => item.metric_id === id); return <div className="comparison-row" key={id}><span className="comparison-metric-label"><b>{id}</b><StateMark state={decision?.comparable ? 'comparable' : 'not_comparable'} />{decision && Object.entries(decision.coverage_by_run).map(([runId, coverage]) => <small key={runId}>{runId.slice(0, 8)} · {formatPercent(coverage)}</small>)}{!!decision?.reasons.length && <small>{decision.reasons.join(' · ')}</small>}</span>{result.runs.map((entry) => { const metric = entry.summary.summary?.metrics.find((item) => item.metric_id === id); if (!metric) return <span key={entry.run.run_id}><StateMark state="unavailable" /></span>; const resolved = resolveMetricDescriptor(metric, entry.summary.metric_descriptors); return <span key={entry.run.run_id}><ArtifactMetricCell metric={metric} descriptor={resolved.descriptor} descriptorConflict={resolved.conflict} /></span> })}</div>})}</div>
      <small>{t('page.compare.metricContract')}</small>
    </section>}
  </>
}
