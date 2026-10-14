# V4 score accounting audit and acceptance matrix — October 14, 2026

Step 1 of the V4.1 accounting and ownership consolidation. Sean approved the plan on October 14, 2026. This file is read-only evidence: nothing here changes a score. Steps 2 and later must satisfy the matrix in §3. Step 2 changes no score: it adds receipts and corrects explanation text.

## 1. Scope, layers and provenance

- **Production path.** `score_supplements_v4.py::score_product_v4` runs the route module (`scripts/scoring_v4/modules/*`) to produce the module breakdown. `quality_score.py::assemble_quality_score` → `_build_pillars` then builds the six public pillars. `scored_artifact.py` assembles the Stage-3 artifact. `build_final_db.py` produces the export, and Flutter renders it (`lib/core/scoring/v4_pillars.dart`, `pg_score_breakdown_card.dart`).
- **Config.** `scripts/scoring_v4/config/quality_score.json` (main at `1.24.0-independent-delivery`). Omega uses `scripts/data/omega_rubric.json`.
- **Corpus layer.** The stored Stage-3 outputs in `scripts/products/output_*_scored` of the primary checkout: 15,426 products, of which 15,123 are `scored`, 69 `suppressed_safety` and 234 `not_scored`. They were scored on October 14, 2026 at quality_score `1.23.0-dose-evidence-ownership`. Main's 1.24.0 changes only Formulation delivery credit, so delivery-affected counts may shift slightly. These are stored outputs, not a fresh rebuild of current main.
- **Meru.** `reports/meru_shilajit_20261014/clinical/meru-scored.json`, from branch `codex/shilajit-mapping` at `da1bc55f` (not on main). A live rescore of `meru-enriched.json` on that branch reproduced 55.7.
- **Reviews folded in.** Claude's audit, two Codex reviews and Sean's challenge on Verification. Outside claims were reproduced before being accepted (§6).

## 2. Findings

**What holds.**
- For every one of the 15,123 scored products, the public total equals the sum of the six pillars (`quality_score.py:1233`).
- Every Dose, Evidence and Transparency pillar equals `clip(round(raw ÷ reference × weight, 1))`. Formulation follows the same rule except for the 204 products that receive the unrated-form neutral.
- Verification is tier-assembled and Safety is a base minus deductions (§3.5–§3.6).
- `raw_score_v4_100` is internal only (`FINAL_EXPORT_SCHEMA_V1.md:12`).

**What does not hold.**

| # | Finding | Products | Owner |
|---|---|---:|---|
| F1 | Additive/sugar charged in Formulation (B1) **and** again in Safety (`formula_quality_checks` mirror, cap 4). `safety_hygiene.py:87-90` itself says that zeroing hygiene for these would double-penalise. | 3,509 | `quality_score.py:545-560` |
| F2 | B7 and its Safety mirror (cap 3) coexist in 403 products. Every one of them has a penalized `confirmed_over_threshold` flag at ≥150% of a UL. By code, the generic window credit for that nutrient is also zeroed (`generic_dose.py:191-193`), and B-complex withdraws `moderate_dose_fit` 3. Per-product window loss was **not** measured. | 403 (mirror + B7, measured) | `generic_dose.py:191-195`, `dose_safety.py`, `quality_score.py:563-573` |
| F3 | `caution` products whose sixth pillar shows 10/10 ("Strong"). Measured split: 333 have a confirmed over-UL state below the B7 threshold ("Safety concern" reason, no deduction); 1 has an unresolved dose state; 5 are cautions for an undisclosed stimulant blend, with no dose state and the reason "No banned, recalled, or watchlisted ingredients". | 339 | `quality_score.py:610-672` |
| F4 | Confirmed high-risk/watchlist: Formulation B0 −10/−5 **and** Safety base zeroed (−10). The two owners also use different match rules (B0 counts confirmed matches only; the base also counts likely and review matches). | 348 | `generic_formulation.py:278-290`, `safety_hygiene.py:80-147` |
| F5 | Printed amount or identity earns points in Formulation, Dose and Transparency. Meru's single "500 mg" earns about 15.3 points: Dose 6.6 (live probe), Formulation 2.7, Transparency 6.0. | thousands (§3) | botanical/collagen/probiotic/sports/fiber/multi/b_complex modules |
| F6 | Fact-independent baselines (unknown Verification 6, unconditional Transparency base 9, clean Safety screen 10, unrated and route bases) make up 28.6% of the median total (p90 44.6%). They carry no label. The Verification 6 is also the starting point of every tier below product level (claim 6 + signals ≤ 8; manufacturing ≤ 10). | all | §3 |
| F7 | Unknown dose adequacy is treated inconsistently: botanical 11.4, generic 14.5, collagen 9.5 public. A botanical verified below or above its studied range scores the same as one with no reference (12 = 12 = 12 raw). A collagen verified below range equals no reference (10 = 10), and a verified collagen overdose (12) outranks both. | 1,718 botanical no-reference products | `botanical_profile.py:796-892`, `generic_dose.py:400-445` |
| F8 | Evidence zero copy: the fact "0 in PharmaGuide's current evidence data" is attached to applicability and not-yet-reviewed states, and the authority copy appears at 0 points. | 3,210 / 40 | `pillar_explanations.py:105-120`, `quality_score.py:939-942` |
| F9 | Positive Evidence points are withheld from display (the pillar shows no number) yet still count in the total | 104 | app `pg_score_breakdown_card.dart:508` |
| F10 | Explanation text claims things that were not measured. **Dose:** "applicable PharmaGuide dose benchmarks" with no benchmark. **Formulation:** "well-absorbed forms" on profile routes. **Transparency:** "hidden in a proprietary blend" with no blend. | 1,712 / 1,572 / 4 | `quality_score.py:86-247` |
| F11 | Count, focus and single-only bonuses survive despite `.claude/rules/scoring.md` | 512 sports protein, 192 fiber, 456 sports single, 90 B-complex | §3 (COUNT) |
| F12 | Delivery claim subject is not established. Enrichment stores only the matched token; eligibility re-matches it. Example: 259879 "My probiotic blend contains acid resistant strains" was read as capsule delivery. | not yet censused | `enrich_supplements_v3.py:10916-10933`, `generic_helpers.py:73-76` |
| F13 | One detector, two awards: a branded studied botanical earns standardization 4 and branded 3 | 119 | `botanical_profile.py:667,727` |
| F14 | 155 `partial` products: 153 have unfinished Evidence at 0, 1 has unfinished Evidence at 4.4, and 1 is partial with an applicability state at 0. The total counts the unfinished pillar as scored. The app already labels these "Assessment incomplete". | 155 | app `catalog_product_semantics.dart:137-155` |
| F15 | Probiotic Evidence certainty earns up to 10 points while applicability is 0; generic routes give the same state 0 | 103 | `probiotic_evidence.py:115-118` |
| F16 | Many magnitudes are literals, not config; two dead registry keys; stale raw metadata says `production_score: rubric_raw_score_100` | — | §3 (LIT, DEAD); `generic.py:441-444` |
| F17 | A non-zero B5 or B6 blocks the complete-disclosure bonus (nominal 4 raw = 6 public). Measured: 2,251 products carry B5; 1,282 are on routes that have the bonus; 995 of those fail the bonus for other reasons anyway; in **287** the blend is the only blocker, so the double charge is realized. On sports protein an opaque blend also costs source quality (3), focus (1) and the named-source point. | 287 realized (2,251 nominal) | `generic_transparency.py:114-118`; `sports_formulation.py` |
| F18 | A raw Dose of `None` ("fail-open") is read by the public pillar as 0/20 (`quality_score.py:967`). Dormant: 0 stored scored products. | 0 | `generic_dose.py:718-723`; probiotic pending-AFU path `probiotic_dose.py:87-90` |
| F19 | A shipped Dose explanation fact says "Unresolved dose assessments can also trigger the fail-closed penalty". `_classify` penalizes only `confirmed_over_threshold` at ≥ threshold; `material_but_unresolved` is never penalized. | every product showing the dose-safety policy fact | `pillar_explanations.py:201`; `dose_safety.py:413-478` |

**Already single-owner (correct).**
- Manufacturer violations: Class I → Safety, otherwise → Verification.
- Titanium dioxide clean-label: Safety only (0 of 1,423 also appear in B1).
- Enhanced delivery vs form, after PR143, apart from F12.

## 3. Acceptance matrix: every score-bearing rule

**How a pillar is computed.**
- **Formulation, Dose, Evidence:** public = `clip(round(raw ÷ reference × 20, 1))`.
  - Formulation reference: profile first (generic_iqm / botanical / collagen 15), otherwise archetype (sports protein 29, fiber 28, multi 14, omega 12, probiotic 15, B-complex 23, others 24–30).
  - Dose reference: generic 22, botanical/collagen 21, immune 22, multi 23, sports/fiber/B-complex 25, omega 20, probiotic 22.
  - Evidence reference: generic/sports/fiber 18, immune 17, others 20.
- **Transparency:** public = raw × 15 ÷ raw max.
- **Verification and Safety:** assembled directly in `quality_score.py`.
- **Total:** `round(Σ pillars, 1)`; tier from the whole number.

**Classification rule for DUP-A.** A fact may inform several assessments. DUP-A is used only when the **same property** earns points in two places, which a counterfactual shows: remove the fact and more than one pillar drops for the same reason.
- Assessing the quality or adequacy of a disclosed fact is not a duplicate of the disclosure credit. Examples: omega form quality vs form disclosure; EPA+DHA adequacy vs EPA/DHA disclosure.
- A pillar awarding points merely because something is printed, without assessing it, is a duplicate.

**Classes.**

| Class | Meaning |
|---|---|
| DUP-D | Same concern deducted in two pillars |
| DUP-A | Same label fact awarded in more than one pillar |
| DUP-W | One detector, two awards in one pillar |
| BASE | Points for absence, unknown or unconditional, unlabelled |
| COUNT | Ingredient-count, focus or single-only rule |
| LIT | Literal magnitude in code |
| CTX | Claim subject or context not established |
| HIDE | Reduced award that acts as an invisible penalty |
| COPY | Explanation claims something not measured |
| MATCH | Owners use different match rules |
| FLOOR | Floor or cap absorbs or replaces the sum |
| DEAD | Registered, never emitted |
| RAW | Affects only internal `raw_score_v4_100` |

In the tables below:
- "Products" is the number of stored scored products where the key is non-zero.
- Each key appears in exactly one row, written as `section.key`. Pillar-level assembler rows use `pillar.<name>.<item>`.

### 3.1 Formulation (20)

| Key | Routes | Fact → condition | Kind | When unknown | Magnitude | Products | Classes |
|---|---|---|---|---|---|---:|---|
| `formulation.A1_bio_score` | generic, sports non-protein, fiber fallback | Mean IQM parent-relative form rating of scorable rows. On botanical and collagen routes, **overwritten with the profile score** (`generic_formulation.py:466-469`). | earned | Unrated rows skipped; none rated → `pillar.formulation.unrated_neutral` | 0–15 `formulation_magnitudes.a1_bio_score_cap` | 10,690 | COPY (key mislabels profile points) |
| `formulation.A3_delivery_system` | generic, sports, fiber | `eligible_delivery_data`: definition tier, https source, token re-match, not represented by resolved form | earned | 0 | 3/2/1 `a3_delivery_tier_points` | 1,277 | CTX (F12) |
| `formulation.A4_absorption_enhancer` | generic, sports, fiber | Enhancer paired with enhanced nutrient | earned | 0 | 3 `a4_absorption_cap` | 530 | — |
| `formulation.A5b_standardized_botanical` | generic, sports, fiber (0 under profiles) | `standardized_botanicals` meets threshold / marker only | earned | 0 | 1 / 0.5 `a5b_*` | 126 | — |
| `botanical_formulation.recognized_botanical_identity` | botanical profile | Primary botanical identity recognized | neutral (identity, not quality) | Not recognized → −4 row | 6 literal | 3,970 | BASE, LIT |
| `botanical_formulation.weak_or_unidentified_botanical` | botanical profile | Identity not recognized. The sum clamps at 0, so −4 never subtracts anything; the real effect is the missing +6 identity point. | deduction, effective 0 (unregistered) | — | −4 literal | 83 | LIT |
| `botanical_formulation.plant_part_disclosed` | botanical profile | `row.plantPart` present | disclosure | 0 | 2 literal | 2,233 | DUP-A, LIT |
| `botanical_formulation.quantified_dose_present` | botanical profile | `_mass_mg(row)` parsed | disclosure | 0 | 2 literal | 3,967 | DUP-A, LIT |
| `botanical_formulation.extract_not_whole_herb` | botanical profile | Extract token present and no "powder" | earned (wording) | 0 | 2 literal | 2,786 | LIT |
| `botanical_formulation.marker_standardization_declared` | botanical profile | Branded or meets threshold → 4; ≥75% → 3; ≥50% → 2; marker named with no amount → 1 | earned (tier 1 = disclosure) | 0 | `formulation_variant_magnitudes.botanical.standardization_tier_*` | 645 | DUP-W |
| `botanical_formulation.formulation_cap` | botanical profile | Profile sum capped (raw can reach 19) | cap | — | 15 `formulation_variant_magnitudes.botanical.botanical_formulation_cap` | not counted | FLOOR |
| `botanical_formulation.branded_clinically_studied_extract` | botanical profile | `_branded_studied_row` (also sets standardization to 4) | earned (evidence-derived) | 0 | 3 literal | 119 | DUP-W, LIT |
| `collagen_formulation.recognized_collagen_identity` | collagen profile | Collagen identity | neutral | — | 6 literal | 139 | BASE, LIT |
| `collagen_formulation.hydrolyzed_peptides` | collagen | Hydrolyzed / peptide wording | earned | 0 | 2 literal | 95 | LIT |
| `collagen_formulation.type_disclosed` | collagen | Collagen type stated | disclosure | 0 | 2 literal | 17 | DUP-A, LIT |
| `collagen_formulation.source_disclosed` | collagen | Source stated | disclosure | 0 | 3 literal | 68 | DUP-A, LIT |
| `collagen_formulation.quantified_dose_present` | collagen | Mass parsed | disclosure | 0 | 2 literal | 139 | DUP-A, LIT |
| `collagen_formulation.branded_clinically_studied` | collagen | Branded studied collagen | earned | 0 | 3 literal | 29 | LIT |
| `collagen_formulation.formulation_cap` | collagen | Profile sum capped | cap | — | 15 `collagen.collagen_formulation_cap` | not counted | FLOOR |
| `formulation.presence_floor` | generic formulation engine (generic, sports non-protein, fiber fallback) and multi; not sports-protein or fiber profiles | Module-level: mapped active, positive > 0, net < 2 | floor | — | 2 `formulation_magnitudes.presence_floor` / multi `formulation_presence_floor` | 582 | FLOOR (absorbs B0/B1) |
| `pillar.formulation.unrated_neutral` | generic_iqm with 0 rated forms | `iqm_form_quality_assessed_count == 0`; applied as `max(val, neutral)` **after** penalties | neutral floor | — | 12/20 public = `panel_form_neutral_floor ÷ bio_score_max` | 204 | BASE, FLOOR (absorbs B0/B1 while the Safety mirror still charges B1) |
| `formulation.panel_form_quality` | multi | Row IQM ratings; the **panel average** is floored at 9, so a panel of poorly rated forms is also lifted to neutral | earned + neutral floor | 9 (panel average) | `(max(avg, 9) ÷ 15) × 12` (`cap_panel_form_quality`, `panel_form_neutral_floor`) | 2,052 | BASE, FLOOR |
| `formulation.panel_disclosure_structure` | multi | Share of rows dosed (≥90% → 2, ≥60% → 1) | disclosure | 0 | cap 2 `cap_panel_disclosure_structure`; thresholds literal | 1,997 | DUP-A, LIT |
| `formulation.b_form_quality` | B-complex | IQM rating; unrated mapped row = 10 | earned + neutral | 10 | (avg ÷ 15) × 8 literal | 146 | BASE, LIT |
| `formulation.core_b_panel_coverage` | B-complex | Core B rows present ÷ core panel | category panel | 0 | × 10 literal | 146 | LIT (panel kept) |
| `formulation.b_complex_focus_purity` | B-complex | Number of non-B actives → 3/2/0 | count | — | literal | 90 | COUNT, LIT |
| `formulation.dose_disclosure` | B-complex | Share of rows dosed | disclosure | 0 | × 2 literal | 146 | DUP-A, LIT |
| `formulation.form_tier` | omega | IQM parent-relative form rating (IQM "unspecified" rating when not disclosed) | earned | IQM unspecified | `omega_rubric.json formulation.form_quality` | 709 | — (assesses form quality; the disclosure credit is `transparency.form_disclosed`) |
| `formulation.epa_dha_concentration` | omega | EPA+DHA ÷ oil mass (Total Fat fallback) | earned | Total Fat fallback | 4/3/2/1 `omega_rubric.json` | 620 | — |
| `formulation.total_cfu_disclosed` | probiotic | Total CFU > 0 | disclosure | 0 | 4 `probiotic.cap_total_potency_disclosure` | 519 | DUP-A |
| `formulation.exact_identity_completeness` | probiotic | Strains identified to strain level | disclosure | 0 | 8 × ratio `cap_exact_identity_completeness` | 424 | DUP-A |
| `formulation.delivery_survivability` | probiotic | Delivery coating + tier; a studied formula gets 3 unconditionally | earned | 0 | 3; tier 2 → 2.5, tier 3 → 1.5 (literal) | 224 | CTX (F12), LIT |
| `formulation.native_potency_disclosed` | probiotic studied formula | Studied formula potency (same detector feeds `transparency.aggregate_native_afu_disclosure` and the studied Dose) | earned | 0 | 4 | 1 | DUP-A |
| `formulation.studied_formula_strain_identity` | probiotic studied formula | Studied formula identity | earned | 0 | 8 | 1 | — |
| `formulation.sports_protein_source_quality` | sports protein | Source class: whey isolate 15, casein 14, whey/soy 13, complete plant 12, pea 9, rice 8, unnamed protein 6, collagen 4, opaque blend 3 | earned | 6 (unnamed) | literal | 512 | LIT, DUP-D (opaque blend also charged by B5, focus 1, lost named-source point) |
| `formulation.sports_protein_dose_transparency` | sports protein | Protein grams + named source | disclosure / earned | 0 | ≤5 literal | 512 | DUP-A, LIT |
| `formulation.sports_amino_profile_disclosure` | sports protein | EAA / BCAA / leucine rows present | disclosure | 0 | 3/2/1.5 literal | 139 | DUP-A, LIT |
| `formulation.sports_protein_focus` | sports protein | Count of non-accessory dosed rows (≤2 → 4, else 3; collagen/opaque 1) | count | — | literal | 512 | COUNT, LIT |
| `formulation.sports_route_base` | sports protein | Unconditional | neutral | — | 2 `formulation_variant_magnitudes.sports.route_base` | 512 | BASE |
| `formulation.fiber_source_quality` | fiber | Fiber source class (3 = claim with no mapped fiber) | earned | 3 | 12–3 literal | 192 | LIT, DUP-A (the same property, fiber type, also earns `dose.fiber_type_specificity`) |
| `formulation.fiber_disclosure` | fiber | Grams and/or named type | disclosure | 0 | 6/4/3 literal | 190 | DUP-A, LIT |
| `formulation.fiber_formula_focus` | fiber | Active-row count; stimulant laxative → 1 | count + reduced award | 2 (no rows) | 5/3/2/1 literal | 192 | COUNT, HIDE, LIT |
| `formulation.fiber_route_base` | fiber | Unconditional | neutral | — | 5 `fiber_digestive.route_base` | 192 | BASE |
| `formulation.fiber_practicality` | fiber | Product name contains cleanse/detox → 0.5 | neutral (name-based) + reduced award | 2 | 2 / 0.5 literal | 192 | HIDE, LIT |
| `formulation.B0_moderate_watchlist` | all | Gate concern with `match_resolution == confirmed`: high-risk 10, watchlist 5, moderate severity 10 (moderate severity does not affect the Safety base) | deduction | — | `b0_high_risk_penalty` / `b0_watchlist_penalty` / `b0_moderate_penalty`; cap 30 = `formulation_magnitudes.dimension_cap` | 348 | DUP-D (F4), MATCH |
| `formulation.B1_harmful_additives` | all | `harmful_additives` rows after active-source suppression | deduction | — | 4/3/2/0.5, cap 15 `formulation_penalties` | 7,891 | DUP-D (F1) |
| `formulation.B1_dietary_sugar` | all | `dietary_sensitivity_data.sugar` | deduction | — | 1/1/2/3/4, cap 4 `fm.dietary_sugar_*` | 2,534 | DUP-D (F1) |
| `formulation.immune_high_variability_botanical_stack` | immune profile | ≥3 high-variability botanicals | deduction | — | 3 `category_magnitudes.immune_support` | 0 | — |
| `formulation.sports_opaque_protein_blend` | sports protein | Opaque protein matrix | deduction | — | 8/6 literal | 29 | DUP-D (with B5), LIT |
| `formulation.sports_amino_spiking_risk` | sports protein | Free-amino spiking pattern | deduction | — | 6/3 literal | 8 | LIT |
| `formulation.sports_collagen_not_complete_protein` | sports protein | Collagen as protein source | deduction | — | 8 literal | 6 | LIT |
| `formulation.fiber_cleanse_detox_penalty` | — | Registered, never emitted | — | — | — | 0 | DEAD |
| `formulation.fiber_stimulant_laxative_penalty` | — | Registered, never emitted | — | — | — | 0 | DEAD |

### 3.2 Dose (20)

| Key | Routes | Fact → condition | Kind | When unknown | Magnitude | Products | Classes |
|---|---|---|---|---|---|---:|---|
| `dose.supplemental_window_proxy` | generic, fiber | `rda_ul_data` % of RDA/AI at minimum directed intake, % of UL at maximum. DRI: 11 → 22 across 20–100% RDA; clinical anchor proportional; legacy 25% threshold; UL > 100% → 11; ≥150% → 0. Also averages per-purpose specialized owners (botanical, collagen, sleep, joint, immune purpose dose; immune purpose zeroes zinc > 40 mg and vitamin D > 100 mcg), aggregate-formula benchmarks and clinical benchmarks (`generic_dose.py:312-375`). Capped at 16 when a mass-primary active is unassessed (686-694). | earned (UL reduces it) | No reference: 16 if individually dosed, 12 for a blend anchor; nothing → raw `None`, which the public pillar reads as 0 (F18, dormant) | `dose_magnitudes.generic.*`; immune purpose scale 22 literal | 6,144 | DUP-A (no-reference credit is a disclosure reward), HIDE (UL; the 16 cap), COPY |
| `dose.botanical_clinical_dose` | botanical | Primary row mass × minimum servings vs `botanical_dosing` range. Within 21, near 16, above 12, below 12, no reference 12, blend total or product anchor 10, no amount 5, no botanical 0. | earned / graded / neutral + disclosure | 12 with amount, 5 without | `formulation_variant_magnitudes.botanical.botanical_dose_*` | 3,827 | DUP-A, COPY (1,712), F7 tie |
| `dose.collagen_clinical_dose` | collagen | Collagen grams vs reference: within 21, near 16, above 12, below 10, no reference 10, blend 7, no amount 0 | earned / graded / neutral | 10 (amount printed), 0 (none) | literal (`collagen_profile.py:180-206`) | 115 | LIT, DUP-A, F7 (below = no reference; overdose outranks both) |
| `dose.joint_support_dose` | joint | Glucosamine / chondroitin / MSM / UC-II / HA vs target | earned | — | 22 / 20 / ratio × 20 literal; targets `category_magnitudes.joint_support` | 162 | LIT |
| `dose.sleep_support_dose` | sleep | Melatonin bands 8/22/20/17/11/5/2; 5-HTP bands 8/16/12/8 (minimum and maximum directed intake) | earned (graded) | — | literal (`sleep_support.py:113-136`) | 210 | LIT |
| `dose.vitamin_c_daily_range` | immune whole-route adapter (single purpose) | Vitamin C daily mg band 100–1,000 | earned | 0 | 3 `category_magnitudes.immune_support.dose_bands`; above band × 0.5 | 0 (dormant) | — |
| `dose.vitamin_d_daily_range` | immune adapter | Vitamin D band 15–50 mcg; zeroed above 100 mcg | earned + UL zero | 0 | 3; `high_vitamin_d_threshold_mcg` | 0 (dormant) | HIDE |
| `dose.zinc_daily_range` | immune adapter | Zinc band 8–25 mg; zeroed above 40 mg | earned + UL zero | 0 | 3; `high_zinc_threshold_mg` | 0 (dormant) | HIDE |
| `dose.copper_balance` | immune adapter | Copper band 0.5–2 mg | earned | 0 | 1.5 | 0 (dormant) | — |
| `dose.selenium_daily_range` | immune adapter | Selenium band 45–200 mcg | earned | 0 | 1.5 | 0 (dormant) | — |
| `dose.beta_glucan_disclosed` | immune adapter | Beta-glucan band 100–250 mg | earned | 0 | 3 | 0 (dormant) | — |
| `dose.quercetin_disclosed` | immune adapter | Quercetin band 250–1,000 mg | earned | 0 | 2.5 | 0 (dormant) | — |
| `dose.elderberry_disclosed` | immune adapter | Elderberry band 100–600 mg | earned | 0 | 2.5 | 0 (dormant) | — |
| `dose.daily_use_discipline` | immune adapter | No zinc > 40 mg and no vitamin D > 100 mcg | neutral (absence) | — | 2 `daily_use_discipline_points`; cap 22 `dose_cap` | 0 (dormant) | BASE, HIDE, DUP-D (with B7) |
| `dose.rda_ai_coverage` | multi | Panel RDA/AI coverage | earned | — | avg × 15 `multi_prenatal.cap_rda_ai_coverage` | 2,052 | — |
| `dose.panel_breadth` | multi | Count of covered nutrients ÷ 18 (open-ended: adding a nutrient raises Dose) | count | — | × 3 `cap_panel_breadth`, `panel_breadth_full_count` | 2,052 | COUNT |
| `dose.critical_nutrient_coverage` | multi | Folate/iron/iodine/D/B12/choline minimum % RDA | earned | — | × 5 `cap_critical_nutrient_coverage` | 2,050 | — |
| `dose.prenatal_complement_support` | prenatal | Choline (pregnancy threshold) and DHA 200/100 mg | earned | — | × 2 `cap_prenatal_complement_support` | 72 | DUP-W (choline also earns `critical_nutrient_coverage`) |
| `dose.b_rda_ai_coverage` | B-complex | Coverage average | earned | — | × 18 literal | 146 | LIT |
| `dose.core_b_panel_breadth` | B-complex | Covered ÷ core | category panel | — | × 4 literal | 146 | LIT |
| `dose.moderate_dose_fit` | B-complex | b7 == 0 and coverage; withdrawn whenever B7 > 0 | neutral (absence) | — | 3 literal | 97 | BASE, LIT, HIDE, DUP-D (F2) |
| `dose.epa_dha_band` | omega | EPA+DHA per day bands; prenatal DHA 20/14/10 | earned | — | 20/20/16/10/5/4/2.5/0 `omega_rubric.json`; prenatal literal | 605 | — |
| `dose.per_strain_cfu_disclosure` | probiotic | Strains with individual CFU | disclosure | 0 | 10 × ratio `cap_per_strain_cfu_disclosure` | 145 | DUP-A |
| `dose.cfu_adequacy` | probiotic | Strain-owned CFU tiers; aggregate floor 2/4; strain-mass floor 5; guarantee ×0.9 / ×0.85 | earned + floors | Floors | `dose_magnitudes.probiotic.*`; multipliers literal | 464 | FLOOR, LIT |
| `dose.studied_formula_dose_adequacy` | probiotic studied formula | Studied formula amount | earned | — | 25 `cap_dose` | 1 | — |
| `dose.sports_primary_active_dose` | sports | Grams per identity band; off-list → generic Dose proxy | earned | Proxy | 0–20 literal | 901 | LIT |
| `dose.sports_stack_support` | sports | Other sports groups present (+1 each, cap 3) | presence | — | literal | 118 | COUNT, LIT |
| `dose.sports_ratio_or_completeness` | sports | BCAA ratio / complete EAA | earned | — | 2 literal | 102 | LIT |
| `dose.sports_focused_single_completion` | sports | Primary ≥20 and single group | single-only bonus | — | 5 literal | 456 | COUNT, LIT |
| `dose.fiber_effective_dose` | fiber | Daily grams: 22/18/13/7, or max(1, 4 × g) | earned | — | literal | 190 | LIT |
| `dose.fiber_type_specificity` | fiber | Psyllium etc. 2 / inulin etc. 1 | earned | — | literal | 183 | LIT, DUP-A (with `fiber_source_quality`) |
| `dose.fiber_dose_disclosure` | fiber | Grams > 0 | disclosure | 0 | 1 literal | 190 | DUP-A, LIT |
| `dose.B7_dose_safety` | all (universal adapter) | Only `confirmed_over_threshold` flags at ≥150% of a UL are penalized. Unresolved, not-applicable and conversion-failed states are not. | deduction | — | −2/flag, cap 3 `dose_safety_policy` | 403 | DUP-D (F2), COPY (F19) |
| `dose.opaque_primary_sports_blend` | sports | Primary dose 0 and blend none/partial | deduction | — | −10 literal | 9 | DUP-D (with B5), LIT |

### 3.3 Evidence (20)

| Key | Routes | Fact → condition | Kind | When unknown | Magnitude | Products | Classes |
|---|---|---|---|---|---|---:|---|
| `evidence.clinical_evidence_pipeline` | generic, sports, fiber | Applicable matched records (effect × enrollment × design), top-N | earned | 0 | ≤7 per ingredient, weights `evidence_magnitudes.generic` | 6,694 | — |
| `evidence.depth_bonus` | generic, sports, fiber | Published study count ≥20 / ≥40 | earned | 0 | 0.25 / 0.5 | 439 | — |
| `evidence.primary_evidence_floor` | generic, sports, fiber | Prominent active with positive strong/moderate evidence (14/11, branded 18/17), or nutrition authority (10). **Not additive:** the score is the maximum of pipeline and floor. | floor | — | `primary_floor_*`, `nutrition_authority_floor` | 6,909 | FLOOR |
| `evidence.immune_support_evidence_cap` | immune | Cap 17 (minimum). It equals the immune Evidence reference (17), so public Evidence is 20 with or without it | cap, no public effect | — | `category_magnitudes.immune_support.evidence_cap` | 44 | RAW |
| `evidence.joint_support_evidence_cap` | joint | Cap 14 | cap | — | `joint_support.evidence_cap` | 25 | FLOOR |
| `evidence.evidence_family_certainty` | probiotic | Strain-family research certainty, counted even when applicability is 0 | earned | 0 | ≤10 `probiotic.certainty_cap` | 339 | F15 |
| `evidence.product_applicability` | probiotic | 6 × alignment (direct 1, partial 0.75, broad 0.5) × identity weight; 0 whenever certainty is 0 | earned | 0 | ≤6 `applicability_cap`, `alignment_weights` | 236 | — |
| `evidence.independent_replication_consistency` | probiotic | Independent same-condition replication: 4 × consistency credit (the config doc states 0/2/4; the credit steps themselves were not traced) | earned | 0 | ≤4 `replication_cap` | 4 | — |
| `evidence.clinical_evidence` | omega | Reviewed purpose standard, gated on explicit EPA+DHA identity, population and purpose (`evidence_resolver.py:333-355`): weak 10.4, triglyceride 20, prenatal DHA 11.1; amount-independent | earned (reviewed purpose evidence) | Held states score 0 | `evidence_magnitudes.omega.purpose_standards` | 453 | — |
| `evidence.essential_panel_authority` | multi | Expected essential nutrients whose resolver disposition is `RESOLVED_BY_AUTHORITY`, ÷ expected × 20 (`evidence_resolver.py:1580-1625`) | earned (authority-backed) | Unresolved nutrients score 0 | `multi_prenatal.cap_evidence` | 2,048 | — (magnitude is a separate policy question) |
| `evidence.b_nutrient_authority_panel` | B-complex | Same resolver over the fixed core B panel | earned (authority-backed) | Unresolved nutrients score 0 | 20 | 146 | — |
| `pillar.evidence.result_state` | all | `evidence_result_state` → `display_state` → copy and facts | display | not_yet_reviewed / applicability / not_applicable withhold the number in the app | — | 15,123 | COPY (F8), HIDE (F9, F14) |

### 3.4 Transparency (15)

| Key | Routes | Fact → condition | Kind | When unknown | Magnitude | Products | Classes |
|---|---|---|---|---|---|---:|---|
| `transparency.clear_disclosure_base` | generic, sports, fiber, B-complex | **Unconditional** | neutral | — | 6 → 9 public `transparency_magnitudes.generic.clear_disclosure_base` | 11,827 | BASE (named as disclosure) |
| `transparency.complete_active_identity_dose_disclosure` | generic, sports, fiber, B-complex | Every declared active identified and dosed; withheld whenever B5 or B6 is non-zero | disclosure | 0 | 4 → 6 public | 10,315 | DUP-A, HIDE, DUP-D (F17) |
| `transparency.B3_claim_compliance` | generic, sports, fiber, B-complex, multi | All b3 magnitudes 0 | — | — | 0 | 0 | inert |
| `transparency.hypoallergenic_bonus` | same | Literal 0 | — | — | 0 | 0 | inert |
| `transparency.panel_identity_disclosure` | multi | Panel identity ratio | disclosure | 0 | 5 × ratio | 2,052 | — |
| `transparency.panel_individual_dose_disclosure` | multi | Panel dose ratio | disclosure | 0 | 10 × ratio | 2,052 | DUP-A |
| `transparency.strain_identities_named` | probiotic | Strains named | disclosure | 0 | ≤8 | 530 | DUP-A |
| `transparency.per_strain_cfu_on_label` | probiotic | Per-strain CFU | disclosure | 0 | 7 × ratio | 145 | DUP-A |
| `transparency.aggregate_cfu_disclosure_proxy` | probiotic | Total CFU (4/3/2 minus per-strain points) | disclosure | 0 | 4 `cap_aggregate_cfu_disclosure_proxy`; 3/2 literal | 381 | DUP-A, LIT |
| `transparency.aggregate_native_afu_disclosure` | probiotic studied formula | Studied formula potency | disclosure | 0 | 4 | 1 | DUP-A |
| `transparency.epa_or_dha_disclosed` | omega | EPA or DHA printed | disclosure | 0 | 5 `omega_rubric.json` | 656 | — (disclosure only; adequacy is the Dose band, concentration is Formulation) |
| `transparency.form_disclosed` | omega | Molecular form printed | disclosure | 0 | 3 | 261 | — |
| `transparency.source_disclosed` | omega | Source printed | disclosure | 0 | 3 | 687 | — |
| `transparency.B2_false_allergen_free_claim` | all | Free-from claim contradicted | deduction | — | 2/1.5/1, cap 2 | 809 | COPY (4 products show blend text) |
| `transparency.B5_proprietary_blend_opacity` | all | Blend hides amounts | deduction | — | base + proportional × class multiplier, cap 10 (multi adjunct 2) | 2,251 | DUP-D (sports Dose / Formulation, botanical blend band) |
| `transparency.B6_marketing_claims` | all | Disease claim | deduction | — | 5 | 0 | — |

### 3.5 Verification (15): assembler `quality_score.py::_pillar_verification`

| Key | Fact → condition | Kind | When unknown | Magnitude | Products | Classes |
|---|---|---|---|---|---:|---|
| `pillar.verification.neutral_baseline` | Starting point of every tier: `base = 6 + signals` (claim ceiling 8, manufacturing ceiling 10, product floor 11). Pure unknown = 6. | neutral (policy baseline, kept at 6) | — | 6 `verification_subscale.neutral_baseline` | 5,623 pure unknown; part of 14,302 below product level | BASE (to be labelled, not removed) |
| `verification_bonus.B4a_verified_certifications` (omega `b4a_…`) | Registry SKU/product-line cert → pillar `cert` 12/9/5; label-asserted → 2 | earned | 0 | `cert_tiers`, `label_asserted_cert_points` | 1,342 (pillar `cert`) | — |
| `verification_bonus.B4b_gmp` (omega `b4b_…`) | Audited basis and b4b ≥ 4 → pillar `gmp` 2 | earned | 0 | `gmp_certified_points` | 4,112 | — |
| `verification_bonus.B4c_batch_traceability` (omega `b4c_…`) | COA or batch lookup (label/QR-derived) → `coa_batch` (b4c ÷ 2) × 5 | earned (claim tier) | 0 | `coa_batch_max` | 183 | — |
| `verification_bonus.B4d_brand_testing_posture` (omega `b4d_…`) | Brand testing posture → `brand_testing` 2 | earned (claim tier) | 0 | `brand_testing_points` | 9,030 | — |
| `pillar.verification.brand_only_cert` | Verified brand/facility-scoped cert, no registry cert | earned | 0 | 2 `brand_only_cert_points` | 1,296 | — |
| `manufacturer_trust.D1_manufacturer_reputation` | Reputation → `reputation` ≤2; excluded when mid-tier comes from verified evidence | earned (claim tier) | 0 | `reputation_cap` | 9,340 | — |
| `pillar.verification.tier_bounds` | Claim/brand ceiling 8, manufacturing ceiling 10, product floor 11 (inert: 6 + the minimum product cert of 5 already equals 11), cap 15 | cap / floor | — | `tier_ceilings`, `product_level_floor`, `cap` | 15,123 | FLOOR |
| `manufacturer_violations.manufacturer_violation_deduction` | Without Class I → Verification `quality_system_violation_penalty`; with Class I in 3 years → Safety `class_i_recall_penalty` | deduction (single owner) | — | Raw magnitude, floor −25 / −35 / −50 `verification_magnitudes.manufacturer` | 8 | — |
| `manufacturer_trust.D2_disclosure_quality` | Raw score only | — | — | 1 | 12,123 | RAW |
| `manufacturer_trust.D3_physician_formulated` | Raw score only | — | — | 0.5 | 45 | RAW |
| `manufacturer_trust.D4_high_standard_region` | Raw score only | — | — | 1 | 9,380 | RAW |
| `manufacturer_trust.D5_sustainability` | Raw score only | — | — | 0.5 | 1,129 | RAW |

### 3.6 Formula & quality checks (10): assembler `quality_score.py::_pillar_safety_hygiene`

| Key | Fact → condition | Kind | When unknown | Magnitude | Products | Classes |
|---|---|---|---|---|---:|---|
| `safety_hygiene_base.no_banned_high_risk_or_watchlist_match` | No banned/high-risk/watchlist gate concern of any match resolution. Any one match zeroes **both** base components. | neutral (absence) | — | 2 literal → contributes to `clean_base` 10 | 14,766 | BASE, DUP-D (F4), MATCH, LIT |
| `safety_hygiene_base.no_recalled_match` | No recalled gate concern | neutral (absence) | — | 2 literal | 14,766 | BASE, LIT |
| `pillar.safety_hygiene.class_i_recall_penalty` | Manufacturer Class I recall within 3 years | deduction | — | Raw violation magnitude | 0 | — |
| `pillar.safety_hygiene.clean_label_penalty` | `clean_label_hits` (for example TiO2): base × role multiplier; unmapped role uses 0.5 | deduction (unregistered) | — | cap 5 `clean_label_subscale`; default multiplier literal | 1,423 | LIT |
| `pillar.safety_hygiene.additive_or_sweetener_penalty` | Mirror of B1, excluding low severity | deduction | — | cap 4 `additive_or_sweetener_max_penalty` | 3,509 | DUP-D (F1) |
| `pillar.safety_hygiene.over_ul_penalty` | Mirror of B7 | deduction | — | cap 3 `over_ul_max_penalty` | 403 | DUP-D (F2) |
| `pillar.safety_hygiene.dose_safety_state_counts` | UL explanation only (0 points) | display | — | — | 1,085 | COPY (F3: 339 caution at 10/10) |

**Raw-only and inert items.** None of these reaches a public pillar:
- the `verification_bonus` ×8÷15 rescale;
- the `safety_hygiene_base` raw adjustment;
- `botanical_raw_floor` 40 (inert: `botanical_dose_deferred` is always False);
- `audit_affine_v3_compare`.

## 4. Unknown-state treatment today

| Unknown | Today | Shown as |
|---|---|---|
| No Verification record | 6/15 neutral policy baseline (kept) | "treated as unknown, not penalized" |
| No dose benchmark | Botanical 11.4 / generic 14.5 / collagen 9.5 public, only if the amount is printed | "partial credit against the applicable benchmarks" (botanical) |
| Amount hidden in a blend | Botanical 9.5, collagen 6.7; sports Dose −10 penalty; Transparency also withholds the complete-disclosure bonus | Not separated from verified bands |
| Form unrated | 12/20 floor after penalties (generic); panel average floored at 9/15 (multi); 10 per row (B-complex) | "not rated" (generic only) |
| Botanical identity recognized, quality unrated | 6 raw (8.0 public) | Folded into `A1_bio_score` |
| Evidence under review | 0 counted in the total; app shows "Assessment incomplete" | Pillar number withheld |
| Evidence applicability not established | 0 (generic) or up to 10 (probiotic) | Number withheld, even when positive |
| No catalog concern matched | 10/10 | "Strong"; listed as a strength |

## 5. Open decisions for Step 3

Measure each as a complete option set; nothing changes until Sean chooses.
1. Remove the Safety mirrors (F1, F2).
2. B0 owner (F4): the sixth pillar (Claude) or none (Codex), with one match rule.
3. Retire points awarded only because something is printed (F5): Transparency owns disclosure.
4. Unknown Dose adequacy (F7): one route-uniform neutral, graded inadequacy, and the invariant that hiding an amount cannot raise the total (Dose and Transparency together).
5. Dose for an amount hidden in a blend: same neutral as no-benchmark, opacity owned by Transparency. Do not set `not_scored`.
6. Unrated-form neutral, including recognized botanical identity: one value, labelled `neutral`.
7. Re-express the Transparency base as earned components (identity + amounts).
8. Remove COUNT bonuses and route bases; keep category reference panels.
9. Remove the DUP-W branded double (F13).
10. Probiotic certainty without applicability (F15).
11. Additive/sugar owner: Formulation or the sixth pillar.
12. Delivery claim subject (F12): a correctness fix with a fail-first test.

Verification stays at 6 throughout. Tier review comes only after the new distribution exists.

## 6. Evidence ledger

| Claim | Proof |
|---|---|
| Meru 55.7 = 13.3 + 11.4 + 0 + 15 + 6 + 10 | `meru-scored.json` `quality_pillars_v4`; live rescore of `meru-enriched.json` on `codex/shilajit-mapping` with project Python returned 55.7 |
| A printed amount is worth 6.6 Dose points to Meru | Same rescore with shilajit amount fields cleared → Dose 4.8, total 49.1 |
| Total = Σ pillars for 15,123 products | Corpus probe (§7, `identity`) |
| F1–F4, F9, F14 counts | Corpus probe (§7) |
| B0 counts confirmed matches only; the hygiene base counts any resolution | `generic_formulation.py:281-289`; `safety_hygiene.py:80-147` |
| F12 delivery context | `enrich_supplements_v3.py:10916-10933` stores `matched_text`; enriched statements of 259879 / 278019 / 298070 |
| App partial handling exists | `catalog_product_semantics.dart:137-155`; `pg_hero_section.dart:363` |
| B7 is emitted on every route | Corpus census: B7 key present on all 15,123; non-zero on generic, multi, B-complex, fiber and sports |
| Verification census | Corpus probe (§7, `verification`) |
| Corpus coverage: every key observed in the stored catalog has a row | `check_matrix` in §7 (114 observed keys, 0 missing). This proves inventory coverage only, not that each row's description is correct. |
| Code-path coverage | From code review, not the corpus: dormant keys (immune whole-route adapter, immune stack penalty, B6, the `None` Dose paths) and assembler operations (floors, caps, mirrors, tier bounds, rounding). |
| No duplicate rows | `dup_rows` check in §7 (the set-based `check_matrix` cannot detect duplicates) |
| Matrix accuracy | Fresh-context review checked 106 of the original 124 rows: 88 correct, 18 defective, all corrected after re-verification in code. The reviewer's reconstructed list of its 18 unchecked rows (A4, probiotic CFU and Evidence rows, sports Dose rows, B7 unresolved case, essential panel, probiotic Transparency, D2–D5, dose-state counts) and the 11 rows added in revision were then verified in code by Claude. A second review corrected the omega DUP-A, authority-Evidence and causal-count claims (F2, F3, F14, F17) and found F19. |

## 7. Reproduction probe

Run from the primary checkout, which holds the stored corpus. It writes nothing.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'EOF'
import json, glob, collections, re, statistics
AUDIT = '.claude/worktrees/score-ledger/scripts/audits/score_accounting_20261014/AUDIT.md'
row_list = re.findall(r'^\| `([a-z_0-9]+\.[A-Za-z_0-9.]+)`', open(AUDIT).read(), re.M)
rows = set(row_list)
dup_rows = sorted(k for k, c in collections.Counter(row_list).items() if c > 1)
n = lambda x: float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0
C = collections.Counter(); keys = set(); ver = collections.defaultdict(list)
for f in sorted(glob.glob('scripts/products/output_*_scored/scored/*.json')):
    d = json.load(open(f)); d = d if isinstance(d, list) else d.get('products', [])
    for p in d:
        if p.get('quality_score_status') != 'scored': continue
        P = p['quality_pillars_v4']; mb = p['_v4_module_breakdown']; dims = mb['dimensions']
        C['scored'] += 1
        C['identity_fail'] += abs(round(sum(v['score'] for v in P.values()), 1) - p['quality_score_v4_100']) > 0.05
        for dn, dim in dims.items():
            for kind in ('components', 'penalties'):
                keys |= {f'{dn}.{k}' for k in (dim.get(kind) or {})}
        fm = dims['formulation'].get('metadata') or {}
        keys |= {f'botanical_formulation.{k}' for k in (fm.get('botanical_formulation') or {})}
        keys |= {f'collagen_formulation.{k}' for k, v in (fm.get('collagen_formulation') or {}).items() if isinstance(v, (int, float))}
        for sec in ('verification_bonus', 'manufacturer_trust', 'manufacturer_violations', 'safety_hygiene_base'):
            keys |= {f'{sec}.{k}' for k in ((mb.get(sec) or {}).get('components') or {})}
        sc = P['safety_hygiene']['components']; fp = dims['formulation']['penalties']
        C['F1_b1_twice'] += n(sc.get('additive_or_sweetener_penalty')) > 0 and (n(fp.get('B1_harmful_additives')) < 0 or n(fp.get('B1_dietary_sugar')) < 0)
        C['F2_b7_twice'] += n(sc.get('over_ul_penalty')) > 0 and n(dims['dose']['penalties'].get('B7_dose_safety')) < 0
        C['F3_caution_10'] += p['product_safety_status'] == 'caution' and P['safety_hygiene']['score'] == 10
        C['F4_b0_twice'] += n(fp.get('B0_moderate_watchlist')) < 0 and n((mb.get('safety_hygiene_base') or {}).get('score')) < 4
        ev = P['evidence']
        C['F9_hidden_points'] += ev.get('display_state') in ('applicability_unestablished', 'not_yet_reviewed') and ev['score'] > 0
        C['F14_partial'] += p.get('quality_assessment_status') == 'partial'
        ver[P['verification']['components'].get('tier')].append(p['quality_score_v4_100'])
print(dict(C))
print({t: (len(v), round(statistics.median(v), 1)) for t, v in ver.items()})
def norm(k):  # omega lowercase verification keys share the uppercase row
    return re.sub(r'^verification_bonus\.b4([a-d])_', lambda m: f'verification_bonus.B4{m.group(1)}_', k)
missing = sorted(k for k in keys if norm(k) not in rows)
print('check_matrix: census keys', len(keys), 'missing rows', missing, '| rows', len(row_list), 'duplicates', dup_rows)
EOF
```

## 8. Step 2 receipt contract (zero numerical or state change)

Each scored pillar in `quality_pillars_v4` gains `receipt` (named so to avoid the existing "Row ledger"), built by `quality_score.py` from the module breakdown it already reads.

**Fields.**
- `entries`: ordered signed score effects in public pillar points. Each entry is `{id, kind, source, raw, points}`.
  - `kind` is one of `earned | neutral | disclosure | deduction | floor | cap | rounding`.
  - Positive kinds add points, `deduction` is negative, and `floor` and `cap` carry their own sign.
  - `rounding` entries: `rounding` is the residue of the pillar's 0.1 rounding (≤ 0.05 plus four-decimal reporting residue). `module_rounding` is where a module rounds its dimension to 0.01 (omega, probiotic), at most 0.006 raw.
- `nominal_deductions`: the sum of `deduction` entries (≤ 0).
- `realized_deductions`: the pillar score minus the score the same assembler returns with every deduction set to zero (≤ 0). It is computed, not inferred, so a floor that absorbs a penalty shows as a realized effect smaller than the nominal one.
- `unawarded`: `max − score_without_deductions`. This is capacity not earned. It is **not** an entry and does not add into the sum.

**Invariants.** The contract test checks each of these on every product.
1. `Σ entries.points == pillar.score`, exactly, after rounding.
2. `max == score + unawarded − realized_deductions`.
3. `Σ pillar.score == quality_score_v4_100`, exactly, after rounding.
4. **Nested detail replaces its aggregate.** On botanical and collagen routes, the profile components replace `A1_bio_score`; they are never added on top of it. Evidence floors and caps are `floor`/`cap` entries, never addends.
5. **Every public score-bearing operation appears once:**
   - normalization (the raw × weight ÷ reference factor on every raw entry);
   - clamps at 0 and at max;
   - the module presence floor and the pillar unrated-form neutral;
   - multi panel-average floor lift, B5 or B6 bonus withholding (a zero-valued disclosure entry with a reason);
   - Verification baseline, signals, tier ceilings, product floor and violation;
   - Safety base, Class I, clean-label and both mirrors;
   - per-pillar rounding.
6. **Excluded keys are listed with a reason and never become entries:**
   - raw-only: D2–D5, the verification-bonus rescale, the safety-base raw adjustment, `botanical_raw_floor`;
   - inert zeros: `B3_claim_compliance`, `hypoallergenic_bonus`;
   - nested subtotals: `A1_bio_score` when a profile applied;
   - display-only: `dose_safety_state_counts`.
7. **Zero delta.** Re-assembling every stored module breakdown with the new code reproduces the stored `score`, `max`, tier, statuses and `evidence_result_state` byte-for-byte. Only `reason`, `explanation` and the new `ledger` may differ.

**Proof order.**
- First, representative fixtures: one per route, plus floors, caps, both mirrors, unknown baselines, an unrated form, an Evidence floor and cap, a hidden positive Evidence number, a partial product and each dormant path.
- Then reconciliation across all 15,123 stored scored products.
- Existing partial-assessment behaviour (`quality_assessment_status`, `catalogProductAssessmentIncomplete`) is preserved; its consumers are verified, not replaced.

**Copy corrections in the same step:** F8, F10, F19, the Verification "neutral 6, 9 not earned" wording, the sixth-pillar scope wording, baselines removed from `strengths`, and the stale `production_score` label. Scores, states and safety stay unchanged.
