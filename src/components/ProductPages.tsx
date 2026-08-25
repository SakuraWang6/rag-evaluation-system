import { useEffect, useMemo, useRef, useState } from 'react'
import { Archive, CheckCircle2, ChevronRight, CircleAlert, Database, FileUp, Play, ServerCog, ShieldCheck, Sparkles, Upload } from 'lucide-react'
import { api } from '../api'
import type { DatasetDraft, DatasetSummary, EvaluationDraft, ExperimentSpec, ProductSystemSummary, SystemConnectionPayload, SystemProfile, SystemSummary } from '../types'
import { useLocale } from '../i18n/LocaleProvider'
import { ErrorBanner } from '../components'
import { Button, DisclosureSection, SegmentedControl, StatusBadge, Surface } from './primitives'
import { PageHeader } from './AppShell'

export function OverviewPage({ datasets, systems, runs, onNewEvaluation, onAddDataset, onAddSystem }: { datasets: DatasetSummary[]; systems: ProductSystemSummary[]; runs: number; onNewEvaluation: () => void; onAddDataset: () => void; onAddSystem: () => void }) {
  const { t } = useLocale()
  const datasetReady = datasets.length > 0
  const systemReady = systems.length > 0
  const runtimeReady = systems.some((system) => system.connection_test_status === 'passed')
  const ready = datasetReady && systemReady && runtimeReady
  const nextAction = !datasetReady ? onAddDataset : !systemReady || !runtimeReady ? onAddSystem : onNewEvaluation
  const nextLabel = !datasetReady ? t('page.overview.uploadDataset') : !systemReady || !runtimeReady ? t('page.overview.addSystem') : t('page.overview.newEvaluation')
  return <>
    <PageHeader title={t('page.overview.title')} description={t('page.overview.description')} actions={<Button variant="primary" onClick={nextAction}><Sparkles size={16} /> {nextLabel}</Button>} />
    <div className="onboarding-grid">
      <Surface className="onboarding-card" tone="inset"><Database size={18} /><b>{t('page.overview.datasets')}</b><strong>{datasets.length}</strong><small>{t('page.overview.datasetsDetail')}</small></Surface>
      <Surface className="onboarding-card" tone="inset"><ServerCog size={18} /><b>{t('page.overview.systems')}</b><strong>{systems.length}</strong><small>{t('page.overview.systemsDetail')}</small></Surface>
      <Surface className="onboarding-card" tone="inset"><Archive size={18} /><b>{t('page.overview.runs')}</b><strong>{runs}</strong><small>{t('page.overview.runsDetail')}</small></Surface>
    </div>
    <Surface className={ready ? 'onboarding-next onboarding-next--ready' : 'onboarding-next'}>
      {ready ? <CheckCircle2 size={20} /> : <CircleAlert size={20} />}<div><b>{ready ? t('page.overview.readyTitle') : t('page.overview.setupTitle')}</b><p>{ready ? t('page.overview.readyDescription') : t('page.overview.setupDescription')}</p></div><Button onClick={nextAction}>{nextLabel} <ChevronRight size={16} /></Button>
    </Surface>
    <Surface className="setup-checklist" tone="inset">
      <span className={datasetReady ? 'ready' : ''}>{datasetReady ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}<b>{t('page.overview.datasetReady')}</b><small>{datasetReady ? t('page.overview.complete') : t('page.overview.required')}</small></span>
      <span className={systemReady ? 'ready' : ''}>{systemReady ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}<b>{t('page.overview.systemReady')}</b><small>{systemReady ? t('page.overview.complete') : t('page.overview.required')}</small></span>
      <span className={runtimeReady ? 'ready' : ''}>{runtimeReady ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}<b>{t('page.overview.runtimeReady')}</b><small>{runtimeReady ? t('page.overview.complete') : t('page.overview.testRequired')}</small></span>
      <span className={ready ? 'ready' : ''}>{ready ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}<b>{t('page.overview.runReady')}</b><small>{ready ? t('page.overview.complete') : t('page.overview.required')}</small></span>
    </Surface>
    <div className="onboarding-actions"><Button onClick={onAddDataset}>{t('page.overview.uploadDataset')}</Button><Button onClick={onAddSystem}>{t('page.overview.addSystem')}</Button><Button variant="primary" onClick={onNewEvaluation} disabled={!ready}>{t('page.overview.newEvaluation')}</Button></div>
  </>
}

export function ProductDatasetsPage({ datasets, refresh }: { datasets: DatasetSummary[]; refresh: () => Promise<void> }) {
  const { t } = useLocale()
  const [uploading, setUploading] = useState(false)
  const [localPath, setLocalPath] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const upload = async (file: File | undefined) => {
    if (!file) return
    setUploading(true); setError('')
    try { const value = await api.uploadDataset(file); setMessage(t('product.datasets.uploaded', { id: value.bundle_id.slice(0, 12) })); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setUploading(false) }
  }
  const registerLocal = async () => {
    try { const value = await api.registerLocalDataset(localPath); setMessage(t('product.datasets.localRegistered', { id: value.bundle_id.slice(0, 12) })); setLocalPath(''); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  return <>
    <PageHeader title={t('product.datasets.title')} description={t('product.datasets.description')} />
    <div className="resource-actions">
      <label className="upload-tile"><Upload size={19} /><span><b>{t('product.datasets.uploadTitle')}</b><small>{t('product.datasets.uploadDescription')}</small></span><input type="file" accept=".zip,application/zip" onChange={(event) => void upload(event.target.files?.[0])} disabled={uploading} /><em>{uploading ? t('product.datasets.uploading') : t('product.datasets.chooseZip')}</em></label>
      <DatasetAuthoring onSealed={refresh} />
    </div>
    <DisclosureSection title={t('product.datasets.advancedLocal')}><div className="inline-form"><label><span>{t('product.datasets.localPath')}</span><input value={localPath} onChange={(event) => setLocalPath(event.target.value)} placeholder={t('product.datasets.localPathPlaceholder')} /></label><Button disabled={!localPath} onClick={() => void registerLocal()}>{t('product.datasets.registerLocal')}</Button></div><p className="field-note">{t('product.datasets.localPathNote')}</p></DisclosureSection>
    {message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}{error && <ErrorBanner message={error} />}
    <section className="resource-list"><header><h3>{t('product.datasets.available')}</h3><small>{t('product.datasets.sealedNote')}</small></header>{datasets.map((dataset) => <article key={dataset.bundle_id}><div><b>{dataset.name}</b><small>{t('common.version', { version: dataset.version })} · {t('product.datasets.caseCount', { count: dataset.cases })}</small></div><code>{dataset.bundle_id}</code><StatusBadge state="immutable" /></article>)}</section>
  </>
}

function DatasetAuthoring({ onSealed }: { onSealed: () => Promise<void> }) {
  const { t } = useLocale()
  const sourceRef = useRef<HTMLTextAreaElement>(null)
  const [draftId, setDraftId] = useState('')
  const [name, setName] = useState('')
  const [version, setVersion] = useState('1.0.0')
  const [documentId, setDocumentId] = useState('document-1')
  const [filename, setFilename] = useState('source.md')
  const [content, setContent] = useState('')
  const [question, setQuestion] = useState('')
  const [gold, setGold] = useState('')
  const [selection, setSelection] = useState({ start: 0, end: 0 })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const payload = (): DatasetDraft => ({
    ...(draftId ? { draft_id: draftId } : {}), name, version,
    documents: [{ document_id: documentId, filename, content }],
    cases: question && gold && selection.end > selection.start ? [{ case_id: 'case-1', question, gold_answer: gold, document_id: documentId, span_start: selection.start, span_end: selection.end }] : [],
  })
  const save = async () => {
    try { const value = await api.saveDatasetDraft(payload()); setDraftId(value.draft_id || ''); setMessage(t('product.datasets.draftSaved')); setError('') }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  const validate = async () => { try { const value = await api.saveDatasetDraft(payload()); setDraftId(value.draft_id || ''); await api.validateDatasetDraft(value.draft_id || ''); setMessage(t('product.datasets.validated')); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } }
  const seal = async () => { try { const value = await api.saveDatasetDraft(payload()); const sealed = await api.sealDatasetDraft(value.draft_id || ''); setDraftId(value.draft_id || ''); setMessage(t('product.datasets.sealed', { id: sealed.bundle_id.slice(0, 12) })); setError(''); await onSealed() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } }
  const captureSelection = () => { const source = sourceRef.current; if (source) setSelection({ start: source.selectionStart, end: source.selectionEnd }) }
  return <DisclosureSection title={t('product.datasets.createTitle')} className="dataset-authoring"><p className="field-note">{t('product.datasets.createDescription')}</p><div className="authoring-grid"><label><span>{t('product.datasets.name')}</span><input value={name} onChange={(event) => setName(event.target.value)} /></label><label><span>{t('product.datasets.version')}</span><input value={version} onChange={(event) => setVersion(event.target.value)} /></label><label><span>{t('product.datasets.documentId')}</span><input value={documentId} onChange={(event) => setDocumentId(event.target.value)} /></label><label><span>{t('product.datasets.filename')}</span><input value={filename} onChange={(event) => setFilename(event.target.value)} /></label></div><label><span>{t('product.datasets.source')}</span><textarea ref={sourceRef} value={content} onChange={(event) => setContent(event.target.value)} onSelect={captureSelection} placeholder={t('product.datasets.sourcePlaceholder')} /></label><div className="selection-note"><ShieldCheck size={15} />{t('product.datasets.selection', { start: selection.start, end: selection.end })}</div><div className="authoring-grid"><label><span>{t('product.datasets.question')}</span><input value={question} onChange={(event) => setQuestion(event.target.value)} /></label><label><span>{t('product.datasets.goldAnswer')}</span><input value={gold} onChange={(event) => setGold(event.target.value)} /></label></div><div className="authoring-actions"><Button disabled={!name || !content} onClick={() => void save()}>{t('product.datasets.saveDraft')}</Button><Button disabled={!name || !content} onClick={() => void validate()}>{t('product.datasets.validate')}</Button><Button variant="primary" disabled={!name || !content || !question || !gold || selection.end <= selection.start} onClick={() => void seal()}>{t('product.datasets.seal')}</Button></div>{message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}{error && <ErrorBanner message={error} />}</DisclosureSection>
}

export function ProductSystemsPage({ legacy }: { legacy: SystemSummary[] }) {
  const { t } = useLocale()
  const [profiles, setProfiles] = useState<SystemProfile[]>([])
  const [systems, setSystems] = useState<ProductSystemSummary[]>([])
  const [selected, setSelected] = useState('lightrag@1.0.1')
  const [displayName, setDisplayName] = useState('LightRAG')
  const [provider, setProvider] = useState<'local' | 'docker'>('local')
  const [secretKey, setSecretKey] = useState('')
  const [secretValue, setSecretValue] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const refresh = async () => { try { const [nextProfiles, nextSystems] = await Promise.all([api.profiles(), api.productSystems()]); setProfiles(nextProfiles); setSystems(nextSystems) } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } }
  useEffect(() => { void refresh() }, [])
  const profile = profiles.find((item) => `${item.profile_id}@${item.profile_version}` === selected)
  useEffect(() => { if (profile) setDisplayName(profile.display_name) }, [profile?.profile_id, profile?.profile_version])
  const save = async () => {
    if (!profile) return
    const connection: SystemConnectionPayload = { system_id: profile.system_id, display_name: displayName || profile.display_name, profile_id: profile.profile_id, profile_version: profile.profile_version, execution_provider: provider, logical_endpoint_ref: profile.default_logical_endpoint }
    try { await api.saveProductSystem(connection, secretKey && secretValue ? { [secretKey]: secretValue } : {}); setSecretValue(''); setMessage(t('product.systems.saved')); setError(''); await refresh() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  const test = async () => { if (!profile) return; try { const value = await api.testProductSystem(profile.system_id); setMessage(t('product.systems.tested', { adapter: value.adapter_id })); setError(''); await refresh() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); await refresh() } }
  return <><PageHeader title={t('product.systems.title')} description={t('product.systems.description')} /><div className="system-setup"><Surface tone="inset"><header><span><ServerCog size={18} />{t('product.systems.add')}</span><small>{t('product.systems.basic')}</small></header><div className="authoring-grid"><label><span>{t('product.systems.type')}</span><select value={selected} onChange={(event) => setSelected(event.target.value)}>{profiles.map((item) => <option value={`${item.profile_id}@${item.profile_version}`} key={`${item.profile_id}@${item.profile_version}`}>{item.display_name} · {item.profile_version}</option>)}</select></label><label><span>{t('product.systems.name')}</span><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label><label><span>{t('product.systems.execution')}</span><select value={provider} onChange={(event) => setProvider(event.target.value as 'local' | 'docker')}><option value="local">{t('product.systems.local')}</option><option value="docker">{t('product.systems.docker')}</option></select></label></div>{profile && <p className="field-note">{t('product.systems.profileVersion', { version: profile.profile_version })} · {t('product.systems.defaultsNote')}</p>}<div className="authoring-actions"><Button onClick={() => void save()} disabled={!profile}>{t('product.systems.save')}</Button><Button variant="primary" onClick={() => void test()} disabled={!profile}>{t('product.systems.test')}</Button></div></Surface><Surface><header><span>{t('product.systems.configured')}</span><small>{t('product.systems.safeState')}</small></header><div className="resource-list resource-list--compact">{systems.map((item) => <article key={item.system_id}><div><b>{item.display_name}</b><small>{item.profile_id}@{item.profile_version} · {item.execution_provider}</small></div><StatusBadge state={item.connection_test_status === 'passed' ? 'ok' : item.connection_test_status === 'failed' ? 'error' : 'needs_review'} /></article>)}</div></Surface></div>{message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}{error && <ErrorBanner message={error} />}<DisclosureSection title={t('product.systems.credentials')}><p className="field-note">{t('product.systems.credentialsNote')}</p><div className="inline-form"><label><span>{t('product.systems.credentialKey')}</span><input value={secretKey} onChange={(event) => setSecretKey(event.target.value)} /></label><label><span>{t('product.systems.credentialValue')}</span><input type="password" value={secretValue} onChange={(event) => setSecretValue(event.target.value)} autoComplete="new-password" /></label></div></DisclosureSection><DisclosureSection title={t('product.systems.advancedLegacy')}><p className="field-note">{t('product.systems.advancedLegacyNote')}</p>{legacy.map((item) => <code className="legacy-system" key={item.system_id}>{item.system_id} · {item.adapter_id}</code>) || <p className="field-note">{t('product.systems.noLegacy')}</p>}</DisclosureSection></>
}

export function NewEvaluationPage({ datasets, onQueued }: { datasets: DatasetSummary[]; onQueued: () => void }) {
  const { t } = useLocale()
  const [profiles, setProfiles] = useState<SystemProfile[]>([])
  const [systems, setSystems] = useState<ProductSystemSummary[]>([])
  const [bundleId, setBundleId] = useState('')
  const [systemId, setSystemId] = useState('')
  const [model, setModel] = useState('')
  const [embedding, setEmbedding] = useState('')
  const [queryMode, setQueryMode] = useState('')
  const [mode, setMode] = useState<'basic' | 'advanced'>('basic')
  const [candidateK, setCandidateK] = useState('')
  const [contextK, setContextK] = useState('')
  const [tokenBudget, setTokenBudget] = useState('')
  const [seed, setSeed] = useState('0')
  const [repetitions, setRepetitions] = useState('1')
  const [draft, setDraft] = useState<EvaluationDraft | null>(null)
  const [preview, setPreview] = useState<ExperimentSpec | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { void Promise.all([api.profiles(), api.productSystems()]).then(([nextProfiles, nextSystems]) => { setProfiles(nextProfiles); setSystems(nextSystems); if (!systemId && nextSystems[0]) setSystemId(nextSystems[0].system_id) }).catch((cause) => setError(cause instanceof Error ? cause.message : String(cause))) }, [])
  const system = systems.find((item) => item.system_id === systemId)
  const profile = profiles.find((item) => item.profile_id === system?.profile_id && item.profile_version === system?.profile_version)
  const buildDraft = (): EvaluationDraft | null => {
    if (!bundleId || !system || !profile) return null
    if (!model.trim() || !embedding.trim()) throw new Error(t('product.wizard.modelsRequired'))
    const parseInteger = (value: string, minimum: number, label: string): number | undefined => {
      if (!value.trim()) return undefined
      const parsed = Number(value)
      if (!Number.isInteger(parsed) || parsed < minimum) throw new Error(t('product.wizard.invalidInteger', { label, minimum }))
      return parsed
    }
    const candidate = mode === 'advanced' ? parseInteger(candidateK, 1, t('product.wizard.candidateK')) : undefined
    const context = mode === 'advanced' ? parseInteger(contextK, 1, t('product.wizard.contextK')) : undefined
    const tokens = mode === 'advanced' ? parseInteger(tokenBudget, 1, t('product.wizard.tokenBudget')) : undefined
    const selectedSeed = mode === 'advanced' ? parseInteger(seed, 0, t('product.wizard.seed')) ?? 0 : 0
    const selectedRepetitions = mode === 'advanced' ? parseInteger(repetitions, 1, t('product.wizard.repetitions')) ?? 1 : 1
    const adapterOverrides: Record<string, unknown> = { model: { llm_model: model.trim(), embedding_model: embedding.trim() }, ...(queryMode.trim() ? { query_mode: queryMode.trim() } : {}), ...(candidate === undefined ? {} : { retrieval_candidate_k: candidate }), ...(context === undefined ? {} : { final_context_k: context }), ...(tokens === undefined ? {} : { max_context_tokens: tokens }) }
    const queryOverrides: Record<string, unknown> = { ...(candidate === undefined ? {} : { retrieval_candidate_k: candidate }), ...(context === undefined ? {} : { final_context_k: context }), ...(tokens === undefined ? {} : { max_context_tokens: tokens }) }
    return { mode, bundle_id: bundleId, system_id: system.system_id, profile_id: profile.profile_id, profile_version: profile.profile_version, display_name: `${profile.profile_id}-evaluation`, adapter_overrides: adapterOverrides, query_overrides: queryOverrides, metric_overrides: {}, case_ids: null, seed: selectedSeed, repetitions: selectedRepetitions, formal: false }
  }
  const previewSpec = async () => { try { const value = buildDraft(); if (!value) return; const saved = await api.saveEvaluationDraft(value); setDraft(saved); const result = await api.previewEvaluationDraft(saved.draft_id || ''); setPreview(result); setMessage(t('product.wizard.ready')); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); setPreview(null); setDraft(null) } }
  const run = async () => { if (!draft?.draft_id) return; try { await api.finalizeEvaluationDraft(draft.draft_id); setMessage(t('product.wizard.queued')); setError(''); onQueued() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } }
  return <><PageHeader title={t('product.wizard.title')} description={t('product.wizard.description')} /><ol className="wizard-steps"><li className={bundleId ? 'done' : ''}>{t('product.wizard.stepDataset')}</li><li className={system ? 'done' : ''}>{t('product.wizard.stepSystem')}</li><li className={preview ? 'done' : ''}>{t('product.wizard.stepReview')}</li><li>{t('product.wizard.stepRun')}</li></ol><Surface className="wizard-form"><div className="authoring-actions"><span className="field-note">{t('product.wizard.mode')}</span><SegmentedControl label={t('product.wizard.mode')} value={mode} onChange={setMode} options={[{ value: 'basic', label: t('product.wizard.basicMode') }, { value: 'advanced', label: t('product.wizard.advancedMode') }]} /></div><div className="authoring-grid"><label><span>{t('product.wizard.dataset')}</span><select value={bundleId} onChange={(event) => { setBundleId(event.target.value); setPreview(null) }}><option value="">{t('product.wizard.selectDataset')}</option>{datasets.map((item) => <option value={item.bundle_id} key={item.bundle_id}>{item.name} · {item.version}</option>)}</select></label><label><span>{t('product.wizard.system')}</span><select value={systemId} onChange={(event) => { setSystemId(event.target.value); setPreview(null) }}><option value="">{t('product.wizard.selectSystem')}</option>{systems.map((item) => <option value={item.system_id} key={item.system_id}>{item.display_name}</option>)}</select></label><label><span>{t('product.wizard.model')}</span><input value={model} onChange={(event) => { setModel(event.target.value); setPreview(null) }} placeholder={t('product.wizard.modelPlaceholder')} /></label><label><span>{t('product.wizard.embedding')}</span><input value={embedding} onChange={(event) => { setEmbedding(event.target.value); setPreview(null) }} placeholder={t('product.wizard.embeddingPlaceholder')} /></label><label><span>{t('product.wizard.queryMode')}</span><input value={queryMode} onChange={(event) => { setQueryMode(event.target.value); setPreview(null) }} placeholder={t('product.wizard.queryModePlaceholder')} /></label></div>{mode === 'advanced' && <DisclosureSection title={t('product.wizard.advancedConfig')} open><div className="authoring-grid"><label><span>{t('product.wizard.candidateK')}</span><input inputMode="numeric" value={candidateK} onChange={(event) => { setCandidateK(event.target.value); setPreview(null) }} /></label><label><span>{t('product.wizard.contextK')}</span><input inputMode="numeric" value={contextK} onChange={(event) => { setContextK(event.target.value); setPreview(null) }} /></label><label><span>{t('product.wizard.tokenBudget')}</span><input inputMode="numeric" value={tokenBudget} onChange={(event) => { setTokenBudget(event.target.value); setPreview(null) }} /></label><label><span>{t('product.wizard.seed')}</span><input inputMode="numeric" value={seed} onChange={(event) => { setSeed(event.target.value); setPreview(null) }} /></label><label><span>{t('product.wizard.repetitions')}</span><input inputMode="numeric" value={repetitions} onChange={(event) => { setRepetitions(event.target.value); setPreview(null) }} /></label></div></DisclosureSection>}<p className="field-note">{profile ? t('product.wizard.profileDefaults', { profile: profile.profile_id, version: profile.profile_version }) : t('product.wizard.noProfile')}</p><div className="authoring-actions"><Button onClick={() => void previewSpec()} disabled={!bundleId || !system || !model.trim() || !embedding.trim()}>{t('product.wizard.review')}</Button><Button variant="primary" onClick={() => void run()} disabled={!preview}>{t('product.wizard.run')} <Play size={16} /></Button></div></Surface>{message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}{error && <ErrorBanner message={error} />}{preview && <DisclosureSection title={t('product.wizard.canonicalSpec')} open><pre className="canonical-spec">{JSON.stringify(preview, null, 2)}</pre></DisclosureSection>}</>
}
