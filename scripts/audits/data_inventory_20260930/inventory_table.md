| File | Status | Pipeline readers (first 3) | App copy | Purpose / note |
|---|---|---|---|---|
| `absorption_enhancers.json` | PIPELINE | batch_processor.py, build_final_db.py, clean_dsld_data.py (+cfg) |  | Absorption enhancers that improve nutrient bioavailability |
| `allergen_prevalence_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
| `allergen_regulatory_status_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `allergens.json` | PIPELINE | api_audit/fda_weekly_sync.py, build_final_db.py, clean_dsld_data.py (+cfg) |  | Regulatory allergen identification database for supplement ingredients. Covers FDA major allergens (9) and EU Annex II allergens (8). Used for consumer warnings and on-de |
| `backed_clinical_studies.json` | PIPELINE | api_audit/normalize_clinical_pubmed.py, build_final_db.py, clinical_applicability.py (+cfg) |  | Ingredients backed by clinical research and studies - Enhanced for Section C v3.4.0 |
| `backed_studies_ghost_review.json` | GATE |  |  | Reviewed GHOST-SUSPECT findings from verify_backed_studies_citations.py --strict. A suspect blocks the release gate until it is reviewed here with a rationale that states |
| `ban_context_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `banned_match_allowlist.json` | PIPELINE | enrich_supplements_v3.py (+cfg) |  | Allowlist/denylist for banned ingredient matching overrides |
| `banned_recalled_ingredients.json` | PIPELINE | api_audit/fda_weekly_sync.py, api_audit/verify_cui.py, api_audit/verify_interactions.py (+cfg) | yes | Banned and recalled ingredients database for regulatory compliance and safety (v3.0) |
| `banned_status_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `botanical_ingredients.json` | PIPELINE | api_audit/verify_interactions.py, batch_processor.py, clean_dsld_data.py (+cfg) |  | Non-standardized whole herb powders and simple botanical extracts without guaranteed marker compounds. Used for basic ingredient mapping. For premium standardized extract |
| `botanical_marker_contributions.json` | PIPELINE | build_final_db.py, enrich_supplements_v3.py (+cfg) |  | Maps source-botanical canonicals to the bioactivity markers they may deliver. Used by enricher to compute delivers_markers[] per ingredient when label declares standardiz |
| `branded_blend_anchor_overrides.json` | ORPHANED |  |  | reader lived in v3 `score_supplements.py` (added 7c42c4767), deleted with v3 in 211486211; v4 never ported it |
| `caers_adverse_event_signals.json` | DORMANT |  |  | B8 scoring gated off pending PRR/ROR thresholds (V1.1 ROADMAP §5.1); dashboard + ingest only |
| `canary_products.json` | GATE |  |  | Curated 35-product v4 canary set spanning 14 primary classes (single_nutrient, multivitamin, prenatal_multi, probiotic, fish_oil, herbal_branded_extract / unstandardized  |
| `canonical_equivalences.json` | PIPELINE | constants.py, enhanced_normalizer.py, enrich_supplements_v3.py |  | Reviewed identity equivalences and specificity relationships across pipeline registries. |
| `catalog_brand_registry.json` | PIPELINE | build_final_db.py |  | Exact source-brand aliases for consumer catalog display. Raw source identity remains immutable. |
| `cert_claim_rules.json` | PIPELINE | constants.py, enrich_supplements_v3.py, enrichment_contract_validator.py (+cfg) |  | Versioned rules for certification/claim detection with evidence-based scoring eligibility |
| `cert_registry.json` | PIPELINE | cert_resolver.py |  | Cached snapshots of public third-party certification registries. |
| `citation_content_backlog.json` | GATE |  |  | Citations the first full-coverage run (2026-09-26) flagged: 'mismatch' means the live PubMed record shares no identity word with its entry (a heuristic; many are wrong pa |
| `clean_label_policy.json` | PIPELINE | inactive_ingredient_resolver.py, scoring_v4/quality_score.py |  | Jurisdiction-explicit clean-label preferences kept separate from legal safety verdicts. |
| `clinical_indication_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `clinical_risk_taxonomy.json` | PIPELINE | build_final_db.py, enrich_supplements_v3.py, sync_flutter_reference_data.py (+cfg) | yes | Controlled clinical risk taxonomy for condition and medication-class interaction alerts |
| `clinical_risk_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `clinically_relevant_strains.json` | PIPELINE | constants.py, enhanced_normalizer.py, enrich_supplements_v3.py (+cfg) |  | Clinically relevant probiotic strains and prebiotic compounds |
| `cluster_ingredient_aliases.json` | PIPELINE | enrich_supplements_v3.py | yes | Canonical-form ingredient aliases for synergy cluster matching. Each canonical form maps to the variant strings that supplement labels use in the wild. Used by enrich_sup |
| `color_indicators.json` | PIPELINE | clean_dsld_data.py, constants.py, enhanced_normalizer.py (+cfg) |  | Context-aware indicators for distinguishing natural vs artificial colors in supplement ingredient mapping |
| `confidence_tier_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `cross_db_overlap_allowlist.json` | GATE |  |  | Explicitly allowed normalized term overlaps across routing databases. Any new overlap must be reviewed before scoring deployment. |
| `curated_interactions/batch_critical_2026_05.json` | PIPELINE |  |  | interaction DB via the same curated_interactions directory glob |
| `curated_interactions/curated_interactions_v1.json` | PIPELINE | audit_source_of_truth_contract.py, build_interaction_db.py |  | Tier 1 curated drug-supplement and supplement-supplement interactions for the interaction database |
| `curated_interactions/med_med_pairs_v1.json` | PIPELINE | audit_source_of_truth_contract.py |  | interaction DB via `rebuild_interaction_db.sh` → `verify_interactions.py --drafts scripts/data/curated_interactions` (directory glob) |
| `curated_overrides/cert_verification_overrides.json` | PIPELINE | cert_resolver.py |  | Manual overrides for cert verification scope. Used when (a) the fuzzy resolver returns needs_review and a human confirms/downgrades, or (b) a known-good cert isn't in the |
| `curated_overrides/cui_overrides.json` | PIPELINE | api_audit/verify_cui.py |  |  |
| `curated_overrides/gsrs_policies.json` | GATE |  |  |  |
| `curated_overrides/product_context_canonical_overrides.json` | PIPELINE | constants.py, enhanced_normalizer.py, enrich_supplements_v3.py |  | Reviewer-signed per-product canonical_id + IQM form overrides for DSLD rows where the row text alone is ambiguous but the surrounding product-name context disambiguates t |
| `curated_overrides/product_label_corrections.json` | PIPELINE | constants.py, enhanced_normalizer.py |  | Reviewer-signed corrections for DSLD product rows where label text, a source identifier, or a quantity value/unit contains a verified transcription or attribution defect. |
| `curated_overrides/pubchem_policies.json` | GATE |  |  |  |
| `curated_overrides/upc_overrides.json` | PIPELINE | build_final_db.py |  | Manually curated UPC overrides for DSLD products missing barcode data |
| `daily_values.json` | PIPELINE | enhanced_normalizer.py |  | FDA labeling Daily Values used for Supplement Facts %DV cross-checks |
| `drug_class_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `drug_classes.json` | PIPELINE | api_audit/verify_interactions.py, audit_source_of_truth_contract.py, build_interaction_db.py |  | Drug class expansion map for interaction matching (class:X → RxCUIs) |
| `effect_direction_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `efsa_genotoxicity_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
| `efsa_openfoodtox_reference.json` | GATE |  |  | Curated EFSA OpenFoodTox reference data for harmful additive validation |
| `efsa_status_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
| `enhanced_delivery.json` | PIPELINE | batch_processor.py, constants.py, enhanced_normalizer.py (+cfg) |  | Tiered enhanced delivery systems for bioavailability scoring |
| `evidence_level_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `evidence_strength_vocab.json` | PIPELINE | api_audit/verify_interactions.py | yes | Controlled vocabulary for the 6 qualitative evidence-strength tiers used by ingredient_interaction_rules evidence_level fields. This is intentionally separate from eviden |
| `fda_caers/food-event-0001-of-0001.json` | RAW-INPUT |  |  | untracked openFDA dump for `api_audit/ingest_caers.py` |
| `fda_drug_labels/drug-label-0001-of-0013.json` | RAW-INPUT |  |  | untracked openFDA dumps (3 of 13 parts) for `api_audit/mine_drug_label_interactions.py` |
| `fda_unii_cache.json` | GATE |  |  | untracked offline UNII registry for verifiers/`data_batch` |
| `form_factor_vocab.json` | PIPELINE | form_factor_normalizer.py | yes | Canonical form-factor vocabulary for product physical state. 18 canonical IDs covering DSLD physicalState.langualCodeDescription values and common label variants. |
| `form_keywords_vocab.json` | PIPELINE | enhanced_normalizer.py, enrich_supplements_v3.py, evidence_resolver.py |  | Controlled vocabulary for ingredient FORM KEYWORDS extracted from raw label text. Single source of truth for the cleaner (extracts forms from ingredient names), the score |
| `functional_ingredient_groupings.json` | PIPELINE | constants.py, functional_grouping_handler.py |  | Functional ingredient grouping patterns and transparency scoring for supplement labeling |
| `functional_roles_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `harmful_additives.json` | PIPELINE | api_audit/verify_cui.py, api_audit/verify_interactions.py, batch_processor.py (+cfg) |  | Comprehensive database of harmful additives, contaminants, and concerning ingredients found in dietary supplements. Used for scoring penalties and consumer warnings. |
| `high_dose_rule_exemptions.json` | GATE |  |  | Explicit reviewed exemptions for active pairwise interaction rules that must remain visible without a numeric high-dose threshold. |
| `id_redirects.json` | GATE |  |  | Redirects deprecated IDs to canonical IDs in banned_recalled_ingredients.json |
| `ingredient_category_vocab.json` | PIPELINE | ingredient_category_normalizer.py, supplement_type_utils.py | yes | Canonical line-level ingredient category vocabulary for classifying what an ingredient row IS (vitamin / mineral / botanical / amino acid / etc.) — distinct from form (ca |
| `ingredient_classification.json` | PIPELINE | batch_processor.py, clean_dsld_data.py, constants.py |  | Ingredient classification rules for active/inactive categorization |
| `ingredient_interaction_rules.json` | PIPELINE | audit_source_of_truth_contract.py, build_final_db.py, build_interaction_db.py (+cfg) |  | Deterministic ingredient-level interaction rules keyed by canonical database identity |
| `ingredient_quality_map.json` | PIPELINE | api_audit/verify_cui.py, api_audit/verify_interactions.py, batch_processor.py (+cfg) |  | Comprehensive quality mapping database for active dietary supplement ingredients. Form quality is bio_score alone. |
| `ingredient_weights.json` | DEAD | constants.py (+cfg) |  | `constants.INGREDIENT_WEIGHTS` defined in the first commit, never used; enricher loads it by config and never reads it |
| `interaction_orphan_allowlist.json` | PIPELINE | audit_source_of_truth_contract.py |  | Allowlist of supplement canonical_ids tolerated as referential orphans in the interaction pipeline. Each entry covers a pairwise interaction surfaced in interaction_db.sq |
| `interaction_rules_ghost_review.json` | GATE |  |  | Reviewed GHOST-SUSPECT findings from verify_interaction_rules_citations.py --strict, keyed by PMID, rule_id and sub_rule. A suspect blocks the strict gate until it is rev |
| `iqm_category_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `iqm_excellent_evidence_backlog.json` | PIPELINE | iqm_form_evidence.py |  | Frozen governance ledger for pre-existing curated Excellent IQM forms. remaining_forms are permitted legacy scores whose supporting form evidence has not been source-veri |
| `legal_status_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `literature_evidence_records.json` | PIPELINE | evidence_resolver.py |  | Phase 4 shadow literature resolution registry for high-impact canonical actives |
| `manufacture_deduction_expl.json` | MAINTENANCE |  |  | live maintenance input: `api_audit/fda_manufacturer_violations_sync.py::recalculate_all_entries` applies it; stored deductions need periodic re-aging (see F3) |
| `manufacturer_trust_tier_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
| `manufacturer_violations.json` | PIPELINE | enrich_supplements_v3.py, scoring_v4/modules/b_complex.py, scoring_v4/modules/fiber_digestive.py (+cfg) |  | Manufacturer FDA violations and recall history |
| `match_mode_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `medication_depletion_citation_expectations.json` | GATE |  |  | Reviewed PubMed content expectations for every active verified medication-depletion claim plus suppressed delta candidates. |
| `medication_depletions.json` | PIPELINE | build_medication_depletions_artifact.py, sync_flutter_reference_data.py | yes | Medication-nutrient effects — true depletions, functional antagonism, monitoring notes, condition-related effects, and supplement interactions |
| `medication_depletions_b1_1_signoff.json` | TEST-LEDGER |  |  | machine-enforced sign-off fingerprints, enforced by tests |
| `medication_depletions_b1_delta_signoff.json` | TEST-LEDGER |  |  | machine-enforced sign-off fingerprints, enforced by tests |
| `medication_depletions_b1_signoff.json` | TEST-LEDGER |  |  | machine-enforced sign-off fingerprints, enforced by tests |
| `medication_profile_gate_rules.json` | PIPELINE | build_final_db.py (+cfg) | yes | Standalone medication profile-gate rules for stack medications. Rules use the same v6.0 profile_gate schema as ingredient interaction warnings, but the product context is |
| `migration_report.json` | GATE |  |  | Migration report from schema upgrades |
| `omega_rubric.json` | PIPELINE | scoring_v4/config_registry.py, scoring_v4/config_schema.py, scoring_v4/gate_completeness.py |  | P1.6 omega/fish-oil rubric. Reviewed purpose evidence is resolved from INGR_OMEGA3 through evidence_resolver against the shared directed daily-exposure interval; the 250  |
| `other_ingredients.json` | PIPELINE | api_audit/verify_interactions.py, batch_processor.py, build_final_db.py (+cfg) |  | Other/inactive ingredients database for supplement excipients and additives |
| `primary_outcome_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
| `product_type_vocab.json` | PIPELINE | supplement_taxonomy.py, sync_flutter_reference_data.py | yes | Controlled vocabulary for the 22 canonical supplement product types. Single source of truth shared between pipeline (supplement_taxonomy.py) and Flutter app (product_type |
| `production_assessable_actives.json` | AUDIT-ARTIFACT |  |  | output of `scripts/audits/build_production_assessable_actives.py`; nothing reads it |
| `profile_gate_test_cases.json` | GATE |  |  | Shared evaluator fixture for v6.0 profile_gate. Python (scripts/profile_gate_evaluator.py) and Dart (Flutter alert-rendering layer) MUST both produce the same fires/sever |
| `proprietary_blends.json` | PIPELINE | batch_processor.py, clean_dsld_data.py, constants.py (+cfg) |  | Proprietary blend recognition database for supplement label mapping |
| `rda_optimal_uls.json` | PIPELINE | build_final_db.py, constants.py, enhanced_normalizer.py (+cfg) | yes | RDA (Recommended Dietary Allowance), optimal dosing, and UL (Upper Limit) reference values for nutrient dosing validation |
| `rda_therapeutic_dosing.json` | PIPELINE | collagen_taxonomy.py, constants.py, evidence_resolver.py (+cfg) |  | Therapeutic dosing ranges for clinical efficacy validation |
| `safety_alerts/_TEMPLATE.json` | TEMPLATE |  |  | authoring template; `build_safety_alerts.py` reads `SA_*.json` only (none present) |
| `score_contribution_tier_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `severity_vocab.json` | PIPELINE | audit_source_of_truth_contract.py | yes | Controlled vocabulary for the 7 severity tiers used across interaction rules, harmful-additive flags, allergen warnings, and the clinical-risk taxonomy. Carries the full  |
| `signal_strength_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
| `standardized_botanicals.json` | PIPELINE | batch_processor.py, build_final_db.py, clean_dsld_data.py (+cfg) |  | Bonus-eligible standardized-extract registry. NOT a botanical identity file — identity lives in botanical_ingredients.json. |
| `study_type_vocab.json` | GATE |  | yes | validation vocab (db_integrity); app bundles a copy |
| `synergy_cluster.json` | PIPELINE | build_final_db.py, constants.py, enrich_supplements_v3.py (+cfg) | yes | Ingredient synergy clusters for bonus scoring when complementary ingredients are combined |
| `timing_rules.json` | PIPELINE | sync_flutter_reference_data.py | yes | Supplement timing and absorption interaction rules for optimal nutrient uptake |
| `timing_rules_rejected.json` | GATE |  |  | Clinical rejection ledger for timing rules. |
| `top_manufacturers_data.json` | PIPELINE | constants.py, enrich_supplements_v3.py, scoring_v4/modules/brand_testing_posture.py (+cfg) |  | Top supplement manufacturers with quality ratings and certifications |
| `unii_exoneration_allowlist.json` | PIPELINE | enhanced_normalizer.py |  | Explicit exoneration allowlist for SAME_UNII_DIFFERENT_NAMES audit findings. Each entry documents a UNII that maps to multiple reference entries which are legitimately th |
| `unit_conversions.json` | PIPELINE | constants.py, enrich_supplements_v3.py, scoring_v4/modules/multi_prenatal_dose.py (+cfg) |  | Unit conversion factors for supplement dosing normalization |
| `unit_mappings.json` | DEAD | constants.py |  | `constants.UNIT_MAPPINGS` defined in the first commit, never used; holds assumed default strengths per form (unsafe if ever wired) |
| `user_goals_to_clusters.json` | PIPELINE | build_final_db.py (+cfg) | yes | User goal to product-cluster matching rules (pipeline-owned matching contract) |
| `user_goals_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
| `verdict_vocab.json` | APP-VOCAB |  | yes | no pipeline reader; the app bundles a manual copy |
