import type {
  ArtifactCaseIndexViewV2,
  ArtifactCaseViewV2,
  ArtifactOverviewV2,
  ComparisonResponse,
  DatasetSummary,
  FormalCaseContent,
  FormalReleaseCaseIndexResponse,
  FormalReleaseContentResponse,
  FormalDatasetsResponse,
  FormalDocumentView,
  ExperimentSpec,
  JobRecord,
  RunManifest,
  SystemSummary,
  SystemProfile,
  ProductSystemSummary,
  SystemConnectionPayload,
  DatasetDraft,
  EvaluationDraft,
  AuthoringDataset,
  AuthoringTarget,
  AuthoringTargetPreview,
  AuthoringCandidate,
  AuthoringDiscoveryJob,
  AuthoringGenerationJob,
  AuthoringResolution,
  AuthoringExport,
  LLMConfigRevision,
  LLMProviderConfig,
  LLMStageBinding,
} from './types'

const API_ROOT = (import.meta.env.VITE_RAG_EVAL_API || 'http://127.0.0.1:8765/api/v1').replace(/\/$/, '')

// HTTP header values are Latin-1 only.  File names selected from a Chinese
// desktop therefore need an ASCII transport form; the API restores UTF-8
// before storing the original source name.
const uploadFilenameHeader = (filename: string) => `utf-8''${encodeURIComponent(filename)}`

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    })
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : String(cause)
    throw new Error(`${message} (${API_ROOT}${path})`)
  }
  if (!response.ok) {
    const body = await response.text()
    throw new Error(body || `${response.status} ${response.statusText}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; schema_version: number; producer: string; product_layer_enabled?: boolean }>('/health'),
  datasets: () => request<DatasetSummary[]>('/datasets'),
  formalDatasets: () => request<FormalDatasetsResponse>('/product/formal-datasets'),
  formalDatasetContent: (releaseId: string) => request<FormalReleaseContentResponse>(`/product/formal-datasets/${encodeURIComponent(releaseId)}/content`),
  formalDatasetCaseIndex: (releaseId: string) => request<FormalReleaseCaseIndexResponse>(`/product/formal-datasets/${encodeURIComponent(releaseId)}/cases`),
  formalDatasetCase: (releaseId: string, caseId: string) => request<FormalCaseContent>(`/product/formal-datasets/${encodeURIComponent(releaseId)}/cases/${encodeURIComponent(caseId)}`),
  formalDatasetDocument: (releaseId: string) => request<FormalDocumentView>(`/product/formal-datasets/${encodeURIComponent(releaseId)}/document`),
  formalDatasetSourceUrl: (releaseId: string) => `${API_ROOT}/product/formal-datasets/${encodeURIComponent(releaseId)}/source`,
  formalDatasetNativeDocumentUrl: (releaseId: string) => `${API_ROOT}/product/formal-datasets/${encodeURIComponent(releaseId)}/document/native`,
  deleteFormalDataset: (releaseId: string) => request<{ release_id: string; deleted: boolean }>(`/product/formal-datasets/${encodeURIComponent(releaseId)}`, { method: 'DELETE' }),
  registerDataset: (path: string) => request<{ bundle_id: string }>('/datasets', {
    method: 'POST', body: JSON.stringify({ path }),
  }),
  systems: () => request<SystemSummary[]>('/systems'),
  experiments: () => request<ExperimentSpec[]>('/experiments'),
  createExperiment: (spec: ExperimentSpec) => request<ExperimentSpec>('/experiments', {
    method: 'POST', body: JSON.stringify(spec),
  }),
  queueRun: (experimentId: string) => request<JobRecord>(`/experiments/${encodeURIComponent(experimentId)}/runs`, { method: 'POST' }),
  jobs: () => request<JobRecord[]>('/jobs'),
  cancelJob: (jobId: string) => request<JobRecord>(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' }),
  runs: () => request<RunManifest[]>('/runs'),
  run: (runId: string) => request<RunManifest>(`/runs/${encodeURIComponent(runId)}`),
  summary: (runId: string) => request<ArtifactOverviewV2>(`/runs/${encodeURIComponent(runId)}/summary`),
  cases: (runId: string) => request<{ cases: ArtifactCaseViewV2[] }>(`/runs/${encodeURIComponent(runId)}/cases`),
  caseIndex: (runId: string) => request<ArtifactCaseIndexViewV2>(`/runs/${encodeURIComponent(runId)}/cases/index`),
  case: (runId: string, caseId: string, repetition: number) => request<ArtifactCaseViewV2>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}?repetition=${encodeURIComponent(repetition)}`),
  reviewCase: (runId: string, caseId: string, repetition: number, payload: { verdict: 'correct' | 'incorrect' | 'needs_review'; reviewer: string; note: string }) => request<import('./types').CaseReview>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/review?repetition=${encodeURIComponent(repetition)}`, { method: 'POST', body: JSON.stringify(payload) }),
  semanticReviewCase: (runId: string, caseId: string, repetition: number) => request<import('./types').CaseReview>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/semantic-review?repetition=${encodeURIComponent(repetition)}`, { method: 'POST', body: JSON.stringify({}) }),
  reviewAnswerSupport: (runId: string, caseId: string, repetition: number, payload: { verdict: 'supported' | 'unsupported' | 'needs_review'; reviewer: string; note: string }) => request<import('./types').AnswerSupportReview>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/answer-support-review?repetition=${encodeURIComponent(repetition)}`, { method: 'POST', body: JSON.stringify(payload) }),
  semanticReviewAnswerSupport: (runId: string, caseId: string, repetition: number) => request<import('./types').AnswerSupportReview>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/semantic-answer-support-review?repetition=${encodeURIComponent(repetition)}`, { method: 'POST', body: JSON.stringify({}) }),
  renameRun: (runId: string, payload: { display_name: string; actor?: string; note?: string }) => request<{ run: RunManifest; presentation: { history: Array<Record<string, unknown>> } }>(`/runs/${encodeURIComponent(runId)}/presentation`, { method: 'PUT', body: JSON.stringify(payload) }),
  verify: (runId: string) => request<{ valid: boolean; missing: string[]; unexpected: string[]; mismatched: string[] }>(`/runs/${encodeURIComponent(runId)}/artifacts/verify`),
  compare: (runIds: string[], tier: string) => request<ComparisonResponse>('/comparisons/validate', {
    method: 'POST', body: JSON.stringify({ run_ids: runIds, tier }),
  }),
  productStatus: () => request<{ enabled: boolean }>('/product/status'),
  llmConfig: () => request<LLMConfigRevision>('/product/llm/config'),
  saveLlmConfig: (payload: { providers: Array<Pick<LLMProviderConfig, 'provider_id' | 'display_name' | 'kind' | 'endpoint' | 'model' | 'embedding_model' | 'enabled'>>; bindings: LLMStageBinding[]; actor: string; reason: string; secrets?: Record<string, string> }) => request<LLMConfigRevision>('/product/llm/config', {
    method: 'PUT', body: JSON.stringify(payload),
  }),
  testLlmProvider: (providerId: string) => request<LLMProviderConfig>(`/product/llm/providers/${encodeURIComponent(providerId)}/health`, { method: 'POST' }),
  measureLlmProviderLatency: (providerId: string) => request<LLMProviderConfig>(`/product/llm/providers/${encodeURIComponent(providerId)}/speed`, { method: 'POST' }),
  profiles: () => request<SystemProfile[]>('/product/profiles'),
  productSystems: () => request<ProductSystemSummary[]>('/product/systems'),
  saveProductSystem: (connection: SystemConnectionPayload, secrets: Record<string, string> = {}) => request<ProductSystemSummary>('/product/systems', {
    method: 'POST', body: JSON.stringify({ connection, secrets }),
  }),
  deleteProductSystem: (systemId: string) => request<{ system_id: string; deleted: boolean; previous_execution_provider: string; secret_keys: string[] }>(`/product/systems/${encodeURIComponent(systemId)}`, { method: 'DELETE' }),
  removeProductSystemSecret: (systemId: string, environmentKey: string) => request<{ system_id: string; secret_keys: string[]; configured: boolean }>(`/product/systems/${encodeURIComponent(systemId)}/secrets/${encodeURIComponent(environmentKey)}`, { method: 'DELETE' }),
  testProductSystem: (systemId: string) => request<{ status: string; system_id: string; adapter_id: string; execution_provider: string }>(`/product/systems/${encodeURIComponent(systemId)}/test`, { method: 'POST' }),
  uploadDataset: async (file: File) => {
    let response: Response
    try {
      response = await fetch(`${API_ROOT}/product/datasets/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/zip', 'X-RAG-EVAL-Filename': uploadFilenameHeader(file.name) },
        body: file,
      })
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause)
      throw new Error(`${message} (${API_ROOT}/product/datasets/upload)`)
    }
    if (!response.ok) throw new Error(await response.text())
    return response.json() as Promise<{ bundle_id: string }>
  },
  saveDatasetDraft: (draft: DatasetDraft) => request<DatasetDraft>('/product/dataset-drafts', {
    method: 'POST', body: JSON.stringify(draft),
  }),
  sealDatasetDraft: (draftId: string) => request<{ bundle_id: string; sealed: boolean }>(`/product/dataset-drafts/${encodeURIComponent(draftId)}/seal`, { method: 'POST' }),
  authoringDatasets: () => request<AuthoringDataset[]>('/authoring/datasets'),
  uploadAuthoringDocument: async (file: File) => {
    let response: Response
    try {
      response = await fetch(`${API_ROOT}/authoring/datasets`, { method: 'POST', headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'X-RAG-EVAL-Filename': uploadFilenameHeader(file.name) }, body: file })
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause)
      throw new Error(`${message} (${API_ROOT}/authoring/datasets)`)
    }
    if (!response.ok) throw new Error(await response.text())
    return response.json() as Promise<AuthoringDataset>
  },
  analyzeAuthoringDocument: (datasetId: string) => request<AuthoringDataset>(`/authoring/datasets/${encodeURIComponent(datasetId)}/analyze`, { method: 'POST' }),
  authoringSourceUrl: (datasetId: string) => `${API_ROOT}/authoring/datasets/${encodeURIComponent(datasetId)}/source`,
  authoringDocument: (datasetId: string) => request<FormalDocumentView>(`/authoring/datasets/${encodeURIComponent(datasetId)}/document`),
  authoringNativeDocumentUrl: (datasetId: string) => `${API_ROOT}/authoring/datasets/${encodeURIComponent(datasetId)}/document/native`,
  authoringTargets: (datasetId: string) => request<AuthoringTarget[]>(`/authoring/datasets/${encodeURIComponent(datasetId)}/targets`),
  authoringTargetPreview: (datasetId: string, targetId: string) => request<AuthoringTargetPreview>(`/authoring/datasets/${encodeURIComponent(datasetId)}/targets/${encodeURIComponent(targetId)}/preview`),
  discoverAuthoringTargets: (datasetId: string, provider: 'rule' | 'ollama' | 'remote' = 'ollama') => request<AuthoringTarget[]>(`/authoring/datasets/${encodeURIComponent(datasetId)}/targets/discover`, { method: 'POST', body: JSON.stringify({ provider }) }),
  authoringDiscoveryJobs: (datasetId: string) => request<AuthoringDiscoveryJob[]>(`/authoring/datasets/${encodeURIComponent(datasetId)}/discovery-jobs`),
  createAuthoringDiscoveryJob: (datasetId: string, provider: 'rule' | 'ollama' | 'remote' = 'ollama') => request<AuthoringDiscoveryJob>(`/authoring/datasets/${encodeURIComponent(datasetId)}/discovery-jobs`, { method: 'POST', body: JSON.stringify({ provider }) }),
  retryAuthoringDiscoveryJob: (datasetId: string, jobId: string) => request<AuthoringDiscoveryJob>(`/authoring/datasets/${encodeURIComponent(datasetId)}/discovery-jobs/${encodeURIComponent(jobId)}/retry`, { method: 'POST' }),
  authoringCandidates: (datasetId: string) => request<AuthoringCandidate[]>(`/authoring/datasets/${encodeURIComponent(datasetId)}/candidates`),
  createAuthoringQuestion: (datasetId: string, targetId: string, question: string) => request<AuthoringCandidate>(`/authoring/datasets/${encodeURIComponent(datasetId)}/candidates`, { method: 'POST', body: JSON.stringify({ target_id: targetId, question }) }),
  generateAuthoringProposal: (datasetId: string, targetId: string, provider: 'ollama' | 'remote' = 'ollama') => request<AuthoringCandidate>(`/authoring/datasets/${encodeURIComponent(datasetId)}/candidates/generate-proposal`, { method: 'POST', body: JSON.stringify({ target_id: targetId, provider }) }),
  authoringGenerationJobs: (datasetId: string) => request<AuthoringGenerationJob[]>(`/authoring/datasets/${encodeURIComponent(datasetId)}/generation-jobs`),
  createAuthoringGenerationJob: (datasetId: string, targetIds: string[], provider: 'ollama' | 'remote' = 'ollama') => request<AuthoringGenerationJob>(`/authoring/datasets/${encodeURIComponent(datasetId)}/generation-jobs`, { method: 'POST', body: JSON.stringify({ target_ids: targetIds, provider }) }),
  cancelAuthoringGenerationJob: (datasetId: string, jobId: string) => request<AuthoringGenerationJob>(`/authoring/datasets/${encodeURIComponent(datasetId)}/generation-jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' }),
  retryAuthoringGenerationJob: (datasetId: string, jobId: string, targetIds?: string[]) => request<AuthoringGenerationJob>(`/authoring/datasets/${encodeURIComponent(datasetId)}/generation-jobs/${encodeURIComponent(jobId)}/retry`, { method: 'POST', body: JSON.stringify(targetIds?.length ? { target_ids: targetIds } : {}) }),
  resolveAuthoringCandidate: (datasetId: string, candidateId: string, resolution: AuthoringResolution) => request<AuthoringCandidate>(`/authoring/datasets/${encodeURIComponent(datasetId)}/candidates/${encodeURIComponent(candidateId)}/resolve`, { method: 'POST', body: JSON.stringify({ resolution }) }),
  generateAuthoringAnswer: (datasetId: string, candidateId: string, provider: 'ollama' | 'remote' = 'ollama') => request<AuthoringCandidate>(`/authoring/datasets/${encodeURIComponent(datasetId)}/candidates/${encodeURIComponent(candidateId)}/resolve/generate`, { method: 'POST', body: JSON.stringify({ provider }) }),
  reviewAuthoringCandidate: (datasetId: string, candidateId: string, decision: 'accept' | 'edit' | 'reject', reviewer: string, note = '', editedQuestion?: string, editedResolution?: AuthoringResolution) => request<AuthoringCandidate>(`/authoring/datasets/${encodeURIComponent(datasetId)}/candidates/${encodeURIComponent(candidateId)}/review`, { method: 'POST', body: JSON.stringify({ decision, reviewer, note, ...(editedQuestion === undefined ? {} : { edited_question: editedQuestion }), ...(editedResolution === undefined ? {} : { edited_resolution: editedResolution }) }) }),
  exportAuthoringDataset: (datasetId: string, name: string, version: string) => request<AuthoringExport>(`/authoring/datasets/${encodeURIComponent(datasetId)}/exports`, { method: 'POST', body: JSON.stringify({ name, version }) }),
  registerAuthoringExport: (datasetId: string, releaseId: string, view: 'canonical-text' | 'native-docx') => request<{ bundle_id: string; export: AuthoringExport }>(`/authoring/datasets/${encodeURIComponent(datasetId)}/exports/${encodeURIComponent(releaseId)}/register/${encodeURIComponent(view)}`, { method: 'POST' }),
  publishAuthoringFormalRelease: (datasetId: string, displayName: string, releaseVersion: string, actor: string) => request<{ release_id: string; dataset_id: string; name: string | null; version: string; case_count: number; gold_count: number }>(`/authoring/datasets/${encodeURIComponent(datasetId)}/formal-releases`, { method: 'POST', body: JSON.stringify({ display_name: displayName, release_version: releaseVersion, actor }) }),
  archiveAuthoringDataset: (datasetId: string) => request<AuthoringDataset>(`/authoring/datasets/${encodeURIComponent(datasetId)}/archive`, { method: 'POST' }),
  deleteAuthoringDataset: (datasetId: string) => request<void>(`/authoring/datasets/${encodeURIComponent(datasetId)}`, { method: 'DELETE' }),
  evaluationDrafts: () => request<EvaluationDraft[]>('/product/evaluation-drafts'),
  saveEvaluationDraft: (draft: EvaluationDraft) => request<EvaluationDraft>('/product/evaluation-drafts', {
    method: 'POST', body: JSON.stringify(draft),
  }),
  previewEvaluationDraft: (draftId: string) => request<ExperimentSpec>(`/product/evaluation-drafts/${encodeURIComponent(draftId)}/preview`),
  finalizeEvaluationDraft: (draftId: string) => request<{ experiment: ExperimentSpec; job?: JobRecord }>(`/product/evaluation-drafts/${encodeURIComponent(draftId)}/finalize`, {
    method: 'POST', body: JSON.stringify({ queue: true }),
  }),
}
