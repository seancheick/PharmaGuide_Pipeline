# Dose model proposal, measured (2026-09-28)

Nothing here changes scoring. Numbers come from a read-only calculation over real labels
(`~/pg_quality/rr_fix/dose_proposal.py` at branch tip a91f6104; outputs `pall_final.json`,
`pagreed*.jsonl`). It implements Sean's direction as refined in his answer of 2026-09-28: proportional
credit only where the amount and an applicable benchmark are both known; unknown stays unknown; no
trace floor; excess handled as harm, not as bonus; weighting by the existing roles.

## Corrected replay (2026-09-29): supersedes the numbers in the sections after it

A review of the first replay found grouping and benchmark defects; each was reproduced before it was
fixed. Calculation: `dose_proposal_v2.py` (rows) and `v2_report.py` (options), both in this
directory, over the same 365 labels plus the 5 agreed-product labels; full output in
`dose_proposal_v2_report.txt`. Scoring code is unchanged.

| Review finding | Reproduced on | Correction in the replay |
|---|---|---|
| Calcium counted as a main ingredient of an HMB product | 312819: the Calcium row's DSLD form is `Calcium Beta-Hydroxy-Beta-Methylbutyrate Monohydrate`, the same compound as the HMB row; the title "Calcium HMB" made it claim-prominent | a row whose forms are the same compound as a primary row is that compound's salt and goes to the supporting group |
| A 100 mg whey line weighted equally with a 1.6 g EAA complex | 66953: whey is a sports driver canonical, so the classifier marks it primary at any amount. Today's sports scorer also picks it: "protein under 15 g" gives a flat 8/25 for 100 mg | a main-group row lighter than 25% of the heaviest main row (the classifier's own `_ROLE_MASS_MAJOR_FRACTION`) is supporting |
| Leucine judged against the combined BCAA benchmark | 311946 L-Leucine 5 g read as 5 g BCAA (full credit); Wheybolic's three BCAA rows each took the whole set's credit | BCAA and EAA are one item each, only for a complete set or a declared total (`sports_helpers.group_bcaa` / `group_eaa`); a lone amino acid has no set benchmark |
| Turmeric missed its reference | the botanical owner's own lookup (`_dosing_entry_for`) misses too: the only turmeric-family entry is "Curcumin (from Turmeric)" 500-1000 mg, keyed on "turmeric extract", not on the row's canonical "turmeric". The earlier note that switching to that lookup fixes it was wrong | stays not assessable; whether a turmeric extract of unstated curcuminoid content matches a curcumin range is a data question for `/data-fix` |
| Supporting rows decide Dose when the main group has no benchmark | 184004, 233404/233406, 37261, 42176 (B: 184004 9.5 → 16.9) | option R below |
| 227 + 74 + 28 = 329, not 344 | yes | counts below report the unassessable labels separately |
| (found in this replay) A blend heading whose contents all print amounts counted as hidden | 220082 Wheybolic Complex 22.4 g lists BCAA 15 g, glutamine 6 g, Velositol 1 g, ProHydrolase 400 mg | a heading hides amounts only when a direct content has none (or it lists DSLD forms without content rows); otherwise its contents are assessed and the heading is not |

Not fixed here, recorded: DSLD two-column labels (2 scoops / 1 scoop, e.g. 220082) arrive as
duplicate rows (two caffeine, two carnitine rows), in today's scorer as well; "Glucosamine/MSM" marks
only glucosamine as title-named (MSM is `major`); the `legacy` reference kind is the default for every
nutrient without a DRI or clinical-anchor mapping, so DIM, indole-3-carbinol and CoQ10 read "% of RDA"
against `rda_optimal_uls` values.

### Missing benchmark: four options, same rows

- **A**: a row or group with no benchmark counts 0.
- **B**: it is left out and the rest rescaled; a product with nothing assessable is scored over 80.
- **C**: it keeps today's fixed no-reference credit (14.5 of 20).
- **R**: the Evidence pillar's existing coverage-gap rule (`quality_score.evidence_display_state`:
  a gap earns 0 points and is shown as "not yet reviewed", never as a 0/20 verdict). An unbenchmarked
  main ingredient earns 0 and Dose is shown as not fully assessed; an unbenchmarked supporting
  ingredient is left out (it neither helps nor hurts). Nothing is rescaled.

339 scored labels outside the probiotic route (5 probiotic labels unchanged, 21 not scored),
excess option E0:

| Option | Dose down / up / same | Nothing assessable | Mean total change | Tier crossings |
|---|---|---:|---:|---:|
| A | 270 / 48 / 21 | 0 (Dose 0) | −3.57 | 83 |
| B | 222 / 77 / 23 | 17 (rescaled) | −0.15 | 52 |
| C | 225 / 81 / 33 | 0 (14.5) | −0.02 | 64 |
| **R** | **244 / 72 / 23** | 0 (Dose 0, "not assessed") | **−1.02** | **61** |

Where the options differ:

- 160 products (155 multivitamins, 1 B-complex, 2 fiber, 2 generic) whose only unbenchmarked rows are add-ons (lutein, boron, silica): A costs about
  5 Dose points each (Centrum Adults 17139: 17.8 → 11.9); B and R leave the panel as the Dose (17.0).
- 5 products whose main ingredients have no benchmark: B lets the supporting rows stand in (184004
  Artery Advantage 9.5 → 16.9, total 73.2 → 80.6; Keto Brain 233404 14.5 → 20.0); R keeps them to their
  30% share (5.1 and 6.0).
- 17 products with nothing assessable (Ipriflavone, garcinia, guarana, barley grass, keratin, pygeum,
  dong quai, spirulina, lone L-leucine, Beanaid, ...): R and A read Dose 0 (totals −5 to −15; guarana
  69.4 → 59.9); B rescales (74.9); C keeps 14.5. R's "not assessed" state is the Evidence precedent
  applied to Dose; it becomes a public display state, which is Sean's decision.

Recommendation: **R**. It is the one existing rule for a coverage gap, it never rewards a missing
assessment (the review's objection to B), it invents no points (C), and it does not charge a
multivitamin for add-ons we have no reference for (A). Its cost falls on the 17 unbenchmarked
products until each gets a verified benchmark.

### Excess over the upper limit: three options (missing R)

- **E0**: benefit capped at the benchmark; no Dose reduction; Safety alone handles excess.
- **E1**: over UL at most 0.75, at or over 150% of UL at most 0.5 (the first replay).
- **E2**: over UL at most 0.75, at or over 150% at most 0.25.

All three keep today's Safety deduction; the proposal replaces today's Dose-side excess cost (the
11/22 and 0 bands and the B7 Dose penalty). Totals: E0 −1.02, E1 −1.24, E2 −1.28 mean; tier
crossings 61 / 55 / 54.

| Product | UL | Safety today | Dose today | E0 | E1 | E2 | Total today → E0 / E1 / E2 |
|---|---:|---:|---:|---:|---:|---:|---|
| 247332 Vitamin D3 10,000 IU | 250% | 8 | 0 | 20 | 10 | 5 | 70.1 → 90.1 / 80.1 / 75.1 |
| 236915 Niacin 250 mg | 714% | 7 | 0 | 20 | 10 | 5 | 48.1 → 68.1 / 58.1 / 53.1 |
| 252640 Ascorbic Acid 750 mg (up to 4 a day) | 150% | 8 | 0 | 20 | 10 | 5 | |
| 180225 Iron 65 mg | 144% | 8 | 5.7 | 14.4 | 10.9 | 10.9 | |
| 184058 Vitamin D3 5,000 IU | 125% | 10 | 10 | 20 | 15 | 15 | |
| Magnesium chelates 114-116% (5 labels) | | 10 | 10 | 20 | 15 | 15 | |

Today's Safety pillar deducts 2 for vitamin D at 250% of its UL, so under E0 a 10,000 IU product
reads 90.1, the top tier. "Excess is handled by Safety" holds only if the Safety deduction scales
with the excess, which today it does not. Either keep a Dose reduction (E1 or E2) or change the
Safety UL deduction (a separate owner and decision). No recommendation between E1 and E2 without
a clinical basis for the numbers; the table is the comparison.

### Multivitamin panels: the 25% reference (missing R, E0)

Calcium, magnesium and every other nutrient without a DRI or clinical-anchor mapping use the
`legacy` 25% reference (`generic_dose._adequacy_reference_kind`); no calcium- or magnesium-specific
rationale is recorded in code or config. Moving them to 100% on multi routes moves 188 of 199
multivitamin/B-complex labels by −1.15 Dose on average (worst −1.8); 78 tier crossings instead of 61.

### Agreed products, corrected (missing R, excess E0)

| Product | Dose today | Corrected | Total today → corrected | Why |
|---|---:|---:|---|---|
| 182940 Glucosamine/MSM | 6.1 | 6.7 | 66.6 → 67.2 | glucosamine 500 of 1,500 mg (main); MSM 0.33 supporting; ginger, turmeric not assessable |
| 312819 HMB | 3.5 | 7.6 | 65.2 → 69.3 | HMB 825 mg of 3 g (main, 0.28); calcium from the HMB salt now supporting |
| 252551 Inulin | 7.2 | 5.7 | 73.1 → 71.6 | 2 g of 7 g fiber |
| 66953 Essential Amino Acids | 6.4 | 2.8 | 41.9 → 38.3 | EAA 1.6 of 8 g (main, 0.2); the 100 mg whey line supporting |
| 1179 Ravage Fruit Punch | 0 | 5.2 | 25.3 → 30.5 | main blends hide amounts (0); calcium, niacin supporting |
| 239467 Fish Oil 1000 mg | 0 | 0 | unchanged | EPA/DHA not stated |
| 236915 Niacin 250 mg | 0 | 20 / 10 / 5 | 48.1 → 68.1 / 58.1 / 53.1 | E0 / E1 / E2 |
| 247332 Vitamin D3 10,000 IU | 0 | 20 / 10 / 5 | 70.1 → 90.1 / 80.1 / 75.1 | E0 / E1 / E2 |
| 315089 Healthy Hormone Formula | 9.5 | 2.9 | 42.9 → 36.3 | tongkat ali 0.5, tribulus unbenchmarked (0), Tesnor hidden (0) |
| 54775 Sytrinol | 9.5 | 0 (10.0 with D23) | 49.5 → 40.0 (50.0) | blend total, contents hidden |
| 315333 One Daily Multi + Probiotics | 19.2 | 12.6 | 80.5 → 73.9 | panel proportional to 100% of RDA |
| 214586 Ipriflavone | 14.5 | 0, not assessed | 56.8 → 42.3 | no benchmark |
| 311946 L-Leucine 5 g | 14.5 | 0, not assessed | 67.5 → 53.0 | no leucine-alone benchmark |
| 220082 Wheybolic Ripped | 11.2 | 16.8 | 60.0 → 65.6 | BCAA 15 g as one item (main); supporting rows 0.3 |

### Branded-trial credit, corrected

The measured removal already keeps label-stated standardization: without the brand shortcut,
`_standardization_tier_credit` still reads the label's marker percentage. What it loses is studied-
dose matching, because the branded entries do not carry a studied dose: only 4 of 57 `BRAND_*`
entries in `backed_clinical_studies.json` have `min_clinical_dose`. Theracurmin's full Dose today
(259371, 600 mg "within studied range" 500-1000 mg) comes from the generic curcumin range reached
through the shortcut, not from Theracurmin's own trials; without the shortcut it falls to the
blend-total band (10). A valid match needs the brand's studied dose on its entry, checked per
entry against its trials, and then the same seam as D23 (exact brand, composition, preparation and
unit). So the order is: studied doses for the brands the 23 movers name (Theracurmin, Pycnogenol,
curcumin phytosome, BioPerine, Testofen, Sytrinol and the others in the branded measurement) as a
`/data-fix` batch, then removal of the shortcut, then the ZyloFresh alias fix.

### Decisions, corrected

1. Grouping: the three corrections above (salt of the primary, trace main rows, sets as one item),
   then the 70 / 30 split.
2. Hidden amounts: 0 with an explicit "amount not disclosed" explanation.
3. Missing benchmark: R (recommended), A, B or C.
4. Excess: E0, E1 or E2, or a Safety-owner change instead; the vitamin D row is the case to decide on.
5. Multivitamin panels proportional to 100% of RDA, keeping the 25% legacy reference (or moving it).
6. Branded shortcut: studied-dose data first, then removal, then the ZyloFresh alias.
7. D23: exact brand, composition, preparation, dose and unit match against the entry's studied dose.

## The rule (first replay, 2026-09-28)

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

\* Superseded: the botanical owner's lookup misses this row too (see the corrected replay above).

## Across 365 labels (the audit sample and the targeted set)

344 scored, of which 5 probiotic (unchanged) and 15 unassessable: Dose goes down on 227, up on 74,
unchanged on 28 of the other 329 (mean −0.48); 42 cross a tier. Superseded by the corrected replay. By
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
