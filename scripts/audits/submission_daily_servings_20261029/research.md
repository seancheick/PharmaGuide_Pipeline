# Submission daily-servings corrections — 2026-10-29

Batch: label-sourced daily servings for approved submission labels whose import carried no
min/maxDailyServings, so Clean fell back to a default regimen that daily-exposure consumers treat as
unknown (`serving_frequency.py`, `enrich_supplements_v3.py`). Owner: `product_label_corrections.json`
`serving_basis_correction`, bound to the raw approved bytes' SHA-256. Raw approved files unchanged.
Reviewer: agent review (Claude Opus 5.5) of the approved submission photographs.

| Entry | Printed directions (photo) | Serving size | Daily | Verdict |
|---|---|---|---|---|
| PG_SUB_8800C6CB… O Positiv URO | "Adults take 2 capsules once daily…" (03_directions_warnings) | 2 capsules | 1/1 | applied |
| PG_SUB_F580FBD6… TJ Omega-3 | "SUGGESTED USE: Take one softgel daily with food." (04_supplement_facts) | 1 softgel | 1/1 | applied |
| PG_SUB_7283A83B… One A Day Prenatal Advanced | "Directions: Adults, take one softgel and one tablet daily with food." (01, submitted label artwork) | 1 softgel + 1 tablet (two rows) | 1/1 each | applied |
| PG_SUB_C926B40D… Force Factor NAD+ | directions side not photographed; brand page "Take 2 capsules once daily" shows a newer formula edition (Luteolin 100 mg vs box 50 mg) | 2 capsules | — | NOT applied: needs a retake of the directions panel |
| PG_SUB_4ACB39B9…, PG_SUB_5E4D136A… | already corrected to 1/1 by existing entries | | | unaffected |

Measurement (`replay.py snapshot --full`, base origin/main 0c49a381c vs candidate, 3 affected + 2 controls):
scores/pillars/verdicts unchanged; cleaned `servingSizes[*].dailyServingsSource` default→label on the 3
entries; enriched `dosage_normalization.serving_basis.confidence` low→high (8800C6CB, F580FBD6); controls
(C926B40D, 3D5877FE) byte-identical. Receipts: ~/pg_quality/submission_daily_20261029/.

Out of scope (owner cannot represent; no shipped consumer impact found), from the same photo audit:
54970EAA "Total Carbohydrate less than 1g" (typed nutritionalInfo has no operator), F580FBD6
Polyunsaturated Fat 0.5 g, 7283A83B tablet ingredient grouping (Clean flattens inactives),
5871249A creatine listed as other ingredient (Clean already drops the duplicate inactive).
