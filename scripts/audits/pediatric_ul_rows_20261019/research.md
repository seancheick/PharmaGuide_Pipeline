# Receipts — child Tolerable Upper Intake Levels (October 19, 2026)

Decision: Sean, 2026-10-19, option 1 of `scripts/audits/dose_hold_census_20261019/REPORT.md`.
Batch: `scripts/data/rda_optimal_uls.json`, 22 `nutrient_recommendations` entries, applied by
`apply.py` beside this file; `data_batch.py check --since origin/main --expect <22 keys>` →
"22 entries changed, 0 problem(s)". Reference version `5.1.4-2026-10-18-dose-reference-semantics` →
`5.1.5-2026-10-19-pediatric-ul-rows`; semantic fingerprint recomputed by
`reference_data_contract.semantic_rda_ul_fingerprint`.

Sources, read in the browser by the main model on 2026-10-19 (identical for every entry):

- V = National Academies DRI summary tables, *Tolerable Upper Intake Levels, Vitamins*, NCBI Bookshelf
  NBK545442 Appendix J, https://www.ncbi.nlm.nih.gov/books/NBK545442/table/appJ_tab8/
- E = same, *Tolerable Upper Intake Levels, Elements*, https://www.ncbi.nlm.nih.gov/books/NBK545442/table/appJ_tab9/

Applicability: the table's "Children 1–3 y" and "4–8 y" rows are not sex-specific and are written for
both Male and Female; "Males 9–13 y" and "Females 9–13 y" are identical for every nutrient here.
Each UL keeps the scope the record already declares (`ul_basis`, form scope): total intake unless the
table footnote limits it (magnesium: pharmacological agents only, note b; vitamin E, niacin, folate:
synthetic forms, note c; vitamin A: preformed only, note a). Rows carry `rda_ai: null` — the batch adds
safety-screen limits only; adequacy stays on the adult reference profile.
Cross-check: every child UL is positive and at or below the record's existing Male/Female 14–18 UL
(`test_rda_ul_pediatric_rows.py::test_every_established_ul_has_child_rows_except_vanadium`).

| Entry | Unit (record) | Source value 1–3 / 4–8 / 9–13 | Stored | Table | Verdict |
|---|---|---|---|---|---|
| vitamin_a | mcg RAE | 600 / 900 / 1,700 µg (preformed) | 600 / 900 / 1700 | V | added |
| vitamin_c | mg | 400 / 650 / 1,200 | 400 / 650 / 1200 | V | added |
| vitamin_d | mcg | 63 / 75 / 100 µg | 63 / 75 / 100 | V | added |
| vitamin_e | mg alpha-tocopherol | 200 / 300 / 600 | 200 / 300 / 600 | V | added |
| niacin | mg NE | 10 / 15 / 20 mg (synthetic) | 10 / 15 / 20 | V | added; same number convention as the existing 14–18 row (30) |
| vitamin_b6 | mg | 30 / 40 / 60 | 30 / 40 / 60 | V | added |
| folate | mcg DFE | 300 / 400 / 600 µg folic acid | 500 / 667 / 1000 | V | added; × 1.667 rounded, the file's convention (14–18: 800 → 1334) |
| choline | mg | 1.0 / 1.0 / 2.0 g | 1000 / 1000 / 2000 | V | added |
| boron | mg | 3 / 6 / 11 | 3 / 6 / 11 | E | added |
| calcium | mg | 2,500 / 2,500 / 3,000 | 2500 / 2500 / 3000 | E | added |
| copper | mcg | 1,000 / 3,000 / 5,000 µg | 1000 / 3000 / 5000 | E | added |
| fluoride | mg | 1.3 / 2.2 / 10 | 1.3 / 2.2 / 10 | E | added |
| iodine | mcg | 200 / 300 / 600 µg | 200 / 300 / 600 | E | added |
| iron | mg | 40 / 40 / 40 | 40 / 40 / 40 | E | added |
| magnesium | mg | 65 / 110 / 350 (pharmacological only) | 65 / 110 / 350 | E | added |
| manganese | mg | 2 / 3 / 6 | 2 / 3 / 6 | E | added |
| molybdenum | mcg | 300 / 600 / 1,100 µg | 300 / 600 / 1100 | E | added |
| nickel | mg | 0.2 / 0.3 / 0.6 | 0.2 / 0.3 / 0.6 | E | added; matches the record's own reviewed `reference_semantics` text ("younger 0.2/0.3/0.6 mg") |
| phosphorus | mg | 3 / 3 / 4 g | 3000 / 3000 / 4000 | E | added |
| selenium | mcg | 90 / 150 / 280 µg | 90 / 150 / 280 | E | added |
| zinc | mg | 7 / 12 / 23 | 7 / 12 / 23 | E | added |
| chloride | mg | 2.3 / 2.9 / 3.4 g | 2300 / 2900 / 3400 | E | added |

Siblings, one disposition each:

- vanadium — **confirmed not applicable**: E lists ND for 1–3, 4–8, 9–13 and 14–18; note d says the animal
  data "could be used to set a UL for adults but not children and adolescents". No row added; a child label
  keeps the explicit reference gap.
- Infants 0–6 / 7–12 months — **out of scope by Sean's decision** (1–3, 4–8, 9–13 only). Several nutrients
  have infant ULs in V/E (e.g. vitamin A 600, vitamin D 25/38, iron 40, zinc 4/5, selenium 45/60, calcium
  1,000/1,500, fluoride 0.7/0.9). Infant-tagged labels (27 in the corpus) keep the explicit gap. Queued as a
  possible follow-up, not added.
- Nutrients with no established UL (54 records, e.g. vitamin K, thiamin, B12) — **unaffected**: V/E list ND
  for every age, and the screen already treats them as completed "no established UL".
- Child RDA/AI values — **not added**: adequacy uses the adult profile by design; out of scope.

Free text checked: the only text in the file about younger ages is nickel's `reference_semantics`, which
already states the same values. No phrase asserting "no rows below 14" exists in the data; the code string
`pediatric_ul_rows_below_14_not_in_reference_data` is replaced by `pediatric_ul_row_missing_for_stated_age`
and appears nowhere else (`grep -rn` over `scripts/`, excluding dated audits).
