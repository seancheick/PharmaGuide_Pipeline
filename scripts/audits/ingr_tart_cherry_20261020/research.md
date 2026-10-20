# INGR_TART_CHERRY record corrections — receipt (2026-10-20)

Batch: `scripts/data/backed_clinical_studies.json` entry `INGR_TART_CHERRY` (one entry).

| Field | Before → after | Verified by content (2026-10-20) |
|---|---|---|
| `notable_studies` | called PMID 35790450 recovery/soreness "systematic review" evidence → describes each study as it is | PMID 35790450 (Nutr Health 2026; e-pub 2022): RCT, 44 adults, Montmorency tart cherry juice or powdered capsules for 30 days; no difference in sleep time or quality, body composition, cellular health or blood pressure. PMID 22038497 (Eur J Nutr 2012): tart cherry juice RCT; higher melatonin, total sleep time and efficiency. PMID 40964149 (Food Sci Nutr 2025): sleep systematic review. PMID 33440334 (Int J Sport Nutr Exerc Metab 2021, Hill et al.): systematic review and meta-analysis of 14 studies; small benefit for muscle soreness (ES −0.44), moderate for strength (−0.78) and power (−0.53) recovery, small for CRP and IL-6. Added because the entry's `notes` ("stronger for exercise recovery and inflammation") had no recovery citation once 35790450 was described correctly. |
| `external_ids.unii` | BUC5I9595W → 1L29G6428X | GSRS BUC5I9595W = "CHERRY", class mixture ("CHERRY, UNSPECIFIED"). GSRS 1L29G6428X = "SOUR CHERRY", parent substance PRUNUS CERASUS WHOLE. The generic cherry-flavor entry in other_ingredients keeps BUC5I9595W (correct there). |
| `standard_name` | "Tart Cherry Extract" → "Tart Cherry" | The cited evidence is juice (22038497) and juice or powdered capsules (35790450), not an extract. "tart cherry extract" is kept as an alias so existing matches hold. |

`verify_backed_studies_citations.py` (live PubMed, all entries): 923 ok of 924 claims, 0 title mismatches. Every
INGR_TART_CHERRY PMID is ok. The one ghost suspect is pre-existing and unrelated: INGR_LUTEIN cites PMID 42211211,
whose live title is "Retraction Notice".

Score effect: the new name key "tart cherry" lets rows printed "Tart Cherry" match this record directly (before, only
"tart cherry extract" or the aliases did). See the PR for the 12 products that gain tart cherry evidence.
