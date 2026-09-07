import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Archive, ArrowLeft, BrainCircuit, CheckCircle2, ChevronRight, CircleAlert, Database, Eye, ExternalLink, FileText, FileUp, Gauge, ListTree, Play, Plus, RefreshCw, ServerCog, ShieldCheck, Sparkles, Trash2, Upload, WandSparkles } from 'lucide-react'
import { api } from '../api'
import { generationJobProgress, latestResumableAuthoringDataset, visibleDiscoveryJob, visibleGenerationJob } from '../authoringGeneration'
import type { AuthoringCandidate, AuthoringDataset, AuthoringDiscoveryJob, AuthoringGenerationJob, AuthoringTarget, AuthoringTargetPreview, DatasetDraft, DatasetSummary, EvaluationDraft, ExperimentSpec, FormalCaseContent, FormalCaseListItem, FormalDatasetsResponse, FormalDocumentView, FormalReleaseCaseIndexResponse, LLMConfigRevision, LLMProviderConfig, LLMProviderKind, LLMStage, LLMStageBinding, ProductSystemSummary, SystemConnectionPayload, SystemProfile, SystemSummary } from '../types'
import { useLocale } from '../i18n/LocaleProvider'
import type { MessageKey } from '../i18n'
import { ErrorBanner } from '../components'
import { Button, DisclosureSection, Modal, SegmentedControl, StatusBadge, Surface } from './primitives'
import { PageHeader } from './AppShell'

// Let React paint the reader shell before waiting on a potentially large
// source-faithful document projection.  The request itself is already in
// flight, so this costs no document-load time while keeping the click alive.
function yieldToBrowserPaint(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined') { resolve(); return }
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(() => resolve())
      return
    }
    window.setTimeout(resolve, 0)
  })
}

export function OverviewPage({ datasets, formalDatasets, systems, runs, onNewEvaluation, onAddDataset, onAddSystem }: { datasets: DatasetSummary[]; formalDatasets: FormalDatasetsResponse; systems: ProductSystemSummary[]; runs: number; onNewEvaluation: () => void; onAddDataset: () => void; onAddSystem: () => void }) {
  const { t } = useLocale()
  // A formal release is a usable dataset. Bundle 3.0 is only its runtime
  // projection, so it must not make the overview look configured by itself.
  const datasetCount = datasets.length + formalDatasets.releases.length
  const datasetReady = datasetCount > 0
  const systemReady = systems.length > 0
  const runtimeReady = systems.some((system) => system.connection_test_status === 'passed')
  const ready = datasetReady && systemReady && runtimeReady
  const nextAction = !datasetReady ? onAddDataset : !systemReady || !runtimeReady ? onAddSystem : onNewEvaluation
  const nextLabel = !datasetReady ? t('page.overview.uploadDataset') : !systemReady || !runtimeReady ? t('page.overview.addSystem') : t('page.overview.newEvaluation')
  return <>
    <PageHeader title={t('page.overview.title')} actions={<Button variant="primary" onClick={nextAction}><Sparkles size={16} /> {nextLabel}</Button>} />
    <div className="onboarding-grid">
      <Surface className="onboarding-card" tone="inset"><Database size={18} /><b>{t('page.overview.datasets')}</b><strong>{datasetCount}</strong></Surface>
      <Surface className="onboarding-card" tone="inset"><ServerCog size={18} /><b>{t('page.overview.systems')}</b><strong>{systems.length}</strong></Surface>
      <Surface className="onboarding-card" tone="inset"><Archive size={18} /><b>{t('page.overview.runs')}</b><strong>{runs}</strong></Surface>
    </div>
    <Surface className={ready ? 'onboarding-next onboarding-next--ready' : 'onboarding-next'}>
      {ready ? <CheckCircle2 size={20} /> : <CircleAlert size={20} />}<div><b>{ready ? t('page.overview.readyTitle') : t('page.overview.setupTitle')}</b></div><Button onClick={nextAction}>{nextLabel} <ChevronRight size={16} /></Button>
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

type FormalReleaseSummary = FormalDatasetsResponse['releases'][number]
type FormalEvidence = FormalCaseContent['gold']['evidence'][number]
type AuthoringWorkspaceSnapshot = {
  targets: AuthoringTarget[]
  candidates: AuthoringCandidate[]
}

// Closing a modal unmounts its contents. Keep the already fetched review
// workspace in this page-session cache so reopening a DOCX authoring modal
// does not briefly look like an empty, new dataset while its API requests
// complete. The server remains the source of truth and refreshes it below.
const authoringWorkspaceSnapshots = new Map<string, AuthoringWorkspaceSnapshot>()

// Formal validation keeps reviewer approval separate from the actor that
// freezes a release.  The direct local flow has no release-manager field, so
// use a stable local release-manager identity rather than reusing the
// reviewer value and turning every approved Case/Gold into a self-approval
// after it is frozen.
const localReleaseManager = 'local-release-manager'

export function ProductDatasetsPage({ datasets, formalDatasets, refresh }: { datasets: DatasetSummary[]; formalDatasets: FormalDatasetsResponse; refresh: () => Promise<void> }) {
  const { t } = useLocale()
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [authoringDatasets, setAuthoringDatasets] = useState<AuthoringDataset[]>([])
  const [creationOpen, setCreationOpen] = useState(false)
  const [creationMode, setCreationMode] = useState<DatasetCreationMode | null>(null)
  const [resumedAuthoringDataset, setResumedAuthoringDataset] = useState<AuthoringDataset | null>(null)
  const [deletingReleaseId, setDeletingReleaseId] = useState('')
  const [selectedRelease, setSelectedRelease] = useState<FormalReleaseSummary | null>(null)
  const [formalCaseIndex, setFormalCaseIndex] = useState<FormalReleaseCaseIndexResponse | null>(null)
  const [formalCaseIndexCache, setFormalCaseIndexCache] = useState<Record<string, FormalReleaseCaseIndexResponse>>({})
  const [formalCaseCache, setFormalCaseCache] = useState<Record<string, FormalCaseContent>>({})
  const [selectedFormalCase, setSelectedFormalCase] = useState<FormalCaseContent | null>(null)
  const [indexLoading, setIndexLoading] = useState(false)
  const [caseLoading, setCaseLoading] = useState(false)
  const [formalError, setFormalError] = useState('')
  const [formalCaseError, setFormalCaseError] = useState('')
  const formalCaseIndexRequests = useRef<Record<string, Promise<FormalReleaseCaseIndexResponse>>>({})
  const formalCaseRequests = useRef<Record<string, Promise<FormalCaseContent>>>({})
  const formalReleaseRequestToken = useRef(0)
  const formalCaseRequestToken = useRef(0)
  const [documentView, setDocumentView] = useState<FormalDocumentView | null>(null)
  const [formalDocumentCache, setFormalDocumentCache] = useState<Record<string, FormalDocumentView>>({})
  const formalDocumentRequests = useRef<Record<string, Promise<FormalDocumentView>>>({})
  const formalDocumentRequestToken = useRef(0)
  const [documentEvidenceIds, setDocumentEvidenceIds] = useState<string[]>([])
  const [documentCase, setDocumentCase] = useState<FormalCaseContent | null>(null)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [documentError, setDocumentError] = useState('')
  const refreshAuthoring = async () => {
    try {
      setAuthoringDatasets(await api.authoringDatasets())
      setError('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }
  useEffect(() => { void refreshAuthoring() }, [])
  useEffect(() => {
    if (!message) return
    const timer = window.setTimeout(() => setMessage(''), 3600)
    return () => window.clearTimeout(timer)
  }, [message])
  const refreshAll = async () => {
    await Promise.all([refresh(), refreshAuthoring()])
  }
  const closeCreation = () => {
    setCreationOpen(false)
    setCreationMode(null)
    setResumedAuthoringDataset(null)
  }
  const openCreation = (mode: DatasetCreationMode) => {
    setCreationOpen(true)
    // The persisted authoring state is an implementation detail. If someone
    // closes the creation flow before publishing, opening DOCX again quietly
    // resumes the latest unfinished document instead of showing a workspace
    // catalogue or making them start over.
    const latestUnpublishedDocument = mode === 'docx'
      ? latestResumableAuthoringDataset(authoringDatasets)
      : null
    setResumedAuthoringDataset(latestUnpublishedDocument)
    setCreationMode(mode)
  }
  const upload = async (file: File | undefined) => {
    if (!file) return
    setUploading(true); setError('')
    try { const value = await api.uploadDataset(file); setMessage(t('product.datasets.uploaded', { id: value.bundle_id.slice(0, 12) })); await refreshAll(); closeCreation() }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setUploading(false) }
  }
  const deleteFormalRelease = async (release: FormalReleaseSummary) => {
    if (!window.confirm(t('product.datasets.formalDeleteConfirm', { version: release.version }))) return
    setDeletingReleaseId(release.release_id); setError('')
    try {
      await api.deleteFormalDataset(release.release_id)
      setMessage(t('product.datasets.formalDeleted'))
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setDeletingReleaseId('')
    }
  }
  const formalCaseKey = (releaseId: string, caseId: string) => `${releaseId}:${caseId}`
  const fetchFormalCaseIndex = (releaseId: string): Promise<FormalReleaseCaseIndexResponse> => {
    const cached = formalCaseIndexCache[releaseId]
    if (cached) return Promise.resolve(cached)
    const inFlight = formalCaseIndexRequests.current[releaseId]
    if (inFlight) return inFlight
    const request = api.formalDatasetCaseIndex(releaseId)
      .then((index) => {
        setFormalCaseIndexCache((current) => current[releaseId] ? current : { ...current, [releaseId]: index })
        return index
      })
      .finally(() => { delete formalCaseIndexRequests.current[releaseId] })
    formalCaseIndexRequests.current[releaseId] = request
    return request
  }
  const fetchFormalCase = (releaseId: string, caseId: string): Promise<FormalCaseContent> => {
    const key = formalCaseKey(releaseId, caseId)
    const cached = formalCaseCache[key]
    if (cached) return Promise.resolve(cached)
    const inFlight = formalCaseRequests.current[key]
    if (inFlight) return inFlight
    const request = api.formalDatasetCase(releaseId, caseId)
      .then((item) => {
        setFormalCaseCache((current) => current[key] ? current : { ...current, [key]: item })
        return item
      })
      .finally(() => { delete formalCaseRequests.current[key] })
    formalCaseRequests.current[key] = request
    return request
  }
  const fetchFormalDocument = (releaseId: string): Promise<FormalDocumentView> => {
    const cached = formalDocumentCache[releaseId]
    if (cached) return Promise.resolve(cached)
    const inFlight = formalDocumentRequests.current[releaseId]
    if (inFlight) return inFlight
    const request = api.formalDatasetDocument(releaseId)
      .then((view) => {
        setFormalDocumentCache((current) => current[releaseId] ? current : { ...current, [releaseId]: view })
        return view
      })
      .finally(() => { delete formalDocumentRequests.current[releaseId] })
    formalDocumentRequests.current[releaseId] = request
    return request
  }
  const selectFormalCase = async (releaseId: string, item: FormalCaseListItem) => {
    const token = formalCaseRequestToken.current + 1
    formalCaseRequestToken.current = token
    const cached = formalCaseCache[formalCaseKey(releaseId, item.case_id)]
    setSelectedFormalCase(cached ?? null)
    setFormalCaseError('')
    if (cached) {
      setCaseLoading(false)
      return
    }
    setCaseLoading(true)
    await yieldToBrowserPaint()
    try {
      const detail = await fetchFormalCase(releaseId, item.case_id)
      if (formalCaseRequestToken.current === token) setSelectedFormalCase(detail)
    } catch (cause) {
      if (formalCaseRequestToken.current === token) setFormalCaseError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      if (formalCaseRequestToken.current === token) setCaseLoading(false)
    }
  }
  const openFormalRelease = async (release: FormalReleaseSummary) => {
    const token = formalReleaseRequestToken.current + 1
    formalReleaseRequestToken.current = token
    formalCaseRequestToken.current += 1
    setSelectedRelease(release)
    const cached = formalCaseIndexCache[release.release_id]
    setFormalCaseIndex(cached ?? null)
    setSelectedFormalCase(null)
    setFormalError('')
    setFormalCaseError('')
    setIndexLoading(false)
    setCaseLoading(false)
    setDocumentView(null)
    setDocumentCase(null)
    setDocumentError('')
    const openFirstCase = (index: FormalReleaseCaseIndexResponse) => {
      const first = index.cases[0]
      if (first) void selectFormalCase(release.release_id, first)
    }
    if (cached) {
      openFirstCase(cached)
      return
    }
    setIndexLoading(true)
    await yieldToBrowserPaint()
    try {
      const index = await fetchFormalCaseIndex(release.release_id)
      if (formalReleaseRequestToken.current !== token) return
      setFormalCaseIndex(index)
      openFirstCase(index)
    } catch (cause) {
      if (formalReleaseRequestToken.current === token) setFormalError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      if (formalReleaseRequestToken.current === token) setIndexLoading(false)
    }
  }
  const closeFormalRelease = () => {
    formalReleaseRequestToken.current += 1
    formalCaseRequestToken.current += 1
    formalDocumentRequestToken.current += 1
    setSelectedRelease(null)
    setFormalCaseIndex(null)
    setSelectedFormalCase(null)
    setFormalError('')
    setFormalCaseError('')
    setIndexLoading(false)
    setCaseLoading(false)
    setDocumentView(null)
    setDocumentCase(null)
    setDocumentLoading(false)
    setDocumentError('')
  }
  const openFormalDocument = async (item: FormalCaseContent) => {
    if (!selectedRelease) return
    // Near-miss and conflicting passages are deliberately retained in the
    // formal Gold record for evaluation.  They are not answer evidence and
    // must never be highlighted as if they supported the answer.
    const evidenceIds = item.gold.evidence
      .filter((evidence) => evidence.canonical && evidence.reachable && !['near_miss', 'conflicting'].includes(evidence.role))
      .map((evidence) => evidence.canonical_object_id)
    setDocumentCase(item)
    setDocumentEvidenceIds(evidenceIds)
    const cached = formalDocumentCache[selectedRelease.release_id]
    setDocumentView(cached ?? null)
    setDocumentError('')
    if (!cached) {
      const token = formalDocumentRequestToken.current + 1
      formalDocumentRequestToken.current = token
      const request = fetchFormalDocument(selectedRelease.release_id)
      setDocumentLoading(true)
      await yieldToBrowserPaint()
      try {
        const view = await request
        if (formalDocumentRequestToken.current === token) setDocumentView(view)
      } catch (cause) {
        if (formalDocumentRequestToken.current === token) setDocumentError(cause instanceof Error ? cause.message : String(cause))
      } finally {
        if (formalDocumentRequestToken.current === token) setDocumentLoading(false)
      }
    }
  }
  const backToQuestions = () => {
    formalDocumentRequestToken.current += 1
    setDocumentView(null)
    setDocumentCase(null)
    setDocumentEvidenceIds([])
    setDocumentLoading(false)
    setDocumentError('')
  }
  // Product users work with published datasets. The persisted authoring
  // record remains available only to recover an interrupted creation flow.
  const visibleCatalogCount = datasets.length + formalDatasets.releases.length
  return <>
    <PageHeader title={t('product.datasets.title')} />
    {message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}
    {error && <ErrorBanner message={error} />}
    <section className="dataset-quick-create" aria-label={t('product.datasets.createButton')}>
      <button type="button" className="creation-method-card" onClick={() => openCreation('zip')}><FileUp size={20} /><span><b>{t('product.datasets.uploadTitle')}</b></span><ChevronRight size={16} /></button>
      <button type="button" className="creation-method-card" onClick={() => openCreation('text')}><FileText size={20} /><span><b>{t('product.datasets.textTitle')}</b></span><ChevronRight size={16} /></button>
      <button type="button" className="creation-method-card" onClick={() => openCreation('docx')}><WandSparkles size={20} /><span><b>{t('product.authoring.title')}</b></span><ChevronRight size={16} /></button>
    </section>
    <section className="dataset-catalog" aria-label={t('product.datasets.available')}>
      {datasets.length > 0 && <div className="dataset-catalog__group">
        <div className="dataset-catalog__group-title">{t('product.datasets.importedTitle')}</div>
        {datasets.map((dataset) => <article key={dataset.bundle_id} className="dataset-row dataset-row--muted">
          <div className="dataset-row__identity">
            <span className="dataset-row__icon"><Archive size={16} /></span>
            <div><b>{dataset.name}</b><small>{t('common.version', { version: dataset.version })} · {t('product.datasets.caseCount', { count: dataset.cases })}</small></div>
          </div>
        </article>)}
      </div>}
      {formalDatasets.releases.length > 0 && <div className="dataset-catalog__group">
        <div className="dataset-catalog__group-title">{t('product.datasets.formalTitle')}</div>
        {formalDatasets.releases.map((release) => <article key={release.release_id} className="dataset-row dataset-row--published">
          <div className="dataset-row__identity">
            <span className="dataset-row__icon"><ShieldCheck size={16} /></span>
            <div><b>{release.name}</b><small>{t('product.datasets.formalDatasetLabel')} · {t('product.datasets.releaseVersion', { version: release.version })} · {t('product.datasets.releaseSummary', { cases: release.case_count, answers: release.gold_count })}</small></div>
          </div>
          <div className="dataset-row__actions">
            <Button variant="quiet" onClick={() => void openFormalRelease(release)}>{t('product.datasets.viewDetails')}</Button>
            <Button variant="quiet" className="button--danger" onClick={() => void deleteFormalRelease(release)} disabled={deletingReleaseId === release.release_id}><Trash2 size={14} />{t('product.datasets.delete')}</Button>
          </div>
        </article>)}
      </div>}
      {visibleCatalogCount === 0 && <p className="dataset-catalog__empty">{t('product.datasets.empty')}</p>}
    </section>
    {creationOpen && creationMode !== null && <Modal
      className="dataset-creation-modal"
      title={creationMode === 'zip' ? t('product.datasets.uploadTitle') : creationMode === 'text' ? t('product.datasets.textTitle') : resumedAuthoringDataset?.source.original_filename || t('product.authoring.title')}
      closeLabel={t('product.datasets.closeCreation')}
      onClose={closeCreation}
    >
      <div className="creation-flow">
        {creationMode === 'zip' && <section className="creation-panel">
          <div className="creation-panel__heading"><FileUp size={20} /><h3>{t('product.datasets.uploadTitle')}</h3></div>
          <label className="file-picker-button"><Upload size={16} /><span>{uploading ? t('product.datasets.uploading') : t('product.datasets.chooseZip')}</span><input type="file" accept=".zip,application/zip" onChange={(event) => void upload(event.target.files?.[0])} disabled={uploading} /></label>
        </section>}
        {creationMode === 'text' && <DatasetAuthoring onSealed={async () => { await refreshAll(); closeCreation() }} />}
        {creationMode === 'docx' && <DocumentAuthoring initialDataset={resumedAuthoringDataset} onChanged={refreshAuthoring} onRegistered={async () => { await refreshAll(); closeCreation() }} />}
      </div>
    </Modal>}
    {selectedRelease && <Modal className="formal-release-modal" title={t('product.datasets.formalDatasetTitle', { version: selectedRelease.version })} closeLabel={t('product.datasets.detailModalClose')} onClose={closeFormalRelease}>{indexLoading && <div className="formal-loading"><span className="loading__bar" /><p>{t('product.datasets.loadingDetails')}</p></div>}{formalError && <ErrorBanner message={formalError} />}{documentCase && documentView && <FormalDocumentViewer view={documentView} evidenceIds={documentEvidenceIds} onBack={backToQuestions} sourceUrl={api.formalDatasetSourceUrl(selectedRelease.release_id)} nativeUrl={api.formalDatasetNativeDocumentUrl(selectedRelease.release_id)} />}{documentCase && !documentView && documentLoading && <div className="formal-loading"><span className="loading__bar" /><p>{t('product.datasets.loadingDocument')}</p></div>}{documentCase && !documentView && documentError && <div className="formal-document-error"><ErrorBanner message={documentError} /><Button variant="quiet" onClick={backToQuestions}>{t('product.datasets.backToQuestions')}</Button></div>}{formalCaseIndex && !documentCase && <FormalReleaseDetails index={formalCaseIndex} selectedCase={selectedFormalCase} loading={caseLoading} error={formalCaseError} onSelect={(item) => void selectFormalCase(selectedRelease.release_id, item)} onViewDocument={openFormalDocument} />}</Modal>}
  </>
}

type DatasetCreationMode = 'zip' | 'text' | 'docx'

function FormalReleaseDetails({ index, selectedCase, loading, error, onSelect, onViewDocument }: { index: FormalReleaseCaseIndexResponse; selectedCase: FormalCaseContent | null; loading: boolean; error: string; onSelect: (item: FormalCaseListItem) => void; onViewDocument: (item: FormalCaseContent) => void }) {
  const { t } = useLocale()
  const selectedId = selectedCase?.case_id
  const selectedIndex = selectedId ? index.cases.findIndex((item) => item.case_id === selectedId) : -1
  return <div className="formal-release-reader"><aside className="formal-case-directory" aria-label={t('product.datasets.caseDirectory')}><header><span>{t('product.datasets.caseDirectory')}</span><b>{t('product.datasets.caseCount', { count: index.cases.length })}</b></header><nav>{index.cases.map((item, itemIndex) => <button key={item.case_id} type="button" className={item.case_id === selectedId ? 'active' : ''} onClick={() => onSelect(item)}><span>{String(itemIndex + 1).padStart(2, '0')}</span><div><b>{item.question}</b><small>{item.language}</small></div></button>)}</nav></aside><section className="formal-case-inspector">{loading ? <div className="formal-loading formal-loading--compact"><span className="loading__bar" /><p>{t('product.datasets.loadingQuestion')}</p></div> : error ? <ErrorBanner message={error} /> : selectedCase ? <FormalCaseDetails item={selectedCase} index={selectedIndex} answerText={(value) => value === null ? t('common.none') : Array.isArray(value) ? value.join(' · ') : value} onViewDocument={onViewDocument} /> : <p className="field-note">{t('product.datasets.noQuestionSelected')}</p>}</section></div>
}

function FormalCaseDetails({ item, index, answerText, onViewDocument }: { item: FormalCaseContent; index: number; answerText: (value: string | string[] | null) => string; onViewDocument: (item: FormalCaseContent) => void }) {
  const { t } = useLocale()
  const language = item.language.toLowerCase().startsWith('zh') ? t('product.datasets.languageZh') : item.language.toLowerCase().startsWith('en') ? t('product.datasets.languageEn') : item.language
  const isUnanswerable = item.gold.answer.kind === 'abstain'
  const answerEvidence = item.gold.evidence.filter((evidence) => evidence.role !== 'near_miss')
  const nearMissEvidence = item.gold.evidence.filter((evidence) => evidence.role === 'near_miss')
  return <details className="formal-case" open>
    <summary><span className="formal-case-number">{String(index + 1).padStart(2, '0')}</span><span className="formal-case-summary"><b>{item.question}</b><small>{language}</small></span></summary>
    <div className="formal-case-body">
      <section className={isUnanswerable ? 'formal-answer formal-answer--unanswerable' : 'formal-answer'}><span className="formal-section-label">{t('product.datasets.detailAnswer')}</span><p>{isUnanswerable ? t('product.datasets.unanswerableAnswer') : answerText(item.gold.answer.canonical)}</p>{!isUnanswerable && item.gold.answer.accepted_values.length > 0 && <small>{t('product.datasets.detailAcceptedValues')}: {item.gold.answer.accepted_values.join(' · ')}</small>}</section>
      <section className="formal-evidence">{answerEvidence.length === 0 && <p className="field-note">{t('product.datasets.detailNoEvidence')}</p>}<div className="formal-evidence-list">{answerEvidence.map((evidence, evidenceIndex) => <FormalEvidenceDetails key={evidence.evidence_id} evidence={evidence} index={evidenceIndex} onViewDocument={() => onViewDocument(item)} />)}</div>{nearMissEvidence.length > 0 && <details className="formal-near-miss"><summary>{t('product.datasets.nearMissTitle')}</summary><p>{t('product.datasets.nearMissHint')}</p>{nearMissEvidence.map((evidence, evidenceIndex) => <FormalEvidenceDetails key={evidence.evidence_id} evidence={evidence} index={evidenceIndex} onViewDocument={() => onViewDocument(item)} />)}</details>}</section>
    </div>
  </details>
}

function FormalEvidenceDetails({ evidence, index, onViewDocument }: { evidence: FormalEvidence; index: number; onViewDocument: () => void }) {
  const { t } = useLocale()
  const canonical = evidence.canonical
  const label = ({ required: t('product.datasets.roleRequired'), supporting: t('product.datasets.roleSupporting'), conflicting: t('product.datasets.roleConflicting'), near_miss: t('product.datasets.roleNearMiss'), negative_scope: t('product.datasets.roleNegativeScope') } as Record<string, string>)[evidence.role] ?? t('product.datasets.detailEvidence')
  const isTable = canonical?.object_type === 'table'
  return <article className={`formal-evidence-item formal-evidence-item--${evidence.role}`}><header className="formal-evidence-item__header"><div className="formal-evidence-item__title"><span className="formal-evidence-number">{t('product.datasets.detailEvidenceNumber', { index: index + 1 })}</span><b>{label}</b></div>{canonical && evidence.reachable && <Button variant="quiet" onClick={onViewDocument}><Eye size={14} />{t('product.datasets.viewDocumentShort')}</Button>}</header>{!canonical ? <p className="formal-evidence-unavailable">{t('product.datasets.detailCanonicalUnavailable')}</p> : <div className="formal-evidence-item__body"><p className="formal-evidence-quote">{isTable ? t('product.datasets.tableEvidenceHint') : canonical.canonical_value ?? t('common.none')}</p></div>}</article>
}

const documentPageBudget = 42

function documentBlockWeight(block: FormalDocumentView['blocks'][number]): number {
  if (block.kind === 'table') {
    const characters = block.cells.reduce((total, cell) => total + cell.text.length, 0)
    return Math.max(5, Math.ceil(characters / 260) + 3)
  }
  return Math.max(block.heading_level ? 2 : 1, Math.ceil(block.text.length / 180))
}

function paginateDocumentBlocks(blocks: FormalDocumentView['blocks']): FormalDocumentView['blocks'][] {
  const pages: FormalDocumentView['blocks'][] = []
  let page: FormalDocumentView['blocks'] = []
  let weight = 0
  blocks.forEach((block) => {
    const blockWeight = documentBlockWeight(block)
    const startsNewPage = page.length > 0 && (
      block.page_break_before ||
      (block.heading_level === 1 && weight > 10) ||
      weight + blockWeight > documentPageBudget
    )
    if (startsNewPage) {
      pages.push(page)
      page = []
      weight = 0
    }
    page.push(block)
    weight += blockWeight
  })
  if (page.length > 0) pages.push(page)
  return pages
}

export function FormalDocumentViewer({ view, evidenceIds, onBack, sourceUrl, nativeUrl }: { view: FormalDocumentView; evidenceIds: string[]; onBack: () => void; sourceUrl: string; nativeUrl: string }) {
  const { t } = useLocale()
  // Opening from a question should take the reviewer directly to the
  // highlighted evidence. The Word-faithful layout remains available as an
  // explicit reading mode rather than delaying or obscuring that location.
  const [viewMode, setViewMode] = useState<'native' | 'evidence'>('evidence')
  const [nativeFailed, setNativeFailed] = useState(false)
  const evidenceSet = useMemo(() => new Set(evidenceIds), [evidenceIds])
  const readableBlocks = useMemo(() => view.blocks.filter((block) => block.kind !== 'figure'), [view.blocks])
  const pages = useMemo(() => paginateDocumentBlocks(readableBlocks), [readableBlocks])
  const headings = useMemo(() => readableBlocks.filter((block) => block.kind === 'heading' && block.text.trim()), [readableBlocks])
  const blockRefs = useRef<Record<string, HTMLElement | null>>({})
  useEffect(() => {
    const first = readableBlocks.find((block) => block.object_ids.some((id) => evidenceSet.has(id)))
    if (first) window.setTimeout(() => blockRefs.current[first.block_id]?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 0)
  }, [evidenceSet, readableBlocks])
  const isHighlighted = (ids: string[]) => ids.some((id) => evidenceSet.has(id))
  const groupedRows = (block: FormalDocumentView['blocks'][number]) => {
    const rows = new Map<number, FormalDocumentView['blocks'][number]['cells']>()
    block.cells.forEach((cell) => rows.set(cell.row, [...(rows.get(cell.row) ?? []), cell]))
    return [...rows.entries()].sort(([left], [right]) => left - right)
  }
  const scrollToBlock = (blockId: string) => {
    blockRefs.current[blockId]?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }
  const renderBlock = (block: FormalDocumentView['blocks'][number]) => {
    const highlighted = isHighlighted(block.object_ids)
    const baseClass = `formal-document-block formal-document-block--${block.kind}${highlighted ? ' formal-document-block--highlighted' : ''}`
    if (block.kind === 'table' && block.cells.length > 0) {
      const rows = groupedRows(block)
      const [header, ...body] = rows
      const renderCell = (cell: FormalDocumentView['blocks'][number]['cells'][number], row: number, headerCell = false) => {
        const Cell = headerCell ? 'th' : 'td'
        return <Cell key={`${row}-${cell.column}-${cell.object_ids[0]}`} rowSpan={cell.row_span} colSpan={cell.column_span} className={isHighlighted(cell.object_ids) ? 'formal-document-cell--highlighted' : ''}>{cell.text || t('common.none')}</Cell>
      }
      return <article key={block.block_id} ref={(node) => { blockRefs.current[block.block_id] = node }} className={`${baseClass} formal-document-block--table`}><div className="formal-document-table"><table>{rows.length > 1 && <thead><tr>{header[1].sort((left, right) => left.column - right.column).map((cell) => renderCell(cell, header[0], true))}</tr></thead>}<tbody>{(rows.length > 1 ? body : rows).map(([row, cells]) => <tr key={row}>{cells.sort((left, right) => left.column - right.column).map((cell) => renderCell(cell, row))}</tr>)}</tbody></table></div></article>
    }
    if (block.kind === 'heading') {
      const level = Math.min(6, Math.max(1, block.heading_level ?? 2))
      const Heading = level === 1 ? 'h1' : level === 2 ? 'h2' : level === 3 ? 'h3' : level === 4 ? 'h4' : level === 5 ? 'h5' : 'h6'
      return <article key={block.block_id} ref={(node) => { blockRefs.current[block.block_id] = node }} className={`${baseClass} formal-document-block--heading-level-${level}`}><Heading>{block.text || t('common.none')}</Heading></article>
    }
    const isListItem = block.kind === 'list_item' || block.list_level !== null && block.list_level !== undefined
    return <article key={block.block_id} ref={(node) => { blockRefs.current[block.block_id] = node }} className={baseClass}><p className={`${block.kind === 'caption' ? 'formal-document-caption ' : ''}${isListItem ? 'formal-document-list-item' : ''}`}>{isListItem && <span className="formal-document-list-marker" aria-hidden="true">•</span>}{block.text || t('common.none')}</p></article>
  }
  return <div className="formal-document-viewer"><header className="formal-document-toolbar"><Button variant="quiet" onClick={onBack}><ArrowLeft size={15} />{t('product.datasets.backToQuestions')}</Button><div><b>{t('product.datasets.documentViewTitle')}</b><small>{view.filename}</small></div><SegmentedControl label={t('product.datasets.documentViewMode')} value={viewMode} options={[{ value: 'native', label: t('product.datasets.documentNativeMode') }, { value: 'evidence', label: t('product.datasets.documentEvidenceMode') }]} onChange={setViewMode} /><a className="button button--quiet" href={sourceUrl} target="_blank" rel="noreferrer"><ExternalLink size={14} />{t('product.datasets.openOriginal')}</a></header>{viewMode === 'native' && !nativeFailed ? <section className="formal-native-document"><div className="formal-native-document__caption"><span>{t('product.datasets.documentNativeHint')}</span><span>{t('product.datasets.documentNativePagination')}</span></div><iframe title={view.filename} src={nativeUrl} onError={() => setNativeFailed(true)} /></section> : <>{nativeFailed && viewMode === 'native' && <div className="formal-document-native-error"><ErrorBanner message={t('product.datasets.documentNativeUnavailable')} /><Button variant="quiet" onClick={() => { setNativeFailed(false); setViewMode('evidence') }}>{t('product.datasets.documentEvidenceMode')}</Button></div>}<div className="formal-document-layout"><aside className="formal-document-outline" aria-label={t('product.datasets.documentOutline')}><div className="formal-document-outline__title"><ListTree size={15} />{t('product.datasets.documentOutline')}</div>{headings.length === 0 ? <p className="formal-document-outline__empty">{t('product.datasets.documentOutlineEmpty')}</p> : <nav>{headings.map((heading, index) => <button type="button" key={heading.block_id} className={`formal-document-outline__item formal-document-outline__item--level-${Math.min(6, Math.max(1, heading.heading_level ?? 2))}`} onClick={() => scrollToBlock(heading.block_id)}><span>{String(index + 1).padStart(2, '0')}</span><b>{heading.text}</b></button>)}</nav>}</aside><main className="formal-document-pages">{readableBlocks.length === 0 && <p className="field-note">{t('product.datasets.documentEmpty')}</p>}{pages.map((page, pageIndex) => <section className="formal-document-page" key={`${view.document_id}-page-${pageIndex}`}><div className="formal-document-page__meta"><span>{view.filename}</span><span>{t('product.datasets.documentPage', { current: pageIndex + 1, total: pages.length })}</span></div><div className="formal-document-page__body">{page.map(renderBlock)}</div><footer className="formal-document-page__footer">{pageIndex + 1} / {pages.length}</footer></section>)}</main></div></>}</div>
}

function DatasetAuthoring({ onSealed }: { onSealed: () => Promise<void> }) {
  const { t } = useLocale()
  const sourceRef = useRef<HTMLTextAreaElement>(null)
  const [draftId, setDraftId] = useState('')
  const [name, setName] = useState('')
  const [version, setVersion] = useState('1.0.0')
  const [content, setContent] = useState('')
  const [question, setQuestion] = useState('')
  const [gold, setGold] = useState('')
  const [selection, setSelection] = useState({ start: 0, end: 0 })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const automaticDiscoveryAttempt = useRef('')
  const payload = (): DatasetDraft => ({
    ...(draftId ? { draft_id: draftId } : {}), name, version,
    documents: [{ document_id: 'document-1', filename: 'source.md', content }],
    cases: question && gold && selection.end > selection.start ? [{ case_id: 'case-1', question, gold_answer: gold, document_id: 'document-1', span_start: selection.start, span_end: selection.end }] : [],
  })
  const seal = async () => { try { const value = await api.saveDatasetDraft(payload()); const sealed = await api.sealDatasetDraft(value.draft_id || ''); setDraftId(value.draft_id || ''); setMessage(t('product.datasets.sealed', { id: sealed.bundle_id.slice(0, 12) })); setError(''); await onSealed() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } }
  const captureSelection = () => { const source = sourceRef.current; if (source) setSelection({ start: source.selectionStart, end: source.selectionEnd }) }
  return <div className="authoring-panel">
    <div className="authoring-panel__heading"><FileText size={20} /><h3>{t('product.datasets.textTitle')}</h3></div>
    <div className="authoring-grid">
      <label><span>{t('product.datasets.name')}</span><input value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label><span>{t('product.datasets.version')}</span><input value={version} onChange={(event) => setVersion(event.target.value)} /></label>
    </div>
    <label><span>{t('product.datasets.source')}</span><textarea ref={sourceRef} value={content} onChange={(event) => { setContent(event.target.value); setSelection({ start: 0, end: 0 }) }} onSelect={captureSelection} placeholder={t('product.datasets.sourcePlaceholder')} /></label>
    {selection.end > selection.start && <div className="selection-note"><ShieldCheck size={15} />{t('product.datasets.selection', { start: selection.start, end: selection.end })}</div>}
    <div className="authoring-grid">
      <label><span>{t('product.datasets.question')}</span><input value={question} onChange={(event) => setQuestion(event.target.value)} /></label>
      <label><span>{t('product.datasets.goldAnswer')}</span><input value={gold} onChange={(event) => setGold(event.target.value)} /></label>
    </div>
    <div className="authoring-actions"><Button variant="primary" disabled={!name || !content || !question || !gold || selection.end <= selection.start} onClick={() => void seal()}>{t('product.datasets.createDataset')}</Button></div>
    {message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}
    {error && <ErrorBanner message={error} />}
  </div>
}

function AuthoringSourcePreview({ preview, loading }: { preview?: AuthoringTargetPreview; loading?: boolean }) {
  const { t } = useLocale()
  const sourceTypeLabel = (item: AuthoringTargetPreview['source'][number]) => item.object_type === 'cell' || item.object_type === 'logical_cell'
    ? t('product.authoring.sourceTableCell')
    : item.object_type === 'block' || item.object_type === 'text_span'
      ? t('product.authoring.sourceParagraph')
      : t('product.authoring.sourceExcerpt')
  if (loading) return <div className="authoring-source-preview authoring-source-preview--loading"><span className="loading__bar" />{t('product.authoring.sourcePreviewLoading')}</div>
  if (!preview) return null
  const items = (values: AuthoringTargetPreview['source'], prefix: string) => values.map((item, index) => <article className="authoring-source-preview__item" key={`${prefix}-${item.object_type}-${index}`}><small>{sourceTypeLabel(item)}{item.table?.header_path.length ? ` · ${item.table.header_path.join(' / ')}` : ''}</small><p>{item.text || t('common.none')}</p></article>)
  return <div className="authoring-source-preview">{items(preview.source, 'source')}{preview.context.length > 0 && <div className="authoring-source-preview__context"><small>{t('product.authoring.sourceTableContext')}</small>{items(preview.context, 'context')}</div>}</div>
}

function DocumentAuthoring({ onRegistered, onChanged, initialDataset = null }: { onRegistered: () => Promise<void>; onChanged?: () => Promise<void>; initialDataset?: AuthoringDataset | null }) {
  const { t } = useLocale()
  const [dataset, setDataset] = useState<AuthoringDataset | null>(initialDataset)
  const [targets, setTargets] = useState<AuthoringTarget[]>([])
  const [candidates, setCandidates] = useState<AuthoringCandidate[]>([])
  const [workspaceLoading, setWorkspaceLoading] = useState(Boolean(initialDataset))
  const [manualTargetId, setManualTargetId] = useState('')
  const [manualQuestion, setManualQuestion] = useState('')
  const [manualCandidateAnswer, setManualCandidateAnswer] = useState('')
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [answerEdits, setAnswerEdits] = useState<Record<string, string>>({})
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({})
  const [targetPreviews, setTargetPreviews] = useState<Record<string, AuthoringTargetPreview>>({})
  const [expandedSourceIds, setExpandedSourceIds] = useState<Record<string, boolean>>({})
  const [previewLoadingIds, setPreviewLoadingIds] = useState<Record<string, boolean>>({})
  const [generationCount, setGenerationCount] = useState(3)
  const [generationCapability, setGenerationCapability] = useState('all')
  const [generationJob, setGenerationJob] = useState<AuthoringGenerationJob | null>(null)
  const [discoveryJob, setDiscoveryJob] = useState<AuthoringDiscoveryJob | null>(null)
  const [discoveryElapsedSeconds, setDiscoveryElapsedSeconds] = useState(0)
  const [reviewer, setReviewer] = useState('local-reviewer')
  const [releaseName, setReleaseName] = useState('')
  const [releaseVersion, setReleaseVersion] = useState('1.0.0')
  const [busy, setBusy] = useState(false)
  const [authoringDocument, setAuthoringDocument] = useState<FormalDocumentView | null>(null)
  const [documentEvidenceIds, setDocumentEvidenceIds] = useState<string[]>([])
  const [documentOpen, setDocumentOpen] = useState(false)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [documentError, setDocumentError] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const automaticDiscoveryAttempt = useRef('')
  const authoringDocumentRequest = useRef<{ datasetId: string; promise: Promise<FormalDocumentView> } | null>(null)
  const authoringDocumentRequestToken = useRef(0)
  const stateLabel = (state: string) => ({ uploaded: t('product.authoring.stateUploaded'), analyzed: t('product.authoring.stateAnalyzed'), targets_ready: t('product.datasets.authoringReady'), candidates_ready: t('product.datasets.authoringInReview'), review_required: t('product.datasets.authoringInReview'), answer_resolved: t('product.authoring.answerResolved'), draft: t('product.authoring.candidateDraft'), approved: t('product.datasets.authoringApproved'), rejected: t('product.authoring.candidateRejected'), blocked: t('product.authoring.candidateBlocked'), exported: t('product.datasets.authoringExported'), registered: t('product.datasets.immutable'), formal_released: t('product.authoring.formalReleased'), archived: t('product.datasets.archivedState') } as Record<string, string>)[state] ?? state
  const targetLabel = (capability: string) => ({ table_lookup: t('product.authoring.targetTable'), single_document_retrieval: t('product.authoring.targetFact'), cross_section_relation: t('product.authoring.targetCrossSection'), negative_candidate: t('product.authoring.targetNegative'), version_or_authority_relation: t('product.authoring.targetVersion') } as Record<string, string>)[capability] ?? t('product.authoring.targetSource')
  const targetCategory = (capability: string) => ['table_lookup', 'single_document_retrieval', 'cross_section_relation', 'negative_candidate', 'version_or_authority_relation'].includes(capability) ? capability : 'source'
  const targetLocation = (target: AuthoringTarget) => target.capability === 'table_lookup' ? t('product.authoring.targetTableLocation') : target.capability === 'cross_section_relation' ? t('product.authoring.targetCrossSectionLocation') : t('product.authoring.targetTextLocation')
  const answerText = (candidate: AuthoringCandidate) => {
    const value = candidate.answer_evidence?.canonical_answer
    return value === undefined || value === null ? '' : Array.isArray(value) ? value.join(' · ') : value
  }
  const gateSummary = (candidate: AuthoringCandidate) => {
    if (!candidate.gates.length) return t('product.authoring.notResolved')
    const failures = candidate.gates.filter((gate) => gate.status === 'FAIL').length
    const flags = candidate.gates.filter((gate) => gate.status === 'FLAG').length
    if (failures) return t('product.authoring.checkFailed', { count: failures })
    if (flags) return t('product.authoring.checkReview', { count: flags })
    return t('product.authoring.checkPassed')
  }
  const usableTargets = useMemo(() => targets.filter((target) => !target.flags.includes('gold_evidence_prohibited') && !target.flags.includes('partial_source_representation')), [targets])
  const targetCapabilities = useMemo(() => [...new Set(usableTargets.map((target) => targetCategory(target.capability)))], [usableTargets])
  const targetGroups = useMemo(() => targetCapabilities.map((capability) => ({ capability, targets: usableTargets.filter((target) => targetCategory(target.capability) === capability) })), [targetCapabilities, usableTargets])
  const targetById = useMemo(() => new Map(targets.map((target) => [target.target_id, target])), [targets])
  const manualTarget = targetById.get(manualTargetId) ?? usableTargets[0] ?? null
  // Discovery fallback metadata describes how targets were found; it must not
  // silently remove question types from a resumed workspace. The configured
  // generation provider decides whether a selected type can be generated.
  const automaticTargets = usableTargets
  const generationCategories = useMemo(() => [...new Set(automaticTargets.map((target) => targetCategory(target.capability)))], [automaticTargets])
  const generatedTargetIds = useMemo(() => new Set(candidates.filter((candidate) => candidate.state !== 'rejected').map((candidate) => candidate.target_id)), [candidates])
  const generationPool = useMemo(() => automaticTargets.filter((target) => !generatedTargetIds.has(target.target_id) && (generationCapability === 'all' || targetCategory(target.capability) === generationCapability)), [automaticTargets, generatedTargetIds, generationCapability])
  const generationLimit = generationPool.length
  const requestedGenerationCount = generationLimit ? Math.min(Math.max(1, generationCount), generationLimit) : 0
  const generationJobActive = Boolean(generationJob && ['queued', 'running'].includes(generationJob.state))
  const discoveryJobActive = Boolean(discoveryJob && ['queued', 'running'].includes(discoveryJob.state))
  const generationProgress = generationJobProgress(generationJob)
  const generationJobSucceeded = generationProgress.succeeded
  const generationJobFailed = generationProgress.failed
  const fetchAuthoringDocument = useCallback((datasetId: string): Promise<FormalDocumentView> => {
    const cached = authoringDocumentRequest.current
    if (cached?.datasetId === datasetId) return cached.promise
    const request = api.authoringDocument(datasetId)
    authoringDocumentRequest.current = { datasetId, promise: request }
    void request.catch(() => {
      if (authoringDocumentRequest.current?.promise === request) authoringDocumentRequest.current = null
    })
    return request
  }, [])
  const refreshGenerationJobs = useCallback(async (datasetId: string) => {
    const jobs = await api.authoringGenerationJobs(datasetId)
    const next = visibleGenerationJob(jobs)
    setGenerationJob(next)
    return next
  }, [])
  const refreshDiscoveryJobs = useCallback(async (datasetId: string) => {
    const jobs = await api.authoringDiscoveryJobs(datasetId)
    const next = visibleDiscoveryJob(jobs)
    setDiscoveryJob(next)
    return next
  }, [])
  useEffect(() => {
    if (!initialDataset) return
    const datasetId = initialDataset.authoring_dataset_id
    const cached = authoringWorkspaceSnapshots.get(datasetId)
    setDataset(initialDataset)
    setTargets(cached?.targets ?? [])
    setCandidates(cached?.candidates ?? [])
    setGenerationJob(null)
    setDiscoveryJob(null)
    setWorkspaceLoading(!cached)
    setTargetPreviews({})
    setExpandedSourceIds({})
    setAnswerDrafts({})
    setAuthoringDocument(null)
    authoringDocumentRequest.current = null
    authoringDocumentRequestToken.current += 1
    setDocumentEvidenceIds([])
    setDocumentOpen(false)
    setDocumentLoading(false)
    setDocumentError('')
    automaticDiscoveryAttempt.current = ''
    let cancelled = false
    void Promise.all([api.authoringTargets(datasetId), api.authoringCandidates(datasetId), api.authoringGenerationJobs(datasetId), api.authoringDiscoveryJobs(datasetId)])
      .then(([nextTargets, nextCandidates, nextJobs, nextDiscoveryJobs]) => {
        if (cancelled) return
        authoringWorkspaceSnapshots.set(datasetId, { targets: nextTargets, candidates: nextCandidates })
        setTargets(nextTargets)
        setCandidates(nextCandidates)
        setGenerationJob(visibleGenerationJob(nextJobs))
        setDiscoveryJob(visibleDiscoveryJob(nextDiscoveryJobs))
      })
      .catch((cause) => { if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause)) })
      .finally(() => { if (!cancelled) setWorkspaceLoading(false) })
    return () => { cancelled = true }
  }, [initialDataset?.authoring_dataset_id])
  useEffect(() => {
    if (!dataset || workspaceLoading) return
    authoringWorkspaceSnapshots.set(dataset.authoring_dataset_id, { targets, candidates })
  }, [candidates, dataset?.authoring_dataset_id, targets, workspaceLoading])
  useEffect(() => {
    if (generationCapability !== 'all' && !generationCategories.includes(generationCapability)) {
      setGenerationCapability('all')
    }
  }, [generationCapability, generationCategories])
  useEffect(() => {
    if (manualTarget && manualTarget.target_id !== manualTargetId) {
      setManualTargetId(manualTarget.target_id)
    }
  }, [manualTarget?.target_id, manualTargetId])
  useEffect(() => {
    if (generationLimit > 0) {
      setGenerationCount((current) => Math.min(Math.max(1, current), generationLimit))
    }
  }, [generationLimit])
  useEffect(() => {
    if (!message) return
    const timer = window.setTimeout(() => setMessage(''), 3600)
    return () => window.clearTimeout(timer)
  }, [message])
  const refreshCandidates = async (datasetId: string) => setCandidates(await api.authoringCandidates(datasetId))
  useEffect(() => {
    if (!dataset || !generationJob || !['queued', 'running'].includes(generationJob.state)) return
    let cancelled = false
    const refresh = async () => {
      try {
        const next = await refreshGenerationJobs(dataset.authoring_dataset_id)
        if (!next || !['queued', 'running'].includes(next.state)) {
          await refreshCandidates(dataset.authoring_dataset_id)
          await onChanged?.()
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause))
      }
    }
    const timer = window.setInterval(() => { void refresh() }, 850)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [dataset?.authoring_dataset_id, generationJob?.job_id, generationJob?.state, onChanged, refreshGenerationJobs])
  useEffect(() => {
    if (!discoveryJobActive || !discoveryJob?.started_at) {
      setDiscoveryElapsedSeconds(0)
      return
    }
    const update = () => setDiscoveryElapsedSeconds(Math.max(0, Math.floor((Date.now() - Date.parse(discoveryJob.started_at!)) / 1000)))
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [discoveryJob?.job_id, discoveryJob?.started_at, discoveryJobActive])
  useEffect(() => {
    if (!dataset || !discoveryJob || !['queued', 'running'].includes(discoveryJob.state)) return
    let cancelled = false
    const refresh = async () => {
      try {
        const next = await refreshDiscoveryJobs(dataset.authoring_dataset_id)
        if (!next) return
        if (['queued', 'running'].includes(next.state)) {
          // Rule discovery has already covered the full document. Once that
          // first snapshot is saved, let authors use it while the optional
          // model suggestion continues in the background.
          if (next.rule_target_count > 0 && targets.length === 0) {
            const [nextTargets, datasets] = await Promise.all([
              api.authoringTargets(dataset.authoring_dataset_id),
              api.authoringDatasets(),
            ])
            if (cancelled) return
            setTargets(nextTargets)
            setDataset(datasets.find((item) => item.authoring_dataset_id === dataset.authoring_dataset_id) ?? dataset)
          }
          return
        }
        if (next.state === 'completed') {
          const [nextTargets, datasets] = await Promise.all([
            api.authoringTargets(dataset.authoring_dataset_id),
            api.authoringDatasets(),
          ])
          if (cancelled) return
          setTargets(nextTargets)
          setDataset(datasets.find((item) => item.authoring_dataset_id === dataset.authoring_dataset_id) ?? dataset)
          setMessage(t('product.authoring.targetsReady'))
          await onChanged?.()
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause))
      }
    }
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 850)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [dataset?.authoring_dataset_id, discoveryJob?.job_id, discoveryJob?.state, onChanged, refreshDiscoveryJobs, t, targets.length])
  const upload = async (file: File | undefined) => {
    if (!file) return
    setBusy(true); setError('')
    try { const value = await api.uploadAuthoringDocument(file); authoringWorkspaceSnapshots.delete(value.authoring_dataset_id); setDataset(value); setTargets([]); setCandidates([]); setGenerationJob(null); setDiscoveryJob(null); setWorkspaceLoading(false); setTargetPreviews({}); setExpandedSourceIds({}); setAnswerDrafts({}); setAuthoringDocument(null); authoringDocumentRequest.current = null; authoringDocumentRequestToken.current += 1; setDocumentEvidenceIds([]); setDocumentOpen(false); setDocumentLoading(false); setDocumentError(''); automaticDiscoveryAttempt.current = ''; setMessage(t('product.authoring.uploaded')); await onChanged?.() }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const analyze = async () => {
    if (!dataset) return
    setBusy(true); setError('')
    try {
      // Target discovery is persisted separately from parsing.  The response
      // returns immediately; a slow local model continues in the background.
      const value = await api.analyzeAuthoringDocument(dataset.authoring_dataset_id)
      const job = await api.createAuthoringDiscoveryJob(dataset.authoring_dataset_id, 'ollama')
      setDataset(value)
      setTargets([])
      setCandidates([])
      setDiscoveryJob(job)
      setTargetPreviews({})
      setExpandedSourceIds({})
      setAnswerDrafts({})
      setAuthoringDocument(null)
      authoringDocumentRequest.current = null
      authoringDocumentRequestToken.current += 1
      setDocumentEvidenceIds([])
      setDocumentOpen(false)
      setDocumentLoading(false)
      setDocumentError('')
      setMessage(t('product.authoring.discoveryQueued'))
      await onChanged?.()
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const discover = async () => {
    if (!dataset) return
    setBusy(true); setError('')
    try {
      const job = await api.createAuthoringDiscoveryJob(dataset.authoring_dataset_id, 'ollama')
      setDiscoveryJob(job)
      setMessage(t('product.authoring.discoveryQueued'))
      await onChanged?.()
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const retryDiscovery = async () => {
    if (!dataset || !discoveryJob || discoveryJobActive) return
    setBusy(true); setError('')
    try {
      const job = await api.retryAuthoringDiscoveryJob(dataset.authoring_dataset_id, discoveryJob.job_id)
      setDiscoveryJob(job)
      setMessage(t('product.authoring.discoveryRetryQueued'))
      await onChanged?.()
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  useEffect(() => {
    // Workspaces created by an older UI can stop at `analyzed`.  Resume them
    // automatically so they enter the same direct generation flow as newly
    // uploaded documents, without exposing a second setup button.
    if (!dataset || dataset.state !== 'analyzed' || targets.length > 0 || automaticDiscoveryAttempt.current === dataset.authoring_dataset_id) return
    automaticDiscoveryAttempt.current = dataset.authoring_dataset_id
    void discover()
  }, [dataset?.authoring_dataset_id, dataset?.state, targets.length])
  useEffect(() => {
    // The reading view is intentionally fetched after the authoring controls
    // have painted. It stays cached locally, so opening a source passage is
    // immediate in the usual review path.
    if (!dataset || targets.length === 0 || authoringDocument) return
    const datasetId = dataset.authoring_dataset_id
    let cancelled = false
    const timer = window.setTimeout(() => {
      void fetchAuthoringDocument(datasetId)
        .then((view) => { if (!cancelled) setAuthoringDocument(view) })
        .catch(() => undefined)
    }, 280)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [authoringDocument, dataset?.authoring_dataset_id, fetchAuthoringDocument, targets.length])
  const selectableTargets = () => {
    const groups = new Map<string, AuthoringTarget[]>()
    generationPool
      .forEach((target) => {
        const category = targetCategory(target.capability)
        groups.set(category, [...(groups.get(category) ?? []), target])
      })
    const selected: AuthoringTarget[] = []
    while (selected.length < requestedGenerationCount) {
      let added = false
      for (const group of groups.values()) {
        const target = group.shift()
        if (!target) continue
        selected.push(target)
        added = true
        if (selected.length === requestedGenerationCount) break
      }
      if (!added) break
    }
    return selected
  }
  const generateBatch = async () => {
    if (!dataset) return
    const selected = selectableTargets()
    if (!selected.length) { setMessage(t('product.authoring.noTargetsForSelection')); return }
    setBusy(true); setError('')
    try {
      const job = await api.createAuthoringGenerationJob(dataset.authoring_dataset_id, selected.map((target) => target.target_id))
      setGenerationJob(job)
      setMessage(t('product.authoring.batchQueued', { count: selected.length }))
      await onChanged?.()
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const cancelGenerationBatch = async () => {
    if (!dataset || !generationJob || !generationJobActive) return
    setBusy(true); setError('')
    try {
      setGenerationJob(await api.cancelAuthoringGenerationJob(dataset.authoring_dataset_id, generationJob.job_id))
      setMessage(t('product.authoring.batchCancellationRequested'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const retryGenerationBatch = async () => {
    if (!dataset || !generationJob || generationJobActive) return
    setBusy(true); setError('')
    try {
      setGenerationJob(await api.retryAuthoringGenerationJob(dataset.authoring_dataset_id, generationJob.job_id))
      setMessage(t('product.authoring.batchRetryQueued'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const loadTargetPreview = async (targetId: string) => {
    if (!dataset || targetPreviews[targetId] || previewLoadingIds[targetId]) return
    setPreviewLoadingIds((current) => ({ ...current, [targetId]: true }))
    try {
      const preview = await api.authoringTargetPreview(dataset.authoring_dataset_id, targetId)
      setTargetPreviews((current) => ({ ...current, [targetId]: preview }))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPreviewLoadingIds((current) => ({ ...current, [targetId]: false }))
    }
  }
  const toggleTargetPreview = (targetId: string) => {
    const willOpen = !expandedSourceIds[targetId]
    setExpandedSourceIds((current) => ({ ...current, [targetId]: willOpen }))
    if (willOpen) void loadTargetPreview(targetId)
  }
  const preloadGroupPreviews = (groupTargets: AuthoringTarget[]) => {
    // A collapsed category should stay inexpensive.  Once a person opens it,
    // preload only the visible source rows so their actual document excerpts
    // replace generic labels without making the author wait for every target.
    groupTargets.slice(0, 6).forEach((target) => void loadTargetPreview(target.target_id))
  }
  const generateAnswer = async (candidate: AuthoringCandidate) => {
    if (!dataset) return
    setBusy(true); setError('')
    try {
      const resolved = await api.generateAuthoringAnswer(dataset.authoring_dataset_id, candidate.candidate_id)
      setCandidates((current) => current.map((item) => item.candidate_id === candidate.candidate_id ? resolved : item))
      setMessage(t('product.authoring.answerProposalReady'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const resolveManual = async (candidate: AuthoringCandidate) => {
    const draft = answerDrafts[candidate.candidate_id]?.trim()
    if (!dataset || !draft) return
    setBusy(true); setError('')
    try { const resolved = await api.resolveAuthoringCandidate(dataset.authoring_dataset_id, candidate.candidate_id, { answer_kind: 'text', canonical_answer: draft, evidence: candidate.source_object_ids.map((source_object_id) => ({ source_object_id })) }); setCandidates((current) => current.map((item) => item.candidate_id === candidate.candidate_id ? resolved : item)); setAnswerDrafts((current) => ({ ...current, [candidate.candidate_id]: '' })); setMessage(t('product.authoring.answerProposalReady')) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const createManual = async (target: AuthoringTarget) => {
    if (!dataset || !manualQuestion.trim()) return
    setBusy(true); setError('')
    try { let candidate = await api.createAuthoringQuestion(dataset.authoring_dataset_id, target.target_id, manualQuestion.trim()); if (manualCandidateAnswer.trim()) candidate = await api.resolveAuthoringCandidate(dataset.authoring_dataset_id, candidate.candidate_id, { answer_kind: 'text', canonical_answer: manualCandidateAnswer.trim(), evidence: target.source_object_ids.map((source_object_id) => ({ source_object_id })) }); setCandidates((current) => [...current, candidate]); setManualQuestion(''); setManualCandidateAnswer(''); setMessage(t('product.authoring.questionProposalReady')) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const review = async (candidate: AuthoringCandidate, decision: 'accept' | 'reject') => {
    if (!dataset || !reviewer.trim() || !releaseName.trim()) return
    setBusy(true); setError('')
    try { await api.reviewAuthoringCandidate(dataset.authoring_dataset_id, candidate.candidate_id, decision, reviewer); await refreshCandidates(dataset.authoring_dataset_id); setMessage(decision === 'accept' ? t('product.authoring.candidateApproved') : t('product.authoring.candidateRejected')) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const edit = async (candidate: AuthoringCandidate) => {
    if (!dataset || !reviewer.trim()) return
    const editedQuestion = edits[candidate.candidate_id]?.trim()
    const editedAnswer = answerEdits[candidate.candidate_id]?.trim()
    const originalAnswer = answerText(candidate)
    const questionChanged = Boolean(editedQuestion && editedQuestion !== candidate.question)
    const answerChanged = Boolean(candidate.answer_evidence && editedAnswer && editedAnswer !== originalAnswer)
    if (!questionChanged && !answerChanged) return
    const editedResolution = answerChanged && candidate.answer_evidence ? { ...candidate.answer_evidence, canonical_answer: editedAnswer } : undefined
    setBusy(true); setError('')
    try { await api.reviewAuthoringCandidate(dataset.authoring_dataset_id, candidate.candidate_id, 'edit', reviewer, '', questionChanged ? editedQuestion : undefined, editedResolution); await refreshCandidates(dataset.authoring_dataset_id); setMessage(t('product.authoring.editSaved')) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const openAuthoringDocument = async (evidenceIds: string[]) => {
    if (!dataset) return
    setDocumentEvidenceIds(evidenceIds)
    setDocumentOpen(true)
    setDocumentError('')
    if (authoringDocument) return
    const token = authoringDocumentRequestToken.current + 1
    authoringDocumentRequestToken.current = token
    const request = fetchAuthoringDocument(dataset.authoring_dataset_id)
    setDocumentLoading(true)
    await yieldToBrowserPaint()
    try {
      const view = await request
      if (authoringDocumentRequestToken.current === token) setAuthoringDocument(view)
    } catch (cause) {
      if (authoringDocumentRequestToken.current === token) setDocumentError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      if (authoringDocumentRequestToken.current === token) setDocumentLoading(false)
    }
  }
  const closeAuthoringDocument = () => {
    authoringDocumentRequestToken.current += 1
    setDocumentOpen(false)
    setDocumentEvidenceIds([])
    setDocumentLoading(false)
    setDocumentError('')
  }
  const publishFormalRelease = async () => {
    if (!dataset || !reviewer.trim()) return
    setBusy(true); setError('')
    try {
      await api.publishAuthoringFormalRelease(dataset.authoring_dataset_id, releaseName, releaseVersion, localReleaseManager)
      setMessage(t('product.authoring.published'))
      await onRegistered()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(false)
    }
  }
  const sourceSummary = (target: AuthoringTarget) => {
    const preview = targetPreviews[target.target_id]
    const source = preview?.source.find((item) => item.text.trim()) ?? preview?.source[0]
    if (!source) return { title: targetLocation(target), subtitle: t('product.authoring.verifiedSource') }
    const text = source.text.trim()
    const headerPath = source.table?.header_path.filter(Boolean) ?? []
    return {
      title: headerPath.length ? [headerPath.join(' / '), text].filter(Boolean).join(' · ') : text || targetLocation(target),
      subtitle: source.table ? t('product.authoring.sourceTableCell') : source.object_type === 'block' || source.object_type === 'text_span' ? t('product.authoring.sourceParagraph') : t('product.authoring.sourceExcerpt'),
    }
  }
  const sourceIdsForCandidate = (candidate: AuthoringCandidate) => {
    const evidenceIds = candidate.answer_evidence?.evidence?.map((item) => item.source_object_id) ?? []
    return evidenceIds.length ? evidenceIds : candidate.source_object_ids
  }
  const needsAnalysis = Boolean(dataset && ['uploaded', 'interrupted'].includes(dataset.state))
  const needsDiscovery = Boolean(dataset && dataset.state === 'analyzed' && !discoveryJob)
  const hasApprovedCandidate = candidates.some((candidate) => candidate.state === 'approved')
  if (documentOpen) {
    return <div className="docx-authoring-panel docx-authoring-panel--reader">
      {authoringDocument && dataset && <FormalDocumentViewer view={authoringDocument} evidenceIds={documentEvidenceIds} onBack={closeAuthoringDocument} sourceUrl={api.authoringSourceUrl(dataset.authoring_dataset_id)} nativeUrl={api.authoringNativeDocumentUrl(dataset.authoring_dataset_id)} />}
      {!authoringDocument && documentLoading && <div className="formal-loading"><span className="loading__bar" /><p>{t('product.datasets.loadingDocument')}</p></div>}
      {!authoringDocument && !documentLoading && documentError && <div className="formal-document-error"><ErrorBanner message={documentError} /><Button variant="quiet" onClick={closeAuthoringDocument}>{t('product.datasets.backToQuestions')}</Button></div>}
    </div>
  }
  return <div className="docx-authoring-panel">
    {!dataset && <section className="docx-upload-choice">
      <span className="docx-authoring-icon"><FileText size={19} /></span>
      <label className="docx-select-button"><Upload size={15} /><span>{busy ? t('product.authoring.working') : t('product.authoring.chooseDocx')}</span><input type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => void upload(event.target.files?.[0])} disabled={busy} /></label>
    </section>}
    {dataset && workspaceLoading && <section className="authoring-stage authoring-stage--working"><b>{dataset.source.original_filename}</b><span role="status">{t('product.authoring.working')}</span></section>}
    {dataset && !workspaceLoading && needsAnalysis && <section className="authoring-stage"><b>{dataset.source.original_filename}</b><Button variant="primary" onClick={() => void analyze()} disabled={busy}>{busy ? t('product.authoring.working') : t('product.authoring.analyze')}</Button></section>}
    {dataset && needsDiscovery && <section className="authoring-stage authoring-stage--working"><b>{dataset.source.original_filename}</b><div><span role="status">{busy ? t('product.authoring.discoveryWorking') : t('product.authoring.discoveryPending')}</span>{!busy && <Button variant="quiet" onClick={() => void discover()}>{t('product.authoring.retryDiscovery')}</Button>}</div></section>}
    {discoveryJob && <section className="discovery-job-panel" aria-live="polite">
      <div className="discovery-job-panel__header"><b>{t('product.authoring.discoveryJobTitle')}</b><span>{t(`product.authoring.discoveryState.${discoveryJob.state}` as MessageKey)}</span></div>
      <p>{discoveryJob.phase_detail || t(`product.authoring.discoveryPhase.${discoveryJob.phase}` as MessageKey)}</p>
      <ol className="discovery-job-panel__steps">
        {(['building_rule_targets', 'awaiting_model', 'saving_results'] as const).map((phase, index) => {
          const order = (['building_rule_targets', 'awaiting_model', 'saving_results'] as string[]).indexOf(discoveryJob.phase)
          const complete = discoveryJob.state === 'completed' || (order > index && discoveryJob.phase !== 'failed')
          const active = discoveryJob.phase === phase && discoveryJobActive
          return <li key={phase} className={complete ? 'is-complete' : active ? 'is-active' : ''}><span>{index + 1}</span>{t(`product.authoring.discoveryPhase.${phase}` as MessageKey)}</li>
        })}
      </ol>
      <div className="discovery-job-panel__meta">
        {discoveryJob.rule_target_count > 0 && <span>{t('product.authoring.discoveryRuleTargets', { count: discoveryJob.rule_target_count })}</span>}
        {discoveryJobActive && <span>{t('product.authoring.discoveryElapsed', { seconds: discoveryElapsedSeconds })}</span>}
        {discoveryJob.state === 'completed' && <span>{t('product.authoring.discoveryTargetCount', { count: discoveryJob.target_count })}</span>}
      </div>
      {discoveryJob.state === 'failed' && <div className="discovery-job-panel__failure"><b>{t('product.authoring.discoveryFailed')}</b><span>{t('product.authoring.discoveryRetryHint')}</span>{discoveryJob.error_detail && <details><summary>{t('product.authoring.discoveryTechnicalDetails')}</summary><code>{discoveryJob.error_detail}</code></details>}</div>}
      {discoveryJob.state === 'failed' && <div className="discovery-job-panel__actions"><Button variant="primary" disabled={busy} onClick={() => void retryDiscovery()}><RefreshCw size={14} />{t('product.authoring.retryDiscovery')}</Button></div>}
    </section>}
    {dataset && !workspaceLoading && <div className="docx-source-switch"><span>{dataset.source.original_filename}</span><label className="docx-select-button docx-select-button--compact"><Upload size={14} /><span>{t('product.authoring.chooseDocx')}</span><input type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => void upload(event.target.files?.[0])} disabled={busy} /></label></div>}
    {targets.length > 0 && <section className="generation-panel">
      <header><h4>{t('product.authoring.generationTitle')}</h4></header>
      <div className="generation-controls">
        <label><span>{t('product.authoring.generationType')}</span><select value={generationCapability} onChange={(event) => setGenerationCapability(event.target.value)} disabled={busy || workspaceLoading || generationJobActive}><option value="all">{t('product.authoring.allTypes')}</option>{generationCategories.map((capability) => <option value={capability} key={capability}>{targetLabel(capability)}</option>)}</select></label>
        <label><span>{t('product.authoring.generationCount')}</span><input type="number" min="1" max={Math.max(1, generationLimit)} value={generationLimit ? requestedGenerationCount : 0} onChange={(event) => { const raw = Number(event.target.value); setGenerationCount(Number.isFinite(raw) ? Math.min(Math.max(1, raw), Math.max(1, generationLimit)) : 1) }} disabled={busy || workspaceLoading || generationJobActive || generationLimit === 0} /><small>{t('product.authoring.generationLimit', { count: generationLimit })}</small></label>
        <Button variant="primary" disabled={busy || workspaceLoading || generationJobActive || generationLimit === 0} onClick={() => void generateBatch()}><Sparkles size={15} />{t('product.authoring.generateBatch', { count: requestedGenerationCount })}</Button>
      </div>
    </section>}
    {generationJob && <section className="generation-job-panel" aria-live="polite">
      <div><b>{t('product.authoring.batchJobTitle')}</b><span>{t('product.authoring.batchJobProgress', { completed: generationProgress.completed, total: generationProgress.total })}</span></div>
      <p>{t(`product.authoring.batchState.${generationJob.state}` as MessageKey)}</p>
      {generationJobFailed > 0 && <ul>{generationJob.items.filter((item) => item.state === 'failed').map((item) => <li key={item.target_id}><b>{targetLabel(targetById.get(item.target_id)?.capability ?? 'source')}</b><span>{item.error_code}: {item.error_detail}</span></li>)}</ul>}
      <div className="generation-job-panel__actions">
        {generationJobActive && <Button variant="quiet" disabled={busy || generationJob.cancel_requested} onClick={() => void cancelGenerationBatch()}>{t('product.authoring.cancelBatch')}</Button>}
        {!generationJobActive && generationJob.items.some((item) => ['failed', 'cancelled'].includes(item.state)) && <Button variant="primary" disabled={busy} onClick={() => void retryGenerationBatch()}><RefreshCw size={14} />{t('product.authoring.retryFailed')}</Button>}
      </div>
    </section>}
    {manualTarget && <DisclosureSection title={t('product.authoring.manualQuestionTitle')}>
      <div className="manual-question-form">
        <label><span>{t('product.authoring.manualQuestionTarget')}</span><select value={manualTarget.target_id} onChange={(event) => setManualTargetId(event.target.value)} disabled={busy || generationJobActive}>{usableTargets.map((target) => <option key={target.target_id} value={target.target_id}>{targetLabel(target.capability)} · {targetLocation(target)}</option>)}</select></label>
        <label><span>{t('product.authoring.question')}</span><textarea value={manualQuestion} rows={2} onChange={(event) => setManualQuestion(event.target.value)} placeholder={t('product.authoring.manualQuestionPlaceholder')} /></label>
        <label><span>{t('product.authoring.proposedAnswer')}</span><textarea value={manualCandidateAnswer} rows={2} onChange={(event) => setManualCandidateAnswer(event.target.value)} placeholder={t('product.authoring.manualAnswerPlaceholder')} /></label>
        <div className="authoring-actions"><Button disabled={busy || generationJobActive || !manualQuestion.trim()} onClick={() => void createManual(manualTarget)}>{t('product.authoring.addManualQuestion')}</Button></div>
      </div>
    </DisclosureSection>}
    {candidates.length > 0 && <section className="candidate-review-section">
      <header><h4>{t('product.authoring.humanReview')}</h4><label className="reviewer-field"><span>{t('product.authoring.reviewer')}</span><input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label></header>
      <div className="candidate-list">{candidates.map((candidate, index) => {
        const answer = answerText(candidate)
        const questionChanged = (edits[candidate.candidate_id] ?? candidate.question) !== candidate.question
        const answerChanged = Boolean(candidate.answer_evidence && (answerEdits[candidate.candidate_id] ?? answer) !== answer)
        return <article className="candidate-card" key={candidate.candidate_id}>
          <div className="candidate-card__header"><span>{t('product.authoring.candidateNumber', { index: index + 1 })}</span><span className="candidate-card__state">{stateLabel(candidate.state)}</span><span>{gateSummary(candidate)}</span></div>
          <div className="candidate-card__fields">
            <label><span>{t('product.authoring.question')}</span><textarea value={edits[candidate.candidate_id] ?? candidate.question} onChange={(event) => setEdits((current) => ({ ...current, [candidate.candidate_id]: event.target.value }))} rows={2} /></label>
            {candidate.answer_evidence ? <label><span>{t('product.authoring.proposedAnswer')}</span><textarea value={answerEdits[candidate.candidate_id] ?? answer} onChange={(event) => setAnswerEdits((current) => ({ ...current, [candidate.candidate_id]: event.target.value }))} rows={2} /></label> : <section className="candidate-card__missing"><b>{t('product.authoring.answerPending')}</b><div className="candidate-answer-inline"><Button variant="quiet" onClick={() => void generateAnswer(candidate)} disabled={busy}>{t('product.authoring.generateAnswer')}</Button><input value={answerDrafts[candidate.candidate_id] ?? ''} onChange={(event) => setAnswerDrafts((current) => ({ ...current, [candidate.candidate_id]: event.target.value }))} placeholder={t('product.authoring.answerPlaceholder')} /><Button onClick={() => void resolveManual(candidate)} disabled={busy || !(answerDrafts[candidate.candidate_id] ?? '').trim()}>{t('product.authoring.saveAnswer')}</Button></div></section>}
          </div>
          <div className="candidate-card__source"><Button variant="quiet" onClick={() => void openAuthoringDocument(sourceIdsForCandidate(candidate))}><Eye size={14} />{t('product.authoring.viewSourcePreview')}</Button></div>
          {!['approved', 'rejected'].includes(candidate.state) && <div className="candidate-card__actions"><Button onClick={() => void edit(candidate)} disabled={busy || (!questionChanged && !answerChanged)}>{t('product.authoring.saveEdit')}</Button><Button onClick={() => void review(candidate, 'reject')} disabled={busy}>{t('product.authoring.reject')}</Button>{candidate.state === 'review_required' && <Button variant="primary" onClick={() => void review(candidate, 'accept')} disabled={busy}>{t('product.authoring.approve')}</Button>}</div>}
        </article>
      })}</div>
    </section>}
    {hasApprovedCandidate && <section className="publication-panel publication-panel--direct"><header><div><h4>{t('product.authoring.publishTitle')}</h4><small>{t('product.authoring.publishHint')}</small></div><ShieldCheck size={19} /></header><div className="publication-controls publication-controls--direct"><label className="publication-version"><span>{t('product.authoring.datasetName')}</span><input value={releaseName} onChange={(event) => setReleaseName(event.target.value)} placeholder={dataset?.source.original_filename.replace(/\.docx$/i, '') || t('product.authoring.datasetName')} /></label><label className="publication-version"><span>{t('product.authoring.version')}</span><input value={releaseVersion} onChange={(event) => setReleaseVersion(event.target.value)} placeholder="1.0.0" /></label><Button variant="primary" disabled={busy || !reviewer.trim() || !releaseName.trim() || !releaseVersion.trim()} onClick={() => void publishFormalRelease()}><ShieldCheck size={15} />{t('product.authoring.publish')}</Button></div></section>}
    {message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}
    {error && <ErrorBanner message={error} />}
  </div>
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
  useEffect(() => {
    const configured = systems.find((item) => item.system_id === profile?.system_id)
    setProvider(configured?.execution_provider ?? 'local')
    if (configured) setDisplayName(configured.display_name)
  }, [profile?.system_id, systems])
  const connectionPayload = (): SystemConnectionPayload | null => profile ? { system_id: profile.system_id, display_name: displayName || profile.display_name, profile_id: profile.profile_id, profile_version: profile.profile_version, execution_provider: provider, logical_endpoint_ref: profile.default_logical_endpoint } : null
  const save = async () => {
    const connection = connectionPayload()
    if (!connection) return
    try { await api.saveProductSystem(connection, secretKey && secretValue ? { [secretKey]: secretValue } : {}); setSecretValue(''); setMessage(t('product.systems.saved')); setError(''); await refresh() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  const test = async () => { const connection = connectionPayload(); if (!connection) return; try { await api.saveProductSystem(connection); const value = await api.testProductSystem(connection.system_id); setMessage(t('product.systems.tested', { adapter: value.adapter_id })); setError(''); await refresh() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); await refresh() } }
  const remove = async (item: ProductSystemSummary) => {
    if (!window.confirm(t('product.systems.deleteConfirm', { name: item.display_name }))) return
    try { await api.deleteProductSystem(item.system_id); setMessage(t('product.systems.deleted')); setError(''); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); await refresh() }
  }
  return <><PageHeader title={t('product.systems.title')} /><div className="system-setup"><Surface tone="inset"><header><span><ServerCog size={18} />{t('product.systems.add')}</span></header><div className="authoring-grid"><label><span>{t('product.systems.type')}</span><select value={selected} onChange={(event) => setSelected(event.target.value)}>{profiles.map((item) => <option value={`${item.profile_id}@${item.profile_version}`} key={`${item.profile_id}@${item.profile_version}`}>{item.display_name} · {item.profile_version}</option>)}</select></label><label><span>{t('product.systems.name')}</span><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label><label><span>{t('product.systems.execution')}</span><select value={provider} onChange={(event) => setProvider(event.target.value as 'local' | 'docker')}><option value="local">{t('product.systems.local')}</option><option value="docker">{t('product.systems.docker')}</option></select></label></div><p className="field-note">{t('product.systems.exclusiveNote')}</p><div className="authoring-actions"><Button onClick={() => void save()} disabled={!profile}>{t('product.systems.save')}</Button><Button variant="primary" onClick={() => void test()} disabled={!profile}>{t('product.systems.test')}</Button></div></Surface><Surface><header><span>{t('product.systems.configured')}</span></header><div className="resource-list resource-list--compact">{systems.map((item) => <article key={item.system_id}><div><b>{item.display_name}</b><small>{item.profile_id}@{item.profile_version} · {item.execution_provider}</small></div><div className="system-row-actions"><StatusBadge state={item.connection_test_status} /><Button variant="quiet" onClick={() => void remove(item)}>{t('product.systems.delete')}</Button></div></article>)}</div></Surface></div>{message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}{error && <ErrorBanner message={error} />}<DisclosureSection title={t('product.systems.credentials')}><div className="inline-form"><label><span>{t('product.systems.credentialKey')}</span><input value={secretKey} onChange={(event) => setSecretKey(event.target.value)} /></label><label><span>{t('product.systems.credentialValue')}</span><input type="password" value={secretValue} onChange={(event) => setSecretValue(event.target.value)} autoComplete="new-password" /></label></div></DisclosureSection><DisclosureSection title={t('product.systems.advancedLegacy')}>{legacy.map((item) => <code className="legacy-system" key={item.system_id}>{item.system_id} · {item.adapter_id}</code>) || <p className="field-note">{t('product.systems.noLegacy')}</p>}</DisclosureSection></>
}

const llmStageLabelKeys: Record<LLMStage, MessageKey> = {
  target_discovery: 'product.llm.targetDiscovery',
  question_generation: 'product.llm.questionGeneration',
  answer_evidence: 'product.llm.answerEvidence',
  review_assist: 'product.llm.reviewAssist',
  calibration: 'product.llm.calibration',
  runtime_generation: 'product.llm.runtimeGeneration',
  runtime_embedding: 'product.llm.runtimeEmbedding',
}

type LLMProviderDraft = {
  display_name: string
  kind: LLMProviderKind
  endpoint: string
  api_key: string
}

const emptyLLMProviderDraft: LLMProviderDraft = {
  display_name: '',
  kind: 'ollama',
  endpoint: 'http://127.0.0.1:11434',
  api_key: '',
}

type ModelUse = 'chat' | 'embedding'

const uniqueModelNames = (values: Array<string | null | undefined>) => Array.from(new Set(values.map((value) => value?.trim() ?? '').filter(Boolean)))

const modelsForProvider = (provider: LLMProviderConfig, use: ModelUse, selected?: string | null) => {
  const typed = use === 'embedding' ? provider.available_embedding_models : provider.available_chat_models
  // Older persisted configurations do not have typed catalogues yet.  Their
  // flat catalogue is still a safe fallback until the next detection pass.
  return uniqueModelNames([...(typed ?? []), ...((typed?.length ?? 0) ? [] : provider.available_models ?? []), selected])
}

// This is a read-only view of an actual detection result.  It intentionally
// does not include a previously selected stage model, so an undetected
// provider never looks as though it has already returned a catalogue.
const detectedModelGroups = (provider: LLMProviderConfig): Array<{ label: MessageKey; models: string[] }> => {
  const fallback = uniqueModelNames(provider.available_models)
  const chatModels = uniqueModelNames(provider.available_chat_models.length ? provider.available_chat_models : fallback)
  const embeddingModels = uniqueModelNames(provider.available_embedding_models)
  if (!chatModels.length && !embeddingModels.length) return []
  const sameGroups = chatModels.length === embeddingModels.length && chatModels.every((model) => embeddingModels.includes(model))
  if (!embeddingModels.length || sameGroups) return [{ label: 'product.llm.availableModels', models: chatModels }]
  if (!chatModels.length) return [{ label: 'product.llm.embeddingModels', models: embeddingModels }]
  return [
    { label: 'product.llm.chatModels', models: chatModels },
    { label: 'product.llm.embeddingModels', models: embeddingModels },
  ]
}

const bindingModelUse = (stage: LLMStage): ModelUse => stage === 'runtime_embedding' ? 'embedding' : 'chat'

const generatedProviderId = (displayName: string, providers: LLMProviderConfig[]) => {
  const stem = displayName
    .normalize('NFKD')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'model'
  let candidate = stem
  let index = 2
  const known = new Set(providers.map((provider) => provider.provider_id))
  while (known.has(candidate)) {
    candidate = `${stem}-${index}`
    index += 1
  }
  return candidate
}

export function LLMConfigurationPage() {
  const { t } = useLocale()
  const [config, setConfig] = useState<LLMConfigRevision | null>(null)
  const [providerDraft, setProviderDraft] = useState<LLMProviderDraft>(emptyLLMProviderDraft)
  const [pendingSecrets, setPendingSecrets] = useState<Record<string, string>>({})
  const [showAdd, setShowAdd] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [detecting, setDetecting] = useState('')
  const [measuring, setMeasuring] = useState('')
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      setConfig(await api.llmConfig())
      setDirty(false)
      setError('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!message) return
    const timer = window.setTimeout(() => setMessage(''), 3200)
    return () => window.clearTimeout(timer)
  }, [message])

  const providers = config?.providers ?? []
  const providerMap = useMemo(() => new Map(providers.map((provider) => [provider.provider_id, provider])), [providers])
  const updateProvider = (providerId: string, patch: Partial<LLMProviderConfig>) => {
    setDirty(true)
    const catalogueChanged = Object.hasOwn(patch, 'endpoint') || Object.hasOwn(patch, 'kind')
    setConfig((current) => current ? {
      ...current,
      providers: current.providers.map((provider) => provider.provider_id === providerId ? {
        ...provider,
        ...patch,
        health_status: 'not_checked',
        health_message: null,
        available_models: catalogueChanged ? [] : provider.available_models,
        available_chat_models: catalogueChanged ? [] : provider.available_chat_models,
        available_embedding_models: catalogueChanged ? [] : provider.available_embedding_models,
        last_checked_at: null,
        latency_status: catalogueChanged ? 'not_checked' : provider.latency_status,
        latency_ms: catalogueChanged ? null : provider.latency_ms,
        last_latency_checked_at: catalogueChanged ? null : provider.last_latency_checked_at,
      } : provider),
    } : current)
  }
  const updateBinding = (stage: LLMStage, patch: Partial<LLMStageBinding>) => {
    setDirty(true)
    setConfig((current) => current ? { ...current, bindings: current.bindings.map((binding) => binding.stage === stage ? { ...binding, ...patch } : binding) } : current)
  }
  const openAdd = () => {
    setProviderDraft(emptyLLMProviderDraft)
    setShowAdd(true)
    setError('')
  }
  const addProvider = () => {
    if (!config || !providerDraft.display_name.trim() || !providerDraft.endpoint.trim()) {
      setError(t('product.llm.validation'))
      return
    }
    if (providerDraft.kind === 'openai_compatible' && !providerDraft.api_key.trim()) {
      setError(t('product.llm.externalKeyRequired'))
      return
    }
    const id = generatedProviderId(providerDraft.display_name, config.providers)
    const provider: LLMProviderConfig = {
      provider_id: id,
      display_name: providerDraft.display_name.trim(),
      kind: providerDraft.kind,
      endpoint: providerDraft.endpoint.trim().replace(/\/$/, ''),
      model: '',
      embedding_model: null,
      enabled: true,
      api_key_configured: false,
      health_status: 'not_checked',
      available_models: [],
      available_chat_models: [],
      available_embedding_models: [],
      health_message: null,
      last_checked_at: null,
      latency_status: 'not_checked',
      latency_ms: null,
      last_latency_checked_at: null,
    }
    setConfig({ ...config, providers: [...config.providers, provider] })
    setDirty(true)
    if (providerDraft.api_key) setPendingSecrets((current) => ({ ...current, [id]: providerDraft.api_key }))
    setShowAdd(false)
  }
  const save = async (): Promise<boolean> => {
    if (!config) return false
    const missingKey = config.providers.find((provider) => provider.kind === 'openai_compatible' && !provider.api_key_configured && !pendingSecrets[provider.provider_id]?.trim())
    if (missingKey) {
      setError(t('product.llm.externalKeyRequired'))
      return false
    }
    setSaving(true)
    setError('')
    try {
      const saved = await api.saveLlmConfig({
        providers: config.providers.map(({ provider_id, display_name, kind, endpoint, model, embedding_model, enabled }) => ({ provider_id, display_name, kind, endpoint, model, embedding_model, enabled })),
        bindings: config.bindings,
        actor: 'local-user',
        reason: 'edited in model settings',
        secrets: pendingSecrets,
      })
      setConfig(saved)
      setPendingSecrets({})
      setDirty(false)
      setMessage(t('product.llm.saved'))
      return true
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
      return false
    } finally {
      setSaving(false)
    }
  }
  const detectProviderModels = async (providerId: string) => {
    setDetecting(providerId)
    setError('')
    try {
      // An edited endpoint/model must be saved before it can be checked.  A
      // clean check only updates the operational health observation and does
      // not create a needless configuration revision.
      if (dirty && !(await save())) return
      const tested = await api.testLlmProvider(providerId)
      setConfig((current) => current ? { ...current, providers: current.providers.map((provider) => provider.provider_id === providerId ? tested : provider) } : current)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setDetecting('')
    }
  }
  const measureProviderLatency = async (providerId: string) => {
    setMeasuring(providerId)
    setError('')
    try {
      // A changed service address needs saving before this operational probe
      // can run against the same provider configuration the user sees.
      if (dirty && !(await save())) return
      const measured = await api.measureLlmProviderLatency(providerId)
      setConfig((current) => current ? { ...current, providers: current.providers.map((provider) => provider.provider_id === providerId ? measured : provider) } : current)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setMeasuring('')
    }
  }

  if (loading) return <div className="llm-page"><div className="formal-loading"><span className="loading__bar" /><p>{t('common.checking')}</p></div></div>
  if (!config) return <div className="llm-page">{error && <ErrorBanner message={error} />}</div>

  return <>
    <PageHeader title={t('product.llm.title')} actions={<Button variant="primary" onClick={() => void save()} disabled={saving}><CheckCircle2 size={15} />{saving ? t('product.llm.saving') : t('product.llm.save')}</Button>} />
    <div className="llm-page">
      <section className="llm-section">
        <header className="llm-section__header"><div><h2>{t('product.llm.providers')}</h2></div><Button onClick={openAdd}><Plus size={15} />{t('product.llm.addProvider')}</Button></header>
        <div className="llm-provider-list">{providers.map((provider) => <article className="llm-provider-card" key={provider.provider_id}>
          <header className="llm-provider-card__header"><div className="llm-provider-card__identity"><span className="llm-provider-card__icon"><BrainCircuit size={16} /></span><div><b>{provider.display_name}</b><small>{provider.kind === 'ollama' ? t('product.llm.ollama') : t('product.llm.openaiCompatible')}</small></div></div><StatusBadge state={provider.health_status} /></header>
          <div className="llm-provider-grid">
            <label className="llm-provider-grid__wide"><span>{t('product.llm.endpoint')}</span><input value={provider.endpoint} onChange={(event) => updateProvider(provider.provider_id, { endpoint: event.target.value })} /></label>
            {provider.kind === 'openai_compatible' && <label className="llm-provider-grid__wide"><span>{t('product.llm.apiKeyRequired')}</span><input required type="password" autoComplete="new-password" value={pendingSecrets[provider.provider_id] ?? ''} placeholder={provider.api_key_configured ? t('product.llm.apiKeyConfigured') : t('product.llm.apiKeyEmpty')} onChange={(event) => setPendingSecrets((current) => ({ ...current, [provider.provider_id]: event.target.value }))} /></label>}
            <div className="llm-provider-grid__wide llm-provider-grid__actions"><Button variant="quiet" onClick={() => void measureProviderLatency(provider.provider_id)} disabled={detecting !== '' || measuring !== '' || saving}>{measuring === provider.provider_id ? <><Gauge size={13} className="spin" />{t('product.llm.measuring')}</> : <><Gauge size={13} />{t('product.llm.measureLatency')}</>}</Button><Button variant="quiet" onClick={() => void detectProviderModels(provider.provider_id)} disabled={detecting !== '' || measuring !== '' || saving}>{detecting === provider.provider_id ? <><RefreshCw size={13} className="spin" />{t('product.llm.testing')}</> : <><RefreshCw size={13} />{t('product.llm.detectModels')}</>}</Button>{provider.latency_status === 'measured' && provider.latency_ms !== null && <span className="llm-latency" title={t('product.llm.latency')}><Gauge size={12} />{provider.latency_ms} ms</span>}{(provider.latency_status === 'unreachable' || provider.latency_status === 'invalid') && <span className="llm-latency llm-latency--failed">{t('product.llm.speedUnavailable')}</span>}</div>
            {detectedModelGroups(provider).length > 0 && <div className="llm-provider-grid__wide llm-provider-catalog">{detectedModelGroups(provider).map((group) => <div className="llm-provider-catalog__group" key={group.label}><span>{t(group.label)}</span><div>{group.models.map((model) => <code key={model}>{model}</code>)}</div></div>)}</div>}
          </div>
        </article>)}</div>
      </section>
      <section className="llm-section">
        <header className="llm-section__header"><div><h2>{t('product.llm.modelConfiguration')}</h2><p className="field-note">{t('product.llm.runtimeSelectedInEvaluation')}</p></div></header>
        <div className="llm-stage-list"><div className="llm-stage-list__head"><span>{t('product.llm.scenario')}</span><span>{t('product.llm.modelProvider')}</span><span>{t('product.llm.selectedModel')}</span></div>{config.bindings.filter((binding) => binding.stage !== 'runtime_generation' && binding.stage !== 'runtime_embedding').map((binding) => {
          const provider = providerMap.get(binding.provider_id)
          const modelUse = bindingModelUse(binding.stage)
          const options = provider ? modelsForProvider(provider, modelUse, binding.model) : []
          return <div className="llm-stage-row" key={binding.stage}><div className="llm-stage-row__name"><b>{t(llmStageLabelKeys[binding.stage])}</b></div><select value={binding.provider_id} onChange={(event) => { const nextProvider = providerMap.get(event.target.value); const use = bindingModelUse(binding.stage); const choices = nextProvider ? modelsForProvider(nextProvider, use, use === 'embedding' ? nextProvider.embedding_model : nextProvider.model) : []; updateBinding(binding.stage, { provider_id: event.target.value, model: choices[0] ?? null }) }}>{providers.map((item) => { const itemOptions = modelsForProvider(item, modelUse, modelUse === 'embedding' ? item.embedding_model : item.model); return <option disabled={!itemOptions.length} key={item.provider_id} value={item.provider_id}>{item.display_name}</option> })}</select><select value={binding.model ?? ''} disabled={!options.length} onChange={(event) => updateBinding(binding.stage, { model: event.target.value || null })}>{options.length ? options.map((model) => <option value={model} key={model}>{model}</option>) : <option value="">{t('product.llm.detectFirst')}</option>}</select></div>
        } )}</div>
      </section>
      {message && <p className="product-message"><CheckCircle2 size={15} />{message}</p>}
      {error && <ErrorBanner message={error} />}
    </div>
    {showAdd && <Modal title={t('product.llm.addTitle')} closeLabel={t('product.llm.cancel')} onClose={() => setShowAdd(false)} className="llm-provider-modal"><div className="llm-provider-form"><label><span>{t('product.llm.providerName')}</span><input value={providerDraft.display_name} onChange={(event) => setProviderDraft((current) => ({ ...current, display_name: event.target.value }))} /></label><label><span>{t('product.llm.providerType')}</span><select value={providerDraft.kind} onChange={(event) => setProviderDraft((current) => ({ ...current, kind: event.target.value as LLMProviderKind, api_key: event.target.value === 'ollama' ? '' : current.api_key }))}><option value="ollama">{t('product.llm.ollama')}</option><option value="openai_compatible">{t('product.llm.openaiCompatible')}</option></select></label><label className="llm-provider-form__wide"><span>{t('product.llm.endpoint')}</span><input value={providerDraft.endpoint} onChange={(event) => setProviderDraft((current) => ({ ...current, endpoint: event.target.value }))} /></label>{providerDraft.kind === 'openai_compatible' && <label className="llm-provider-form__wide"><span>{t('product.llm.apiKeyRequired')}</span><input required type="password" autoComplete="new-password" value={providerDraft.api_key} onChange={(event) => setProviderDraft((current) => ({ ...current, api_key: event.target.value }))} /></label>}<div className="llm-provider-form__actions"><Button onClick={() => setShowAdd(false)}>{t('product.llm.cancel')}</Button><Button variant="primary" onClick={addProvider}>{t('product.llm.add')}</Button></div></div></Modal>}
  </>
}

type EvaluationModelChoice = { value: string; label: string }

const evaluationModels = (providers: LLMProviderConfig[], use: ModelUse): EvaluationModelChoice[] => {
  const values = providers.flatMap((provider) => modelsForProvider(provider, use, use === 'embedding' ? provider.embedding_model : provider.model)
    .map((model) => ({ value: model, label: `${provider.display_name} · ${model}` })))
  return values.filter((item, index) => values.findIndex((candidate) => candidate.value === item.value) === index)
}

const queryModesFor = (profileId: SystemProfile['profile_id'] | undefined) => profileId === 'rag-anything'
  ? ['naive', 'mix']
  : ['naive', 'local', 'global', 'hybrid', 'mix']

export function NewEvaluationPage({ datasets, formalDatasets, onQueued }: { datasets: DatasetSummary[]; formalDatasets: FormalDatasetsResponse; onQueued: () => void }) {
  const { t } = useLocale()
  const [profiles, setProfiles] = useState<SystemProfile[]>([])
  const [systems, setSystems] = useState<ProductSystemSummary[]>([])
  const [modelChoices, setModelChoices] = useState<EvaluationModelChoice[]>([])
  const [embeddingChoices, setEmbeddingChoices] = useState<EvaluationModelChoice[]>([])
  const [datasetValue, setDatasetValue] = useState('')
  const [runName, setRunName] = useState('')
  const [systemId, setSystemId] = useState('')
  const [model, setModel] = useState('')
  const [embedding, setEmbedding] = useState('')
  const [queryMode, setQueryMode] = useState('')
  const [mode, setMode] = useState<'basic' | 'advanced'>('basic')
  const [candidateK, setCandidateK] = useState('')
  const [contextK, setContextK] = useState('')
  const [tokenBudget, setTokenBudget] = useState('')
  const [queryTimeoutSeconds, setQueryTimeoutSeconds] = useState('300')
  const [metricPreset, setMetricPreset] = useState('balanced')
  const [generateAnswer, setGenerateAnswer] = useState('default')
  const [seed, setSeed] = useState('0')
  const [repetitions, setRepetitions] = useState('1')
  const [draft, setDraft] = useState<EvaluationDraft | null>(null)
  const [preview, setPreview] = useState<ExperimentSpec | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    void Promise.all([api.profiles(), api.productSystems(), api.llmConfig()]).then(([nextProfiles, nextSystems, llmConfig]) => {
      const nextModels = evaluationModels(llmConfig.providers, 'chat')
      const nextEmbeddings = evaluationModels(llmConfig.providers, 'embedding')
      setProfiles(nextProfiles)
      setSystems(nextSystems)
      setModelChoices(nextModels)
      setEmbeddingChoices(nextEmbeddings)
      if (!systemId && nextSystems[0]) setSystemId(nextSystems[0].system_id)
      setModel((current) => nextModels.some((item) => item.value === current) ? current : (nextModels[0]?.value ?? ''))
      setEmbedding((current) => nextEmbeddings.some((item) => item.value === current) ? current : (nextEmbeddings[0]?.value ?? ''))
    }).catch((cause) => setError(cause instanceof Error ? cause.message : String(cause)))
  }, [])

  const selectedLegacyBundle = datasetValue.startsWith('bundle:') ? datasetValue.slice('bundle:'.length) : null
  const selectedReleaseId = datasetValue.startsWith('release:') ? datasetValue.slice('release:'.length) : null
  const selectedRelease = formalDatasets.releases.find((item) => item.release_id === selectedReleaseId)
  const system = systems.find((item) => item.system_id === systemId)
  const profile = profiles.find((item) => item.profile_id === system?.profile_id && item.profile_version === system?.profile_version)
  const queryModes = queryModesFor(profile?.profile_id)
  const isLightRAG = profile?.profile_id === 'lightrag'
  const validDataset = Boolean(selectedLegacyBundle || selectedRelease?.runnable)

  const clearPreview = () => { setPreview(null); setDraft(null); setMessage('') }
  const buildDraft = (): EvaluationDraft | null => {
    if (!validDataset || !system || !profile) return null
    if (!model || !embedding) throw new Error(t('product.wizard.modelsRequired'))
    const parseInteger = (value: string, minimum: number, label: string): number | undefined => {
      if (!value.trim()) return undefined
      const parsed = Number(value)
      if (!Number.isInteger(parsed) || parsed < minimum) throw new Error(t('product.wizard.invalidInteger', { label, minimum }))
      return parsed
    }
    const candidate = mode === 'advanced' ? parseInteger(candidateK, 1, t('product.wizard.candidateK')) : undefined
    const context = mode === 'advanced' ? parseInteger(contextK, 1, t('product.wizard.contextK')) : undefined
    const tokens = mode === 'advanced' ? parseInteger(tokenBudget, 1, t('product.wizard.tokenBudget')) : undefined
    // This is one deadline, not a second independent timeout.  The adapter
    // applies the same value to LightRAG's QUERY_LLM_TIMEOUT and keeps only a
    // fixed response-serialization grace window outside the experiment.
    const queryTimeout = isLightRAG
      ? parseInteger(queryTimeoutSeconds || '0', 30, t('product.wizard.queryTimeout'))
      : undefined
    const selectedSeed = mode === 'advanced' ? parseInteger(seed, 0, t('product.wizard.seed')) ?? 0 : 0
    const selectedRepetitions = mode === 'advanced' ? parseInteger(repetitions, 1, t('product.wizard.repetitions')) ?? 1 : 1
    const retrieval = {
      ...(candidate === undefined ? {} : { retrieval_candidate_k: candidate }),
      ...(context === undefined ? {} : { final_context_k: context }),
      ...(tokens === undefined ? {} : { max_context_tokens: tokens }),
    }
    const metricValues = metricPreset === 'recall' ? [1, 5, 10] : metricPreset === 'quick' ? [1, 3] : [1, 3, 5]
    const queryOverrides: Record<string, unknown> = {
      ...retrieval,
      ...(mode === 'advanced' && generateAnswer !== 'default' ? { generate_answer: generateAnswer === 'on' } : {}),
    }
    return {
      mode,
      bundle_id: selectedLegacyBundle,
      dataset_release_id: selectedReleaseId,
      system_id: system.system_id,
      profile_id: profile.profile_id,
      profile_version: profile.profile_version,
      // Empty intentionally delegates to the API's frozen, readable default
      // (system + creation time + short Run ID).  A person can provide an
      // explicit title without it becoming a scoring/configuration setting.
      display_name: runName.trim(),
      adapter_overrides: {
        model: { llm_model: model, embedding_model: embedding },
        ...(queryMode ? { query_mode: queryMode } : {}),
        ...retrieval,
        ...(queryTimeout === undefined ? {} : { query_timeout_seconds: queryTimeout }),
      },
      query_overrides: queryOverrides,
      metric_overrides: mode === 'advanced' ? { k_values: metricValues } : {},
      case_ids: null,
      seed: selectedSeed,
      repetitions: selectedRepetitions,
      formal: false,
    }
  }
  const previewSpec = async () => {
    try {
      const value = buildDraft()
      if (!value) return
      const saved = await api.saveEvaluationDraft(value)
      setDraft(saved)
      const result = await api.previewEvaluationDraft(saved.draft_id || '')
      setPreview(result)
      setMessage(t('product.wizard.ready'))
      setError('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
      setPreview(null)
      setDraft(null)
    }
  }
  const run = async () => {
    if (!draft?.draft_id) return
    try {
      await api.finalizeEvaluationDraft(draft.draft_id)
      setMessage(t('product.wizard.queued'))
      setError('')
      onQueued()
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }

  return <>
    <PageHeader title={t('product.wizard.title')} />
    <ol className="wizard-steps"><li className={validDataset ? 'done' : ''}>{t('product.wizard.stepDataset')}</li><li className={system ? 'done' : ''}>{t('product.wizard.stepSystem')}</li><li className={preview ? 'done' : ''}>{t('product.wizard.stepReview')}</li><li>{t('product.wizard.stepRun')}</li></ol>
    <Surface className="wizard-form">
      <div className="authoring-actions"><span className="field-note">{t('product.wizard.mode')}</span><SegmentedControl label={t('product.wizard.mode')} value={mode} onChange={(value) => { setMode(value); clearPreview() }} options={[{ value: 'basic', label: t('product.wizard.basicMode') }, { value: 'advanced', label: t('product.wizard.advancedMode') }]} /></div>
      <div className="authoring-grid">
        <label><span>运行名称（可选）</span><input value={runName} maxLength={160} placeholder="例如：LightRAG · 供应商审计 v1" onChange={(event) => { setRunName(event.target.value); clearPreview() }} /><small className="field-note">留空时会生成包含系统、时间和短 Run ID 的默认名称。</small></label>
        <label><span>{t('product.wizard.dataset')}</span><select value={datasetValue} onChange={(event) => { setDatasetValue(event.target.value); clearPreview() }}><option value="">{t('product.wizard.selectDataset')}</option>{formalDatasets.releases.map((item) => <option value={`release:${item.release_id}`} disabled={!item.runnable} key={item.release_id}>{item.name}{item.name === item.version ? '' : ` · ${item.version}`} · {t('product.datasets.caseCount', { count: item.case_count })}{item.runnable ? '' : ` · ${t('product.wizard.datasetUnavailable')}`}</option>)}{datasets.map((item) => <option value={`bundle:${item.bundle_id}`} key={item.bundle_id}>{item.name}{item.name === item.version ? '' : ` · ${item.version}`}</option>)}</select>{selectedRelease && !selectedRelease.runnable && <small className="field-note">{t('product.wizard.datasetUnavailableReason', { reason: selectedRelease.runtime_reason || t('product.wizard.datasetUnavailable') })}</small>}{selectedRelease?.runnable && <small className="field-note">{t('product.wizard.formalDatasetNote')}</small>}</label>
        <label><span>{t('product.wizard.system')}</span><select value={systemId} onChange={(event) => { setSystemId(event.target.value); setQueryMode(''); clearPreview() }}><option value="">{t('product.wizard.selectSystem')}</option>{systems.map((item) => <option value={item.system_id} key={item.system_id}>{item.display_name}</option>)}</select></label>
        <label><span>{t('product.wizard.model')}</span><select value={model} onChange={(event) => { setModel(event.target.value); clearPreview() }} disabled={!modelChoices.length}><option value="">{modelChoices.length ? t('product.wizard.selectModel') : t('product.wizard.detectModelsFirst')}</option>{modelChoices.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select><small className="field-note">{t('product.wizard.modelSource')}</small></label>
        <label><span>{t('product.wizard.embedding')}</span><select value={embedding} onChange={(event) => { setEmbedding(event.target.value); clearPreview() }} disabled={!embeddingChoices.length}><option value="">{embeddingChoices.length ? t('product.wizard.selectEmbedding') : t('product.wizard.detectModelsFirst')}</option>{embeddingChoices.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select><small className="field-note">{t('product.wizard.embeddingSource')}</small></label>
        <label><span>{t('product.wizard.queryMode')}</span><select value={queryMode} onChange={(event) => { setQueryMode(event.target.value); clearPreview() }}><option value="">{t('product.wizard.queryModeDefault')}</option>{queryModes.map((item) => <option value={item} key={item}>{t(`product.wizard.queryMode.${item}` as MessageKey)}</option>)}</select><small className="field-note">{t('product.wizard.queryModeHelp')}</small></label>
      </div>
      {mode === 'advanced' && <DisclosureSection title={t('product.wizard.advancedConfig')} open><p className="field-note">{t('product.wizard.advancedHelp')}</p><div className="authoring-grid">
        <label><span>{t('product.wizard.candidateK')}</span><select value={candidateK} onChange={(event) => { setCandidateK(event.target.value); clearPreview() }}><option value="">{t('product.wizard.useSystemDefault')}</option>{[10, 20, 40, 80].map((value) => <option value={value} key={value}>{value}</option>)}</select></label>
        <label><span>{t('product.wizard.contextK')}</span><select value={contextK} onChange={(event) => { setContextK(event.target.value); clearPreview() }}><option value="">{t('product.wizard.useSystemDefault')}</option>{[1, 3, 5, 8, 10].map((value) => <option value={value} key={value}>{value}</option>)}</select></label>
        <label><span>{t('product.wizard.tokenBudget')}</span><select value={tokenBudget} onChange={(event) => { setTokenBudget(event.target.value); clearPreview() }}><option value="">{t('product.wizard.useSystemDefault')}</option>{[2048, 4096, 8192, 12000, 16384].map((value) => <option value={value} key={value}>{value.toLocaleString()}</option>)}</select></label>
        {isLightRAG && <label><span>{t('product.wizard.queryTimeout')}</span><input type="number" min="30" step="30" inputMode="numeric" value={queryTimeoutSeconds} onChange={(event) => { setQueryTimeoutSeconds(event.target.value); clearPreview() }} /><small className="field-note">{t('product.wizard.queryTimeoutHelp')}</small></label>}
        <label><span>{t('product.wizard.answerGeneration')}</span><select value={generateAnswer} onChange={(event) => { setGenerateAnswer(event.target.value); clearPreview() }}><option value="default">{t('product.wizard.useSystemDefault')}</option><option value="on">{t('product.wizard.answerGenerationOn')}</option><option value="off">{t('product.wizard.answerGenerationOff')}</option></select></label>
        <label><span>{t('product.wizard.metricRange')}</span><select value={metricPreset} onChange={(event) => { setMetricPreset(event.target.value); clearPreview() }}><option value="balanced">{t('product.wizard.metricBalanced')}</option><option value="quick">{t('product.wizard.metricQuick')}</option><option value="recall">{t('product.wizard.metricRecall')}</option></select></label>
        <label><span>{t('product.wizard.repetitions')}</span><select value={repetitions} onChange={(event) => { setRepetitions(event.target.value); clearPreview() }}>{[1, 3, 5, 10].map((value) => <option value={value} key={value}>{value}</option>)}</select></label>
        <label><span>{t('product.wizard.seed')}</span><input inputMode="numeric" value={seed} onChange={(event) => { setSeed(event.target.value); clearPreview() }} /><small className="field-note">{t('product.wizard.seedHelp')}</small></label>
      </div></DisclosureSection>}
      <div className="authoring-actions"><Button onClick={() => void previewSpec()} disabled={!validDataset || !system || !model || !embedding}>{t('product.wizard.review')}</Button><Button variant="primary" onClick={() => void run()} disabled={!preview}>{t('product.wizard.run')} <Play size={16} /></Button></div>
    </Surface>
    {message && <p className="product-message"><CheckCircle2 size={15} /> {message}</p>}
    {error && <ErrorBanner message={error} />}
    {preview && <DisclosureSection title={t('product.wizard.canonicalSpec')} open><pre className="canonical-spec">{JSON.stringify(preview, null, 2)}</pre></DisclosureSection>}
  </>
}
