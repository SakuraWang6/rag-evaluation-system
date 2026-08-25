import type {
  CaseResult,
  ComparisonResponse,
  DatasetSummary,
  ExperimentSpec,
  JobRecord,
  RunManifest,
  RunSummary,
  SystemSummary,
  SystemProfile,
  ProductSystemSummary,
  SystemConnectionPayload,
  DatasetDraft,
  EvaluationDraft,
} from './types'

const API_ROOT = (import.meta.env.VITE_RAG_EVAL_API || 'http://127.0.0.1:8765/api/v1').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(body || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; schema_version: number; producer: string; product_layer_enabled?: boolean }>('/health'),
  datasets: () => request<DatasetSummary[]>('/datasets'),
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
  summary: (runId: string) => request<RunSummary>(`/runs/${encodeURIComponent(runId)}/summary`),
  cases: (runId: string) => request<CaseResult[]>(`/runs/${encodeURIComponent(runId)}/cases`),
  verify: (runId: string) => request<{ valid: boolean; missing: string[]; unexpected: string[]; mismatched: string[] }>(`/runs/${encodeURIComponent(runId)}/artifacts/verify`),
  compare: (runIds: string[], tier: string) => request<ComparisonResponse>('/comparisons/validate', {
    method: 'POST', body: JSON.stringify({ run_ids: runIds, tier }),
  }),
  productStatus: () => request<{ enabled: boolean }>('/product/status'),
  profiles: () => request<SystemProfile[]>('/product/profiles'),
  productSystems: () => request<ProductSystemSummary[]>('/product/systems'),
  saveProductSystem: (connection: SystemConnectionPayload, secrets: Record<string, string> = {}) => request<ProductSystemSummary>('/product/systems', {
    method: 'POST', body: JSON.stringify({ connection, secrets }),
  }),
  removeProductSystemSecret: (systemId: string, environmentKey: string) => request<{ system_id: string; secret_keys: string[]; configured: boolean }>(`/product/systems/${encodeURIComponent(systemId)}/secrets/${encodeURIComponent(environmentKey)}`, { method: 'DELETE' }),
  testProductSystem: (systemId: string) => request<{ status: string; system_id: string; adapter_id: string; execution_provider: string }>(`/product/systems/${encodeURIComponent(systemId)}/test`, { method: 'POST' }),
  uploadDataset: async (file: File) => {
    const response = await fetch(`${API_ROOT}/product/datasets/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip', 'X-RAG-EVAL-Filename': file.name },
      body: file,
    })
    if (!response.ok) throw new Error(await response.text())
    return response.json() as Promise<{ bundle_id: string }>
  },
  registerLocalDataset: (path: string) => request<{ bundle_id: string }>('/product/datasets/local-path', {
    method: 'POST', body: JSON.stringify({ path }),
  }),
  datasetDrafts: () => request<DatasetDraft[]>('/product/dataset-drafts'),
  saveDatasetDraft: (draft: DatasetDraft) => request<DatasetDraft>('/product/dataset-drafts', {
    method: 'POST', body: JSON.stringify(draft),
  }),
  validateDatasetDraft: (draftId: string) => request<{ valid: boolean }>(`/product/dataset-drafts/${encodeURIComponent(draftId)}/validate`, { method: 'POST' }),
  sealDatasetDraft: (draftId: string) => request<{ bundle_id: string; sealed: boolean }>(`/product/dataset-drafts/${encodeURIComponent(draftId)}/seal`, { method: 'POST' }),
  evaluationDrafts: () => request<EvaluationDraft[]>('/product/evaluation-drafts'),
  saveEvaluationDraft: (draft: EvaluationDraft) => request<EvaluationDraft>('/product/evaluation-drafts', {
    method: 'POST', body: JSON.stringify(draft),
  }),
  previewEvaluationDraft: (draftId: string) => request<ExperimentSpec>(`/product/evaluation-drafts/${encodeURIComponent(draftId)}/preview`),
  finalizeEvaluationDraft: (draftId: string) => request<{ experiment: ExperimentSpec; job?: JobRecord }>(`/product/evaluation-drafts/${encodeURIComponent(draftId)}/finalize`, {
    method: 'POST', body: JSON.stringify({ queue: true }),
  }),
}
