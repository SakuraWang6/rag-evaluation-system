export type MetricStatus = 'observed' | 'unavailable' | 'not_applicable' | 'error' | 'needs_review'

export interface MetricResult {
  metric_id: string
  status: MetricStatus
  value: number | null
  numerator: number | null
  denominator: number | null
  scorer_id: string
  scorer_version: string
  scorer_digest: string
  evaluator_mode: string | null
  reason: string | null
}

export interface EvidenceItem {
  item_id: string
  rank: number
  content: string
  document_id: string | null
  locator: Record<string, unknown> | null
  score: number | null
  token_count: number | null
  native_id: string | null
  metadata: Record<string, unknown>
}

export interface RAGResult {
  answer: string | null
  raw_retrieval: EvidenceItem[] | null
  ranked_retrieval: EvidenceItem[] | null
  final_context: EvidenceItem[] | null
  latency: Record<string, number> | null
  token_usage: Record<string, number> | null
}

export interface CaseResult {
  case_id: string
  repetition: number
  seed: number
  status: 'completed' | 'timeout' | 'system_error' | 'cancelled'
  question: string
  gold_answer: { kind: string; canonical: string | string[] | null; unit?: string | null } | null
  gold_evidence_set: {
    required_groups: string[][]
    evidence: Array<{
      evidence_id: string
      document_id: string
      canonical_value: string | null
      quote_anchor: string | null
      locator: Record<string, unknown>
    }>
  } | null
  rag_result: RAGResult | null
  metrics: MetricResult[]
  error: { code: string; message: string; retryable: boolean } | null
  failure_assessment: {
    labels: string[]
    certainty: 'deterministic' | 'reviewed' | 'unknown'
    reasons: string[]
    review_required: boolean
  } | null
}

export interface RunManifest {
  run_id: string
  experiment_id: string
  status: string
  bundle_id: string
  case_selection_id: string
  adapter_id: string
  adapter_version: string
  system_id: string
  system_version: string
  scorer_id: string
  scorer_version: string
  scorer_digest: string
  started_at: string
  completed_at: string | null
  repetitions: number
  repetition_seeds: number[]
  execution_counts: Record<string, number>
  effective_config: Record<string, unknown>
  replay_of_run_id: string | null
  artifact_checksums: Record<string, string>
}

export interface SummaryMetric {
  status: string
  value: number | null
  mean?: number
  standard_deviation?: number
  denominator: number
  errors?: number
  coverage?: number
  status_counts?: Record<string, number>
  repetition_values?: number[]
}

export interface RunSummary {
  metrics: Record<string, SummaryMetric>
  execution: Record<string, number>
}

export interface DatasetSummary {
  bundle_id: string
  name: string
  version: string
  cases: number
}

export interface SystemProfile {
  profile_id: 'lightrag' | 'rag-anything'
  profile_version: string
  display_name: string
  system_id: string
  adapter_id: string
  default_logical_endpoint: string
  docker_available: boolean
}

export interface ProductSystemSummary {
  system_id: string
  display_name: string
  profile_id: string
  profile_version: string
  execution_provider: 'local' | 'docker'
  logical_endpoint_ref: string
  secret_keys: string[]
  configured: boolean
  connection_test_status: 'not_tested' | 'passed' | 'failed'
  last_connection_tested_at: string | null
  updated_at: string
}

export interface SystemConnectionPayload {
  system_id: string
  display_name: string
  profile_id: string
  profile_version: string
  execution_provider: 'local' | 'docker'
  logical_endpoint_ref: string
  python_executable?: string
  non_secret_environment?: Record<string, string>
  secret_bindings?: Record<string, string>
  adapter_overrides?: Record<string, unknown>
  query_overrides?: Record<string, unknown>
  metric_overrides?: Record<string, unknown>
  request_timeout_seconds?: number
}

export interface DatasetDraftDocument {
  document_id: string
  filename: string
  content: string
}

export interface DatasetDraftCase {
  case_id: string
  question: string
  gold_answer: string
  document_id: string
  span_start: number
  span_end: number
}

export interface DatasetDraft {
  draft_id?: string
  name: string
  version: string
  documents: DatasetDraftDocument[]
  cases: DatasetDraftCase[]
}

export interface EvaluationDraft {
  draft_id?: string
  mode: 'basic' | 'advanced'
  bundle_id: string | null
  system_id: string | null
  profile_id: string | null
  profile_version: string | null
  display_name: string
  adapter_overrides: Record<string, unknown>
  query_overrides: Record<string, unknown>
  metric_overrides: Record<string, unknown>
  case_ids: string[] | null
  seed: number
  repetitions: number
  formal: boolean
}

export interface SystemSummary {
  system_id: string
  adapter_id: string
  adapter_factory: string
  python_executable: string
  environment_keys: string[]
  request_timeout_seconds: number
  description: string
}

export interface ExperimentSpec {
  experiment_id: string
  bundle_id: string
  system_id: string
  adapter_id: string
  adapter_config: Record<string, unknown>
  query_config: Record<string, unknown>
  metric_config: Record<string, unknown>
  case_ids: string[] | null
  case_selection_id: string
  seed: number
  repetitions: number
}

export interface JobRecord {
  job_id: string
  status: string
  run_id: string | null
  error: string | null
  updated_at: string
  experiment: ExperimentSpec
}

export interface ComparisonResponse {
  tier: 'task_comparable' | 'strict_controlled' | 'exploratory'
  compatible: boolean
  reasons: string[]
  may_declare_winner: boolean
  metric_decisions: Array<{
    metric_id: string
    comparable: boolean
    reasons: string[]
    coverage_by_run: Record<string, number>
    winner_eligible: boolean
  }>
  runs: Array<{ run: RunManifest; summary: RunSummary }>
}
