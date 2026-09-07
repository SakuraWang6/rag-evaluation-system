"""Append-only product-layer adjudications for completed evaluation cases.

Run artifacts are research records and therefore immutable.  A reviewer (or a
configured semantic-review assistant) writes a separate, revisioned decision
stream here; the read model can then present a final product verdict without
rewriting the original CaseResult.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.contracts.dataset import GoldAnswerKind
from rag_eval.contracts.run import CaseResult, MetricStatus
from rag_eval.evaluation.answers import AnswerVerdict, score_answer
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id

if TYPE_CHECKING:
    from rag_eval.llm import LLMConfigurationService


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseReviewVerdict(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    NEEDS_REVIEW = "needs_review"


class CaseReviewSource(StrEnum):
    HUMAN = "human"
    LLM = "llm"


class SemanticReviewRunState(StrEnum):
    """Lifecycle of a non-blocking post-run semantic review pass."""

    NOT_STARTED = "not_started"
    NOT_CONFIGURED = "not_configured"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    SKIPPED = "skipped"


class CaseReviewDecision(ReviewModel):
    revision: int = Field(ge=1)
    verdict: CaseReviewVerdict
    source: CaseReviewSource
    reviewer: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=4000)
    created_at: datetime
    # Model/prompt identities are only set for an LLM assist.  They make the
    # non-human proposal traceable without storing provider credentials.
    model: str | None = Field(default=None, max_length=240)
    prompt_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class CaseReviewRecord(ReviewModel):
    schema_version: int = 1
    run_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    decisions: list[CaseReviewDecision] = Field(default_factory=list)

    @property
    def latest(self) -> CaseReviewDecision | None:
        return self.decisions[-1] if self.decisions else None

    @property
    def latest_human(self) -> CaseReviewDecision | None:
        """Return the final human adjudication, if one has been recorded.

        A human decision is intentionally terminal for the product verdict.
        The append-only history is retained in full, but a later automated
        retry must never silently replace a reviewer decision.
        """

        return next(
            (
                decision
                for decision in reversed(self.decisions)
                if decision.source == CaseReviewSource.HUMAN
            ),
            None,
        )

    def api_view(self) -> dict[str, object]:
        latest = self.latest
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "repetition": self.repetition,
            "latest": latest.model_dump(mode="json") if latest is not None else None,
            "history": [item.model_dump(mode="json") for item in self.decisions],
        }


class AnswerSupportVerdict(StrEnum):
    """Whether the generated answer is supported by its final RAG context.

    This is deliberately not an answer-correctness verdict.  A response can
    be supported by an incomplete context and still be incorrect relative to
    Gold, or it can be correct while relying on unavailable context.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    NEEDS_REVIEW = "needs_review"


class AnswerSupportReviewDecision(ReviewModel):
    revision: int = Field(ge=1)
    verdict: AnswerSupportVerdict
    source: CaseReviewSource
    reviewer: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=4000)
    created_at: datetime
    model: str | None = Field(default=None, max_length=240)
    prompt_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AnswerSupportReviewRecord(ReviewModel):
    """A separate append-only review history for support/hallucination."""

    schema_version: int = 1
    run_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    decisions: list[AnswerSupportReviewDecision] = Field(default_factory=list)

    @property
    def latest(self) -> AnswerSupportReviewDecision | None:
        return self.decisions[-1] if self.decisions else None

    @property
    def latest_human(self) -> AnswerSupportReviewDecision | None:
        return next(
            (
                decision
                for decision in reversed(self.decisions)
                if decision.source == CaseReviewSource.HUMAN
            ),
            None,
        )

    def api_view(self) -> dict[str, object]:
        latest = self.latest
        return {
            "axis": "answer_support",
            "run_id": self.run_id,
            "case_id": self.case_id,
            "repetition": self.repetition,
            "latest": latest.model_dump(mode="json") if latest is not None else None,
            "history": [item.model_dump(mode="json") for item in self.decisions],
        }


class SemanticReviewRunStatus(ReviewModel):
    """Small, durable progress view separate from immutable Run artifacts."""

    schema_version: int = 1
    run_id: str = Field(min_length=1)
    state: SemanticReviewRunState = SemanticReviewRunState.NOT_STARTED
    candidate_count: int = Field(default=0, ge=0)
    processed_count: int = Field(default=0, ge=0)
    adjudicated_count: int = Field(default=0, ge=0)
    needs_human_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    detail: str | None = Field(default=None, max_length=1200)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def api_view(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class CaseReviewStore:
    """Small append-only review ledger separate from immutable run files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, run_id: str, case_id: str, repetition: int) -> CaseReviewRecord:
        path = self._path(run_id, case_id, repetition)
        if not path.is_file():
            return CaseReviewRecord(run_id=run_id, case_id=case_id, repetition=repetition)
        return CaseReviewRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def append(
        self,
        *,
        run_id: str,
        case_id: str,
        repetition: int,
        verdict: CaseReviewVerdict,
        source: CaseReviewSource,
        reviewer: str,
        note: str = "",
        model: str | None = None,
        prompt_digest: str | None = None,
    ) -> CaseReviewRecord:
        record = self.get(run_id, case_id, repetition)
        if source == CaseReviewSource.LLM and record.latest_human is not None:
            raise ValueError(
                "a human adjudication already exists; automated review cannot replace it"
            )
        decision = CaseReviewDecision(
            revision=len(record.decisions) + 1,
            verdict=verdict,
            source=source,
            reviewer=reviewer.strip() or "local-reviewer",
            note=note.strip(),
            created_at=datetime.now(UTC),
            model=model,
            prompt_digest=prompt_digest,
        )
        updated = record.model_copy(update={"decisions": [*record.decisions, decision]})
        atomic_write_json(self._path(run_id, case_id, repetition), updated.model_dump(mode="json"))
        return updated

    def review_run_status(self, run_id: str) -> SemanticReviewRunStatus:
        path = self._review_run_path(run_id)
        if not path.is_file():
            return SemanticReviewRunStatus(run_id=run_id)
        return SemanticReviewRunStatus.model_validate_json(path.read_text(encoding="utf-8"))

    def save_review_run_status(
        self, status: SemanticReviewRunStatus
    ) -> SemanticReviewRunStatus:
        atomic_write_json(
            self._review_run_path(status.run_id), status.model_dump(mode="json")
        )
        return status

    def review_run_statuses(self) -> list[SemanticReviewRunStatus]:
        root = self.root / "_runs"
        if not root.is_dir():
            return []
        values: list[SemanticReviewRunStatus] = []
        for path in sorted(root.glob("*.json")):
            try:
                values.append(
                    SemanticReviewRunStatus.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                )
            except (OSError, ValueError):
                # A malformed product-side progress file cannot invalidate a
                # completed immutable evaluation Run.
                continue
        return values

    def _path(self, run_id: str, case_id: str, repetition: int) -> Path:
        return (
            self.root
            / safe_id(run_id)
            / f"rep-{repetition:04d}-{safe_id(case_id)}.json"
        )

    def _review_run_path(self, run_id: str) -> Path:
        return self.root / "_runs" / f"{safe_id(run_id)}.json"


class AnswerSupportReviewStore:
    """Append-only support-review ledger kept apart from answer correctness."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, run_id: str, case_id: str, repetition: int) -> AnswerSupportReviewRecord:
        path = self._path(run_id, case_id, repetition)
        if not path.is_file():
            return AnswerSupportReviewRecord(
                run_id=run_id,
                case_id=case_id,
                repetition=repetition,
            )
        return AnswerSupportReviewRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def append(
        self,
        *,
        run_id: str,
        case_id: str,
        repetition: int,
        verdict: AnswerSupportVerdict,
        source: CaseReviewSource,
        reviewer: str,
        note: str = "",
        model: str | None = None,
        prompt_digest: str | None = None,
    ) -> AnswerSupportReviewRecord:
        record = self.get(run_id, case_id, repetition)
        if source == CaseReviewSource.LLM and record.latest_human is not None:
            raise ValueError(
                "a human support adjudication already exists; automated review cannot replace it"
            )
        decision = AnswerSupportReviewDecision(
            revision=len(record.decisions) + 1,
            verdict=verdict,
            source=source,
            reviewer=reviewer.strip() or "local-reviewer",
            note=note.strip(),
            created_at=datetime.now(UTC),
            model=model,
            prompt_digest=prompt_digest,
        )
        updated = record.model_copy(update={"decisions": [*record.decisions, decision]})
        atomic_write_json(self._path(run_id, case_id, repetition), updated.model_dump(mode="json"))
        return updated

    def review_run_status(self, run_id: str) -> SemanticReviewRunStatus:
        path = self._review_run_path(run_id)
        if not path.is_file():
            return SemanticReviewRunStatus(run_id=run_id)
        return SemanticReviewRunStatus.model_validate_json(path.read_text(encoding="utf-8"))

    def save_review_run_status(
        self, status: SemanticReviewRunStatus
    ) -> SemanticReviewRunStatus:
        atomic_write_json(
            self._review_run_path(status.run_id), status.model_dump(mode="json")
        )
        return status

    def review_run_statuses(self) -> list[SemanticReviewRunStatus]:
        root = self.root / "_runs"
        if not root.is_dir():
            return []
        values: list[SemanticReviewRunStatus] = []
        for path in sorted(root.glob("*.json")):
            try:
                values.append(
                    SemanticReviewRunStatus.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                )
            except (OSError, ValueError):
                continue
        return values

    def _path(self, run_id: str, case_id: str, repetition: int) -> Path:
        return (
            self.root
            / safe_id(run_id)
            / f"rep-{repetition:04d}-{safe_id(case_id)}.json"
        )

    def _review_run_path(self, run_id: str) -> Path:
        return self.root / "_runs" / f"{safe_id(run_id)}.json"


class SemanticReviewError(RuntimeError):
    pass


def answer_support_reviewer_digest() -> str:
    """Fingerprint the support-review implementation used by product views."""

    try:
        source = Path(__file__).read_bytes()
    except OSError:  # pragma: no cover - package source is present in production
        source = b"<source-unavailable>"
    return "sha256:" + hashlib.sha256(source).hexdigest()


ANSWER_SUPPORT_REVIEWER_DIGEST = answer_support_reviewer_digest()


class SemanticAnswerReviewer:
    """Configured LLM second-pass for non-deterministic text answers.

    It never replaces numeric, set, abstention, or deterministic-pass rules.
    The response is a proposal recorded in the same append-only ledger; an
    ``uncertain`` proposal keeps the Case in human-review state.
    """

    def __init__(self, store: CaseReviewStore, llm: "LLMConfigurationService | None") -> None:
        self.store = store
        self.llm = llm

    def automatically_available(self) -> tuple[bool, str]:
        """Whether this host can safely start local automatic review.

        Remote providers remain an explicit per-user action because their use
        requires consent.  A local Ollama binding has no arbitrary request
        timeout; the background coordinator reports progress independently of
        the completed evaluation job.
        """

        if self.llm is None:
            return False, "LLM review configuration is unavailable"
        try:
            from rag_eval.llm import LLMProviderKind, LLMStage

            provider, binding = self.llm.provider_for_stage(LLMStage.REVIEW_ASSIST)
        except (OSError, ValueError) as exc:
            return False, str(exc) or "LLM review configuration is invalid"
        if not provider.enabled or not binding.enabled:
            return False, "the semantic-review model binding is disabled"
        if provider.kind != LLMProviderKind.OLLAMA:
            return False, "automatic semantic review uses only a local Ollama binding"
        if not (binding.model or provider.model).strip():
            return False, "the semantic-review model is not selected"
        return True, "local semantic review is available"

    def eligible(self, run_id: str, case: CaseResult) -> bool:
        """Return whether one Case still needs a first semantic proposal."""

        if case.status != "completed" or case.gold_answer is None:
            return False
        if case.gold_answer.kind not in {GoldAnswerKind.TEXT, GoldAnswerKind.FORMULA}:
            return False
        if score_answer(
            case.rag_result.answer if case.rag_result else None, case.gold_answer
        ).verdict != AnswerVerdict.NEEDS_REVIEW:
            return False
        record = self.store.get(run_id, case.case_id, case.repetition)
        return record.latest_human is None and not any(
            decision.source == CaseReviewSource.LLM
            for decision in record.decisions
        )

    def review(
        self, run_id: str, case: CaseResult, *, remote_consent: bool = False
    ) -> CaseReviewRecord:
        if case.status != "completed" or case.gold_answer is None:
            raise SemanticReviewError("only completed Cases with a Gold answer can be semantically reviewed")
        if case.gold_answer.kind not in {GoldAnswerKind.TEXT, GoldAnswerKind.FORMULA}:
            raise SemanticReviewError("semantic review is limited to text and formula answers")
        existing = self.store.get(run_id, case.case_id, case.repetition)
        if existing.latest_human is not None:
            raise SemanticReviewError(
                "a human adjudication already exists; it remains the final verdict"
            )
        # The semantic second pass is idempotent.  A recorded LLM proposal is
        # auditable and should be reviewed by a human rather than silently
        # replaced by a second nondeterministic call.
        if any(decision.source == CaseReviewSource.LLM for decision in existing.decisions):
            return existing

        score = score_answer(case.rag_result.answer if case.rag_result else None, case.gold_answer)
        if score.verdict != AnswerVerdict.NEEDS_REVIEW:
            raise SemanticReviewError(
                "the deterministic rule already produced a final answer verdict"
            )
        if self.llm is None:
            raise SemanticReviewError("LLM review configuration is unavailable")

        from rag_eval.authoring.providers import (
            ConfiguredRemoteProvider,
            LocalOllamaProvider,
            ProposalProviderError,
        )
        from rag_eval.llm import LLMProviderKind, LLMStage, _ollama_generate_endpoint

        provider_config, binding = self.llm.provider_for_stage(LLMStage.REVIEW_ASSIST)
        if not provider_config.enabled or not binding.enabled:
            raise SemanticReviewError("the semantic-review model binding is disabled")
        model = (binding.model or provider_config.model).strip()
        if not model:
            raise SemanticReviewError("the semantic-review model is not selected")
        if provider_config.kind == LLMProviderKind.OLLAMA:
            provider = LocalOllamaProvider(
                endpoint=_ollama_generate_endpoint(provider_config.endpoint),
                model=model,
                provider_id=provider_config.provider_id,
                # Review is explicitly user initiated and its UI has an active
                # progress state. Do not impose an arbitrary local-model cap.
                timeout_seconds=None,
            )
        elif provider_config.kind == LLMProviderKind.OPENAI_COMPATIBLE:
            if not remote_consent:
                raise SemanticReviewError("remote semantic review requires explicit consent")
            authorization = None
            if provider_config.api_key_ref is not None:
                # The secret itself remains server-side and is never returned.
                raise SemanticReviewError("remote semantic review is not enabled in this local product build")
            provider = ConfiguredRemoteProvider(
                endpoint=provider_config.endpoint,
                model=model,
                authorization=authorization,
                provider_id=provider_config.provider_id,
            )
        else:  # pragma: no cover - exhaustiveness guard for future providers
            raise SemanticReviewError("unsupported semantic-review provider")

        prompt = (
            "You are a strict answer-equivalence adjudicator. Return only one JSON object "
            "with keys verdict and reason. verdict must be exactly equivalent, "
            "not_equivalent, or uncertain. Decide whether the generated answer answers "
            "the question with the same meaning as the Gold answer. Do not infer missing "
            "facts and do not accept contradictory values. If wording, scope, negation, "
            "or formula equivalence is uncertain, return uncertain."
        )
        source = [
            {
                "question": case.question,
                "gold_answer": case.gold_answer.canonical,
                "accepted_answers": case.gold_answer.accepted_values,
                "answer_kind": case.gold_answer.kind.value,
                "generated_answer": case.rag_result.answer if case.rag_result else None,
                "deterministic_reason": score.reason,
            }
        ]
        try:
            value = provider.propose(
                task="semantic_answer_adjudication",
                source=source,
                prompt=prompt,
                seed=0,
            )
        except ProposalProviderError as exc:
            raise SemanticReviewError(
                "the semantic-review model did not complete; check its model configuration"
            ) from exc
        proposed = value.get("verdict")
        reason = value.get("reason")
        if proposed not in {"equivalent", "not_equivalent", "uncertain"}:
            raise SemanticReviewError("semantic-review model returned an invalid verdict")
        if not isinstance(reason, str) or not reason.strip():
            raise SemanticReviewError("semantic-review model returned no reason")
        verdict = {
            "equivalent": CaseReviewVerdict.CORRECT,
            "not_equivalent": CaseReviewVerdict.INCORRECT,
            "uncertain": CaseReviewVerdict.NEEDS_REVIEW,
        }[proposed]
        digest_source = json.dumps(
            {"prompt": prompt, "source": source},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return self.store.append(
            run_id=run_id,
            case_id=case.case_id,
            repetition=case.repetition,
            verdict=verdict,
            source=CaseReviewSource.LLM,
            reviewer=f"{provider_config.provider_id}:{model}",
            note=reason.strip(),
            model=model,
            prompt_digest=hashlib.sha256(digest_source.encode("utf-8")).hexdigest(),
        )


class SemanticAnswerSupportReviewer:
    """LLM proposal for whether an answer is supported by final RAG context.

    This reviewer intentionally receives no Gold answer.  It judges only the
    relationship between the generated answer and the evidence actually given
    to the generator, which keeps correctness and hallucination independent.
    Human support decisions remain terminal in their own append-only ledger.
    """

    def __init__(
        self,
        store: AnswerSupportReviewStore,
        llm: "LLMConfigurationService | None",
    ) -> None:
        self.store = store
        self.llm = llm

    def automatically_available(self) -> tuple[bool, str]:
        if self.llm is None:
            return False, "LLM review configuration is unavailable"
        try:
            from rag_eval.llm import LLMProviderKind, LLMStage

            provider, binding = self.llm.provider_for_stage(LLMStage.REVIEW_ASSIST)
        except (OSError, ValueError) as exc:
            return False, str(exc) or "LLM review configuration is invalid"
        if not provider.enabled or not binding.enabled:
            return False, "the semantic-review model binding is disabled"
        if provider.kind != LLMProviderKind.OLLAMA:
            return False, "automatic semantic review uses only a local Ollama binding"
        if not (binding.model or provider.model).strip():
            return False, "the semantic-review model is not selected"
        return True, "local semantic review is available"

    @staticmethod
    def _requires_review(case: CaseResult) -> bool:
        return any(
            metric.metric_id == "answer_hallucination"
            and metric.status == MetricStatus.NEEDS_REVIEW
            for metric in case.metrics
        )

    def eligible(self, run_id: str, case: CaseResult) -> bool:
        if case.status != "completed" or case.rag_result is None:
            return False
        if not (case.rag_result.answer or "").strip() or not self._requires_review(case):
            return False
        record = self.store.get(run_id, case.case_id, case.repetition)
        return record.latest_human is None and not any(
            decision.source == CaseReviewSource.LLM
            for decision in record.decisions
        )

    def review(
        self, run_id: str, case: CaseResult, *, remote_consent: bool = False
    ) -> AnswerSupportReviewRecord:
        if case.status != "completed" or case.rag_result is None:
            raise SemanticReviewError("only completed Cases with a generated answer can be support-reviewed")
        if not (case.rag_result.answer or "").strip():
            raise SemanticReviewError("an empty answer has no affirmative claim to support-review")
        if not self._requires_review(case):
            raise SemanticReviewError("the deterministic support rule already produced a final verdict")
        existing = self.store.get(run_id, case.case_id, case.repetition)
        if existing.latest_human is not None:
            raise SemanticReviewError(
                "a human support adjudication already exists; it remains the final verdict"
            )
        if any(decision.source == CaseReviewSource.LLM for decision in existing.decisions):
            return existing
        if self.llm is None:
            raise SemanticReviewError("LLM review configuration is unavailable")

        from rag_eval.authoring.providers import (
            ConfiguredRemoteProvider,
            LocalOllamaProvider,
            ProposalProviderError,
        )
        from rag_eval.llm import LLMProviderKind, LLMStage, _ollama_generate_endpoint

        provider_config, binding = self.llm.provider_for_stage(LLMStage.REVIEW_ASSIST)
        if not provider_config.enabled or not binding.enabled:
            raise SemanticReviewError("the semantic-review model binding is disabled")
        model = (binding.model or provider_config.model).strip()
        if not model:
            raise SemanticReviewError("the semantic-review model is not selected")
        if provider_config.kind == LLMProviderKind.OLLAMA:
            provider = LocalOllamaProvider(
                endpoint=_ollama_generate_endpoint(provider_config.endpoint),
                model=model,
                provider_id=provider_config.provider_id,
                timeout_seconds=None,
            )
        elif provider_config.kind == LLMProviderKind.OPENAI_COMPATIBLE:
            if not remote_consent:
                raise SemanticReviewError("remote semantic review requires explicit consent")
            if provider_config.api_key_ref is not None:
                raise SemanticReviewError("remote semantic review is not enabled in this local product build")
            provider = ConfiguredRemoteProvider(
                endpoint=provider_config.endpoint,
                model=model,
                authorization=None,
                provider_id=provider_config.provider_id,
            )
        else:  # pragma: no cover - exhaustiveness guard for future providers
            raise SemanticReviewError("unsupported semantic-review provider")

        prompt = (
            "You are a strict evidence-support adjudicator. Return only one JSON object "
            "with keys verdict and reason. verdict must be exactly supported, unsupported, "
            "or uncertain. Judge whether every material factual claim in the generated answer "
            "is directly supported by the final retrieval context supplied to the generator. "
            "Do not use external knowledge or any Gold answer. A response may be incorrect "
            "relative to Gold yet supported by incomplete context; missing Gold evidence alone "
            "is not proof of hallucination. A refusal or statement of insufficient information "
            "is supported only when it faithfully describes the supplied context. Use uncertain "
            "when the context cannot establish the claim relationship."
        )
        source = [
            {
                "question": case.question,
                "generated_answer": case.rag_result.answer,
                "final_context": [
                    {
                        "rank": item.rank,
                        "segment_id": item.document_id,
                        "content": item.content,
                    }
                    for item in sorted(
                        case.rag_result.final_context or [], key=lambda item: item.rank
                    )
                ],
            }
        ]
        try:
            value = provider.propose(
                task="semantic_answer_support_adjudication",
                source=source,
                prompt=prompt,
                seed=0,
            )
        except ProposalProviderError as exc:
            raise SemanticReviewError(
                "the semantic-review model did not complete; check its model configuration"
            ) from exc
        proposed = value.get("verdict")
        reason = value.get("reason")
        if proposed not in {"supported", "unsupported", "uncertain"}:
            raise SemanticReviewError("semantic-review model returned an invalid support verdict")
        if not isinstance(reason, str) or not reason.strip():
            raise SemanticReviewError("semantic-review model returned no reason")
        verdict = {
            "supported": AnswerSupportVerdict.SUPPORTED,
            "unsupported": AnswerSupportVerdict.UNSUPPORTED,
            "uncertain": AnswerSupportVerdict.NEEDS_REVIEW,
        }[proposed]
        digest_source = json.dumps(
            {"prompt": prompt, "source": source},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return self.store.append(
            run_id=run_id,
            case_id=case.case_id,
            repetition=case.repetition,
            verdict=verdict,
            source=CaseReviewSource.LLM,
            reviewer=f"{provider_config.provider_id}:{model}",
            note=reason.strip(),
            model=model,
            prompt_digest=hashlib.sha256(digest_source.encode("utf-8")).hexdigest(),
        )


class SemanticReviewCoordinator:
    """Run rule → local LLM → human review without delaying evaluation jobs.

    The coordinator writes progress to the review ledger, starts only after a
    Run has completed, and intentionally leaves unanswered/uncertain cases in
    ``needs_review``.  It never changes a Run artifact or retries a human
    decision.
    """

    def __init__(
        self,
        reviewer: SemanticAnswerReviewer,
        cases_for_run: Callable[[str], list[CaseResult]],
    ) -> None:
        self.reviewer = reviewer
        self.cases_for_run = cases_for_run
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def schedule(self, run_id: str) -> SemanticReviewRunStatus:
        store = self.reviewer.store
        current = store.review_run_status(run_id)
        if current.state in {
            SemanticReviewRunState.COMPLETED,
            SemanticReviewRunState.COMPLETED_WITH_ERRORS,
            SemanticReviewRunState.SKIPPED,
        }:
            return current
        if current.state in {
            SemanticReviewRunState.QUEUED,
            SemanticReviewRunState.RUNNING,
        }:
            with self._lock:
                prior = self._threads.get(run_id)
                if prior is not None and prior.is_alive():
                    return current
        available, detail = self.reviewer.automatically_available()
        if not available:
            return store.save_review_run_status(
                current.model_copy(
                    update={
                        "state": SemanticReviewRunState.NOT_CONFIGURED,
                        "detail": detail,
                    }
                )
            )
        try:
            candidates = [
                case for case in self.cases_for_run(run_id)
                if self.reviewer.eligible(run_id, case)
            ]
        except (OSError, ValueError) as exc:
            return store.save_review_run_status(
                current.model_copy(
                    update={
                        "state": SemanticReviewRunState.COMPLETED_WITH_ERRORS,
                        "detail": str(exc) or "could not load completed cases",
                        "error_count": 1,
                        "completed_at": datetime.now(UTC),
                    }
                )
            )
        if not candidates:
            return store.save_review_run_status(
                current.model_copy(
                    update={
                        "state": SemanticReviewRunState.SKIPPED,
                        "detail": "no text/formula answers require semantic adjudication",
                        "completed_at": datetime.now(UTC),
                    }
                )
            )
        queued = store.save_review_run_status(
            current.model_copy(
                update={
                    "state": SemanticReviewRunState.QUEUED,
                    "candidate_count": len(candidates),
                    "processed_count": 0,
                    "adjudicated_count": 0,
                    "needs_human_count": 0,
                    "error_count": 0,
                    "detail": "waiting for the local semantic-review model",
                    "started_at": None,
                    "completed_at": None,
                }
            )
        )
        with self._lock:
            prior = self._threads.get(run_id)
            if prior is not None and prior.is_alive():
                return queued
            thread = threading.Thread(
                target=self.review_cases,
                args=(run_id, candidates),
                name=f"rag-eval-semantic-review-{run_id[:12]}",
                daemon=True,
            )
            self._threads[run_id] = thread
            thread.start()
        return queued

    def resume_pending(self) -> list[SemanticReviewRunStatus]:
        """Resume only interrupted queued/running local review batches."""

        resumed: list[SemanticReviewRunStatus] = []
        for status in self.reviewer.store.review_run_statuses():
            if status.state not in {
                SemanticReviewRunState.QUEUED,
                SemanticReviewRunState.RUNNING,
            }:
                continue
            resumed.append(self.schedule(status.run_id))
        return resumed

    def review_cases(
        self, run_id: str, cases: list[CaseResult]
    ) -> SemanticReviewRunStatus:
        """Perform one already-selected review batch; public for deterministic tests."""

        store = self.reviewer.store
        status = store.review_run_status(run_id).model_copy(
            update={
                "state": SemanticReviewRunState.RUNNING,
                "candidate_count": len(cases),
                "detail": "the local semantic-review model is adjudicating answers",
                "started_at": datetime.now(UTC),
                "completed_at": None,
            }
        )
        store.save_review_run_status(status)
        for case in cases:
            # A human may have reviewed this Case while the previous local
            # model request was running. Respect that decision and move on.
            if not self.reviewer.eligible(run_id, case):
                status = status.model_copy(
                    update={"processed_count": status.processed_count + 1}
                )
                store.save_review_run_status(status)
                continue
            try:
                record = self.reviewer.review(run_id, case)
                decision = record.latest
                status = status.model_copy(
                    update={
                        "processed_count": status.processed_count + 1,
                        "adjudicated_count": status.adjudicated_count + 1,
                        "needs_human_count": status.needs_human_count
                        + int(
                            decision is None
                            or str(decision.verdict)
                            == CaseReviewVerdict.NEEDS_REVIEW.value
                        ),
                    }
                )
            except SemanticReviewError as exc:
                # A semantic-review error must not fail or relabel the Run.
                # Retain the deterministic needs-review state for a human.
                status = status.model_copy(
                    update={
                        "processed_count": status.processed_count + 1,
                        "needs_human_count": status.needs_human_count + 1,
                        "error_count": status.error_count + 1,
                        "detail": str(exc),
                    }
                )
            store.save_review_run_status(status)
        final_state = (
            SemanticReviewRunState.COMPLETED_WITH_ERRORS
            if status.error_count
            else SemanticReviewRunState.COMPLETED
        )
        return store.save_review_run_status(
            status.model_copy(
                update={
                    "state": final_state,
                    "detail": (
                        "semantic review completed with cases left for human confirmation"
                        if status.needs_human_count
                        else "semantic review completed"
                    ),
                    "completed_at": datetime.now(UTC),
                }
            )
        )
