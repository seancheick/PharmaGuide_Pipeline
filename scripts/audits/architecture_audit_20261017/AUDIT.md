# Architecture and code-quality audit — PharmaGuide pipeline

Revision audited: `5fb2be1ca` (main; latest green `pipeline-tests` run 39070168203). Dates: October 17–18, 2026.
Audit-only: no production file, data file, rule, skill or handoff was changed. Deliverables live in this
directory; every number below comes from `census.json` (rebuild with `census.py`, byte-identical across runs)
or from a probe in `probes/`, and every asserted claim has a command in `EVIDENCE_LEDGER.md`.

**Three tiers, labelled honestly.** **L1** is automated analysis of all 339 production modules
(`census.json`). The published criteria (>800 LOC, a function >300 lines or nesting ≥10, ≥30 commits since
2026-07-01, lazy-import cycle member, fan-in ≥15 / fan-out ≥10, ≥2 matrix concepts, release chain) promote
98 modules. Of those, **L2-source** — the source was opened and dependencies traced — covers the hotspots in
§C.1–C.9 and every symbol named with a line number in §B.3, §D and §H (each has a ledger row). The other 89
promoted modules are **L2-card**: their generated structure card (`probes/cards.md`, built from the AST —
header, class/function layout, imports, importers) was read and a verdict formed; source was opened only
where a card raised a question (`_list_paginated`, the api_audit client classes, the dashboard views named in
§C.10). A card is a metric view, not a reading; nothing below claims more than that.

**Structural vs behavioral.** Every recommendation is structural (behavior-preserving) unless its priority
line says **behavioral**; those are listed so they are not mistaken for refactors.

---

## A. Executive summary

**Overall assessment.** At the stage level the pipeline is well architected and unusually well guarded:
four subprocess-isolated stages (`scripts/run_pipeline.py::PipelineRunner`), per-stage manifests with
SHA-256 ownership (`scripts/stage_manifest.py::write_stage_manifest`), code-and-reference fingerprints that
refuse stale output (`scripts/pipeline_freshness.py::stage_code_fingerprint`), one public scorer behind one
config (ADR-0002), a machine-readable ownership matrix with 44 concepts and a gate that enforces it, a
dead-code ratchet, 1,069 test files (290k lines, 1.4× production), a release chain that builds into
candidates and promotes atomically. The structural debt is concentrated, not diffuse: four files hold 27%
of production code and absorb the change load, and one layering inversion between the scoring-input
contract and the scorer package is held apart by lazy imports.

**What is already working well (evidence).**
- No import cycle at module top level across 339 modules (`census.json: imports.cycles_top_level = []`).
- 92.6% of 5,141 functions carry type annotations; the four largest files are at 93–100%.
- `print()` is confined to CLIs: 1,797 of 1,803 calls sit in modules with a `__main__` guard.
- Ownership is explicit and machine-checked: `scripts/contracts/source_of_truth_matrix.json` (44 concepts, 43
  required) gated by `scripts/audit_source_of_truth_contract.py`; ADR-0004 records the consolidations that
  removed earlier duplicate brains (cert filter, probiotic predicates).
- The error-handling pattern in the enricher is deliberate: `enrich_product` zeroes every section on any
  failure so a partially enriched product can never reach the scorer without its safety sections
  (`scripts/enrich_supplements_v3.py:24243-24283`).
- Config is fingerprinted into every artifact (`scripts/scoring_v4/config_registry.py`,
  `config_fingerprint_history.json`), and the exporter never scores (`scripts/build_final_db.py` imports only
  `shipped_whole_score` and `SCORING_ENGINE_VERSION` from the scorer, lines 115–116).
- Release safety is a real package: typed errors, a JSON-file mutex, gates, quarantine with recovery,
  bundle alignment (`scripts/release_safety/`, 18 modules, 9,173 LOC, promoted by the release-chain
  criterion and reviewed at card level, with `_list_paginated` and the lock/gates docstrings opened).

**Biggest technical risks, ranked.**
1. **Change-risk concentration in the enricher.** `scripts/enrich_supplements_v3.py` is 25,186 lines, one
   class with 291 methods, 268 commits since July 1 (102 in September, 75 in the first 17 days of October).
   27% of all commits touching the watched files touch two or more of them. Tests are plentiful (260 test
   files name the class) but every change lands inside a 24,208-line class body.
2. **Contract ↔ scorer reach-ins held apart by lazy imports.** The contract's top-level import of
   `scoring_v4.route_features` is the direction the matrix prescribes (`fiber_identity` is owned by
   `route_features`, consumed by the contract). The inversions are narrower: the contract lazily imports
   `scoring_v4.router` (an adapter over the contract's own function), `scoring_v4.modules.immune_support` and
   `scoring_v4.modules.sports_helpers` to compute role drivers, and `generic_helpers` lazily imports the
   assembler's private `_archetype`. Routing vocabulary still has three homes (the contract's `_ROUTE_*`
   sets, `route_features`, `sports_helpers`), and the contract + `scoring_v4/*` pair is the most frequent
   co-change in the repository (66 commits).
3. **An inconsistent guard in the exporter's banned/recalled bridge** (`scripts/build_final_db.py::_resolver_status_in`,
   1139): if the alias index or the inactive resolver fails to load, this one site returns `False` with no log
   line — while the same loaders run unguarded at 1057, 1078, 6806 and 6959, so an unloadable index crashes
   the build elsewhere today. The defect is the guard shape at the one place that exists to catch what
   `contaminant_data` misses; it should fail loudly like its neighbours.
4. **No corpus-scale equivalence tool for Enrich/Export refactors.** `replay.py` compares scores, pillars,
   status and route; `catalog_diff.py` compares core-row score/tier/safety; the full enriched JSON and detail
   blob are compared only for 9 canary labels and 33 frozen scored products.
5. **Pipeline wall time doubled in five weeks** (37.5 min on Sep 8 → 75 min on Oct 15 for the same 38 brands)
   and the score stage grew 3.5× (366 s → 1,299 s). The cause is unmeasured; code shows the classification
   builder invoked from four sites per product in the score path.
6. **Stale pointers in rules and docs**: engine `4.6.0` in code vs `4.5.0` in `scripts/PIPELINE_ARCHITECTURE.md`;
   "~45-minute full pipeline" in `.claude/rules/scoring.md:44`; `scripts/config/scoring_config.json` is read by
   nothing in the pipeline yet is surfaced by the dashboard as the scoring config and named in
   `scripts/constants.py:860` as the home of "all scoring values".

**Highest-value opportunities.** Five small, low-risk changes can land first (§H): duration-balanced CI
shards (≈28% shorter CI wall), three duplicate-logic removals that each put a decision back under its matrix
owner, and deletion of 1,417 lines of unreachable dashboard views. Then the equivalence harness (§F.3)
unlocks the medium-term work: one leaf home for routing vocabulary, extracting the exporter's inline blob
sections, and the first enricher extraction (the interaction profile: 20 of its 29 helpers, 875 of 1,603
LOC, are used by no other collector).

---

## B. Architecture review

### B.1 Stage map as built

```
batch_run_all_datasets.sh ─► run_pipeline.py per brand (subprocess per stage)
   clean:  clean_dsld_data.py ─► batch_processor.py ─► enhanced_normalizer.py      ─► cleaned/.stage_manifest.json
   enrich: enrich_supplements_v3.py (SupplementEnricherV3.enrich_product)          ─► enriched/.stage_manifest.json
   gates:  enrichment_contract_validator.py, coverage_gate.py (in-process)
   score:  score_products_v4.py ─► scored_artifact.build_scored_artifact ─► score_supplements_v4.score_product_v4
                                                                                  ─► scored/.stage_manifest.json
rebuild_dashboard_snapshot.sh ─► build_final_db.py ─► release_catalog_artifact.py ─► promote_release_artifacts.py
release_full.sh (8 steps, 19 shell functions) ─► sync_to_supabase.py, Flutter bundle, interaction DB
```

Stage isolation is strong: the enricher is imported at top level by no production module (only
`audit_label_ledger_reconciliation` and `reports/canary_rebuild` import it lazily), and
`score_products_v4` is imported by nobody. Manifests record owned files and SHA-256; freshness fingerprints
cover stage code (transitive imports) and every `scripts/data/*.json`. This is the backbone that makes
refactoring safe — and it also means **any structural edit to Clean/Enrich/Score code invalidates the stage
fingerprints and requires a corpus rebuild before the next release** (see §I).

### B.2 Authority map versus placement

The matrix and `PIPELINE_ARCHITECTURE.md §2` name one owner per decision. Placement mostly agrees, with
three exceptions that are the architectural findings of this audit:

| Concern | Declared authority | Where the code actually lives | Verdict |
|---|---|---|---|
| V4 route decision | `scoring_input_contract.py` | `scoring_input_contract.py` (36 `route_*` functions, 38 `_ROUTE_*` constants) **plus** `scoring_v4/route_features.py` (861 LOC: `B_VITAMIN_CANONICALS`, `FIBER_CANONICALS`, `extract_route_features`…) **plus** module-level sets in `scoring_v4/modules/sports_helpers.py` (`BCAA_AGGREGATE_CANONICALS`, `EAA_AGGREGATE_CANONICALS`, `SPORTS_PROTEIN_CANONICALS`) | **Intended direction for `route_features`** — the matrix's `fiber_identity` names it owner and the contract a consumer. The `sports_helpers` sets and the contract's lazy reach-ins into `router`, `immune_support` and `sports_helpers` are the finding (B.3) |
| Module dispatch adapter | `scoring_v4/router.py` | 44-line adapter that imports the contract; the contract lazily imports it back inside `_role_context` to learn the module when none was passed | Self-cycle through the adapter (B.3) |
| Archetype of a scored product | not in the matrix; de facto `scoring_v4/quality_score.py::_archetype` | `scoring_v4/modules/generic_helpers.py::archetype_dose_reference` lazily imports the assembler's private `_archetype` (commit 842e68331, 2026-10-15) | Helper reaching up into the public assembler (B.3) |
| Certification evidence | `scoring_v4/cert_evidence.py` (ADR-0004) | program-key derivation duplicated in `generic_trust.py` and `omega_trust.py` (D.1) | Residual copy outside the owner |
| Text normalization | `normalization.py` ("the only normalizer", AGENTS.md) | UNII canonicalization duplicated in `enhanced_normalizer.py:116` and `enrich_supplements_v3.py:544` (D.1) | Identity normalizer outside the owner |
| Enricher-owned concepts | 11 concepts in the matrix (identity resolution, IQD contract, taxonomy input, active safety, interaction profile, display ingredients, product-level evidence, fallback policy, canonical id, type mirror, enriched active safety) | one class | The matrix already names the seams a decomposition would follow (C.1) |

### B.3 Dependency direction: the lazy-import cycle, edge by edge

Top-level imports form a DAG (688 import statements between production modules, 0 cycles). Adding the 289
in-function import statements creates three strongly connected components (12, 3 and 2 modules; 56 edges). Each edge was read with its enclosing
function, comment context and origin commit (`scratchpad` dossier, reproduced in `EVIDENCE_LEDGER.md`), and
classified. Only layering inversions are findings; the rest is recorded as intentional.

**Component 1 (12 modules) — contract, scorer, evidence, probiotics.**

| Edge | Kind | Origin | Classification |
|---|---|---|---|
| `scoring_input_contract` → `scoring_v4.route_features` (top level, line 48; lazily again at 6084 in `role_driver_canonicals`) | TOP + lazy | 036bb624d 2026-08-20 | **Intended direction (matrix).** `source_of_truth_matrix.json::fiber_identity` names `route_features` the owner of the fiber/enzyme canonical sets and the contract a consumer ("…comes only from route_features.FIBER_CANONICALS…"); `route_features` imports only `re`/`typing`, so it is a leaf. The lazy import at 6084 brings four more names from the module already imported at line 48 and should simply be hoisted. Its package path (`scoring_v4/`) is the only oddity; relocating the module would move a matrix owner and needs Sean. |
| `scoring_input_contract._role_context` → `scoring_v4.router.class_for_product` (6258, `# lazy`) | lazy | 3d85f31f9 2026-05-31 | **Self-cycle through the adapter.** `class_for_product` is a 11-line wrapper around the contract's own `build_scoring_classification`; the contract could call itself. |
| `scoring_input_contract._role_context` → `scoring_v4.modules.immune_support` (6265), → `scoring_v4.modules.sports_helpers` (6273) | lazy | 4c4400c10 2026-09-26; 3ee91eae9 2026-10-01 | **Inversion.** Role classification (contract) consults module-specific product predicates and canonical sets. These are routing vocabulary, not scoring policy. |
| `scoring_v4.router` → contract (14); `scoring_v4.modules.generic_helpers` → contract (24, top; 462 lazy); `immune_support` → contract (21); `sports_helpers` → contract (7) and → `route_features` (9) | TOP | 2026-08-05 … 2026-10-17 | Intended direction (scorer consumes the contract). They are the other half of the cycle only because of the rows above. |
| `scoring_v4.modules.generic_helpers.archetype_dose_reference` → `scoring_v4.quality_score._archetype` (201) | lazy | 842e68331 2026-10-15 | **Inversion.** A helper module imports a private function of the public assembler so Dose credits and the pillar agree on the archetype. The agreement is right; the placement is upside-down. |
| `scoring_input_contract` → `evidence_resolver` (`is_reviewed_branded_material` 1820, 3358; `evidence_indication_categories` 6227) | lazy | 06b00bb38 2026-09-30; 3c8bf24f7 2026-09-26 | **Small inversion.** The matrix lists `evidence_resolver` as a consumer of the contract; here the contract asks the evidence layer two questions. Two symbols. |
| `evidence_resolver` → contract (9 edges, 2026-09-20 … 10-06), → `route_features` (448), → `studied_formulas` (806, 838), → `clinical_applicability` (997, 1200), → `probiotic_measurements` (830) | lazy | | Intended direction; lazy only because of the two edges above. |
| `clinical_applicability` → contract (`get_evidence_subject_rows` ×3) | lazy | 0d69eeb0b 2026-09-29 | Intended direction. |
| The remaining edges that close the component: contract → `probiotic_measurements` (47 top; 1319, 4168, 6115 lazy), `studied_formulas` → `clinical_applicability` (16), `quality_score` → `dose_safety` (27), `dose_safety` → `generic_helpers` (41), `immune_support` → `generic_helpers` (12), `sports_helpers` → `generic_helpers` (13) | TOP (+3 lazy) | — | Intended direction, no finding. `scoring_v4.dose_safety` is the component's twelfth member only through these; the `_archetype` edge above closes its loop via `quality_score → dose_safety → generic_helpers`. |
| `probiotic_measurements` ↔ `studied_formulas` (4 lazy edges one way; 1 top + 3 lazy the other, including the private `_label_designation_tokens`) | both | 2026-09-03 … 09-20 | **Acknowledged cycle-breaker** (comment at `probiotic_measurements.py:688`: "studied_formulas imports this module, so re-import lazily"). Two owners of one topic (probiotic row identity vs. studied-formula contract). The private-token import is the only part worth moving. |
| `scoring_v4.route_features._probiotic_features` → `probiotic_measurements.declared_total_cfu` | lazy | e8fc7ef08 2026-09-04 | Intended (feature extraction consumes the probiotic owner). |

**Component 2 — `dsld_validator` → `product_submission_import._required_uuid` (68, lazy, 44a2069c1 2026-10-13)**;
`product_submission_import` → `enhanced_normalizer.parse_other_ingredient_disclosure` (503); `enhanced_normalizer`
→ `dsld_validator` (9941). **Small inversion:** the Clean path imports a private UUID validator from the
submission importer, a peripheral tool that itself imports Clean.

**Component 3 — `audit_identity_integrity.audit_product` → `build_final_db._warning_only_identity_labels` (215,
lazy, 1e61ec4a0 2026-10-12)**; `build_final_db` → `audit_identity_integrity` (57, top). **Small inversion:** the
identity release gate imports a private rule from the exporter. `audit_identity_integrity.py:212` records
the current intent ("Export owns warning-only row eligibility") and no matrix concept covers the rule, so
where it belongs is an ownership decision for Sean, not a refactor; the function also uses the exporter's
`_has_verified_source_label` and `safe_str`. **Decided 2026-10-18 (Sean): export owns the rule;** the
private import stands and no second warning-only policy may be created. A public name for the function
would be a courtesy, not a requirement.

### B.4 Hubs and fan-out

| Module | Fan-in (top level) | Note |
|---|---|---|
| `scoring_v4/quality_score_config.py` (45 LOC) | 37 (40 importers incl. lazy) | Config reader; correct hub. |
| `scoring_v4/modules/generic_helpers.py` (474 LOC) | 34 | Named "helpers" but is the matrix owner of `ingredient_form_quality` (`eligible_delivery_data`) and the home of Dose reference scoping. A policy owner hiding behind a utility name (P3 naming). |
| `scoring_input_contract.py` (6,451 LOC) | 29 (33 incl. lazy) | Expected: it is the contract. |
| `env_loader.py` (35 LOC) | 24 | Fine. |
| `normalization.py` (860 LOC) | 15 | Fine; the declared owner. |

Fan-out: `enrich_supplements_v3` 25, `build_final_db` 22, `score_supplements_v4` 16, route modules 10–12.
The exporter's 22 top-level imports come with eight lazy ones (`cert_resolver`, `clinical_applicability`,
`probiotic_measurements`, `studied_formulas`, `scoring_v4.cert_evidence`, `sports_helpers`…) — the exporter
re-derives presentation from several owners rather than from the scored artifact alone (C.3).

---

## C. Hotspot analysis (Level 2, full protocol)

Ranking inputs for every candidate: churn since 2026-07-01 (`census.json: churn.production_top`), co-change,
closure/coupling from `probes/`, test files referencing it.

### C.1 `scripts/enrich_supplements_v3.py` — 25,186 LOC, 268 commits, L2

**Responsibilities.** One class `SupplementEnricherV3` (lines 880–25087, 291 methods, 24,208 lines) owning
11 matrix concepts. `enrich_product` (23976–24288) runs 30 `_collect_*` collectors in a fixed, commented
order (taxonomy after probiotics; evidence after taxonomy and native classification; percentile after
taxonomy), each writing one top-level key of the enriched record.

**What the shared-state probe found (the September check, done mechanically — `probes/SupplementEnricherV3_state.md`).**
- 78 instance attributes: 6 load-once, 23 built in `__init__` and rebuilt by index builders, 28 never
  written in the class (set by `_init_scoring_modules`/`_load_all_databases` helpers), **21 per-run mutable** —
  and those 21 are caches (`_product_text_cache`, `_regex_pattern_cache`, …) and diagnostic counters
  (`match_counters`, `_rda_ul_warning_count`, `_parent_fallback_details`). The collectors are **not**
  stateful accumulators: 28 of 30 write no attribute at all; `_collect_rda_ul_data` writes one counter and
  `_collect_delivery_data` one cache; `_match_quality_map_impl` (the shared matcher) writes four diagnostics.
- The real coupling is the **private helper graph**, not mutable state. The 30 collectors transitively reach
  240 methods (14,012 LOC; probe `closures.summary`). A shared core of 62 methods (4,134 LOC) is used by three or more collectors —
  dominated by matching and form logic (`_match_quality_map_impl` 1,355 L, `_match_multi_form` 404 L,
  `_build_form_info_from_cleaned` 376 L, `_parse_single_form`, `_extract_form_from_label`, text helpers).
- Exclusive helper families (used by no other collector): `_collect_ingredient_quality_data` 52 methods /
  3,334 LOC; `_collect_interaction_profile` 20 / 875; `_collect_rda_ul_data` 13 / 1,022 (plus its own 2,278);
  `_collect_certification_data` 8 / 473; `_collect_dietary_sensitivity_data` 8 / 338; `_collect_evidence_data`
  8 / 301; `_collect_probiotic_data` 6 / 305. Nine collectors have a closure of ≤2 methods.
- Hidden inputs: `self.databases` (the loaded reference-file bag) is read in 57 methods; `_collect_rda_ul_data`
  reads 16 module-level constants (`_RDA_REFERENCE_PROFILE`, `_VITAMIN_E_ADULT_UL_MG`, folate form constants…).

**The actual problem.** Not size per se — change risk: every fix to any of eleven concepts is an edit inside
one class whose helper graph is shared, so a form-matching fix can change identity, evidence and taxonomy
inputs at once (the September and October commit subjects are exactly that: forms, sugar bounds, delivery
credit, identities). Review cost is paid per concept; the file offers no boundary at which to pay it.

**Does decomposition pay?** Yes, but only along the seams the closures expose, and only after the
equivalence harness (§F.3) exists. Decomposition that pays:

| Candidate | What moves (at `5fb2be1ca`) | Owner afterwards | Remaining dependencies / state | Interface | Verification | Measurable benefit |
|---|---|---|---|---|---|---|
| **Interaction profile** | `_collect_interaction_profile` (20086–20616) and its 20 exclusive helpers (875 LOC; names in `probes/SupplementEnricherV3_state.json` under `closures.per_method._collect_interaction_profile.exclusive_helpers`; exclusivity is among the 30 collectors) | extend the existing matrix owner concept `interaction_profile_contract`; a new module requires Sean (new owner module, not a new semantic owner — the concept exists) | transitive reads: `databases` (`ingredient_interaction_rules`, `clinical_risk_taxonomy`), `unit_converter`, `logger`, three class-level unit tables (`_MASS_FACTORS_MG`, `_IU_UNIT_ALIASES`, `_EQUIVALENT_BASE_MASS_UNITS`); transitive writes: only the `_canonical_registry_id_cache` memo (via `_canonical_registry_ids`); 0 module globals | `collect_interaction_profile(enriched, *, rules, risk_taxonomy, registry_ids, converter, user_profile)`; the enricher keeps a one-line call | full enriched-JSON diff on the frozen brand set (§F.3); `test_interaction_rules_integrity_regressions.py` (67 commits) | the 531-line collector and its helpers leave the shared graph; co-change with scoring/export for interaction rules becomes visible at one file |
| **Identity/IQD matching core** | `_match_quality_map_impl` family (shared core: 62 methods, 4,134 LOC) + the 52 helpers exclusive to `_collect_ingredient_quality_data` (3,334 LOC) | `ingredient_identity_resolution` is already a matrix concept owned by the enricher; `scripts/identity_integrity.py` and `scripts/identity/` hold the pure identity contract (`resolve_identity`, called once at 4412). The matcher is the *stateful* half | reads `databases`, the performance indexes (`_iqm_exact_index`, `_iqm_norm_index`, `_nonscorable_index`), caches (`_match_quality_cache`), writes diagnostics (`match_counters`, `_parent_fallback_details`, counters) → needs an explicit `MatchContext` object — a new owner object, so an ADR **and Sean** | `match_quality_map(..., ctx)`; diagnostics returned on the context, not on the enricher | full enriched diff + `match_ledger` byte equality + `test_ingredient_matching_regression.py`; `audit_dead_code.py trace` afterwards | the largest change-risk surface moves behind one interface; the enricher's remaining collectors call it, never its internals |
| **RDA/UL collection** | `_collect_rda_ul_data` (21693–23970, 2,278 L, nesting 18) + 13 exclusive helpers (1,022 LOC) | `scripts/rda_ul_calculator.py::RDAULCalculator` (already `self.rda_calculator`) and `scripts/dose_assessment.py` (`clinical_exposure_assessments` already appended at 24159) are the owners of adequacy and exposure; the collector is orchestration plus label-reading policy | reads `rda_calculator`, `unit_converter`, 16 module constants (must move with it or be passed), writes `_rda_ul_warning_count` | `collect_rda_ul_data(product, *, calculator, converter, servings)` | **behavioral surface is UL safety**: corpus diff of `rda_ul_data` per product (frozen inputs); the 75 test files that name `rda_ul_data`/`RDAULCalculator` (e.g. `scripts/tests/test_b7_ul_aggregation.py`, `scripts/tests/test_b7_pct_ul_none_failsafe.py`, `scripts/tests/test_audit_rda_ul_reference_stamps.py`, `scripts/tests/test_clinical_research_exposure.py`); the Dose shadow-diff from `/pg-scoring-change` | the one 2,278-line function becomes a module with named sections; nesting 18 is the symptom |

Decomposition that does **not** pay (and is not recommended, §J): moving the ten tiny collectors; moving
`_collect_ingredient_quality_data` *without* its matching core; any "label fact provider" (ledger Q37).

**Sequencing and risk.** Interaction profile first (private closure, no writes, one data file), matching
core second (needs the context object and the harness), RDA/UL last (safety surface). Complexity: M / L / L.
Regression risk: low / medium / medium-high. Tests before: full-artifact baseline on the 38-brand frozen set;
tests after: byte-identical enriched JSON except `enriched_date`/`generated_at`.

### C.2 `scripts/enhanced_normalizer.py` — 12,722 LOC, 114 commits, 7 matrix concepts, L2

`EnhancedDSLDNormalizer` (157 methods, 11,510 lines) plus `EnhancedIngredientMatcher` (14 methods).
`normalize_product` (6394, 708 L) has a closure of 139 methods / 9,774 LOC and **does** carry per-product
accumulators written during the run: `_canonical_serving_row`, `_display_ingredients_buffer`,
`_display_source_rows`, `_label_ledger_omissions` (written in `normalize_product`, `_record_unsupported_label_source`,
`_stamp_raw_source_paths`). `_process_single_ingredient_enhanced` (7472, 1,296 L, nesting 9) calls 49
methods and reads 54 attributes. Forty-one attributes are load-once lookups built in `__init__` — the
normalizer's state is mostly reference indexes, plus the four accumulators.

**Problem.** The label-ledger accumulators make the per-ingredient path order-dependent on class state; this
is the stateful shape the September audit missed. **Recommendation (structural, wave 3):** introduce an
explicit per-product context object for the four accumulators (constructed at the top of `normalize_product`,
passed down), *before* any split of `_process_single_ingredient_enhanced`. Then the 1,296-line method can be
sectioned by its existing responsibilities (quantity, forms, mapping, display rows). Owner stays the cleaner
(7 matrix concepts). Verification: byte-identical cleaned JSON on frozen raw labels (`replay.py freeze-raw`
runs Clean; the harness must keep the cleaned record, §F.3) and `test_cleaner_first_contract_canary.py`.
Risk medium; benefit: `_process_single_ingredient_enhanced` becomes testable per section.

### C.3 `scripts/build_final_db.py` — 11,289 LOC, 164 commits, release chain, L2

213 module-level functions. `build_detail_blob` (6600–8283, 1,684 L) already delegates to 23 section
builders (`derive_non_gmo_audit`, `build_banned_substance_detail`, `_build_canonical_label_ledger`…) but
assembles 35 keys inline in one dict literal (line 7730) and then a dozen more `blob[...] =`
sections inline (`formulation_detail`, `nutrition_detail`, `unmapped_actives`, `score_bonuses`/`penalties`,
`audit`, `banned_substance_detail`, raw counts, dropped reasons, proprietary flags). Five module-level
`global` caches (`_SHARED_INACTIVE_RESOLVER`, `_ACTIVE_BANNED_RECALLED_INDEX`, `IQM_REFERENCE_INDEX`,
`HARMFUL_REFERENCE_INDEX`, `_GOAL_MAPPINGS_CACHE`) are lazy singletons.

**Problem.** The exporter is the second most-changed file (164 commits) and the second most co-changed with
`scoring_v4/*` (53). Its inline sections are pure functions of `(enriched, scored)` that cannot be tested or
reviewed alone. Its 8 lazy imports show it re-deriving presentation from several owners.

**Recommendation (structural, wave 2).** Extract the inline sections of `build_detail_blob` into
module-level section builders *in the same file*, one PR per section, in the order of their churn (use
`git log -L` per section when scheduling). No new module, no new owner, no shim: the dict literal becomes
calls. Verification: byte-identical detail blobs for the 9 canary rebuilds (`scripts/reports/canary_rebuild.py::rebuild_one`),
`test_build_final_db.py` (6,896 L), and a full catalog build diff on frozen inputs (`release_safety/catalog_diff.py`
for the core rows; blob hashes from the harness). Risk low per PR; benefit: each section becomes a unit with
a test, and the churn of the exporter stops landing in one 1,684-line function.

**Behavioral item found here (not a refactor):** `scripts/build_final_db.py::_resolver_status_in` (1122;
the product-level banned/recalled bridge) returns `False` silently at line 1139 when
`_get_active_banned_recalled_index()` or `_get_shared_inactive_resolver()` raises. Per `.claude/rules/release.md` ("a gate only protects you if
something runs it") and AGENTS.md ("under-warning is the worse failure"), a reference-load failure in a
safety bridge should fail the build loudly. **P1, behavioral, needs its own specification and a fail-first
test** (simulate an unloadable index; assert the build stops or the product is held). Related, lower
severity: `:1524` and `:9010` degrade at `debug` level only.

### C.4 `scripts/scoring_input_contract.py` — 6,451 LOC, 130 commits, 3 concepts, fan-in 30, L2

170 functions in four banner-separated sections (row ownership and evidence derivation; scoring rows;
ScoringClassification v1 — "single route/profile seam", line 3536; role classification, line 5978).
`derive_product_scoring_evidence` (1813, 468 L), `build_scoring_classification` (5824, 152 L),
`classify_ingredient_roles` (6373), `declared_serving_dose_input` (6397). Thirty-six `route_*` functions and
38 `_ROUTE_*` constant sets.

**Problem.** Not size: this file is one owner of one contract and its sections are cohesive. The problem is
B.3: routing vocabulary split across the contract, `scoring_v4/route_features.py` and `sports_helpers.py`,
and the contract's role classifier reaching into scorer modules. Evidence that it costs: contract +
`scoring_v4/*` co-change 66 commits; contract + `generic_evidence.py` 21.

**Recommendation (structural, wave 2) — one leaf module for routing vocabulary.** `route_features.py` is
already a leaf (it imports nothing from `scripts/` at module level), so it — not the contract — is the
cycle-free home. Moving constants *into* the contract would force `route_features` to import the contract and
create a genuine top-level cycle; that design is rejected.
- Move the three sports aggregate sets (`sports_helpers.py:22` `SPORTS_PROTEIN_CANONICALS`, `:43`
  `EAA_AGGREGATE_CANONICALS`, `:52` `BCAA_AGGREGATE_CANONICALS` — literal frozensets; `SPORTS_CANONICALS` at
  `:53` is their union and keeps working by importing them) into `route_features`, which `sports_helpers`
  already imports at top level. Then `_role_context` needs no `sports_helpers` import. These three sets are
  **distinct** from the contract's `_ROUTE_BCAA_CANONICALS` (= `BCAA_CANONICALS`, the leucine/isoleucine/valine
  trio, 3789), `_ROUTE_EAA_CANONICALS` (3790) and `_ROUTE_SPORTS_PROTEIN_CANONICALS` (= `PROTEIN_CANONICALS −
  {"protein"}`, 3781) and must not be merged with them; `sports_dose.py` and `sports_formulation.py:129` score
  with the aggregate sets.
- The fiber/enzyme sets (`FIBER_CANONICALS`, `DIGESTIVE_ENZYME_CANONICALS`, `DUAL_USE_ENZYME_CANONICALS`,
  `SYSTEMIC_ENZYME_CANONICALS`) **stay in `route_features`**: it is their matrix owner (`fiber_identity`) and
  uses them itself (121, 476–513, 602–609, 655, 681). Hoist the lazy import at `scoring_input_contract.py:6084`
  into the top-level import block at line 48 (same module, four more names); no cycle, since `route_features`
  is a leaf.
- Immune support: the predicate is one comparison of the taxonomy primary type (`immune_support.py:61`,
  `primary_type_of(product) == "immune_support"`); `_role_context` can read the taxonomy directly. The alias
  expansion (`_active_id` `:227`, `_ALIASES` `:39`, `_row_keys` `:236`, `_matches_any` `:251`) depends on
  `generic_helpers._norm_text`, and `generic_helpers` imports the contract at top level, so moving it into
  `route_features` would create a cycle unless it is rewritten on `route_features`' own
  `_normalize_signal_text` with a byte-equality check on the real corpus. **Default: keep that one lazy import
  and record it as an acknowledged cycle-breaker**; attempt the rewrite only with the F.3 harness.
- Replace `_role_context`'s lazy `router.class_for_product` (6258) with the contract's own
  `build_scoring_classification(product)["route_module"]`, keeping the adapter's `VALID_CLASSES` check
  (`router.py:34-44` raises on an unknown route) — exactly what the adapter does.
- Optionally, in a later PR, move `route_features.py` itself out of `scoring_v4/` (e.g. beside the contract)
  so the package path matches the authority map; five importers change one line each. It is the matrix owner
  of `fiber_identity`, so the matrix entry moves with it: an owner-location change that needs Sean.
- Verification: `test_scoring_input_contract.py` (2,553 L), `test_routing_snapshot_baseline.py`,
  `api_audit/audit_v4_route_consistency.py`, `audit_v4_native_classification_parity.py`, archetype fixtures
  (`scripts/audit_v4_archetype_fixtures.py`); `replay.py` route/subroute equality on the frozen set.
- Risk medium (import-order regressions are caught at import time; semantics unchanged by construction —
  three literal sets move, bodies do not). Benefit: the sports vocabulary joins the fiber vocabulary in the
  one leaf; the contract's lazy import modules go from 7 to 4 (`evidence_resolver`, `probiotic_measurements`,
  `serving_frequency` at 6404, and `immune_support` while the alias expansion stays lazy), and the
  contract→`router`/`sports_helpers` edges of component 1 disappear.

`scoring_input_contract` → `evidence_resolver` (two symbols): move `is_reviewed_branded_material` and
`evidence_indication_categories` to the lower owner they really read (both read curated reference data —
check `scripts/evidence_resolver.py` loaders `load_*` at module level before choosing between
`scoring_reference_resolver.py` and a new small module; a new module requires Sean). Wave 2, small.

### C.5 `scripts/supplement_taxonomy.py::classify_supplement` — 1,117 L, nesting 30, 94 `if` nodes (106 `if`/`elif` source lines), one `return`, L2

A documented precedence tree ("CLASSIFICATION DECISION TREE", R1–R5 rule comments, explicit "checked
before X" ordering), assigning `primary_type` at 59 sites across 19 types, with `None` as a sentinel so
fall-through is explicit. 23 test files, including `test_supplement_taxonomy_determinism.py` and
`test_taxonomy_adversarial_review.py`. Called once, from the enricher's `apply_taxonomy_projection` (17577).

**Problem.** Review cost: a reader must hold 94 nested `if`s to know why a product is `herbal_botanical`. The
order *is* the policy, so any data-driven rewrite is behavioral (§J).

**Recommendation (structural, wave 2–3).** Extract each `# --- X ---` branch into a predicate/decision
function returning `(primary_type, confidence, reasons)` or `None`, and keep the tree as an explicit ordered
list of those functions with the same single return — precedence stays visible and unchanged. Owner
unchanged (`supplement_taxonomy` matrix concept). Verification: corpus-wide equality of
`supplement_taxonomy.{primary_type, secondary_type, percentile_category, classification_reasons}` from the
enriched records on frozen inputs (the harness) plus the 23 files. Risk medium (order mistakes are the
failure mode; the corpus diff catches them). Benefit: nesting 30 → single-digit per function; each rule gets
a name and a test.

### C.6 `scripts/scoring_v4/modules/generic_evidence.py` — 1,893 LOC, 81 commits, 18 lazy imports, L2

`score_evidence` (218, 246 L) and `_recover_verified_primary_ingredient_matches` (830, 179 L). The 18
in-function imports target `evidence_resolver` (nine symbols, including private `_evidence_claim_purposes`
and `_evidence_entry_purposes`), `scoring_input_contract`, `studied_formulas`, `sports_helpers`. Not a cycle
member, so the laziness is habit or import-time cost, not a cycle-breaker. **Recommendation (P3,
structural):** hoist the imports to module level (if import time allows) and export the two private
`evidence_resolver` symbols under public names — the scorer's evidence dimension is a legitimate consumer.
Verification: `test_evidence_resolver.py`, `test_evidence_prominence_ownership.py` (33 commits) and the
score replay. Risk low.

### C.7 `scripts/evidence_resolver.py` — 1,682 LOC, 39 commits, cycle member, L2

`resolve_evidence_for_row` (632, 661 L) is one long decision ladder (numbered comments "5. Check Probiotic
Strain Registry"). It is consumed by both Enrich (`_collect_evidence_data`) and Score (`generic_evidence`,
`b_complex`, `botanical_profile`), which is why it sits in the cycle. **Recommendation (structural, wave 3):**
section the ladder into named steps in the same module after the harness exists; no owner change. Not a
first-wave item: 39 commits and heavy clinical semantics; the corpus evidence diff is the only acceptable
proof.

### C.8 `scripts/batch_processor.py` (2,105 LOC, 18 broad excepts) and `scripts/clean_dsld_data.py`

`BatchProcessor` (39 methods) with a `PerformanceTracker`, resume state, quarantine files and worker
timeouts. The broad `except`s were read (`EVIDENCE_LEDGER.md`): all 18 are log-and-continue with error
accounting (`errors.append`, `batch_logger.error`) or defensive memory/IO fallbacks; the only silent ones are
the handler-close `pass` (1814) and the conservative memory probe (69), both commented. **Verdict: leave alone.** It is the kind of code that should catch
broadly.

### C.9 Shell entry points — `scripts/release_full.sh` (971 L, 53 commits), `scripts/test.sh` (590 L, 26), `batch_run_all_datasets.sh` (520 L, 16)

`release_full.sh` has 19 functions and 8 labelled steps with needs-run predicates (`step1_needs_run`…);
`test.sh` 14 functions (RAM-aware worker cap, machine lock via `scripts/test_lock.py`, release preflights).
Both are covered by tests (`test_release_full_snapshot_gate.py`, `test_rebuild_dashboard_snapshot_order.py`).
**Verdict: leave alone** (ADR-0001; `.claude/rules/release.md` forbids re-implementing the steps). One
documentation finding: `PIPELINE_ARCHITECTURE.md §9` already records that a snapshot failure inside the batch
exits zero — that is a known behavioral item for Sean, not an audit finding.

### C.10 Card-level (L2-card) verdicts for the other 89 promoted modules

Full cards in `probes/cards.md`. Grouped verdicts:

| Group | Modules | Verdict |
|---|---|---|
| `release_safety/` (18, 9,173 LOC) | lock, gates, quarantine, sweeper, registry, protected blobs, index validator, bundle alignment, catalog diff, storage audit, audit log, transient retry, backfill/retire tools | Well-factored: small modules, typed error classes, one shared transient-retry helper (fan-in 11), one lock. Only duplication: `_list_paginated` in `delete_stale_version_dirs.py:637` and `storage_audit.py:539` (29 L, structurally identical) → P3. **Leave alone otherwise.** |
| `api_audit/` L2 (13 of 72; 35,721 LOC total) | verifier CLIs (`verify_cui`, `verify_unii`, `verify_pubchem`, `verify_comptox`, `verify_clinical_trials`, `verify_interactions`, `verify_certifications`, `verify_rda_uls`), FDA syncs, `iqm_identifier_sweep`, `discover_clinical_evidence`, `backfill_unii_from_cache`, `audit_v4_profile_cutover_impact` | Operator tooling with a repeated **per-file HTTP-client-plus-disk-cache** pattern: `_cache_get` in 8 files, `_cache_set` in 7, `_get` in 7, `_make_ssl_ctx` in 6 (`family_maps/api_audit.md`; `census.json: duplication.same_name_private_helpers`). Two of the client classes are exact duplicates (`enrich_chembl_bioactivity.py:108/132` vs `verify_clinical_trials.py:96/120`, 21 + 14 lines). `pubmed_client.py` already is the shared client for the PubMed family (11 importers). **P2 (D.1):** one shared cached-HTTP client under `api_audit/` for the seven verifier classes — a one-policy-many-consumers consolidation, not a new abstraction. Production-adjacent members (`fda_manufacturer_violations_sync` imported by the enricher; `verify_interactions` imported by `build_interaction_db`) are the ones to protect with tests first. |
| `scoring_v4/` other L2 (20) | `gate_safety` (1,468 L, 36 commits), `quality_score` (1,682 L, 67), `confidence`, `dose_safety`, route modules, `generic_dose`/`_transparency`, `botanical_profile`, `sports_helpers`, `immune_support`, `route_features`, `router`, `scored_artifact`, `quality_score_config` | Cohesive per pillar/module; the package's internal layering is the B.3 finding. `quality_score.py` 67 commits with `_pillar_verification` 139 L and `_itemize_dimension` 129 L: fine. **Leave alone** except B.3/D.1 items. |
| Core other L2 | `assessment_readiness` (1,354 L, `_dose_readiness` 354 L), `audit_source_of_truth_contract` (2,191 L), `enrichment_contract_validator` (3,123 L; `_validate_label_ledger_omissions` 461 L), `coverage_gate`, `db_integrity_sanity_check` (1,804 L, 36 `check_*`), `identity_integrity` (`resolve_identity` 375 L, nesting 11), `inactive_ingredient_resolver`, `cert_resolver` (`resolve` 225 L), `probiotic_measurements`, `studied_formulas`, `clinical_applicability`, `dose_assessment` (`build_dose_assessment` nesting 11), `row_ledger` (`build_row_ledger` nesting 13), `unit_converter` (`convert_nutrient` 381 L), `constants` (1,693 L, 109 constants, one section banner), `preflight`, `dsld_api_sync`, `sync_to_supabase` (`sync` 324 L), `iqm_form_evidence`, `validate_safety_copy`, `cleanup_old_versions` (`quarantine_orphan_blob_batch` 453 L), `sweep_quarantine` (`_execute` 303 L), `generate_pharmacist_review_packet` (`build_packet` 310 L) | Validators and gates are long by nature (one check per finding) and are the protection layer; **leave alone**. `constants.py` is a grab-bag (P3: section it; do not split). `unit_converter.convert_nutrient` 381 L and `identity_integrity.resolve_identity` 375 L/nesting 11 are candidates for sectioning *after* the harness (wave 3, P2). |
| `dashboard/` (3) | `data_loader` (1,524 L), `views/quality` (803 L), `app` (nesting 14 in a 29-line dispatcher) | No production imports; coupled by artifact schema only. Findings (L1-verified): `views/audit_section_a/b/c/d.py` (1,417 LOC) are re-exported by `views/__init__.py` but dispatched by neither `app.py` nor `navigation.PAGE_DEFINITIONS` → unreachable UI (P3 deletion, §H); `views/safety_copy.py:32` hard-codes `/Users/seancheick/PharmaGuide ai/assets/reference_data`; `components/score_breakdown.py:88-91` still renders a v3 four-section breakdown (25/30/20/5) and `V4_PILLARS` (line 9) hard-codes maxima that `scoring_v4/config/quality_score.json` owns; `data_loader.py:1424` surfaces `scripts/config/scoring_config.json` (D.4). |
| `submission_review/` (1 L2: `extraction/benchmark.py` 956 L) + `product_submission_import.py` (1,543 L) | Family map verified at the boundary: the only pipeline imports are `product_submission_import.py:503` → `enhanced_normalizer.parse_other_ingredient_disclosure` and `dsld_validator.py:68` → `product_submission_import._required_uuid` (B.3). | **Leave alone** apart from the private-symbol inversion. |

---

## D. Code-quality findings

### D.1 Duplicated logic, classified with AGENTS.md's three shapes

| Duplicate (verified by structural body hash and by reading) | Shape | Owner that already exists | Priority / action |
|---|---|---|---|
| `scripts/enhanced_normalizer.py::_normalize_unii` (116), `scripts/enrich_supplements_v3.py::_normalize_unii` (544), `scripts/api_audit/audit_unii_data_quality.py::_normalize_unii` (64) + four copies of the placeholder set (`_UNII_PLACEHOLDERS` ×2, `_PLACEHOLDER_UNIIS`, `PLACEHOLDER_UNIIS` at `audit_unii_same_tier_conflicts.py:26`) + `scripts/api_audit/audit_unii_same_tier_conflicts.py::normalize_unii` | **false dual brain** (one identity decision, identical today, four files to keep in step) | `scripts/normalization.py` (declared the only normalizer; already owns `classify_folate_form`, unit canonicalization) | **P2, §H.** 21 call sites (normalizer 8, enricher 6, `audit_unii_data_quality` 2, `backfill_unii_from_cache` 2 via import from it, `audit_unii_same_tier_conflicts` 3); 3 test files name it. |
| `scripts/scoring_v4/modules/generic_trust.py::_label_asserted_program_key` (261) and `scripts/scoring_v4/modules/omega_trust.py::_cert_program_key` (200) — 19 identical lines mapping display/rule_id to a program key | **false dual brain**; the exact shape ADR-0004 consolidated into `cert_evidence.py` on 2026-09-16 after a drift bug | `scripts/scoring_v4/cert_evidence.py` (matrix owner `certification_evidence`); `scripts/cert_resolver.py::normalize_program` holds the canonical program-name map | **P1, §H.** 0 tests name either function → write the fail-first test, move one function to `cert_evidence`, route both callers (`generic_trust.py:242`, `omega_trust.py:135,181`). |
| `scripts/scoring_v4/modules/joint_support.py::_row_quantity_mg` (183) and `scripts/scoring_v4/modules/sleep_support.py::_row_quantity_mg` (156) — 31 identical lines of mg conversion | **false dual brain** | `scripts/scoring_v4/modules/generic_helpers.py` (both files already import `has_usable_individual_dose`, `_as_float`, `_norm_text` from it); `scripts/normalization.py::canonicalize_mass_unit` for the unit vocabulary | **P2, §H-adjacent.** 4 call sites, 0 direct tests. |
| `to_breakdown` in `GenericModuleResult`, `OmegaModuleResult`, `ProbioticModuleResult`, `MultiPrenatalModuleResult` — four dataclasses with **identical field lists** (verified) and identical 17-line renderers, consumed at one site (`score_supplements_v4.py:433`) | **one policy, many consumers** (the public `v4_breakdown["module"]` shape) | `scripts/scoring_v4/modules/generic.py` (holds `GenericModuleResult` and the component result types) | **P2, §H.** One `ModuleResult` dataclass (or a shared base) in `generic.py`; 30 test files reference `to_breakdown` as consumers. |
| `scripts/scoring_v4/dose_safety.py::dose_safety_scope` and `scripts/scoring_v4/gate_safety.py::safety_gate_scope` — same contextvar scope pattern, different results | **one pattern, two legitimate owners** | — | Not a defect. Leave. |
| `release_safety/delete_stale_version_dirs.py::_list_paginated` and `release_safety/storage_audit.py::_list_paginated` (29 L) | one policy, two consumers | `release_safety/transient.py` is the shared I/O helper home | P3. |
| `api_audit` HTTP client classes (`UMLSClient`, `GSRSClient`, `PubChemClient`, `CompToxClient`, `ClinicalTrialsClient`, `ChEMBLClient`, `APIClient`): `_cache_get` ×8, `_cache_set` ×7, `_get` ×7, `_make_ssl_ctx` ×6; two exact copies | one policy, many consumers | `scripts/api_audit/pubmed_client.py` is the precedent (shared client, 11 importers) | P2 (operator tooling; schedule after production items). |
| Three UPC normalizers: `scripts/dsld_validator.py::DSLDValidator.normalize_upc` (Clean), `scripts/build_final_db.py::normalize_upc` (digits-only, four GTIN widths), `scripts/sync_to_supabase.py::normalize_catalog_upc` (drops separators to mirror Flutter `upcNormalizeSql`) | **two policies, one topic** (validation, storage normalization, app parity) | none declared | P2: do **not** merge; add one parity test that the three agree on the catalog's real UPCs, and record the owner split in `scripts/GLOSSARY.md` (memory: "same UPC, different label" decisions depend on it). |

### D.2 The 93 `normalize_*` definitions, triaged (the September lesson, applied)

Read individually (`EVIDENCE_LEDGER.md` lists the dump). Outcome:
- **Semantic normalizers under their rightful owner (no action):** `identity/safety.py::normalize_safety_signals`
  ("the ONE normalizer" for safety), `identity/interaction.py` canonical-id normalizers,
  `identity_integrity.py::normalize_label_display`, `cert_resolver.py::normalize_brand/normalize_product/normalize_program`,
  `brand_identity.py::normalize_brand_key`, `normalization.py`'s own six.
- **Identity normalizer outside its owner:** UNII (D.1).
- **Unit canonicalizers beside the owner (inventory before consolidation, Q37 style):** in the enricher
  `_normalize_unit_for_signal` (5953), `_normalize_serving_unit_label` (18191), `_normalize_threshold_unit`
  (19197, delegates partly to `normalization.canonicalize_nutrient_unit`), module-level `_normalize_parent_blend_mg`
  (648); in the normalizer `_normalize_dosage` (1105), `_normalize_daily_value_unit` (2324), `_normalize_label_unit`
  (4664); plus `audit_dv_plausibility._normalize_unit`, `verify_rda_uls.normalize_unit`. Nine unit normalizers
  against two in `normalization.py` and `scripts/unit_converter.py`. **P2:** inventory each one's vocabulary
  and consumers, then route the ones with the same vocabulary to `canonicalize_mass_unit`/`canonicalize_nutrient_unit`.
  Do not build a unit abstraction from one case.
- **Harmless casts or documented mirrors (no action; the September false positive):** `_norm` (29 files),
  `_normalize_text` in `form_factor_normalizer`, `supplement_type_utils`, `ingredient_category_normalizer`
  (docstring says it mirrors `canonical_category`), `inactive_ingredient_resolver._normalize` (docstring:
  "matches build_final_db.normalize_text"), `audit_raw_to_final._normalize_name`, the api_audit `_normalize`
  helpers, `prebiotic_catalog.normalize_prebiotic_text`.
- **Different concerns that share the verb:** `dsld_validator.normalize_upc`, `dsld_api_client.normalize_api_label`,
  `verify_interactions.normalize_direction/normalize_severity`, `scoring_input_contract.normalize_product_evidence_scope`.

### D.3 Complexity hotspots

| Function | Lines | Nesting | Branches | Self-attrs | Verdict |
|---|---|---|---|---|---|
| `SupplementEnricherV3._collect_rda_ul_data` | 2,278 | 18 | 54 `for` loops, 4 nested defs | 20 | C.1 (RDA/UL extraction) |
| `build_detail_blob` | 1,684 | 5 | — | 0 | C.3 (section builders) |
| `SupplementEnricherV3._match_quality_map_impl` | 1,355 | 8 | 27 nested defs | 20 | C.1 (matching core) |
| `EnhancedDSLDNormalizer._process_single_ingredient_enhanced` | 1,296 | 9 | 49 self-calls | 54 | C.2 (context object first) |
| `classify_supplement` | 1,117 | 30 | 94 `if` nodes | 0 | C.5 (named rules, same order) |
| `resolve_evidence_for_row` | 661 | 5 | — | 0 | C.7 |
| `build_row_ledger` (`row_ledger.py:128`) | 210 | 13 | — | 0 | wave 3 sectioning |
| `_render_current_view` (`dashboard/app.py:151`) | 29 | 14 | — | 0 | cosmetic (an if-chain dispatcher); P3 |

137 functions exceed 150 lines; 43 exceed 300. The audit does not recommend touching any of the other 36
over-300 functions: they are validators, CLI `main`s or gates whose length is one check per finding.

### D.4 Configuration, constants, docs

- `scripts/config/scoring_config.json` has no `_metadata`, is read at runtime only by the dashboard
  (`data_loader.py:1424`, `views/audit_caers.py:241`, `views/quality.py:579`, `page_meta.py:55,260`), is cited by `scripts/constants.py:860` as holding "all
  scoring values", and is displayed by the dashboard's config snapshot — while the production scorer reads only
  `scripts/scoring_v4/config/quality_score.json` (ADR-0002). **P2 (behavioral for the dashboard, documentation
  elsewhere):** retire the file or mark it legacy in its own text, point the dashboard at the real config and
  fingerprint, fix the `constants.py` comment.
- `scripts/constants.py`: 1,693 lines, 109 constants, one section banner ("SCORABLE INGREDIENT CLASSIFICATION
  CONSTANTS"), imported by 13 modules. P3: add section banners by consumer; do not split (a split creates
  import churn for no coupling gain).
- Docs drift (P3, docs-only class): `PIPELINE_ARCHITECTURE.md` lines 50 and 125 say engine `4.5.0`; code says
  `4.6.0` (`score_supplements_v4.py:98`). `.claude/rules/scoring.md:44` says "~45-minute full pipeline"; the
  five October full runs report 64–75 minutes of pipeline time (3,838–4,512 s; E.1).
- Eight L2 modules carry their header string *after* `from __future__ import annotations`, so
  `ast.get_docstring` returns nothing (`probes/cards.md` marks them "bare string": `build_final_db`,
  `enhanced_normalizer`, `enrich_supplements_v3`, `verify_unii`, `verify_pubchem`, `verify_comptox`,
  `fda_weekly_sync`, `backfill_unii_from_cache`). P3 cosmetic.

### D.5 Error handling and observability

- 295 broad `except` handlers. The 78 in the eight most-affected files were read and classified:
  log-and-continue with error accounting (batch processor, most of the enricher), zero-out-on-failure (the
  enricher's deliberate safety pattern), fail-closed with a recorded reason (`scoring_input_contract.py:5859-5893`
  sets `failed=True`/`failure_reason`), and **defensive fail-open fallbacks** that return an empty value:
  `build_final_db.py::_resolver_status_in` at 1139 (no log — **P2 behavioral**, C.3; the same loaders are
  unguarded at 1057, 1078, 6806 and 6959, so today the build crashes rather than degrades),
  `build_final_db.py::_active_export_contract` at 1524 and `::_pre_workout_goal_cluster_ids` at 9010 (debug
  level only, P3), `scoring_input_contract.py::_botanical_identity_lookup` at 569 and
  `::_botanical_title_alias_index` at 4998 (a missing `botanical_ingredients.json` silently disables fallback
  evidence/title matching — P3: log once at warning level).
- Logging is not a finding: 1,797 of 1,803 `print` calls are CLI output; library prints are six lines in four
  files. 537 logger calls.
- Module-level mutable state in the core is limited to the exporter's five lazy caches, `unit_converter` (1),
  `quality_score` (1), `batch_processor` (2). Test-isolation note for the exporter: tests that swap data files
  between cases would read stale caches (P3; a `reset_reference_caches()` helper is enough).

---

## E. Performance findings — existing evidence only

### E.1 Measured (from `scripts/products/reports/batch_run_summary_*.txt`, parsed per stage by `census.py`; sha256 of each file in `census.json`)

| Run (38 brands, ~15,420 products) | Wall | Clean | Enrich | Gates | Score | Enrich share |
|---|---|---|---|---|---|---|
| 2026-09-08 10:57 | 2,252 s (37.5 min) | 193 s | 1,675 s | 10 s | 366 s | 74% |
| 2026-09-21 13:35 | 2,665 s | 191 s | 1,942 s | 11 s | 518 s | 73% |
| 2026-10-03 00:32 | 3,583 s | 261 s | 2,215 s | 24 s | 1,075 s | 62% |
| 2026-10-13 02:11 | 4,002 s (66.7 min) | 268 s | 2,521 s | 22 s | 1,184 s | 63% |
| 2026-10-15 17:43 | 4,525 s (75.4 min) | 299 s | 2,880 s | 27 s | 1,299 s | 64% |

- **Trend:** wall time ×2.0 in five weeks for the same brand set. Enrich ×1.7 (109 → 187 ms/product).
  **Score ×3.5 (24 → 84 ms/product)** — the stage that moved most. Clean ×1.5.
- Per brand (Oct 15): enrich median 34.5 s, max 556 s; score median 10 s, max 318 s; clean median 6 s;
  gates median 1 s. The July enrichment summaries (28 brands, 14,193 products) put the median at 0.156 s per
  product, p90 0.30, max 0.75 (GNC: 2,214 products in 460 s).
- Enricher start-up is negligible: "Performance indexes built" median 0.23 s (n=5,776 log lines), and the
  reference-data load adds a second or two per brand subprocess (STAGE 2 banner to index build).
- One anomalous run (2026-10-08 19:46: 16,512 s, enrich 10,598 s) coincides with another job on the machine;
  treat as contention, not a regression.
- CI (`run 39070168203`): fast-rung shard times 404 / 651 / 343 / 390 s; wall 717 s. Shards are assigned
  round-robin by sorted filename (`scripts/test_profiles.py::iter_profile_paths`, `paths[shard_index::shard_count]`),
  so the slowest shard sets the wall. Job durations are 472 / 715 / 403 / 461 s, i.e. ≈65 s of fixed setup
  per job; a balanced fast rung (≈447 s) gives a run-wall floor of ≈510 s (≈−28%).
- Footprint: `scripts/products` 11 GB, `scripts/dist` 4.8 GB, `scripts/final_db_output` 2.5 GB, `scripts/data`
  2.3 GB. Tests are 1.4× production by lines.

### E.2 Hypothesized — needs measurement (each with the command that would measure it; none is a finding)

| Hypothesis | Code evidence (not timing) | Measurement (requires separate approval) |
|---|---|---|
| The score-stage growth comes from re-deriving the scoring classification several times per product. | `build_scoring_classification` is invoked in the score path from `scoring_v4/scored_artifact.py:331`, `scoring_v4/router.py:41` (via `class_for_product`), and `scoring_v4/modules/botanical_profile.py:260,317`; the contract caches rows (`_ROUTE_SCORING_ROWS_CACHE_KEY`) but not the classification result. The enricher also stamps it natively (`enrich_supplements_v3.py:17557`). | `$PG_PYTHON -m cProfile -o /tmp/score.prof scripts/score_products_v4.py --input <one enriched brand dir> --output <scratch>` on stored enriched input (read-only), then `pstats` top 30 by cumulative time. |
| Enrichment cost is dominated by regex/text matching in the identity core. | `_match_quality_map_impl` closure 33 methods / 3,016 LOC; `_regex_pattern_cache`, `_token_bounded_pattern_cache`, `_hyphen_space_pattern_cache` exist, i.e. the authors already found pattern compilation hot. | `replay.py freeze-raw` on one brand into the scratchpad, then `snapshot --workers 1` under `cProfile`. |
| Brand outliers (556 s enrich, 318 s score) are large catalogs, not pathological labels. | Oct 15 per-brand table in `census.json: pipeline_timing.batch_summaries[...].slowest_brands`. | Compare per-product ms across brands from the same run. |

The audit makes **no** concurrency, caching or brand-parallelization recommendation (§J).

---

## F. Testing and equivalence

### F.1 Existing protections (inventory)

Stage manifests + SHA-256 (`stage_manifest.py`); code/reference fingerprints and the freshness gate
(`pipeline_freshness.py`, `scripts/test.sh release` preflight); matrix gate (`audit_source_of_truth_contract.py`);
`enrichment_contract_validator.py` and `coverage_gate.py` in strict mode; export contract validation and
`audit_contract_sync.py` (68 blob keys, 117 core columns); lineage audit `audit_raw_to_final.py` (BLOCKER exits
non-zero); dead-code ratchet `test_no_unreferenced_production_code.py` (`audit_dead_code.py`, 16 `KEEP` entries);
`ci_skip_guard.py`; file-list profiles (`test_profiles.py`: SLOW 20, LOCAL_ONLY 25, RELEASE 11, ARTIFACT 19)
applied centrally in `scripts/tests/conftest.py::pytest_collection_modifyitems`; machine-wide test lock; 251 fixture files
(253 directory entries) including 33 frozen scored canaries (`fixtures/contract_snapshots/_manifest.json`, `test_scoring_snapshot_v1.py`,
refreshed only through `freeze_contract_snapshots.py`), 9 canary rebuilds (`reports/canary_rebuild/`, full detail
blobs from raw labels), archetype fixtures (`audit_v4_archetype_fixtures.py`), canary pins (`regen_canary_pins.py`),
`replay.py` (frozen-input score replay), `release_safety/catalog_diff.py` (release gate on safety transitions).
Pre-existing failures on the pinned revision: **none** (CI run 39070168203 green; local rung receipt in the
handoff: 546 passed).

### F.2 Equivalence surface for future refactoring PRs, mapped to existing tools

| Surface that must be proven unchanged | Existing tool that covers it | Gap |
|---|---|---|
| Score, pillars, status, route/subroute, components | `scripts/audits/quality_redesign/replay.py` (`snapshot` → `compare`, `project_record`) | None for scores. It is **scores only**: `project_record` keeps total, pillars, status, route. |
| Safety classification and transitions (`product_safety_status`, banned/recalled, warned products) at the core-row level | `release_safety/catalog_diff.py::diff_catalogs` (baseline DB vs candidate DB) | Needs a built catalog; covers core rows, not blob text. |
| Full detail blob (warnings text, `safety_warning*` copy, ingredient identities, interaction profile, eligibility) | `reports/canary_rebuild.py::rebuild_one` for 9 labels; `freeze_contract_snapshots.py` whitelist for 33 scored products; `audit_raw_to_final.py` lineage checks | **Corpus-scale gap**: no tool diffs every enriched record / scored record / detail blob between two checkouts on frozen inputs. |
| Cleaned record (row roles, eligibility, dose class, raw taxonomy — 7 cleaner-owned concepts) | `test_cleaner_first_contract_canary.py`; `replay.py freeze-raw` runs Clean but discards the cleaned record | Same gap. |
| Export contracts | `audit_contract_sync.py` (presence), `core_export_model.py`, `FINAL_EXPORT_SCHEMA_V1.md` | Presence, not value equality. |
| Taxonomy outputs (`primary_type`…) | `test_supplement_taxonomy_determinism.py` (142 L), routing snapshot baseline | No corpus diff of the taxonomy fields. |

### F.3 The one tool to build before any Enrich/Clean/Export refactor (extend the owner, do not duplicate)

Extend `replay.py` — it already freezes raw labels, runs Clean → Enrich → Score with a checkout's own modules
under a worker pool, and compares projections — with a `--full` projection that keeps a canonical hash of the
**whole** cleaned, enriched and scored record (volatile fields `enriched_date`, `generated_at`, `run_id`
excluded by an explicit, reviewed list — never by convenience) and, optionally, calls the in-memory blob path
that `reports/canary_rebuild.py::rebuild_one` already uses to add the detail-blob hash. `compare` then
reports, per product, which record changed and the first differing JSON path. Rule for every PR: **no field
is excluded to make a comparison pass; every difference is listed and justified in the PR.** This is the
prerequisite for C.1, C.2, C.3, C.5, C.7 and is itself a tests/audit-tooling change (no production owner).

### F.4 Test-suite findings

- **Fragile sharding**: round-robin by filename (E.1). P2, infrastructure: balance shards from the per-file
  durations already uploaded as `junit-fast-<shard>.xml` artifacts (greedy longest-first assignment; a
  committed `shard_plan.json` refreshed by a script, with round-robin as the fallback when a file is new).
- **Slow enricher boot per test class**: `test_enrichment_regressions.py` (4,699 L, 232 tests) builds a full
  `SupplementEnricherV3` per class ("loads all 26 reference databases"); the state probe shows `enrich_product`
  clears its per-product caches in `finally` and the only cross-product state is diagnostic counters. P2:
  measure the boot cost, then move to a module- or session-scoped enricher fixture where assertions do not
  read counters. Behaviorally neutral; test-only class.
- `test_build_final_db.py`: 6,896 lines, 80 commits — the single most-changed test file. P3 (tests-only):
  split by exporter section when C.3 lands, one test module per section builder.
- `scripts/tests/test_dashboard_smoke.py` renders 12 of the 14 routed dashboard slugs; `caers-audit` and
  `clinical-copy` are never rendered. P3 (tests-only): add them to `view_renderers`.
- 21 `skipif` markers and only 2 inline `pytest.mark.slow`: profile membership lives in `test_profiles.py`
  lists. That is deliberate and CI-enforced (`ci_skip_guard.py`); no change recommended.
- Coverage is not measured anywhere (no `pytest-cov` in the workflow). P3: a coverage artifact per shard would
  let the roadmap target characterization tests where the mega-files are thin; not a gate.

---

## J. Changes NOT recommended (with reasons)

| Not recommended | Why |
|---|---|
| Move-plus-stub relocation of enricher collectors (moving methods to new files that call back into the class) | Relocates complexity without removing coupling; the closures show the shared core is the coupling. Rejected in September for the same reason. Only the three seams in C.1, each with an explicit context/inputs object, are proposed. |
| A "label fact provider" or any abstraction over the enricher's topic readers | Ledger Q37: inventory the readers first; no abstraction from one case. |
| Rewriting `classify_supplement` as a data-driven rule table | The branch order is the policy (R1–R5, "checked before X"); a table reorders precedence silently. C.5 keeps the order and names the branches. |
| Splitting `scoring_input_contract.py` by size | It is one owner of one contract; its problem is the scorer-package dependency (B.3), which the vocabulary consolidation fixes without a split. |
| Touching `scripts/scoring_v4/config/quality_score.json` magnitudes, dose thresholds, or any scoring policy | Behavioral; out of scope by the brief; owned by `/pg-scoring-change` and Sean. |
| Brand-level parallelism in `batch_run_all_datasets.sh`, caching across brands, or concurrency in the enricher | 16 GB machine, one-heavy-job rule, log/manifest ordering and reproducibility risk; E.2 hypotheses must be measured first. |
| Replacing `print` with logging across the api_audit CLIs | 1,797 of 1,803 prints are CLI output; no observability gain. |
| Consolidating the 2–4-line `_norm`/`_safe_dict`/`_safe_list`/`_clamp` helpers into a shared util module (55 same-name helpers across 3+ files) | No decision lives in them; a shared module adds an import to 50 files and conflicts across active lanes for no change-safety gain. Record the counts; do nothing. |
| Refactoring `release_safety/`, `test.sh`'s lock/worker logic, `release_full.sh` steps, `batch_processor.py`, the validators and gates | Recently tuned, well structured, or protection code where length is one check per finding; ADR-0001 and `.claude/rules/release.md` forbid re-implementing the release steps. |
| Changing the enricher's zero-out-on-failure error handling or the broad `except`s in the batch processor | Deliberate safety and resilience semantics; changing them is behavioral. |
| Deleting `scripts/config/scoring_config.json` unilaterally | It is surfaced to the operator by the dashboard; retiring it is a (small) product decision — D.4 asks for it, the audit does not do it. |
| Relocating `scoring_v4/route_features.py` as a whole in the first pass | Import churn across five importers; the constants that cause the inversion can move without it. |

---

## H. First wave — the five highest-value, lowest-regression-risk improvements

Ranked by the four factors (maintainability gain 1–5 ↑, regression risk 1–5 ↓, effort S/M/L, churn of the
affected code). LOC is reported, never a factor.

| # | Change | Gain | Risk | Effort | Churn of affected code | Validation class (AGENTS.md) | Rollback |
|---|---|---|---|---|---|---|---|
| 1 | **Balance CI shards by measured duration.** Add a greedy longest-first plan built from the uploaded junit timings; `scripts/test.sh`/`test_profiles.py` read `shard_plan.json`, fall back to round-robin for unknown files. Balanced fast rung ≈447 s; with the ≈65 s fixed per-job setup (job durations 472/715/403/461 s) the run-wall floor is ≈510 s, ≈28% shorter than today's 717 s, on every push. | 4 | 1 | S–M | `test.sh` 26, `test_profiles.py` | Infrastructure: harness checks + one green CI; `ci_skip_guard` unchanged. | Revert the plan file; round-robin resumes. |
| 2 | **One UNII normalizer.** Add `normalize_unii` and the placeholder set to `scripts/normalization.py`; import it in `enhanced_normalizer.py`, `enrich_supplements_v3.py`, `api_audit/audit_unii_data_quality.py`, `api_audit/backfill_unii_from_cache.py` (today imports it from `audit_unii_data_quality`), `audit_unii_same_tier_conflicts.py`; delete the four function copies and the four placeholder sets. | 3 | 1 | S | normalizer 114, enricher 268 (identity path) | Behavioral-code class by the table (Clean/Enrich code), although semantics are identical by hash: fail-first test asserting the shared function is the one called, owner tests (`test_ingredient_matching_regression.py`, the 3 UNII tests), full-fast CI; trips the freshness gate (§I). | Revert one commit. |
| 3 | **One certification program key.** Move `_cert_program_key`/`_label_asserted_program_key` (identical) into `scripts/scoring_v4/cert_evidence.py` as the owner's public function; route `generic_trust.py:242` and `omega_trust.py:135,181`; add the missing test (there is none today). | 4 | 1 | S | `generic_trust` / `omega_trust` (cert logic drifted once before: ADR-0004) | Scoring-module code: fail-first test, `test_v4_quality_score.py`, `replay.py` score equality on the frozen set (Trust pillar), CI. | Revert one commit. |
| 4 | **One module-result type.** Replace the four identical result dataclasses' `to_breakdown` with one `ModuleResult` in `scoring_v4/modules/generic.py` (same fields, same dict shape); the public `v4_breakdown["module"]` contract is unchanged by construction. | 3 | 2 | S–M | route modules 10–27 commits each | Scoring code: 30 consumer test files, `replay.py` equality (breakdown is inside the artifact), archetype fixtures, CI. | Revert one commit. |
| 5 | **Delete the unreachable dashboard section views** (`views/audit_section_a/b/c/d.py`, 1,417 LOC, their `views/__init__.py` exports and the four `page_meta` keys), after confirming with the dead-code proof tags that nothing else names them (the ratchet currently sees only the `__init__` re-export). | 3 | 1 | S | dashboard (low) | Dashboard only; `test_dashboard_smoke.py` renders 12 of the 14 routed slugs (`caers-audit` and `clinical-copy` are not in its `view_renderers` — a test gap in its own right, F.4); no production change. | Revert one commit. |

Same-day companions (too small to rank separately, same validation classes): `_row_quantity_mg` ×2 →
`generic_helpers` (D.1) — migrating, in the same commit, the six path-keyed `legacy_debt_main_0b7bf3f7`
allowlist entries in `scripts/audit_scoring_contract_leaks.py:130-136` (the scan is `V4_DIR.rglob("*.py")`),
or `scripts/tests/test_scoring_contract_leak_audit.py` fails; `_required_uuid` out of
`product_submission_import` into the Clean-side owner it validates for (`scripts/label_record_contract.py` or
`dsld_validator`), removing component 2; the three docs/rule pointer fixes (engine version, 45-minute,
`constants.py:860`). Component 3 (`_warning_only_identity_labels`) is **not** a companion: Sean decided on
2026-10-18 that export owns the rule (B.3); nothing moves.

**Behavioral items surfaced, for Sean, not for the refactor train:** the inconsistent guard in
`build_final_db.py::_resolver_status_in` (1139; P2 — the same loaders are unguarded elsewhere, so the build
crashes rather than degrades today; the fix is to fail loudly at the bridge too); the legacy
`scoring_config.json` surfaced as live (P2); the hard-coded Flutter path in `dashboard/views/safety_copy.py:32`
(P3 — it must be a configured path).

---

## G. Prioritized roadmap

**Wave 1 (now; independent of each other; no corpus run needed for #1 and #5):** the five items in §H plus
the same-day companions. Items 2–4 touch pipeline code and therefore trip the freshness gate: land them in
the same window as the next planned corpus run (the handoff already lists one pending Sean's omega decision),
not between releases.

**Wave 1.5 (prerequisite for everything below):** the full-artifact `replay.py --full` projection (F.3), plus
capturing a **baseline** on the current 38-brand frozen set at the commit before wave 2 starts.

**Wave 2 (medium complexity; one PR each; each proven by the F.3 baseline):**
- One leaf home for routing vocabulary (C.4): the sports sets and the immune alias table into
  `route_features`, `_role_context` without scorer or router imports, `_archetype` moved out of the assembler's private namespace into a
  small shared owner the assembler imports (candidate: `generic_helpers`, which already computes Dose from it;
  if a new module is preferred it needs Sean). Removes the substantive part of component 1.
- Exporter section builders (C.3), section by section, by churn.
- `classify_supplement` named branches in fixed order (C.5).
- The two private-symbol moves in `evidence_resolver`/contract (C.4 tail) and the probiotic private-token
  import (`studied_formulas` → `probiotic_measurements._label_designation_tokens`): export public names.
- api_audit shared cached-HTTP client (C.10), starting with the two exact-duplicate classes.
- Unit-normalizer inventory (D.2) and the UPC parity test (D.1).

**Wave 3 (larger; each needs its own design review against the F.3 baseline and the matrix):**
- Enricher extraction in the order interaction profile → matching core with a `MatchContext` → RDA/UL
  collection (C.1). The matching-core extraction is the only item in this audit that changes the enricher's
  internal architecture; it should be designed as its own ADR (owner, context object, diagnostics contract)
  and, because `MatchContext` is a new owner object, approved by Sean.
- Normalizer per-product context object, then sectioning `_process_single_ingredient_enhanced` (C.2).
- Sectioning `resolve_evidence_for_row`, `convert_nutrient`, `resolve_identity`, `build_row_ledger` (C.7, C.10).

**Dependencies.** Wave 2 and 3 depend on wave 1.5. Wave 3's matching-core step depends on wave 2's vocabulary
consolidation only insofar as both touch `scoring_input_contract` imports — sequence them, do not run them in
parallel lanes. Nothing in the roadmap depends on a scoring-policy decision.

---

## I. PR strategy

- **One refactor per PR**, each independently revertible, each with: the owner named, the exact symbols moved
  (line ranges at the base commit), the `self.*`/global census of anything extracted, the tests run (named
  files or nodes, per AGENTS.md "iteration is targeted"), and the F.3 comparison output attached with every
  difference justified.
- **Baseline before, compare after.** For Clean/Enrich/Score PRs: `replay.py snapshot` (scores) and `--full`
  (records) on the frozen 38-brand set, baseline from the base commit, candidate from the PR head. For Export
  PRs: canary rebuilds byte-identical, `catalog_diff.py` on a candidate build from frozen inputs, blob hashes.
  For CI/test-only PRs: the harness checks and one green CI.
- **The freshness constraint is the schedule.** Every PR that edits a file under a stage's transitive import
  set changes that stage's code fingerprint; the release preflight then requires rebuilding every brand from
  the earliest stale stage. Batch wave-1 items 2–4 and all of wave 2/3 into windows that end with the corpus
  run already planned for other reasons; never land one structural PR between a corpus run and a release.
- **Validation class per PR** is the AGENTS.md table's class for the files touched (infrastructure for #1 and
  #5; behavioral-code for anything under `scripts/` on the pipeline path, even when semantics are identical by
  construction — the table keys on what changed, and the F.3 comparison is what makes the behavioral class
  cheap to satisfy).
- **Never weaken a test to pass a refactor.** A pin that moves is either a defect in the refactor or a
  pre-existing stale pin to be corrected against source and policy (AGENTS.md "stale tests"); record which.
- **Rollback** is `git revert` of the single PR; no PR in this roadmap changes a stored data format, a schema
  version or a public field, so no migration or compatibility shim is needed. If a PR is reverted after a
  corpus run, the fingerprints change again and the run is stale — another reason to batch.
- **Review**: fresh-context reviewer with the requirement, the matrix owners and the diff only (CLAUDE.md).

---

## Appendix 1 — Recommendation register (all items, four factors)

| ID | Item | Priority | Type | Gain | Risk | Effort | Churn | Order |
|---|---|---|---|---|---|---|---|---|
| R1 | CI shard balancing | P2 | infra | 4 | 1 | S–M | 26 | wave 1 |
| R2 | UNII normalizer under `normalization.py` | P2 | structural | 3 | 1 | S | 114/268 | wave 1 |
| R3 | Cert program key under `cert_evidence.py` | P1 | structural | 4 | 1 | S | low | wave 1 |
| R4 | One `ModuleResult` | P2 | structural | 3 | 2 | S–M | 10–27 | wave 1 |
| R5 | Delete unreachable dashboard views | P3 | deletion | 3 | 1 | S | low | wave 1 |
| R6 | `_row_quantity_mg` under `generic_helpers` (+ migrate six path-keyed leak-allowlist entries) | P2 | structural | 2 | 1 | S | low | wave 1 |
| R7 | `_required_uuid` to the Clean-side owner; `_warning_only_identity_labels` ownership — **decided 2026-10-18 (Sean): export owns warning-only eligibility, identity owns identity findings, release validation verifies containment; no code change** | P3 | structural / decided | 2 | 1 | S | low | wave 1 (`_required_uuid` only) |
| R8 | Docs/rule pointers (engine version, 45-minute, `constants.py:860`) | P3 | docs | 2 | 0 | S | — | wave 1 |
| R9 | Inconsistent guard in the exporter's banned/recalled bridge → fail loudly like its unguarded neighbours | P2 | **behavioral** | 3 | 2 | S | 164 | Sean |
| R10 | Legacy `scoring_config.json` surfaced as live | P2 | **behavioral (dashboard)** | 3 | 1 | S | — | Sean |
| R11 | `replay.py --full` equivalence projection | P1 | tooling | 5 | 1 | M | — | wave 1.5 |
| R12 | Routing vocabulary: hoist 6084; sports sets into the leaf `route_features`; `_role_context` calls the contract directly (keeping `VALID_CLASSES`); fiber sets stay with their matrix owner; immune alias expansion stays lazy unless rewritten leaf-safe | P1 | structural | 4 | 3 | M | 130/66 co-change | wave 2 |
| R13 | `_archetype` out of the assembler's private namespace | P2 | structural | 3 | 2 | S | 67 | wave 2 |
| R14 | Exporter inline sections → section builders | P1 | structural | 4 | 2 | M (many S PRs) | 164 | wave 2 |
| R15 | `classify_supplement` named branches, same order | P2 | structural | 4 | 3 | M | 28 | wave 2 |
| R16 | Contract → evidence_resolver private symbols; probiotic private token | P3 | structural | 2 | 1 | S | — | wave 2 |
| R17 | api_audit shared cached-HTTP client | P2 | structural | 3 | 2 | M | low | wave 2 |
| R18 | Unit-normalizer inventory and routing to `normalization.py` | P2 | structural (inventory first) | 3 | 2 | M | — | wave 2 |
| R19 | UPC normalizer parity test + glossary entry | P2 | tests/docs | 3 | 1 | S | — | wave 2 |
| R20 | Enricher: interaction profile extraction | P1 | structural | 4 | 2 | M | 268 | wave 3 |
| R21 | Enricher: matching core behind `MatchContext` (new owner object: ADR + Sean) | P1 | structural (ADR) | 5 | 4 | L | 268 | wave 3 |
| R22 | Enricher: RDA/UL collection to the calculator/exposure owners | P2 | structural (safety surface) | 4 | 4 | L | 268 | wave 3 |
| R23 | Normalizer per-product context, then sectioning | P2 | structural | 4 | 3 | L | 114 | wave 3 |
| R24 | Sectioning `resolve_evidence_for_row`, `convert_nutrient`, `resolve_identity`, `build_row_ledger` | P3 | structural | 2 | 2 | M | 39 | wave 3 |
| R25 | Session-scoped enricher fixture for slow tests (measure first) | P2 | tests | 3 | 1 | S | — | any |
| R26 | Split `test_build_final_db.py` by section when R14 lands | P3 | tests | 2 | 1 | M | 80 | wave 2 |
| R27 | `constants.py` section banners; docstrings after `__future__` | P3 | cosmetic | 1 | 0 | S | — | any |
| R28 | Hard-coded Flutter path in `safety_copy.py:32` → configured | P3 | **behavioral (dashboard)** | 2 | 1 | S | — | any |
| R29 | Exporter/contract fail-open fallbacks logged at warning (`_active_export_contract`, `_pre_workout_goal_cluster_ids`, `_botanical_identity_lookup`, `_botanical_title_alias_index`) | P3 | behavioral (logging only) | 2 | 1 | S | — | any |

## Appendix 2 — How to reproduce

```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/audits/architecture_audit_20261017/census.py                 # census.json, census.md (pinned to 5fb2be1ca)
"$PG_PYTHON" scripts/audits/architecture_audit_20261017/probes/class_state.py scripts/enrich_supplements_v3.py SupplementEnricherV3 --prefix _collect_
"$PG_PYTHON" scripts/audits/architecture_audit_20261017/probes/class_state.py scripts/enhanced_normalizer.py EnhancedDSLDNormalizer --prefix _process_ --prefix normalize_product
"$PG_PYTHON" scripts/audits/architecture_audit_20261017/probes/structure_cards.py
"$PG_PYTHON" scripts/audits/architecture_audit_20261017/census.py --check-refs AUDIT.md
```
