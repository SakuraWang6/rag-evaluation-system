# Phase A UI Report — macOS-inspired Research Console

Date: 2026-08-25

## Outcome

Phase A is complete. The WebUI now has a compact, desktop-first,
macOS-inspired research-console foundation. It replaces the editorial paper /
serif treatment with a Finder/System Settings-like application shell, light
neutral surfaces, system typography, compact controls, and one semantic status
language. No dependency was added.

This phase deliberately does **not** rewrite the Runs, Compare, or Case Detail
information architecture. Their current content remains available while using
the new shell, tokens, controls, status badges, and localized display layer.

## Delivered foundation

| Area | Delivered |
| --- | --- |
| Design tokens | System UI and mono font stacks; 12/13/14/17/20/24px text scale; 4/8/12/16/20/24px spacing; 6/10/12px radii; window/sidebar/grouped/inset/selected/inspector/popover surfaces; shared borders and semantic status tones. |
| Application shell | `AppShell`, compact sidebar grouped as Analysis and Configuration, top toolbar, breadcrumb/current page title, connection state, refresh action, and persistent language switcher. |
| Primitives | `Button`, `IconButton`, `SegmentedControl`, `StatusBadge`, `Surface`, `DataTable`, `InspectorSection`, and `DisclosureSection`. The dataset list now uses semantic table markup. |
| Page foundation | `PageHeader` replaces oversized numbered editorial intros; existing business content is styled through the shared foundation rather than page-local visual language. |
| Accessibility | A shared `:focus-visible` ring, semantic table headers, icon labels, status icon + text, and reduced-motion handling. The mobile drawer close control is rendered only while the drawer is open. |

## i18n

Added the requested structure:

```text
src/i18n/
  en-US.json
  zh-CN.json
  index.ts
  LocaleProvider.tsx
  i18n.test.ts
```

- `rag-eval-webui.locale` stores an explicit user choice.
- Resolution order is saved choice → browser `zh-*` → `zh-CN`; all other
  browser locales resolve to `en-US`.
- The toolbar switcher exposes `中文` and `English`; date and percentage output
  uses `Intl` for the active locale.
- Visible static UI copy, status labels, metric explanations, failure-label
  displays, aria labels, placeholders, and action text use the dictionaries.
- The dictionaries have an exact-key-parity test.

## Browser review and screenshots

Local validation used a copied Golden Smoke Platform home; no sealed bundle,
run artifact, checksum, or source Platform home was changed. Screenshot review
was performed in the browser at the following viewports; raster captures were
not added to the repository as product assets.

| Viewport / screen | Result |
| --- | --- |
| 1440 × 960 — Runs | Compact sidebar, toolbar, run master/detail surface, localized status badges, and metric state presentation all render without document overflow (`1440 == 1440`). |
| 1280 × 900 — Compare | Two completed Golden Smoke runs produced a comparison surface without document overflow (`1280 == 1280`). Per-metric `not_comparable` state remains present; the UI says only “No global winner declaration”, never declares one. |
| 390 × 844 — Runs and Cases | `scrollWidth == clientWidth == 390`; menu opens/closes correctly, the hidden sidebar no longer leaks a close button, case selector/index/detail remain usable, and three evidence sections render. |
| Language persistence | Selecting English changed `document.lang` to `en-US`, changed the title to `RAG Evaluation`, and remained selected after reload. |
| Keyboard focus and console | Shared focus rule computed as `3px` on the refresh control; browser console recorded zero warnings and zero errors. |

## Semantic boundary verification

The following are intentionally unchanged:

- API endpoints, request payloads, response types, Artifact Contract 1.2, and
  Worker Protocol 1.0.
- Evaluation, comparison, metric, failure-assessment, run, artifact, and
  checksum logic.
- Raw API/artifact values. `StatusBadge` retains the incoming enum in
  `data-status`; it translates only the visible label. Failure labels are
  translated only when they are known contract values; unknown backend reasons
  remain verbatim.
- `presentMetric()` still emits `0.000` for observed zero and distinct states
  for unavailable, not-applicable, error, and needs-review. `evidenceState()`
  still distinguishes `null` (unavailable), `[]` (observed empty), and
  populated evidence.

## Verification

| Check | Result |
| --- | --- |
| `npm run test` | PASS — 2 files, 5 tests |
| `npm run build` | PASS — TypeScript build and Vite production build |
| Dictionary parity / locale selection | PASS |
| Existing semantic distinctions | PASS |
| `git diff --check` | PASS |
| Browser console | PASS — 0 warnings, 0 errors |

## Recommended next order

1. **Phase B — page-level navigation:** make Run Detail a durable contextual
   route, move Cases into run context while retaining a reachable direct URL,
   and add keyboard-complete drawer behavior.
2. **Phase C — Runs / Run Detail / Case Detail:** replace the master/detail
   run list with the requested high-density run table, then introduce the
   Overview / Cases / Retrieval / Failures / Artifacts / Reproducibility
   structure and evidence flow using existing API data only.
3. **Phase D — Compare / Failure Analysis:** add controlled/treatment-factor
   facts, dynamic table columns, and case-derived failure filters without an
   overall-winner calculation.
