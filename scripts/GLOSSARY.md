# PharmaGuide Glossary

Ubiquitous language for the IQM / scoring / enrichment domain. Every term here
should be used consistently in code, tests, commit messages, and conversation
with AI. When introducing a new term, add it here first.

This file is the source of truth for terminology — read it before audits,
refactors, or PRD writing. If a term in code drifts from this glossary, update
one or the other; never let them disagree silently.

## Core data structures

| Term | Meaning |
|---|---|
| **IQM** | Ingredient Quality Map — `scripts/data/ingredient_quality_map.json`. The 610-parent quality scoring database. |
| **Parent** | A canonical ingredient family keyed by snake_case name (e.g., `vitamin_a`, `magnesium`, `boswellia_serrata`). Each parent has `standard_name`, `category`, `cui`, `rxcui`, `forms`. |
| **Form** | A specific salt / chelate / extract under a parent (e.g., `magnesium_glycinate`, `beta-carotene from mixed carotenoids`). The unit at which `bio_score` and `absorption_structured` are assigned. |
| **Form name** | The IQM key for a form. Enricher match priority: literal `form_name` → `aliases` → fallback to `(unspecified)` form. |
| **Aliases** | Alternative strings the enricher normalizes to this form. Includes Greek letters (β-carotene), spacing variants, brand names (Betatene), regional spellings. |
| **(unspecified) form** | Catch-all form for a parent when no specific form matches. Receives conservative `bio_score` 5–7 due to quality uncertainty. |

## Scoring fields (IQM-level, per form)

| Field | Range | Meaning |
|---|---|---|
| `bio_score` | 1–15 | Form-quality score. For systemic actives, this means absorption/bioavailability. For local/matrix actives (fibers, prebiotics, mushrooms, demulcents, phytosterols), this means active-form quality and delivery-to-site confidence rather than serum absorption. **14–15** = premium; **11–13** = high quality; **8–10** = standard; **5–7** = basic / unspecified; **1–4** = poor. |
| `natural` | bool | Whether the form is naturally derived (food / plant / whole-food / naturally-occurring chelate). |
| `natural_bonus` | +3 | Added to `score` if `natural: true`. |
| `score` | 1–18 | `bio_score + natural_bonus`. Max possible = 18. |
| `absorption` | string | Human-readable absorption rate, e.g., `"8.7-65%"`. |
| `absorption_structured` | object | `{value, range_low, range_high, quality, notes}`. `quality` enum: `{excellent, very_good, good, moderate, low, poor, variable, unknown}`. |
| `dosage_importance` | enum | How much dosing precision matters for this form's effect. |

## Scoring fields (product-level export — v2.0.0 v4 production)

- `quality_score_v4_100` — **canonical shipped score** (six-pillar /100). The primary export/ranking field.
- `quality_score_status` — `scored` | `suppressed_safety` | `not_scored`.
- `quality_tier` — Elite/Excellent/Strong/Acceptable/Weak/Poor.
- `raw_score_v4_100` — audit/debug only; **never** the shipped score and never shown when `quality_score_status` suppresses display.
- `score_100_equivalent` / `score_display_100_equivalent` — honest /100 compat mirrors of `quality_score_v4_100`.
- `score_quality_80` — **DROPPED at v2.0.0** (legacy /80 column). Do not reintroduce; use `quality_score_v4_100`.
- `has_banned_substance` / `has_recalled_ingredient` — ingredient-level safety flags.
- **Never** use `is_recalled` — implies product-level recall, unsupported in v1.
- **Verdict precedence (deterministic):** BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE.

## Dose-safety assessment terms

| Term | Meaning |
|---|---|
| **Indeterminate UL assessment** | The pipeline has an applicable UL reference but lacks the form or source lineage required to compare the label dose honestly. It must not emit `over_ul=true` or silently treat the dose as cleared. |
| **UL review flag** | An additive `rda_ul_data.ul_review_flags[]` record emitted when an indeterminate assessment reaches a clinically relevant screening threshold. It routes the product to `CAUTION`/review without asserting that the UL was exceeded. |
| **No-UL adequacy cap** | When the authoritative reference establishes an RDA/AI but no UL, dose adequacy may be capped at `high` instead of being treated as toxic or `excessive`. This is a scoring rule, not a safety conclusion; interaction and contraindication evidence remains independent. |

## Production scoring pillars (v4)

| Pillar | Max | What it measures |
|---|---|---|
| Formulation | 20 | Ingredient form quality, delivery, formulation fit |
| Dose | 20 | Category-aware dosing adequacy and excess-dose handling |
| Evidence | 20 | Verified clinical support and category fit |
| Transparency | 15 | Label disclosure, proprietary blend opacity, completeness |
| Verification | 15 | Verified third-party testing, COA, GMP/certification signals |
| Safety/Hygiene | 10 | Product-level safety hygiene and clean-label penalties |

Config: `scripts/scoring_v4/config/quality_score.json`.

The legacy `score_supplements.py` 80-point model still runs for review queues,
detail-blob scaffolding, verdict history, and audits. It is not the shipped score
contract.

## Audit terminology (used during IQM batches)

| Term | Meaning |
|---|---|
| **Ghost reference** | A PMID that exists on PubMed but does NOT support the claim it's cited for (wrong topic, wrong species, misattribution). Detected by *content* verification, not existence alone. |
| **Phantom citation** | Synonym for ghost reference. Preferred in test names: `test_*_phantom_citation_*`. |
| **Framework category error** | An ingredient placed in the wrong taxonomic / regulatory class (e.g., manuka honey treated as a botanical when it's a food product). Surfaces as inappropriate scoring rules. |
| **Bridge question** | A cross-cluster query the audit prompt makes (e.g., "every PMID in IQM also appears in `backed_clinical_studies`"). Verifies internal consistency across data files. |
| **BRC class** | Brown Rice Chelate forms — `<mineral>_brown_rice_chelate`. Invariant: `bio_score = 11`. `absorption_structured.quality` varies by mineral (zinc=moderate, manganese=low, iron=low, selenium=moderate). |
| **Class-based absorption constraint** | A regression assertion that holds across an entire ingredient class, not just one form (e.g., "all chelates ≥ moderate absorption"). |
| **Conflation** | Two distinct claims merged into one (e.g., "rat-only BBB-crossing" cited as "BBB-crossing in humans"). Triggers a phantom-citation verdict. |
| **Source-descriptor prefix** | A `from <source>` form name (e.g., `iron from brown rice chelate`). The enricher's `prefix='from'` rule currently blocks these from matching their proper IQM form. See `project_enricher_prefix_from_bug` memory. |
| **Marketing claim** | An unqualified efficacy claim in `notes` not backed by cited evidence. Caught by phantom-citation tests with audit-trail context. |

## Pipeline stages

| Stage | Script | Input → Output |
|---|---|---|
| **Clean** | `clean_dsld_data.py` | Raw DSLD JSON → normalized records |
| **Enrich** | `enrich_supplements_v3.py` | Cleaned records → matched / classified / enriched ingredients (~13K lines) |
| **Score** | `score_supplements.py` | Enriched records → legacy scaffolding + verdicts (~4K lines) |
| **Build** | `build_final_db.py` | Scored records + V4 adapter → Flutter SQLite blob |
| **Sync** | `sync_to_supabase.py` | Build output → Supabase (offline-first cache) |

## External identifier types

| Type | Source | Verifier |
|---|---|---|
| **CUI** | UMLS concept identifier | `verify_cui.py` (UMLS API) |
| **RXCUI** | RxNorm ingredient ID | `verify_interactions.py` (RxNorm API) |
| **PMID** | PubMed article ID | `verify_pubmed_references.py`, `verify_all_citations_content.py` |
| **CID / CAS** | PubChem compound IDs | `verify_pubchem.py` |
| **UNII** | FDA Unique Ingredient ID | `verify_unii.py` |
| **NCT ID** | ClinicalTrials.gov registration | `verify_clinical_trials.py` |

**Critical rule:** every identifier in production data MUST be verified by *content*, not just existence. PMIDs that "exist" but are about a different topic are ghost references. See `critical_no_hallucinated_citations` and `critical_clinical_data_integrity` memories.

## Schema versioning

- Most data files: `schema_version` in `_metadata` block, range **5.0.0 – 5.3.0**
- `user_goals_to_clusters.json`: **6.0.0** (separate evolution)
- Scoring engine version: **3.4.0** (`scripts/config/scoring_config.json`)
- Pipeline version: **3.4.0** (`scripts/FINAL_EXPORT_SCHEMA_V1.md` manifest)

When changing schema: bump `schema_version`, update `last_updated`, recompute `total_entries`, run `db_integrity_sanity_check.py`.

## Test naming conventions

- `test_<topic>_integrity.py` — regression suites per IQM batch (e.g., `test_boswellia_absorption_integrity.py`)
- `test_<topic>_phantom_citation_*` — content-verified PMID assertions
- `test_*_class_absorption_*` — class-based absorption constraints
- Snapshot tests: `test_scoring_snapshot_v1.py` — refresh via `freeze_contract_snapshots.py <product_id>` after intentional scoring changes
