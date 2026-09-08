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
  review: CaseReview | null
  answer_support_review?: AnswerSupportReview | null
  historical_rescore?: HistoricalRescore | null
  answer_judgment: AnswerJudgment
  evidence_judgment: EvidenceJudgment
}

export type AnswerJudgment = 'correct' | 'incorrect' | 'needs_review' | 'unavailable'
export type EvidenceJudgment = 'grounded' | 'missing' | 'ungrounded' | 'unverifiable' | 'needs_review' | 'unavailable'

export interface CaseReviewDecision {
  revision: number
  verdict: AnswerJudgment
  source: 'human' | 'llm'
  reviewer: string
  note: string
  created_at: string
  model: string | null
  prompt_digest: string | null
}

export interface CaseReview {
  run_id: string
  case_id: string
  repetition: number
  latest: CaseReviewDecision | null
  history: CaseReviewDecision[]
}

export type AnswerSupportVerdict = 'supported' | 'unsupported' | 'needs_review'

export interface AnswerSupportReviewDecision {
  revision: number
  verdict: AnswerSupportVerdict
  source: 'human' | 'llm'
  reviewer: string
  note: string
  created_at: string
  model: string | null
  prompt_digest: string | null
}

export interface AnswerSupportReview {
  run_id: string
  case_id: string
  repetition: number
  latest: AnswerSupportReviewDecision | null
  history: AnswerSupportReviewDecision[]
}

export interface CaseListItem {
  case_id: string
  repetition: number
  seed: number
  status: 'completed' | 'timeout' | 'system_error' | 'cancelled'
  question: string
  answer_judgment: AnswerJudgment
  evidence_judgment: EvidenceJudgment
  review?: CaseReview | null
}

export interface RunManifest {
  run_id: string
  experiment_id: string
  display_name?: string | null
  display_name_source?: 'manifest' | 'override' | 'generated' | string
  execution_view?: string | null
  diagnostic_only?: boolean
  status: string
  bundle_id: string
  dataset_release_id?: string | null
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
  numerator?: number
  errors?: number
  coverage?: number
  status_counts?: Record<string, number>
  repetition_values?: number[]
  reason?: string | null
}

export interface RunDatasetIdentity {
  name: string
  version: string | null
  case_count: number | null
  selected_case_count: number
  resolution: 'formal_release' | 'bundle_manifest' | 'unresolved' | string
  dataset_id: string | null
  release_id: string | null
  bundle_id: string
}

export interface LocalizationStageSummary {
  matched: number
  partial: number
  retrieval_missed: number
  provenance_missing: number
  denominator: number
  observed_cases: number
  unavailable_cases: number
  coverage: number
  status: 'observed' | 'unavailable' | string
  reason: string | null
}

export interface LocalizationSummary {
  scope: 'selected_path_clauses' | string
  stages: Record<'raw' | 'ranked' | 'context', LocalizationStageSummary>
}

export interface HistoricalRescore {
  status: string
  source_rescore_status?: string
  rescore_identity: string
  method: string
  source_artifacts_verified: boolean
  note: string
  acceptance?: {
    reviewer?: string | null
    reviewed_at?: string | null
    scope?: { limitations?: string[]; worker_runtime_verified?: boolean } | null
  }
  diagnostic_matrix: {
    decision_count?: number
    status_counts?: Record<string, number>
    by_stage?: Record<string, Record<string, number>>
  }
}

export interface SemanticReviewStatus {
  schema_version: number
  run_id: string
  state: 'not_started' | 'not_configured' | 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'skipped' | string
  candidate_count: number
  processed_count: number
  adjudicated_count: number
  needs_human_count: number
  error_count: number
  detail: string | null
  started_at: string | null
  completed_at: string | null
}

export interface RunSummary {
  metrics: Record<string, SummaryMetric>
  execution: Record<string, number>
  dataset?: RunDatasetIdentity
  localization?: LocalizationSummary
  historical_rescore?: HistoricalRescore | null
  semantic_review?: SemanticReviewStatus | null
  semantic_support_review?: SemanticReviewStatus | null
  presentation?: { kind: string; raw_summary_available: boolean; notes: string[] }
  judgments?: {
    answer: Record<AnswerJudgment, number>
    answer_support: Record<AnswerSupportVerdict | 'unavailable', number>
    evidence: Record<EvidenceJudgment, number>
  }
}

export interface DatasetSummary {
  bundle_id: string
  name: string
  version: string
  cases: number
}

export interface FormalDatasetReleaseSummary {
  release_id: string
  dataset_id: string
  name: string
  version: string
  release_digest: string
  parent_release_id: string | null
  case_count: number
  gold_count: number
  canonical_digest: string
  validation_report_digest: string
  runnable: boolean
  runtime_reason: string | null
}

export interface FormalBundleV3Summary {
  bundle_id: string
  target_release_id: string
  dataset_id: string
  case_count: number
  gold_count: number
  evidence_count: number
  runnable: boolean
  visibility: string
}

export interface FormalDatasetsResponse {
  releases: FormalDatasetReleaseSummary[]
  bundles_v3: FormalBundleV3Summary[]
}

export interface FormalCanonicalObjectView {
  object_id: string
  document_id: string
  object_type: string
  representation_status: string
  document_order: number
  canonical_value: string | null
  provenance: {
    source_sha256: string
    parser_identity: string
    canonicalizer_identity: string
    configuration_digest: string
    extraction_method: string
    source_spans: Array<Record<string, unknown>>
    derived_from_object_ids: string[]
  }
  attributes: Record<string, unknown>
}

export interface FormalEvidenceView {
  evidence_id: string
  canonical_object_id: string
  role: string
  rationale: string | null
  reachable: boolean
  canonical: FormalCanonicalObjectView | null
}

export interface FormalMsesPathView {
  path_id: string
  clauses: Array<{ clause_id: string; alternatives: string[] }>
}

export interface FormalGoldContent {
  gold_id: string
  gold_revision_id: string
  revision: number
  lifecycle: string
  answer: {
    kind: string
    canonical: string | string[] | null
    accepted_values: string[]
    locale: string | null
    unit: string | null
    tolerance: string | null
  }
  evidence: FormalEvidenceView[]
  mses_paths: FormalMsesPathView[]
  dependencies: Array<{ dependency_id: string; depends_on: string[]; description: string }>
  negative_scope_object_ids: string[]
  negative_rationale: string | null
  origin: Record<string, unknown>
  actor: string
  reason: string
  lineage: {
    reviews: Array<Record<string, unknown>>
    approvals: Array<Record<string, unknown>>
    adjudications: Array<Record<string, unknown>>
  }
}

export interface FormalCaseContent {
  case_id: string
  case_revision_id: string
  revision: number
  lifecycle: string
  question: string
  language: string
  target_id: string
  source_object_ids: string[]
  source_digest: string
  canonical_contract_digest: string | null
  origin: Record<string, unknown>
  actor: string
  reason: string
  gold: FormalGoldContent
  relation_context: Array<{
    relation_id: string
    relation_type: string
    source_object_id: string
    target_object_id: string
    attributes: Record<string, unknown>
  }>
  lineage: {
    reviews: Array<Record<string, unknown>>
    approvals: Array<Record<string, unknown>>
    adjudications: Array<Record<string, unknown>>
  }
}

export interface FormalReleaseContentResponse {
  release: {
    release_id: string
    dataset_id: string
    version: string
    release_digest: string
    parent_release_id: string | null
    canonical_digest: string
    source_digest: string
    validation_report_digest: string
    case_count: number
    gold_count: number
    canonical_schema_version: string
  }
  cases: FormalCaseContent[]
}

export interface FormalCaseListItem {
  case_id: string
  question: string
  language: string
  lifecycle: string
}

export interface FormalReleaseCaseIndexResponse {
  release: FormalReleaseContentResponse['release']
  cases: FormalCaseListItem[]
}

export interface FormalDocumentCell {
  text: string
  row: number
  column: number
  row_span: number
  column_span: number
  object_ids: string[]
}

export interface FormalDocumentBlock {
  block_id: string
  kind: string
  text: string
  document_order: number
  object_ids: string[]
  cells: FormalDocumentCell[]
  heading_level: number | null
  page_break_before: boolean
  list_level: number | null
}

export interface FormalDocumentView {
  document_id: string
  filename: string
  blocks: FormalDocumentBlock[]
}

export interface SystemProfile {
  profile_id: string
  profile_version: string
  display_name: string
  system_id: string
  adapter_id: string
  default_logical_endpoint: string
  docker_available: boolean
  query_modes: string[]
  query_timeout_min_seconds: number | null
}

export type ArtifactViewAvailability = 'available' | 'legacy_unavailable' | 'corrupted'
export type ObservationStatus = 'observed' | 'unsupported' | 'unobserved' | 'failed' | 'corrupted'
export type ObservationCompleteness = 'complete' | 'truncated' | 'partial' | 'unknown'
export type ArtifactMetricStatus = 'observed' | 'unavailable'

export interface ArtifactVerification {
  valid: boolean
  missing: string[]
  unexpected: string[]
  mismatched: string[]
  invalid_models?: string[]
}

export interface MetricDescriptorV2 {
  metric_id: string
  scorer_id: string
  scorer_version: string
  scorer_digest: string
  aggregation: string
  stage: 'candidate' | 'ranked' | 'context' | null
  cutoff: number | null
  candidate_cutoff: number
  ranked_cutoff: number
  context_budget: number
}

export interface MetricDescriptorBindingV2 {
  metric_id: string
  descriptor_digest: string
  descriptor: MetricDescriptorV2
}

export interface AggregateMetricV2 {
  metric_id: string
  status: ArtifactMetricStatus
  value: number | null
  case_count: number
  observed_case_count: number
  unavailable_case_count: number
  descriptor_digests: string[]
  reason: string | null
}

export interface EvaluationMetricV2 {
  metric_id: string
  status: ArtifactMetricStatus
  value: number | null
  lower_bound: number
  upper_bound: number
  descriptor: MetricDescriptorV2
  reason: string | null
}

export interface ArtifactJudgmentV2 {
  status: 'observed' | 'needs_review' | 'unavailable'
  value: string | null
  reason: string | null
}

export interface ArtifactEvidenceJudgmentV2 {
  status: 'observed' | 'unavailable'
  value: 'complete' | 'partial' | 'missing' | null
  reason: string | null
}

export interface ObservedStageItemV2 {
  native_chunk_id: string
  native_rank: number
  runtime_score: number | null
  content_sha256: string
  content: string | null
  provenance_edge_ids: string[]
  metadata: Record<string, unknown>
}

export interface StageObservationV2 {
  stage: 'candidate' | 'ranked' | 'context'
  observation_status: ObservationStatus
  completeness: ObservationCompleteness
  configured_cutoff: number | null
  proven_prefix_depth: number | null
  items: ObservedStageItemV2[]
  reason: string | null
  diagnostics: Record<string, unknown>
}

export interface ContentObservationV2 {
  observation_status: ObservationStatus
  completeness: ObservationCompleteness
  content: string | null
  content_sha256: string | null
  reason: string | null
}

export interface RunArtifactCaseV2 {
  schema_version: '2.0'
  case_id: string
  repetition: number
  seed: number
  status: string
  question: string
  gold_answer: { kind: string; canonical: string | string[] | null; unit?: string | null }
  gold_evidence_set: {
    gold_evidence_set_id: string
    required_groups: string[][]
    mses_paths: string[][][] | null
    source_identities: unknown[]
    evidence: Array<{
      evidence_id: string
      document_id: string
      canonical_object_id?: string | null
      canonical_value?: string | null
      quote_anchor?: string | null
      locator?: Record<string, unknown>
    }>
  }
  trace_validation: { status: ObservationStatus; reason: string | null; wire_shadow_verified: boolean }
  adapter_result: {
    protocol_version: '2.0'
    adapter_id: string
    adapter_version: string
    system_id: string
    system_version: string
    trace: {
      runtime_profile: { profile_id: string; system_id: string; system_version: string; configuration_digest: string }
      observation_profile: { profile_id: string; adapter_id: string; adapter_version: string; profile_digest: string }
      ingestion_catalog: { observation_status: ObservationStatus; completeness: ObservationCompleteness; items: unknown[]; reason: string | null }
      raw_retrieval: StageObservationV2
      ranked_retrieval: StageObservationV2
      final_context: StageObservationV2
      prompt_trace: ContentObservationV2
      answer: ContentObservationV2
      transformations: unknown[]
      mapping_diagnostics: unknown[]
      trace_digest: string
    }
  } | null
  evaluation: {
    scorer_id: string
    scorer_version: string
    scorer_digest: string
    metrics: EvaluationMetricV2[]
    localizations: Array<Record<string, unknown>>
    pipeline_deltas: Array<Record<string, unknown>>
    failure: { kind: string; cutoff: number | null; reason: string; proof_subjects: string[] } | null
  }
  answer_judgment: ArtifactJudgmentV2
  evidence_judgment: ArtifactEvidenceJudgmentV2
  error: { code: string; message: string; retryable: boolean } | null
}

export interface ArtifactOverviewV2 {
  schema_version: '1.0'
  run_id: string
  artifact_contract_version: '2.0' | '1.2'
  availability: ArtifactViewAvailability
  reason: string | null
  verification: ArtifactVerification | null
  manifest: {
    benchmark_identity: { dataset_release_id: string; benchmark_snapshot_digest: string; source_identities: unknown[] }
    runtime_profiles: Array<{ profile_id: string; system_id: string; system_version: string; configuration_digest: string }>
    observation_profiles: Array<{ profile_id: string; adapter_id: string; adapter_version: string; profile_digest: string }>
    artifact_digest: string
  } | null
  summary: {
    case_count: number
    execution_status_counts: Record<string, number>
    metrics: AggregateMetricV2[]
    leaderboard_eligibility: {
      eligible: boolean
      case_count: number
      required_metric_ids: string[]
      descriptor_digests: Record<string, string>
      reasons: string[]
    }
  } | null
  metric_descriptors: MetricDescriptorBindingV2[]
}

export interface RunCaseIndexEntryV2 {
  case_id: string
  repetition: number
  seed: number | null
  status: string
  question: string
  answer_judgment: ArtifactJudgmentV2
  evidence_judgment: ArtifactEvidenceJudgmentV2
  core_metrics_available: boolean
  failure_kind: string | null
}

export interface ArtifactCaseIndexViewV2 {
  schema_version: '1.0'
  run_id: string
  artifact_contract_version: '2.0' | '1.2'
  availability: ArtifactViewAvailability
  reason: string | null
  verification: ArtifactVerification | null
  cases: RunCaseIndexEntryV2[]
}

export interface LegacyRunCaseV2 {
  case_id: string
  repetition: number
  seed: number | null
  status: string
  question: string
  answer: string | null
  error: Record<string, unknown> | null
}

export interface ArtifactCaseViewV2 {
  schema_version: '1.0'
  run_id: string
  artifact_contract_version: '2.0' | '1.2'
  availability: ArtifactViewAvailability
  reason: string | null
  verification: ArtifactVerification | null
  artifact_case: RunArtifactCaseV2 | null
  legacy_case: LegacyRunCaseV2 | null
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

export type LLMProviderKind = 'ollama' | 'openai_compatible'
export type LLMHealthStatus = 'not_checked' | 'healthy' | 'unreachable' | 'model_unavailable' | 'invalid'
export type LLMLatencyStatus = 'not_checked' | 'measured' | 'unreachable' | 'invalid'
export type LLMStage = 'target_discovery' | 'question_generation' | 'answer_evidence' | 'review_assist' | 'calibration' | 'runtime_generation' | 'runtime_embedding'

export interface LLMProviderConfig {
  provider_id: string
  display_name: string
  kind: LLMProviderKind
  endpoint: string
  model: string
  embedding_model: string | null
  enabled: boolean
  api_key_configured: boolean
  health_status: LLMHealthStatus
  available_models: string[]
  available_chat_models: string[]
  available_embedding_models: string[]
  health_message: string | null
  last_checked_at: string | null
  latency_status: LLMLatencyStatus
  latency_ms: number | null
  last_latency_checked_at: string | null
}

export interface LLMStageBinding {
  stage: LLMStage
  provider_id: string
  model: string | null
  enabled: boolean
  fallback_provider_id: string | null
}

export interface LLMConfigRevision {
  schema_version: string
  revision_id: string
  config_version: number
  created_at: string
  actor: string
  reason: string
  parent_revision_id: string | null
  config_digest: string
  providers: LLMProviderConfig[]
  bindings: LLMStageBinding[]
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

export interface AuthoringDataset {
  authoring_dataset_id: string
  state: string
  created_at: string
  updated_at: string
  archived_at?: string | null
  source: { original_filename: string; sha256: string; size_bytes: number }
  document_id: string | null
  canonical_digest: string | null
  analysis: { record_count?: number; records_by_status?: Record<string, number>; records_by_object_type?: Record<string, number> }
  failure: string | null
  formal_release_ids?: string[]
}

export interface AuthoringTarget {
  target_id: string
  capability: string
  source_object_ids: string[]
  retrieval_route: string[]
  distractor_object_ids: string[]
  confidence: number
  discovery_method: string
  flags: string[]
  rationale: string
}

export interface AuthoringTargetPreviewItem {
  object_type: string
  text: string
  table: {
    row: number | null
    column: number | null
    header_path: string[]
  } | null
}

export interface AuthoringTargetPreview {
  target_id: string
  source: AuthoringTargetPreviewItem[]
  context: AuthoringTargetPreviewItem[]
  distractors: AuthoringTargetPreviewItem[]
}

export interface AuthoringEvidence {
  source_object_id: string
  required_group?: string
  near_miss_object_ids?: string[]
}

export interface AuthoringResolution {
  answer_kind: 'text' | 'numeric' | 'formula' | 'set' | 'abstain'
  canonical_answer?: string | string[] | null
  accepted_values?: string[]
  locale?: string | null
  unit?: string | null
  tolerance?: number | null
  evidence?: AuthoringEvidence[]
  dependency_graph?: Array<Record<string, unknown>>
  negative_scope_object_ids?: string[]
  negative_rationale?: string | null
  resolution_method?: string
  provider_metadata?: Record<string, unknown>
}

export interface AuthoringCandidate {
  candidate_id: string
  target_id: string
  version: number
  state: string
  question: string
  language: string
  source_object_ids: string[]
  generation_method: string
  answer_evidence: AuthoringResolution | null
  gates: Array<{ gate_id: string; status: 'PASS' | 'FLAG' | 'FAIL'; message: string }>
}

export type AuthoringGenerationJobState = 'queued' | 'running' | 'completed' | 'partial' | 'failed' | 'cancelled'
export type AuthoringGenerationItemState = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface AuthoringGenerationJobItem {
  target_id: string
  state: AuthoringGenerationItemState
  attempts: number
  candidate_id: string | null
  error_code: string | null
  error_detail: string | null
  started_at: string | null
  completed_at: string | null
}

export interface AuthoringGenerationJob {
  job_id: string
  authoring_dataset_id: string
  provider: string
  seed: number
  remote_consent: boolean
  state: AuthoringGenerationJobState
  items: AuthoringGenerationJobItem[]
  requested_at: string
  started_at: string | null
  completed_at: string | null
  cancel_requested: boolean
}

export type AuthoringDiscoveryJobState = 'queued' | 'running' | 'completed' | 'failed'
export type AuthoringDiscoveryJobPhase = 'queued' | 'building_rule_targets' | 'awaiting_model' | 'saving_results' | 'completed' | 'failed'

export interface AuthoringDiscoveryJob {
  job_id: string
  authoring_dataset_id: string
  provider: string
  seed: number
  remote_consent: boolean
  state: AuthoringDiscoveryJobState
  phase: AuthoringDiscoveryJobPhase
  phase_detail: string
  requested_at: string
  started_at: string | null
  completed_at: string | null
  total_source_records: number
  model_source_records: number
  rule_target_count: number
  target_count: number
  error_code: string | null
  error_detail: string | null
}

export interface AuthoringExport {
  release_id: string
  name: string
  version: string
  approved_case_ids: string[]
  views: Record<string, string>
  blocked_cases: Array<Record<string, unknown>>
  registered_bundle_ids: Record<string, string>
}

export interface EvaluationDraft {
  draft_id?: string
  mode: 'basic' | 'advanced'
  bundle_id: string | null
  dataset_release_id?: string | null
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
  display_name?: string | null
  bundle_id: string
  dataset_release_id?: string | null
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
  runs: Array<{ run: RunManifest; summary: ArtifactOverviewV2 }>
}
