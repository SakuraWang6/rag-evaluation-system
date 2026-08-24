from __future__ import annotations

import pytest

from rag_eval.contracts.research import AnalysisContract
from rag_eval.statistics import case_clustered_paired_bootstrap


def test_case_clustered_bootstrap_does_not_promote_seeds_to_cases() -> None:
    legacy = {
        "case-a": {1: 0.0, 2: 0.0, 3: 0.0},
        "case-b": {1: 1.0, 2: 1.0, 3: 1.0},
    }
    enhanced = {
        "case-a": {1: 1.0, 2: 1.0, 3: 1.0},
        "case-b": {1: 1.0, 2: 1.0, 3: 1.0},
    }
    result = case_clustered_paired_bootstrap(
        legacy,
        enhanced,
        AnalysisContract(analysis_seed=7, bootstrap_iterations=1000),
    )

    assert result.n_cases == 2
    assert result.matched_seeds_by_case["case-a"] == (1, 2, 3)
    assert result.estimate == 0.5


def test_missing_matched_seed_invalidates_formal_run() -> None:
    with pytest.raises(ValueError, match="operationally invalid"):
        case_clustered_paired_bootstrap(
            {"a": {1: 0.0, 2: 0.0}, "b": {1: 0.0, 2: 0.0}},
            {"a": {1: 1.0, 2: 1.0}, "b": {1: 1.0}},
            AnalysisContract(analysis_seed=7, bootstrap_iterations=1000),
        )


def test_missing_case_invalidates_formal_run_instead_of_shrinking_n() -> None:
    with pytest.raises(ValueError, match="unmatched case IDs"):
        case_clustered_paired_bootstrap(
            {"a": {1: 0.0}, "b": {1: 0.0}},
            {"a": {1: 1.0}},
            AnalysisContract(analysis_seed=7, bootstrap_iterations=1000),
        )
