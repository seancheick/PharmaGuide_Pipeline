# Dashboard v4 acceptance — October 19, 2026

Scope: finish the existing v4 dashboard plan's 20 acceptance checks. Baseline `afa3f7bbd`.
Class: dashboard tooling/infrastructure; production pipeline, clinical data, scoring, export and release code unchanged.

Owner: `scripts/dashboard/score_index.py::IndexReader`, `saved_views.py::apply_filters`, `shell.py::PageContext`, existing page renderers and `triage.py::effective_status` — evidence: ownership-matrix/glossary/caller search, source review, fail-first regression nodes, current index and browser checks. Config bytes remain owned by `scoring_v4/config_registry.py`; movement explanations remain owned by replay.
Will NOT create: scorer, clinical policy, public field/status, registry, pipeline/release step or another execution register.

## Acceptance results

The dashboard capabilities pass all 20 checks. Data qualification is explicitly scoped: the frozen full-corpus index is older than the running operator rebuild. The accepted raw golden outputs are qualified separately; they are not a new full catalog.

| # | Check | Evidence |
|---|---|---|
| 1 | Every Evidence-zero product | 5,054 exact indexed matches; browser saved view and downloaded IDs agree. |
| 2 | Split zero Evidence by state | Applicability/reviewed-null/no-qualifying/review-incomplete saved views and Evidence-state filter; positive/negative fixtures. |
| 3 | Dose 11.4 and why | Exact-value saved view: 9,125; Trace uses recorded neutral/benchmark/ceiling state and receipts. |
| 4 | Every Dose UL cap | 1,010 applied ceilings; separate evaluated-over-limit view. |
| 5 | Triggering ingredient/exposure | Trace's dose flags identify nutrient, %UL, minimum exposure and limit; references preserve per-day amounts. |
| 6 | Every Verification 6 | Exact-value view: 5,412; distinct from the broader fail-open state. |
| 7 | Neutral unknown meaning | Trace and Score Lab explain unknown as neutral, not a failure. |
| 8 | Every deduction/cap/floor/neutral | Receipt-id and kind filters on both planes; named fixture controls. |
| 9 | Reconstruct score/capacity | All 15,426 records: maximum receipt/pillar mismatch 0.0; capacity totals 100; unavailable pillars hatch as not assessed. |
| 10 | Nominal/realized/absorbed | Recorded ledgers, waterfall, absorption filters and fail-first floor controls. |
| 11 | Candidate/release product comparison | Trace timeline and Run Compare; drill-through carries correct product and run, clears stale search. |
| 12 | Every tier crossing | 3,427 in the frozen comparison; filtering/export and owner tests. |
| 13 | Change behind movement | Replay causes and run provenance, plus 721 exact config/calibration-setting diffs; both configs recovered by content fingerprint. Missing history stays unavailable. |
| 14 | Unmapped/unrated | Saved views: 25 unmapped-active products, 917 unrated-form products; separate ingredient index explicitly labelled. |
| 15 | Incomplete calibration records | 45 current records checked; all complete in current data; fault fixtures detect missing sources, rationale and owner. Current-source fingerprint labels prevent historical misattribution. |
| 16 | Golden set/broken canaries | Browser: 53 canaries, 520 checks, zero failures on accepted source-qualified raw outputs. Frozen full index honestly shows 11 failures across 3 older products. Recorded history available. |
| 17 | Exact filtered export | Browser CSV and Parquet IDs exactly equal the 5,054 Evidence-zero index IDs; filenames carry run key. |
| 18 | Index freshness | Changed manifests/deleted batches/projection changes identified; actual active-run stale warning observed. |
| 19 | Catalog parity | Frozen comparison explicitly shows 6,744 movers, 478 status changes, 527 safety changes, zero unattributed movements. This answers mismatch; it does not approve these movements or claim publication. |
| 20 | Pipeline independence | All executable changes confined to dashboard; no scorer executors imported, no pipeline/release writes, no dependency-pin changes. Operator corpus job left running. |

## Corrections

- Backfill identity includes catalog contents, so equal versions/timestamps/counts cannot silently discard different snapshots. Three real older catalogs backfilled locally with pillar-only fidelity.
- Operations now shows provenance and refreshes its cached reader after backfill.
- Peer percentiles and robust outlier checks isolate config fingerprints, including different content under one version.
- Product navigation clears stale search and defers run/plane widget updates to the next initialization. Run Compare defaults remain distinct and follow the globally selected run. Historical runs are selectable.
- Accepted exceptions use each finding's product fingerprint, reopen under changed/unscoped configurations, and cannot inherit another product's scope in a mixed run. Triage widgets isolate selected findings.
- Trace distinguishes unavailable from unearned points; ingredients use filter pushdown and independent index provenance; shared peer context shows its denominator.
- Explorer exposes remaining existing filters and exact Dose/Verification audit views without overwriting saved confidence predicates.
- Config/calibration diff verifies historical bytes against canonical fingerprints; current calibrations and ingredient exports identify their independent source.
- Overview projects only needed columns and counts tiers once per plane.

## Verification and limits

- 98 focused dashboard/guard checks passed, including four dead-code ratchet checks. Fail-first nodes cover history collisions, missing Operations banner, mixed-config peers, stale navigation, scope reopening, unassessed composition, saved-filter overrides and identical Release comparison defaults.
- Browser: all ten pages on Candidate, Release and Historical (30 combinations), zero application exceptions; final browser console reports zero errors/warnings.
- Warm browser timings, three repetitions under an active operator corpus job: Overview 262–335 ms; Explorer 568–784 ms; Trace 410–563 ms; Compare 596–1,117 ms. Each meets the original warm target. First entry can be slower; Market's separate ingredient index is outside those four targets.
- Original full-index source provenance and raw golden qualification are in `acceptance.json`. Local browser logs, 30 screenshots, exact downloads and timing receipts live in this worktree's `output/playwright/`.
- Completed-source whole-fast CI: pending. No local broad suite was run beside the corpus job.
- This batch does not qualify the running corpus, publish a catalog, import app assets, merge/push main, or build an IPA. After the operator rebuild, refresh the full index and inspect its new golden/parity results using the existing owners. No expectations or approvals were fabricated.
