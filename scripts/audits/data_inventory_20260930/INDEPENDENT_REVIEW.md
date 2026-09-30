# Independent review and retirement shortlist — 2026-09-30

Scope: review of the supplied Claude reports against the local checkout at
`0d69eeb0` on `evidence/owner-eligibility`, including its existing uncommitted
Evidence edits. This is an audit, not authorization to change scoring or publish.
No production data, code, app assets or memory were changed by this review.

## Owner check

- Existing audit owner: `scripts/audits/data_inventory_20260930/README.md` and
  `inventory_table.md`; this document qualifies their conclusions.
- Reference selection: `scripts/scoring_reference_resolver.py::reference_family`.
- Quantified nutrient assessment: `scripts/rda_ul_calculator.py`, consumed through
  `rda_ul_data`, including adequacy and safety results.
- Clinical applicability: `scripts/clinical_applicability.py` and
  `scripts/evidence_resolver.py`; Evidence scoring consumes their decisions.
- Manufacturer recalculation:
  `scripts/api_audit/fda_manufacturer_violations_sync.py::recalculate_all_entries`.
- App reference copying: `scripts/sync_flutter_reference_data.py`.
- Evidence: inspected source-of-truth matrix and glossary; searched file names,
  stems, constants, configurations, shell scripts, tests and Flutter consumers.
- Will NOT create: another scorer, reference registry, normalizer, clinical
  policy, status or archive loader.

## Corrections to the supplied findings

1. **Manufacturer framework is live maintenance input.**
   `manufacture_deduction_expl.json` is loaded by `load_deduction_expl`; sync's
   `main` invokes `recalculate_all_entries`, which applies recency and modifiers.
   Calling it gate-only or saying no recomputation exists is incorrect. The
   freshness problem is real: an in-memory run of the existing recalculator
   changed Nature's Way -6.5 -> -3.25, Green Lumber -18 -> -9, and Hydroxie
   -18 -> -9. These are stored deduction values, not measured public-score deltas.
   Reuse this owner; decide deterministic calculation date/freshness before
   adding runtime aging elsewhere.
2. **16/210 describes fields, not complete runtime eligibility.** There are 11
   records with `min_clinical_dose` and 5 with applicability minimums. This does
   not establish that all remaining records receive full Evidence at any amount.
   Form, purpose, population, disclosure, direction and specialized route rules
   also affect eligibility. Sports/probiotic/omega references also mean a miss
   in the two named JSON files is not proof of absent Dose assessment.
3. **Fallback numbers are raw points.** The generic no-reference function returns
   16 or 12 raw points. For a 22-point public normalization reference these are
   about 14.5/20 and 10.9/20 before other effects, not 16/20 and 12/20.
4. **One ingredient need not have one universal studied dose.** Study exposure,
   RDA/AI, upper limit, indication-specific treatment window and combination
   threshold are distinct facts. Consolidate duplicated facts with the same
   scope, not every number attached to the same ingredient.
5. **Zinc record is not a picolinate cold regimen.** The historical ID
   `INGR_ZINC_PICOLINATE` now names acetate/gluconate lozenges; the record explicitly
   restricts dosage form, acute adult cold context, and 80–207 mg/day exposure.
   Never migrate by the legacy ID alone or convert this into generic zinc RDA.
6. **Evidence and Dose both depending on exposure is not automatically a bug.**
   Duplicate exposure calculation should be consolidated. Whether Evidence
   measures ingredient research strength or evidence applicable to this product
   is a scoring-policy decision. Do not erase dose-sensitive applicability or
   study exposure history as a side effect of moving numerical Dose penalties.
7. Legacy v3 inspection confirms an EPA/DHA-specific Section E and clinical-dose
   guards inside Evidence. Historical behavior explains migration risk; it is
   not automatically the current specification.

## Retirement and consolidation list

| File/group | Disposition | Required condition |
|---|---|---|
| `ingredient_weights.json` | Strong retirement candidate | No scoring read found; remove dead constant, enrichment load, preflight/schema/data-batch checks and file-specific tests together. Do not confuse with live IQM `dosage_importance`. |
| `unit_mappings.json` | Strong retirement candidate | No value consumer found; contains assumed capsule strengths, not legitimate unit conversions. Remove references atomically; never transfer default strengths into dose extraction. |
| `production_assessable_actives.json` | Relocate generated output | Move into its existing audit area and update the generator's output path. |
| `branded_blend_anchor_overrides.json` | Migrate before retirement | Five curated anchors lost their old runtime reader; preserve identity, source restrictions and citations in existing owners, verify actual v4 gaps per entry, then retire the old file. No new override engine. |
| `manufacture_deduction_expl.json` | Keep | Live recalculation policy; correct stale v3 path documentation and freshness handling. |
| `rda_optimal_uls.json` | Keep | Live nutrient references, clinical anchors and safety data. Keep reference kinds explicit. |
| `rda_therapeutic_dosing.json` | Keep | Live clinical ranges; route access needs review, not wholesale migration. |
| `backed_clinical_studies.json` | Keep | Preserve trial exposures and applicability; remove only proven redundant operational copies after consumers migrate. |
| `synergy_cluster.json` | Keep; review individual thresholds | Combination thresholds may have a different purpose from standalone benchmarks. Reference a shared value only when semantics match. |
| `unit_conversions.json`, `daily_values.json` | Keep | Actual conversion and labeling-reference owners; neither is the unused `unit_mappings`. |
| App vocabulary copies | Keep generated copies, one authoring source | Confirmed inequality for category, legal-status and verdict vocabularies. Extend existing sync and validate source-to-app fingerprints. |
| `views/` clinician documents | Regenerate, not independent policy | Keep canonical interaction rules authoritative; remove obsolete generated views through the generator's workflow. |
| Gate vocabularies, citation ledgers, sign-off records | Keep | Test/release consumers are real consumers. |
| CAERS signals | Keep explicitly dormant | Dormant policy is not dead code; do not activate or delete by reachability alone. |
| Raw FDA inputs/caches | Keep outside runtime authoring set as appropriate | Preserve reproducibility; ignored files are not protected by git history. |

For retired tracked files, prefer git history to a second live-looking JSON in
`scripts/data/_archive`. If a physical archive is desired, use the existing
archive area outside production loaders, with original path, commit, disposition
and successor documented. Curated clinical deletion still needs explicit approval.

## Recommended execution order

1. Correct the inventory classifications and commit the read-only inventory.
2. Retire the two unused files plus their wiring; relocate the audit output.
   This batch should have zero score and verdict deltas.
3. Repair manufacturer freshness using the existing recalculator; synchronize
   vocabularies and regenerate clinician views in separate bounded fixes.
4. For lane 3a, build a rule-level migration table: source, semantic kind, exact
   material/form, population, indication, regimen, units, current consumers,
   existing owner, and expected scoring/display change. Include sports, omega,
   probiotic, joint/immune/sleep and synergy paths, not only generic Dose.
5. Reuse the reference resolver and canonical exposure/adequacy contracts;
   preserve evidence applicability and the app's low-dose flag. Verify botanical
   access in mixed products without reclassifying an ingredient as active solely
   because a reference exists.
6. Migrate the five branded anchors per entry, then retire the orphaned file.
   Measure label/control changes before any scoring-policy rollout.

No claim is made here that every PMID, every inventory row, or every historical
consumer was independently reverified. This review concentrates on retirement
candidates, source ownership and the high-impact claims driving the proposal.
