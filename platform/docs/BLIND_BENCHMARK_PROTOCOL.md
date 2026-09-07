# Blind Benchmark Protocol

Formal Phase 9 work is separated by role even where one person performs more
than one role. The Curator builds and seals source, questions and Gold; the
Experiment Developer receives only the public tree and freezes code, model
lock, configuration, ComparisonSpec and AnalysisContract; the Evaluator runs
the frozen package and reveals Gold only after all formal runs complete.

```text
blind/
├── source_public/
├── questions_public/
└── public_manifest.json

sealed/
├── gold_answers.jsonl
├── gold_evidence.jsonl
├── canonical/
├── checksums.json
└── blind_protocol.json
```

`rag-eval validate-blind-layout blind sealed` rejects a public tree containing
Gold-named files, a public manifest that exposes Gold/canonical entries, a
missing required path, a symlinked required path, a nested sealed directory,
or a `sealed_bundle_digest` that does not match `checksums.json`.

`blind_protocol.json` is a final immutable timeline record. It requires:

```text
sealed_at < config_frozen_at < formal_runs_started_at
          <= formal_runs_completed_at < gold_revealed_at
```

It also records curator/evaluator identities, frozen code commit, model-lock,
ComparisonSpec and AnalysisContract digests. Any headline configuration change
after Gold reveal is a new, explicitly post-hoc Experiment/ComparisonSpec.
