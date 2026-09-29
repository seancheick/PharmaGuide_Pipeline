# C. A→Z pipeline wire (actual symbols at HEAD 391b87c5)

```
RAW  ~/Downloads/PharmaGuide_Datasets/staging/brands/<Brand>/<id>.json  (DSLD label: ingredientRows[].{name,forms[],notes,quantity[],nestedRows[]}, otheringredients, statements[], servingSizes[], physicalState)
 │  run_pipeline.py::PipelineRunner.run_clean → clean_dsld_data.py::DSLDCleaningPipeline → enhanced_normalizer.py::EnhancedDSLDNormalizer.normalize_product
 ▼
CLEAN  activeIngredients[] (raw_source_path, cleaner_row_role ∈ {active_scorable, blend_header_total, nested_display_only, daily_value_no_amount …}, score_eligible_by_cleaner, forms[], notes, quantity/unit(+quantityVariants), dailyValue), inactiveIngredients[], display_ingredients[], label_source_rows[], nutritionalInfo, servingSizes; stage manifest with data+code fingerprints (pipeline_freshness.py, af488ecf)
 │  identity: enhanced_normalizer._resolve_canonical_identity (IQM/botanical/other registries, canonical_equivalences), curated_overrides/product_label_corrections.json applied here
 ▼
ENRICH  enrich_supplements_v3.py::SupplementEnricherV3.enrich_product
   identity stamp   _stamp_iqd_identity (identity_integrity.resolve_identity; canonical_source_db follows the id, 7dbbf677)
   form             _match_quality_map (name → forms[] → row notes via source_form_aliases → branded token → parent re-read 1eab691f) → matched_form/form_id/bio_score/form_source/form_match_status; unknown form: scoring_reference_resolver.unknown_form_quality; disclosed-but-unmapped → held (83f75fe9)
   exposure         serving_frequency.resolve_daily_serving_range → per_day_min/max; RDA adequacy = per_day_min, UL = per_day_max (enricher 21556–21610); typed exposure for fiber/sports in scoring_v4/exposure.py (max directed use)  ← RR-03
   safety           _check_banned_substances (resolver index shared with the gate, 2df4bed2) → contaminant_data; interaction profile _collect_interaction_profile (subjects: identity/interaction.py interaction_subject_refs + BOTANICAL_INTERACTION_TWIN + row safety_flags; presence: label_row_establishes_presence; dose decisions _dose_decision_rule)
   evidence rows    scoring_input_contract.derive_product_scoring_evidence (blend_anchor_mass, declared_active_fiber, sports_primary_dose, omega_epa_dha_aggregate, probiotic_cfu, enzyme_activity)  ← RR-04
   outputs          ingredient_quality_data.{ingredients, ingredients_scorable, ingredients_skipped}, product_scoring_evidence[], rda_ul_data.{adequacy_results, analyzed_ingredients}, probiotic_data, certification_data (cert_resolver), interaction_profile, contaminant_data, serving_basis, nutrition_summary
 ▼
SCORING INPUT  scoring_input_contract.get_scoring_ingredients(strict=True) (rows + rejected_rows), classify_ingredient_roles (primary/claim_prominent/major/adjunct; role_source provenance), route: route_features + class_for_product → v4_module; dose_disclosure_status; epa_dha_amounts_per_serving; _row_unit
 ▼
SCORE  score_products_v4.py::score_all → score_supplements_v4.py::score_product_v4 → _score_v4_core
   gates            gate_safety.evaluate_safety_gate (BLOCKED/UNSAFE; ingredient_assessment_complete ← RR-08), gate_completeness (not_scored: disclosed_form_unmapped, incomplete_product_data …), assessment_readiness (dose/identity/evidence/verification/route readiness)
   modules          generic (generic_formulation A1 parent-relative ← RR-01, botanical_profile ← RR-07; generic_dose; generic_evidence owner-scoped ← RR-05; generic_transparency; generic_trust/cert_evidence; safety_hygiene), sports, fiber_digestive, omega, probiotic, multi_or_prenatal (authority panel evidence), b_complex; every magnitude from scoring_v4/config/quality_score.json (+ data/omega_rubric.json)
   assembler        scoring_v4/quality_score.py::assemble_quality_score → pillars = raw × weight ÷ normalization_references[route] (+ Verification fail_open_neutral), tiers from cfg["tiers"], verdict (POOR = lowest tier); dose_safety.resolve_dose_safety → CAUTION
   artifact         scoring_v4/scored_artifact.py::build_scored_artifact → quality_score_v4_100, quality_score_status (scored/suppressed_safety/not_scored), quality_pillars_v4 (score, max, reason, evidence_result_state, display_state ← RR-11 check), verdict, product_safety_status, quality_assessment_status, quality_tier, v4_module, strict_scoring_contract.findings, provenance (scoring_engine_version 4.4.0, config fingerprints)
 ▼
EXPORT  rebuild_dashboard_snapshot.sh → build_final_db.py::build_final_db → build_core_row (core_export_model.PRODUCTS_CORE_COLUMNS 117 @2.5.0 / APP_CORE_COLUMNS 91 @3.0.0; safe_bool ints) + build_detail_blob (audit_contract_sync.BLOB_TOP_LEVEL 68 keys; ACTIVE_CONTRACT/INACTIVE_CONTRACT row shapes; json_bool) + generate_ingredient_fingerprint / classify_product_categories (key_ingredient_tags) / generate_dosing_summary (serving_basis owner) / _dedup_warnings (one card per plant+hazard+dose state); gates: audit_contract_sync (undeclared keys fail), test_scoring_snapshot_v1, freshness (FRESHNESS_STAGE_INPUT_MISMATCH), citation gates
 ▼
SQLITE / CATALOG  dist/pharmaguide_core.db (products_core, products_fts, export_manifest, reference_data), dist/detail_blobs/<id>.json, dist/detail_index.json, dist/export_manifest.json (db_version, schema_version, scoring_version, quality_score_config_checksum, interaction_db_version, min_app_version); release_full.sh → Supabase + Flutter bundle (assets/db) + interaction DB pin (release_interaction_artifact.py --publish-flutter-pin)
 ▼
FLUTTER  lib/data/database/tables/products_core_table.dart (92 columns) / products_core_projection.dart (generated by generate_flutter_core_projection.py) → core_database.dart; lib/data/supabase/detail_blob_service.dart → detail_blob_provider.dart; lib/core/scoring/v4_pillars.dart, score_tier.dart (quality_tier authoritative, legacy fallback); profile_gate_evaluator.dart (dose/condition gates against the viewer); product_canonical_ids.dart (fingerprint join)
 ▼
UI  hero (score, tier, pillars with display_state), warnings (severity verbs verbatim), ingredients (label_display_name/form, display_badge), interactions/stack
```
Seams verified by probe on 61 labels (D.3); the export→Flutter seam by key greps (H). Not traced in this pass: submission (manual label) path beyond 992a29bf; Supabase sync.
