# Removals, restorations and retained aliases — closure 2026-09-21

Companion to `FINAL_CLOSURE_AUDIT_20260921.md` §2 #14–16. Lists are generated from
`git diff HEAD` (functions absent now that existed at `d70fd740`) and from the
edit scripts that removed dead reads. Nothing here was removed because a static
grep or pyflakes said so; every removal carries one of the proof categories
below.

## Proof categories

| Tag | Proof required | Tooling |
|---|---|---|
| **ZERO** | No reference from any production module, test, script, shell file or config — iterated to a fixpoint, so helpers of removed helpers were re-checked — and not reachable through a decorator, registry, `getattr` string or CLI entry point | zero-reference scanner (AST names + string literals across `scripts/`, `*.sh`, config JSON) |
| **TRACE** | A full-corpus runtime trace shows the code never executes on real input, and no dynamic hook can reach it | `sys.monitoring` line trace of `build_scored_artifact` over the corpus |
| **FIELD** | The key it reads appears in no artifact of any layer (raw, cleaned, enriched, scored, detail blob) for 15,421 products, and nothing writes it | key census across all five layers |
| **SUPERSEDED** | A live canonical owner does the same job; no external contract (DB, app, public schema) depends on the old path | owner named per row |
| **RETARGETED** | Only tests called it. Each test's behavioral guarantee was re-pinned on the live owner first; a test that pinned only the dead function was deleted with it | tests named in §2 #15 of the report |

Deliberate fail-closed safety mechanisms were **never** removed on corpus
absence alone (see "Kept on proof of life" below).

## Functions and classes removed (110)

| File | Removed | Proof |
|---|---|---|
| `api_audit/cert_audit_report.py` | `_load_claimed_certs` | ZERO |
| `api_audit/fda_manufacturer_violations_sync.py` | `is_supplement_record` | ZERO |
| `api_audit/verify_clinical_trials.py` | `search_studies` | ZERO |
| `api_audit/verify_comptox.py` | `get_chemical_details`, `get_skin_eye` | ZERO |
| `audit_evidence_utils.py` | `_as_float` | ZERO (only caller was the removed V3 omega bonus field) |
| `audit_source_of_truth_contract.py` | `_cap_adjusted_public_total` | SUPERSEDED — post-sum cap removed (decision A); validator requires the literal sum |
| `audit_source_of_truth_contract.py` | `iqd_count` | ZERO |
| `audits/.../measure_phase1a_impact.py`, `batch_pl_gapfill/backfill.py`, `phase_1_5/_pubmed_search2.py`, `quarantine_triage_20260919/full_corpus_replay.py` | `score_evidence_baseline`, `set_if_diff`, `absx`, `signature_from_stored` | ZERO (inside one-off audit scripts) |
| `build_final_db.py` | `backfill_image_thumbnails`, `blob_has_safety_blocking_warning`, `index_by_id` | ZERO |
| `build_final_db.py` | `load_other_ingredients_index`, `resolve_other_ingredient_reference`, `profile_gated_hard_safety_signal` | RETARGETED — a second other-ingredient lookup beside `InactiveIngredientResolver`; label-descriptor test intents re-pinned on the resolver |
| `cleanup_old_versions.py` | `delete_storage_path` | ZERO |
| `db_integrity_sanity_check.py` | `check_percentile_categories` | SUPERSEDED — `percentile_categories.json` was loaded and never read; file retired |
| `enhanced_normalizer.py` | `_check_orphaned_data`, `_extract_ingredient_features`, `_generate_integrity_statistics`, `_load_context_canonical_overrides`, `_process_ingredients_parallel` (+ nested `safe_order_key`, `add_unii_payload`), `_validate_cross_references`, `_validate_data_consistency`, `_validate_required_fields`, `get_cache_stats`, `get_enhanced_unmapped_summary`, `validate_database_integrity` | ZERO |
| `enhanced_normalizer.py` | `_check_banned_recalled` | RETARGETED — the Cleaner's copy of ban detection; ephedra/DMAA/vacha/7-keto intents re-pinned on the enricher owner `_check_banned_substances` |
| `enhanced_normalizer.py` | `_extract_nutritional_amount` | RETARGETED — only a slow-tier case in `test_pipeline_regressions.py` called it; the case pinned only the dead function and was removed with it |
| `enrich_supplements_v3.py` | `_strain_match` | RETARGETED — infantis strain-code intent re-pinned on `studied_formulas.clinical_strain_identity_matches` |
| `enrich_supplements_v3.py` | `get_unmapped_forms_report` | ZERO |
| `enrichment_contract_validator.py` | `get_summary`, `log_violations`, `validate_enriched_product` | ZERO / RETARGETED (test-only wrappers of the live per-rule checks) |
| `evidence_resolver.py` | `run_resolver_shadow_audit` (+ `__main__`) | SUPERSEDED — Phase-5 shadow A/B tool, retired after the final A/B |
| `form_vocab.py` | `canonicals_in`, `category_ids` | ZERO |
| `functional_grouping_handler.py` | `score_transparency_for_enrichment` | ZERO |
| `identity/safety.py` | `classify_safety`, `build_safety_exact_index` | RETARGETED — duplicate classifier beside the live resolver path; live-owner test `test_live_banned_owner_catches_names_aliases_and_case` |
| `inactive_ingredient_resolver.py` | `iter_clean_label_policy_entries_for_audit`, `iter_harmful_additives_entries_for_audit`, `iter_other_ingredients_entries_for_audit` | ZERO / RETARGETED (test-only iterators) |
| `ingest_suppai.py` | `build_rxcui_to_cui_crosswalk` | ZERO |
| `scoring_input_contract.py` | `_recoverable_nested_identity`, `_has_omega_identity_text` | TRACE — skipped-row "recovery" block never executes on fresh artifacts; C1 full corpus 0 movers |
| `scoring_input_contract.py` | `_route_number`, `_route_positive_number` | ZERO |
| `scoring_v4/config_registry.py` | `registered_rubrics` | ZERO |
| `scoring_v4/modules/b_complex.py`, `generic_dose.py`, `multi_prenatal_dose.py` | `_b7_dose_safety`, `_penalty_b7_dose_safety` | RETARGETED — one `evaluate_dose_safety` call in `score_supplements_v4` applies B7 to every module; parity tests now use the shared evaluation |
| `scoring_v4/modules/generic_evidence.py` | `has_verified_ingredient_human_evidence_for_row` | ZERO |
| `scoring_v4/modules/generic_formulation.py` | `_penalty_b1_harmful_additives` | RETARGETED — thin wrapper; `test_v4_additive_points_config` now pins the live `_b1_harmful_additive_penalty_detail` |
| `scoring_v4/modules/generic_formulation.py` | `_penalty_dietary_sugar` | ZERO |
| `scoring_v4/modules/generic_helpers.py` | `is_single_scorable_active_of` | RETARGETED |
| `scoring_v4/modules/generic_transparency.py` | `_score_b2_allergen_penalty` | ZERO |
| `scoring_v4/modules/omega_dose.py` | `_as_float`, `_safe_dict` | ZERO after the `omega3_detail` fallback (FIELD) was removed |
| `scoring_v4/modules/omega_evidence.py` | `_compute_per_day_epa_dha` | ZERO |
| `scoring_v4/modules/sleep_support.py` | `has_sleep_active` | ZERO |
| `scoring_v4/modules/sports_helpers.py`, `scoring_v4/quality_score.py` | `sports_public_quality_cap`, `_public_quality_cap` | SUPERSEDED — behavior decision A (literal pillar sum); 34 capped products measured |
| `scoring_v4/scored_artifact.py` | `suppress_scored_artifact_for_hard_block` | RETARGETED |
| `unii_cache.py` | `resolve_all_form_uniis` | ZERO |

Files deleted: `audits/run_phase5_production_ab.py` (SUPERSEDED — A/B done),
`audits/supptype_drift_preview.py` + its 2 tests (SUPERSEDED — temporary
consolidation harness), `dashboard/components/score_trace.py` (SUPERSEDED — it
rendered V3 section math V4 never emits), `data/percentile_categories.json` + 2
tests (SUPERSEDED), `tests/shadow_diff_snapshots.py` (SUPERSEDED — V3 shadow),
`tests/test_blend_header_member_dedup.py` and `tests/test_scorer_dedup_audit.py`
(SUPERSEDED — their corpus scans read the V3 `breakdown.A` / `A2` sections
V4 never emits, so they could only skip or pass vacuously; the remaining case
grepped enricher source text and pointed at `test_b7_ul_aggregation.py`, the
behavioral UL-summing suite, which stays).

## Dead field reads removed (FIELD unless noted)

| File | Keys no longer read |
|---|---|
| `assessment_readiness.py` | `activity_value` (misnamed; now reads the real `activity_quantity`), `probiotic_detail` (blob-shape fallback on an enriched-product path) |
| `build_final_db.py` | `label_text`, `search_text`, `supp_type`, `organic`/`verification_status` (organic verification), `is_in_proprietary_blend`, `ingredient_canonical`, `source_rule`, synergy `clusters`/`cluster_id`/`clusters_matched` category branch |
| `enhanced_normalizer.py` | DV "serving context" block: `servingSizeQuantity`, `servingSizeUnitOfMeasure`, `serving_size_*`, `targetGroup`, `context` |
| `enrich_supplements_v3.py` | `activity_value`, `daily_value_percent`, `percent_dv`, `db_id`, `deliveryForm` text, `dosage`, `dosage_unit`, `dsldId`, `productId`, `productName`, `isProprietaryBlend` (×6), `min/maxServingsPerDay`, `min/max_daily_servings`, `servingSizeUnitOfMeasure`, `net_contents`, `rawName`, `common_allergens` |
| `enrich_supplements_v3.py` (rewired, not removed) | match-ledger allergens domain read `compliance_data.allergens_detected` (never populated) → now `allergen_hits`; delivery domain read `matched_systems` → now `delivery_data.systems`. Both domains were empty on every product; now filled on 126/126 and 82/82 sampled products |
| `evidence_resolver.py` | `rda_or_ai`, `min_clinical_mg`, `max_clinical_mg` provenance copies |
| `probiotic_measurements.py`, `supplement_taxonomy.py` | `iqm_parent_key`, `quantityUnit`, `qty`, `probiotic_detail` |
| `scoring_input_contract.py` | `activity_value`, `dailyValueTargetGroup`, `percent`, `display_label`, `form_aliases`, `parent_key`, `items`, `active_ingredients`, product-level `evidence` dict branch |
| `scoring_v4/gate_completeness.py` | `activity_value`, `dailyValueTargetGroup`, `ingredient_id`, `matched_id`, `percent` |
| `scoring_v4/gate_safety.py` | `disclosure`, `raw_name` |
| `scoring_v4/confidence.py`, `route_features.py`, `generic_formulation.py`, `prebiotic_catalog.py` | `form_factor_source`, `dsldId`, `match_basis`, `is_blend` |
| `scoring_v4/modules/generic_evidence.py` | `full_name`, `max_clinical_dose`, `max_studied_dose` (live key is `max_studied_clinical_dose`) |
| `scoring_v4/modules/multi_prenatal_transparency.py`, `probiotic_dose.py`, `fiber_digestive_helpers.py` | `disclosure_status`, `mapped_parent`, `parent_key`, `cleaner_role`, `role`, `scoring_input_kind`, `is_blend`, `is_in_proprietary_blend`, `dosage`, `dosage_unit` |
| `serving_frequency.py` | `min/max_daily_servings`, `servingSizeQuantity`, `servingSizeUnit` |
| `studied_formulas.py` | `population`, `target_population`, `age_group` |
| `audit_evidence_utils.py` | `claim_non_gmo_project_verified` |

Blob / artifact fields removed: `section_breakdown`, `omega3_detail`,
`a_sub`, `gate_audit.probiotic_eligibility`, the nested `audit.*` duplicate of
every `*_audit`, the V3-derived omega-3 bonus and blend-penalty audit fields,
`quality_score_cap_v4`, the scored-artifact `_v4_*` overlay,
`scoring_status` and repeated `scoring_metadata` facts (report §4), and the
enriched `percentile_category_label/_source/_confidence/_signals` copies (no
reader in pipeline, dashboard or app; the label ships from the scored artifact
via `percentile_label_for`).

Score neutrality of all of the above: C1 full corpus B1→C1 0 movers (pillars,
totals, status, assessment, verdict, evidence/display state, tier, rules);
fresh raw→clean→enrich→score sample of 395 products on the final code: 0 movers.

## Kept on proof of life ("looked dead, is live")

| Item | Why it looked dead | Why it stays |
|---|---|---|
| `scoring_input_contract` `allow_legacy_fallback` | no caller passes it in most modules | `gate_safety` passes `True`; the corpus trace executes it |
| `identity/safety.py` legacy top-level flags + `recall_status` / `matched_source` aliases | absent from current artifacts | fail-closed quarantine for legacy-shaped safety records; removing them broke the quarantine tests |
| 30 `# noqa: F401` imports (`env_loader` side effects, re-exports incl. `dsld_api_client`) | pyflakes-unused | side-effect imports and public re-exports; restored from HEAD |
| `SCORING_ENGINE_VERSION` in `scored_artifact` | unused-import sweep removed it | read at runtime (249 failures); now imported from its owner `score_supplements_v4` |
| `evidence_resolver._as_float` | looked orphaned in one hunk | used earlier in the file |
| blob-shape goal path in `build_final_db` | no pipeline caller | audit tooling passes detail blobs |
| `generic_trust` / `omega_trust` | no static import | lazy imports |
| `is_blocked` strains, stale-cert `scoring_blocked_reason`, policy holds, schema-2.x `migration_inference` quarantine | no current corpus product triggers them | data-driven fail-closed guards |
| share-index output key `productName` | same spelling as a dead input alias | it is the share index's own published JSON key (`sync_to_supabase.py`) |

## Retained external compatibility aliases (one-way; none writes back)

| Canonical owner | → one-way alias | → external consumer |
|---|---|---|
| `quality_score_v4_100` (`quality_score.py`, literal pillar sum) | `score_100_equivalent`, `display_100` | core DB columns read by the app and Supabase sync |
| `quality_tier` (from the shipped whole number) | `grade` | core DB column (app fallback) |
| `quality_score_confidence` | `v4_confidence` | core DB column (app fallback) |
| — (V3 retired) | 2.5.0 V3 section columns `score_ingredient_quality*`, … | published 2.5.0 SQLite schema; always NULL by contract, deprecated compatibility, not a live scoring field; schema 3 drops them. Nothing is fabricated to populate them |

## Round 2 (2026-09-22) removals

| Removed | Why it had to go | Proof |
|---|---|---|
| `router.class_for_product` `except Exception: return "generic"` and its unknown-route fallback | a classifier defect silently scored the product on the generic route | the classifier returns `generic` on its own for every malformed shape probed (`{}`, null name, null rows); routing slice 2,090 passed |
| enricher silent fallback around `build_scoring_classification` | same failure mode at enrich time | enrich path now raises; fast suite green |
| `SUB_CLINICAL_DOSE_GUARD_MULTIPLIER` + config `sub_clinical_dose_guard_multiplier` | Evidence was a second Dose owner (D5) | 119 attributed movers; config fingerprint history `1.13.0-dose-applicability-gate` |
| legacy `cfu_thresholds.evidence` summaries on BS01, LP01, M-63, the four DS-01 members | agent-authored second owners (LP01's cited a combination as strain-specific; DS-01's duplicated `FORMULA_SEED_DS01`) | D1 applier asserts each block existed and was replaced by contexts, a conclusion, or the formula owner |
| `pectinase`, `hemicellulase`, `xylanase`, `beta-glucanase` aliases under `cellulase`; `pectinase enzyme` under `digestive_enzymes` | a different enzyme under cellulase's CUI; one identity with two owners | 183 affected labels, 0 movers |
