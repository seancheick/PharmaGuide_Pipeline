# Evidence review receipts: packet item 3 (2026-09-28)

Sean asked for every product whose Evidence read `not_yet_reviewed` to be reviewed (packet item 3).
The 8 products' open identities were their purpose-owning blends (owner-scoped
`evidence_resolver.resolve_product_evidence` returned `literature_resolution_required`). One
receipt per identity. Searches ran against live PubMed E-utilities on 2026-09-28; the abstracts of
every trial cited were read in full (efetch).

## Literature records (`literature_evidence_records.json`)

A record completes the review; it never awards points.

| Canonical | Products | Query | Hits | Verdict |
|---|---|---|---:|---|
| `anabolic_muscle_primer` | 1179, 14168 | `"Anabolic Muscle Primer"[tiab] OR ("Ravage"[tiab] AND "GNC"[tiab])` | 0 | no qualifying human evidence |
| `muscle_buffering_system` | 1179, 14168 | `"Muscle Buffering System"[tiab]` | 0 | no qualifying human evidence |
| `thermo_energy_matrix` | 14168 | `"Thermo Energy Matrix"[tiab] OR ("Rampant"[tiab] AND "GNC"[tiab])` | 0 | no qualifying human evidence |
| `organic_golden_milk_blend` | 243271 | `"golden milk"[tiab] AND (randomized controlled trial[pt] OR clinical trial[pt] OR systematic review[pt])` | 0 | no qualifying human evidence |
| `organic_u_s_a_farmed_green_juice_blend` | 282638 | `("grass juice"[tiab] OR "cereal grass"[tiab]) AND (randomized controlled trial[pt] OR clinical trial[pt])` | 4 | no qualifying human evidence: three small wheat-grass-juice pilots in disease populations (PMIDs 11989836 colitis, 15297687 thalassemia, 17571966 chemotherapy) and an observational diet study; none tests this five-grass blend |
| `raw_organic_sprout_and_fiber_blend` | 299755 | `"Raw Organic Fiber"[tiab] OR ("sprout"[tiab] AND "fiber blend"[tiab])` | 0 | no qualifying human evidence |
| `raw_fitbiotic_blend` | 275464 | `Fitbiotic[tiab] OR ("Garden of Life"[tiab] AND probiotic*[tiab])` | 0 | no qualifying human evidence |

Each blend's disclosed constituents keep their existing records (turmeric, ashwagandha, flaxseed,
barley grass, the probiotic species, ...); a blend's undisclosed amounts cannot inherit them.

## Composition searches (added after review)

Brand-name searches alone cannot close a review, so each blend was also searched by composition. The
GNC blends list their contents as DSLD `forms` (their `nestedRows` are empty; an earlier note here wrongly
said they list none), with no individual amounts.

| Canonical | Composition query | Hits | Verdict |
|---|---|---:|---|
| `muscle_buffering_system` (astaxanthin, CarnoSyn) | `(astaxanthin[tiab]) AND ("beta-alanine"[tiab] OR "beta alanine"[tiab] OR carnosyn[tiab]) AND (randomized controlled trial[pt] OR clinical trial[pt])` | 0 | none |
| `anabolic_muscle_primer` (betaine, fenugreek, saw palmetto, yam, yohimbe) | `(betaine[tiab]) AND (fenugreek[tiab] OR "saw palmetto"[tiab] OR yohimbe[tiab] OR yohimbine[tiab] OR "wild yam"[tiab] OR dioscorea[tiab]) AND (randomized controlled trial[pt] OR clinical trial[pt])`; `(fenugreek[tiab] AND ("saw palmetto"[tiab] OR yohimbe[tiab] OR yohimbine[tiab])) AND (randomized controlled trial[pt] OR clinical trial[pt])` | 0 | none |
| `thermo_energy_matrix` (acetyl-L-carnitine, black pepper, caffeine, Capsimax, choline, phenylalanine, taurine) | `(caffeine[tiab]) AND (capsicum[tiab] OR capsaicin*[tiab] OR capsimax[tiab]) AND (taurine[tiab] OR carnitine[tiab] OR choline[tiab]) AND humans[mh]` | 2 | two narrative reviews (PMIDs 35565754, 27465721), no trial of the combination |
| `organic_golden_milk_blend` | `(turmeric[tiab] OR curcuma[tiab]) AND ginger[tiab] AND (cinnamon[tiab] OR ashwagandha[tiab] OR "black pepper"[tiab]) AND (randomized controlled trial[pt] OR clinical trial[pt]) AND humans[mh]` | 6 | other formulas only (PMIDs 42360298, 36419388, 32211803, 32180294, 30259284, 25592751) |
| `organic_u_s_a_farmed_green_juice_blend` | `("barley grass"[tiab] OR "young barley"[tiab]) AND (wheatgrass[tiab] OR "wheat grass"[tiab] OR alfalfa[tiab] OR "oat grass"[tiab]) AND (randomized controlled trial[pt] OR clinical trial[pt])` | 0 | none |
| `raw_organic_sprout_and_fiber_blend` | `(sprouted[tiab] OR sprout[tiab]) AND (flax*[tiab] OR chia[tiab] OR quinoa[tiab] OR amaranth[tiab]) AND fiber[tiab] AND (randomized controlled trial[pt] OR clinical trial[pt])` | 0 | none |
| `raw_fitbiotic_blend` | `(probiotic*[tiab]) AND "Lactobacillus gasseri"[tiab] AND "Bifidobacterium longum"[tiab] AND "Lactobacillus rhamnosus"[tiab] AND (weight[tiab] OR adipos*[tiab] OR obes*[tiab] OR "body fat"[tiab]) AND randomized controlled trial[pt]` | 1 | a different formula for GI symptoms after bariatric surgery (PMID 38418752); the label names no strains |

Product-level state after review (owner-scoped `resolve_product_evidence`): 7 of 8 read
`applicability_unestablished` because another owner ingredient legitimately keeps it there
(cinnamon/turmeric amount undisclosed inside a blend, pomegranate and flaxseed sub-clinical,
Sytrinol 150 mg below the 300 mg studied dose, Tesnor blocked by D23); Fitbiotic reads `assessed`.

## Reviewed clinical entries (`backed_clinical_studies.json`)

The one Evidence points owner. Query `Tesnor[tiab]` returned 4 records; query
`("polymethoxylated flavones"[tiab] OR "citrus flavonoids"[tiab]) AND tocotrienol*[tiab] AND humans[mh]`
returned 3 (the third, PMID 9781306, is an animal-cancer review and does not qualify).

- **BRAND_TESNOR** (315089): LN18178/Tesnor, standardized pomegranate fruit-rind + cocoa seed
  extracts. PMID 35129040 (Sreeramaneni 2023, J Diet Suppl): 120 men 21-35 y, placebo / 200 / 400
  mg/day, 56 days; free testosterone up at both doses, total testosterone up at 400 mg versus
  placebo. PMID 35928723 (Pandit 2022, Int J Med Sci): 120 men 36-55 y, same arms; aging males'
  symptoms score down, free and total testosterone up. Both from the developer, no independent
  replication, hormone and symptom-score endpoints: `positive_weak`, studied 200-400 mg/day. The
  label gives 400 mg/day (one pack daily), inside the studied range.
- **BRAND_SYTRINOL** (54775): citrus polymethoxylated flavones + palm tocotrienols. PMID 17985810
  (Roza 2007, Altern Ther Health Med): 270 mg flavones + 30 mg tocotrienols (300 mg/day) versus
  placebo; 120 adults for 12 weeks plus two open-label groups of 10; total cholesterol down
  20-30%, LDL down 19-27%. PMID 25828621 (Schuchardt 2015, Eur J Clin Nutr): 240 adults, 115 or
  59 mg/day combinations versus placebo for 12 weeks; no LDL-C or hsCRP difference. `mixed`,
  positive only at 300 mg/day. The label gives 150 mg with no directions (one softgel a day by
  default), below the only positive dose, so it earns no points.

## Verification

- `scripts/api_audit/verify_backed_studies_citations.py`: 494 PMID claims, 0 title mismatch, 0
  drift, 0 ghost suspects, 0 not found.
- `verify_literature_records.verify_literature_file(apply_fixes=False)`: 754 records, 0 failures,
  0 corrections, 0 retractions. The new records carry provenance naming the live E-utilities
  searches above, not the file-wide verifier run.
- `scripts/data_batch.py check ... --since HEAD`: 7 literature records and 2 clinical entries
  added, nothing else changed.
- No clinician sign-off is asserted.

## BRAND_ZYLOFRESH alias (2026-09-29)

- **Entry:** `backed_clinical_studies.json` BRAND_ZYLOFRESH, aliases `["zylofresh", "alfalfa extract"]` →
  `["zylofresh"]`. The entry is preclinical and its own `notable_studies` records no human trials for
  the brand. "alfalfa extract" names the plant preparation, not the brand; it stays where it belongs,
  on IQM `alfalfa` and `botanical_ingredients` `alfalfa_leaf`.
- **Effect:** the branded clinically-studied form credit (`botanical_profile._branded_studied_set`: +3
  and full standardization) and a preclinical Evidence match reached every alfalfa extract.
- **Replay:** 300 frozen labels naming a branded ingredient (`~/pg_quality/rr_fix/frozen_branded`),
  origin/main c581a9ae against the fix: 2 move, BulkSupplements Alfalfa Extract 253578 and 253582,
  63.0 → 55.7 (Formulation 20 → 13.3; Evidence 0.6 → 0, now `applicability_unestablished` from the
  existing reviewed `alfalfa` literature record: PubMed, no qualifying human studies). No status,
  route or verdict change.
- **Siblings, recorded not changed:** 29 other BRAND_ entries carry a generic ingredient name as an
  alias (for example astaxanthin, L-theanine, MSM, HMB, methylfolate, piperine, lactoferrin,
  citicoline, urolithin A). For Evidence some may be intended (ingredient-level trials); for the
  branded Formulation credit they are the same defect, which the branded-shortcut decision (register
  D24 item 6) removes at the owner. Not bulk-edited.

## MSM evidence applicability (2026-09-29)

- **Finding (review):** 182940 Glucosamine/MSM read Evidence 15.6/20 `evaluated_applicable` at 500 mg
  MSM/day; the cited trials used 2 and 6 g/day. Cause: `BRAND_OPTIMSM` carried the generic aliases
  "msm" and "methylsulfonylmethane" and no studied dose, so every MSM row took the branded
  verified-primary floor (`generic_evidence`, `_BRANDED_EVIDENCE_LEVELS` / `brand_` id) with no
  sub-clinical check.
- **Receipts (live PubMed efetch, Europe PMC full text, 2026-09-29):** PMID 16309928 (Kim 2006,
  Osteoarthritis Cartilage): 50 adults with knee OA, MSM 3 g twice daily (6 g/day) 12 weeks, WOMAC
  pain and physical function better than placebo; stiffness and total symptoms unchanged; pilot;
  MSM source not named in the abstract. PMID 37447322 (Toguchi 2023, Nutrients, PMC10346176): 88
  adults with mild knee pain, ten 200 mg tablets (2 g/day) 12 weeks, JKOM total score better than
  placebo (p = 0.046); full text: "OptiMSM (Bergstrom Nutrition ...) was used as the active
  substance". Identity: UNII 9H4PO4Z4FT = methylsulfonylmethane (GSRS), as on IQM `msm`.
- **Change:** `BRAND_OPTIMSM` aliases → `["optimsm"]`, studied dose 2000-6000 mg/day; new
  `INGR_MSM` (ingredient-human, aliases msm / methylsulfonylmethane, same two trials, 2000-6000
  mg/day, positive_weak, tier_2, joint endpoints only). `verify_backed_studies_citations.py`: 496
  claims ok, 0 mismatch, 0 ghost.
- **Replay** (82 raw labels with a 3-letter title ingredient, main 827f6b90 vs this): 44 move,
  33 tier crossings, no status or route change, Evidence only. Glucosamine + MSM products return
  to their values before the title fix (182940 74.9 → 66.6). Single MSM products below 2 g/day at
  minimum directed use lose the brand floor (224694 MSM 1000 mg, 1 g/day: 78.4 → 62.8, Evidence
  15.6 → 0, `applicability_unestablished`); at 2 g/day or more they keep ingredient-level
  Evidence (202773 3 g/day: 15.6 → 10.4).
- **Scope, recorded not changed:** 202 of 211 clinical entries carry no studied dose, so Evidence
  cannot check the label amount for them; register Q39g.
