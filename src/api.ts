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
  health: () => request<{ status: string; schema_version: number; producer: string }>('/health'),
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
}
