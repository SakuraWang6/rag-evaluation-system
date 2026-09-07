"""Typed deterministic answer scorer v1.3.

The scorer owns only outcomes it can establish without interpretation.  Text
answers which are neither an exact match nor a mechanical contradiction are
deliberately handed to the configured semantic reviewer, then to a human when
the reviewer remains uncertain.  It does not claim formula equivalence without
a versioned parser.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path

from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind

ANSWER_SCORER_ID = "typed-answer"
ANSWER_SCORER_VERSION = "1.3"


def scorer_source_digest() -> str:
    """Digest the actual scorer source instead of a manually maintained label."""

    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


ANSWER_SCORER_DIGEST = scorer_source_digest()


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
        return _score_text(text, accepted)
    if gold.kind == GoldAnswerKind.NUMERIC:
        return _score_numeric(text, accepted, gold.unit, gold.tolerance)
    if gold.kind == GoldAnswerKind.FORMULA:
        return _score_formula(text, accepted)
    if gold.kind == GoldAnswerKind.SET:
        canonical = gold.canonical if isinstance(gold.canonical, list) else accepted
        return _score_set(text, canonical)
    return AnswerScore(AnswerVerdict.NEEDS_REVIEW, "unsupported answer kind")


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
        # Treat ASCII identifiers as tokens only next to another ASCII
        # identifier character.  Chinese prose commonly attaches a term such
        # as ``HTTP`` directly to ``协议``; rejecting that is a false boundary
        # and unnecessarily sends an otherwise determinate answer to review.
        left_ok = start == 0 or not (
            _is_ascii_identifier_char(normalized_expected[0])
            and _is_ascii_identifier_char(normalized_answer[start - 1])
        )
        right_ok = end == len(normalized_answer) or not (
            _is_ascii_identifier_char(normalized_expected[-1])
            and _is_ascii_identifier_char(normalized_answer[end])
        )
        if left_ok and right_ok:
            return True
        start = normalized_answer.find(normalized_expected, start + 1)
    return False


def _is_ascii_identifier_char(value: str) -> bool:
    return value.isascii() and value.isalnum()


def _score_text(answer: str, accepted: list[str]) -> AnswerScore:
    normalized = normalize_text(answer)
    values = {normalize_text(value) for value in accepted if normalize_text(value)}
    if normalized in values:
        return AnswerScore(AnswerVerdict.PASS, "exact normalized text matched")
    if _is_unambiguous_value_statement(answer, accepted):
        return AnswerScore(
            AnswerVerdict.PASS,
            "unambiguous answer statement matched",
        )
    if any(_contains_value(answer, value) for value in accepted):
        return AnswerScore(
            AnswerVerdict.NEEDS_REVIEW,
            "text contains a gold value but is not exact-normalized",
        )
    # A text mismatch is often a legitimate paraphrase (or an equally real
    # contradiction) that a lexical rule cannot safely distinguish.  Keep it
    # out of the final score until the semantic LLM / human stages decide it.
    return AnswerScore(
        AnswerVerdict.NEEDS_REVIEW,
        "text semantic equivalence requires LLM or human adjudication",
    )


_REFERENCE_SECTION = re.compile(
    r"(?:^|\n)\s{0,3}#{1,6}\s*(?:references?|sources?|citations?|"
    r"参考资料|参考文献|引用|来源)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_NEGATION_OR_ALTERNATIVE = re.compile(
    r"(?:不是|并非|非\s*[^。；;，,]*$|而不是|或者|或是|还是|either|or|not)"
    r"|(?:\bno\b|\bneither\b)",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION = re.compile(r"^[\s。．.!！?？,，;；:：\)）\]】]*$")
_LEADING_ANSWER_OPERATOR = re.compile(r"(?:是|为|:|：|=|\bis\b)\s*$", re.IGNORECASE)


def _is_unambiguous_value_statement(answer: str, accepted: list[str]) -> bool:
    """Accept a single value in a plain answer sentence, not arbitrary prose.

    Models routinely wrap a short text Gold value in a sentence such as
    ``型号是 S2910-48GT4XS-E。`` and then append a references section.  That is
    a determinate answer, not an answer needing human review.  We deliberately
    keep the rule narrow: it accepts exactly one Gold occurrence introduced by
    an answer operator and permits only punctuation afterwards.  Negation and
    alternatives still require review.
    """

    body = _REFERENCE_SECTION.split(answer, maxsplit=1)[0].strip()
    if not body or _NEGATION_OR_ALTERNATIVE.search(body):
        return False
    matches: list[tuple[int, int]] = []
    for value in accepted:
        normalized_value = normalize_text(value)
        if not normalized_value:
            continue
        normalized_body = normalize_text(body)
        start = normalized_body.find(normalized_value)
        while start >= 0:
            end = start + len(normalized_value)
            if _contains_value(normalized_body[start:end], normalized_value):
                matches.append((start, end))
            start = normalized_body.find(normalized_value, start + 1)
    if len(matches) != 1:
        return False

    normalized_body = normalize_text(body)
    start, end = matches[0]
    prefix = normalized_body[:start]
    suffix = normalized_body[end:]
    return bool(
        _LEADING_ANSWER_OPERATOR.search(prefix)
        and _TRAILING_PUNCTUATION.fullmatch(suffix)
    )


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


def _score_numeric(
    answer: str,
    accepted: list[str],
    unit: str | None,
    tolerance: Decimal | None,
) -> AnswerScore:
    expected_numbers = [number for value in accepted for number in _numbers(value)]
    answer_numbers = _numbers(answer)
    if not expected_numbers or not answer_numbers:
        return AnswerScore(AnswerVerdict.FAIL, "numeric answer has no parseable value")
    allowed = tolerance or Decimal(0)
    matching = [
        value
        for value in answer_numbers
        if any(abs(expected - value) <= allowed for expected in expected_numbers)
    ]
    if not matching:
        return AnswerScore(AnswerVerdict.FAIL, "numeric value did not match")
    if len(matching) != len(answer_numbers):
        return AnswerScore(
            AnswerVerdict.NEEDS_REVIEW,
            "numeric answer contains an additional contradictory or ambiguous value",
        )
    if unit is not None and not _contains_unit(answer, unit):
        return AnswerScore(AnswerVerdict.FAIL, "numeric answer has an incorrect or missing unit")
    return AnswerScore(AnswerVerdict.PASS, "unambiguous numeric value and unit matched")


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


def _score_formula(answer: str, accepted: list[str]) -> AnswerScore:
    candidate = canonical_formula(answer)
    canonicals = {canonical_formula(value) for value in accepted}
    canonicals.discard("")
    if candidate and candidate in canonicals:
        return AnswerScore(AnswerVerdict.PASS, "normalized formula matched exactly")
    return AnswerScore(
        AnswerVerdict.NEEDS_REVIEW,
        "formula equivalence requires a versioned parser or AST evaluator",
    )


_SET_SEPARATOR = re.compile(r"[,;\n\u3001\uff0c\uff1b]+")


def _score_set(answer: str, canonical: str | list[str]) -> AnswerScore:
    expected_values = canonical if isinstance(canonical, list) else [canonical]
    expected = {normalize_text(value) for value in expected_values if normalize_text(value)}
    candidate = {
        normalize_text(value)
        for value in _SET_SEPARATOR.split(answer)
        if normalize_text(value)
    }
    if not expected:
        return AnswerScore(AnswerVerdict.NEEDS_REVIEW, "gold set is empty")
    if candidate == expected:
        return AnswerScore(AnswerVerdict.PASS, "exact normalized set matched")
    if candidate.issuperset(expected):
        return AnswerScore(AnswerVerdict.FAIL, "answer set has extra members")
    if candidate.issubset(expected):
        return AnswerScore(AnswerVerdict.FAIL, "answer set is missing members")
    return AnswerScore(
        AnswerVerdict.NEEDS_REVIEW,
        "set representation is ambiguous or contains non-canonical members",
    )


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
