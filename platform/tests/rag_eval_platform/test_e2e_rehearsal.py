from types import SimpleNamespace

from rag_eval.e2e_rehearsal import CanonicalValueIndex, mses_progress


def _payload() -> SimpleNamespace:
    return SimpleNamespace(
        answer=SimpleNamespace(kind="text"),
        mses_paths=(
            SimpleNamespace(
                path_id="primary",
                clauses=(
                    SimpleNamespace(
                        clause_id="primary-a", alternatives=("a1", "a2")
                    ),
                    SimpleNamespace(clause_id="primary-b", alternatives=("b",)),
                ),
            ),
            SimpleNamespace(
                path_id="alternative",
                clauses=(
                    SimpleNamespace(
                        clause_id="alternative-c", alternatives=("c",)
                    ),
                ),
            ),
        ),
    )


def test_mses_preserves_or_paths_and_or_clause_alternatives() -> None:
    progress = mses_progress(_payload(), {"a2": 4, "b": 2})

    assert progress["complete_path_ids"] == ["primary"]
    assert progress["first_complete_rank"] == 4
    assert progress["best_clause_coverage"] == 1.0


def test_mses_uses_an_alternative_path_without_flattening_required_groups() -> None:
    progress = mses_progress(_payload(), {"c": 1})

    assert progress["complete_path_ids"] == ["alternative"]
    assert progress["first_complete_rank"] == 1
    primary = next(item for item in progress["paths"] if item["path_id"] == "primary")
    assert primary["complete"] is False


def test_private_canonical_mapping_fails_closed_for_short_or_ambiguous_witnesses() -> None:
    index = CanonicalValueIndex(
        by_value={
            "unique canonical witness": frozenset({"object-unique"}),
            "short": frozenset({"object-short"}),
            "ambiguous canonical witness": frozenset({"object-a", "object-b"}),
        },
        by_object={
            "object-unique": frozenset({"unique canonical witness"}),
            "object-short": frozenset({"short"}),
            "object-a": frozenset({"ambiguous canonical witness"}),
            "object-b": frozenset({"ambiguous canonical witness"}),
        },
    )

    mapping = index.map_content(
        "unique canonical witness short ambiguous canonical witness"
    )

    assert mapping["canonical_object_ids"] == []
    assert mapping["status"] == "unmapped"
    assert mapping["short_value_canonical_object_ids"] == [
        "object-a",
        "object-b",
        "object-short",
        "object-unique",
    ]
    assert mapping["ambiguous_canonical_object_ids"] == []


def test_private_mapping_accepts_only_a_source_unique_long_witness() -> None:
    witness = "x" * 48
    index = CanonicalValueIndex(
        by_value={witness + " target": frozenset({"target"}), "other": frozenset({"other"})},
        by_object={"target": frozenset({witness + " target"}), "other": frozenset({"other"})},
    )

    mapping = index.map_content("prefix " + witness + " suffix", ["target"])

    assert mapping["canonical_object_ids"] == ["target"]
    assert mapping["status"] == "exact_unique_canonical_witness"
