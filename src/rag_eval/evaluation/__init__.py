"""Deterministic evaluation independent of any RAG implementation."""

from rag_eval.evaluation.answers import AnswerScore, score_answer
from rag_eval.evaluation.engine import evaluate_case
from rag_eval.evaluation.metrics import evaluate_retrieval_stages

__all__ = [
    "AnswerScore",
    "evaluate_case",
    "evaluate_retrieval_stages",
    "score_answer",
]
