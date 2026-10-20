# INGR_TART_CHERRY record corrections — receipt (2026-10-20)

Batch: `scripts/data/backed_clinical_studies.json` entry `INGR_TART_CHERRY` (one entry).

| Field | Before → after | Verified by content (2026-10-20) |
|---|---|---|
| `notable_studies` | called PMID 35790450 recovery/soreness "systematic review" evidence → describes each study as it is | PMID 35790450 (Nutr Health 2026; e-pub 2022): RCT, 44 adults, Montmorency tart cherry juice or powdered capsules for 30 days; no difference in sleep time or quality, body composition, cellular health or blood pressure. PMID 22038497 (Eur J Nutr 2012): tart cherry juice RCT; higher melatonin, total sleep time and efficiency. PMID 40964149 (Food Sci Nutr 2025): sleep systematic review. PMID 33440334 (Int J Sport Nutr Exerc Metab 2021, Hill et al.): systematic review and meta-analysis of 14 studies; small benefit for muscle soreness (ES −0.44), moderate for strength (−0.78) and power (−0.53) recovery, small for CRP and IL-6. Added because the entry's `notes` ("stronger for exercise recovery and inflammation") had no recovery citation once 35790450 was described correctly. |
| `external_ids.unii` | BUC5I9595W → 1L29G6428X | GSRS BUC5I9595W = "CHERRY", class mixture ("CHERRY, UNSPECIFIED"). GSRS 1L29G6428X = "SOUR CHERRY", parent substance PRUNUS CERASUS WHOLE. The generic cherry-flavor entry in other_ingredients keeps BUC5I9595W (correct there). |
| `standard_name` | unchanged ("Tart Cherry Extract") | Renaming to "Tart Cherry" (the evidence is juice and powder) was measured and reverted (option A): the new name key let 12 rows printed "Tart Cherry", undosed blend members, match by name and earn Evidence credit. "Tart Cherry" is re-applied after the Evidence materiality fix lands. |
| `references_structured` | add PMID 33440334; 40964149 graded `systematic_review` | 33440334 live metadata: Int J Sport Nutr Exerc Metab 2021, publication types Journal Article / Meta-Analysis / Systematic Review, not retracted. 40964149's title is "…A Systematic Review" (PubMed lists the types as Journal Article / Review, kept verbatim). |

`verify_backed_studies_citations.py` (live PubMed, all entries): 923 ok of 924 claims, 0 title mismatches. Every
INGR_TART_CHERRY PMID is ok. The one ghost suspect is pre-existing and unrelated: INGR_LUTEIN cites PMID 42211211,
whose live title is "Retraction Notice".

Score effect: none intended (the name is unchanged). The replay on the PR measures it.
