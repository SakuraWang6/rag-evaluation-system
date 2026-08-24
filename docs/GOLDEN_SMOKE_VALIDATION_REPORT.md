# Golden Smoke Validation Report — v1

## Scope

This is Phase 8 preparation evidence, not a RAG performance comparison. The
bundle and adversarial checks establish whether the Evaluation Platform can be
trusted before any real-model result is interpreted.

## Golden bundle

- Bundle path: `examples/golden-smoke-v1/`
- Bundle ID: `bbfbb1d2761b714a595ae072f786bd527fdff5c85ba7c57c40b6d8087072ba1e`
- Source material: newly authored for Golden Smoke; no historical
  `memory_eval`, structured-ranking, or exact-ID debugging corpus was reused.
- Categories: 4 each of `plain-text`, `numeric/unit`, `table-cell`,
  `explicit-ID`, `multi-evidence`, and `abstain/negative`.

## Bundle formal QA

`load_bundle()` completed with the formal validation profile:

| Check | Result |
| --- | --- |
| Questions | 24 / 24 valid |
| Gold answers | 24 / 24 valid |
| Gold evidence sets | 24 / 24 valid |
| Text-span boundaries and structured locators | 24 / 24 valid |
| Canonical values and quote uniqueness | valid |
| Required evidence groups | 24 / 24 valid |
| Content-address and `checksums.json` | valid |

## Human review

`examples/golden-smoke-v1/golden-smoke-review-checklist.csv` records all 24
cases as approved. The reviewer is explicitly **author review**; this is not
represented as independent review.

## Offline adversarial semantics

The Golden Smoke semantic regression test exercises the FakeAdapter and direct
adversarial artifacts. It verifies:

- observed empty retrieval is `[]`, whereas unavailable stages are `None`;
- observed retrieval miss is metric value `0`, not `unavailable`;
- timeout and adapter error remain `error` with null metric values and zero
  metric denominator, rather than being counted as a zero score;
- answer-wrong/evidence-present yields `generation_failure`;
- answer-correct/evidence-missing yields `retrieval_missing` and
  `unsupported_answer`, without a false generation-failure label;
- partial two-group evidence has recall `0.5`; ambiguous typed answer produces
  `needs_review`;
- JSON case artifacts and Markdown report both include `FailureAssessment`.

## Model lock and system execution

No official `model-lock.json` was created. This environment has no configured
LLM/embedding model runtime and no verified immutable model digest or revision.
Creating a lock from mutable names would violate the Phase 8 identity rule.

| System | Phase 8 status |
| --- | --- |
| FakeAdapter adversarial profiles | completed offline; no model result claimed |
| LightRAG Legacy | not executed due to environment |
| LightRAG Enhanced | not executed due to environment |
| RAG-Anything | not executed due to environment |

## Reconciliation and decision

There is no real-model run artifact, so the required 24/24 human-versus-
automatic per-case reconciliation has not begun. No synthetic or historical
run substitutes for it. Phase 9 remains disallowed.

```text
PHASE 8 GATE: BLOCKED
```
