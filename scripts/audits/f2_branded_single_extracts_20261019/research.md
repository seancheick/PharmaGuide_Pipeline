# F2 follow-ups: branded single extracts filed as DSLD blends (2026-10-19)

Golden-set finding F2: Prosterol 269286 was read as a blend. That fix (e91e6b90f) made one-constituent
DSLD blend rows count as their ingredient, so the IQM form each one reaches now drives Formulation.
This batch is `ingredient_quality_map.json` entries `curcumin`, `saw_palmetto` and `blueberry`
(`data_batch.py check --expect curcumin,saw_palmetto,blueberry`: 3 changed, 0 problems).

Sources were gathered by a research agent. The main session re-read every identity source below before
applying (DSLD label API v9, NCBI esummary/efetch, Indena PDF).

| Entry | Change | Source | Verdict |
|---|---|---|---|
| curcumin | Alias `turmeric phytosome` moves from `liposomal curcumin` to `meriva curcumin`. | Indena Meriva sheet (https://www.indena.com/indena_files/2025/10/meriva_ss_us.pdf): "Curcumin Indena Phytosome®", based on lecithin, "18-22% of total curcuminoids". IQM already filed "Meriva Turmeric Phytosome" under meriva. A phytosome is a phospholipid complex, not a liposome (PMID 16164374, a review of the silybin–phosphatidylcholine phytosome). | Fixed. The old alias contradicted the sibling alias. |
| curcumin | Aliases `Mervia` and `mervia curcumin` move from `curcumin (unspecified)` to `meriva curcumin`. | "Mervia" is a label misspelling of Meriva. DSLD 296446 ("Fish Oil + Meriva Curcumin") prints "Mervia". The corpus row 293989 is "Mervia" with the form "Turmeric Phytosome". | Fixed. |
| saw_palmetto | Aliases `prosterol` and `prosterol standardized extract` move from `saw palmetto (unspecified)` to `supercritical CO₂ saw palmetto extract`. | DSLD 269589: "With Prosterol Euromed Phyto Proof", 85-95% total fatty acids. PMID 27186566 (Euromed, Barcelona): "novel saw palmetto supercritical CO2 extract (SPSE)". Nutraceuticals World 2016-07: "Euromed's branded CO2 supercritical saw palmetto extract, sold under the registered name of Prosterol". | Fixed. |
| blueberry | Alias `Wildcrafted Blueberry Complex` added to `blueberry extract`. | DSLD 232505: "AuroraBlue Wildcrafted Blueberry Complex" = Alaska, oval-leaf and alpine blueberry plus dwarf bilberry (Vaccinium spp.); "AuroraBlue is a registered trademark of Denali BioTechnologies". `AuroraBlue` was already an alias of this form. | Fixed: AuroraBlue's own descriptor. It is a multi-species Vaccinium material, not V. angustifolium alone. |

## Closed without change

| Item | Finding |
|---|---|
| Siliphos → `silymarin phytosome` | Correct. `siliphos` and `silybin phytosome` are curated aliases of that form (PMID 16164374, Siliphos = silybin–phosphatidylcholine). |
| Saw palmetto 320 mg: "no applicable dose benchmark" | Neutral Dose kept: no source supports a general dose. Record cleaned up on Sean's request (see below). |
| Carrier-complex mass (phytosome, cyclodextrin) used as the dose | Latent only. Every affected canonical (coq10, quercetin, milk_thistle, curcumin joint route) takes `no_benchmark_neutral`; Dose is identical before and after. Existing policy (`botanical_profile._is_named_standardized_botanical_complex`) treats a named phytosome mass as the studied dose form. Reference fractions: Meriva 18–22% curcuminoids (Indena); Siliphos about 29.7% silybin and Quercefit about 40% quercetin (label arithmetic); MicroActive about 25% CoQ10 (unofficial; supplier specification not found). |
| Duplicate blend-header predicate | `identity_integrity` now imports `probiotic_measurements.is_probiotic_source_header` (4535e09bb). |
| Blend-filed single form (AuroraBlue, Celadrin) | The exclusion from 0b7967268 was removed. With the AuroraBlue form mapped, identity agreement is the guard. Celadrin's form "esterified fatty acid carbons" was already a celadrin alias (cetylated fatty acid blend: cetyl myristoleate, myristate, palmitoleate, laurate, palmitate, oleate). |

## Measurement (replay.py, base main e6f2dd103, 178 raw labels)

- 37 changed; 0 of 16 controls moved; no status or safety change.
- Celadrin 302646: 50.9 → 56.4, Evidence `no_assessable_actives` → assessed.
- AuroraBlue 328293: stays scored at 60.1, with AuroraBlue now a blueberry row.
- Joint Complex 293989: 82.0 → 79.2, Very good → Good. Meriva bio 8 replaces the dropped row; the liposomal pick was 78.8.
- Prosterol 302650: 65.2 → 66.0 (CO₂ form).
- The six AuroraBlue nested-blend headers and the seven other Meriva labels are unchanged.
- Golden set: only 269286 moves. Raw contract canaries: 33/33 unchanged.

## Saw palmetto dose record cleanup (`rda_therapeutic_dosing.json::saw_palmetto_extract`, Sean 2026-10-19)

The Dose result does not change: the curve stays `completed_no_benchmark_neutral`; 0 of 61 replayed saw palmetto labels changed. Only the record's classification, sources and text are corrected.

| Field | Before → after | Source |
|---|---|---|
| `reference_type` | `no_benchmark` → `discrete_studied_regimen` (same convention as ginkgo and ashwagandha) | EMA HMPC monograph EMA/HMPC/280079/2013 (read): well-established use, hexane soft extract DER 7-11:1, "320 mg once daily or 160 mg 2 times daily"; traditional use, ethanol 90-96% extract, 320 mg once daily. |
| `references` / `source_ids` | + 37345871, + 21954478, + EMA PDF | 37345871 Cochrane 2023 (abstract read): "Serenoa repens alone provides little to no benefits"; no hexanic vs non-hexanic difference. 21954478 CAMUS (abstract read): "Increasing doses … did not reduce lower urinary tract symptoms more than placebo" (320/640/960 mg/day). `verify_all_citations_content.py --changed-since HEAD`: 3/3 MATCH. |
| `upper_limit` | `"640"` → `null`; note now says a limit is "not established" | No established upper limit: CAMUS reached 960 mg/day without clearly attributable adverse effects; EMA reports no overdose cases. Same convention as the 2026-10-11 trial-exposure corrections. |
| `upper_limit_notes` | "Doses above 320mg show no additional benefit in studies" removed | Misleading: no studied dose beat placebo (Cochrane, CAMUS). |
| `review_date` / `approval_status` | 2026-10-19 / `approved_existing_neutral_2026_10_19` | Sean asked for this cleanup; existing neutral policy unchanged. |

Not covered: the CO2 extract and whole-berry powder have no monograph dose. The AUA guideline text is behind a login and was not read.
