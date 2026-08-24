# RAG Evaluation WebUI — UI / UX Audit

Date: 2026-08-24
Scope: presentation, navigation, accessibility, responsiveness, and i18n only. No Evaluation API, Artifact Contract 1.2, Worker Protocol 1.0, artifact, metric, comparison, or failure-assessment semantics are changed by this proposal.

## Executive summary

The current UI is a compact, working prototype with a sound semantic core: it
does not conflate observed `0`, `[]`, `null`, `unavailable`, `error`, or
`needs_review`. The live Golden Smoke review also found no console errors and
no document-level horizontal overflow at 390px.

Its main problem is information architecture rather than missing data. The
product currently presents itself as an editorial “Evidence ledger”: oversized
serif headings, paper texture, large page introductions, decorative numbering,
and card-like grids consume attention that should go to run selection,
coverage, comparability, failures, and reproducibility. The requested target is
a restrained experiment-analysis workspace closer to GitHub Actions, MLflow,
or Linear: compact, tabular, inspectable, and stable during long analysis
sessions.

Recommended design direction: **a neutral laboratory console**. Use a compact
application shell, semantic tables, clear panes and tabs, quiet surfaces, and
one shared status system. Do not add gradients, glass effects, oversized cards,
or decorative animation.

## Review method and observed baseline

- Source review: `src/App.tsx` (341 lines), `src/components.tsx` (70 lines),
  `src/styles.css` (193 lines), `src/semantics.ts`, and API/type boundaries.
- Runtime review: copied (not modified) Golden Smoke Platform home, six runs,
  real cases, and a successful comparison.
- Viewports: desktop and `390 × 844`.
- Runtime result: no browser console warnings/errors; at 390px,
  `document.scrollWidth === 390`.
- Theme result: no existing dark/light theme implementation was found. There is
  only a fixed light `theme-color`; Phase A must not introduce an unrelated
  theme feature, but its tokens should be theme-ready.

## Current UX findings

| Priority | Finding | Evidence | Impact | Direction |
| --- | --- | --- | --- | --- |
| P0 | No i18n layer exists. | Static English is spread through `App.tsx`, `components.tsx`, `semantics.ts`, and `index.html`; no locale, language, or persistence code exists. | The Chinese-language requirement cannot be met safely or consistently. | Introduce a small typed locale layer before page work. |
| P0 | Runs is a master/detail inspector, not the requested run-analysis table. | `RunsPage` loads summary/integrity only for the selected run (`App.tsx:236-268`). | Users cannot scan System, Dataset, Coverage, primary metrics, failures, or duration across runs. | Make Runs a progressive, dense table; route to a dedicated detail view. |
| P0 | Run Detail, Artifacts, and Reproducibility are not first-class information areas. | Selected run stays in component state; there is no durable run-detail route or tab model. | Inspection is not linkable, shareable, or structured around audit tasks. | Add a UI-only run detail route with Overview, Cases, Retrieval, Failures, Artifacts, and Reproducibility tabs. |
| P0 | Comparison table has a fixed four-run CSS grid. | `.comparison-row` uses `repeat(4, ...)` in `styles.css:176`, while selected run count is dynamic. | Empty columns and unstable density appear when comparing fewer/more than four runs. | Use a semantic table or CSS column count derived from selected runs. |
| P1 | Job failures compete with the run list for primary attention. | The job tape is placed before Runs and exposes long raw errors (`App.tsx:251`). | A completed, verified run is visually buried below incidental historical job errors. | Move active jobs into a compact utility panel; link failures to their job/run rather than using a page-wide tape. |
| P1 | Metric cards dominate both run and case analysis. | Every metric is a minimum 116px card, including unavailable metrics (`styles.css:133-141`). | Large grids make coverage and primary metrics harder to scan than the empty states themselves. | Use metric rows/columns; reserve small metric tiles for a short overview only. |
| P1 | Failure analysis has no aggregate entry point or filters. | Labels appear only inside one case detail (`App.tsx:301`). | `retrieval_missing`, `ranking_failure`, `context_selection_loss`, `generation_failure`, `unsupported_answer`, `timeout`, `adapter_error`, and `needs_review` cannot be scanned across cases. | Derive an existing-data Failure view from `GET /runs/{id}/cases`; do not introduce a new backend endpoint. |
| P1 | Case evidence is present but not expressed as a flow. | Gold, answer, evidence stages, metrics, and telemetry form one long stream (`App.tsx:296-310`). | Readers must infer Raw → Ranked → Context → Answer → Evaluation themselves. | Add named Evidence Flow stages, stage counts, and controlled disclosure while preserving `null`, `[]`, and `0`. |
| P2 | The visual language is editorial rather than operational. | Large Baskerville/Iowan titles, paper texture, orange rail rule, page numbers, and decorative “SYSTEM” text (`styles.css:23-69`, `94-99`). | It is memorable, but not the desired calm high-density research dashboard. | Replace with a neutral UI and mono treatment only for identifiers, configs, and protocol values. |
| P2 | No shared token scale exists beyond a few color variables. | 30+ literal colors and many one-off spacing/type values occur in one CSS file. | Surfaces, spacing, badge states, and typography drift as pages grow. | Establish primitive and semantic tokens, then migrate all components to them. |

## Page-level review

### Global shell and navigation

The desktop rail is clear, but `Cases` is treated as a peer destination even
though it is normally reached from a run. The fixed 146px top bar and large
page introductions leave too little vertical space for analysis. At 390px the
navigation drawer can open, but it has no backdrop/focus management and the
header removes run/job context entirely.

Recommended hierarchy:

```text
Analysis
  Runs
  Compare

Configuration
  Datasets
  Systems
  Experiments

Contextual routes
  Run detail → Overview | Cases | Retrieval | Failures | Artifacts | Reproducibility
  Case detail
```

`Cases` remains addressable, but becomes a contextual route reached from a run
rather than a competing top-level task. The header should carry a compact
breadcrumb, page title, connection state, refresh action, and the language
switcher—without a marketing-style identity block.

### Runs

The current list exposes only status, experiment id, run id, adapter, and date.
The adjacent inspector then renders every metric for one run. In the live
Golden Smoke view, failed preliminary jobs occupy the first large block and
the verified completed run begins below the fold.

Replace it with a table whose default columns are:

```text
Run | System | Dataset | Status | Created | Cases | Coverage |
Primary metrics | Execution failure | Duration | Integrity
```

- Fetch summaries progressively and cache them by `run_id`; table rows remain
  useful before secondary summary values return.
- Derive duration from `started_at` and `completed_at` without altering run
  data.
- Select a documented primary metric order for presentation only; never imply
  a winner.
- Keep full technical ids available through a copy affordance or detail page.
- Put active jobs in a compact status strip or an expandable queue section.

### Run Detail

The current inspector proves checksum validity and exposes metric values, but
it loses context on navigation and overflows the page with metric tiles.

The replacement header should contain only:

```text
Run · System · Dataset · Model (when recorded) · Status · Coverage · Integrity
```

Then present tabs:

| Tab | Presentation-only content from existing API/artifacts |
| --- | --- |
| Overview | primary metrics, execution counts, duration, status timeline, protocol/version facts |
| Cases | searchable/filterable existing case list |
| Retrieval | stage coverage and retrieval/context metrics; never convert unavailable to zero |
| Failures | aggregates and filters derived from existing case results/error/failure assessment |
| Artifacts | manifest/run checksums and existing verify result |
| Reproducibility | system/adapter/scorer versions, effective config, seeds, replay relation, and existing report reference |

No backend contract change is required. The already available run manifest,
summary, cases, verification response, and existing report endpoint are
sufficient. When a model identity is not recorded in existing effective config,
the UI must render a localized “not recorded” state rather than infer one.

### Case Detail

Current content is complete but is read as a long article. Gold and generated
answers appear side by side, yet their visual distinction depends mostly on a
small label. Raw, ranked, and final-context sections are present but do not
read as an evidence pipeline. On mobile, the horizontal case chooser works but
is visually dominant before the selected case’s decisive outcome.

Use this fixed Evidence Flow, with a small stage navigator and visibly ordered
sections:

```text
Question
  ↓
Raw Retrieval
  ↓
Ranked Retrieval
  ↓
Final Context
  ↓
Answer
  ↓
Evaluation
```

Place a separate, clearly labeled Gold panel next to or immediately above the
model-result panel. Gold Answer and Gold Evidence use a quiet protected surface;
model evidence uses the normal surface. For every stage, retain the current
semantic display rules:

| Raw artifact value | UI meaning |
| --- | --- |
| `null` | `unavailable` / not observable; never display as zero |
| `[]` | observed empty result |
| `0` | observed numeric zero |
| `error` | error state with original diagnostic preserved |
| `needs_review` | review-needed semantic state, never completion |

Large evidence payloads may be collapsed after a visible count and state, but
must be keyboard-accessible and must not hide Gold evidence or failure labels.

### Compare

The current view correctly avoids a global-winner claim, which must be kept.
It nevertheless leads with run selection and a large metric matrix before
showing why the comparison is valid. It shows per-metric comparability and
coverage but not the requested controlled/treatment-factor summary.

Reorder the page:

```text
Comparison tier → Compatibility → Controlled factors → Treatment factors
→ selected runs → metric table
```

- Build factor facts from the returned run manifests (`bundle_id`, case
  selection, system/adapter/scorer versions, repetitions, and effective
  config). Mark equal/different facts only; do not invent causal language.
- The metric table must show value, coverage, comparable status, winner
  eligibility, and reason per metric. “Winner eligible” remains per-metric;
  never render an overall winner.
- Keep backend reasons verbatim under a localized “Platform reason (original)”
  label because they are artifact/API content, not frontend copy.
- Use an accessible horizontal table at narrow widths with a sticky first
  column, not a fixed number of grid columns.

### Failure Analysis

Implement this as a Run Detail tab using only fetched case artifacts. Offer
facets for the contract values and display them unchanged in data attributes/
filter state while translating their labels:

```text
retrieval_missing · ranking_failure · context_selection_loss
generation_failure · unsupported_answer · timeout · adapter_error · needs_review
```

Rows should expose case id, repetition, stage, failure label, status, short
reason, and review requirement. A filter never changes `FailureAssessment`;
it only selects existing cases for display.

## Component and visual consistency review

### Current strengths to preserve

- `presentMetric()` and `evidenceState()` preserve the important value-state
  distinction and already have semantic tests.
- `StateMark` pairs an icon with text, so most status states are not color-only.
- Existing `prefers-reduced-motion` handling is present.
- Long ids and evidence metadata generally use monospaced treatment and wrap.

### Required refactor

| Current element | Problem | Replacement |
| --- | --- | --- |
| `StateMark` | It derives visible labels by replacing underscores; no localized label map, and state styling is distributed. | One `StatusBadge` with translation keys, tone tokens, icons, and a raw enum value only in metadata. |
| `MetricCell` | Card is the only metric presentation; unavailable states take substantial area. | `MetricValue` for tables plus a compact `MetricSummary` for overview; same formatter/state map. |
| `EvidenceList` | Title/copy is caller-provided English and semantic helper text is hard-coded. | `EvidenceStage` keyed by stage enum and shared empty/unavailable presentation. |
| CSS div “tables” | Dataset and comparison grids lack table semantics and comparison column count is fixed. | `DataTable` with `<table>`, headers, responsive row presentation, and keyboard-readable cells. |
| `PageIntro` | Large editorial intro repeats on all pages. | `PageHeader` with concise description and optional scoped actions. |
| Global `styles.css` | Tokens, component styles, page layouts, and breakpoints are interleaved. | Token layer plus component/page style layers using semantic class names. |

### Token proposal

No dependency is needed. Define CSS custom properties once and prohibit
component-local raw colors/spacing values.

```text
Typography
  --font-ui, --font-mono
  --text-xs 12px, --text-sm 13px, --text-md 14px, --text-lg 16px,
  --text-xl 20px, --text-2xl 24px

Spacing
  --space-1 4px, --space-2 8px, --space-3 12px, --space-4 16px,
  --space-5 24px, --space-6 32px

Geometry
  --radius-sm 4px, --radius-md 6px, --border-subtle, --border-default
  --content-max 1600px, --table-row-compact 36px, --table-row-default 44px

Surfaces
  --canvas, --surface, --surface-raised, --surface-selected, --surface-inset
  --text, --text-muted, --text-subtle

Semantic status
  --status-success-*, --status-warning-*, --status-error-*,
  --status-review-*, --status-unavailable-*, --status-neutral-*
```

Use no gradient, texture overlay, glass blur, large shadow, or ornamental
background text. Use neutral selected/focus treatments for navigation and
reserve status tones for status semantics only.

## Responsive and accessibility findings

At 390px, the page does not horizontally overflow, but the behavior is not yet
analysis-first:

- Run/job counts are hidden in the header; job/error blocks still precede the
  run table.
- The mobile case carousel exposes only a few case ids and competes with the
  selected detail.
- The comparison table is only wrapped in horizontal overflow; its first column
  is not sticky and its fixed desktop grid does not scale with selected runs.
- Tables are visually grids of `div`/`span`, so column relationships are weaker
  for assistive technology.
- Buttons have hover styles but no systematic `:focus-visible` treatment;
  modal navigation has no focus trap or backdrop semantics.
- Several labels are 0.52–0.66rem, below a comfortable long-session analysis
  size, especially for status, metric provenance, and comparison metadata.

Implementation targets:

- Desktop: 1280px and 1440px review with bounded content width.
- Mobile: 390px; no document overflow; readable 12px minimum metadata;
  horizontal data tables only where the full matrix is essential.
- Keyboard: visible focus, semantic tabs/table headers, drawer focus handling,
  and all expandable evidence reachable by keyboard.
- Color: status icon + translated text + tone; never tone alone.
- Motion: keep reduced-motion support; remove decorative page-entry/pulse
  animation unless it communicates an actual update.

## i18n hard-coded string inventory

There is currently no locale provider, dictionary, persistence key, or locale-
aware date/number formatting. The following inventory is the migration scope;
all static user-facing copy must move into the locale layer.

| Source | Lines | Current copy categories to migrate |
| --- | --- | --- |
| `index.html` | 7 | document title |
| `src/App.tsx` | 35-41, 113-145 | navigation, brand, connection state, top-bar counters, tooltips, aria labels |
| `src/App.tsx` | 176-191 | dataset description, form labels, buttons, columns, empty state |
| `src/App.tsx` | 197-232 | systems and experiment descriptions, actions, validation/queued messages, labels |
| `src/App.tsx` | 250-267 | run description, cancel, integrity, counts, empty states, case action |
| `src/App.tsx` | 286-309 | case title, question metadata, Gold/model labels, evidence titles, telemetry, semantic explanation |
| `src/App.tsx` | 324-340 | comparison tiers, compatibility copy, winner-eligibility wording, coverage/reason labels, loading copy |
| `src/components.tsx` | 16, 29-56 | status display, metric provenance, evidence availability/empty text, unknown/empty evidence fallbacks |
| `src/semantics.ts` | 4-18, 34-38 | metric explanations and metric status presentation |
| `src/styles.css` | 96 | visible decorative `SYSTEM` pseudo-content; remove rather than translate |

Contract and artifact values are not translation targets. The UI will retain
the raw values in API payloads, URLs, filters, classes, and copied identifiers,
then translate only the displayed label. Examples:

```text
needs_review       → 需要人工复核 / Needs Review
unavailable        → 不可用 / Unavailable
generation_failure → 生成失败 / Generation Failure
```

Technical identifiers such as `context_recall@5`, `MRR`, `Recall@K`, run ids,
and raw API diagnostics remain unchanged. The UI may add a translated
explanation adjacent to them. Dynamic artifact content—questions, answers,
evidence, model output, and backend-generated reasons—is displayed verbatim
under localized labels and is never rewritten.

## Proposed i18n architecture

Use React context and JSON dictionaries; do not add `react-i18next` or another
dependency for this small static application.

```text
src/i18n/
  en-US.json
  zh-CN.json
  index.ts             # typed t(), interpolation, enum/metric helpers
  LocaleProvider.tsx   # persisted selection and browser-locale detection
  i18n.test.ts         # exact key parity and locale-selection tests
```

- Persist under a stable key such as `rag-eval-webui.locale`.
- Resolution order: saved preference → `navigator.languages`/`navigator.language`
  (`zh-*` → `zh-CN`) → `en-US`.
- Add an accessible header Language Switcher: `中文 | English`.
- Format dates, counts, percentages, and numeric metrics with `Intl` using the
  selected locale, rather than raw `toLocaleString()`.
- Replace all new and existing static JSX strings, `title`, `aria-label`,
  placeholder, empty-state text, status presentation, metric explanation, and
  button copy with translation keys.

## Proposed file plan

| File | Planned change | Contract impact |
| --- | --- | --- |
| `src/App.tsx` | reduce to shell, routing, data coordination, and page composition | none |
| `src/components.tsx` | split/replace with presentation primitives | none |
| `src/styles.css` | replace editorial global stylesheet with tokenized UI styles | none |
| `src/semantics.ts` | retain state logic; accept presentation/i18n helpers instead of English literals | none |
| `src/semantics.test.ts` | preserve zero/unavailable/error/needs-review assertions; add locale-aware presentation coverage | none |
| `src/api.ts` | optionally expose existing report read endpoint only; no endpoint/schema change | none |
| `src/types.ts` | keep transport types unchanged; add only local presentation helper types if required | none |
| `src/i18n/*` | add locale dictionaries, provider, formatters, and tests | none |
| `src/components/*`, `src/pages/*` | add small reusable layout/table/detail components if extraction improves clarity | none |
| `UI_AUDIT.md` | this audit | none |

## Delivery sequence

### Phase A — design tokens and presentation primitives

- Add token layer, `AppShell`, `PageHeader`, `StatusBadge`, `MetricValue`,
  `DataTable`, and focus/reduced-motion rules.
- Maintain all existing enum values and semantic tests.

### Phase B — layout and navigation

- Compact the application shell, group navigation, add durable contextual
  routes, connection state, and Language Switcher placement.

### Phase C — Runs, Run Detail, and Case Detail

- Deliver the run table, run tabs, Evidence Flow, Gold/model separation,
  progressive summaries, and artifact/reproducibility views sourced only from
  existing data.

### Phase D — Compare and Failure Analysis

- Add the factor summary, dynamic comparison table, per-metric reasons, and
  derived case-failure filters; do not calculate or declare a global winner.

### Phase E — `zh-CN` / `en-US` i18n

- Migrate every static visible string, persist language choice, add locale
  detection and enum/metric translation tests.

### Phase F — responsive, accessibility, and polish

- Validate 390px and desktop layouts, keyboard interaction, focus states,
  no-color-only states, no console errors, and final visual density.

## Verification gates for implementation

- `npm run test`
- `npm run build` (TypeScript check and production bundle)
- Existing Platform semantic tests, including contract and Golden Smoke
  coverage, remain green.
- Browser validation at desktop and 390px: no document overflow, clear tables
  and tabs, keyboard focus, no console errors.
- Direct checks that selected locale persists, `zh-*` defaults to `zh-CN`, and
  every locale has the same key set.
- Semantic regression checks prove `0`, `[]`, `null`, `unavailable`, `error`,
  and `needs_review` keep their current distinctions.

## Explicit non-goals

- No change to API routes, request/response payloads, schemas, Contract 1.2,
  Worker Protocol 1.0, Evaluation Engine, metric calculation, comparison
  decision, failure assessment, run checksums, or sealed artifacts.
- No new server-side feature or UI dependency.
- No dark-mode feature is added solely because tokens become theme-ready.
- No global “winner” label or inferred model claim.
