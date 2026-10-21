# Export fidelity audit — Enrich/Score → detail blob + core row (2026-10-20)

Requested by Sean after DSLD 218842 (beta-carotene exported no mcg RAE amount).
Question: what does `scripts/build_final_db.py::build_detail_blob` / `build_core_row`
drop, overwrite or distort relative to the enriched and scored artifacts?

- Inputs: the 2026-10-20 corpus run (`scripts/products/output_*_{enriched,scored}`, all stage
  manifests fresh against main 1d60f43f3). 15,426 enriched / 15,426 scored, 0 duplicate ids,
  0 unpaired (staging joins by `dsld_id`, `INSERT OR REPLACE`; probe `census`).
- Exporter under test: branch `claude/export-fidelity-audit` (= `claude/normalized-dose-row-key`
  12386b153 + the fixes below). Blobs built in-process, the same calls `build_final_db()` makes
  (`validate_export_contract` → `build_detail_blob` → `build_core_row`). 15,426/15,426 built,
  0 build errors.
- Probes and raw outputs: `~/pg_quality/export_fidelity_audit_20261020/probes/`
  (`export_fidelity_probe.py` → `full_v1.jsonl`, `_v2.py` → `full_v2.jsonl`, `_v3.py` →
  `full_v3.jsonl`, `gate_norm_dose_corpus.py`). App reader checked:
  `lib/services/ingredients/ingredient_row_fields.dart::readDoseAmount/readDoseUnit`,
  `lib/services/health/product_health_facts.dart::_extractNutrients`,
  `lib/services/warnings/interaction_warning.dart::_dedupeKey`,
  `lib/services/warnings/profile_gate_evaluator.dart::evaluateProfileGate`.

## Findings

| # | Seam (path::symbol) | Verdict | Corpus count | Examples | User impact | Confidence | Status |
|---|---|---|---|---|---|---|---|
| 1 | `build_final_db.py::_normalized_dose_entry` (name-keyed normalization) | Defect, fixed upstream of this branch | After 12386b153: 0 / 77,832 rows disagree with their own `source_field` entry. Pre-fix exporter: 717 rows / 213 products (gate proof) | 218842 | App dose/UL readers (`normalized_amount` is 4th in `readDoseAmount`) saw a sibling's conversion or none | High | Fixed on `claude/normalized-dose-row-key` |
| 2 | `build_final_db.py::_warning_dedup_key` — identity-less warnings | **Defect** | `harmful_additive`: 5,582 products lost ≥1 card in `warnings` (6,184 cards), 767 lost a moderate/critical card from `warnings_profile_gated`; `dietary`: 143 products | 178352 (Sucralose hidden under FD&C Yellow No. 6), 180206, 295000 (Corn Syrup Solids under Silicon Dioxide), 213042 (Diabetes under Hypertension) | Distinct additive / dietary cards silently merged by severity; the app never shows them (its own dedupe would have kept them) | High | **Fixed** c8b8ca5f3 |
| 3 | `audit_raw_to_final.py::_check_unsafe_unit_conversion` — gate coverage | **Gap** | Gate checked normalized doses only for vitamin A/E in IU; 218842 was caught by that coincidence | 218842 | A sibling-row normalized dose for any other nutrient would ship unflagged | High | **Fixed**: new BLOCKER `NORMALIZED_DOSE_NOT_FROM_OWN_ROW` |
| 4 | `_warning_dedup_key` merges same-rule interaction cards whose `profile_gate` differs (no gate in key; app's `_dedupeKey` has one) | **Defect — needs Sean (clinical applicability)** | 3,214 merged cards / 2,762 products / 17 rules; the kept card is gated `pregnant` only, the dropped one `pregnant OR breastfeeding` (B6/lactation the reverse) | 254734 Yohimbe, 253957 Butterbur, 31147 7-Keto-DHEA, 294795 B6 | A breastfeeding user loses the stronger card in 12/17 rule patterns (e.g. Yohimbe contraindicated → only "lactation / avoid"; Butterbur contraindicated → "lactation / no_data"); 5/17 still covered at equal severity | High (simulated with the app's gate semantics) | **Open — not patched** (see below) |
| 5 | `build_detail_blob::_consumer_supported_exposure_rows` empties `rda_ul_data.analyzed_ingredients`; app `_extractNutrients` then falls back to `blob.ingredients` | Second brain (app), low live impact | 4,117 products ship an empty analyzed list while Enrich had rows; 417 have a UL-listed nutrient on the fallback surface, of which only 5 nutrients carry a UL and only 315691 (potassium iodide 130 mg) is over it | 315691, 329881, 241724 | App re-derives a UL decision the pipeline withheld; today it only fires on 315691, directionally right (≈99 mg iodide vs 1.1 mg UL) | High | Open — Flutter follow-up |
| 6 | Enrich `rda_ul_data.safety_flags` with `ul_gate_eligible: false`, reason `compound_mass_not_elemental` | Export consistent with Stage 3; **upstream** identity gap | 2 products | PG_SUB_C926B40D83F1491CB6CD3EEBEBC73FC7 ("Niacin (as Niacinamide)" 40 mg NE, 114% UL, `canonical_id: null`), 315691 | Niacin UL covers niacinamide, so this over-UL flag should reach the user; scorer marks it `material_but_unresolved` | Medium-high | Open — Enrich follow-up |
| 7 | `generate_ingredient_fingerprint` / `generate_key_nutrients_summary`: `normalized_amount or quantity`, `normalized_unit or unit` | Distorted but unconsumed | IQD rows never carry `normalized_amount`, so amounts are raw label units; app reads only fingerprint `nutrients` **keys**; `key_nutrients_summary` has no app reader | any multivitamin | None today; a future reader of these amounts would get per-serving label units | High | Recorded; dead-value candidate |

## Checked and clean (controls)

| Claim | Evidence (probe → result) |
|---|---|
| Staging pairs every enriched with its own scored product | census: 15,426 / 15,426, 0 dupes, 0 unpaired |
| Exported `normalized_amount/unit` equals the row's own normalization entry | `full_v1` A: 77,832 rows, 0 mismatches, 0 name-fallbacks, 0 blob rows without an enriched path |
| App amount/unit fields never come from different sources | `full_v1` B: 77,823 `ingredients` + 59,295 `analyzed_ingredients` dosed rows, 0 splits under `readDoseAmount`/`readDoseUnit` priority |
| Exported identity = enricher's decision for the path | `full_v1` K: 0 |
| Core row = scored artifact (status, safety status, tier, verdict, 6 pillars) | `full_v1` I: 0 diffs |
| Core `has_banned_substance`/`has_recalled_ingredient` agree with Stage-3 verdicts | `full_v1` H: 0 |
| Inactive rows: enriched count = blob count | `full_v1` J: 0 |
| Every interaction subject × target reaches `warnings` | `full_v2` F2_SUBJECT_TARGET_MISSING: 0 |
| Active rows absent from `ingredients[]` are still on the label | `full_v1` C: 35,518 rows / 4,241 products, all present in `display_ingredients`; dosed ones are nutrition-facts rows (fiber 742, protein 619, chloride 355, sodium 265), blend headers and demoted enhancers kept out by the strict scoring contract (by design) |
| Other title merges are one hazard under two label spellings | `full_v2` W for interaction / drug_interaction / high_risk / watchlist / banned share a rule id or interaction subject by construction of the key (Yohimbe vs Yohimbe extract; EDTA spellings; Niacinamide vs Vitamin B3) |

## Existing gates: covered vs missed

- `audit_raw_to_final.py --all` (run by `rebuild_dashboard_snapshot.sh`): raw→ledger rows, names,
  printed amounts/units, export identity per path, vitamin A/E IU normalization, blend children,
  core/blob active counts. **Missed:** normalized dose for every other nutrient (#1/#3, now added),
  warning-list collapses (#2, #4), analyzed-row filtering vs app fallback (#5).
- `build_detail_blob` validators (`_validate_inactive_preservation`, active-count reconciliation,
  banned preflight, warning display-mode/authored copy) check presence, not distinctness.
- `project_export_scored_artifact` guards safety-verdict parity only.

## Fixes on this branch

1. c8b8ca5f3 `fix(export): keep distinct identity-less warnings apart in dedup` —
   `_warning_dedup_key` uses the title as the identity of last resort; context events keep
   their own key (checked first). Tests: `test_warning_dedup.py` (+4, fail-first 3 failures).
2. `audit_raw_to_final.py::_check_export_normalized_dose` — BLOCKER
   `NORMALIZED_DOSE_NOT_FROM_OWN_ROW`, called from `_check_export_identity` so it covers DSLD and
   submission products. Tests: `test_audit_raw_to_final_reconciliation.py` (+4, fail-first 2
   failures).

## Gate proof (`gate_norm_dose_corpus.py`, all 15,426 products, in-process blobs)

- main's pre-fix exporter (1d60f43f3): 717 findings in 213 products, e.g. 218842 beta-carotene
  exported None vs its own 750 mcg RAE; 312861 exported 400 mg vs 8,000 mg; 241710 100 mg vs 600 mg.
- this branch's exporter (rebased on main 1575a57e3): 0 findings, also after the review hardening
  below (own entry, else one positionless same-name entry, else unknown; values coerced with the
  exporter's `safe_float`/`safe_str`).

## Post-fix measurement (`full_v2_postfix.jsonl` vs `full_v2.jsonl`)

Distinct-title collapses: harmful_additive 6,184 → 0 (`warnings`), 769 → 0 (`profile_gated`);
dietary 143 → 0 in each list; interaction, drug_interaction, high_risk, watchlist and banned counts
unchanged; 0 merges across warning types.

## Independent review (fresh-context agent, requirement + diff only)

No blocker. Acted on: gate false negative when a row has no entry of its own (a name fallback
could hand it a sibling's dose) and gate false positives on string / non-finite amounts and
unstripped units — fixed with tests. Noted: the title fallback lets identity-less critical cards
of different types merge if they share a title; measured 0 on the corpus (titles carry a
type-specific prefix).

## #4 — options for Sean (not patched)

The `pregnant OR breastfeeding` hit comes from Enrich with generated or mismatched copy
(254734: "Avoid yohimbe pregnancy during pregnancy and breastfeeding"; the banned-rule twin
carries pregnancy-only text under a breastfeeding gate). Options:
(a) add the gate to the pipeline dedup key (mirror the app): ships that copy to breastfeeding
users and shows pregnant users two pregnancy cards;
(b) fix the Enrich emission so the combined block produces a lactation-target hit with lactation
copy, leaving dedup unchanged (needs a clinical copy review);
(c) keep as is (breastfeeding users get only the weaker lactation card).
Recommendation: (b); it changes Enrich and authored copy, so it is Sean's call.

## Stage reruns

- #1 and #2 are export-only (`build_final_db.py` is in no stage fingerprint): no Clean/Enrich/Score
  rerun; the next catalog rebuild picks them up.
- The new gate runs inside the existing snapshot/raw-to-final step.
- #4 option (b) and #6 would need Enrich (and Score) reruns when decided.
