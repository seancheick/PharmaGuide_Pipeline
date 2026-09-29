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
- **Scope, recorded not changed:** 201 of 211 clinical entries carry no studied dose, so Evidence
  cannot check the label amount for them; register Q39g.

## Brand evidence reaching plain ingredients (2026-09-29)

- **Owner:** `enrich_supplements_v3._brand_mentioned` confirms an alias-only BRAND_ match in the
  product text; aliases are the discovery surface and may be generic, and a curated `brand_tokens`
  list is the confirmation. Without `brand_tokens` the check fell back to the aliases, so a generic
  alias confirmed itself.
- **Census** (all 15,414 raw labels holding a BRAND_ entry's generic name, enriched at 495c2d8c):
  221 BRAND_ matches; 81 labels took a brand record while never naming a brand: BioPerine via
  "piperine" 37, HMB 35, OptiFerrin via "lactoferrin" 6, Zynamite via "mangiferin" 2 (a Suntheanine
  case was a census false positive: 261621 names Suntheanine). Entries that already carry
  `brand_tokens` (AstaReal, Quatrefolic, Cognizin, Suntheanine, MenaQ7) leaked nothing.
- **Receipts** (live PubMed efetch, 2026-09-29):
  - BRAND_BIOPERINE: its only citation, PMID 9619120 (Shoba 1998), is a pharmacokinetic study
    (piperine 20 mg raised curcumin bioavailability). → `brand_tokens: ["bioperine"]`.
  - BRAND_ZYNAMITE: PMIDs 32717999, 30736383, 31661850 all name Zynamite (>60% mangiferin); two
    test it with luteolin or quercetin. → `brand_tokens: ["zynamite"]`.
  - BRAND_HMB → **INGR_HMB**, ingredient-human: PMIDs 24599749 (HMB free acid RCT), 35911112 and
    41305674 (meta-analyses), 25700845 (RCT, older men) test HMB with no brand. No dose in the
    abstracts, so none recorded.
  - BRAND_OPTIFERRIN → **INGR_LACTOFERRIN**, ingredient-human, 200 mg/day: its notes already said
    the brand identity was never verified; PMID 19639462 (bovine lactoferrin 100 mg twice daily vs
    ferrous sulfate, 100 pregnant women) and PMID 35276902 (meta-analysis).
  - `verify_backed_studies_citations.py`: every cited PMID resolves and matches its stored title.
- **Replay** (81 affected + 25 brand-naming controls, main 495c2d8c vs this): 23 move, 10 tier
  crossings, no status change, 0 controls move. HMB -4.4 x12 (ingredient evidence, no brand floor);
  lactoferrin -0.5 to -4.4 x6; plain black pepper extract -18.9 x5 (311167 81.3 -> 62.4, Evidence
  18.9 -> 0).
- **Recorded, not changed:** BioPerine's evidence is pharmacokinetic (absorption of other
  compounds), yet the entry reads positive_strong with "Increase Energy"; and the Formulation
  branded-trial credit (`botanical_profile._branded_studied_set`) still keys on aliases, so plain
  black pepper extract keeps +3/+4 there (register D24 item 6).

## Branded form credit follows the brand check (2026-09-29)

- **Defect:** `botanical_profile._branded_studied_set` gave full standardization (4), +3 "branded
  clinically studied" and studied-dose status to any row whose names met a BRAND_ entry's aliases,
  a second, looser answer to "does this label name the brand". A plain black pepper extract
  (BulkSupplements 311167) scored Formulation 20/20 as BioPerine.
- **Owner:** `enrich_supplements_v3._brand_mentioned` (aliases find, `brand_tokens` confirm) and the
  clinical match's `matched_source_row_refs`. New `botanical_profile._branded_studied_row(product,
  row)` reads that record; a preclinical-only brand is not "clinically studied".
- **Replay** (920 raw labels whose rows meet a brand alias, cc0d8b92 vs this): 6 move, no status
  or tier change. Five plain black pepper extracts -4.0 (311167, 330436-330439: Formulation
  20 -> 16, 62.4 -> 58.4); 300258 Legion Fortify +0.7 (its row reads "Meriva Curcuma longa L.
  rhizome extract", which the exact-name set missed).
- **Regression caught in the fresh corpus (07116c4a) and fixed:** a label-level projection (a
  brand-named blend total: Sytrinol 54775/251856, Tesnor 315089/315816, Pycnogenol in Mirtogenol
  231868) is never assessed by the enricher's evidence matcher, so it lost the credit (-4.0 to -6.7;
  231868 SAFE -> POOR). The same rule now reads such a row's own label name (aliases find,
  `brand_tokens` confirm). Full corpus re-scored from the fresh enriched outputs: exactly these 5
  return to their prior Formulation, nothing else of 15,421 changes. Remove the projection branch
  when the enricher records brand matches for brand-named blend totals.
- **Found, not changed:** GNC 316434 names KSM-66 only in label statements ("Ashwagandha as
  KSM-66") over a plain "Ashwagandha Root Extract" row, so no brand record is discovered
  (before and after this change).

## BioPerine evidence record (2026-09-29, decision for Sean)

- `BRAND_BIOPERINE` reads positive_strong, primary outcome "Increase Energy", goals Energy and
  Healthy Aging. Its one citation, PMID 9619120 (Shoba 1998, doi 10.1055/s-2006-957450), is a
  pharmacokinetic study: piperine 20 mg with 2 g curcumin raised curcumin exposure (reported
  2000%) in human volunteers. No energy or ageing outcome.
- PubMed, piperine RCTs without curcumin/turmeric in the title (9 hits, read 2026-09-29): absorption
  results differ by compound. Resveratrol 2.5 g + piperine 5 or 25 mg showed no significant PK
  change (PMID 32868637, doi 10.1097/CEJ.0000000000000621); resveratrol + piperine 20 mg changed
  cerebral blood flow but not plasma levels, cognition or mood (PMID 24804871); nevirapine
  exposure rose ~170% (PMID 17963429, a drug-interaction signal). Piperine-alone efficacy: one
  12-week NAFLD trial at 5 mg/day (PMID 38200253, liver enzymes, glucose, lipids).
- The absorption-aid fact already has an owner: `absorption_enhancers.json` ENHANCER_BLACK_PEPPER
  (same PMIDs, content-verified 2026-08-08; piperine <= 10 mg demoted to non-scorable). The
  clinical record restates it as efficacy for user goals the evidence does not reach.
- Impact today: after c842e774 the record reaches only labels naming BioPerine; in the 100 such
  labels in the 2026-09-22 corpus, Evidence came from the main ingredient (CoQ10, curcumin).
- Recommendation: remove the record (the enhancer entry keeps the fact). Deleting curated clinical
  data is Sean's decision.
- **Removed 2026-09-29 (Sean):** `BRAND_BIOPERINE` deleted; ENHANCER_BLACK_PEPPER keeps the fact.
  Replay of the 63 raw labels that matched it (ea72092f vs this): 2 move, 182824 and 184133
  "Curcumin 500 with Bioperine" 69.1 -> 66.4 (Evidence 2.7 -> 0, now "review pending"), because
  of the defect below.

## Absorption-enhancer demotion never reaches scoring (2026-09-29, recorded for next cycle)

- `enrich_supplements_v3._apply_absorption_enhancer_demotion` removes piperine <= 10 mg from
  `ingredients_scorable` (130 rows in the fresh corpus at 07116c4a), but the scoring contract
  puts it back: through a row-level `label_active_projection` (229934: enricher
  `product_scoring_evidence` reason `identity_bearing_active_anchor_mass`) or a row rebuilt
  from the label (262176). All 114 products with a demoted piperine score it anyway.
- The demotion also matches names exactly and the IQM name "Piperine (Black Pepper Extract)"
  (UNII U71XL721QK) is no enhancer alias, so 44 more <= 10 mg rows are never demoted.
- Effect: piperine enters Formulation averages, and on a title that names BioPerine it becomes
  the Evidence owner (182824: `evidence_owner_canonicals` = {piperine}, not the 500 mg turmeric).
- Fix together, measured: the contract honours the enricher's demotion, then the alias. About
  158 products move. The one-alias change alone was reverted (it moves enriched rows while
  scoring re-adds them).
