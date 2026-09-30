# scripts/data inventory — what each file does, who reads it, what is orphaned (2026-09-30)

Scope: every file under `scripts/data/` (169 on disk: 108 JSON, 53 Markdown, 4 zip, 2
`.DS_Store`, 2 `.gitkeep`; 158 tracked). Untracked: the openFDA raw dumps (`fda_caers/`,
`fda_drug_labels/`, ~2.5 GB) and `fda_unii_cache.json`. Full per-file table:
[`inventory_table.md`](inventory_table.md).

## Method (reproducible)

1. Inventory + `_metadata` (description, schema version, counts, top-level keys) of every JSON.
2. Consumers: `git grep` of each basename and bare stem across the repo, bucketed
   production / config+shell / audit+verify / tests / docs; `rg` of the stem in the Flutter repo.
3. Reachability: transitive `import` graph (AST, lazy imports included) from the real entry
   points — pipeline (`run_pipeline`, `clean_dsld_data`, `enrich_supplements_v3`,
   `score_products_v4`, `build_final_db`, `build_all_final_dbs`, `release_catalog_artifact`,
   `sync_to_supabase`, `build_interaction_db`, `release_interaction_artifact`,
   `sync_flutter_reference_data`, `build_safety_alerts`, `sync_safety_alerts`,
   `fda_weekly_sync`, `product_submission_import`, `promote_release_artifacts`,
   `ingest_suppai`, `extract_product_images`) reaches 158 modules; release gates
   (`audit_source_of_truth_contract`, `audit_contract_sync`, `preflight`,
   `db_integrity_sanity_check`, `verify_*`, …) add 28. A file is PIPELINE when a reachable
   module or a config read by one names it.
4. Manual verification of every non-PIPELINE file: directory globs, the enricher's
   `enrichment_config.json` database map (loaded ≠ read), constants actually used, git
   history of removed readers, the retired v3 scorer (`score_supplements.py`, deleted
   211486211), and the app's bundled copies.

## Status counts (verified)

106 JSON rows (the 3 drug-label parts share one row): PIPELINE 56 · GATE (validation or
verification input only) 30 · MAINTENANCE 1 (read by a sync tool) · APP-VOCAB 8 · TEST-LEDGER 3 · DORMANT 1 · TEMPLATE 1 ·
RAW-INPUT 2 (4 files) · AUDIT-ARTIFACT 1 · DEAD 2 · ORPHANED 1.
Markdown: `views/` (47 generated clinician views), `METADATA_CONTRACT_EXEMPTIONS.md`,
`safety_alerts/README.md`. `_archive/` holds only empty dirs + `.DS_Store`.

## Findings

Corrected 2026-09-30 after [`INDEPENDENT_REVIEW.md`](INDEPENDENT_REVIEW.md) (each correction reproduced): F2, F3 rewritten; the generic no-reference Dose credit is 16/12 **raw** points on a 22-point cap (≈14.5/20 and 10.9/20), not 16/20; `INGR_ZINC_PICOLINATE` is zinc acetate/gluconate lozenges, 80–207 mg/day, acute adult cold (never migrate by the legacy ID).


| # | Finding | Evidence | Impact | Action |
|---|---|---|---|---|
| F1 | `branded_blend_anchor_overrides.json` ORPHANED: 5 PubMed-verified branded blend headers (Urox, Xanthigen, Metabolaid, Univestin, …) cleared for blend-header anchoring; the reader was in v3 `score_supplements.py` (7c42c4767), deleted with v3 (211486211), never ported to v4 | `git log -S branded_blend_anchor_overrides -- scripts`; only readers now are `verify_all_citations_content.py` and `reference_data_schema.py` | these studied materials own no Evidence identity in v4 | fold into lane 2A's "known studied material" rule (with the curated `BRAND_*` records) — not a new reader |
| F2 | Dose-related facts live in four files, and they are **not all one fact**: `rda_optimal_uls.json` (RDA/AI adequacy, UL, clinical anchors → Dose + Safety UL), `rda_therapeutic_dosing.json` (therapeutic ranges; botanical/collagen route only), `backed_clinical_studies.json` (`min_clinical_dose` on 11 records + `applicability.minimum_daily_dose` on 5: trial exposure / indication regimen → Evidence gates and applicability), `synergy_cluster.json` (`min_effective_doses`: combination thresholds → synergy signal/export). "16 of 210" counts fields, not runtime eligibility: form, purpose, population, disclosure, direction and route rules still apply to the other 194 | memory `project_dosing_two_file_boundary`; `generic_dose._band_credit`; INDEPENDENT_REVIEW.md §2, §4 | the same underdose can be charged twice (Evidence gate + Dose); copies of a same-scope value can drift | lane 3a: **one owner per fact of the same scope**; build the all-route rule table first; no dose-dependent decision disappears (see INDEPENDENT_REVIEW.md) |
| F3 | Manufacturer deductions are stored per record and need periodic re-aging. The framework (`manufacture_deduction_expl.json`) IS live: `api_audit/fda_manufacturer_violations_sync.py::recalculate_all_entries` applies recency + modifiers. Before the 2026-09-30 sync, 3 stored values were stale (Nature's Way −6.5 → −3.25, Green Lumber −18 → −9, Hydroxie −18 → −9 by the existing recalculator); commit 065d081e re-aged them. Remaining defect: the recalculator reads `date.today()` (l.781, 849, 1062–1064), so results are not reproducible for a fixed build date | INDEPENDENT_REVIEW.md §1; `git show 065d081e` | stale deductions between syncs; non-reproducible builds | owned by the FDA-sync session: explicit calculation date, recalculate-only option, freshness check (requested 2026-09-30) |
| F4 | App vocab drift: the app bundles its own copies (`assets/data/*_vocab.json`); its "drift tests" read only the app asset. 3 differ: `verdict_vocab` (app still has retired NUTRITION_ONLY), `iqm_category_vocab` (app lacks `mushroom_extracts`, used by 10 IQM parents), `legal_status_vocab` (app lacks `under_review`, used by 13 banned/high-risk entries incl. IGF-1, piracetam, vinpocetine) | per-vocab JSON compare against `scripts/data`; `rg` in Flutter lib | low today (legal status is not exported; the app only loads the vocab) — silent the day it is shown | sync every app-bundled vocab through `sync_flutter_reference_data.py` (it already syncs product_type) and make the app test compare against the synced manifest |
| F5 | DEAD since the first commit: `ingredient_weights.json`, `unit_mappings.json` (`constants.INGREDIENT_WEIGHTS/UNIT_MAPPINGS` never used; the enricher loads `ingredient_weights` and never reads it). `unit_mappings.json` holds assumed default strengths per form (e.g. "Vitamin D3 capsule 1000 IU") — unsafe if ever wired | `git grep -w INGREDIENT_WEIGHTS/UNIT_MAPPINGS`; `git log -S` → b74807993 only | maintenance cost in preflight/db_integrity/data_batch gates | delete with their constants, config entry, gate checks and contract tests in one commit (dead-code rule) |
| F6 | Clinician views stale: `views/by_condition/liver_disease.md` (21 vs 22 rules — misses dandelion "avoid"), `views/pregnancy_lactation.md` (dandelion and Siberian ginseng now "avoid", views say no_data), leftover `views/by_drug_class/hypoglycemics.md` (class split into high/lower/unknown) | regenerate `scripts/tools/split_rules_by_condition.py` into a temp dir and `diff -rq` | shipped rules are correct; clinician review reads stale views | regenerate; add a freshness check to the rule-edit path |
| F7 | Loaded but never read by key in the enricher: `ingredient_weights`, `rda_therapeutic_dosing`, `unit_conversions`, `user_goals_to_clusters`, `medication_profile_gate_rules`, `proprietary_blends`, `botanical_marker_contributions` (most are read directly by other modules) | `enrichment_config.json` database map vs `self.databases[...]` reads | memory per worker only | record; trim the config map when touching the enricher |
| F8 | `production_assessable_actives.json` is an audit output stored in `scripts/data/` with no reader | only `scripts/audits/build_production_assessable_actives.py` | misleading location | move to its audit folder |
| F9 | `build_interaction_db.py` docstring names `curated_interactions/interaction_overrides.json`, which does not exist; `--overrides` is optional and never passed | `rebuild_interaction_db.sh` step 2 | stale doc | drop the example |
| F10 | `caers_adverse_event_signals.json` has no pipeline reader — intentional: B8 gated off pending PRR/ROR thresholds (V1.1 ROADMAP §5.1) | `signal_strength_vocab.json` `_metadata` | none | none (dormant by design) |

Not defects (verified): `curated_interactions/*.json` all feed the interaction DB through the
directory glob; the 3 `medication_depletions_b1*_signoff.json` are test-enforced sign-off ledgers;
`safety_alerts/_TEMPLATE.json` is an authoring template (`build_safety_alerts.py` reads
`SA_*.json`); GATE files are validation vocabularies, allowlists, ghost-review ledgers and
verifier policies read by release gates; missing-file references to `percentile_categories.json`
(retired 2026-09-21) and `reference_data_manifest.json` (a Flutter-side asset) are intentional.
