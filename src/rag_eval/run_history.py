"""Unified read-only access to native runs and completed Bundle 3 rehearsals.

Completed rehearsals already use the schema-v2 ``RunManifest`` and are
immutable.  Their per-case execution/evaluation artifacts predate the normal
WebUI case/summary projection, so this reader presents a compatible view at
request time.  It never copies, rewrites, or exposes Gold-bearing fields.
"""

from __future__ import annotations

import json
import os
import hashlib
from dataclasses import asdict
from datetime import UTC
from pathlib import Path
from typing import Any, Iterable

from rag_eval.contracts.run import CaseResult, MetricResult, MetricStatus, RunManifest
from rag_eval.datasets.bundle import DatasetBundleStore
from rag_eval.execution import aggregate_metrics
from rag_eval.evaluation.evidence import (
    PROVENANCE_UNAVAILABLE_REASON,
    CorpusEvidenceIndex,
    evidence_observability,
)
from rag_eval.reviews import (
    ANSWER_SUPPORT_REVIEWER_DIGEST,
    AnswerSupportReviewStore,
    CaseReviewStore,
)
from rag_eval.run_presentations import RunPresentationStore
from rag_eval.history_provenance.acceptance import accepted_projection_receipt
from rag_eval.storage.runs import ArtifactVerification, RunStore, case_judgments, safe_id


_RUN_ARCHIVES_ENV = "RAG_EVAL_RUN_ARCHIVES"
_PRIVATE_EVALUATION_DIR = "private-evaluation"


def _review_history(value: object | None) -> list[object]:
    if value is None:
        return []
    history = value.get("history") if isinstance(value, dict) else getattr(value, "decisions", None)
    if isinstance(history, Iterable) and not isinstance(history, (str, bytes, dict)):
        return list(history)
    return []


def _review_field(decision: object, name: str) -> object | None:
    return decision.get(name) if isinstance(decision, dict) else getattr(decision, name, None)


def _review_has_human_decision(value: object | None) -> bool:
    return any(str(_review_field(item, "source")) == "human" for item in _review_history(value))


def _support_review_verdict(value: object | None) -> str | None:
    """Read a support verdict, with a human decision taking precedence."""

    history = _review_history(value)
    for decision in reversed(history):
        if str(_review_field(decision, "source")) != "human":
            continue
        verdict = str(_review_field(decision, "verdict"))
        if verdict in {"supported", "unsupported", "needs_review"}:
            return verdict
    latest = value.get("latest") if isinstance(value, dict) else getattr(value, "latest", None)
    verdict = str(_review_field(latest, "verdict"))
    return verdict if verdict in {"supported", "unsupported", "needs_review"} else None


class RunHistory:
    """Read native runs first and expose eligible archive runs as read-only."""

    def __init__(
        self,
        primary: RunStore,
        *,
        reviews: CaseReviewStore | None = None,
        answer_support_reviews: AnswerSupportReviewStore | None = None,
        presentations: RunPresentationStore | None = None,
        dataset_store: DatasetBundleStore | None = None,
        dataset_releases: Any | None = None,
        authoring_store: Any | None = None,
        historical_rescores_root: Path | None = None,
    ) -> None:
        self.primary = primary
        self.reviews = reviews
        self.answer_support_reviews = answer_support_reviews
        self.presentations = presentations
        # These stores are read-only inputs to the product projection.  A Run
        # manifest remains the immutable authority for the technical pins;
        # this reader merely resolves a human-readable dataset identity.
        self.dataset_store = dataset_store
        self.dataset_releases = dataset_releases
        self.authoring_store = authoring_store
        self.historical_rescores_root = historical_rescores_root
        # Historical rescores may be large because they retain a per-Gold
        # audit matrix. Cache a deliberately compact read model by immutable
        # file signature instead of reparsing it for every case request.
        self._historical_rescore_cache: dict[
            str, tuple[tuple[tuple[str, int, int], ...], dict[str, Any] | None]
        ] = {}

    def list(self) -> list[RunManifest]:
        values: dict[str, RunManifest] = {
            item.run_id: item for item in self.primary.list()
        }
        for store in self._archives():
            for item in store.list():
                if self._is_presentable_rehearsal(store, item.run_id):
                    values.setdefault(item.run_id, item)
        return sorted(values.values(), key=lambda item: (item.started_at, item.run_id), reverse=True)

    def get(self, run_id: str) -> RunManifest:
        return self._locate(run_id)[1].get(run_id)

    def list_views(self) -> list[dict[str, object]]:
        """Return Run manifests with a product-only, human-readable label."""

        return [self.run_view(item.run_id) for item in self.list()]

    def run_view(self, run_id: str) -> dict[str, object]:
        """Project presentation metadata without writing the immutable Run."""

        manifest = self.get(run_id)
        value: dict[str, object] = manifest.model_dump(mode="json")
        source = "manifest"
        display_name = manifest.display_name.strip() if manifest.display_name else ""
        if self.presentations is not None:
            record = self.presentations.get(run_id)
            if record.latest is not None:
                display_name = record.latest.display_name
                source = "override"
        if not display_name:
            display_name = self._default_display_name(manifest)
            source = "generated"
        value["display_name"] = display_name
        value["display_name_source"] = source
        return value

    @staticmethod
    def _default_display_name(manifest: RunManifest) -> str:
        timestamp = manifest.started_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
        system = manifest.system_id.strip() or manifest.adapter_id.strip() or "RAG"
        return f"{system} · {timestamp} · {manifest.run_id[:8]}"

    def cases(self, run_id: str) -> list[CaseResult]:
        is_primary, store = self._locate(run_id)
        if is_primary:
            return store.cases(run_id)
        return self._rehearsal_cases(store.root / safe_id(run_id))

    def case_index(self, run_id: str) -> list[dict[str, object]]:
        """Expose just enough data to navigate large per-case artifacts."""

        is_primary, store = self._locate(run_id)
        if is_primary:
            return [
                self._case_index_view(run_id, item)
                for item in store.case_index(run_id)
            ]
        return [
            {
                "case_id": item.case_id,
                "question": item.question,
                "status": str(item.status),
                "repetition": item.repetition,
                "seed": item.seed,
                **self._product_judgments(
                    run_id,
                    item,
                    metrics=item.metrics,
                    failure_assessment=self._presentation_failure_assessment(
                        run_id, item
                    ),
                    review=self.review(run_id, item.case_id, item.repetition),
                ),
                **(
                    {"answer_support_review": support_review}
                    if (
                        support_review := self.answer_support_review(
                            run_id, item.case_id, item.repetition
                        )
                    )
                    is not None
                    else {}
                ),
            }
            for item in self._rehearsal_cases(store.root / safe_id(run_id))
        ]

    def case(self, run_id: str, case_id: str, *, repetition: int = 1) -> CaseResult:
        is_primary, store = self._locate(run_id)
        if is_primary:
            return store.case(run_id, case_id, repetition=repetition)
        for item in self._rehearsal_cases(store.root / safe_id(run_id)):
            if item.case_id == case_id and item.repetition == repetition:
                return item
        raise FileNotFoundError(case_id)

    def case_view(
        self, run_id: str, case_id: str, *, repetition: int = 1
    ) -> dict[str, Any]:
        """Return an immutable case artifact with derived display outcomes."""

        item = self.case(run_id, case_id, repetition=repetition)
        projected = self._project_case_for_product(run_id, item)
        review = self.review(run_id, case_id, repetition)
        failure_assessment = self._presentation_failure_assessment(run_id, item)
        value = {
            **projected.model_dump(mode="json"),
            "failure_assessment": failure_assessment,
            **self._product_judgments(
                run_id,
                item,
                metrics=projected.metrics,
                failure_assessment=failure_assessment,
                review=review,
            ),
            "review": review,
            "historical_rescore": self._historical_rescore_view(run_id),
        }
        support_review = self.answer_support_review(run_id, case_id, repetition)
        if support_review is not None:
            value["answer_support_review"] = support_review
        return value

    def review(self, run_id: str, case_id: str, repetition: int) -> dict[str, object] | None:
        if self.reviews is None:
            return None
        record = self.reviews.get(run_id, case_id, repetition)
        return record.api_view() if record.latest is not None else None

    def semantic_review_status(self, run_id: str) -> dict[str, object] | None:
        if self.reviews is None:
            return None
        return self.reviews.review_run_status(run_id).api_view()

    def answer_support_review(
        self, run_id: str, case_id: str, repetition: int
    ) -> dict[str, object] | None:
        if self.answer_support_reviews is None:
            return None
        record = self.answer_support_reviews.get(run_id, case_id, repetition)
        return record.api_view() if record.latest is not None else None

    def semantic_support_review_status(self, run_id: str) -> dict[str, object] | None:
        if self.answer_support_reviews is None:
            return None
        return self.answer_support_reviews.review_run_status(run_id).api_view()

    def _case_index_view(self, run_id: str, value: dict[str, object]) -> dict[str, object]:
        case_id = value.get("case_id")
        repetition = value.get("repetition")
        if not isinstance(case_id, str) or not isinstance(repetition, int):
            return value
        # RunStore intentionally returns a small index. Re-read just the
        # selected compact Case to derive the current provenance/review state;
        # no evidence payload is returned to the caller.
        item = self.primary.case(run_id, case_id, repetition=repetition)
        review = self.review(run_id, case_id, repetition)
        projected = {
            **value,
            **self._product_judgments(
                run_id,
                item,
                metrics=self._project_case_for_product(run_id, item).metrics,
                failure_assessment=self._presentation_failure_assessment(
                    run_id, item
                ),
                review=review,
            ),
            "review": review,
        }
        support_review = self.answer_support_review(run_id, case_id, repetition)
        if support_review is not None:
            projected["answer_support_review"] = support_review
        return projected

    def summary(self, run_id: str) -> dict[str, Any]:
        is_primary, store = self._locate(run_id)
        root = store.root / safe_id(run_id)
        if is_primary:
            return self._product_summary(
                run_id,
                self.cases(run_id),
                store.get(run_id),
                raw_summary=self._read_object(root / "summary.json"),
            )
        manifest = store.get(run_id)
        return self._product_summary(
            run_id,
            self._rehearsal_cases(root),
            manifest,
            raw_summary=self._rehearsal_summary(root, manifest),
        )

    def _product_summary(
        self,
        run_id: str,
        cases: list[CaseResult],
        manifest: RunManifest,
        *,
        raw_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Aggregate a product read-model without changing immutable files."""

        projected = [self._project_case_for_product(run_id, item) for item in cases]
        expected = int(manifest.execution_counts.get("expected", len(cases)))
        summary = aggregate_metrics(
            projected, repetitions=manifest.repetitions, expected=expected
        )
        answers = {"correct": 0, "incorrect": 0, "needs_review": 0, "unavailable": 0}
        answer_support = {
            "supported": 0,
            "unsupported": 0,
            "needs_review": 0,
            "unavailable": 0,
        }
        evidence = {
            "grounded": 0,
            "missing": 0,
            "ungrounded": 0,
            "unverifiable": 0,
            "needs_review": 0,
            "unavailable": 0,
        }
        for item, projected_item in zip(cases, projected, strict=True):
            verdicts = self._product_judgments(
                run_id,
                item,
                metrics=projected_item.metrics,
                failure_assessment=self._presentation_failure_assessment(
                    run_id, item
                ),
                review=self.review(run_id, item.case_id, item.repetition),
            )
            answers[verdicts["answer_judgment"]] = (
                answers.get(verdicts["answer_judgment"], 0) + 1
            )
            support = _support_review_verdict(
                self.answer_support_review(run_id, item.case_id, item.repetition)
            ) or "unavailable"
            answer_support[support] = answer_support.get(support, 0) + 1
            evidence[verdicts["evidence_judgment"]] = (
                evidence.get(verdicts["evidence_judgment"], 0) + 1
            )
        return {
            **summary,
            "dataset": self._dataset_identity(manifest, cases),
            "localization": self._localization_summary(projected),
            "presentation": {
                "kind": "product_projection",
                "raw_summary_available": bool(raw_summary),
                "notes": [
                    "answer verdicts use the current deterministic rule and append-only adjudications",
                    "source localization and answer grounding are reported separately",
                    "unverifiable retrieval metrics are excluded rather than shown as zero",
                ],
            },
            "judgments": {
                "answer": answers,
                "answer_support": answer_support,
                "evidence": evidence,
            },
            "historical_rescore": self._historical_rescore_view(run_id),
            "semantic_review": self.semantic_review_status(run_id),
            "semantic_support_review": self.semantic_support_review_status(run_id),
        }

    def _dataset_identity(
        self, manifest: RunManifest, cases: list[CaseResult]
    ) -> dict[str, object]:
        """Resolve readable dataset metadata without ever mutating a Run.

        Formal releases are preferred because their display name, version, and
        Case pins are immutable.  Older releases may predate a display name;
        for those, the original DOCX filename is a truthful, useful fallback.
        Bundle metadata is only used when no formal release is available.
        """

        release = None
        if self.dataset_releases is not None and manifest.dataset_release_id:
            try:
                release = self.dataset_releases.get(manifest.dataset_release_id)
            except (FileNotFoundError, OSError, ValueError):
                release = None

        name: str | None = None
        version: str | None = None
        dataset_case_count: int | None = None
        dataset_id: str | None = None
        resolution = "unresolved"
        if release is not None:
            raw_name = getattr(release, "display_name", None)
            name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
            version_value = getattr(release, "release_version", None)
            version = version_value if isinstance(version_value, str) else None
            release_cases = getattr(release, "cases", ())
            dataset_case_count = len(release_cases) if release_cases is not None else None
            dataset_value = getattr(release, "dataset_id", None)
            dataset_id = dataset_value if isinstance(dataset_value, str) else None
            resolution = "formal_release"
            if name is None:
                document = getattr(release, "document", None)
                source_digest = getattr(document, "source_digest", None)
                if isinstance(source_digest, str):
                    name = self._source_name_for_digest(source_digest)

        bundle = None
        if self.dataset_store is not None:
            try:
                bundle = self.dataset_store.get(manifest.bundle_id)
            except (FileNotFoundError, OSError, ValueError):
                bundle = None
        if bundle is not None:
            bundle_name = getattr(bundle.manifest, "name", None)
            if name is None and isinstance(bundle_name, str) and bundle_name.strip():
                name = bundle_name.strip()
                resolution = "bundle_manifest"
            bundle_version = getattr(bundle.manifest, "version", None)
            if version is None and isinstance(bundle_version, str):
                version = bundle_version
            if dataset_case_count is None:
                dataset_case_count = len(bundle.questions)

        selected_case_count = len({item.case_id for item in cases})
        return {
            # Never turn an opaque hash into a misleading pseudo-name.  The
            # UI can make the absence actionable while retaining technical
            # pins in its inspect/details view.
            "name": name or "未命名数据集",
            "version": version,
            "case_count": dataset_case_count,
            "selected_case_count": selected_case_count,
            "resolution": resolution,
            "dataset_id": dataset_id,
            "release_id": manifest.dataset_release_id,
            "bundle_id": manifest.bundle_id,
        }

    def _source_name_for_digest(self, source_digest: str) -> str | None:
        if self.authoring_store is None:
            return None
        try:
            datasets = self.authoring_store.list()
        except (FileNotFoundError, OSError, ValueError):
            return None
        matches: list[tuple[str, str]] = []
        for dataset in datasets:
            source = getattr(dataset, "source", None)
            if getattr(source, "sha256", None) != source_digest:
                continue
            filename = getattr(source, "original_filename", None)
            authoring_id = getattr(dataset, "authoring_dataset_id", "")
            if isinstance(filename, str) and filename.strip():
                # Keep a human's source name but remove only the presentation
                # suffix. It is not inferred from any internal ID.
                matches.append((str(authoring_id), Path(filename).stem))
        return sorted(matches)[0][1] if matches else None

    @staticmethod
    def _localization_summary(cases: list[CaseResult]) -> dict[str, object]:
        """Aggregate selected-path source localization, not answer grounding.

        The four ``*_localization_*`` metrics are emitted by the production
        evaluator for one selected MSES path.  Their denominator is therefore
        a count of required clauses, not a count of answers and not the full
        diagnostic Gold matrix.  Keeping that scope explicit prevents the UI
        from calling every non-answer case "unverifiable".
        """

        statuses = (
            "matched",
            "partial",
            "retrieval_missed",
            "provenance_missing",
        )
        value: dict[str, object] = {
            "scope": "selected_path_clauses",
            "stages": {},
        }
        stages: dict[str, dict[str, object]] = {}
        for stage in ("raw", "ranked", "context"):
            counts = {status: 0.0 for status in statuses}
            denominator = 0.0
            observed_cases = 0
            unavailable_cases = 0
            reasons: set[str] = set()
            for case in cases:
                by_id = {metric.metric_id: metric for metric in case.metrics}
                metrics = [
                    by_id.get(f"{stage}_localization_{status}")
                    for status in statuses
                ]
                observed = [
                    metric
                    for metric in metrics
                    if metric is not None
                    and metric.status == MetricStatus.OBSERVED
                    and isinstance(metric.numerator, (int, float))
                    and isinstance(metric.denominator, (int, float))
                ]
                if not observed:
                    unavailable_cases += 1
                    for metric in metrics:
                        if metric is not None and metric.reason:
                            reasons.add(metric.reason)
                    continue
                # All four status metrics describe the same case/path
                # denominator.  Count it once, even when a malformed legacy
                # artifact contains only a subset of the status metrics.
                observed_cases += 1
                denominator += float(observed[0].denominator or 0)
                for status, metric in zip(statuses, metrics, strict=True):
                    if (
                        metric is not None
                        and metric.status == MetricStatus.OBSERVED
                        and isinstance(metric.numerator, (int, float))
                    ):
                        counts[status] += float(metric.numerator)
            stages[stage] = {
                **{
                    status: int(amount) if amount.is_integer() else amount
                    for status, amount in counts.items()
                },
                "denominator": int(denominator)
                if denominator.is_integer()
                else denominator,
                "observed_cases": observed_cases,
                "unavailable_cases": unavailable_cases,
                "coverage": observed_cases / len(cases) if cases else 0.0,
                "status": "observed" if observed_cases else "unavailable",
                "reason": "; ".join(sorted(reasons)) if reasons else None,
            }
        value["stages"] = stages
        return value

    def _project_case_for_product(self, run_id: str, item: CaseResult) -> CaseResult:
        review = self.review(run_id, item.case_id, item.repetition)
        answer_support_review = self.answer_support_review(
            run_id, item.case_id, item.repetition
        )
        verdicts = self._product_judgments(
            run_id,
            item,
            metrics=item.metrics,
            failure_assessment=self._presentation_failure_assessment(run_id, item),
            review=review,
        )
        historical_metrics = self._historical_rescore_metrics(run_id, item)
        metrics: list[MetricResult] = []
        for metric in historical_metrics if historical_metrics is not None else item.metrics:
            if metric.metric_id == "answer_accuracy":
                value = {"correct": 1.0, "incorrect": 0.0}.get(
                    verdicts["answer_judgment"]
                )
                if value is None:
                    metrics.append(
                        metric.model_copy(
                            update={
                                "status": MetricStatus.NEEDS_REVIEW,
                                "value": None,
                                "numerator": None,
                                "denominator": None,
                                "reason": "answer needs semantic or human adjudication",
                            }
                        )
                    )
                else:
                    metrics.append(
                        metric.model_copy(
                            update={
                                "status": MetricStatus.OBSERVED,
                                "value": value,
                                "numerator": value,
                                "denominator": 1,
                                "scorer_id": "product-answer-judgment",
                                "scorer_version": "1.0",
                                "scorer_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                                "reason": "current deterministic rule or append-only adjudication",
                            }
                        )
                    )
                continue
            if (
                metric.metric_id == "answer_hallucination"
                and metric.status == MetricStatus.NEEDS_REVIEW
            ):
                metrics.append(
                    self._project_answer_support_metric(metric, answer_support_review)
                )
                continue
            stage_reason = (
                None
                if historical_metrics is not None
                else self._metric_stage_provenance_reason(item, metric.metric_id)
            )
            if stage_reason is not None:
                metrics.append(
                    metric.model_copy(
                        update={
                            "status": MetricStatus.UNAVAILABLE,
                            "value": None,
                            "numerator": None,
                            "denominator": None,
                            "reason": stage_reason,
                        }
                    )
                )
                continue
            metrics.append(metric)
        return item.model_copy(update={"metrics": metrics})

    @staticmethod
    def _project_answer_support_metric(
        metric: MetricResult,
        review: object | None,
    ) -> MetricResult:
        """Project support review without changing immutable metric artifacts."""

        verdict = _support_review_verdict(review)
        value = {"supported": 0.0, "unsupported": 1.0}.get(verdict)
        if value is None:
            return metric.model_copy(
                update={
                    "status": MetricStatus.NEEDS_REVIEW,
                    "value": None,
                    "numerator": None,
                    "denominator": None,
                    "reason": "answer support needs semantic or human adjudication",
                }
            )
        source = "human" if _review_has_human_decision(review) else "llm"
        return metric.model_copy(
            update={
                "status": MetricStatus.OBSERVED,
                "value": value,
                "numerator": value,
                "denominator": 1,
                "scorer_id": "product-answer-support-judgment",
                "scorer_version": "1.0",
                "scorer_digest": ANSWER_SUPPORT_REVIEWER_DIGEST,
                "evaluator_mode": f"append_only_{source}_support_adjudication",
                "reason": "append-only answer-support adjudication",
            }
        )

    def _historical_rescore_metrics(
        self, run_id: str, item: CaseResult
    ) -> list[MetricResult] | None:
        projection = self._historical_rescore(run_id)
        if projection is None:
            return None
        values = projection["case_metrics"].get((item.case_id, item.repetition))
        return list(values) if isinstance(values, list) else None

    def _historical_rescore_view(self, run_id: str) -> dict[str, object] | None:
        projection = self._historical_rescore(run_id)
        if projection is None:
            return None
        return {
            "status": projection["status"],
            "source_rescore_status": projection["source_rescore_status"],
            "rescore_identity": projection["rescore_identity"],
            "method": projection["method"],
            "source_artifacts_verified": True,
            "note": (
                "This is an accepted, append-only offline projection. The original "
                "Run files remain unchanged, and it is not a new Worker run or a "
                "benchmark-contract/v1 comparable result."
            ),
            "acceptance": projection["acceptance"],
            "diagnostic_matrix": projection["diagnostic_matrix"],
        }

    def _historical_rescore(self, run_id: str) -> dict[str, Any] | None:
        """Load a validated, external historical re-score read model.

        A rescore is never inferred from a filename alone.  It must pin the
        requested Run, validate all retained Case hashes, and carry a complete
        baseline-verification result.  Invalid or unavailable derivatives are
        ignored rather than being presented as corrected metrics.
        """

        if self.historical_rescores_root is None:
            return None
        try:
            directory = self.historical_rescores_root / safe_id(run_id)
        except ValueError:
            return None
        if not directory.is_dir():
            return None
        candidates = sorted(
            (
                path
                for path in directory.glob("historical-rescore-*.json")
                if "acceptance" not in path.stem
            ),
            key=lambda path: path.name,
            reverse=True,
        )
        acceptance_paths = sorted(directory.glob("*projection-acceptance*.json"))
        signatures: list[tuple[str, int, int]] = []
        for candidate in [*candidates, *acceptance_paths]:
            try:
                stat = candidate.stat()
            except OSError:
                continue
            signatures.append((candidate.name, stat.st_mtime_ns, stat.st_size))
        signature = tuple(signatures)
        cached = self._historical_rescore_cache.get(run_id)
        if cached is not None and cached[0] == signature:
            return cached[1]
        for path in candidates:
            projection = self._load_historical_rescore(
                path, run_id, acceptance_paths=acceptance_paths
            )
            if projection is not None:
                self._historical_rescore_cache[run_id] = (signature, projection)
                return projection
        self._historical_rescore_cache[run_id] = (signature, None)
        return None

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _load_historical_rescore(
        self,
        path: Path,
        run_id: str,
        *,
        acceptance_paths: Iterable[Path],
    ) -> dict[str, Any] | None:
        try:
            payload = self._read_object(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if payload.get("run_id") != run_id or payload.get("schema_version") != "historical-rescore/1":
            return None
        baseline = payload.get("baseline_verification")
        if not isinstance(baseline, dict) or baseline.get("ok") is not True:
            return None
        cases = payload.get("cases")
        if not isinstance(cases, list) or not cases:
            return None
        case_metrics: dict[tuple[str, int], list[MetricResult]] = {}
        for case in cases:
            if not isinstance(case, dict):
                return None
            case_id = case.get("case_id")
            repetition = case.get("repetition")
            artifact = case.get("case_artifact")
            metrics = case.get("metrics_after")
            if (
                not isinstance(case_id, str)
                or not isinstance(repetition, int)
                or not isinstance(artifact, dict)
                or not isinstance(metrics, list)
            ):
                return None
            artifact_path = artifact.get("path")
            artifact_hash = artifact.get("sha256")
            if not isinstance(artifact_path, str) or not isinstance(artifact_hash, str):
                return None
            source_case = Path(artifact_path)
            try:
                if not source_case.is_file() or self._sha256_file(source_case) != artifact_hash:
                    return None
                case_metrics[(case_id, repetition)] = [
                    MetricResult.model_validate(metric)
                    for metric in metrics
                    if isinstance(metric, dict)
                ]
            except (OSError, TypeError, ValueError):
                return None
        matrix = payload.get("localization_summary")
        diagnostic_matrix = (
            matrix.get("matrix_19_gold_x_3_stages")
            if isinstance(matrix, dict)
            else None
        )
        if not isinstance(diagnostic_matrix, dict):
            diagnostic_matrix = {}
        status = payload.get("status")
        identity = payload.get("rescore_identity")
        method = payload.get("method")
        if not isinstance(status, str) or not isinstance(identity, str) or not isinstance(method, str):
            return None
        try:
            source_run = self._locate(run_id)[1].root / safe_id(run_id)
        except (FileNotFoundError, OSError, ValueError):
            return None
        acceptance = next(
            (
                value
                for candidate in reversed(list(acceptance_paths))
                if (
                    value := accepted_projection_receipt(
                        candidate,
                        run_dir=source_run,
                        run_id=run_id,
                        rescore_path=path,
                        rescore_identity=identity,
                    )
                )
                is not None
            ),
            None,
        )
        if acceptance is None:
            # A derivative without a current, pinned root-acceptance receipt
            # is diagnostic only.  It must never silently replace product
            # metrics for the original historical Run.
            return None
        return {
            "status": str(acceptance["status"]),
            "source_rescore_status": status,
            "rescore_identity": identity,
            "method": method,
            "case_metrics": case_metrics,
            "acceptance": {
                "reviewer": acceptance.get("reviewer"),
                "reviewed_at": acceptance.get("reviewed_at"),
                "scope": acceptance.get("scope"),
            },
            "diagnostic_matrix": diagnostic_matrix,
        }

    @staticmethod
    def _case_provenance_unavailable(item: CaseResult) -> bool:
        """Whether final-context grounding is unavailable.

        Retrieval stages are intentionally independent.  A missing raw
        locator must not make ranked/context metrics or answer grounding
        unavailable; only the stage consumed by that product field is
        relevant here.
        """

        return RunHistory._stage_provenance_unavailable(item, "context")

    @staticmethod
    def _stage_provenance_unavailable(item: CaseResult, stage: str) -> bool:
        if item.gold_evidence_set is None or item.rag_result is None:
            return False
        items = {
            "raw": item.rag_result.raw_retrieval,
            "ranked": item.rag_result.ranked_retrieval,
            "context": item.rag_result.final_context,
        }.get(stage)
        if items is None:
            return False
        return evidence_observability(
            items, item.gold_evidence_set, CorpusEvidenceIndex({})
        ) is not None

    @staticmethod
    def _metric_stage_provenance_reason(
        item: CaseResult, metric_id: str
    ) -> str | None:
        """Return a provenance reason for only the stage a metric consumes."""

        stage: str | None = None
        if metric_id.startswith("raw_"):
            stage = "raw"
        elif metric_id.startswith("ranked_"):
            stage = "ranked"
        elif metric_id.startswith("context_"):
            stage = "context"
        elif metric_id.startswith("retrieval_stage_delta"):
            if RunHistory._stage_provenance_unavailable(item, "raw") or RunHistory._stage_provenance_unavailable(item, "ranked"):
                return PROVENANCE_UNAVAILABLE_REASON
            return None
        elif metric_id.startswith("context_selection_loss"):
            if RunHistory._stage_provenance_unavailable(item, "ranked") or RunHistory._stage_provenance_unavailable(item, "context"):
                return PROVENANCE_UNAVAILABLE_REASON
            return None
        elif metric_id in {"answer_groundedness", "unsupported_answer_rate"}:
            stage = "context"
        if stage is not None and RunHistory._stage_provenance_unavailable(item, stage):
            return PROVENANCE_UNAVAILABLE_REASON
        return None

    def _product_judgments(
        self,
        run_id: str,
        item: CaseResult,
        *,
        metrics: list[MetricResult],
        failure_assessment: object | None,
        review: object | None,
    ) -> dict[str, str]:
        """Calculate product verdicts with the correct provenance authority."""

        # A validated historical derivative carries a repaired provenance map.
        # Passing the original blank map to the generic legacy detector would
        # incorrectly turn its independently re-localized metrics back into
        # ``unverifiable``.  The immutable Gold answer still participates in
        # answer judgment; only the obsolete locator-absence shortcut is
        # suppressed for this derived read model.
        derived = self._historical_rescore_metrics(run_id, item) is not None
        return case_judgments(
            status=str(item.status),
            metrics=metrics,
            failure_assessment=failure_assessment,
            gold_answer=item.gold_answer,
            gold_evidence_set=None if derived else item.gold_evidence_set,
            rag_result=item.rag_result,
            review=review,
        )

    def _presentation_failure_assessment(
        self, run_id: str, item: CaseResult
    ) -> dict[str, Any] | None:
        """Hide obsolete legacy diagnoses from the product presentation only.

        Old immutable case files classified a lost locator mapping as a
        retrieval miss and often as an unsupported answer.  That is a false
        claim: the text was returned, but it cannot be safely located in the
        canonical document.  Preserve the raw artifact on disk while exposing
        the accurate, actionable diagnosis to the product UI.
        """

        historical_metrics = self._historical_rescore_metrics(run_id, item)
        if historical_metrics is not None:
            by_id = {metric.metric_id: metric for metric in historical_metrics}
            miss = by_id.get("context_localization_retrieval_missed")
            labels = (
                ["retrieval_missing"]
                if (
                    miss is not None
                    and miss.status == MetricStatus.OBSERVED
                    and isinstance(miss.numerator, (int, float))
                    and miss.numerator > 0
                )
                else []
            )
            derived = self._historical_rescore(run_id)
            status = derived.get("status") if isinstance(derived, dict) else "UNVERIFIED"
            return {
                "labels": labels,
                "certainty": "unknown",
                "review_required": status != "VERIFIED",
                "reasons": [
                    "该诊断来自独立保存的原文定位复算；原始运行文件未被改写，仍需新 Worker 运行验证。"
                ],
            }
        if not self._case_provenance_unavailable(item):
            return (
                item.failure_assessment.model_dump(mode="json")
                if item.failure_assessment is not None
                else None
            )
        raw_labels = (
            [str(label) for label in item.failure_assessment.labels]
            if item.failure_assessment is not None
            else []
        )
        stale = {
            "retrieval_missing",
            "ranking_failure",
            "context_selection_loss",
            "unsupported_answer",
        }
        labels = [label for label in raw_labels if label not in stale]
        if "provenance_unavailable" not in labels:
            labels.append("provenance_unavailable")
        return {
            "labels": labels,
            "certainty": "unknown",
            "review_required": True,
            "reasons": [
                "The runtime returned source content, but its canonical document coordinates could not be verified. This is not a retrieval-missing or answer-correctness verdict."
            ],
        }

    def verify_artifacts(self, run_id: str) -> ArtifactVerification:
        _is_primary, store = self._locate(run_id)
        return store.verify_artifacts(run_id)

    def report(self, run_id: str) -> str:
        is_primary, store = self._locate(run_id)
        root = store.root / safe_id(run_id)
        if is_primary:
            return (root / "report.md").read_text(encoding="utf-8")
        manifest = store.get(run_id)
        evaluation = self._read_object(root / _PRIVATE_EVALUATION_DIR / "summary.json")
        verification = store.verify_artifacts(run_id)
        return "\n".join(
            (
                "# Archived Bundle 3.0 rehearsal",
                "",
                "This is a read-only presentation of the original completed run; its immutable artifacts were not imported or modified.",
                "",
                f"- Run: `{manifest.run_id}`",
                f"- Status: `{manifest.status.value}`; completed Cases: `{manifest.execution_counts.get('completed', 0)}`",
                f"- Dataset Release: `{manifest.dataset_release_id}`",
                f"- Artifact verification: `{verification.valid}`",
                f"- Private evaluator: `{evaluation.get('evaluator', {}).get('id', 'unavailable')}`",
                "- Per-case Gold values and evidence are intentionally not exposed through this runtime-history view.",
                "",
            )
        )

    def _locate(self, run_id: str) -> tuple[bool, RunStore]:
        safe = safe_id(run_id)
        if (self.primary.root / safe / "run.json").is_file():
            return True, self.primary
        for store in self._archives():
            if (store.root / safe / "run.json").is_file() and self._is_presentable_rehearsal(store, safe):
                return False, store
        raise FileNotFoundError(run_id)

    def _archives(self) -> list[RunStore]:
        values: list[RunStore] = []
        seen = {self.primary.root.resolve()}
        for raw in os.environ.get(_RUN_ARCHIVES_ENV, "").split(os.pathsep):
            if not raw.strip():
                continue
            root = Path(raw).expanduser().resolve() / "runs"
            if root in seen or not root.is_dir():
                continue
            seen.add(root)
            values.append(RunStore(root))
        return values

    @staticmethod
    def _is_presentable_rehearsal(store: RunStore, run_id: str) -> bool:
        root = store.root / safe_id(run_id)
        return (
            (root / _PRIVATE_EVALUATION_DIR / "case-execution.jsonl").is_file()
            and (root / _PRIVATE_EVALUATION_DIR / "case-evaluation.jsonl").is_file()
            and (root / _PRIVATE_EVALUATION_DIR / "summary.json").is_file()
        )

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{path.name} is malformed")
        return value

    def _rehearsal_cases(self, root: Path) -> list[CaseResult]:
        execution_by_case = {
            str(item["case_id"]): item
            for item in self._read_jsonl(root / _PRIVATE_EVALUATION_DIR / "case-execution.jsonl")
        }
        evaluation_by_case = {
            str(item["case_id"]): item
            for item in self._read_jsonl(root / _PRIVATE_EVALUATION_DIR / "case-evaluation.jsonl")
        }
        values: list[CaseResult] = []
        for case_id, execution in sorted(execution_by_case.items(), key=lambda item: (int(item[1].get("ordinal", 0)), item[0])):
            evaluation = evaluation_by_case.get(case_id, {})
            raw_status = execution.get("status")
            status = raw_status if raw_status in {"completed", "timeout", "system_error", "cancelled"} else "system_error"
            private_metrics = dict(evaluation.get("answer_evaluation") or {})
            values.append(
                CaseResult.model_validate(
                    {
                        "case_id": case_id,
                        "status": status,
                        "question": execution.get("question") or "[question unavailable]",
                        # This is a runtime-history projection.  Gold never
                        # leaves the private Bundle/evaluator files.
                        "gold_answer": None,
                        "gold_evidence_set": None,
                        "rag_result": execution.get("rag_result"),
                        "metrics": self._case_metrics(private_metrics),
                        "error": self._case_error(execution.get("error")),
                        "failure_assessment": evaluation.get("failure_assessment"),
                        "started_at": execution.get("started_at"),
                        "completed_at": execution.get("completed_at"),
                        "repetition": 1,
                        "seed": 20260830,
                    }
                )
            )
        return values

    @staticmethod
    def _case_metrics(values: dict[str, Any]) -> list[dict[str, Any]]:
        scorer = dict(values.get("answer_scorer") or {})
        result: list[dict[str, Any]] = []
        for metric_id in ("answer_accuracy", "answer_groundedness", "unsupported_answer_rate"):
            metric = values.get(metric_id)
            if not isinstance(metric, dict) or not isinstance(metric.get("status"), str):
                continue
            result.append(
                MetricResult.model_validate(
                    {
                        "metric_id": metric_id,
                        "status": metric["status"],
                        "value": metric.get("value"),
                        "scorer_id": scorer.get("id", "bundle-v3-private-evaluator"),
                        "scorer_version": scorer.get("version", "1.0"),
                        "scorer_digest": scorer.get("digest", "unavailable"),
                        "evaluator_mode": "private_post_run_projection",
                        "reason": metric.get("reason"),
                    }
                ).model_dump(mode="json")
            )
        return result

    @staticmethod
    def _case_error(value: object) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        message = value.get("message")
        if not isinstance(message, str):
            return None
        code = value.get("type")
        return {"code": code if isinstance(code, str) else "archive_error", "message": message, "retryable": False}

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number} is malformed")
            values.append(value)
        return values

    @staticmethod
    def _rehearsal_summary(root: Path, manifest: RunManifest) -> dict[str, Any]:
        private_summary = RunHistory._read_object(root / _PRIVATE_EVALUATION_DIR / "summary.json")
        denominator = int(private_summary.get("completed_case_count", 0))
        metrics = {
            metric_id: {
                "status": "observed",
                "value": value,
                "denominator": denominator,
                "coverage": 1.0 if denominator else 0.0,
            }
            for metric_id, value in sorted(dict(private_summary.get("mean_metrics") or {}).items())
            if isinstance(value, (int, float))
        }
        return {"metrics": metrics, "execution": dict(manifest.execution_counts)}
