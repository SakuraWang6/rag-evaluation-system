# Golden Smoke v1 real-model execution record

This directory is deliberately separate from the immutable `golden-smoke-v1`
bundle. It holds the verified model lock, formal execution contracts, registered
experiment specifications, platform-owned raw run artifacts, and human-review
handoff records for the Phase 8 real-model closure.

The selected local runtime is Ollama. The display tags are retained as requested
references only; all formal experiments bind to the resolved SHA-256 identities
in `frozen/model-lock.json`. No `latest` or mutable tag is used as the immutable
identity.

`golden-smoke-independent-review-checklist.csv` is a pending handoff to a
reviewer independent of the author. Completion by the author does not satisfy
the Phase 8 independent-review gate.

The comparison specification declares the three systems task-comparable. It is
not a leaderboard or a claim that RAG-Anything offers equivalent retrieval-stage
observability; unavailable stages must remain unavailable in the recorded cases.
