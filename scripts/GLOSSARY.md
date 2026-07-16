# PharmaGuide Glossary

> Last verified against executable code: 2026-07-15

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
| **Promotion** | Atomic replacement of both live snapshot directories after every candidate gate passes. Failed candidates are deleted; the last good live snapshot remains. |
| **Release** | The auto-smart workflow in `scripts/release_full.sh`: ensure the snapshot is current, update images and interactions when needed, run strict gates, then sync Supabase and import the Flutter bundle. |
| **Auto-smart** | A release step runs only when inputs, checksums, or manifests show that its output is stale. It is not permission to skip gates. |
| **Contract quarantine** | A product intentionally excluded from the shipped catalog because its output cannot satisfy the export contract, while the build continues and records the exclusion. |
| **Contract failure** | A systemic or required-contract error that stops candidate promotion or release. |
| **Scoring snapshot contract** | Per-product regression fixtures checked immediately before Supabase/Flutter publication. Intentional deltas must be reviewed and explicitly re-frozen. |
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
| **IQM** | Ingredient Quality Map: `scripts/data/ingredient_quality_map.json`. Current metadata: schema 5.4.11, 629 parents. |
| **Parent** | Canonical ingredient family identified by a stable snake-case key, such as `magnesium`. |
| **Form** | A specific salt, chelate, extract, strain, source, or delivery form under a parent. |
| **Canonical ID** | Stable machine identity selected by deterministic exact/canonical/bounded-alias matching. Display text is not identity. |
| **Printed name** | Full ingredient name as printed on the label. It is retained even when a verified branded token is extracted. |
| **Branded token** | Separately stored verified brand marker; it never replaces the printed name. |
| **Marker contribution** | A bioactive delivered by a source ingredient. The source keeps its identity; the marker is not promoted into a duplicate active row. |
| **Parent-total row** | A declared nutrient total that groups subforms. It is preserved for label fidelity but excluded from duplicate scoring when its children carry the form detail. |
| **Blend header** | A declared proprietary/structural blend container. It is not an individually dosed active. |
| **Blend member** | A child ingredient linked to a blend header by stable parent linkage. A display-only child may remain visible without becoming independently scoreable. |
| **Scorable row** | An active ingredient row that satisfies cleaner/enrichment eligibility and the shared scoring-input contract. |
| **Display-only row** | A label-faithful row retained for explanation but excluded from independent score math. |
| **Mapped coverage** | Fraction of score-eligible active rows with a usable canonical mapping, computed by the shared scoring-input contract. |

## IQM form fields

| Field | Contract |
|---|---|
| `bio_score` | 0–15 form-quality signal. For systemic actives it represents absorption/bioavailability evidence; for local/matrix actives it represents relevant form and delivery-to-site confidence. |
| `natural` | Whether the form is supported as naturally derived. |
| `score` | Legacy `bio_score + 3` when `natural=true`, capped at 18. Do not use this value as pure bioavailability. |
| `absorption_structured` | Structured value/range/quality/notes evidence. It must not claim more precision than the supporting source. |

## Production scoring terms

| Term | Meaning |
|---|---|
| **V4 quality score** | The only shipped public score. Produced during Stage 3 by `score_products_v4.py`/`scoring_v4/` and exported unchanged as `quality_score_v4_100`. |
| **Scored artifact** | The sole Stage-3 output produced by `build_scored_artifact()`: v4 score/status/pillars, shared coverage and strict diagnostics, safety/verdict state, provenance, and compatibility mirrors. |
| **Quality score status** | `scored`, `suppressed_safety`, or `not_scored`. Status controls whether a public number is allowed. |
| **Raw v4 score** | `raw_score_v4_100`; audit math only. It is never substituted for a suppressed public score. |
| **Compatibility mirrors** | `score_100_equivalent` and `score_display_100_equivalent`; exact /100 mirrors of the v4 public score, not a legacy /80 conversion. |
| **Quality pillars** | Formulation 20, Dose 20, Evidence 20, Transparency 15, Verification 15, Safety/Hygiene 10. |
| **V4 module** | One category-aware scoring route: `generic`, `probiotic`, `multi_or_prenatal`, `b_complex`, `sports`, `fiber_digestive`, or `omega`. |
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
| **Reference profile** | Named adult-neutral compatibility profile emitted alongside `data_by_group`; it is not a claim that one demographic fits everyone. |
| **Indeterminate UL assessment** | A UL exists but form/source lineage is insufficient for an honest comparison. The pipeline does not guess `over_ul`. |
| **UL review flag** | Explicit review signal for a clinically material indeterminate UL case; may carry CAUTION without asserting an exceedance. |
| **Folic-acid contribution** | The portion of declared folate positively identified as folic acid. This pipeline applies the folic-acid UL only to an identified folic-acid contribution. |
| **Folinic form** | Folinic acid, folinate, or leucovorin. Explicit mcg DFE may support adequacy; bare mcg without a verified DFE conversion is adequacy-unknown and not scoring-eligible. No folic-acid UL is guessed for a folinic form. |

## Safety and evidence terms

| Term | Meaning |
|---|---|
| **Safety signal** | Canonical identity + applicability + confidence evidence consumed by the v4 safety gate. Raw matcher implementation details do not own verdict policy. |
| **US applicable** | Whether the regulatory evidence applies to the primary shipped US verdict. Other jurisdictions remain as regional advisories. |
| **Ingredient-level recall flag** | `has_banned_substance` or `has_recalled_ingredient`. Never use `is_recalled`, which implies an unsupported product-level recall. |
| **Ghost reference / phantom citation** | A real identifier whose content does not support the claim. Existence alone is not verification. |
| **Content verification** | Confirming that a PMID/CUI/RXCUI/UNII/NCT/CAS/CID identifies and supports the intended entity or claim. |
| **Clinical source of truth** | Primary regulatory or scientific evidence plus curated, tested local data. Generated reports are review queues, not authoritative data. |

## Versions and tests

| Contract | Current code value |
|---|---|
| Export schema | `2.0.0` (`build_final_db.py`) |
| Export core columns | `110` (`build_final_db.py`) |
| Pipeline manifest version | `3.4.0` (`build_final_db.py`) |
| Enrichment version | `3.1.0` (`enrich_supplements_v3.py`) |
| V4 scoring engine | `4.1.0` (`score_supplements_v4.py`) |
| V4 quality config | `1.0.4-sports-subtypes` (`quality_score.json`) |
| Legacy scorer config | `3.6.0` (`scoring_config.json`) |

All tests run through `scripts/test.sh`. `fast` is the development profile;
`release` and `full` are pre-ship profiles. Direct raw pytest commands are not
part of the supported operator contract.
