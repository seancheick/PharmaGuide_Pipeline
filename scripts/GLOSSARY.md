# PharmaGuide Glossary

> Last verified against executable code: 2026-08-25

This is the canonical vocabulary for pipeline, enrichment, scoring, release,
tests, and operator communication. Add a term here before introducing a new
contract name elsewhere.

## Pipeline and release terms

| Term | Meaning |
|---|---|
| **Full-corpus run** | `bash batch_run_all_datasets.sh` with no `--targets`. Runs Clean → Enrich → Score for every eligible brand directory, then rebuilds the snapshot and starts the full release if every brand succeeded. |
| **Targeted run** | A batch run with `--targets`. It is pipeline-only by default; downstream snapshot/release work requires explicit `--release`. |
| **Pipeline-only** | Clean/Enrich/Score work without rebuilding or publishing the catalog. Selected explicitly with `--pipeline-only`; also the safe default for targeted runs. |
| **Strict release gates** | Fail-closed pre-score validation selected by `--strict-release-gates`. Batch runs always enable it. Contract, coverage, or stage-ownership failures stop that brand before scoring completes. |
| **Stage manifest** | `.stage_manifest.json`, the checksum-bearing ownership record for one successful Clean, Enrich, or Score run. It is a control file, never a product. |
| **Owned output** | A product JSON named and hashed by the current stage manifest. Unowned, missing, changed, or stale JSON is rejected in strict mode. |
| **Run ID** | Path-safe identifier shared across enrichment, gates, scoring, and reports for one operational run. |
| **Snapshot** | The paired catalog artifacts in `scripts/final_db_output/` and `scripts/dist/`, built from all current per-brand Enrich/Score outputs. |
| **Candidate** | A temporary sibling directory used to build and gate a proposed snapshot without touching the live snapshot. |
| **Candidate-only build** | A fully gated snapshot build preserved at a new, explicit output path. It stops before live promotion, Supabase upload, Flutter import, cleanup, commit, or push. |
| **Promotion** | Atomic replacement of both live snapshot directories after every candidate gate passes. Failed candidates are deleted; the last good live snapshot remains. |
| **Release** | The auto-smart workflow in `scripts/release_full.sh`: ensure the snapshot is current, update images and interactions when needed, run strict gates, then sync Supabase and import the Flutter bundle. |
| **Auto-smart** | A release step runs only when inputs, checksums, or manifests show that its output is stale. It is not permission to skip gates. |
| **Contract quarantine** | A product intentionally excluded from the shipped catalog because its output cannot satisfy the export contract, while the build continues and records the exclusion. |
| **Contract failure** | A systemic or required-contract error that stops candidate promotion or release. |
| **Scoring snapshot contract** | Per-product regression fixtures checked immediately before Supabase/Flutter publication. Intentional deltas must be reviewed and explicitly re-frozen. |
| **Scoring integrity snapshot** | A self-hashed, manifest-owned freeze of per-product routes, scores, pillars, statuses, verdicts, exclusions, artifact hashes, and payload byte accounting. It is the comparison authority for one integrity candidate; it is not a scoring input. |
| **Routing feature shadow** | A self-hashed, manifest-owned, measure-only table of label-intent and panel-composition facts recomputed from enriched inputs. It never changes route or catalog eligibility; reviewed gold cases and threshold selection consume it before production predicates change. |
| **Routing gold review** | A report that binds one exact baseline/candidate routing-shadow hash pair, assigns every changed product to an approved review group, and fails closed on any unreviewed transition or changed corpus. It records route expectations; it is never a classifier input. |
| **Artifact freshness** | Proof that catalog, manifest, interactions, and upstream product outputs describe the same current state. |

## Canonical stages

| Stage | Authority | Input → output |
|---|---|---|
| **Clean** | `clean_dsld_data.py` + `enhanced_normalizer.py` | Raw DSLD JSON → normalized rows and source-of-truth row roles |
| **Enrich** | `enrich_supplements_v3.py` | Clean rows → canonical identity, safety, RDA/UL, evidence, taxonomy, and scorer inputs |
| **Pre-score gates** | `enrichment_contract_validator.py`, `coverage_gate.py`, `stage_manifest.py` | Enriched outputs → pass/fail decision before Score |
| **Score** | `score_products_v4.py` + `scoring_v4/scored_artifact.py` | Enriched rows → complete v4 scored artifacts |
| **Build** | `build_final_db.py` | Enriched + v4 scored artifacts → validated export candidates; no rescoring |
| **Snapshot** | `rebuild_dashboard_snapshot.sh` | All per-brand outputs → gated `final_db_output/` + `dist/` |
| **Release** | `release_full.sh` | Gated `dist/` → product images, interaction DB, Supabase, Flutter bundle |

## Identity and ingredient terms

| Term | Meaning |
|---|---|
| **IQM** | Ingredient Quality Map: `scripts/data/ingredient_quality_map.json`. Read the live `_metadata` block for its schema version and parent count; do not copy those drifting values into documentation. |
| **Parent** | Canonical ingredient family identified by a stable snake-case key, such as `magnesium`. |
| **Form** | A specific salt, chelate, extract, strain, source, or delivery form under a parent. |
| **Canonical ID** | Stable machine identity selected by deterministic exact/canonical/bounded-alias matching. Display text is not identity. |
| **Printed name** | Full ingredient name as printed on the label. It is retained even when a verified branded token is extracted. |
| **Branded token** | Separately stored verified brand marker; it never replaces the printed name. |
| **Marker contribution** | A bioactive delivered by a source ingredient. The source keeps its identity; the marker is not promoted into a duplicate active row. |
| **Same-identity alias** | A reviewed exact printed-name alias that identifies the IQM parent itself. It may override a broader structured source/group identity only through `alias_identity_scope="same_identity"` or the form's explicit `same_identity_aliases`. |
| **Source-preparation alias** | A source, carrier, brand preparation, or botanical-to-marker clue that may select a form only after primary parent identity is established. It never creates primary identity by itself. |
| **Parent-total row** | A declared nutrient total that groups subforms. It is preserved for label fidelity but excluded from duplicate scoring when its children carry the form detail. |
| **Blend header** | A declared proprietary/structural blend container. It is not an individually dosed active. |
| **Blend member** | A child ingredient linked to a blend header by stable parent linkage. A display-only child may remain visible without becoming independently scoreable. |
| **Scorable row** | An active ingredient row that satisfies cleaner/enrichment eligibility and the shared scoring-input contract. |
| **Label active projection** | A typed scoring row reconstructed from one exact mapped, dose-bearing source label active when the form-quality list has no ordinary scorable row. It retains the source path and participates in routing, materiality, dose, and evidence matching. It is not synthetic product-level evidence or a blend total. |
| **Display-only row** | A label-faithful row retained for explanation but excluded from independent score math. |
| **Mapped coverage** | Fraction of score-eligible active rows with a usable canonical mapping, computed by the shared scoring-input contract. |
| **Row ledger** | The exact one-record-per-source-row reconciliation contract. Each record owns a stable row reference, source section/role, score eligibility, mapping disposition, reason code, final destination, and optional owner reference. |
| **Source descriptor** | A quantified label row that describes the material supplying an owner nutrient but is not an independent clinical exposure. It remains linked to its owner in the row ledger with `cleaner_row_role=source_descriptor`, `score_eligible_by_cleaner=false`, and `dose_class=source_material_mass`. |
| **Owner row** | The source row that owns a form or nested component. Owned components remain traceable in the row ledger but do not independently inflate mapping coverage unless the cleaner explicitly marks the child score-eligible. |
| **Source inactive row** | A row printed in the label's Other Ingredients section and preserved as inactive. It is distinct from an active row later reclassified as inactive. |
| **Active reclassified inactive** | A row originating in Supplement Facts/actives that was deliberately moved to the inactive destination with a row-specific reason. Aggregate `DROPPED_AS_INACTIVE` telemetry is not sufficient evidence of this transition. |

## IQM form fields

| Field | Contract |
|---|---|
| `bio_score` | 0–15 form-quality signal. For systemic actives it represents absorption/bioavailability evidence; for local/matrix actives it represents relevant form and delivery-to-site confidence. |
| `natural` | Whether the form is supported as naturally derived. |
| `score` | Legacy `bio_score + 3` when `natural=true`, capped at 18. Do not use this value as pure bioavailability. |
| `absorption_structured` | Structured value/range/quality/notes evidence. It must not claim more precision than the supporting source. |
| `alias_identity_scope` | Reviewed identity authority for a form alias. `same_identity` permits exact parent-identity recovery; `source_preparation` excludes the form and its aliases from primary identity indexes. |
| `same_identity_aliases` | Narrow per-alias alternative to form-wide `same_identity`; only exact listed labels receive parent-identity authority. |
| `source_form_aliases` | Parent-scoped form-selection clues evaluated only after the cleaner/reviewer has established that IQM parent. They are absent from global identity indexes. |

## Product taxonomy terms

| Term | Meaning |
|---|---|
| **Single vitamin / single mineral** | Exactly one distinct quantified vitamin or mineral identity after canonical identity deduplication. Multiple label forms of the same identity remain single. |
| **Vitamin complex** | Two or more distinct quantified vitamin identities with no mineral identity and no more-specific product class such as B-complex or multivitamin. |
| **Mineral complex** | Two or more distinct quantified mineral identities with no vitamin identity and no more-specific product class such as electrolyte. |
| **Vitamin/mineral combo** | A mixed panel containing both vitamin and mineral identities that does not meet the broad multivitamin contract. |
| **Name-dominant identity** | A multi-row product whose bounded title names exactly one clinically meaningful identity while the companion does not define the product. This may retain a single-family cohort, but never sets `is_single_scorable_active=true`. |

## Production scoring terms

| Term | Meaning |
|---|---|
| **V4 quality score** | The only shipped public score. Stage 3 produces the auditable one-decimal value; final export projects it half-up to a whole number under the canonical `quality_score_v4_100` field. |
| **Scored artifact** | The sole Stage-3 output produced by `build_scored_artifact()`: v4 score/status/pillars, shared coverage and strict diagnostics, safety/verdict state, provenance, and compatibility mirrors. |
| **Quality score status** | `scored`, `suppressed_safety`, or `not_scored`. Status controls whether a public number is allowed. |
| **Clean-label policy registry** | The non-verdict registry of reviewed additive preferences that may inform consumers and apply a small quality-hygiene penalty. An active policy requires explicit jurisdiction, authoritative evidence, penalty, and consumer copy. Review candidates remain inert and never become safety blocks or score penalties. |
| **Product safety status** | Catalog-level safety-gate outcome exported as `product_safety_status`: `blocked`, `unsafe`, `caution`, `no_known_catalog_concern`, or `not_assessed`. It is independent of quality tier, score, mapped coverage, and personalized interaction risk. |
| **Quality assessment status** | Whether the catalog assessment completed: `complete` for scored or safety-suppressed results, `partial` when incomplete identity/payload prevented a quality score, or `failed` when assessment itself was unavailable or invalid. Exported as `quality_assessment_status`. |
| **Assessment readiness** | The single typed decision covering identity, dose, evidence, verification, and route completion. Every dimension is `complete`, `incomplete`, or `not_applicable`. Identity, dose, verification, and route are release-enforced; evidence-review completeness is measured separately so an unfinished curation backlog is never mistaken for weak product quality. |
| **Catalog disposition** | The product-level decision that distinguishes a scoring candidate from an intentionally non-scoreable QA record. `intentional_non_scoreable` requires explicit label evidence such as external-only use, professional formulation material, culinary or nutrition-beverage use, sweetener use, an exact standalone carbohydrate-powder identity outside the current rubric, or a verified emergency-only policy signal that agrees with the label; it never makes a product live and carries a typed reason plus source paths. |
| **Material active** | A score-eligible active classified as `primary`, `claim_prominent`, or `major`. Its evidence and dose assessments must complete. Residual adjunct rows stay visible and reconcile through the row ledger without creating a material-readiness requirement. |
| **Evidence assessment state** | Per-active result: `evaluated_supported`, `evaluated_limited_or_negative`, `not_yet_evaluated`, or `not_applicable`. A missing clinical match is never treated as an evaluated negative result. |
| **Evidence review completeness** | Whether every material active has a documented evidence assessment. `not_yet_evaluated` means the registry review is unfinished; it does not assert that clinical evidence is absent and does not by itself create low score confidence. |
| **Quality score confidence** | Reliability of the completed score calculation given identity, label completeness, verification, and reviewed evidence applicability. It is distinct from the Evidence pillar's support strength and from evidence-review backlog coverage. |
| **Verification assessment state** | Product-level result: `verified_present`, `verified_absent`, or `not_evaluated`. `verified_absent` requires a completed current-registry evaluation and is distinct from a missing collector or unavailable registry. |
| **Raw v4 score** | `raw_score_v4_100`; audit math only. It is never substituted for a suppressed public score. |
| **Compatibility mirrors** | `score_100_equivalent` and `score_display_100_equivalent`; exact /100 mirrors of the v4 public score, not a legacy /80 conversion. |
| **Quality pillars** | Formulation 20, Dose 20, Evidence 20, Transparency 15, Verification 15, Formula & quality checks 10 (internal key: `safety_hygiene`). |
| **V4 module** | One category-aware scoring route: `generic`, `probiotic`, `multi_or_prenatal`, `b_complex`, `sports`, `fiber_digestive`, or `omega`. |
| **V4 scoring archetype** | The purpose-fit normalization profile selected inside the six-pillar assembler after module routing, such as `generic_single_molecule`, `b_complex`, or `sports_pre_workout`. It is not a second product taxonomy or routing system. |
| **Synthetic archetype fixture** | A reviewed enriched-product input with a locked production-scoring outcome used to validate one V4 scoring archetype. Fixtures call `build_scored_artifact()` and contain no copied scoring formulas. |
| **Blinded reviewer benchmark** | A version-locked comparison in which qualified human reviewers assess a frozen product sample without access to the engine score, tier, pillars, verdict, or other reviewers' ratings. |
| **Benchmark freeze** | The immutable sample, label-fact inputs, engine/config provenance, baseline outputs, reviewer instructions, and analysis plan recorded before reviews begin or score-changing data is merged. |
| **Reviewer packet** | The shareable benchmark artifact containing product label facts and blank review fields. It excludes every engine output used in the comparison. |
| **Benchmark baseline key** | The held-back mapping from benchmark IDs to DSLD IDs and frozen engine outputs. It is not distributed to reviewers and is opened only after ratings are locked. |
| **Fixed reviewer panel** | The same three independently registered reviewers rating every frozen benchmark product under stable reviewer slots. This complete target-by-rater design is required for the primary two-way random-effects ICC. |
| **Reviewer registry** | The access-controlled record of reviewer identity, fixed slot, credentials, license verification, experience, conflicts, training, and attestations. Reviewer identities never enter the shareable product packet. |
| **Response lock** | A content-hashed declaration that the reviewer registry and append-only response file are complete before the development baseline key may be opened. |
| **Candidate lock** | The statistician- and clinical-owner-approved, content-hashed list of calibration candidates, mechanistic rationale, and expected direction frozen before the sealed holdout may be opened. |
| **Aggregate clinical evidence identity** | One clinical-evidence record scoped to a required set of disclosed canonical ingredients rather than any one component. Enrichment emits it once only when the complete identity set is present; scoring sums convertible daily component doses and fails closed when a required component or unit is missing. |
| **Router** | `scoring_v4/router.py`, the sole authority for v4 module dispatch. |
| **Safety suppression** | BLOCKED/UNSAFE products retain verdict/evidence but ship a null public score with `quality_score_status=suppressed_safety`. |
| **Completeness exclusion** | Products without usable identity/payload become `NOT_SCORED` and are quarantined from the live catalog. Missing disclosure can instead remain scoreable as explicit soft debt. |
| **Verdict precedence** | BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE. |

Deprecated `/80` export fields (`score_quality_80`, `score_display_80`) must
never be reintroduced. Final export rejects any non-v4 Stage-3 artifact.

## Dose and folate terms

| Term | Meaning |
|---|---|
| **Adequacy exposure** | Minimum/recommended daily exposure (`per_day_min`) used for adequacy. |
| **Safety exposure** | Maximum daily exposure (`per_day_max`) used for UL and other safety comparisons. |
| **Daily serving resolver** | `serving_frequency.py`, the sole policy for converting label serving directions and their provenance into a daily range. Scoring, interaction thresholds, reviewer facts, audits, and consumer cadence copy delegate to it. |
| **CFU normalization** | Enrichment-owned parsing of probiotic label text into `probiotic_data.total_cfu`, `total_billion_count`, per-strain dose evidence, and guarantee provenance. The nutrient unit converter does not interpret CFU. |
| **AFU measurement** | Label-declared active fluorescent units, retained separately from CFU in `probiotic_data.afu_measurements` with row provenance. Scaling million/billion AFU to AFU is not a CFU conversion. Without a reviewed AFU-compatible reference, dose assessment is incomplete, not evidence of underdosing. |
| **Dose assessment** | The enrichment-owned typed result for one material source-label exposure: source and normalized amounts, conversion rule/status, UL state, reason code, and readiness. Scoring and release gates consume this result instead of interpreting nullable booleans or free text. |
| **Dose assessment readiness** | `complete` when a material exposure received a conclusive assessment, `incomplete` when unit/form/compound lineage or calculation failed, and `not_applicable` when the row is not a distinct exposure or no UL applies. An incomplete material exposure cannot enter live scoring. |
| **UL assessment status** | One explicit dose outcome: `assessed_within_limit`, `assessed_over_limit`, `no_ul_applicable`, `not_distinct_exposure`, `unresolved_unit`, `unresolved_form`, `unresolved_compound_mass`, or `assessment_error`. |
| **UL exposure basis** | Typed evidence describing what a label dose measures for UL comparison: a declared nutrient amount, a compound/form mass, or an unresolved amount. This field owns `ul_gate_eligible`; Daily Value presence is one source of evidence, not a universal proxy. |
| **UL-scoped form substance amount** | A label amount tied by direct UNII identity to a nutrient form explicitly listed by the reference as subject to that nutrient's UL. Unlisted derivatives and carrier compounds do not qualify. |
| **Reference profile** | Named adult-neutral compatibility profile emitted alongside `data_by_group`; it is not a claim that one demographic fits everyone. |
| **Indeterminate UL assessment** | A UL exists but form/source lineage is insufficient for an honest comparison. The pipeline does not guess `over_ul`. |
| **UL review flag** | Explicit review signal for a clinically material indeterminate UL case; may carry CAUTION without asserting an exceedance. |
| **Folic-acid contribution** | The portion of declared folate positively identified as folic acid. This pipeline applies the folic-acid UL only to an identified folic-acid contribution. |
| **Folinic form** | Folinic acid, folinate, or leucovorin. Explicit mcg DFE may support adequacy; bare mcg without a verified DFE conversion is adequacy-unknown and not scoring-eligible. No folic-acid UL is guessed for a folinic form. |

## Safety and evidence terms

| Term | Meaning |
|---|---|
| **Profile capture mode** | Taxonomy-owned rule for how a `profile_flags[]` value reaches the evaluator: `derived_from_condition`, `user_selectable`, or `reserved`. Flutter must not maintain a separate selectable list. A `reserved` flag cannot be referenced by an active rule. |
| **Safety signal** | Canonical identity + applicability + confidence evidence consumed by the v4 safety gate. Raw matcher implementation details do not own verdict policy. |
| **US applicable** | Whether the regulatory evidence applies to the primary shipped US verdict. Other jurisdictions remain as regional advisories. |
| **Ingredient-level recall flag** | `has_banned_substance` or `has_recalled_ingredient`. Never use `is_recalled`, which implies an unsupported product-level recall. |
| **Ghost reference / phantom citation** | A real identifier whose content does not support the claim. Existence alone is not verification. |
| **Content verification** | Confirming that a PMID/CUI/RXCUI/UNII/NCT/CAS/CID identifies and supports the intended entity or claim. |
| **Clinical applicability assessment** | A shared decision that an identity-matched evidence record also fits its reviewed form, delivery, daily-dose and outcome scope. Rejected matches remain auditable but cannot supply clinical points, depth bonuses or reviewed-support states. An unreviewed scope is not a negative clinical finding. |
| **Studied formula assessment** | A complete-formula match to a reviewed registry record: product identity, all strain identities, native-unit daily dose and co-ingredient composition. Formula evidence never becomes independent per-strain efficacy or invented per-strain quantities. |
| **Clinical source of truth** | Primary regulatory or scientific evidence plus curated, tested local data. Generated reports are review queues, not authoritative data. |

## Versions and tests

| Contract | Current code value |
|---|---|
| Export schema | `2.3.0` (`build_final_db.py`) |
| Export core columns | `111` (`build_final_db.py`) |
| Pipeline manifest version | `3.4.0` (`build_final_db.py`) |
| Enrichment version | `3.1.0` (`enrich_supplements_v3.py`) |
| V4 scoring engine | `4.2.0` (`score_supplements_v4.py`) |
| V4 quality config | `1.0.6-clean-label-registry` (`quality_score.json`) |
| Legacy scorer config | `3.6.1` (`scoring_config.json`) |

All tests run through `scripts/test.sh`. `fast` is the development profile;
`release` and `full` are pre-ship profiles. Direct raw pytest commands are not
part of the supported operator contract.
