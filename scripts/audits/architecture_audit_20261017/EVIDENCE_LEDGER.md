# Evidence ledger — architecture audit at `5fb2be1ca`

One row per asserted claim in `AUDIT.md`: the claim, the command that proved it (run from the repo root
with `source scripts/python_env.sh`), and the result. Census keys refer to `census.json`. Probe outputs are
in `probes/`. Family maps (`family_maps/*.md`) are Level-1 listings by agents; every family-map fact that
AUDIT.md relies on has its own row here, re-verified against source.

## Pin and scope

| Claim | Command | Result |
|---|---|---|
| Audited revision is `5fb2be1ca`, the latest green main CI run | `git rev-parse HEAD`; `gh run view 39070168203 --json headSha,conclusion,headBranch` | `5fb2be1ca26…`; main, success; `git rev-list --count 5fb2be1ca..HEAD` = 0 |
| Tracked production files are clean; dirty entries are another lane's docs and submissions | `git status --porcelain \| grep -E '\.(py\|sh\|json)$' \| grep -v manual_labels/` | empty; census `pin.dirty_entries` = 10 (docs/plans, SCORING_ENGINE_SPEC.md, LEDGER.md, docs/scoring/, 5 PG_SUB_*.json) |
| No sibling lane is refactoring | `grep -ciE 'refactor\|decompos\|split the\|extract(ed\|ing)? (module\|class)\|modulari' <7 handoffs>` | 0 in every handoff |
| `graphify-out/graph.json` is stale | `python3 -c "…built_at_commit"` | `3b002e78` ≠ HEAD |
| Census is reproducible | `census.py` run twice, `cmp census.json <copy>` | byte-identical |

## Size, structure, hygiene (census.json)

| Claim | Command / key | Result |
|---|---|---|
| 339 production modules, 207,853 LOC; layer split | `overview.production_modules`, `overview.loc_by_layer` | core 142,018; api_audit 35,721; release_safety 9,173; submission_review 9,089; dashboard 8,308; tools 1,325; reports 1,115; identity 1,104 |
| 5,141 functions; 137 >150 L; 43 >300 L; 92.6% annotated | `overview.functions*`, `overview.annotated_function_share` | as stated |
| 295 broad excepts; 1,803 prints vs 537 logger calls; 399 in-function import statements | `overview.broad_excepts`, `.print_calls`, `.logger_calls`, `.lazy_imports` | as stated |
| 1,797 of 1,803 prints are in modules with a `__main__` guard | inline Python over `modules[*].print_calls` + regex for `__main__` | CLI 1,797; library 6 (`release_safety/protected_blobs.py` 2, `api_audit/pubmed_client.py` 2, `release_safety/blob_inventory.py` 1, `enhanced_normalizer.py` 1) |
| Mega-file sizes and shapes | `modules["scripts/enrich_supplements_v3.py"]` etc.; AST census | enricher 25,186 L / 291 methods / class L880–25087; normalizer 12,722 / 157 methods; build_final_db 11,289 / 213 functions / 5 `global`; scoring_input_contract 6,451 / 170 functions |
| Longest/deepest functions | `functions_over_150[:8]`, `deepest_functions` | `_collect_rda_ul_data` 2,278 L nesting 18, 4 nested defs, 20 self attrs; `build_detail_blob` 1,684; `_match_quality_map_impl` 1,355 (27 nested defs); `_process_single_ingredient_enhanced` 1,296 (54 self attrs); `classify_supplement` 1,117 nesting 30 |
| `classify_supplement`: 106 if/elif, 1 return, 61 `primary_type =` across 19 values, one caller | `sed -n 613,1730p scripts/supplement_taxonomy.py \| grep -cE '^\s*(if\|elif) '`; `grep -oE 'primary_type = "[a-z_]+"' … \| sort -u \| wc -l`; `grep -rln classify_supplement scripts --include='*.py'` | 106; 1; 61/19; callers: enricher (`:17577`) and the module itself |
| Header-after-`__future__` "bare string" docstrings | `probes/cards.md` header lines | build_final_db, enhanced_normalizer, enrich_supplements_v3, verify_unii, verify_pubchem, verify_comptox, fda_weekly_sync, backfill_unii_from_cache |

## Dependency structure

| Claim | Command / key | Result |
|---|---|---|
| 688 top-level import statements, 289 lazy import statements (counted per statement, not per module pair), 0 top-level cycles, 3 cycles with lazy (12/3/2), 56 cycle edges | `imports.top_level_edges`, `.lazy_edges`, `.cycles_top_level`, `.cycles_with_lazy`, `.cycle_edges` | 688 / 289 / [] / [12,3,2] / 56 |
| Edge-by-edge classification of the 56 cycle edges (enclosing function, comment, origin commit) | inline Python over `imports.cycle_edges` + `git log --reverse -S'<import text>' -- <file>` (dossier reproduced in the audit's B.3 table) | e.g. contract→route_features top-level since 036bb624d (2026-08-20); contract→router lazy since 3d85f31f9 (2026-05-31); generic_helpers→quality_score lazy since 842e68331 (2026-10-15); dsld_validator→product_submission_import lazy since 44a2069c1 (2026-10-13); audit_identity_integrity→build_final_db lazy since 1e61ec4a0 (2026-10-12) |
| `_role_context` imports router/immune_support/sports_helpers; `role_driver_canonicals` imports route_features | `sed -n 6251,6305p scripts/scoring_input_contract.py`; `sed -n 6077,6097p …` | lines 6258, 6265, 6273; 6084 |
| `router.class_for_product` is an 11-line wrapper over `build_scoring_classification` | `cat scripts/scoring_v4/router.py` | 44 lines; docstring "All routing policy lives in scoring_input_contract" |
| `archetype_dose_reference` imports private `_archetype` | `sed -n 190,210p scripts/scoring_v4/modules/generic_helpers.py`; `grep -n "^def _archetype" scripts/scoring_v4/quality_score.py` | line 201; `_archetype` at 767 |
| `route_features.py` is contract-side vocabulary by its own docstring | `sed -n 1,10p scripts/scoring_v4/route_features.py` | "Pure feature extraction for the canonical v4 route decision… does not choose a route" |
| Hubs | `imports.fan_in_top`, `.fan_out_top` | quality_score_config 37; generic_helpers 34; scoring_input_contract 29; env_loader 24; supabase_client 17; normalization 15; fan-out enricher 25, build_final_db 22, score_supplements_v4 16 |
| Exporter imports only two names from the scorer | `grep -n "from score_supplements_v4 import\|from scoring_v4.quality_score import\|score_product_v4(" scripts/build_final_db.py` | lines 115 (`shipped_whole_score`), 116 (`SCORING_ENGINE_VERSION`); no scoring call |
| `build_scoring_classification` call sites in the score path | `grep -n "build_scoring_classification(" scripts/scoring_v4/scored_artifact.py scripts/scoring_v4/router.py scripts/scoring_v4/modules/botanical_profile.py scripts/enrich_supplements_v3.py` | scored_artifact 331; router 41; botanical_profile 260, 317; enricher 17557 |
| `queue_client` → `worker` import is one-directional (family-map claim of mutual import not confirmed) | `grep -n "from .worker import" scripts/submission_review/extraction/queue_client.py`; `grep -n queue_client scripts/submission_review/extraction/worker.py` | line 36; none |
| Clean path imports `_required_uuid` from the submission importer | `sed -n 60,70p scripts/dsld_validator.py`; `grep -n "^def _required_uuid" scripts/product_submission_import.py` | line 68; def at 168 |
| Identity gate imports `_warning_only_identity_labels` from the exporter | `grep -n _warning_only_identity_labels scripts/build_final_db.py scripts/audit_identity_integrity.py` | def at build_final_db 3359; used at 1796, 8171; imported at audit_identity_integrity 215 |

## Enricher and normalizer state (probes/class_state.py)

| Claim | Command | Result |
|---|---|---|
| Enricher: 78 attributes (6 load-once, 23 init-and-rebuilt, 28 never written in class, 21 per-run mutable); collectors write almost nothing | `probes/class_state.py scripts/enrich_supplements_v3.py SupplementEnricherV3 --prefix _collect_ …` → `probes/SupplementEnricherV3_state.md` | as stated; writes: `_collect_rda_ul_data` {`_rda_ul_warning_count`}, `_collect_delivery_data` {`_last_delivery_data`}, others none |
| Collector order and inputs in `enrich_product` | `awk 'NR>=24060 && NR<=24240 && /self\._collect_/' scripts/enrich_supplements_v3.py`; `Read 24030–24295` | 19 collector calls; `absorption`, `formulation`, `probiotic`, `evidence`, `interaction_profile`, `display` read the partial `enriched`; ordering constraints are commented |
| Closures: 30 collectors reach 240 methods / 14,012 LOC; shared core 62 / 4,134; exclusive families | closure section of the same probe + inline summary | `_collect_ingredient_quality_data` 98/7,704 (52 exclusive, 3,334 LOC); `_collect_interaction_profile` 29 (20 exclusive, 875); `_collect_rda_ul_data` 27 (13 exclusive, 1,022); 9 collectors closure ≤2 |
| `self.databases` read in 57 methods; `_collect_rda_ul_data` reads 16 module constants | attribute table; method row | as stated; constants include `_RDA_REFERENCE_PROFILE`, `_VITAMIN_E_ADULT_UL_MG`, folate form constants |
| Normalizer: 41 load-once attrs; per-product accumulators written in `normalize_product` | `probes/class_state.py scripts/enhanced_normalizer.py EnhancedDSLDNormalizer …` → `probes/EnhancedDSLDNormalizer_state.md` | `_canonical_serving_row`, `_display_ingredients_buffer`, `_display_source_rows`, `_label_ledger_omissions`; `normalize_product` closure 139 / 9,774 LOC; `_process_single_ingredient_enhanced` 49 self-calls |

## Exporter, contract, taxonomy

| Claim | Command | Result |
|---|---|---|
| `build_detail_blob` delegates to 23 section builders and assembles ~30 keys in one dict literal plus a dozen `blob[...] =` sections | `sed -n 6600,8284p scripts/build_final_db.py \| grep -oE '= *_?(build\|compute\|derive\|generate\|resolve\|classify\|assemble)_[a-z_0-9]+\(' \| sort \| uniq -c`; `… \| grep -nE '^\s{4}"[a-z_0-9]+": \|^\s{4}blob\["…"\] ?='` | 23 builder calls; dict literal at 7730; 12 `blob[...]` keys |
| Five module globals are lazy singleton caches | `grep -n "^\s*global " scripts/build_final_db.py` + surrounding lines | `_SHARED_INACTIVE_RESOLVER` 2074, `_ACTIVE_BANNED_RECALLED_INDEX` 2093, `IQM_REFERENCE_INDEX` 2174, `HARMFUL_REFERENCE_INDEX` 2220, `_GOAL_MAPPINGS_CACHE` 8780 |
| Silent fail-open at 1139 | `sed -n 1128,1145p scripts/build_final_db.py` | `except Exception: return False` with a comment, no log |
| Contract structure | `grep -n "^def build_scoring_classification\|^def derive_product_scoring_evidence\|…" scripts/scoring_input_contract.py`; `grep -c '^def _\?route_'`; `grep -c '^_ROUTE_[A-Z_]* *='` | 1813, 3038, 3313, 5824, 6373, 6397; 36 route functions; 38 `_ROUTE_*` constants; banners at 3536 and 5978 |
| Contract fail-closed with reasons at 5859–5893; fail-open on missing reference data at 569/4998 | scratchpad `broad_excepts.md` (sed of each site ±3 lines) | as stated |

## Duplication

| Claim | Command | Result |
|---|---|---|
| 5 exact / 11 structural cross-file duplicate bodies (~364 lines); 55 same-name private helpers in ≥3 files | `duplication.exact_cross_file_groups`, `.structural_cross_file_groups`, `.structural_cross_file_duplicated_lines`, `.same_name_private_helpers` | as stated; `_norm` 29 files, `_safe_dict` 20, `_safe_list` 18, `_clamp` 11, `_as_float` 10, `_cache_get` 9 |
| `_row_quantity_mg` identical in joint_support:183 and sleep_support:156; callers; no direct tests | `sed -n 183,214p …joint_support.py`; `sed -n 156,187p …sleep_support.py`; `grep -n _row_quantity_mg …`; `grep -l _row_quantity_mg scripts/tests/*.py \| wc -l` | identical 31 lines; callers 88, 111 / 74, 94; 0 tests |
| `_label_asserted_program_key` ≡ `_cert_program_key`; callers; no tests; owner has program vocabulary | `sed -n 261,280p generic_trust.py`; `sed -n 200,219p omega_trust.py`; `grep -n … modules/*.py`; `grep -n "^def normalize_program" scripts/cert_resolver.py`; ADR-0004 | identical; callers generic_trust 242, omega_trust 135/181; 0 tests; `normalize_program` at 675; `cert_evidence.py` is the matrix owner |
| Four module result dataclasses have identical fields and identical `to_breakdown`; one consumer | `sed -n <class ranges> \| grep -E '^\s{4}[a-z_]+:'` for generic/omega/probiotic/multi_prenatal; `grep -rn "\.to_breakdown()" scripts --include='*.py' \| grep -v tests/` | identical 11 fields (incl. `botanical_dose_deferred`, not rendered); consumer `score_supplements_v4.py:433`; 30 test files mention `to_breakdown` |
| `_normalize_unii` ×3 + placeholder constants ×3; callers | `sed -n 116,135p enhanced_normalizer.py`; `sed -n 544,563p enrich_supplements_v3.py`; `sed -n 64,83p api_audit/audit_unii_data_quality.py`; `grep -n "_normalize_unii(" …`; `grep -rn "_UNII_PLACEHOLDERS *=\|_PLACEHOLDER_UNIIS *=" scripts --include='*.py'` | identical semantics; callers normalizer ×8, enricher ×2, audit ×2; constants at enricher 400, normalizer 112, audit 61; 3 test files name it |
| `dose_safety_scope` vs `safety_gate_scope` are the same pattern over different results | `sed -n 173,185p scoring_v4/dose_safety.py`; `sed -n 1449,1461p scoring_v4/gate_safety.py` | both set a module `_ACTIVE_RESULT` contextvar |
| 93 `normalize_*` definitions triaged | scratchpad `normalize_defs.md` (signature + 6 lines each) | classification in AUDIT.md §D.2 |
| Three UPC normalizers with different rules | `normalize_defs.md` entries for `dsld_validator.py:167`, `build_final_db.py:246`, `sync_to_supabase.py:1098` | validation tuple / digits-only four GTIN widths / separator-drop mirroring Flutter |
| api_audit per-file HTTP client + cache pattern | `family_maps/api_audit.md` + census `same_name_private_helpers` (`_cache_get` 9, `_cache_set` 7, `_get` 7, `_make_ssl_ctx` 6) | consistent |
| `_list_paginated` duplicated in release_safety | `duplication.structural_groups` | delete_stale_version_dirs 637, storage_audit 539 (29 L) |

## Churn and co-change (`git log 5fb2be1ca --since=2026-07-01 --name-only`)

| Claim | Key | Result |
|---|---|---|
| 2,590 commits since July 1; top churn | `churn.commits`, `churn.production_top` | enricher 268, build_final_db 164, scoring_input_contract 130, normalizer 114, generic_evidence 81, quality_score 67, release_full.sh 53 |
| Enricher churn by month | `churn.enricher_commits_by_month` | Jul 64, Aug 42, Sep 102, Oct (1–17) 75 |
| 27% of commits touching the watched files touch ≥2 groups | `churn.cochange` | 773 touching; 208 ≥2 (26.9%); 70 ≥3; 1 bulk commit skipped |
| Top co-change pairs | `churn.cochange.pairs`, `churn.general_pairs_top` | contract+scoring_v4 66; build+scoring_v4 53; enricher+scoring_v4 53; normalizer+enricher 45; build+enricher 37; enricher+contract 33; contract+generic_evidence 21; probiotic_measurements+studied_formulas 18 |

## Tests, CI, protections

| Claim | Command / key | Result |
|---|---|---|
| 1,069 test files, 290,307 LOC, 253 fixture directory entries (251 files by `find -type f`), profiles SLOW 20 / LOCAL_ONLY 25 / RELEASE 11 / ARTIFACT 19, marks | `tests.*`; `find scripts/tests/fixtures -type f \| wc -l` | parametrize 1,898; skipif 21; inline slow 2 |
| `_collect_interaction_profile` reads/writes (C.1 row) | `sed -n 20086,20616p scripts/enrich_supplements_v3.py \| grep -oE "self\.databases\.get\(['\"][a-z_]+"`; closure entry in `probes/SupplementEnricherV3_state.json` | `ingredient_interaction_rules`, `clinical_risk_taxonomy`; transitive reads `databases`, `unit_converter`, `logger`, `_MASS_FACTORS_MG`, `_IU_UNIT_ALIASES`, `_EQUIVALENT_BASE_MASS_UNITS`; writes `_canonical_registry_id_cache`; module globals none |
| C.4 vocabulary move is cycle-free only toward `route_features` (a leaf) | `probes/cards.md` card for `scoring_v4/route_features.py` ("imports (top-level): none from scripts/"); `grep -n "^BCAA_AGGREGATE_CANONICALS\|^EAA_AGGREGATE_CANONICALS\|^SPORTS_PROTEIN_CANONICALS" -A2 scripts/scoring_v4/modules/sports_helpers.py`; `grep -n "^def is_immune_support_product" -A3 scripts/scoring_v4/modules/immune_support.py` | literal frozensets at 22/43/52; predicate is `primary_type_of(product) == "immune_support"` at 61; `_active_id` alias lookup at 227 |
| Test files referencing each mega-file | `modules[*].test_files_referencing` | enricher 260, normalizer 175, build_final_db 113, scoring_input_contract 73, supplement_taxonomy 76 |
| CI shard times and round-robin assignment | `ci.jobs`; `sed -n 281,312p scripts/test_profiles.py` | fast rung 404 / 651 / 343 / 390 s, wall 717 s; `paths[shard_index::shard_count]` |
| Profiles are applied centrally; file lists, not inline marks | `sed -n 56,75p scripts/tests/conftest.py` | `pytest_collection_modifyitems` adds slow/release/artifact marks from the lists |
| `replay.py` compares scores only | `grep -n "def project_record\|def slim\|PILLARS" scripts/audits/quality_redesign/replay.py` + lines 163–180, 284–295 | projection keeps id, name, route, subroute, total, status, pillars/components |
| `catalog_diff.py` compares core rows between baseline and candidate DBs | docstring lines 1–25; `def diff_catalogs` 196 | as stated |
| `canary_rebuild.py` emits a full detail blob for one raw label; 9 fixtures | docstring; `ls reports/canary_rebuild \| wc -l` | 9 |
| 33 frozen scored canaries with a per-product whitelist | `python -c "json.load(open('scripts/tests/fixtures/contract_snapshots/_manifest.json'))"` | `products` 33; `fixture_schema.frozen_fields` |
| `test_enrichment_regressions.py` boots a full enricher per class; marked slow | `sed -n 1,25p scripts/tests/test_enrichment_regressions.py` | "loads all 26 reference databases"; `pytestmark = pytest.mark.slow`; 232 tests |
| Dead-code ratchet and KEEP size | `python -c "import audit_dead_code as a; len(a.KEEP)"` | 16 |
| Pre-existing failures on the pinned revision | `gh run view 39070168203 --json conclusion` | success |

## Pipeline timing (`scripts/products/reports/batch_run_summary_*.txt`; sha256 per file in `pipeline_timing.batch_summaries[*].sha256`)

| Claim | Key | Result |
|---|---|---|
| Per-stage wall per run (banner timestamps STAGE 1 → 2 → 2.4/2.5 → 3 → PIPELINE COMPLETE) | `pipeline_timing.batch_summaries` | Sep 8: 2,252 s (clean 193 / enrich 1,675 / gates 10 / score 366); Oct 15: 4,525 s (299 / 2,880 / 27 / 1,299); five October full runs 3,838–4,512 s reported |
| Per-brand Oct 15 | `…[file=20261015_174328].stage_wall` | enrich median 34.5 s, max 556 s; score median 10 s, max 318 s; clean median 6 s |
| Enrichment summaries (July) | `pipeline_timing.enrichment_summaries` | 28 brands, 14,193 products, 1,921 s; median 0.156 s/product, p90 0.30, max 0.747; slowest GNC 2,214 products 460 s |
| Enricher index build is negligible | `grep -h "Performance indexes built" scripts/products/reports/batch_run_summary_*.txt \| … awk` | n=5,776, median 0.23 s, max 1.65 s |
| Anomalous run | `pipeline_timing.batch_summaries[20261008_194640]` | wall 16,512 s, enrich 10,598 s |
| Footprint | `du -sh scripts/products scripts/final_db_output scripts/dist scripts/data` | 11G / 2.5G / 4.8G / 2.3G |

## Config, docs, dashboard

| Claim | Command | Result |
|---|---|---|
| `scoring_config.json` has no metadata and is read only by the dashboard | `python -c "…_metadata"`; `grep -rn "scoring_config" scripts --include='*.py' --include='*.sh' \| grep -v "tests/\|audits/"` | `{}`; production hits are a comment (`constants.py:860`) and two docstrings; dashboard `data_loader.py:1424`, `views/audit_caers.py:241` |
| Engine version drift | `grep -n "^SCORING_ENGINE_VERSION" scripts/score_supplements_v4.py`; `grep -n "4\.5\.0" scripts/PIPELINE_ARCHITECTURE.md` | `4.6.0` at 98; doc lines 50, 125 say 4.5.0 |
| "~45-minute" rule | `grep -rn "45-minute" .claude/rules/` | `.claude/rules/scoring.md:44` |
| `constants.py` shape | `grep -c "^[A-Z_][A-Z0-9_]* *=" scripts/constants.py`; banner grep | 109 constants; one banner (897–899) |
| Dashboard section views unrouted | `grep -n "audit_section\|section-a\|section_a" scripts/dashboard/app.py scripts/dashboard/navigation.py scripts/dashboard/page_meta.py scripts/dashboard/views/__init__.py` | only `views/__init__.py:8-11` imports and `page_meta.py` keys at 127, 140, 153, 231; nothing in app.py or navigation.py |
| Hard-coded Flutter path; v3 section maxima | `grep -n "/Users/seancheick" scripts/dashboard/views/safety_copy.py`; `grep -n '"max": ' scripts/dashboard/components/score_breakdown.py` | `safety_copy.py:32`; `score_breakdown.py:88-91` (25/30/20/5), `V4_PILLARS` at 9 |
| Matrix: 44 concepts; enricher owns 11, normalizer 7 | `matrix.per_owner` | as stated |

## Review

### Self-refutation pass (main auditor, before the reviewer)

| Checked | Command | Outcome |
|---|---|---|
| `_collect_interaction_profile` "no writes" | closure entry in `probes/SupplementEnricherV3_state.json` | wrong — it memoizes `_canonical_registry_id_cache`; corrected in C.1 |
| C.4 first design (constants into the contract) | `probes/cards.md` card for `route_features` (imports nothing from `scripts/`); contract line 48 imports it at top level | would create a top-level cycle; design rewritten around `route_features` as the leaf home before the reviewer ran |
| `_row_quantity_mg`, `_cert_program_key`, `to_breakdown`, `_normalize_unii` identical | `sed` of each body pair | identical |
| Exporter never scores | `grep -n "from score_supplements_v4 import\|from scoring_v4.quality_score import\|score_product_v4(" scripts/build_final_db.py` | two names only (lines 115–116) |

### Fresh-context reviewer (general-purpose agent, main model, read-only, 39 tool calls)

Brief: the audit's requirements, `AUDIT.md`, this ledger, `census.json`, the matrix and ADR-0004; verify every
P1 and a sample of P2/P3 directly against source; try to refute; report PASS/PARTIAL/FAIL with commands.

Verdicts: PASS — R3, R4, R11, R13, R14, R28, B.3 rows 2/3/5/6, components 2 and 3 (edges), D.1 UPC trio, E.1
timing table (recomputed from the raw banners), E.2 call sites, C.8, C.10 `_list_paginated`, D.4/D.5, matrix
counts, `KEEP` = 16, `--check-refs` 0 misses. PARTIAL — R1 (arithmetic), R2 (counts), R5 (smoke-test
coverage), R9 (severity framing), R12 (scope), R15 (count method), R20/R21 (closure figures not persisted),
B.3 completeness (47 of 56 edges tabulated), tier labelling. FAIL — B.3 row 1 / B.2 row 1: the contract →
`route_features` edge is the matrix-intended direction (`fiber_identity` owner = `route_features`), not an
inversion.

Every reviewer correction was reproduced here before adoption:

| Reviewer claim | Reproduction | Disposition |
|---|---|---|
| `fiber_identity` owner is `route_features`; contract is a consumer | `python -c` dump of the matrix concept: owner `scripts/scoring_v4/route_features.py`; consumers include the contract; forbidden: "comes only from route_features.FIBER_CANONICALS" | Adopted: B.2/B.3 row 1 reclassified as intended direction; fiber sets stay; relocation = owner move for Sean |
| Moving the fiber sets into the contract creates a top-level cycle | `grep -n "^from \|^import " scripts/scoring_v4/route_features.py` → stdlib only; contract line 48 top-level import; internal uses at 121, 476–513, 602–609, 655, 681 | Adopted (already avoided by the leaf-home rewrite); stated explicitly in C.4 |
| Sports aggregate sets differ from `_ROUTE_*` sets | `scoring_input_contract.py:3781,3789,3790`; `sports_helpers.py:22,43,52`; consumers `sports_dose.py:20,28`, `sports_formulation.py:24,129` | Adopted: "must not be merged" added |
| Immune alias helpers depend on `generic_helpers._norm_text` | `immune_support.py:12` import; `_matches_any` at 251 uses `_norm_text` | Adopted: immune expansion stays lazy by default; predicate inlined |
| `router.class_for_product` raises on unknown route | `router.py:34-44` | Adopted: keep `VALID_CLASSES` check |
| Contract lazy modules after R12: 3 (+ `serving_frequency` at 6404) | `sed -n 6402,6406p scripts/scoring_input_contract.py` | Adopted: "7 → 4 while immune stays lazy" |
| Loaders unguarded at 1057, 1078, 6806, 6959 → build crashes today | `grep -n "_get_active_banned_recalled_index()\|_get_shared_inactive_resolver()" scripts/build_final_db.py` | Adopted: R9 reframed as inconsistent guard, P1 → P2 |
| UNII call sites 21; placeholder sets 4 | `grep -rn "_normalize_unii(\|normalize_unii(" scripts --include='*.py' \| grep -v "tests/\|def " \| awk … uniq -c` → 2/3/2/8/6; `PLACEHOLDER_UNIIS` at `audit_unii_same_tier_conflicts.py:26` | Adopted (the first count had been truncated by `head`) |
| `_row_quantity_mg` move re-keys six leak-allowlist entries | `grep -n _row_quantity_mg scripts/audit_scoring_contract_leaks.py` → 130–136; scan scope `V4_DIR.rglob("*.py")` at 150–154; `scripts/tests/test_scoring_contract_leak_audit.py` exists | Adopted in R6 |
| `audit_identity_integrity.py:212` declares export owns the warning-only rule | `sed -n 210,216p scripts/audit_identity_integrity.py` | Adopted: component 3 becomes an ownership question for Sean |
| Smoke test renders 12 of 14 routed slugs | `sed -n 23,37p scripts/tests/test_dashboard_smoke.py` (12 slugs) vs `navigation.py` (14) | Adopted in H #5 and F.4 |
| CI floor ≈510 s (−28%), not −38% | `gh run view 39070168203 --json jobs` → job durations 472/715/403/461 s vs fast-rung 404/651/343/390 s | Adopted in A, E.1, H #1 |
| `scoring_config.json` also read by `views/quality.py:579`, `page_meta.py:55,260` | `grep -n scoring_config scripts/dashboard/views/quality.py scripts/dashboard/page_meta.py` | Adopted |
| `classify_supplement`: 94 `If` nodes, 59 assignments inside the function | reviewer's AST probe; audit's 106/61 were text-line counts over 613–1730 | Adopted with the method stated |
| Nine cycle edges untabulated; `dose_safety` unnamed; evidence→contract is 9 | `census.json imports.cycle_edges` (56) | Adopted: row added to B.3 |
| Closure figures not reproducible from the committed probe | `probes/SupplementEnricherV3_state.json` had `closure_methods` as an integer only | Adopted: `probes/class_state.py` now persists `closure_members`, `exclusive_helpers`, `exclusive_loc` and a `summary` over the peer group (`--peer-prefix`, default `_collect_`); re-run reproduces 240/14,012, 62/4,134, 52/3,334, 20/875, 13/1,022 |
| "95% private" overstated | 20 of 29 helpers (875 of 1,603 LOC) | Adopted |
| Tier label implied source reading for 89 card-only modules | `probes/cards.md` header | Adopted: three tiers (L1, L2-source, L2-card) defined in the preamble; §A and §C.10 relabelled |
| `MatchContext` is a new owner object | AGENTS.md "Autonomy" | Adopted: "ADR and Sean" in C.1, G, R21 |
| `--check-refs` rejects repo-relative paths | reproduction of the brief's command | Fixed in `census.py` (`given.exists()` branch) |
| `build_detail_blob` dict literal has 35 keys | reviewer's `ast.Dict` count | Adopted |
| Four module-result dataclasses have 11 fields | reviewer's AST | Adopted in this ledger |

Not adopted: none. The reviewer's suggestion to raise R12's risk to 4 applied to the earlier design; with the
fiber sets excluded and the immune expansion kept lazy, R12 stays at risk 3 with gain 4.
