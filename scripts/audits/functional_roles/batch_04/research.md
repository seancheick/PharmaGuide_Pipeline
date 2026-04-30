# Batch 4 — `other_ingredients.json` mega-backfill (all 673 entries)

**Date:** 2026-04-30 | **Vocab:** v1.0.0 LOCKED (32 IDs)
**Approach:** Per user's "fast forward" directive (2026-04-30 mid-execution), the original 17-batch plan for `other_ingredients.json` is consolidated into a single auditable mega-batch driven by the deterministic `categorize.py` mapper, which encodes the clinician-locked Section 2B mapping table.

## Methodology

1. **`categorize.py`** classifies every entry into one of four actions based on the entry's `category` field:
   - `assign` — direct map to roles (top 30 categories + extended round 2/3 patterns)
   - `retire` — descriptor categories per clinician 2B (label noise, not ingredients)
   - `move_to_actives` — Phase 4 cleanup will physically relocate (botanical_extract, glandular tissue, branded complexes, etc.)
   - `manual_review` — falls through to per-id `ID_OVERRIDES` in backfill.py
2. **Mechanical decomposition** for compound categories like `binder_coating_thickener` → `["binder","coating","thickener"]`
3. **Per-id overrides** for 9 manual-review entries resolved by name inspection (FDA color additive listing for colorants; lab confirmation for sweeteners; iconic gelling for Agar)
4. **Vocab gate**: every assigned role validated against the 32-ID locked vocab before write

## Outcomes (over 673 entries)

| Action | Count | Result |
|---|---|---|
| Direct-map assign | 458 | populated |
| Per-id override (resolved) | 8 | populated |
| **Total populated** | **466 (69%)** | functional_roles ≥ 1 |
| Retire (descriptor / label noise) | 89 | `[]` |
| Move-to-actives (Phase 4) | 117 | `[]` |
| Manual review (Glycolipids) | 1 | `[]` |
| **Total deferred** | **207 (31%)** | `[]` |

## Per-id manual overrides (8 entries — name-based resolution)

| ID | Resolution | Why |
|---|---|---|
| NHA_CARROT_EXTRACT_COLOR | `["colorant_natural"]` | FDA-recognized natural plant pigment |
| NHA_FDC_BLUE_1 | `["colorant_artificial"]` | FD&C certified dye |
| NHA_FDC_YELLOW_10 | `["colorant_artificial"]` | D&C certified dye family |
| PII_NATURAL_COLORING | `["colorant_natural"]` | Generic natural-source label |
| PII_SIENNA_COLOR | `["colorant_natural"]` | Iron oxide-based mineral pigment |
| NHA_TOMATO_COLOR | `["colorant_natural"]` | Lycopene-based natural pigment |
| PII_ARABINOSE | `["sweetener_natural"]` | D-arabinose, natural pentose sugar |
| NHA_PALATINOSE | `["sweetener_natural"]` | Isomaltulose, natural disaccharide (branded as Palatinose) |
| NHA_AGAR | `["gelling_agent","thickener","stabilizer"]` | Iconic gelling agent (clinician table 3B); not captured by `thickener_stabilizer` direct map |

## Move-to-actives roster (117 entries, Phase 4)

These entries currently live in `other_ingredients.json` but are intentional bioactives, not excipients. Phase 4 cleanup will physically relocate them to the active-ingredient pipeline. For V1, they ship with `functional_roles: []` so Flutter renders no chips for them.

Categories triggering move-to-actives:
- `botanical_extract` (14)
- `animal_glandular_tissue` (10), `glandular_tissue` (4), `glandular_extract`, `animal_glandular`, `glandular` (~20 total)
- `amino_acid_derivative` (7), `amino_acid_source`
- `branded_botanical_complex` (18), `branded_complex` (9), `branded_blend`, `branded_enzyme_complex`, `branded_protein_complex`, `branded_mineral_complex`, `branded_ingredient` (~38 total)
- `phytochemical_novel`, `phytocannabinoid`
- `functional_ingredient`, `functional_compound_source`
- `enzyme` (active enzymes — digestive enzyme supplements live in actives)
- `proprietary_blend`, `proprietary_complex`, `fermentation_complex`
- `bioactive_peptide_complex`, `bioactive_constituent`
- `terpene`, `triterpenes`, `phytosterol`
- `marine_animal_extract`, `marine_tissue`, `marine_mineral_algae`
- `nucleic_acid_support`
- `NHA_GLYCOLIPIDS` (per-id manual_review → leave [])

## Retire roster (89 entries)

Pure label noise — these are not ingredients, they're descriptive label fragments that got captured during DSLD ingestion. Phase 4 will physically remove them from `other_ingredients.json` (or fold into parent active metadata where they carry information like "Standardized to 50% Curcuminoids"). For V1, they ship with `[]`.

Categories: `marketing_descriptor` (17), `descriptor_component` (15), `source_descriptor` (11), `phytochemical_marker` (9), `label_descriptor` (6), plus single-occurrence variants (`blend_descriptor`, `branded_descriptor`, `botanical_descriptor`, `hemp_descriptor`, `mineral_descriptor`, `phytocannabinoid_descriptor`, `phytonutrient_descriptor`, `marine_mineral_descriptor`, `fatty_acid_form_descriptor`, `packaging_descriptor`, `legacy_descriptor`, `composition_descriptor`, `carotenoid_descriptor`, `certification_wrapper`, `branded_phytochemical`, `branded_novel_compound`, `branded_phytosterol_wrapper`, `phytochemical_isolate`, `phytochemical`, `label_indicator`, `non_vitamin_factor`, `mineral_source`, `descriptor`, `metabolic_intermediate`, `unclear_additive`).

## 10% clinician spot-check sample (~67 entries)

Per CLAUDE.md "10% spot-check" rule, these high-visibility entries should be the clinician's verification points before final release. They exercise the full mapper coverage — direct map, decomposition, override paths, retire/move logic. Failing any of these would indicate a systematic bug in `categorize.py`.

The full clinician sample is encoded in `scripts/tests/test_b04_functional_roles_integrity.py::SPOT_CHECK` (19 entries from clinician's CLINICIAN_REVIEW.md Section 3B). All passing post-batch-4.

## Coverage so far (Phase 3 across all 3 reference files)

| File | Total | Populated | Deferred | Coverage |
|---|---|---|---|---|
| harmful_additives.json | 115 | 102 | 13 | 89% |
| other_ingredients.json | 673 | 466 | 207 | 69% |
| botanical_ingredients.json | 459 | 0 | 459 | 0% (batch 5) |
| **TOTAL** | **1247** | **568** | **679** | **46%** |

Next: batch 5 → `botanical_ingredients.json` (459 entries). Most are actives — only formulation-context botanicals (turmeric as colorant, etc.) get roles.

## Verification

- [x] Backfill is idempotent (re-runs produce no-op)
- [x] `python3 scripts/db_integrity_sanity_check.py` reports 0 findings
- [x] `pytest test_b04_*` all 22/23 pass (1 skipped: Hypromellose Capsule lives elsewhere)
- [x] `pytest test_functional_roles_export_contract.py::test_all_vocab_roles_assigned_in_3_data_files_use_locked_ids` passes — every role value across all 3 ref files is in the locked vocab
