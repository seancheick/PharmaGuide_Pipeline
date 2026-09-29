# Dose model proposal, measured (2026-09-28)

Nothing here changes scoring. Numbers come from a read-only calculation over real labels
(`~/pg_quality/rr_fix/dose_proposal.py` at branch tip a91f6104; outputs `pall_final.json`,
`pagreed*.jsonl`). It implements Sean's direction as refined in his answer of 2026-09-28: proportional
credit only where the amount and an applicable benchmark are both known; unknown stays unknown; no
trace floor; excess handled as harm, not as bonus; weighting by the existing roles.

## The rule

**Per ingredient.** `credit = min(amount / benchmark, 1)`, read at the benchmark's own basis: the
minimum directed daily use for daily benchmarks, one serving for per-use benchmarks (caffeine,
betaine, taurine, alpha-GPC, protein, BCAA/EAA totals, citrulline). Each row gets one state:

| State | Meaning | Credit |
|---|---|---|
| assessed | own amount and an applicable benchmark | 0-1, proportional |
| unknown | the amount of what is assessed is not on the label: an ingredient inside a blend, a blend total over listed contents, fish oil with no EPA/DHA | 0, and the explanation says why |
| not_assessable | declared amount, no applicable benchmark in our data | left out of the average |

**Benchmarks come only from existing owners**, in this order: sports band full-credit edges
(`sports_dose._score_primary`), joint targets (config), fiber 7 g/day (fiber band), omega EPA+DHA
per day (omega owner), melatonin 0.3 mg (sleep band), RDA/AI via `rda_ul_data` with the existing
reference kinds (DRI and clinical-anchor nutrients at 100% of RDA/AI, the remaining legacy
nutrients at 25%), the therapeutic dosing range's low end, then nothing (not_assessable). A dose
mentioned in a study is never a benchmark by itself. Probiotic CFU Dose is out of scope and
unchanged.

**Excess.** Benefit is capped at the benchmark (more earns nothing extra). Above the safety limit
the credit is reduced, because that excess is harmful: over 100% of UL at most 0.75, at or over
150% of UL at most 0.5 (measured below; 0.25 is the stricter option). The Safety pillar keeps its
own UL deduction.

**Weighting (existing roles, `scoring_input_contract.classify_ingredient_roles`).**
Main group = primary and claim-prominent rows; if none, major rows; if none, all rows. On the
multivitamin/prenatal and B-complex routes the main group is the nutrient panel (the route's
purpose), so a title-named add-on ("plus Probiotics") is supporting. Rest = every other row.

`Dose = 20 x (0.7 x main-group mean + 0.3 x rest mean)`, or `20 x` the one group when only one
counts. Within a group, unknown rows count 0 and not_assessable rows are left out.

**No countable row at all.** If every row is not_assessable (our data has no benchmark), Dose reads
"cannot be assessed" and the total is rescaled over the other 80 points (option B below). If every
countable row is unknown (the label hides the amounts), Dose is 0 with that explanation; the total
is not rescaled, so hiding amounts can never raise a score.

## Why these weights

Main ingredient at 2/20 (credit 0.1), four minor ingredients fully dosed:

| Aggregation | Dose |
|---|---:|
| Plain average | 16.4 |
| Role weights 3 (main) : 1 (minor) | 12.3 |
| **Group split 70 / 30 (proposed)** | **7.4** |

Minor ingredients can add at most 6 points (30% of 20) to an underdosed main ingredient.

Codex's unknown case, one ingredient at 20/20 and four main ingredients with hidden amounts:
dropping the unknowns would show 20/20. Proposed: if all five are main, 20 x (1+0+0+0+0)/5 = 4.0;
if the assessed one is minor and the four hidden ones are main, 20 x (0.7 x 0 + 0.3 x 1) = 6.0.

## Agreed products

Today's Dose and total are the branch's current scores; "new total" changes only Dose.

| Product | Route | Dose today | Proposed | Total today -> new | Why |
|---|---|---:|---:|---|---|
| 182940 Glucosamine/MSM | generic | 6.1 | 6.7 | 66.6 -> 67.2 | glucosamine and MSM 500 mg/day of 1,500 (0.33 each); ginger and turmeric extracts not_assessable* |
| 312819 HMB (Calcium HMB) | sports | 3.5 | 8.9 | 65.2 -> 70.7 | HMB 825 mg/day of 3 g (0.28); calcium 16% of RDA vs the 25% legacy reference (0.62), both main |
| 252551 Inulin | fiber | 7.2 | 5.7 | 73.1 -> 71.6 | 2 g declared dietary fiber/day of 7 g (0.29); today's +1 disclosure and +1 type points are gone |
| 66953 Essential Amino Acids | sports | 6.4 | 2.1 | 41.9 -> 37.5 | 1.6 g EAA total of 8 g (0.2); the 100 mg whey line of 20 g protein (0.005); both main |
| 1179 Ravage Fruit Punch | sports | 0.0 | 5.2 | 25.3 -> 30.5 | two main blends hide their amounts (0); calcium 0.74 and niacin 1.0 as supporting (x 0.3); potassium not_assessable |
| 239467 Fish Oil 1000 mg | omega | 0.0 | 0.0 | 27.7 -> 27.7 | EPA+DHA not declared: unknown, "the label does not state EPA/DHA" |
| 236915 Time Released Niacin 250 mg | generic | 0.0 | 10.0 | 48.1 -> 58.1 | 1,562% of RDA, 714% of UL: capped at 0.5 (0.25 option: 5.0) |
| 247332 Vitamin D3 10,000 IU | generic | 0.0 | 10.0 | 70.1 -> 80.1 | 1,667% of RDA, 250% of UL: capped at 0.5 (0.25 option: 5.0) |
| 315089 Healthy Hormone Formula | generic | 9.5 | 4.1 (11.1 with D23) | 42.9 -> 37.5 (44.5) | Tesnor blend unknown (with D23: 400 of 200 mg, 1.0); tongkat ali 100 of 200 mg (0.5); tribulus not_assessable |
| 54775 Sytrinol | generic | 9.5 | 0.0 (10.0 with D23) | 49.5 -> 40.0 (50.0) | Sytrinol blend unknown (with D23: 150 of 300 mg, 0.5) |
| 315333 One Daily Multivitamin plus Probiotics | multi | 19.2 | 12.6 | 80.5 -> 73.9 | panel mean 0.9 (e.g. vitamin K 62%, folate 85% now proportional to 100% RDA, where today everything from 50% to 200% scores full); the probiotic blend is a supporting unknown |
| 214586 Ipriflavone 200 mg | generic | 14.5 | cannot be assessed | 56.8 -> 52.9 (B) / 42.3 (A) | no benchmark in our data; today it gets the fixed 14.5 no-reference credit |

\* Name lookup gap in the calculation, not the rule: "Turmeric (Curcuma longa) extract" did not
match the therapeutic entry "turmeric extract". The implementation must use the botanical
profile's own alias lookup (`botanical_profile._dosing_entry_for`).

## Across 365 labels (the audit sample and the targeted set)

344 scored. Dose goes down on 227, up on 74, unchanged on 28 (mean −0.48); 42 cross a tier. By
route (count, mean, min, max change in Dose points):

| Route | n | Mean | Min | Max |
|---|---:|---:|---:|---:|
| multivitamin / prenatal | 194 | −0.88 | −6.7 | +5.5 |
| generic | 69 | +1.63 | −14.5 | +10.5 |
| sports | 40 | −1.54 | −8.8 | +5.4 |
| fiber | 9 | −4.94 | −12.8 | −0.6 |
| omega | 7 | −2.13 | −5.1 | 0.0 |
| B-complex | 5 | +4.20 | +0.1 | +6.6 |
| probiotic | 5 | 0 | 0 | 0 (unchanged) |

- Dose 0: 6 products today, 5 proposed, and every proposed 0 is "unknown": two fish oils without
  EPA/DHA, Fitbiotic and an enzyme blend with hidden amounts, and Sytrinol without D23.
- Cannot be assessed: 15 products, all single botanicals or foods with no benchmark in our data
  (Ipriflavone, garcinia, guarana, barley grass, keratin, rhubarb, pygeum, dong quai, spirulina,
  ...). Option A (Dose counts 0) would lower their totals by 11.7 on average; option B (rescale
  over 80) moves them −5.5 to +5.5 (mean −0.7).
- Largest rises: B-complex megadose panels (Balanced B-100 19173: 12.2 -> 18.8, with thiamine at
  8,333% of RDA and no UL, so capped benefit is full credit), over-UL single nutrients (0 -> 10), and
  single ingredients dosed at or above their reference (St John's wort, collagen, melatonin
  9.5-10 -> 20).
- Largest falls: fiber (the disclosure and type bonuses leave Dose), multis whose panel sits at
  50-99% of RDA, and products whose main ingredients are hidden in blends.

## Branded-trial form credit (measured)

`botanical_profile._branded_studied_set` grants three things to any row naming a branded clinical
entry: full standardization (4 of 15 botanical Formulation points), +3 "branded clinically studied",
and in Dose it counts the row as a standardized extract for the studied-range check. Removing all
three on 300 raw labels that name a branded ingredient: 23 of 284 scored move, all herbal, mean
−5.2, 14 tier crossings, no verdict change. Largest: Theracurmin (Curica 259371) 87.0 -> 68.5
(Formulation 20 -> 12, Dose 20 -> 9.5); Pycnogenol 67210 −9.3; Sytrinol 251856 −6.7; curcumin
phytosome −6.0.

Data defect found: `BRAND_ZYLOFRESH` (evidence level preclinical, no human trials) carries the
generic alias "alfalfa extract", so every alfalfa extract collects the branded credit (253578,
253582: Formulation 20 -> 13.3). The alias belongs to no brand.

## Overlap inventory (one fact, several pillars)

| Fact | Where it costs or pays today |
|---|---|
| Additives and sugar | Formulation (harmful additives up to −15 raw, sugar up to −4) and Safety (additive/sweetener up to −4, restricted additive up to −5) |
| Excess over UL | Dose (that nutrient's credit, plus up to −3 raw) and Safety (up to −3) |
| Hidden blend amounts | Transparency (blend opacity up to −10 raw) and Dose (sports −10 today; unknown = 0 in the proposal) |
| Disclosure | Transparency, and inside Dose (fiber +1, probiotic per-strain CFU up to 10) and Formulation (multi disclosure structure 2) |
| Branded trial | Formulation (+4, +3), Dose (standardized for range), Evidence |

Some overlap is intended (Dose asks "is the amount right", Transparency asks "is it disclosed").
Each row above needs a stated reason or removal; that is a separate decision from this proposal.

## Corrections to the 2026-09-28 overview

- Generic Dose: DRI vitamins and trace minerals reach full credit at 100% of RDA/AI (half at 20%),
  clinical-anchor ingredients at 100%; only the remaining legacy nutrients (calcium, magnesium, ...)
  at 25%.
- Formulation ceiling: the form engine's profile (generic IQM, botanical, collagen) sets 15 when
  present, which is 139 of 188 sports and 4 of 47 fiber products in these sets; the 24-30 archetype
  ceilings apply to the rest.
- Ravage Safety: 2219 is 0 (yohimbe); 1179, 12800 and 19471 are 6.
- Minimum daily use applies to daily benchmarks; per-use benchmarks (caffeine and the others above)
  read one serving.
- Methylcobalamin was a wrong example of a better form: the six disclosed B12 forms tie at 15.
- "Not efficacy relevant" means no efficacy assessment applies to that food matrix, not that the
  food has no health effect.

## Decisions for Sean

1. Group split 70 / 30 by existing roles (panel as main group on multi routes).
2. Unknown amounts count 0 inside their group; an all-unknown product reads Dose 0 "not disclosed"
   and the total is not rescaled.
3. No benchmark at all: option B, rescale over the other 80 (recommended), or A, count 0, or keep
   today's fixed 14.5.
4. Excess over UL: 0.75 / 0.5 (measured) or 0.75 / 0.25 (stricter). And far above the RDA with no
   UL (B-100 thiamine 8,333%): full credit as measured, or a reduction without a harm basis (which
   your "only if too high is negative" rule argues against).
5. Multi panels proportional to 100% of RDA (today 50-200% all score full), with the existing
   legacy 25% reference kept for calcium/magnesium.
6. Remove the three branded-trial credits; fix the ZyloFresh alias.
7. D23: a studied branded blend is assessed at its printed total when brand token, composition and
   dose unit match.

Then: implement in the route owners behind one shared per-row credit function, replay these
labels, one corpus pass, release rung.
