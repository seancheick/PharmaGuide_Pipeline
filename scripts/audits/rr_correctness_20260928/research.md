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
