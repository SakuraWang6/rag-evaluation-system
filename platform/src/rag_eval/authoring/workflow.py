"""Structure-first targets, reviewable candidates, and formal release gates."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from rag_eval.authoring.models import (
    AnswerEvidenceCandidate,
    ApprovedCase,
    AuthoringDataset,
    AuthoringDiscoveryJob,
    AuthoringState,
    BenchmarkTargetCandidate,
    CandidateEvidence,
    CandidateState,
    DiscoveryMethod,
    DiscoveryJobPhase,
    DiscoveryJobStatus,
    EvidenceRepresentabilityProfile,
    EvidenceRepresentabilityStatus,
    AuthoringGenerationJob,
    GenerationJobItem,
    GenerationJobItemState,
    GenerationJobStatus,
    GateStatus,
    QualityGateResult,
    QuestionCandidate,
    ReviewRecord,
    RuntimeEvidenceCoverage,
)
from rag_eval.authoring.ledger import (
    ActorRole,
    AuthoringLedger,
    LifecycleState,
    ReviewDecision,
    TargetKind,
)
from rag_eval.authoring.providers import (
    ConfiguredRemoteProvider,
    LocalOllamaProvider,
    ProposalProviderError,
    provider_metadata,
)
from rag_eval.authoring.storage import AuthoringWorkspaceStore
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.llm import LLMConfigurationService, LLMStage


class AuthoringWorkflowError(ValueError):
    pass


def _json_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _stable_id(prefix: str, payload: object) -> str:
    return f"{prefix}-{_json_digest(payload)[:20]}"


def _json_lines(items: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for item in items
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _tokens(value: str) -> set[str]:
    return {
        item.casefold()
        for item in re.findall(r"[A-Za-z][A-Za-z0-9_.-]{1,}|\d+(?:\.\d+)?|[\u4e00-\u9fff]{2,8}", value)
    }


class AuthoringWorkflow:
    """Mutable authoring state machine.  Gold appears only after a review record."""

    def __init__(
        self,
        store: AuthoringWorkspaceStore,
        *,
        llm_configuration: LLMConfigurationService | None = None,
        secret_store: Any | None = None,
    ) -> None:
        self.store = store
        self.ledger = AuthoringLedger(store)
        self.llm_configuration = llm_configuration
        self.secret_store = secret_store

    def discover_targets(
        self,
        dataset: AuthoringDataset,
        *,
        provider: DiscoveryMethod = DiscoveryMethod.OLLAMA,
        seed: int = 0,
        remote_consent: bool = False,
    ) -> list[BenchmarkTargetCandidate]:
        """Discover targets synchronously for the legacy API surface.

        New product clients use a persisted discovery job instead.  Retaining
        this method keeps existing integrations compatible and preserves the
        normal provider timeout for a direct HTTP request.
        """

        return self._discover_targets(
            dataset,
            provider=provider,
            seed=seed,
            remote_consent=remote_consent,
            ollama_timeout_seconds=60.0,
        )

    def _discover_targets(
        self,
        dataset: AuthoringDataset,
        *,
        provider: DiscoveryMethod,
        seed: int,
        remote_consent: bool,
        ollama_timeout_seconds: float | None,
        on_progress: Callable[[DiscoveryJobPhase, str, dict[str, int]], None] | None = None,
    ) -> list[BenchmarkTargetCandidate]:
        self._require_analyzed(dataset)
        records = self._records(dataset.authoring_dataset_id)
        if on_progress is not None:
            on_progress(
                DiscoveryJobPhase.BUILDING_RULE_TARGETS,
                "正在根据文档结构识别可出题位置。",
                {"total_source_records": len(records)},
            )
        targets = self._rule_targets(dataset, records)
        rule_target_count = len({target.target_id for target in targets})
        provider_flags: list[str] = []
        if provider == DiscoveryMethod.OLLAMA:
            # Rules inspect the entire canonical document and do not depend on
            # the optional model call. Commit that complete deterministic
            # result before waiting for Ollama so authors can begin from it
            # instead of being blocked by a slow advisory suggestion.
            rule_unique = {target.target_id: target for target in targets}
            rule_targets = sorted(rule_unique.values(), key=lambda item: item.target_id)
            self._save_target_snapshot(dataset, rule_targets)
            model_source_records = min(
                28, sum(record.get("status") == "supported" for record in records)
            )
            if on_progress is not None:
                on_progress(
                    DiscoveryJobPhase.AWAITING_MODEL,
                    "规则目标已生成，正在等待本地模型补充结构化建议；此步骤会持续运行，不设请求超时。",
                    {
                        "total_source_records": len(records),
                        "model_source_records": model_source_records,
                        "rule_target_count": rule_target_count,
                    },
                )
            try:
                targets.extend(
                    self._ollama_targets(
                        dataset,
                        records,
                        seed=seed,
                        timeout_seconds=ollama_timeout_seconds,
                    )
                )
            except ProposalProviderError:
                provider_flags.append("local_model_unavailable_rule_fallback")
            except AuthoringWorkflowError as exc:
                # Target discovery is proposal-only. A malformed model target
                # list must not make an otherwise usable DOCX workspace fail;
                # preserve the deterministic targets and limit automatic
                # generation to the safe direct-evidence subset instead.
                if not str(exc).startswith("target proposal"):
                    raise
                provider_flags.append("invalid_local_model_target_contract")
            except Exception as exc:
                # Discovery is advisory.  A local model integration can also
                # fail outside its provider wrapper (for example while
                # normalizing a malformed streamed response).  The document
                # already has deterministic, source-grounded rule targets, so
                # never turn that recoverable proposal failure into a 500 or
                # leave the authoring screen disconnected.  Keep an explicit
                # flag on the resulting targets for operational diagnosis.
                provider_flags.append(
                    f"local_model_discovery_failed_rule_fallback:{exc.__class__.__name__}"
                )
        elif provider == DiscoveryMethod.REMOTE:
            if not remote_consent:
                raise AuthoringWorkflowError("remote generation requires explicit UI consent")
            targets.extend(self._remote_targets(dataset, records, seed=seed))
        elif provider not in {DiscoveryMethod.RULE, DiscoveryMethod.MANUAL}:
            raise AuthoringWorkflowError(f"unsupported discovery provider: {provider}")
        unique = {target.target_id: target for target in targets}
        normalized = [
            target.model_copy(update={"flags": sorted(set(target.flags + provider_flags))})
            for target in sorted(unique.values(), key=lambda item: item.target_id)
        ]
        if on_progress is not None:
            on_progress(
                DiscoveryJobPhase.SAVING_RESULTS,
                "模型响应已收到，正在保存全部题目目标。",
                {
                    "total_source_records": len(records),
                    "rule_target_count": rule_target_count,
                    "target_count": len(normalized),
                },
            )
        self._save_target_snapshot(dataset, normalized)
        return normalized

    def _save_target_snapshot(
        self, dataset: AuthoringDataset, targets: list[BenchmarkTargetCandidate]
    ) -> None:
        """Atomically expose a source-consistent target snapshot to the UI."""

        atomic_write_json(
            self.store.target_path(dataset.authoring_dataset_id),
            {
                "source_sha256": dataset.source.sha256,
                "canonical_digest": dataset.canonical_digest,
                "targets": [item.model_dump(mode="json") for item in targets],
            },
        )
        self._advance_state(dataset, AuthoringState.TARGETS_READY)

    def list_targets(self, dataset: AuthoringDataset) -> list[BenchmarkTargetCandidate]:
        path = self.store.target_path(dataset.authoring_dataset_id)
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_sha256") != dataset.source.sha256 or payload.get("canonical_digest") != dataset.canonical_digest:
            raise AuthoringWorkflowError("target discovery was created against a different frozen source")
        return [BenchmarkTargetCandidate.model_validate(value) for value in payload.get("targets", [])]

    def target_preview(self, dataset: AuthoringDataset, target_id: str) -> dict[str, Any]:
        """Return a small, user-facing projection of a frozen authoring target.

        Target artifacts intentionally contain canonical IDs and discovery metadata.
        Those are useful to the workflow, but do not tell an author what source
        material a proposed question would use.  This projection exposes only the
        text and human-readable table context required for review; it never
        modifies the target or canonical record.
        """

        self._require_analyzed(dataset)
        target = self._target(dataset, target_id)
        records = {
            str(record["object_id"]): record
            for record in self._records(dataset.authoring_dataset_id)
        }

        def preview(object_ids: list[str]) -> list[dict[str, Any]]:
            values: list[dict[str, Any]] = []
            for object_id in object_ids:
                record = records.get(object_id)
                if record is None:
                    # A stale target must not be silently shown as a valid
                    # proposal against a different canonical document.
                    raise AuthoringWorkflowError("target cites an unknown canonical object")
                logical_record = records.get(str(record.get("logical_cell_id") or "")) or {}
                attributes = record.get("attributes") or {}
                logical_attributes = logical_record.get("attributes") or {}
                header_path = (
                    record.get("effective_header_path")
                    or attributes.get("effective_header_path")
                    or logical_record.get("effective_header_path")
                    or logical_attributes.get("effective_header_path")
                    or []
                )
                table: dict[str, Any] | None = None
                if record.get("object_type") in {"cell", "logical_cell"}:
                    row, column = self._cell_position(record)
                    table = {
                        "row": row,
                        "column": column,
                        "header_path": [str(item) for item in header_path if str(item).strip()],
                    }
                values.append(
                    {
                        "object_type": str(record.get("object_type", "source")),
                        "text": str(record.get("canonical_value") or record.get("witness") or ""),
                        "table": table,
                    }
                )
            return values

        context_ids = self._table_context_ids(records, target.source_object_ids)
        return {
            "target_id": target.target_id,
            "source": preview(target.source_object_ids),
            "context": preview(context_ids),
            "distractors": preview(target.distractor_object_ids),
        }

    def create_target(
        self,
        dataset: AuthoringDataset,
        *,
        capability: str,
        source_object_ids: list[str],
        retrieval_route: list[str],
        distractor_object_ids: list[str] | None = None,
        rationale: str = "manual reviewer target",
    ) -> BenchmarkTargetCandidate:
        """Add one reviewer-authored, source-frozen target without inventing truth."""

        self._require_analyzed(dataset)
        if not capability.strip() or not source_object_ids or not retrieval_route:
            raise AuthoringWorkflowError(
                "manual target requires capability, source objects, and retrieval route"
            )
        records = {
            str(record["object_id"]): record
            for record in self._records(dataset.authoring_dataset_id)
        }
        cited = set(source_object_ids) | set(distractor_object_ids or [])
        unknown = sorted(cited.difference(records))
        if unknown:
            raise AuthoringWorkflowError("manual target cites an unknown canonical object")
        target = self._target_value(
            dataset,
            digest=self._canonical_digest(dataset),
            capability=capability.strip(),
            source_ids=source_object_ids,
            route=retrieval_route,
            distractors=distractor_object_ids,
            confidence=1.0,
            rationale=rationale.strip(),
            method=DiscoveryMethod.MANUAL,
        )
        targets = {item.target_id: item for item in self.list_targets(dataset)}
        targets[target.target_id] = target
        ordered = [targets[key] for key in sorted(targets)]
        atomic_write_json(
            self.store.target_path(dataset.authoring_dataset_id),
            {
                "source_sha256": dataset.source.sha256,
                "canonical_digest": dataset.canonical_digest,
                "targets": [item.model_dump(mode="json") for item in ordered],
            },
        )
        self._advance_state(dataset, AuthoringState.TARGETS_READY)
        return target

    def create_question(
        self,
        dataset: AuthoringDataset,
        *,
        target_id: str,
        question: str,
        language: str = "zh-CN",
        method: DiscoveryMethod = DiscoveryMethod.MANUAL,
        provider_metadata_value: dict[str, Any] | None = None,
    ) -> QuestionCandidate:
        self._require_analyzed(dataset)
        target = self._target(dataset, target_id)
        if not question.strip():
            raise AuthoringWorkflowError("question cannot be empty")
        candidate = QuestionCandidate(
            candidate_id=f"candidate-{uuid.uuid4().hex}",
            target_id=target.target_id,
            question=question.strip(),
            language=language,
            source_sha256=dataset.source.sha256,
            canonical_digest=self._canonical_digest(dataset),
            source_object_ids=target.source_object_ids,
            generation_method=method,
            provider_metadata=provider_metadata_value or {},
        )
        self._save_candidate(dataset, candidate)
        self._create_ledger_case(dataset, candidate)
        self._advance_state(dataset, AuthoringState.CANDIDATES_READY)
        return candidate

    def generate_question(
        self,
        dataset: AuthoringDataset,
        *,
        target_id: str,
        seed: int = 0,
        provider: DiscoveryMethod = DiscoveryMethod.OLLAMA,
        remote_consent: bool = False,
    ) -> QuestionCandidate:
        """Generate one structured question only after canonical source freeze.

        This is deliberately independent from answer/evidence resolution.  If
        the local proposal model is unavailable, a limited source-grounded
        rule fallback can still create a clearly reviewable draft for simple
        direct-evidence targets.  It never approves or freezes the result.
        """

        target = self._target(dataset, target_id)
        records = {
            str(record["object_id"]): record
            for record in self._records(dataset.authoring_dataset_id)
        }
        source_ids = list(
            dict.fromkeys(
                target.source_object_ids
                + self._table_context_ids(records, target.source_object_ids)
            )
        )
        source = self._source_subset(dataset, source_ids)
        prompt = (
            "Create exactly one Chinese RAG benchmark question grounded only in the supplied source objects. "
            "Return JSON {question, source_object_ids}. Do not include object IDs, file names, titles as cues, "
            "or an answer. The question must require retrieval; do not use a fixed template. "
            "For tables, SOURCE may include visible header context. Cite only one or more of these target "
            f"source IDs: {json.dumps(target.source_object_ids, ensure_ascii=False)}."
        )
        try:
            value, metadata, method = self._proposal(
                task="question_generation",
                source=source,
                prompt=prompt,
                seed=seed,
                provider=provider,
                remote_consent=remote_consent,
            )
            citations = value.get("source_object_ids")
            question = value.get("question")
            if not isinstance(question, str) or not question.strip():
                raise AuthoringWorkflowError("question proposal is missing a question")
            if not isinstance(citations, list) or not all(isinstance(item, str) for item in citations):
                raise AuthoringWorkflowError("question proposal must cite canonical object IDs")
            if not set(citations).issubset(set(target.source_object_ids)):
                raise AuthoringWorkflowError("question proposal cites objects outside its frozen target")
        except ProposalProviderError:
            question, citations = self._rule_question_proposal(target, records)
            metadata = {
                "provider": "canonical-rule-fallback",
                "reason": "local_model_unavailable",
                "task": "question_generation",
            }
            method = DiscoveryMethod.RULE
        except AuthoringWorkflowError as exc:
            # A local model may answer but still violate the small proposal
            # contract (for example omit citations).  For a direct, already
            # eligible target we can safely discard that output and use the
            # deterministic source-grounded draft instead.  Do not apply this
            # recovery to other providers or to semantic/gate failures.
            if provider != DiscoveryMethod.OLLAMA or not str(exc).startswith("question proposal"):
                raise
            question, citations = self._rule_question_proposal(target, records)
            metadata = {
                "provider": "canonical-rule-fallback",
                "reason": "invalid_local_model_question_contract",
                "task": "question_generation",
            }
            method = DiscoveryMethod.RULE
        candidate = self.create_question(
            dataset,
            target_id=target_id,
            question=question,
            method=method,
            provider_metadata_value=metadata,
        )
        candidate = candidate.model_copy(update={"source_object_ids": citations})
        self._save_candidate(dataset, candidate)
        self._revise_ledger_case(dataset, candidate, reason="record generated question citations")
        return candidate

    def generate_question_and_answer(
        self,
        dataset: AuthoringDataset,
        *,
        target_id: str,
        seed: int = 0,
        provider: DiscoveryMethod = DiscoveryMethod.OLLAMA,
        remote_consent: bool = False,
    ) -> QuestionCandidate:
        """Create one reviewable question, answer, and evidence proposal.

        The browser receives one complete proposal.  Internally the question
        and answer are generated in two constrained passes: the question pass
        cannot see an answer, and the answer pass sees only the frozen source
        and that resulting question.  This preserves the no-answer-leakage
        check while removing an unnecessary user-facing two-step workflow.
        Neither pass approves Gold; ``resolve_answer_evidence`` still runs the
        validation gates and leaves the candidate pending human review.
        """

        candidate = self.generate_question(
            dataset,
            target_id=target_id,
            seed=seed,
            provider=provider,
            remote_consent=remote_consent,
        )
        return self.generate_answer_evidence(
            dataset,
            candidate_id=candidate.candidate_id,
            seed=seed,
            provider=provider,
            remote_consent=remote_consent,
        )

    def resolve_answer_evidence(
        self,
        dataset: AuthoringDataset,
        *,
        candidate_id: str,
        resolution: AnswerEvidenceCandidate,
    ) -> QuestionCandidate:
        """Attach a separately supplied/manual source-grounded answer/evidence pass."""

        self._require_editable(dataset)
        candidate = self.get_candidate(dataset, candidate_id)
        self._ensure_ledger_candidate(dataset, candidate)
        if candidate.state in {CandidateState.APPROVED, CandidateState.REJECTED}:
            raise AuthoringWorkflowError("reviewed candidates cannot be re-resolved")
        self._validate_resolution(dataset, resolution)
        resolved = candidate.model_copy(
            update={"answer_evidence": resolution, "state": CandidateState.ANSWER_RESOLVED, "gates": []}
        )
        gates = self._run_gates(dataset, resolved)
        new_state = CandidateState.BLOCKED if any(gate.status == GateStatus.FAIL for gate in gates) else CandidateState.REVIEW_REQUIRED
        resolved = resolved.model_copy(update={"state": new_state, "gates": gates})
        self._save_candidate(dataset, resolved)
        self._record_ledger_resolution(dataset, candidate, resolved)
        self._advance_state(dataset, AuthoringState.REVIEW_REQUIRED if new_state == CandidateState.REVIEW_REQUIRED else AuthoringState.BLOCKED)
        return resolved

    def generate_answer_evidence(
        self,
        dataset: AuthoringDataset,
        *,
        candidate_id: str,
        seed: int = 0,
        provider: DiscoveryMethod = DiscoveryMethod.OLLAMA,
        remote_consent: bool = False,
    ) -> QuestionCandidate:
        """Run the answer/evidence proposal independently from question generation.

        The prompt gets only the frozen canonical source subset and the already
        stored question.  It receives neither a scenario answer nor any output
        from a question generator beyond the question itself.
        """

        self._require_editable(dataset)
        candidate = self.get_candidate(dataset, candidate_id)
        target = self._target(dataset, candidate.target_id)
        source_ids = sorted(set(target.source_object_ids + target.distractor_object_ids))
        source = self._source_subset(dataset, source_ids)
        prompt = (
            "Resolve the following RAG question using only SOURCE JSON. Return JSON "
            "{answer_kind,canonical_answer,accepted_values,evidence:[{source_object_id,required_group,near_miss_object_ids}],dependency_graph}. "
            "Cite actual source_object_id values. If the source cannot answer, use answer_kind=abstain with "
            "negative_scope_object_ids and negative_rationale. Do not invent facts.\nQUESTION:\n"
            + candidate.question
        )
        try:
            value, metadata, method = self._proposal(
                task="answer_evidence_resolution",
                source=source,
                prompt=prompt,
                seed=seed,
                provider=provider,
                remote_consent=remote_consent,
            )
            try:
                value, normalizations = self._normalize_answer_evidence_proposal(value)
                if normalizations:
                    metadata = {
                        **metadata,
                        "contract_normalizations": normalizations,
                    }
                resolution = AnswerEvidenceCandidate.model_validate(
                    value | {"resolution_method": method, "provider_metadata": metadata}
                )
            except ValueError as exc:
                raise AuthoringWorkflowError(f"answer/evidence proposal has invalid schema: {exc}") from exc
        except ProposalProviderError:
            resolution = self._rule_answer_evidence_proposal(dataset, candidate, target)
        except AuthoringWorkflowError as exc:
            # Provider-shaped output is never treated as Gold merely because
            # it was syntactically close.  For a simple direct target, discard
            # the malformed local response and rebuild from the frozen
            # Canonical value.  Complex target types still fail closed in the
            # rule helper below.
            if provider != DiscoveryMethod.OLLAMA or not str(exc).startswith(
                "answer/evidence proposal has invalid schema"
            ):
                raise
            resolution = self._rule_answer_evidence_proposal(
                dataset,
                candidate,
                target,
                fallback_reason="invalid_local_model_answer_contract",
            )
        return self.resolve_answer_evidence(dataset, candidate_id=candidate_id, resolution=resolution)

    @staticmethod
    def _normalize_answer_evidence_proposal(
        value: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """Convert known provider spelling variants into the formal contract.

        Providers are allowed to help propose content, but they do not define
        the Authoring schema.  In particular, some models use ``canonical``
        to mean a free-text answer and emit a dependency adjacency map rather
        than the contract's ordered list.  These shape-only conversions retain
        every model value; semantic checks (known evidence, negative scope,
        Gold eligibility, and gates) still fail closed below.
        """

        normalized = dict(value)
        changes: list[str] = []

        raw_kind = normalized.get("answer_kind")
        if isinstance(raw_kind, str):
            key = raw_kind.strip().casefold().replace("-", "_").replace(" ", "_")
            aliases = {
                "canonical": "text",
                "string": "text",
                "free_text": "text",
                "plain_text": "text",
                "number": "numeric",
                "decimal": "numeric",
                "list": "set",
                "array": "set",
            }
            answer_kind = aliases.get(key, key)
            if answer_kind != raw_kind:
                normalized["answer_kind"] = answer_kind
                changes.append(f"answer_kind:{raw_kind}->{answer_kind}")

        accepted_values = normalized.get("accepted_values")
        if accepted_values is None:
            normalized["accepted_values"] = []
            changes.append("accepted_values:null->[]")
        elif isinstance(accepted_values, str):
            normalized["accepted_values"] = [accepted_values]
            changes.append("accepted_values:string->list")

        evidence = normalized.get("evidence")
        if isinstance(evidence, dict):
            normalized["evidence"] = [evidence]
            changes.append("evidence:object->list")

        graph = normalized.get("dependency_graph")
        if graph is None:
            normalized["dependency_graph"] = []
            changes.append("dependency_graph:null->[]")
        elif isinstance(graph, dict):
            if isinstance(graph.get("edges"), list):
                normalized["dependency_graph"] = graph["edges"]
                changes.append("dependency_graph:edges-object->list")
            elif {"from", "to"}.issubset(graph) or "depends_on" in graph:
                normalized["dependency_graph"] = [graph]
                changes.append("dependency_graph:edge-object->list")
            else:
                rows: list[dict[str, Any]] = []
                for node_id, raw_node in sorted(graph.items(), key=lambda item: str(item[0])):
                    if isinstance(raw_node, dict):
                        rows.append({"node_id": str(node_id), **raw_node})
                    else:
                        rows.append({"node_id": str(node_id), "description": str(raw_node)})
                normalized["dependency_graph"] = rows
                changes.append("dependency_graph:adjacency-object->list")

        return normalized, changes

    def get_candidate(self, dataset: AuthoringDataset, candidate_id: str) -> QuestionCandidate:
        candidate = self.store.load_model(self.store.candidate_path(dataset.authoring_dataset_id, candidate_id), QuestionCandidate)
        self._validate_candidate_source(dataset, candidate)
        return candidate

    def list_candidates(self, dataset: AuthoringDataset) -> list[QuestionCandidate]:
        root = self.store.workspace(dataset.authoring_dataset_id) / "candidates"
        values = [self.store.load_model(path, QuestionCandidate) for path in sorted(root.glob("*.json"))]
        for value in values:
            self._validate_candidate_source(dataset, value)
        return values

    def review(
        self,
        dataset: AuthoringDataset,
        *,
        candidate_id: str,
        decision: str,
        reviewer: str,
        note: str = "",
        edited_question: str | None = None,
        edited_resolution: AnswerEvidenceCandidate | None = None,
    ) -> QuestionCandidate:
        self._require_editable(dataset)
        candidate = self.get_candidate(dataset, candidate_id)
        self._ensure_ledger_candidate(dataset, candidate)
        if decision not in {"accept", "edit", "reject"}:
            raise AuthoringWorkflowError("review decision must be accept, edit, or reject")
        if not reviewer.strip():
            raise AuthoringWorkflowError("reviewer is required")
        reviewer_identity = reviewer.strip()
        if candidate.state == CandidateState.APPROVED and decision != "accept":
            raise AuthoringWorkflowError("approved candidates are immutable; create a new candidate for a revision")
        if decision == "accept":
            if candidate.state != CandidateState.REVIEW_REQUIRED:
                raise AuthoringWorkflowError("only a gate-reviewed candidate can be accepted")
            self._formal_accept(dataset, candidate, reviewer=reviewer_identity, note=note)
            approved = candidate.model_copy(update={"state": CandidateState.APPROVED})
            self._save_candidate(dataset, approved)
            approved_case = ApprovedCase(
                case_id=f"case-{approved.candidate_id.removeprefix('candidate-')}",
                candidate_id=approved.candidate_id,
                candidate_version=approved.version,
                approved_at=datetime.now(UTC),
                approved_by=reviewer.strip(),
                candidate=approved,
            )
            self.store.save_model(self.store.approved_path(dataset.authoring_dataset_id, approved_case.case_id), approved_case)
            updated = approved
            self._advance_state(dataset, AuthoringState.APPROVED)
            edited_fields: list[str] = []
        elif decision == "reject":
            self._formal_reject(dataset, candidate, reviewer=reviewer_identity, note=note)
            updated = candidate.model_copy(update={"state": CandidateState.REJECTED})
            self._save_candidate(dataset, updated)
            edited_fields = []
        else:
            if edited_question is None and edited_resolution is None:
                raise AuthoringWorkflowError("an edit review needs an edited question or answer/evidence")
            if edited_question is not None and not edited_question.strip():
                raise AuthoringWorkflowError("edited question cannot be empty")
            if edited_resolution is not None:
                self._validate_resolution(dataset, edited_resolution)
            fields = []
            if edited_question is not None:
                fields.append("question")
            if edited_resolution is not None:
                fields.append("answer_evidence")
            updated = candidate.model_copy(
                update={
                    "version": candidate.version + 1,
                    "question": edited_question.strip() if edited_question is not None else candidate.question,
                    "answer_evidence": edited_resolution if edited_resolution is not None else candidate.answer_evidence,
                    "state": CandidateState.ANSWER_RESOLVED if (edited_resolution or candidate.answer_evidence) else CandidateState.DRAFT,
                    "gates": [],
                }
            )
            if updated.answer_evidence is not None:
                gates = self._run_gates(dataset, updated)
                updated = updated.model_copy(update={"gates": gates, "state": CandidateState.BLOCKED if any(item.status == GateStatus.FAIL for item in gates) else CandidateState.REVIEW_REQUIRED})
            self._save_candidate(dataset, updated)
            self._formal_edit(dataset, candidate, updated, reviewer=reviewer_identity, note=note)
            edited_fields = fields
        review = ReviewRecord(
            review_id=f"review-{uuid.uuid4().hex}",
            candidate_id=candidate.candidate_id,
            candidate_version=candidate.version,
            decision=decision,  # type: ignore[arg-type]
            reviewer=reviewer_identity,
            note=note,
            edited_fields=edited_fields,
            created_at=datetime.now(UTC),
        )
        self.store.save_model(self.store.review_path(dataset.authoring_dataset_id, review.review_id), review)
        return updated

    def list_reviews(self, dataset: AuthoringDataset) -> list[ReviewRecord]:
        root = self.store.workspace(dataset.authoring_dataset_id) / "reviews"
        return [self.store.load_model(path, ReviewRecord) for path in sorted(root.glob("*.json"))]

    def list_approved(self, dataset: AuthoringDataset) -> list[ApprovedCase]:
        root = self.store.workspace(dataset.authoring_dataset_id) / "approved"
        return [self.store.load_model(path, ApprovedCase) for path in sorted(root.glob("*.json"))]

    def mark_formal_released(
        self, dataset: AuthoringDataset, *, release_id: str
    ) -> AuthoringDataset:
        """Close an authoring flow after its immutable formal release exists.

        The private workspace is retained for the provenance chain, but it is
        no longer a resumable product-flow draft.  Retrying an idempotent
        publish request simply retains the already linked release ID.
        """

        current = self.store.get(dataset.authoring_dataset_id)
        linked = list(dict.fromkeys([*current.formal_release_ids, release_id]))
        return self.store.save(
            current.model_copy(
                update={
                    "state": AuthoringState.FORMAL_RELEASED,
                    "formal_release_ids": linked,
                }
            )
        )

    def create_discovery_job(
        self,
        dataset: AuthoringDataset,
        *,
        provider: DiscoveryMethod = DiscoveryMethod.OLLAMA,
        seed: int = 0,
        remote_consent: bool = False,
    ) -> AuthoringDiscoveryJob:
        """Persist target discovery before any potentially long model request.

        A document can be large enough for a local model to take minutes to
        evaluate.  This job is deliberately written first, so closing the UI,
        refreshing it, or restarting the API never loses the operation's
        visible state.
        """

        self._require_analyzed(dataset)
        active = [
            item
            for item in self.list_discovery_jobs(dataset)
            if item.state in {DiscoveryJobStatus.QUEUED, DiscoveryJobStatus.RUNNING}
        ]
        if active:
            raise AuthoringWorkflowError(
                f"target discovery job {active[0].job_id} is already running; reopen it to view progress"
            )
        job = AuthoringDiscoveryJob(
            job_id=f"discovery-{uuid.uuid4().hex}",
            authoring_dataset_id=dataset.authoring_dataset_id,
            provider=provider,
            seed=seed,
            remote_consent=remote_consent,
            requested_at=datetime.now(UTC),
        )
        return self._save_discovery_job(job)

    def get_discovery_job(
        self, dataset: AuthoringDataset, job_id: str
    ) -> AuthoringDiscoveryJob:
        path = self.store.discovery_job_path(dataset.authoring_dataset_id, job_id)
        if not path.is_file():
            raise FileNotFoundError(job_id)
        job = self.store.load_model(path, AuthoringDiscoveryJob)
        if job.authoring_dataset_id != dataset.authoring_dataset_id:
            raise AuthoringWorkflowError("target discovery job belongs to a different dataset")
        return job

    def list_discovery_jobs(self, dataset: AuthoringDataset) -> list[AuthoringDiscoveryJob]:
        root = self.store.discovery_jobs_root(dataset.authoring_dataset_id)
        if not root.is_dir():
            return []
        values = [
            self.store.load_model(path, AuthoringDiscoveryJob)
            for path in sorted(root.glob("discovery-*.json"))
        ]
        return sorted(values, key=lambda item: item.requested_at, reverse=True)

    def retry_discovery_job(
        self, dataset: AuthoringDataset, *, job_id: str
    ) -> AuthoringDiscoveryJob:
        job = self.get_discovery_job(dataset, job_id)
        if job.state in {DiscoveryJobStatus.QUEUED, DiscoveryJobStatus.RUNNING}:
            raise AuthoringWorkflowError("target discovery job is already running")
        return self._save_discovery_job(
            job.model_copy(
                update={
                    "state": DiscoveryJobStatus.QUEUED,
                    "phase": DiscoveryJobPhase.QUEUED,
                    "phase_detail": "任务已重新排队。",
                    "started_at": None,
                    "completed_at": None,
                    "total_source_records": 0,
                    "model_source_records": 0,
                    "rule_target_count": 0,
                    "target_count": 0,
                    "error_code": None,
                    "error_detail": None,
                }
            )
        )

    def run_discovery_job(
        self, dataset: AuthoringDataset, *, job_id: str
    ) -> AuthoringDiscoveryJob:
        """Run a persisted target-discovery job for a background worker.

        Only this job passes ``timeout=None`` to the local Ollama provider.
        The HTTP API has already answered at this point, so a slow model no
        longer blocks the browser request or turns into a misleading network
        failure.
        """

        job = self.get_discovery_job(dataset, job_id)
        if job.state in {DiscoveryJobStatus.COMPLETED, DiscoveryJobStatus.FAILED}:
            return job
        job = self._save_discovery_job(
            job.model_copy(
                update={
                    "state": DiscoveryJobStatus.RUNNING,
                    "phase": DiscoveryJobPhase.BUILDING_RULE_TARGETS,
                    "phase_detail": "正在读取已分析的文档结构。",
                    "started_at": job.started_at or datetime.now(UTC),
                    "completed_at": None,
                    "error_code": None,
                    "error_detail": None,
                }
            )
        )

        def report(
            phase: DiscoveryJobPhase, detail: str, counts: dict[str, int]
        ) -> None:
            current = self.get_discovery_job(dataset, job_id)
            update: dict[str, Any] = {"phase": phase, "phase_detail": detail}
            update.update(counts)
            self._save_discovery_job(current.model_copy(update=update))

        try:
            targets = self._discover_targets(
                self.store.get(dataset.authoring_dataset_id),
                provider=job.provider,
                seed=job.seed,
                remote_consent=job.remote_consent,
                # Unlike a synchronous browser request, a durable background
                # job is allowed to wait for one slow local model response.
                ollama_timeout_seconds=None,
                on_progress=report,
            )
        except Exception as exc:
            detail = str(exc).strip() or exc.__class__.__name__
            code = (
                "provider_unavailable"
                if isinstance(exc, ProposalProviderError)
                else "target_discovery_failed"
            )
            failed = self.get_discovery_job(dataset, job_id).model_copy(
                update={
                    "state": DiscoveryJobStatus.FAILED,
                    "phase": DiscoveryJobPhase.FAILED,
                    "phase_detail": "目标识别未完成；可在模型恢复后重试。",
                    "completed_at": datetime.now(UTC),
                    "error_code": code,
                    "error_detail": detail,
                }
            )
            return self._save_discovery_job(failed)

        completed = self.get_discovery_job(dataset, job_id).model_copy(
            update={
                "state": DiscoveryJobStatus.COMPLETED,
                "phase": DiscoveryJobPhase.COMPLETED,
                "phase_detail": "全部题目目标已保存，可开始生成题目。",
                "target_count": len(targets),
                "completed_at": datetime.now(UTC),
            }
        )
        return self._save_discovery_job(completed)

    def _save_discovery_job(self, job: AuthoringDiscoveryJob) -> AuthoringDiscoveryJob:
        self.store.save_model(
            self.store.discovery_job_path(job.authoring_dataset_id, job.job_id), job
        )
        return job

    def create_generation_job(
        self,
        dataset: AuthoringDataset,
        *,
        target_ids: list[str],
        provider: DiscoveryMethod = DiscoveryMethod.OLLAMA,
        seed: int = 0,
        remote_consent: bool = False,
    ) -> AuthoringGenerationJob:
        """Persist a batch request before any model call begins.

        Persisting the work unit makes closing the modal harmless: the client
        can reconnect to the same job and inspect every target's outcome.
        """

        self._require_analyzed(dataset)
        unique_target_ids = list(dict.fromkeys(target_ids))
        if not unique_target_ids:
            raise AuthoringWorkflowError("at least one generation target is required")
        for target_id in unique_target_ids:
            self._target(dataset, target_id)
        active = [
            item
            for item in self.list_generation_jobs(dataset)
            if item.state in {GenerationJobStatus.QUEUED, GenerationJobStatus.RUNNING}
        ]
        if active:
            raise AuthoringWorkflowError(
                f"generation job {active[-1].job_id} is already running; reopen it to view progress"
            )
        job = AuthoringGenerationJob(
            job_id=f"generation-{uuid.uuid4().hex}",
            authoring_dataset_id=dataset.authoring_dataset_id,
            provider=provider,
            seed=seed,
            remote_consent=remote_consent,
            requested_at=datetime.now(UTC),
            items=[GenerationJobItem(target_id=target_id) for target_id in unique_target_ids],
        )
        return self._save_generation_job(job)

    def get_generation_job(
        self, dataset: AuthoringDataset, job_id: str
    ) -> AuthoringGenerationJob:
        path = self.store.generation_job_path(dataset.authoring_dataset_id, job_id)
        if not path.is_file():
            raise FileNotFoundError(job_id)
        job = self.store.load_model(path, AuthoringGenerationJob)
        if job.authoring_dataset_id != dataset.authoring_dataset_id:
            raise AuthoringWorkflowError("generation job belongs to a different dataset")
        return job

    def list_generation_jobs(self, dataset: AuthoringDataset) -> list[AuthoringGenerationJob]:
        root = self.store.generation_jobs_root(dataset.authoring_dataset_id)
        if not root.is_dir():
            return []
        values = [
            self.store.load_model(path, AuthoringGenerationJob)
            for path in sorted(root.glob("generation-*.json"))
        ]
        return sorted(values, key=lambda item: item.requested_at, reverse=True)

    def cancel_generation_job(
        self, dataset: AuthoringDataset, *, job_id: str
    ) -> AuthoringGenerationJob:
        job = self.get_generation_job(dataset, job_id)
        if job.state in {
            GenerationJobStatus.COMPLETED,
            GenerationJobStatus.PARTIAL,
            GenerationJobStatus.FAILED,
            GenerationJobStatus.CANCELLED,
        }:
            return job
        if job.state == GenerationJobStatus.QUEUED:
            now = datetime.now(UTC)
            return self._save_generation_job(
                job.model_copy(
                    update={
                        "cancel_requested": True,
                        "state": GenerationJobStatus.CANCELLED,
                        "completed_at": now,
                        "items": [
                            item.model_copy(
                                update={
                                    "state": GenerationJobItemState.CANCELLED,
                                    "completed_at": now,
                                }
                            )
                            if item.state == GenerationJobItemState.PENDING
                            else item
                            for item in job.items
                        ],
                    }
                )
            )
        return self._save_generation_job(job.model_copy(update={"cancel_requested": True}))

    def retry_generation_job(
        self,
        dataset: AuthoringDataset,
        *,
        job_id: str,
        target_ids: list[str] | None = None,
    ) -> AuthoringGenerationJob:
        """Requeue failed/cancelled targets without regenerating successful work."""

        job = self.get_generation_job(dataset, job_id)
        if job.state in {GenerationJobStatus.QUEUED, GenerationJobStatus.RUNNING}:
            raise AuthoringWorkflowError("generation job is already running")
        selected = set(target_ids or [
            item.target_id
            for item in job.items
            if item.state in {GenerationJobItemState.FAILED, GenerationJobItemState.CANCELLED}
        ])
        if not selected:
            raise AuthoringWorkflowError("no failed or cancelled generation targets are available to retry")
        known = {item.target_id for item in job.items}
        unknown = sorted(selected.difference(known))
        if unknown:
            raise AuthoringWorkflowError(f"generation retry references unknown target(s): {', '.join(unknown)}")
        retried = False
        items: list[GenerationJobItem] = []
        for item in job.items:
            if item.target_id in selected:
                if item.state not in {GenerationJobItemState.FAILED, GenerationJobItemState.CANCELLED}:
                    raise AuthoringWorkflowError(
                        f"target {item.target_id} is not available for retry"
                    )
                retried = True
                items.append(
                    item.model_copy(
                        update={
                            "state": GenerationJobItemState.PENDING,
                            "candidate_id": None,
                            "error_code": None,
                            "error_detail": None,
                            "started_at": None,
                            "completed_at": None,
                        }
                    )
                )
            else:
                items.append(item)
        if not retried:
            raise AuthoringWorkflowError("no generation target was retried")
        return self._save_generation_job(
            job.model_copy(
                update={
                    "state": GenerationJobStatus.QUEUED,
                    "items": items,
                    "cancel_requested": False,
                    "started_at": None,
                    "completed_at": None,
                }
            )
        )

    def run_generation_job(
        self, dataset: AuthoringDataset, *, job_id: str
    ) -> AuthoringGenerationJob:
        """Run one persisted job synchronously for a background worker.

        State is committed before and after every target, so a client can close
        and reopen the modal at any time.  Cancellation takes effect between
        model calls; an in-flight provider request is never force-killed.
        """

        job = self.get_generation_job(dataset, job_id)
        if job.state in {
            GenerationJobStatus.COMPLETED,
            GenerationJobStatus.PARTIAL,
            GenerationJobStatus.FAILED,
            GenerationJobStatus.CANCELLED,
        }:
            return job
        if job.cancel_requested:
            return self._cancel_remaining_generation_items(job)
        # A process restart can leave the active item recorded as running.
        # No model request survives that restart, so make that one item
        # eligible for a clean retry before continuing the durable job.
        if any(item.state == GenerationJobItemState.RUNNING for item in job.items):
            job = self._save_generation_job(
                job.model_copy(
                    update={
                        "state": GenerationJobStatus.QUEUED,
                        "items": [
                            item.model_copy(
                                update={
                                    "state": GenerationJobItemState.PENDING,
                                    "started_at": None,
                                }
                            )
                            if item.state == GenerationJobItemState.RUNNING
                            else item
                            for item in job.items
                        ],
                    }
                )
            )
        job = self._save_generation_job(
            job.model_copy(
                update={
                    "state": GenerationJobStatus.RUNNING,
                    "started_at": job.started_at or datetime.now(UTC),
                }
            )
        )
        for index, item in enumerate(job.items):
            job = self.get_generation_job(dataset, job_id)
            if job.cancel_requested:
                return self._cancel_remaining_generation_items(job)
            item = job.items[index]
            if item.state != GenerationJobItemState.PENDING:
                continue
            started_at = datetime.now(UTC)
            running = item.model_copy(
                update={
                    "state": GenerationJobItemState.RUNNING,
                    "attempts": item.attempts + 1,
                    "started_at": started_at,
                    "completed_at": None,
                }
            )
            job = self._replace_generation_job_item(job, index, running)
            try:
                candidate = self.generate_question_and_answer(
                    self.store.get(dataset.authoring_dataset_id),
                    target_id=running.target_id,
                    provider=job.provider,
                    seed=job.seed,
                    remote_consent=job.remote_consent,
                )
                completed = running.model_copy(
                    update={
                        "state": GenerationJobItemState.SUCCEEDED,
                        "candidate_id": candidate.candidate_id,
                        "completed_at": datetime.now(UTC),
                    }
                )
            except Exception as exc:  # persisted diagnostics are part of recovery
                code, detail = self._generation_failure(exc)
                completed = running.model_copy(
                    update={
                        "state": GenerationJobItemState.FAILED,
                        "error_code": code,
                        "error_detail": detail,
                        "completed_at": datetime.now(UTC),
                    }
                )
            self._replace_generation_job_item(job, index, completed)
        job = self.get_generation_job(dataset, job_id)
        return self._complete_generation_job(job)

    def _save_generation_job(self, job: AuthoringGenerationJob) -> AuthoringGenerationJob:
        self.store.save_model(
            self.store.generation_job_path(job.authoring_dataset_id, job.job_id), job
        )
        return job

    def _replace_generation_job_item(
        self,
        job: AuthoringGenerationJob,
        index: int,
        item: GenerationJobItem,
    ) -> AuthoringGenerationJob:
        values = list(job.items)
        values[index] = item
        return self._save_generation_job(job.model_copy(update={"items": values}))

    def _cancel_remaining_generation_items(
        self, job: AuthoringGenerationJob
    ) -> AuthoringGenerationJob:
        now = datetime.now(UTC)
        return self._save_generation_job(
            job.model_copy(
                update={
                    "state": GenerationJobStatus.CANCELLED,
                    "completed_at": now,
                    "items": [
                        item.model_copy(
                            update={
                                "state": GenerationJobItemState.CANCELLED,
                                "completed_at": now,
                            }
                        )
                        if item.state == GenerationJobItemState.PENDING
                        else item
                        for item in job.items
                    ],
                }
            )
        )

    def _complete_generation_job(self, job: AuthoringGenerationJob) -> AuthoringGenerationJob:
        if job.cancel_requested:
            return self._cancel_remaining_generation_items(job)
        succeeded = sum(item.state == GenerationJobItemState.SUCCEEDED for item in job.items)
        failed = sum(item.state == GenerationJobItemState.FAILED for item in job.items)
        state = (
            GenerationJobStatus.COMPLETED
            if succeeded == len(job.items)
            else GenerationJobStatus.PARTIAL
            if succeeded and failed
            else GenerationJobStatus.FAILED
        )
        return self._save_generation_job(
            job.model_copy(update={"state": state, "completed_at": datetime.now(UTC)})
        )

    @staticmethod
    def _generation_failure(exc: Exception) -> tuple[str, str]:
        detail = str(exc).strip() or exc.__class__.__name__
        if isinstance(exc, ProposalProviderError):
            return "provider_unavailable", detail
        if isinstance(exc, AuthoringWorkflowError):
            if "formal validation" in detail or "gate" in detail:
                return "proposal_validation_failed", detail
            if "target" in detail:
                return "target_unavailable", detail
            return "proposal_contract_failed", detail
        return "unexpected_generation_error", detail

    def register_representability_profile(
        self,
        dataset: AuthoringDataset,
        *,
        profile_id: str,
        system_id: str,
        adapter_id: str,
        execution_profile_digest: str,
        runtime_map: dict[str, Any],
    ) -> EvidenceRepresentabilityProfile:
        """Persist a content-free, Gold-independent canonical/runtime map.

        The input is the public provenance bridge contract, not an Adapter
        implementation type. Authoring retains only identifiers, coverage, and
        spans needed to diagnose whether approved canonical evidence is
        observable under the declared execution profile.
        """

        self._require_analyzed(dataset)
        if runtime_map.get("schema_version") != 1:
            raise AuthoringWorkflowError("unsupported runtime provenance map schema")
        if not dataset.document_id:
            raise AuthoringWorkflowError("analyzed source has no document ID")
        documents = runtime_map.get("documents")
        runtime_chunks = runtime_map.get("runtime_chunks")
        reverse = runtime_map.get("object_to_runtime_chunks")
        if not isinstance(documents, dict) or not isinstance(runtime_chunks, dict) or not isinstance(reverse, dict):
            raise AuthoringWorkflowError("runtime provenance map is incomplete")
        document = documents.get(dataset.document_id)
        if not isinstance(document, dict):
            raise AuthoringWorkflowError("runtime provenance map does not contain the canonical document")
        if document.get("canonical_digest") != self._canonical_digest(dataset):
            raise AuthoringWorkflowError("runtime provenance map canonical digest mismatch")

        normalized: dict[str, list[RuntimeEvidenceCoverage]] = {}
        for object_id, raw_edges in sorted(reverse.items()):
            if not isinstance(object_id, str) or not isinstance(raw_edges, list):
                raise AuthoringWorkflowError("runtime provenance reverse map is invalid")
            edges: list[RuntimeEvidenceCoverage] = []
            for raw_edge in raw_edges:
                if not isinstance(raw_edge, dict):
                    raise AuthoringWorkflowError("runtime provenance edge is invalid")
                try:
                    edge = RuntimeEvidenceCoverage.model_validate(raw_edge)
                except ValueError as exc:
                    raise AuthoringWorkflowError(f"runtime provenance edge is invalid: {exc}") from exc
                raw_chunk = runtime_chunks.get(edge.runtime_chunk_id)
                if not isinstance(raw_chunk, dict):
                    raise AuthoringWorkflowError("runtime provenance edge cites an unknown chunk")
                forward_objects = raw_chunk.get("canonical_objects")
                if not isinstance(forward_objects, list) or not any(
                    isinstance(item, dict)
                    and item.get("object_id") == object_id
                    and item.get("coverage") == edge.coverage
                    and item.get("overlap_span") == edge.overlap_span
                    for item in forward_objects
                ):
                    raise AuthoringWorkflowError("runtime provenance map does not round-trip")
                edges.append(edge)
            normalized[object_id] = sorted(
                edges,
                key=lambda item: (
                    item.runtime_chunk_id,
                    item.coverage,
                    item.overlap_span.get("start", -1),
                    item.overlap_span.get("end", -1),
                ),
            )

        status_counts = Counter(
            str(value.get("provenance_status", "missing"))
            for value in runtime_chunks.values()
            if isinstance(value, dict)
        )
        profile = EvidenceRepresentabilityProfile(
            profile_id=profile_id,
            system_id=system_id,
            adapter_id=adapter_id,
            execution_profile_digest=execution_profile_digest,
            provenance_map_digest=_json_digest(runtime_map),
            canonical_digest=self._canonical_digest(dataset),
            document_id=dataset.document_id,
            runtime_chunk_count=len(runtime_chunks),
            runtime_status_counts=dict(sorted(status_counts.items())),
            object_to_runtime_chunks=normalized,
        )
        self.store.save_model(
            self.store.representability_profile_path(
                dataset.authoring_dataset_id, profile.profile_id
            ),
            profile,
        )
        return profile

    def list_representability_profiles(
        self, dataset: AuthoringDataset
    ) -> list[EvidenceRepresentabilityProfile]:
        root = self.store.workspace(dataset.authoring_dataset_id) / "diagnostics" / "representability"
        if not root.is_dir():
            return []
        profiles = [
            self.store.load_model(path, EvidenceRepresentabilityProfile)
            for path in sorted(root.glob("*.json"))
        ]
        for profile in profiles:
            if (
                profile.canonical_digest != self._canonical_digest(dataset)
                or profile.document_id != dataset.document_id
            ):
                raise AuthoringWorkflowError("representability profile belongs to a different frozen source")
        return profiles

    def _ensure_ledger_candidate(self, dataset: AuthoringDataset, candidate: QuestionCandidate) -> None:
        """Lazily project pre-ledger candidate views without overwriting them."""

        self.ledger.ensure_dataset(dataset)
        case_id = self.ledger.case_id_for_candidate(candidate.candidate_id)
        if not self.ledger.case_history(dataset.authoring_dataset_id, case_id):
            self.ledger.project_existing_candidate(dataset, candidate)

    def _create_ledger_case(self, dataset: AuthoringDataset, candidate: QuestionCandidate) -> None:
        self.ledger.ensure_dataset(dataset)
        case_id = self.ledger.case_id_for_candidate(candidate.candidate_id)
        draft = self.ledger.case_draft_from_candidate(
            dataset,
            candidate,
            case_id=case_id,
            origin=self.ledger.origin_from_candidate(candidate),
        )
        self.ledger.create_case(
            dataset,
            draft=draft,
            actor=self.ledger.actor_from_candidate(candidate),
            reason="create Case draft from DOCX Authoring question",
        )

    def _revise_ledger_case(self, dataset: AuthoringDataset, candidate: QuestionCandidate, *, reason: str) -> None:
        self._ensure_ledger_candidate(dataset, candidate)
        case_id = self.ledger.case_id_for_candidate(candidate.candidate_id)
        current = self.ledger.current_case(dataset.authoring_dataset_id, case_id)
        draft = self.ledger.case_draft_from_candidate(
            dataset,
            candidate,
            case_id=case_id,
            origin=current.draft.origin,
        )
        self.ledger.revise_case(
            dataset,
            case_id=case_id,
            draft=draft,
            actor=self.ledger.actor_from_candidate(candidate),
            reason=reason,
        )

    def _record_ledger_resolution(
        self,
        dataset: AuthoringDataset,
        original: QuestionCandidate,
        resolved: QuestionCandidate,
    ) -> None:
        """Create/revise independent Gold and propose it only after gates pass."""

        if resolved.answer_evidence is None:
            raise AuthoringWorkflowError("resolved candidate is missing answer/evidence")
        self._ensure_ledger_candidate(dataset, original)
        case_id = self.ledger.case_id_for_candidate(resolved.candidate_id)
        case = self.ledger.current_case(dataset.authoring_dataset_id, case_id)
        actor = self.ledger.actor_from_candidate(resolved)
        if resolved.state == CandidateState.REVIEW_REQUIRED and case.lifecycle in {
            LifecycleState.DRAFT,
            LifecycleState.REJECTED,
        }:
            case = self.ledger.propose_case(
                dataset,
                case_id=case_id,
                actor=actor,
                reason="propose source-grounded Case after answer/evidence gates",
            )
        gold_id = self.ledger.gold_id_for_case(case_id)
        payload = self.ledger.gold_payload_from_candidate(resolved.answer_evidence)
        origin_candidate = resolved.model_copy(
            update={
                "generation_method": resolved.answer_evidence.resolution_method,
                "provider_metadata": resolved.answer_evidence.provider_metadata,
            }
        )
        origin = self.ledger.origin_from_candidate(origin_candidate)
        origin = origin.model_copy(
            update={"source_document_ids": (dataset.document_id,) if dataset.document_id else ()}
        )
        history = self.ledger.gold_history(dataset.authoring_dataset_id, gold_id)
        if history:
            gold = self.ledger.revise_gold(
                dataset,
                gold_id=gold_id,
                payload=payload,
                actor=actor,
                reason="create a new Gold revision from answer/evidence resolution",
                case_revision=case,
            )
        else:
            gold = self.ledger.create_gold(
                dataset,
                gold_id=gold_id,
                case_revision=case,
                payload=payload,
                origin=origin,
                actor=actor,
                reason="create independent Gold draft from answer/evidence resolution",
            )
        if resolved.state == CandidateState.REVIEW_REQUIRED and gold.lifecycle == LifecycleState.DRAFT:
            self.ledger.propose_gold(
                dataset,
                gold_id=gold.gold_id,
                actor=actor,
                reason="propose Gold after answer/evidence gates",
            )

    def _formal_accept(self, dataset: AuthoringDataset, candidate: QuestionCandidate, *, reviewer: str, note: str) -> None:
        self._ensure_ledger_candidate(dataset, candidate)
        case_id = self.ledger.case_id_for_candidate(candidate.candidate_id)
        gold_id = self.ledger.gold_id_for_case(case_id)
        case = self.ledger.current_case(dataset.authoring_dataset_id, case_id)
        gold = self.ledger.current_gold(dataset.authoring_dataset_id, gold_id)
        if reviewer in {case.actor, gold.actor}:
            raise AuthoringWorkflowError("author cannot approve their own Case or Gold")
        try:
            self.ledger.record_review(
                dataset.authoring_dataset_id,
                target_kind=TargetKind.CASE,
                reviewed_revision_id=case.case_revision_id,
                reviewer=reviewer,
                decision=ReviewDecision.APPROVE,
                checklist={"source_grounded": True, "case_ready": True},
                comments=note,
            )
            self.ledger.record_review(
                dataset.authoring_dataset_id,
                target_kind=TargetKind.GOLD,
                reviewed_revision_id=gold.gold_revision_id,
                reviewer=reviewer,
                decision=ReviewDecision.APPROVE,
                checklist={"mses_checked": True, "answer_grounded": True},
                comments=note,
            )
            reviewed_case = self.ledger.mark_reviewed(
                dataset,
                target_kind=TargetKind.CASE,
                revision_id=case.case_revision_id,
                actor=case.actor,
                reason="reviewer accepted Case",
            )
            reviewed_gold = self.ledger.mark_reviewed(
                dataset,
                target_kind=TargetKind.GOLD,
                revision_id=gold.gold_revision_id,
                actor=gold.actor,
                reason="reviewer accepted Gold",
            )
            self.ledger.approve(
                dataset,
                target_kind=TargetKind.CASE,
                revision_id=reviewed_case.case_revision_id,  # type: ignore[union-attr]
                approver=reviewer,
                role=ActorRole.REVIEWER,
                reason="reviewer approval after checklist review",
            )
            self.ledger.approve(
                dataset,
                target_kind=TargetKind.GOLD,
                revision_id=reviewed_gold.gold_revision_id,  # type: ignore[union-attr]
                approver=reviewer,
                role=ActorRole.REVIEWER,
                reason="reviewer approval after checklist review",
            )
        except ValueError as exc:
            raise AuthoringWorkflowError(f"formal ledger approval failed: {exc}") from exc

    def _formal_reject(self, dataset: AuthoringDataset, candidate: QuestionCandidate, *, reviewer: str, note: str) -> None:
        self._ensure_ledger_candidate(dataset, candidate)
        case_id = self.ledger.case_id_for_candidate(candidate.candidate_id)
        case = self.ledger.current_case(dataset.authoring_dataset_id, case_id)
        try:
            if case.lifecycle == LifecycleState.DRAFT:
                case = self.ledger.propose_case(dataset, case_id=case_id, actor=case.actor, reason="submit Case for rejection review")
            self.ledger.reject(dataset, target_kind=TargetKind.CASE, revision_id=case.case_revision_id, reviewer=reviewer, reason=note or "reviewer rejected Case")
            gold_id = self.ledger.gold_id_for_case(case_id)
            history = self.ledger.gold_history(dataset.authoring_dataset_id, gold_id)
            if history:
                gold = history[-1]
                if gold.lifecycle == LifecycleState.DRAFT:
                    gold = self.ledger.propose_gold(dataset, gold_id=gold.gold_id, actor=gold.actor, reason="submit Gold for rejection review")
                if gold.lifecycle in {LifecycleState.PROPOSED, LifecycleState.REVIEWED}:
                    self.ledger.reject(dataset, target_kind=TargetKind.GOLD, revision_id=gold.gold_revision_id, reviewer=reviewer, reason=note or "reviewer rejected Gold")
        except ValueError as exc:
            raise AuthoringWorkflowError(f"formal ledger rejection failed: {exc}") from exc

    def _formal_edit(self, dataset: AuthoringDataset, previous: QuestionCandidate, updated: QuestionCandidate, *, reviewer: str, note: str) -> None:
        self._ensure_ledger_candidate(dataset, previous)
        case_id = self.ledger.case_id_for_candidate(previous.candidate_id)
        case = self.ledger.current_case(dataset.authoring_dataset_id, case_id)
        try:
            if case.lifecycle == LifecycleState.DRAFT:
                case = self.ledger.propose_case(dataset, case_id=case_id, actor=case.actor, reason="submit Case for requested-change review")
            self.ledger.record_review(
                dataset.authoring_dataset_id,
                target_kind=TargetKind.CASE,
                reviewed_revision_id=case.case_revision_id,
                reviewer=reviewer,
                decision=ReviewDecision.REQUEST_CHANGES,
                comments=note,
            )
            draft = self.ledger.case_draft_from_candidate(dataset, updated, case_id=case_id, origin=case.draft.origin)
            new_case = self.ledger.revise_case(dataset, case_id=case_id, draft=draft, actor=self.ledger.actor_from_candidate(updated), reason="apply reviewer-requested Case changes")
            gold_id = self.ledger.gold_id_for_case(case_id)
            if updated.answer_evidence is not None:
                gold_history = self.ledger.gold_history(dataset.authoring_dataset_id, gold_id)
                if gold_history:
                    gold = gold_history[-1]
                    if gold.lifecycle == LifecycleState.DRAFT:
                        gold = self.ledger.propose_gold(dataset, gold_id=gold_id, actor=gold.actor, reason="submit Gold for requested-change review")
                    self.ledger.record_review(
                        dataset.authoring_dataset_id,
                        target_kind=TargetKind.GOLD,
                        reviewed_revision_id=gold.gold_revision_id,
                        reviewer=reviewer,
                        decision=ReviewDecision.REQUEST_CHANGES,
                        comments=note,
                    )
                    gold = self.ledger.revise_gold(
                        dataset,
                        gold_id=gold_id,
                        payload=self.ledger.gold_payload_from_candidate(updated.answer_evidence),
                        actor=self.ledger.actor_from_candidate(updated),
                        reason="apply reviewer-requested Gold changes",
                        case_revision=new_case,
                    )
                else:
                    origin_candidate = updated.model_copy(update={"generation_method": updated.answer_evidence.resolution_method, "provider_metadata": updated.answer_evidence.provider_metadata})
                    origin = self.ledger.origin_from_candidate(origin_candidate).model_copy(
                        update={"source_document_ids": (dataset.document_id,) if dataset.document_id else ()}
                    )
                    gold = self.ledger.create_gold(dataset, gold_id=gold_id, case_revision=new_case, payload=self.ledger.gold_payload_from_candidate(updated.answer_evidence), origin=origin, actor=self.ledger.actor_from_candidate(updated), reason="create Gold revision after Case edit")
                if updated.state == CandidateState.REVIEW_REQUIRED:
                    self.ledger.propose_case(dataset, case_id=case_id, actor=self.ledger.actor_from_candidate(updated), reason="re-propose edited Case")
                    if gold.lifecycle == LifecycleState.DRAFT:
                        self.ledger.propose_gold(dataset, gold_id=gold_id, actor=self.ledger.actor_from_candidate(updated), reason="re-propose edited Gold")
        except ValueError as exc:
            raise AuthoringWorkflowError(f"formal ledger edit failed: {exc}") from exc

    def _rule_targets(self, dataset: AuthoringDataset, records: list[dict[str, Any]]) -> list[BenchmarkTargetCandidate]:
        digest = self._canonical_digest(dataset)
        by_id = {str(record["object_id"]): record for record in records}
        values: list[BenchmarkTargetCandidate] = []
        blocks = [record for record in records if record.get("object_type") == "block" and record.get("canonical_value")]
        for record in blocks:
            flags: list[str] = [] if record.get("status") == "supported" else ["partial_source_representation"]
            capability = "single_document_retrieval"
            text = str(record["canonical_value"])
            if re.search(r"版本|version|v\d|批准|发布|author", text, re.I):
                capability = "version_or_authority_relation"
            values.append(self._target_value(dataset, digest=digest, capability=capability, source_ids=[str(record["object_id"])], route=["section", "text"], flags=flags, confidence=0.75, rationale="deterministic body-block discovery"))
        # Logical cells are the Platform's table-evidence atoms. Physical
        # cells remain in the Catalog as merge/topology proof and must not be
        # selected as independent Gold.
        cells = [
            record
            for record in records
            if record.get("object_type") == "logical_cell"
            and str(record.get("canonical_value", "")).strip()
        ]
        cells_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for cell in cells:
            cells_by_table[str(cell["table_id"])].append(cell)
        for table_cells in cells_by_table.values():
            ordered_cells = sorted(table_cells, key=self._cell_position)
            min_row = min(self._cell_position(item)[0] for item in ordered_cells)
            min_column = min(self._cell_position(item)[1] for item in ordered_cells)
            # A raw header such as "value" does not make a useful authoring
            # target by itself.  Prefer a data-row cell and carry its visible
            # column/row context with it so question and answer proposals can
            # be understood without relying on opaque canonical IDs.
            data_cells = [
                item
                for item in ordered_cells
                if self._cell_position(item)[0] > min_row
            ] or ordered_cells
            for cell in data_cells:
                row, column = self._cell_position(cell)
                column_headers = [
                    item for item in ordered_cells
                    if self._cell_position(item)[1] == column
                    and self._cell_position(item)[0] < row
                ]
                row_headers = [
                    item for item in ordered_cells
                    if self._cell_position(item)[0] == row
                    and min_column <= self._cell_position(item)[1] < column
                ]
                source_records = column_headers + row_headers + [cell]
                source_ids = list(dict.fromkeys(str(item["object_id"]) for item in source_records))
                flags = []
                if any(item.get("status") != "supported" for item in source_records):
                    flags.append("partial_source_representation")
                elif any(item.get("gold_evidence_eligible") is False for item in source_records):
                    flags.append("gold_evidence_prohibited")
                same_table = [str(other["object_id"]) for other in ordered_cells if str(other["object_id"]) not in source_ids]
                values.append(self._target_value(dataset, digest=digest, capability="table_lookup", source_ids=source_ids, route=["table", "row", "cell"], distractors=same_table[:6], flags=flags, confidence=0.85, rationale="deterministic table data-cell discovery with visible header context"))
        token_occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for block in blocks:
            for token in _tokens(str(block["canonical_value"])):
                token_occurrences[token].append(block)
        for occurrences in token_occurrences.values():
            section_ids = {str(item.get("structural_locator", {}).get("section_id", "")) for item in occurrences}
            if len(occurrences) >= 2 and len(section_ids) >= 2:
                source_ids = sorted({str(item["object_id"]) for item in occurrences})[:3]
                values.append(self._target_value(dataset, digest=digest, capability="cross_section_relation", source_ids=source_ids, route=["section", "text", "cross_section"], flags=["requires_question_review"], confidence=0.55, rationale="repeated entity/value across sections"))
        for table_id, table_cells in cells_by_table.items():
            if len(table_cells) >= 2:
                values.append(self._target_value(dataset, digest=digest, capability="negative_candidate", source_ids=[str(table_cells[0]["object_id"])], route=["table", "negative"], distractors=[str(item["object_id"]) for item in table_cells[1:5]], flags=["requires_manual_absence_proof"], confidence=0.4, rationale="plausible near-miss negative from sibling table cells"))
        for record in records:
            if record.get("object_type") in {"equation", "figure", "embedded_object", "note"}:
                values.append(self._target_value(dataset, digest=digest, capability=f"{record['object_type']}_diagnostic", source_ids=[str(record["object_id"])], route=[str(record["object_type"])], flags=["partial_source_representation"] if record.get("status") != "supported" else [], confidence=0.3, rationale="rich-object diagnostic discovery"))
        return values

    def _ollama_targets(
        self,
        dataset: AuthoringDataset,
        records: list[dict[str, Any]],
        *,
        seed: int,
        timeout_seconds: float | None = 60.0,
    ) -> list[BenchmarkTargetCandidate]:
        # Some DOCX cells and paragraphs are very large. Sending the first
        # 100 raw records can overflow a local model context window, which
        # makes a healthy model look unavailable and leaves a rule-only
        # discovery snapshot behind. Discovery needs source-cited excerpts,
        # not every byte of the document.
        source = self._source_subset(
            dataset,
            [str(record["object_id"]) for record in records if record.get("status") == "supported"],
            max_items=28,
            max_value_chars=600,
            include_witness=False,
        )
        prompt = (
            "Propose structure-grounded RAG benchmark targets. Return JSON {targets:[{capability,source_object_ids,retrieval_route,distractor_object_ids,confidence,rationale}]}. "
            "Every cited object ID must be from SOURCE JSON. Do not include questions or answers. Do not enforce quotas."
        )
        provider, _method = self._configured_proposal_provider(
            LLMStage.TARGET_DISCOVERY,
            requested="ollama",
            remote_consent=False,
        )
        if provider is None:
            provider = LocalOllamaProvider(timeout_seconds=timeout_seconds)
        elif isinstance(provider, LocalOllamaProvider):
            # Stage configuration supplies the endpoint/model.  Preserve that
            # configuration while allowing the durable discovery worker to
            # wait without an HTTP timeout.
            provider = replace(provider, timeout_seconds=timeout_seconds)
        value = provider.propose(task="target_discovery", source=source, prompt=prompt, seed=seed)
        return self._proposal_targets(dataset, value, provider=DiscoveryMethod.OLLAMA, metadata=provider_metadata(provider, prompt=prompt, seed=seed))

    def _remote_targets(self, dataset: AuthoringDataset, records: list[dict[str, Any]], *, seed: int) -> list[BenchmarkTargetCandidate]:
        source = self._source_subset(dataset, [str(record["object_id"]) for record in records if record.get("status") == "supported"][:100])
        prompt = "Propose only source-cited RAG benchmark targets as JSON {targets:[...]}; do not generate answers."
        provider, _method = self._configured_proposal_provider(
            LLMStage.TARGET_DISCOVERY,
            requested="remote",
            remote_consent=True,
        )
        if provider is None:
            provider = ConfiguredRemoteProvider.from_environment()
        value = provider.propose(task="target_discovery", source=source, prompt=prompt, seed=seed)
        return self._proposal_targets(dataset, value, provider=DiscoveryMethod.REMOTE, metadata=provider_metadata(provider, prompt=prompt, seed=seed))

    def _proposal_targets(self, dataset: AuthoringDataset, value: dict[str, Any], *, provider: DiscoveryMethod, metadata: dict[str, Any]) -> list[BenchmarkTargetCandidate]:
        raw_targets = value.get("targets")
        if not isinstance(raw_targets, list):
            raise AuthoringWorkflowError("target proposal must contain a targets array")
        records = {str(record["object_id"]): record for record in self._records(dataset.authoring_dataset_id)}
        values: list[BenchmarkTargetCandidate] = []
        for raw in raw_targets:
            if not isinstance(raw, dict):
                continue
            source_ids = raw.get("source_object_ids")
            if not isinstance(source_ids, list) or not source_ids or not all(isinstance(item, str) for item in source_ids):
                continue
            invalid = sorted(set(source_ids).difference(records))
            flags = ["invalid_model_citation"] if invalid else []
            if invalid:
                continue
            capability = raw.get("capability") if isinstance(raw.get("capability"), str) else "model_proposed"
            route = raw.get("retrieval_route") if isinstance(raw.get("retrieval_route"), list) else ["source"]
            distractors = raw.get("distractor_object_ids") if isinstance(raw.get("distractor_object_ids"), list) else []
            values.append(self._target_value(dataset, digest=self._canonical_digest(dataset), capability=capability, source_ids=source_ids, route=[str(item) for item in route], distractors=[str(item) for item in distractors if str(item) in records], flags=flags, confidence=float(raw.get("confidence", 0.5)) if isinstance(raw.get("confidence", 0.5), (int, float)) else 0.5, rationale=str(raw.get("rationale", "model proposal")), method=provider))
        return values

    def _proposal(
        self,
        *,
        task: str,
        source: list[dict[str, Any]],
        prompt: str,
        seed: int,
        provider: DiscoveryMethod,
        remote_consent: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], DiscoveryMethod]:
        stage = {
            "target_discovery": LLMStage.TARGET_DISCOVERY,
            "question_generation": LLMStage.QUESTION_GENERATION,
            "answer_evidence_resolution": LLMStage.ANSWER_EVIDENCE,
        }.get(task)
        if stage is not None:
            configured, configured_method = self._configured_proposal_provider(
                stage,
                requested=provider.value,
                remote_consent=remote_consent,
            )
            if configured is not None:
                value = configured.propose(task=task, source=source, prompt=prompt, seed=seed)
                return value, provider_metadata(configured, prompt=prompt, seed=seed), DiscoveryMethod(configured_method)
        if provider == DiscoveryMethod.OLLAMA:
            selected = LocalOllamaProvider()
            method = DiscoveryMethod.OLLAMA
        elif provider == DiscoveryMethod.REMOTE:
            if not remote_consent:
                raise AuthoringWorkflowError("remote generation requires explicit UI consent")
            selected = ConfiguredRemoteProvider.from_environment()
            method = DiscoveryMethod.REMOTE
        else:
            raise AuthoringWorkflowError("model generation requires local Ollama or consented server-configured remote provider")
        value = selected.propose(task=task, source=source, prompt=prompt, seed=seed)
        return value, provider_metadata(selected, prompt=prompt, seed=seed), method

    def _configured_proposal_provider(
        self,
        stage: LLMStage,
        *,
        requested: str,
        remote_consent: bool,
    ) -> tuple[Any | None, str]:
        if self.llm_configuration is None:
            return None, requested
        try:
            return self.llm_configuration.build_provider(
                stage,
                requested=requested,
                remote_consent=remote_consent,
                secret_store=self.secret_store,
            )
        except (KeyError, RuntimeError, ValueError):
            # Provider construction failures remain proposal failures. The
            # existing workflow catches ProposalProviderError for its safe
            # deterministic fallback; do not turn a settings typo into a
            # successful-looking proposal.
            return None, requested

    def _target_value(self, dataset: AuthoringDataset, *, digest: str, capability: str, source_ids: list[str], route: list[str], distractors: list[str] | None = None, flags: list[str] | None = None, confidence: float, rationale: str, method: DiscoveryMethod = DiscoveryMethod.RULE) -> BenchmarkTargetCandidate:
        payload = {"capability": capability, "source": sorted(source_ids), "route": route, "method": method}
        return BenchmarkTargetCandidate(target_id=_stable_id("target", payload), source_sha256=dataset.source.sha256, canonical_digest=digest, capability=capability, source_object_ids=sorted(set(source_ids)), retrieval_route=route, distractor_object_ids=sorted(set(distractors or [])), confidence=max(0, min(1, confidence)), discovery_method=method, flags=sorted(set(flags or [])), rationale=rationale)

    @staticmethod
    def _header_path(record: dict[str, Any]) -> list[str]:
        attributes = record.get("attributes") or {}
        values = record.get("effective_header_path") or attributes.get("effective_header_path") or []
        return [str(item).strip() for item in values if str(item).strip()]

    @staticmethod
    def _cell_position(record: dict[str, Any]) -> tuple[int, int]:
        """Return one-based physical or logical coordinates."""

        locator = record.get("structural_locator") or {}
        row = record.get("row") or record.get("logical_row_start") or locator.get("row")
        column = (
            record.get("column")
            or record.get("logical_column_start")
            or locator.get("column")
        )
        return int(row or 0), int(column or 0)

    def _rule_question_proposal(
        self,
        target: BenchmarkTargetCandidate,
        records: dict[str, dict[str, Any]],
    ) -> tuple[str, list[str]]:
        """Return an explicit draft only when a direct source can be read safely.

        This recovery path is deliberately narrow.  It is useful when local
        Ollama is unavailable, but must not invent a multi-hop argument or a
        bounded absence claim that still requires human judgment.
        """

        if target.capability in {"cross_section_relation", "negative_candidate"} or "multi_hop" in target.capability:
            raise AuthoringWorkflowError("this target requires a model or human-authored question")
        source = [records[item] for item in target.source_object_ids if item in records]
        if not source:
            raise AuthoringWorkflowError("rule fallback target has no canonical source")
        table_cells = [item for item in source if item.get("object_type") in {"cell", "logical_cell"}]
        if target.capability == "table_lookup" and table_cells:
            value_cell = max(
                table_cells,
                key=self._cell_position,
            )
            header_path = self._header_path(value_cell)
            if header_path:
                label = "”下“".join(header_path[-2:])
                question = f"文档表格中“{label}”对应的内容是什么？"
            else:
                question = "文档表格中该项对应的内容是什么？"
            return question, list(target.source_object_ids)

        primary = next(
            (item for item in source if item.get("object_type") in {"block", "text_span"}),
            source[0],
        )
        text = str(primary.get("canonical_value") or primary.get("witness") or "").strip()
        if not text:
            raise AuthoringWorkflowError("rule fallback source has no visible text")
        topic = re.split(r"[。；;：:，,（(]", text, maxsplit=1)[0].strip()
        topic = re.sub(r"^(?:[一二三四五六七八九十0-9]+[、.．])\s*", "", topic)
        topic = re.sub(r"(?:为|是|有|包括|达到|采用|使用).*$", "", topic).strip()
        topic = topic[:28].strip(" ，,。；;") or "相关事项"
        return f"关于“{topic}”，文档如何说明？", list(target.source_object_ids)

    def _rule_answer_evidence_proposal(
        self,
        dataset: AuthoringDataset,
        candidate: QuestionCandidate,
        target: BenchmarkTargetCandidate,
        *,
        fallback_reason: str = "local_model_unavailable",
    ) -> AnswerEvidenceCandidate:
        """Resolve a direct canonical value as a review-required proposal.

        No automatic fallback is permitted for negative, multi-hop, or
        cross-section targets because their Gold semantics cannot be inferred
        safely from one observable value.
        """

        if target.capability in {"cross_section_relation", "negative_candidate"} or "multi_hop" in target.capability:
            raise AuthoringWorkflowError("this target requires a model or human-authored answer")
        records = {
            str(record["object_id"]): record
            for record in self._records(dataset.authoring_dataset_id)
        }
        source = [records[item] for item in candidate.source_object_ids if item in records]
        if not source:
            raise AuthoringWorkflowError("rule fallback candidate has no canonical source")
        table_cells = [item for item in source if item.get("object_type") in {"cell", "logical_cell"}]
        if target.capability == "table_lookup" and table_cells:
            evidence = max(
                table_cells,
                key=self._cell_position,
            )
        elif len(source) == 1:
            evidence = source[0]
        else:
            raise AuthoringWorkflowError("this target requires a model or human-authored answer")
        if evidence.get("status") != "supported" or evidence.get("gold_evidence_eligible") is False:
            raise AuthoringWorkflowError("rule fallback evidence is not eligible for Gold review")
        answer = str(evidence.get("canonical_value") or evidence.get("witness") or "").strip()
        if not answer:
            raise AuthoringWorkflowError("rule fallback evidence has no visible answer")
        return AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer=answer,
            evidence=[CandidateEvidence(source_object_id=str(evidence["object_id"]), required_group="direct-source")],
            locale="zh-CN",
            resolution_method=DiscoveryMethod.RULE,
            provider_metadata={
                "provider": "canonical-rule-fallback",
                "reason": fallback_reason,
                "task": "answer_evidence_resolution",
            },
        )

    def _run_gates(self, dataset: AuthoringDataset, candidate: QuestionCandidate) -> list[QualityGateResult]:
        assert candidate.answer_evidence is not None
        answer = candidate.answer_evidence
        records = {str(record["object_id"]): record for record in self._records(dataset.authoring_dataset_id)}
        gates: list[QualityGateResult] = []
        source_match = candidate.source_sha256 == dataset.source.sha256 and candidate.canonical_digest == self._canonical_digest(dataset)
        gates.append(self._gate("source_evidence_digest_match", GateStatus.PASS if source_match else GateStatus.FAIL, "candidate source and canonical digests match frozen source" if source_match else "candidate was created against a different source"))
        filename = dataset.source.original_filename.casefold()
        question_norm = _normalize(candidate.question)
        cue_values = [filename, Path(filename).stem, candidate.candidate_id.casefold(), dataset.document_id or ""] + candidate.source_object_ids
        leakage = [item for item in cue_values if item and _normalize(item) in question_norm]
        gates.append(self._gate("title_file_object_id_leakage", GateStatus.FAIL if leakage else GateStatus.PASS, "question exposes title/file/object identity" if leakage else "question contains no file or object-ID cue", {"matches": leakage}))
        if answer.answer_kind != "abstain" and answer.canonical_answer not in (None, "", []):
            values = answer.canonical_answer if isinstance(answer.canonical_answer, list) else [answer.canonical_answer]
            leaked_answers = [str(value) for value in values if len(_normalize(str(value))) >= 3 and _normalize(str(value)) in question_norm]
            gates.append(self._gate("answer_leakage", GateStatus.FAIL if leaked_answers else GateStatus.PASS, "question contains its proposed answer" if leaked_answers else "question does not contain proposed answer", {"matches": leaked_answers}))
        else:
            gates.append(self._gate("answer_leakage", GateStatus.PASS, "abstention has no proposed answer string"))
        # Rejected and blocked candidates are historical review evidence, not
        # active proposals. Regenerating a source must not fail solely because
        # an author rejected an earlier version or a prior attempt was blocked
        # before it became reviewable.
        known_questions = [
            item
            for item in self.list_candidates(dataset)
            if item.candidate_id != candidate.candidate_id
            and item.state not in {CandidateState.REJECTED, CandidateState.BLOCKED}
        ]
        overlap = max((self._question_overlap(candidate.question, item.question) for item in known_questions), default=0.0)
        overlap_status = GateStatus.FAIL if overlap >= 0.98 else (GateStatus.FLAG if overlap >= 0.75 else GateStatus.PASS)
        gates.append(self._gate("duplicate_template_overlap", overlap_status, "question overlaps an existing candidate" if overlap_status != GateStatus.PASS else "no material candidate overlap", {"max_overlap": overlap}))
        evidence_records = [records.get(item.source_object_id) for item in answer.evidence]
        missing = [item.source_object_id for item, record in zip(answer.evidence, evidence_records) if record is None]
        unsupported = [
            str(record["object_id"])
            for record in evidence_records
            if record is not None
            and (
                record.get("status") != "supported"
                or record.get("gold_evidence_eligible") is False
            )
        ]
        locator_status = GateStatus.FAIL if missing or unsupported else GateStatus.PASS
        gates.append(self._gate("locator_witness_round_trip", locator_status, "evidence has missing or non-observable representations" if locator_status == GateStatus.FAIL else "every evidence item has a supported canonical witness", {"missing": missing, "unsupported_or_partial": unsupported}))
        cell_evidence = [record for record in evidence_records if record is not None and record.get("object_type") == "cell"]
        gates.append(self._gate("table_recomputation", GateStatus.FLAG if cell_evidence and answer.answer_kind in {"numeric", "formula"} else GateStatus.PASS, "numeric/formula table answer requires reviewer recomputation" if cell_evidence and answer.answer_kind in {"numeric", "formula"} else "not a table recomputation candidate"))
        if answer.answer_kind == "abstain":
            negative_ok = bool(answer.negative_scope_object_ids and answer.negative_rationale and not answer.evidence)
            gates.append(self._gate("negative_absence", GateStatus.FLAG if negative_ok else GateStatus.FAIL, "negative scope requires reviewer validation" if negative_ok else "abstention requires scope/rationale and no positive evidence"))
        else:
            gates.append(self._gate("negative_absence", GateStatus.PASS, "positive answer is not an abstention case"))
        target = self._target(dataset, candidate.target_id)
        if "multi_hop" in target.capability or target.capability == "cross_section_relation":
            multi_source = len(set(candidate.source_object_ids)) >= 2 and len({item.source_object_id for item in answer.evidence}) >= 2
            gates.append(self._gate("single_block_shortcut", GateStatus.FAIL if not multi_source else GateStatus.PASS, "multi-hop claim has a single-block shortcut" if not multi_source else "multi-hop case uses separate source objects"))
            gates.append(self._gate("multi_hop_removal", GateStatus.FLAG if multi_source else GateStatus.FAIL, "removal test requires reviewer/model validation" if multi_source else "cannot run removal test without multi-source evidence"))
        else:
            gates.extend([self._gate("single_block_shortcut", GateStatus.PASS, "target does not claim multi-hop reasoning"), self._gate("multi_hop_removal", GateStatus.PASS, "target does not claim multi-hop reasoning")])
        representable = not missing and not unsupported and (answer.answer_kind == "abstain" or bool(answer.evidence))
        gates.append(self._gate("export_representability", GateStatus.PASS if representable else GateStatus.FAIL, "answer/evidence maps to Bundle 2.0" if representable else "answer/evidence cannot be faithfully exported"))
        gates.append(self._evidence_representability_gate(dataset, answer))
        gates.append(self._gate("alternative_answers", GateStatus.FLAG, "alternative answer audit requires mandatory human review"))
        return gates

    def _evidence_representability_gate(
        self,
        dataset: AuthoringDataset,
        resolution: AnswerEvidenceCandidate,
    ) -> QualityGateResult:
        profiles = self.list_representability_profiles(dataset)
        if not profiles:
            return self._gate(
                "runtime_evidence_representability",
                GateStatus.FLAG,
                "no canonical execution representability profile is configured",
                {"case_status": EvidenceRepresentabilityStatus.NOT_CONFIGURED, "profiles": []},
            )

        grouped: dict[str, list[str]] = defaultdict(list)
        if resolution.answer_kind == "abstain":
            grouped["negative-scope"].extend(resolution.negative_scope_object_ids)
        else:
            for evidence in resolution.evidence:
                grouped[evidence.required_group].append(evidence.source_object_id)

        profile_results: list[dict[str, Any]] = []
        aggregate = EvidenceRepresentabilityStatus.FULL
        for profile in profiles:
            group_results: list[dict[str, Any]] = []
            profile_status = EvidenceRepresentabilityStatus.FULL
            for group_id, object_ids in sorted(grouped.items()):
                evidence_results: list[dict[str, Any]] = []
                has_full = False
                has_partial = False
                for object_id in sorted(set(object_ids)):
                    edges = profile.object_to_runtime_chunks.get(object_id, [])
                    full_chunks = sorted(
                        {edge.runtime_chunk_id for edge in edges if edge.coverage == "full"}
                    )
                    partial_chunks = sorted(
                        {edge.runtime_chunk_id for edge in edges if edge.coverage == "partial"}
                    )
                    has_full = has_full or bool(full_chunks)
                    has_partial = has_partial or bool(partial_chunks)
                    evidence_results.append(
                        {
                            "source_object_id": object_id,
                            "status": (
                                EvidenceRepresentabilityStatus.FULL
                                if full_chunks
                                else EvidenceRepresentabilityStatus.PARTIAL_UNOBSERVABLE
                                if partial_chunks
                                else EvidenceRepresentabilityStatus.UNOBSERVABLE
                            ),
                            "full_runtime_chunk_ids": full_chunks,
                            "partial_runtime_chunk_ids": partial_chunks,
                        }
                    )
                group_status = (
                    EvidenceRepresentabilityStatus.FULL
                    if has_full
                    else EvidenceRepresentabilityStatus.PARTIAL_UNOBSERVABLE
                    if has_partial
                    else EvidenceRepresentabilityStatus.UNOBSERVABLE
                )
                if group_status == EvidenceRepresentabilityStatus.UNOBSERVABLE:
                    profile_status = EvidenceRepresentabilityStatus.UNOBSERVABLE
                elif (
                    group_status == EvidenceRepresentabilityStatus.PARTIAL_UNOBSERVABLE
                    and profile_status == EvidenceRepresentabilityStatus.FULL
                ):
                    profile_status = EvidenceRepresentabilityStatus.PARTIAL_UNOBSERVABLE
                group_results.append(
                    {
                        "required_group": group_id,
                        "status": group_status,
                        "evidence": evidence_results,
                    }
                )
            if profile_status == EvidenceRepresentabilityStatus.UNOBSERVABLE:
                aggregate = EvidenceRepresentabilityStatus.UNOBSERVABLE
            elif (
                profile_status == EvidenceRepresentabilityStatus.PARTIAL_UNOBSERVABLE
                and aggregate == EvidenceRepresentabilityStatus.FULL
            ):
                aggregate = EvidenceRepresentabilityStatus.PARTIAL_UNOBSERVABLE
            profile_results.append(
                {
                    "profile_id": profile.profile_id,
                    "system_id": profile.system_id,
                    "adapter_id": profile.adapter_id,
                    "execution_profile_digest": profile.execution_profile_digest,
                    "provenance_map_digest": profile.provenance_map_digest,
                    "status": profile_status,
                    "groups": group_results,
                }
            )
        return self._gate(
            "runtime_evidence_representability",
            GateStatus.PASS if aggregate == EvidenceRepresentabilityStatus.FULL else GateStatus.FLAG,
            (
                "every required evidence group has full runtime chunk coverage"
                if aggregate == EvidenceRepresentabilityStatus.FULL
                else "runtime chunk coverage is partial or unobservable; do not classify as an ordinary retrieval miss"
            ),
            {"case_status": aggregate, "profiles": profile_results},
        )

    @staticmethod
    def _gate(gate_id: str, status: GateStatus, message: str, details: dict[str, Any] | None = None) -> QualityGateResult:
        return QualityGateResult(gate_id=gate_id, status=status, message=message, details=details or {})

    @staticmethod
    def _question_overlap(first: str, second: str) -> float:
        left, right = _tokens(first), _tokens(second)
        if not left or not right:
            return 1.0 if _normalize(first) == _normalize(second) else 0.0
        return len(left & right) / len(left | right)

    def _validate_resolution(self, dataset: AuthoringDataset, resolution: AnswerEvidenceCandidate) -> None:
        if resolution.answer_kind == "abstain":
            if resolution.canonical_answer not in (None, "", []):
                raise AuthoringWorkflowError("abstention cannot contain a canonical answer")
        elif resolution.canonical_answer in (None, "", []):
            raise AuthoringWorkflowError("non-abstain answer needs a canonical answer")
        if resolution.answer_kind != "numeric" and resolution.tolerance is not None:
            raise AuthoringWorkflowError("tolerance is valid only for numeric answers")
        records = {str(record["object_id"]): record for record in self._records(dataset.authoring_dataset_id)}
        for evidence in resolution.evidence:
            if evidence.source_object_id not in records:
                raise AuthoringWorkflowError("evidence cites an unknown canonical object")
            unknown_near_miss = set(evidence.near_miss_object_ids).difference(records)
            if unknown_near_miss:
                raise AuthoringWorkflowError("near-miss evidence cites unknown canonical object")
        if resolution.answer_kind != "abstain" and not resolution.evidence:
            raise AuthoringWorkflowError("positive answer needs source evidence")

    def _blocked_cases(self, dataset: AuthoringDataset) -> list[dict[str, Any]]:
        blocked: list[dict[str, Any]] = []
        for candidate in self.list_candidates(dataset):
            if candidate.state == CandidateState.APPROVED:
                continue
            if candidate.state == CandidateState.REJECTED:
                continue
            if candidate.answer_evidence is None:
                continue
            failures = [gate.gate_id for gate in candidate.gates if gate.status == GateStatus.FAIL]
            if failures:
                blocked.append({"candidate_id": candidate.candidate_id, "reason": "failed_gates", "gates": failures})
        return blocked

    def _records(self, authoring_dataset_id: str) -> list[dict[str, Any]]:
        workspace = self.store.workspace(authoring_dataset_id)
        path = workspace / "canonical" / "evidence.jsonl"
        if not path.is_file():
            raise AuthoringWorkflowError("canonical evidence view is unavailable")
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _source_subset(
        self,
        dataset: AuthoringDataset,
        object_ids: list[str],
        *,
        max_items: int | None = None,
        max_value_chars: int | None = None,
        include_witness: bool = True,
    ) -> list[dict[str, Any]]:
        records = {str(record["object_id"]): record for record in self._records(dataset.authoring_dataset_id)}
        result: list[dict[str, Any]] = []
        for item in object_ids:
            if item not in records:
                continue
            if max_items is not None and len(result) >= max_items:
                break
            record = records[item]
            value = str(record["canonical_value"])
            if max_value_chars is not None and len(value) > max_value_chars:
                lead = max(1, max_value_chars * 3 // 4)
                tail = max(1, max_value_chars - lead)
                value = f"{value[:lead]}\n…[已截断]…\n{value[-tail:]}"
            source = {
                "object_id": item,
                "object_type": record["object_type"],
                "canonical_value": value,
            }
            if include_witness:
                source["witness"] = record["witness"]
            result.append(source)
        return result

    @staticmethod
    def _table_context_ids(records: dict[str, dict[str, Any]], object_ids: list[str]) -> list[str]:
        """Find visible table labels around cited cells without widening Gold truth.

        Older target artifacts could cite only a data cell.  Its column header
        and row label are presentation context, not extra candidate evidence,
        but they are necessary for a person (and a question proposal) to read
        that cell naturally.  Candidate citations remain fail-closed against
        the original target source IDs.
        """

        context: list[str] = []
        for object_id in object_ids:
            cell = records.get(object_id)
            if cell is None or cell.get("object_type") not in {"cell", "logical_cell"}:
                continue
            table_id = cell.get("table_id")
            if not table_id:
                continue
            row, column = AuthoringWorkflow._cell_position(cell)
            table_cells = sorted(
                (
                    item
                    for item in records.values()
                    if item.get("table_id") == table_id
                    and item.get("object_type") == cell.get("object_type")
                    and str(item.get("canonical_value") or "").strip()
                ),
                key=AuthoringWorkflow._cell_position,
            )
            min_row = min(
                AuthoringWorkflow._cell_position(item)[0] for item in table_cells
            )
            min_column = min(
                AuthoringWorkflow._cell_position(item)[1] for item in table_cells
            )
            seen_text: set[str] = set()
            for item in table_cells:
                item_id = str(item["object_id"])
                item_row, item_column = AuthoringWorkflow._cell_position(item)
                is_column_context = item_column == column and item_row == min_row
                is_row_context = item_row == row and item_column == min_column
                text = str(item.get("canonical_value") or "").strip()
                if (is_column_context or is_row_context) and item_id not in object_ids and item_id not in context and text not in seen_text:
                    context.append(item_id)
                    seen_text.add(text)
        return context[:8]

    def _target(self, dataset: AuthoringDataset, target_id: str) -> BenchmarkTargetCandidate:
        for target in self.list_targets(dataset):
            if target.target_id == target_id:
                return target
        raise AuthoringWorkflowError("unknown target ID")

    @staticmethod
    def _canonical_digest(dataset: AuthoringDataset) -> str:
        if not dataset.canonical_digest:
            raise AuthoringWorkflowError("dataset has not been canonicalized")
        return dataset.canonical_digest

    def _validate_candidate_source(self, dataset: AuthoringDataset, candidate: QuestionCandidate) -> None:
        if candidate.source_sha256 != dataset.source.sha256 or candidate.canonical_digest != self._canonical_digest(dataset):
            raise AuthoringWorkflowError("candidate belongs to a different frozen source")

    def _save_candidate(self, dataset: AuthoringDataset, candidate: QuestionCandidate) -> None:
        self._validate_candidate_source(dataset, candidate)
        self.store.save_model(self.store.candidate_path(dataset.authoring_dataset_id, candidate.candidate_id), candidate)

    @staticmethod
    def _require_analyzed(dataset: AuthoringDataset) -> None:
        if dataset.state not in {AuthoringState.ANALYZED, AuthoringState.TARGETS_READY, AuthoringState.CANDIDATES_READY, AuthoringState.REVIEW_REQUIRED, AuthoringState.APPROVED, AuthoringState.EXPORTED, AuthoringState.REGISTERED, AuthoringState.BLOCKED}:
            raise AuthoringWorkflowError("dataset must be analyzed before authoring")

    @staticmethod
    def _require_editable(dataset: AuthoringDataset) -> None:
        if dataset.state == AuthoringState.FORMAL_RELEASED:
            raise AuthoringWorkflowError(
                "formal dataset is already published; start a new authoring flow for changes"
            )

    def _advance_state(self, dataset: AuthoringDataset, state: AuthoringState) -> None:
        allowed = {AuthoringState.ANALYZED, AuthoringState.TARGETS_READY, AuthoringState.CANDIDATES_READY, AuthoringState.REVIEW_REQUIRED, AuthoringState.APPROVED, AuthoringState.EXPORTED, AuthoringState.REGISTERED, AuthoringState.BLOCKED}
        if dataset.state not in allowed:
            return
        current = self.store.get(dataset.authoring_dataset_id)
        # Never rewind a release merely because an earlier UI operation is retried.
        order = {item: index for index, item in enumerate((AuthoringState.ANALYZED, AuthoringState.TARGETS_READY, AuthoringState.CANDIDATES_READY, AuthoringState.REVIEW_REQUIRED, AuthoringState.APPROVED, AuthoringState.EXPORTED, AuthoringState.REGISTERED))}
        if current.state in order and state in order and order[current.state] > order[state]:
            return
        self.store.save(current.model_copy(update={"state": state}))
