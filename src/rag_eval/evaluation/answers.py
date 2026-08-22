"""Typed deterministic answer scorer v1."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind

ANSWER_SCORER_ID = "typed-answer"
ANSWER_SCORER_VERSION = "1.0"
ANSWER_SCORER_DIGEST = "sha256:" + hashlib.sha256(
    b"typed-answer-v1:nfkc:decimal:formula:set:abstain"
).hexdigest()


class AnswerVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True, slots=True)
class AnswerScore:
    verdict: AnswerVerdict
    reason: str

    @property
    def passed(self) -> bool:
        return self.verdict == AnswerVerdict.PASS


def score_answer(answer: str | None, gold: GoldAnswer) -> AnswerScore:
    text = answer or ""
    if gold.kind == GoldAnswerKind.ABSTAIN:
        passed = _looks_like_abstain(text)
        return AnswerScore(
            AnswerVerdict.PASS if passed else AnswerVerdict.FAIL,
            "deterministic abstention matched" if passed else "answer did not abstain",
        )
    if not text.strip():
        return AnswerScore(AnswerVerdict.FAIL, "answer is empty")

    accepted = _accepted_values(gold)
    if gold.kind == GoldAnswerKind.TEXT:
        passed = any(_contains_value(text, value) for value in accepted)
    elif gold.kind == GoldAnswerKind.NUMERIC:
        passed = any(
            _numeric_match(text, value, gold.unit, gold.tolerance) for value in accepted
        )
    elif gold.kind == GoldAnswerKind.FORMULA:
        passed = any(_formula_match(text, value) for value in accepted)
    elif gold.kind == GoldAnswerKind.SET:
        canonical = gold.canonical if isinstance(gold.canonical, list) else accepted
        passed = bool(canonical) and all(_contains_value(text, value) for value in canonical)
    else:
        return AnswerScore(AnswerVerdict.NEEDS_REVIEW, "unsupported answer kind")
    return AnswerScore(
        AnswerVerdict.PASS if passed else AnswerVerdict.FAIL,
        "typed deterministic scorer matched"
        if passed
        else "typed deterministic scorer did not match",
    )


def _accepted_values(gold: GoldAnswer) -> list[str]:
    canonical = (
        gold.canonical if isinstance(gold.canonical, list) else [gold.canonical or ""]
    )
    return [value for value in [*canonical, *gold.accepted_values] if value]


def normalize_text(value: str) -> str:
    return re.sub(
        r"\s+", " ", unicodedata.normalize("NFKC", value).strip().casefold()
    )


def _contains_value(answer: str, expected: str) -> bool:
    normalized_answer = normalize_text(answer)
    normalized_expected = normalize_text(expected)
    if not normalized_expected:
        return False
    start = normalized_answer.find(normalized_expected)
    while start >= 0:
        end = start + len(normalized_expected)
        left_ok = start == 0 or not (
            normalized_expected[0].isascii()
            and normalized_expected[0].isalnum()
            and normalized_answer[start - 1].isalnum()
        )
        right_ok = end == len(normalized_answer) or not (
            normalized_expected[-1].isascii()
            and normalized_expected[-1].isalnum()
            and normalized_answer[end].isalnum()
        )
        if left_ok and right_ok:
            return True
        start = normalized_answer.find(normalized_expected, start + 1)
    return False


_NUMBER_RE = re.compile(
    r"(?<![\d.])([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\d.])"
)


def _numbers(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for match in _NUMBER_RE.finditer(unicodedata.normalize("NFKC", text)):
        try:
            values.append(Decimal(match.group(1).replace(",", "")))
        except InvalidOperation:
            continue
    return values


def _numeric_match(
    answer: str,
    expected: str,
    unit: str | None,
    tolerance: Decimal | None,
) -> bool:
    expected_numbers = _numbers(expected)
    answer_numbers = _numbers(answer)
    if not expected_numbers or not answer_numbers:
        return False
    allowed = tolerance or Decimal(0)
    value_matches = all(
        any(abs(expected_value - answer_value) <= allowed for answer_value in answer_numbers)
        for expected_value in expected_numbers
    )
    if not value_matches:
        return False
    return unit is None or _contains_unit(answer, unit)


def _contains_unit(answer: str, unit: str) -> bool:
    normalized_answer = normalize_text(answer)
    normalized_unit = normalize_text(unit)
    if not normalized_unit:
        return False
    if normalized_unit.isascii() and normalized_unit.isalpha():
        return (
            re.search(
                rf"(?<![a-z]){re.escape(normalized_unit)}(?![a-z])",
                normalized_answer,
            )
            is not None
        )
    return normalized_unit in normalized_answer


def canonical_formula(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("η", "eta")
    normalized = re.sub(r"\\(?:eta|mathrm\{eta\})", "eta", normalized)
    normalized = normalized.replace("\\left", "").replace("\\right", "")
    normalized = normalized.replace("\\times", "*").replace("\\cdot", "*")
    normalized = _replace_simple_fractions(normalized)
    normalized = re.sub(r"_\s*\{\s*([^{}]+?)\s*\}", r"_\1", normalized)
    normalized = normalized.replace("{", "").replace("}", "")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("*", "").replace("(", "").replace(")", "")
    return re.sub(r"[^a-z0-9_=/+\-.]+", "", normalized)


def _replace_simple_fractions(value: str) -> str:
    pattern = re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
    previous = None
    while previous != value:
        previous = value
        value = pattern.sub(r"\1/\2", value)
    return value


def _formula_match(answer: str, expected: str) -> bool:
    canonical = canonical_formula(expected)
    return bool(canonical) and canonical in canonical_formula(answer)


def _looks_like_abstain(text: str) -> bool:
    normalized = normalize_text(text)
    patterns = (
        r"\bnot (?:mentioned|provided|specified|stated)\b",
        r"\b(?:cannot|can't|unable to) (?:determine|answer|provide)\b",
        r"\binsufficient information\b",
        r"(?:文档|上下文).{0,15}(?:没有|不存在|未提供|未提及|未包含)",
        r"(?:无法|不能)(?:提供|给出|确定|回答)",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)
