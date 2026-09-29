# Dose model proposal: decision material (2026-09-29)

**Status: decision material, not a validated scoring specification.** Nothing here changes scoring.
Numbers come from a read-only calculation over real labels: `dose_proposal_v2.py` (per-row
assessment) and `v2_report.py --no-g2` (every option on the same rows), over 365 labels (the
release-readiness sample and the targeted set) plus the agreed products. Full output:
`dose_proposal_v2_report.txt`. The first replay (2026-09-28) and its numbers are in git history
(30c4c46a, a6728788) and are superseded.

Target, from the reviews: the same amount and identity get the same assessment regardless of label
formatting; low doses get proportionate credit; missing knowledge is represented honestly; safety
cannot disappear inside an attractive total.

## Accepted

| Rule | Evidence |
|---|---|
| Proportional credit, `min(amount / benchmark, 1)`, only when the amount and an applicable benchmark are both known; no trace floor | agreed products below |
| An amount hidden inside a blend earns 0, with "amount not disclosed" as the reason; the total is never rescaled for it | 1179 Ravage, 54775 Sytrinol |
| A blend heading hides amounts only when a direct content has no amount (or it lists DSLD forms and no content rows); a heading whose contents are all dosed is represented by them | 220082 Wheybolic Complex 22.4 g over BCAA 15 g, glutamine 6 g, Velositol 1 g, ProHydrolase 400 mg |
| BCAA and EAA are assessed once, as a complete set or a declared total (`sports_helpers.group_bcaa` / `group_eaa`); a single amino acid never borrows the set benchmark | 311946 L-Leucine 5 g no longer reads as 5 g BCAA; Wheybolic's three BCAA rows no longer each take the set's credit |
| A genuinely unassessable case stays unassessable (no invented benchmark) | 22 products below |
| Benchmarks only from existing owners (sports band edges, joint targets, fiber 7 g, omega EPA+DHA, melatonin, RDA/AI with the existing reference kinds, therapeutic dosing ranges) | a dose mentioned in one study is not a benchmark |

## Rejected

**Demoting a main ingredient lighter than 25% of the heaviest main ingredient.** Weight is not
importance. On real labels it removes fully dosed main ingredients: 294477 "Calcium Carbonate &
Vitamin D3" loses its vitamin D3 (200% of RDA, 0.03 mg against 600 mg calcium); five magnesium
products lose the elemental magnesium row to the heavier compound row. All numbers in this document
are computed without it. The case it was meant for (66953, a 100 mg whey line as a primary
ingredient) is an identity defect in the existing owner, listed under "Definite defects".

## Definite defects (fix at their owners, independent of the policy choices)

| Defect | Evidence | Owner | State |
|---|---|---|---|
| ZyloFresh (preclinical, no human trials) carried the generic alias "alfalfa extract" | 253578, 253582: 63.0 → 55.7 after the fix; nothing else moves in 300 branded labels | `backed_clinical_studies.json` | **fixed, 2e88cb8a** |
| A trace protein line becomes the sports primary: `sports_helpers.primary_sports_identity` returns "protein" whenever any protein canonical is present, and `sports_dose._score_primary` gives "protein under 15 g" a flat 8/25 at any amount | 66953 Essential Amino Acids: its Dose today is 8/25 from a 100 mg whey line; the product is a 1.6 g EAA complex | `sports_helpers.primary_sports_identity`, `sports_dose._score_primary` (the codex/dose-calibration lane's owners) | open |
| DSLD serving columns nested differently survive the cleaner's column merge as duplicate rows | 318 of 15,414 raw labels print two or more serving columns; 108 repeat a top-level row; after `enhanced_normalizer._merge_alternate_serving_rows` 48 still carry duplicates (mostly GNC Wheybolic, Amplified, Re-Pump and Macros, plus some probiotic gummies). The merge requires identical trees; in 220082 the 2-scoop leucine/isoleucine/valine amounts sit under the 1-scoop heading and caffeine sits under Velositol in one column only | `enhanced_normalizer._merge_alternate_serving_rows` | open: needs a design for inconsistent source trees (which column is the declared serving, how split children rejoin), measured on the 48 and controls |
| 16 IQM forms added in c581a9ae have no `dosage_importance` (calcium acetate, sulfate, chloride, glycerophosphate; magnesium glycerophosphate; ...), so `test_enrichment_regressions::test_dosage_importance_populated` fails on main | calcium siblings mostly 1.5, magnesium mostly 1.0 with exceptions: a curated value, not a mechanical fill | `ingredient_quality_map.json` (the phase-2 curation lane) | open |

## Three policy choices (Sean)

### 1. Purpose-based weighting

Main ingredients should be the product's purpose by identity, not by weight. The existing classifier
(`scoring_input_contract.classify_ingredient_roles`) already reads the route driver, the title and
label function claims; its known errors are identity errors (the HMB salt, the trace protein
driver, "Glucosamine/MSM" marking only glucosamine).

Open question: does a measurable ingredient that is not part of the purpose add to Dose at all?
312819 HMB: HMB 825 mg of 3 g (0.28). The Calcium row is the calcium in the calcium HMB salt.

| Treatment of the calcium | Dose | Total |
|---|---:|---:|
| today | 3.5 | 65.2 |
| supporting at 30% (0.62 credit) | 7.6 | 69.3 |
| not part of the purpose, not counted | 5.5 | 67.2 |

The 70 / 30 main/supporting split remains a candidate. It is not validated.

### 2. How an incomplete assessment affects the total

Four options on the same 339 scored labels (5 probiotic labels unchanged, 21 not scored), excess E0:

| Option | What a missing benchmark does | Dose down / up / same | Mean total | Tier crossings |
|---|---|---|---:|---:|
| A | counts 0 everywhere | 274 / 44 / 21 | −3.68 | 85 |
| B | left out and the rest rescaled; nothing assessable → total over 80 | 225 / 74 / 23 (17 rescaled) | −0.22 | 52 |
| C | today's fixed 14.5 of 20 | 227 / 79 / 33 | −0.09 | 63 |
| R | a main ingredient counts 0, a supporting one is left out; Dose shown "not fully assessed" | 248 / 68 / 23 | −1.13 | 61 |

R is not neutral: it lowers the total and can lower the tier because we lack a benchmark. Guarana
69.4 → 59.9 and L-leucine 67.5 → 53.0 fall with no poor dosing demonstrated. "Not assessed" on the
pillar does not undo that in the total. B does the opposite: 184004 Artery Advantage 73.2 → 80.6
because its supporting rows stand in for the unbenchmarked garlic. The decision is whether a product
with an incomplete Dose assessment should carry an ordinary numeric total and tier at all. A
separate state for that would be a new public meaning (Sean's call); the Evidence pillar's
`not_yet_reviewed` counts 0 in the total today.

The 22 products whose main ingredients have no benchmark, split by why. This is a first pass by
ingredient name, **not source-verified**; each needs its own `/data-fix` receipt before any
benchmark is added.

| Why | Products |
|---|---|
| A benchmark exists in an owner but was not reached | 233404/233406 Keto Brain (FiberSmart resistant starch is fiber; the fiber benchmark only runs on the fiber route) |
| Probably curatable (published studied doses; verify per product, per preparation) | 214586 ipriflavone; 311749 pygeum; 252781, 311946 L-leucine and 37261/42176 Re-Size leucine; 77257 spirulina; 253774 guarana (through its caffeine content); 184004 garlic extract (preparation-specific); 82372 Beanaid (alpha-galactosidase activity units); 286151, 302683 keratin (brand-specific preparations only); 253273 garcinia (HCA content) |
| Probably no suitable reference (a food, or an effect bounded by safety) | 311833 raspberry powder, 329991 lemon powder, 330223 papaya seed powder, 259304 barley grass, 312431 dong quai, 311716 turkey rhubarb and 241318 Laxaherb (stimulant laxatives) |

### 3. Where excess-dose risk is reflected

What the Safety owner does today, probed on the examples (all adult ULs, `rda_ul_data`):

| Product | % of UL | Verdict | Flag | Safety pillar | Dose today |
|---|---:|---|---|---:|---:|
| 247332 Vitamin D3 10,000 IU | 250 | CAUTION | `DOSE_OVER_UL_CRITICAL` | 8 (−2) | 0 (band 0, B7 −2) |
| 236915 Niacin 250 mg | 714 | CAUTION | `DOSE_OVER_UL_CRITICAL` | 7 (−2 over UL, −1 additive) | 0 |
| 252640 Ascorbic Acid 750 mg, up to 4 a day | 150 | CAUTION | `DOSE_OVER_UL_CAUTION` | 8 (−2) | 0 |
| 180225 Iron 65 mg | 144 | CAUTION | `DOSE_OVER_UL_CAUTION` | 8 (additive −2; over UL 0) | 5.7 |
| 184058 Vitamin D3 5,000 IU | 125 | CAUTION | `DOSE_OVER_UL_CAUTION` | 10 | 10 |

So the verdict already carries the risk: every over-UL product is CAUTION whatever its total. The
number does not scale: `quality_score._pillar_safety_hygiene` deducts a flat 2 per flag from 150% of
UL (`quality_score.json` `dose_safety_policy`: threshold 150%, 2 per flag, cap 3; the Safety pillar caps it at
`safety_hygiene_subscale.over_ul_max_penalty` 3), the same at 150% and 714%, and
nothing below 150%. Today most of the numeric cost sits in Dose (band 0 and B7 −2). Capping benefit
at the benchmark and removing the Dose-side cost (E0) lifts 247332 to 90.1 with a CAUTION verdict.

The half and quarter credits (E1, E2) have no clinical basis and are not recommended. If the total
should fall with excess, the owner is the Safety deduction: graduate it by % of UL and population,
then measure. The Dose-side comparison is kept in the report for reference (mean total E0 −1.13,
E1 −1.35, E2 −1.39).

## Branded-trial credit

`botanical_profile._branded_studied_set` gives any row naming a branded clinical entry full
standardization (4), +3 "branded clinically studied" and, in Dose, standardized-extract status for
the studied-range check. Removing it on 300 branded labels moved 23 (mean −5.2, 14 tier crossings,
no verdict change). Label-stated standardization survives the removal; studied-dose matching does
not, because only 4 of 57 `BRAND_*` entries carry a studied dose (Theracurmin's full Dose today comes
from the generic curcumin range reached through the shortcut). Each brand the movers name needs its
own verification of formulation, preparation, dose basis and outcome; some will not support one
dose benchmark. No bulk fill. 29 `BRAND_*` entries carry generic aliases (astaxanthin, L-theanine,
MSM, HMB, methylfolate, piperine, ...): the same false credit, recorded in `research.md`.

D23 (a branded blend at its printed total) only when brand, composition, preparation, dose basis
and the applicable evidence match, through the existing evidence owner.

## Measured reference (no mass rule, missing R, excess E0 unless stated)

| Product | Dose today | Proposed | Total today → proposed | Why |
|---|---:|---:|---|---|
| 182940 Glucosamine/MSM | 6.1 | 6.7 | 66.6 → 67.2 | glucosamine 500 of 1,500 mg (main); MSM supporting; ginger, turmeric no benchmark |
| 312819 HMB | 3.5 | 7.6 | 65.2 → 69.3 | see choice 1 |
| 252551 Inulin | 7.2 | 5.7 | 73.1 → 71.6 | 2 g of 7 g fiber |
| 66953 Essential Amino Acids | 6.4 | 2.1 | 41.9 → 37.5 | EAA 1.6 of 8 g; the 100 mg whey line stays main until the identity defect is fixed |
| 1179 Ravage Fruit Punch | 0 | 5.2 | 25.3 → 30.5 | main blends hide amounts; calcium, niacin supporting |
| 239467 Fish Oil 1000 mg | 0 | 0 | unchanged | EPA/DHA not stated |
| 236915 Niacin 250 mg | 0 | 20 | 48.1 → 68.1 | CAUTION; see choice 3 |
| 247332 Vitamin D3 10,000 IU | 0 | 20 | 70.1 → 90.1 | CAUTION; see choice 3 |
| 315089 Healthy Hormone Formula | 9.5 | 2.9 | 42.9 → 36.3 | tongkat ali 0.5; tribulus no benchmark; Tesnor hidden |
| 54775 Sytrinol | 9.5 | 0 | 49.5 → 40.0 | blend total, contents hidden (D23 would read 150 of 300 mg) |
| 315333 One Daily Multi + Probiotics | 19.2 | 12.6 | 80.5 → 73.9 | panel proportional to 100% of RDA |
| 214586 Ipriflavone | 14.5 | 0 | 56.8 → 42.3 | no benchmark (choice 2) |
| 311946 L-Leucine 5 g | 14.5 | 0 | 67.5 → 53.0 | no benchmark (choice 2) |
| 220082 Wheybolic Ripped | 11.2 | 16.8 | 60.0 → 65.6 | BCAA 15 g as one item; duplicate columns still present |
| 294477 Calcium Carbonate & D3 | 20.0 | 20.0 | 84.9 → 84.9 | both main ingredients fully dosed |

Multivitamin panels: calcium, magnesium and every nutrient without a DRI or clinical-anchor mapping
use the `legacy` 25% reference (`generic_dose._adequacy_reference_kind`), with no recorded rationale
specific to them; moving them to 100% moves 188 of 199 multivitamin/B-complex labels (mean −1.15
Dose). B-100 products with no UL for the nutrient (thiamine 8,333% of RDA) get full capped credit.

## Overlap inventory (one fact, several pillars)

| Fact | Where it costs or pays today |
|---|---|
| Additives and sugar | Formulation (harmful additives up to −15 raw, sugar up to −4) and Safety (additive/sweetener up to −4, restricted additive up to −5) |
| Excess over UL | Dose (band and B7) and Safety (flat, from 150% of UL); verdict CAUTION |
| Hidden blend amounts | Transparency (blend opacity up to −10 raw) and Dose |
| Disclosure | Transparency, and inside Dose (fiber +1, probiotic per-strain CFU up to 10) and Formulation (multi disclosure structure 2) |
| Branded trial | Formulation (+4, +3), Dose (standardized for the range check), Evidence |

## Decisions for Sean (the only current list)

1. **Weighting:** main ingredients by purpose and identity through the existing classifier, with its
   identity defects fixed; whether non-purpose ingredients add to Dose (HMB's calcium); 70 / 30 as a
   candidate.
2. **Incomplete assessment:** whether a product whose Dose cannot be fully assessed carries an
   ordinary numeric total and tier; and if so, A, B, C or R.
3. **Excess:** keep the risk in the verdict and move any numeric consequence to a graduated Safety
   deduction (then measure), rather than half or quarter Dose credit.

Everything in "Accepted" and "Definite defects" proceeds without these. One corrected comparison
under the chosen answers comes next, then implementation through the existing owners.
