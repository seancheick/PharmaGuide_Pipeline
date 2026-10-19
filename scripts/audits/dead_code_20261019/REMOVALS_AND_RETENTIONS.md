# Dead-code batch 2 — write-only keys and KEEP review (2026-10-19)

Branch `claude/suspicious-wing-ef56a4`, base `fd51b5828` (after PR #175 and PR #176). Same method
and proof tags as `scripts/audits/dead_code_20261001/REMOVALS_AND_RETENTIONS.md`. Scope: the files no
active lane owned on 2026-10-19. The cleaner (`enhanced_normalizer.py`, `constants.py`), enrichment
(`enrich_supplements_v3.py` and helpers), identity, fail-closed unit/UNII (`unit_converter.py`,
`batch_processor.py`, `unii_cache.py`) and probiotic/studied-formula files wait for those lanes.

`audit_dead_code.py functions`: 16 findings, all in `KEEP`, 0 new. `keys`: 439 keys written once and
named nowhere else (tracked files plus the Flutter `lib/`).

## Removed

| File | Removed | Proof |
|---|---|---|
| `scoring_v4/modules/omega_evidence.py` | metadata `disclosed_epa_dha_clinical_floor_score` (0.0), `disclosed_epa_dha_clinical_floor_threshold_mg_day` (None), `indication_threshold_mg_day` (None) | FIELD. Constants for components `omega_rubric.json` lists under `evidence.retired_fields`; no reader. `disclosed_epa_dha_clinical_floor_awarded` and `indication_relevance_awarded` stay: tests pin them as retirement guards. |
| `scoring_v4/modules/omega.py` | docstring "+ indication_relevance (+5 at AHA CVD dose)" | Stale copy of the retired bonus; now the reviewed-record standard of `omega_rubric.json` `evidence._doc`. |
| `scoring_v4/modules/generic.py` | metadata `production_score_clamped` (always False) | FIELD |
| `scoring_v4/modules/generic_formulation.py` | metadata `deferred_components`, `deferred_penalties` (always []) | FIELD; one test pinned the constant. |
| `build_final_db.py::dedup_by_upc` | parameters `detail_index`, `detail_blobs_dir` (deleted on entry); report counters `upc_groups_deduped`, `duplicates_removed`, `orphan_blob_files_removed` (0), `removed_ids_sample` ([]) | ZERO / FIELD. The audit is non-destructive (its docstring); the release-parity test subtracted the constant 0. Remaining-rows assertions keep the guarantee. |
| `preflight.py` | `results["schema_v4"]`, `summary.schema_v4_ok`, the fallback read | FIELD. Duplicate of `schema_v5`; no reader in scripts, shell, audits or Flutter. |
| `run_pipeline.py` | default `paths.scored_suffix` | FIELD. The scored directory never read it. |

## Write-only keys kept (439 total)

Classified by the file's role. Every scoring, export and ops key was read in context; 8 offline-tool
keys were sampled by hand.

| Count | Class | Why it stays |
|---:|---|---|
| 188 | (a) Offline audit/verification tool output (`api_audit/`, `audit_*.py`, `release_safety/`, `submission_review/`, `reports/`, sweep/backfill/benchmark tools) | Report JSON a person reads, or an API request payload (e.g. `verify_certifications` `forInterest`). |
| 24 | (a) Score audit trail in `_v4_module_breakdown` (`scoring_v4/`) | Computed values that explain a score (counts, raw sums, thresholds actually applied); read through the Product Trace and explain tools. |
| 23 | (a) Run, stage and release reports or manifests (`score_products_v4`, `run_pipeline`, `preflight`, `row_ledger`, `core_export_model`, export audit counts) | Operator-facing summaries. |
| 23 | (a) Dashboard | Plotly layout kwargs (`bgcolor`, `yanchor`) and displayed table columns. |
| 26 | (a) Lookup-table keys | Read by value, never by name (month and Roman-numeral maps, enum maps, sample-ID tables, category maps). |
| 137 | (c) Active-lane files | Re-run after each lane merges. |
| 9 | (c) Shipped detail-blob fields with no reader | Removing a blob field changes shipped output; Sean decides (below). |
| 9 | (b) Removed | Table above. |

### For Sean: blob fields nothing reads (Flutter `lib/` checked)

- `synergy_detail.bonus_awarded`: `build_final_db` maps the best tier to 1.0/0.75/0.5/0.25, but v4
  awards no synergy points (`quality_score.json` Formulation `_doc`: synergy-dose premiums retired;
  no `scoring_v4` module names synergy).
  The blob states a bonus the score does not contain. The app reads `synergy_detail` but not this key.
- `supplement_type_audit.compatibility_mirror_type` duplicates `enriched_type` in the same dict
  (two names for one value); `compatibility_mirror_matches_taxonomy` and `export_type` sit beside
  them. The matrix concept `supplement_type_compatibility_mirror` owns this projection.
- Prenatal `role_evidence` counts (`core_anchor_count`, `complement_anchor_count`,
  `present_adult_multi_anchors`), `claim_non_gmo_present`, `row_ledger_summary.legacy_raw_actives_count`:
  accurate computed values with no reader.

## KEEP review (16 entries)

Every reason still holds; nothing removed. `recency_for`, `resolve_unambiguous`,
`clear_caches`, `validate_normalized_key`, `ungrounded` and `resolve_evidence_for_canonical` (72
test call lines) are test seams onto live state. `catalog_dist_dir` and `final_build_dir` resolve
`PG_RELEASE_CANDIDATE_ROOT` for the release-rung gates. `_combine_preparation_workers` and
`preparation_phase` are pytest hooks the conftest calls. `evaluate_profile_gate`, `applies_to` and
`resolve_warning_rule_refs` are reference implementations the app must match.
`validate_ingredient_context`, `run_development_split` and `release_safety/gates.failure_summary`
wait on an owner decision (wiring, the submission lane, ledger Q41).
`identity_integrity` and `normalization` entries are in active-lane files and were not re-opened.

## Not yet done

`audit_dead_code.py trace` over the full frozen corpus is deferred until the enrichment and cleaner
lanes merge: two corpus replays were already running, and those lanes rewrite the files the trace
would cover.

## Score neutrality

`replay.py snapshot --full --blob --workers 2` (unpinned hash seed), base `fd51b5828` vs candidate
`8644d753a` (runtime equal to `0430ffacb`) on the 2,221-label frozen cohort
`~/pg_quality/clean_fuzzy_20261019/`, then `compare --all-paths`: 2,145 products changed, all in the
scored record and only at the removed paths: `_v4_module_breakdown.metadata.production_score_clamped`
2,145; `dimensions.formulation.metadata.deferred_components` and `deferred_penalties` 1,704 each;
`dimensions.evidence.metadata.disclosed_epa_dha_clinical_floor_score`,
`disclosed_epa_dha_clinical_floor_threshold_mg_day` and `indication_threshold_mg_day` 104 each.
Cleaned, enriched and detail-blob records: 0 changed. Receipts: `~/pg_quality/dead_code_sweep_20261019/`.
Whole-fast CI `pipeline-tests` 39334007387 passed on `8644d753a`; this note is documentation only.
