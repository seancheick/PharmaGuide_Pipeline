# Cause census — 478 products withheld between main `5fb2be1ca` and main `951a05415` (October 19, 2026)

Read-only. No production file, data file, LEDGER or master-plan entry was changed. Every number
below is reproduced by `census.py` in this directory (output: `census.json`); the commands for the
source reads are in §6.

Inputs (same 15,414 frozen raw DSLD labels, full-artifact replay through Clean → Enrich → Score → blob):

| Baseline | Source | Path |
|---|---|---|
| old | main `5fb2be1ca` (before the October 17–19 batch: PRs 155–167) | `/Users/seancheick/pg_quality/full_artifact_baseline_20261018/baseline_5fb2be1ca.jsonl` |
| new | main `951a05415` (current; accepted development baseline, unpinned) | `/Users/seancheick/pg_quality/corpus_20261019_post167/baseline_951a05415_unpinned.jsonl` |

## 1. Result in one paragraph

All 478 status moves are `scored → not_scored`; there is no reverse move and no safety-status
change. **475 of 478 are one cause: the Dose V4.1 label-population UL screen (PR 166) now screens
every product whose DSLD target group names children against the pediatric upper limits, and the
reference file `scripts/data/rda_optimal_uls.json` has no UL row younger than 14–18 for any of its
77 nutrients, so each material nutrient row is stamped `pediatric_reference_gap`, the Dose
assessment is incomplete, and the product is withheld.** This is the approved, tested V4.1
behaviour ("missing established younger references keep the existing incomplete assessment/strict
hold"), not a defect in the architecture batch, the omega batch or the CFU fix. What was never
measured is its corpus-wide size: the V4.1 packet measured it on a 63-label raw cohort (4
products) and on a 15,426-product replay of *stored* enrichment, which cannot see a stamp that the
enricher writes. The remaining three are two CFU source-identity holds and one EAA identity hold,
all previously documented.

## 2. Status movement

| | scored | not_scored | suppressed_safety |
|---|---:|---:|---:|
| old `5fb2be1ca` | 15,109 | 236 | 69 |
| new `951a05415` | 14,631 | 714 | 69 |
| transitions | `scored→not_scored` 478 | no other transition | |

## 3. Buckets (every product in exactly one)

| Bucket | Count | Driver (field the production code wrote) | Intended policy? |
|---|---:|---|---|
| A. `pediatric_reference_gap` | **475** | `rda_ul_data.dose_assessments[*].reason_code = pediatric_reference_gap`, `ul_assessment_status = assessment_error`, `readiness = incomplete`; `assessment_readiness.dose.readiness = incomplete`, `unavailable_reasons = [dose_assessment_readiness]`, `completeness_gate.reason = incomplete_product_data` | **Yes** — Dose V4.1, decision row `shared.ul_population` (`DOSE_V41_REFERENCE_DECISIONS.md:66`), packet `DOSE_V41_REVIEW_PACKET.md:273, 326–327, 359–366`; pinned by `scripts/tests/test_ul_screening_population.py::test_pediatric_reference_gap_is_incomplete_through_enrich_and_score` (target "Children 4 or More Years of Age" → incomplete). **Blast radius unmeasured** before this census. |
| B. `unresolved_source_quantity` (CFU source identity mismatch) | 2 — `251169` Baby & Me 2 Prenatal Probiotic, `31062` Super Foods 25 | `assessment_readiness.dose.measurements[0].reason_code = cfu_source_identity_mismatch` | Yes — PR 166 commit `0266ccc06` ("hold invalid CFU sources") and PR 167 (`assessment_readiness::_dose_readiness` route-independent); `31062` is the one product the post-run audit already named; `251169` is the "existing hold" in the PR 167 handoff. |
| C. `identity_assessment_readiness` | 1 — `330806` EAA | `unavailable_reasons = [identity_assessment_readiness]` (Dose readiness complete) | Yes — packet `DOSE_V41_REVIEW_PACKET.md:84`: "EAA330806 is an honest persistent identity hold: its 10 g EAA header does not own the separate nine-amino-acid list." |

## 4. Bucket A in detail

### 4.1 Production path (read, not inferred)

1. `scripts/rda_ul_calculator.py::label_population_members` (138–160) maps DSLD `targetGroups` to
   screening populations by substring; any tag containing `child`, `infant`, `boys` or `girls`
   adds `pediatric` (`_UL_POPULATION_TAGS`, 129–135).
2. `scripts/enrich_supplements_v3.py::_ul_screening_pediatric_age_groups` (21715–21743) lifts the
   gap only when every pediatric tag states an adolescent-only range (`14-18`), and declares an
   explicitly younger-only label (e.g. "Children more than 1 but less than 4") as having no row at
   all. The broad DSLD tag "Children 4 or More Years of Age" returns `None` → broad.
3. `scripts/rda_ul_calculator.py::_screening_ul` (743–791): `UL_SCREENING_POPULATIONS["pediatric"]`
   (107–118) has `ages = ("14-18",)` and a fixed `reference_gap =
   "pediatric_ul_rows_below_14_not_in_reference_data"`; for an established UL the scope carries that
   gap whenever `pediatric` is a member and no explicit age lifted it.
4. `scripts/enrich_supplements_v3.py` 22695–22704: `pediatric_reference_gap` → `skip_ul_reason`;
   `scripts/dose_assessment.py` 505–507: that reason → `assessment_status = assessment_error`,
   `readiness = incomplete`.
5. `scripts/assessment_readiness.py::_dose_readiness` (900–1200): a material evidence row whose
   typed assessment is not `complete`/`not_applicable` lands in `incomplete_source_row_refs` →
   `readiness = incomplete` → the completeness gate withholds the score.

The constant in step 3 landed in `841fb2638` (2026-10-18, "retain confirmed caffeine exposure and
applicable UL populations", PR 166). `git log -S'pediatric_ul_rows_below_14_not_in_reference_data'`.

### 4.2 Driver rows (three real products; `census.json["gap"]["drivers"]`)

| Product | DSLD target groups | Driver row | UL found | Scope written | Old total → new |
|---|---|---|---|---|---|
| `12081` Teen for Her Advanced (directions: "Teens, take one tablet daily") | Girls: (All) | Vitamin A 2,500 IU | none | `pediatric`, gap | 73.2 → withheld |
| `15830` 1,000 MG Vitamin C Mangosteen (directions: "Ages 14 and up, one packet up to 2 times per day") | Children 4 or More Years of Age; Adult (18–50) | Vitamin C 1,000 mg | 1,800 mg (14–18 row) | `general_adult+pediatric`, gap | 62.0 → withheld |
| `15854` Five Calories 1000 mg Vitamin C | Children 4 or More Years of Age; Adult (18–50) | Vitamin C 1,000 mg | 1,800 mg | same | 61.5 → withheld |

In the old baseline all three had `assessment_readiness.dose.readiness = complete` and
`ul_basis = lower_sourced_adult_male_female_ul`; the new profile is
`lowest_established_ul_across_label_population`. Directions text ("Ages 14 and up") is not read by
the population owner; only `targetGroups` is.

### 4.3 Size and shape

- Rows stamped: **3,366** across the 475 products; the `ul_population.reference_gap` payload is the
  same string on every one. Units: mg 2,071, mcg 821, IU 299, mcg DFE 137, mcg RAE 24, mg NE 12 — so
  this is not the Q49 unit-sizing gap; plain mg rows are held too.
- Nutrients (rows): vitamin C 391, folate 364, zinc 337, vitamin D 272, B6 263, vitamin E 249,
  vitamin A 222, magnesium 192, niacin 183, calcium 168, manganese 165, iodine 132, selenium 109,
  phosphorus 102, choline 72, iron 45, copper 37, molybdenum 35, boron 13, vanadium 8.
- Population members: `general_adult+pediatric` 2,066 rows, `pediatric` alone 1,248,
  `adults_51_plus+general_adult+pediatric` 51, plus one with pregnancy/lactation.
- Target groups on the 475: "Children 4 or More Years of Age" 457, "Children more than 1 but less
  than 4" 126 (overlapping), "Girls: (All)" 9; 279 also carry "Adult (18–50)".
- Routes: multi_or_prenatal 306, generic 158, probiotic 6, omega 5. Brands: Emergen-C 75,
  Nature's Way 66, Airborne 45, GNC Milestones 25, Equate 22, Pure Encapsulations 20, One A Day 19.
- Prior scores: median 72.2 (range 37.0–92.1); prior bands 85+ 37, 70–84 228, 55–69 173, <55 37.
- Corpus context: 771 products carry a child target group; 483 are now not_scored, 288 scored. Of
  the scored ones, 82 also carry gap rows but stay scored because the gapped nutrient is not an
  evidence-material row for their route (omega 26, generic 24, fiber_digestive 21, probiotic 10,
  b_complex 1 — e.g. Daily Fiber's 0.4 mg iron). Readiness gates only route-material rows; that is
  consistent, but it means the same label-population gap withholds a multivitamin and not a fiber
  product.

### 4.4 The reference file

`scripts/data/rda_optimal_uls.json` (`_metadata.schema_version` 5.1.2, reference
`5.1.4-2026-10-18-dose-reference-semantics`): 77 nutrient records; every `data` row is one of
`14-18`, `19-30`, `31-50`, `51-70`, `71+` (308/308/308/154/154 rows). **No record has a 1–3, 4–8 or
9–13 row.** 23 records carry an established UL, all without younger rows; 54 carry none. So the gap
is structural in the data, not nutrient-specific: a broad children label can never complete today.
The FNB/NASEM DRI tables do publish ULs for those bands for the nutrients listed above (vitamin C
4–8 = 650 mg, 9–13 = 1,200 mg, etc.); whether to add them is a curated-data decision, not a code
fix.

### 4.5 What the north star says

A hold is the right failure mode when an assessment cannot be made (no invented claim, no false
reassurance). But 475 products that previously showed a score now show none, and the app will say
"not assessed" for 3.1 % of the catalog, concentrated in children's and family multivitamins and
vitamin C effervescents. Two of the three drivers above are 1,000 mg vitamin C products tagged for
children 4+: if the 4–8 row (650 mg) existed, the screen would not hold them — it would flag a real
exceedance for the youngest labelled population, which is exactly the sourced concern the north star
wants surfaced. Under V4.1 that exceedance also sets the Dose safety ceiling, so adding the rows will
move scores down for some of these products rather than restore them.

## 5. The sports-protein Dose-0 cases (task item 3)

Five products, all one label family — `294273`, `311852`, `312355`, `312356`, `312357` Whey Protein
(Grass-Fed) — stay `scored` with total 83.9 → 63.9 because Dose went 20 → 0:

- `quality_pillars_v4.dose.explanation.dose_receipt.assessment_status = incomplete`, contribution
  `protein_no_dose` 0 points, receipt entry `dose_not_evaluable` (kind `neutral`, 0 points), fact
  "A required ingredient amount could not be assessed." Owner: `scripts/scoring_v4/modules/sports_dose.py`
  (`_no_dose` labels at 144–157, 367–377; `unresolved_quantity` at 103).
- `assessment_readiness.dose.readiness = complete`: the one typed assessment (Whey Protein 30 g,
  `readiness = not_applicable`, `not_ul_applicable`) satisfies the readiness owner, so the product
  is not withheld.
- The V4.1 packet reviewed this exact product and accepted it: `DOSE_V41_REVIEW_PACKET.md:388`
  "294273 ingredient-only whey 30 g becomes incomplete Dose/partial assessment, preserving
  ingredient mass … a real quantity qualification correction; no purity is inferred." The label
  lists 30 g whey as an ingredient without a protein (g) nutrition line, so protein dose is unknown.

Not reproduced as a defect. Two things for Sean's awareness, both policy rather than bugs:
(a) two owners give different completeness verdicts on the same product (readiness "complete",
receipt "incomplete"); ADR-0004 wants one owner per decision, and today the receipt's verdict scores
0 while the readiness verdict decides publication; (b) an incomplete receipt awards 0/20, whereas a
disclosed amount with no benchmark gets the approved completed-neutral 11.4/20
(`DOSE_V41_REFERENCE_DECISIONS.md:68`). If "unknown protein content" should be neutral rather than
zero, that is a one-line decision in the sports Dose owner; if it should withhold, the readiness
owner would have to treat `protein_no_dose` as incomplete. The other five protein products that
dropped ≥10 points did so with complete receipts under the approved V4.1 references.

## 6. Decision for Sean before the catalog rebuild

The movement is classified; nothing here blocks the architecture roadmap, and nothing here is a
regression in PRs 155–163. It does change what the next catalog shows, and only Sean decides curated
clinical data and publication:

1. **Add the FNB child UL rows (1–3, 4–8, 9–13) for the 23 nutrients that have an established UL**
   to `scripts/data/rda_optimal_uls.json` through `/data-fix` (one batch, per-entry source
   verification against the NASEM DRI tables, `data_batch.py check`), then re-run Enrich → Score
   and re-measure. Expected: most of the 475 become assessable; products exceeding a child UL for
   their labelled population will show a sourced exceedance and a lower Dose rather than return to
   their old score. This is the option consistent with the north star and with the V4.1 rule that
   younger populations never borrow adult limits. Note the code path also needs
   `UL_SCREENING_POPULATIONS["pediatric"].ages` extended to the new bands (and the explicit-age
   parser to pick them), which is a Score/Enrich behavioural change with the full V4.1-class
   validation.
2. **Keep the hold** and ship 714 not_scored (the current main). Honest, but it removes a public
   score from 475 products that have one today, including 37 that scored 85+.
3. **Narrow the population from directions** ("Ages 14 and up" on `15830`) — a new policy and a
   new owner input; not recommended without the data fix, and DSLD directions are free text.

Whichever is chosen, the 715-product omega measurement and the Dose V4.1 packet should be amended
to record this corpus-scale count (475, not 4), because the next release's catalog diff will show it
as scores removed.

## 7. Reproduction

```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/audits/dose_hold_census_20261019/census.py \
  --old /Users/seancheick/pg_quality/full_artifact_baseline_20261018/baseline_5fb2be1ca.jsonl \
  --new /Users/seancheick/pg_quality/corpus_20261019_post167/baseline_951a05415_unpinned.jsonl
# production path
sed -n 107,160p scripts/rda_ul_calculator.py; sed -n 743,791p scripts/rda_ul_calculator.py
sed -n 21715,21743p scripts/enrich_supplements_v3.py; sed -n 22695,22704p scripts/enrich_supplements_v3.py
sed -n 500,510p scripts/dose_assessment.py; sed -n 900,1200p scripts/assessment_readiness.py
git log -S'pediatric_ul_rows_below_14_not_in_reference_data' --format='%h %ad %s' --date=short -- scripts/rda_ul_calculator.py
grep -n "def test" scripts/tests/test_ul_screening_population.py
# reference file age bands
"$PG_PYTHON" -c "import json,collections;d=json.load(open('scripts/data/rda_optimal_uls.json'));print(collections.Counter(str(r.get('age_range')) for rec in d['nutrient_recommendations'] for r in rec.get('data') or []))"
```

Owner Check: no owner created. This directory holds a dated read-only census (convention of
`scripts/audits/`). Will NOT create: a population resolver, a second readiness owner, a hash
exclusion, a restamp, or any data entry — the data addition above is Sean's `/data-fix` batch.
