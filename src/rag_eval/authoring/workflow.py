"""Structure-first targets, reviewable candidates, gates, and Bundle export.

This module only manipulates Authoring workspace state and filesystem export
directories.  Registration into Evaluation's DatasetBundleStore is performed
by the API/composition layer after export, preserving the domain boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from rag_eval.authoring.models import (
    AnswerEvidenceCandidate,
    ApprovedCase,
    AuthoringDataset,
    AuthoringExport,
    AuthoringState,
    BenchmarkTargetCandidate,
    CandidateState,
    DiscoveryMethod,
    GateStatus,
    QualityGateResult,
    QuestionCandidate,
    ReviewRecord,
)
from rag_eval.authoring.providers import (
    ConfiguredRemoteProvider,
    LocalOllamaProvider,
    ProposalProviderError,
    provider_metadata,
)
from rag_eval.authoring.storage import AuthoringWorkspaceStore
from rag_eval.storage.atomic import atomic_write_json


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

    def __init__(self, store: AuthoringWorkspaceStore) -> None:
        self.store = store

    def discover_targets(
        self,
        dataset: AuthoringDataset,
        *,
        provider: DiscoveryMethod = DiscoveryMethod.OLLAMA,
        seed: int = 0,
        remote_consent: bool = False,
    ) -> list[BenchmarkTargetCandidate]:
        self._require_analyzed(dataset)
        records = self._records(dataset.authoring_dataset_id)
        targets = self._rule_targets(dataset, records)
        provider_flags: list[str] = []
        if provider == DiscoveryMethod.OLLAMA:
            try:
                targets.extend(self._ollama_targets(dataset, records, seed=seed))
            except ProposalProviderError:
                provider_flags.append("local_model_unavailable_rule_fallback")
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
        atomic_write_json(
            self.store.target_path(dataset.authoring_dataset_id),
            {"source_sha256": dataset.source.sha256, "canonical_digest": dataset.canonical_digest, "targets": [item.model_dump(mode="json") for item in normalized]},
        )
        self._advance_state(dataset, AuthoringState.TARGETS_READY)
        return normalized

    def list_targets(self, dataset: AuthoringDataset) -> list[BenchmarkTargetCandidate]:
        path = self.store.target_path(dataset.authoring_dataset_id)
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_sha256") != dataset.source.sha256 or payload.get("canonical_digest") != dataset.canonical_digest:
            raise AuthoringWorkflowError("target discovery was created against a different frozen source")
        return [BenchmarkTargetCandidate.model_validate(value) for value in payload.get("targets", [])]

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

        This is deliberately independent from answer/evidence resolution.  A
        failed local model leaves manual authoring available instead of falling
        back to a hidden template question.
        """

        target = self._target(dataset, target_id)
        source = self._source_subset(dataset, target.source_object_ids)
        prompt = (
            "Create exactly one Chinese RAG benchmark question grounded only in the supplied source objects. "
            "Return JSON {question, source_object_ids}. Do not include object IDs, file names, titles as cues, "
            "or an answer. The question must require retrieval; do not use a fixed template."
        )
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
        candidate = self.create_question(
            dataset,
            target_id=target_id,
            question=question,
            method=method,
            provider_metadata_value=metadata,
        )
        candidate = candidate.model_copy(update={"source_object_ids": citations})
        self._save_candidate(dataset, candidate)
        return candidate

    def resolve_answer_evidence(
        self,
        dataset: AuthoringDataset,
        *,
        candidate_id: str,
        resolution: AnswerEvidenceCandidate,
    ) -> QuestionCandidate:
        """Attach a separately supplied/manual source-grounded answer/evidence pass."""

        candidate = self.get_candidate(dataset, candidate_id)
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
        value, metadata, method = self._proposal(
            task="answer_evidence_resolution",
            source=source,
            prompt=prompt,
            seed=seed,
            provider=provider,
            remote_consent=remote_consent,
        )
        try:
            resolution = AnswerEvidenceCandidate.model_validate(
                value | {"resolution_method": method, "provider_metadata": metadata}
            )
        except ValueError as exc:
            raise AuthoringWorkflowError(f"answer/evidence proposal has invalid schema: {exc}") from exc
        return self.resolve_answer_evidence(dataset, candidate_id=candidate_id, resolution=resolution)

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
        candidate = self.get_candidate(dataset, candidate_id)
        if decision not in {"accept", "edit", "reject"}:
            raise AuthoringWorkflowError("review decision must be accept, edit, or reject")
        if not reviewer.strip():
            raise AuthoringWorkflowError("reviewer is required")
        if candidate.state == CandidateState.APPROVED and decision != "accept":
            raise AuthoringWorkflowError("approved candidates are immutable; create a new candidate for a revision")
        if decision == "accept":
            if candidate.state != CandidateState.REVIEW_REQUIRED:
                raise AuthoringWorkflowError("only a gate-reviewed candidate can be accepted")
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
            edited_fields = fields
        review = ReviewRecord(
            review_id=f"review-{uuid.uuid4().hex}",
            candidate_id=candidate.candidate_id,
            candidate_version=candidate.version,
            decision=decision,  # type: ignore[arg-type]
            reviewer=reviewer.strip(),
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

    def export(self, dataset: AuthoringDataset, *, name: str, version: str) -> AuthoringExport:
        self._require_analyzed(dataset)
        if not name.strip() or not version.strip():
            raise AuthoringWorkflowError("export name and version are required")
        approved = self.list_approved(dataset)
        blocked = self._blocked_cases(dataset)
        if not approved:
            raise AuthoringWorkflowError("at least one reviewer-approved case is required for export")
        release_payload = {
            "name": name.strip(),
            "version": version.strip(),
            "source_sha256": dataset.source.sha256,
            "canonical_digest": self._canonical_digest(dataset),
            "approved": [item.model_dump(mode="json") for item in approved],
        }
        release_id = _stable_id("release", release_payload)
        release_root = self.store.export_path(dataset.authoring_dataset_id, release_id)
        views = {
            "canonical-text": release_root / "canonical-text",
            "native-docx": release_root / "native-docx",
        }
        for view_name, root in views.items():
            self._write_bundle(dataset, approved, root=root, name=name.strip(), version=version.strip(), view=view_name)
        export = AuthoringExport(
            release_id=release_id,
            name=name.strip(),
            version=version.strip(),
            source_sha256=dataset.source.sha256,
            canonical_digest=self._canonical_digest(dataset),
            approved_case_ids=[item.case_id for item in approved],
            views={name: str(path.relative_to(self.store.workspace(dataset.authoring_dataset_id))) for name, path in views.items()},
            blocked_cases=blocked,
        )
        self.store.save_model(release_root / "export.json", export)
        self._advance_state(dataset, AuthoringState.EXPORTED)
        return export

    def get_export(self, dataset: AuthoringDataset, release_id: str) -> AuthoringExport:
        return self.store.load_model(self.store.export_path(dataset.authoring_dataset_id, release_id) / "export.json", AuthoringExport)

    def mark_registered(self, dataset: AuthoringDataset, *, release_id: str, view: str, bundle_id: str) -> AuthoringExport:
        export = self.get_export(dataset, release_id)
        if view not in export.views:
            raise AuthoringWorkflowError("unknown execution view")
        updated = export.model_copy(update={"registered_bundle_ids": export.registered_bundle_ids | {view: bundle_id}})
        self.store.save_model(self.store.export_path(dataset.authoring_dataset_id, release_id) / "export.json", updated)
        self._advance_state(dataset, AuthoringState.REGISTERED)
        return updated

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
        cells = [record for record in records if record.get("object_type") == "cell" and str(record.get("canonical_value", "")).strip()]
        cells_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for cell in cells:
            cells_by_table[str(cell["table_id"])].append(cell)
            flags = [] if cell.get("status") == "supported" else ["partial_source_representation"]
            same_table = [str(other["object_id"]) for other in cells_by_table[str(cell["table_id"])] if other["object_id"] != cell["object_id"]]
            values.append(self._target_value(dataset, digest=digest, capability="table_lookup", source_ids=[str(cell["object_id"])], route=["table", "row", "cell"], distractors=same_table[:6], flags=flags, confidence=0.85, rationale="deterministic resolved table-cell discovery"))
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

    def _ollama_targets(self, dataset: AuthoringDataset, records: list[dict[str, Any]], *, seed: int) -> list[BenchmarkTargetCandidate]:
        source = self._source_subset(dataset, [str(record["object_id"]) for record in records if record.get("status") == "supported"][:100])
        prompt = (
            "Propose structure-grounded RAG benchmark targets. Return JSON {targets:[{capability,source_object_ids,retrieval_route,distractor_object_ids,confidence,rationale}]}. "
            "Every cited object ID must be from SOURCE JSON. Do not include questions or answers. Do not enforce quotas."
        )
        provider = LocalOllamaProvider()
        value = provider.propose(task="target_discovery", source=source, prompt=prompt, seed=seed)
        return self._proposal_targets(dataset, value, provider=DiscoveryMethod.OLLAMA, metadata=provider_metadata(provider, prompt=prompt, seed=seed))

    def _remote_targets(self, dataset: AuthoringDataset, records: list[dict[str, Any]], *, seed: int) -> list[BenchmarkTargetCandidate]:
        source = self._source_subset(dataset, [str(record["object_id"]) for record in records if record.get("status") == "supported"][:100])
        prompt = "Propose only source-cited RAG benchmark targets as JSON {targets:[...]}; do not generate answers."
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

    def _target_value(self, dataset: AuthoringDataset, *, digest: str, capability: str, source_ids: list[str], route: list[str], distractors: list[str] | None = None, flags: list[str] | None = None, confidence: float, rationale: str, method: DiscoveryMethod = DiscoveryMethod.RULE) -> BenchmarkTargetCandidate:
        payload = {"capability": capability, "source": sorted(source_ids), "route": route, "method": method}
        return BenchmarkTargetCandidate(target_id=_stable_id("target", payload), source_sha256=dataset.source.sha256, canonical_digest=digest, capability=capability, source_object_ids=sorted(set(source_ids)), retrieval_route=route, distractor_object_ids=sorted(set(distractors or [])), confidence=max(0, min(1, confidence)), discovery_method=method, flags=sorted(set(flags or [])), rationale=rationale)

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
        known_questions = [item for item in self.list_candidates(dataset) if item.candidate_id != candidate.candidate_id]
        overlap = max((self._question_overlap(candidate.question, item.question) for item in known_questions), default=0.0)
        overlap_status = GateStatus.FAIL if overlap >= 0.98 else (GateStatus.FLAG if overlap >= 0.75 else GateStatus.PASS)
        gates.append(self._gate("duplicate_template_overlap", overlap_status, "question overlaps an existing candidate" if overlap_status != GateStatus.PASS else "no material candidate overlap", {"max_overlap": overlap}))
        evidence_records = [records.get(item.source_object_id) for item in answer.evidence]
        missing = [item.source_object_id for item, record in zip(answer.evidence, evidence_records) if record is None]
        unsupported = [str(record["object_id"]) for record in evidence_records if record is not None and record.get("status") != "supported"]
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
        gates.append(self._gate("alternative_answers", GateStatus.FLAG, "alternative answer audit requires mandatory human review"))
        return gates

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

    def _write_bundle(self, dataset: AuthoringDataset, approved: list[ApprovedCase], *, root: Path, name: str, version: str, view: str) -> None:
        if root.exists():
            shutil.rmtree(root)
        documents = root / "documents"
        canonical = root / "canonical"
        documents.mkdir(parents=True)
        canonical.mkdir()
        document_id = dataset.document_id
        if not document_id:
            raise AuthoringWorkflowError("analyzed source has no document ID")
        workspace = self.store.workspace(dataset.authoring_dataset_id)
        evidence_source = workspace / "canonical" / "evidence.jsonl"
        shutil.copyfile(evidence_source, canonical / "evidence.jsonl")
        if view == "canonical-text":
            source_name = f"{document_id}.md"
            shutil.copyfile(workspace / "canonical" / "execution.md", documents / source_name)
            mime_type = "text/markdown"
        elif view == "native-docx":
            source_name = f"{document_id}.docx"
            shutil.copyfile(self.store.source_path(dataset.authoring_dataset_id), documents / source_name)
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise AuthoringWorkflowError("unknown execution view")
        source_path = documents / source_name
        manifest = {
            "schema_version": 2,
            "name": name,
            "version": version,
            "created_at": dataset.created_at.isoformat(),
            "documents": [{"document_id": document_id, "path": f"documents/{source_name}", "canonical_path": "canonical/evidence.jsonl", "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "mime_type": mime_type, "metadata": {"execution_view": view, "source_sha256": dataset.source.sha256}}],
            "metadata": {"validation_profile": "formal", "authoring": {"source_sha256": dataset.source.sha256, "canonical_digest": self._canonical_digest(dataset), "execution_view": view, "private_document": True, "native_diagnostic_only": view == "native-docx"}},
        }
        questions: list[dict[str, Any]] = []
        answers: list[dict[str, Any]] = []
        evidence_sets: list[dict[str, Any]] = []
        records = {str(record["object_id"]): record for record in self._records(dataset.authoring_dataset_id)}
        for approved_case in sorted(approved, key=lambda item: item.case_id):
            candidate = approved_case.candidate
            resolution = candidate.answer_evidence
            if resolution is None:
                raise AuthoringWorkflowError(f"approved case {approved_case.case_id} has no answer/evidence")
            answer_id = f"answer-{approved_case.case_id}"
            evidence_set_id = f"evidence-set-{approved_case.case_id}"
            questions.append({"case_id": approved_case.case_id, "question": candidate.question, "gold_answer_id": answer_id, "gold_evidence_set_id": evidence_set_id, "tags": [self._target(dataset, candidate.target_id).capability], "metadata": {"authoring_candidate_id": candidate.candidate_id, "authoring_candidate_version": candidate.version}})
            answer = {"gold_answer_id": answer_id, "kind": resolution.answer_kind, "canonical": resolution.canonical_answer, "accepted_values": resolution.accepted_values, "locale": resolution.locale, "unit": resolution.unit, "tolerance": resolution.model_dump(mode="json")["tolerance"]}
            answers.append({key: value for key, value in answer.items() if value is not None})
            evidence: list[dict[str, Any]] = []
            grouped: dict[str, list[str]] = defaultdict(list)
            for index, selection in enumerate(resolution.evidence, start=1):
                record = records[selection.source_object_id]
                evidence_id = f"evidence-{approved_case.case_id}-{index}"
                if record["object_type"] == "cell":
                    locator = {"type": "table_cell", "table_id": record["table_id"], "row": record["row"], "column": record["column"]}
                else:
                    locator = {"type": "object", "object_type": record["object_type"], "object_id": record["object_id"]}
                # Structured canonical records intentionally carry value and
                # witness fields, so a quote is not unique in JSONL. Formal
                # validation instead verifies the complete locator/value record.
                evidence.append({"evidence_id": evidence_id, "document_id": document_id, "locator": locator, "canonical_value": record["canonical_value"], "quote_anchor": None})
                grouped[selection.required_group].append(evidence_id)
            if resolution.answer_kind == "abstain":
                # Bundle schema requires a non-empty evidence group. An abstention
                # is exportable only after an explicit scoped canonical witness.
                if not resolution.negative_scope_object_ids:
                    raise AuthoringWorkflowError("abstention export requires scoped negative evidence")
                record = records[resolution.negative_scope_object_ids[0]]
                evidence_id = f"evidence-{approved_case.case_id}-negative-scope"
                evidence.append({"evidence_id": evidence_id, "document_id": document_id, "locator": {"type": "object", "object_type": record["object_type"], "object_id": record["object_id"]}, "canonical_value": record["canonical_value"], "quote_anchor": None})
                grouped["negative-scope"].append(evidence_id)
            evidence_sets.append({"gold_evidence_set_id": evidence_set_id, "evidence": evidence, "required_groups": [grouped[key] for key in sorted(grouped)]})
        atomic_write_json(root / "manifest.json", manifest)
        (root / "questions.jsonl").write_text(_json_lines(questions), encoding="utf-8")
        (root / "gold_answers.jsonl").write_text(_json_lines(answers), encoding="utf-8")
        (root / "gold_evidence.jsonl").write_text(_json_lines(evidence_sets), encoding="utf-8")

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

    def _source_subset(self, dataset: AuthoringDataset, object_ids: list[str]) -> list[dict[str, Any]]:
        records = {str(record["object_id"]): record for record in self._records(dataset.authoring_dataset_id)}
        return [
            {"object_id": item, "object_type": records[item]["object_type"], "canonical_value": records[item]["canonical_value"], "witness": records[item]["witness"]}
            for item in object_ids
            if item in records
        ]

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
