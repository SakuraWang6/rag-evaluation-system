"""Deterministic evaluation independent of any RAG implementation."""

from rag_eval.evaluation.answers import AnswerScore, score_answer
from rag_eval.evaluation.engine import evaluate_case
from rag_eval.evaluation.metrics import evaluate_retrieval_stages
from rag_eval.evaluation.unified import EvaluationProfile, evaluate_unified_trace

__all__ = [
    "AnswerScore",
    "EvaluationProfile",
    "evaluate_case",
    "evaluate_retrieval_stages",
    "evaluate_unified_trace",
    "score_answer",
]
