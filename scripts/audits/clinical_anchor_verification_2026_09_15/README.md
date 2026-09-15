# Clinical dose anchor verification (2026-09-15)

`scripts/data/rda_optimal_uls.json` holds 30 compounds with no official DRI. For each, the
`rda_ai` value is documented as "the lower bound of the clinically effective dose" and the
generic dose window scores products against it. None of those anchors had been content-checked.

## Result

| Decision | Count | Anchors |
|---|---|---|
| verified | 12 | chlorophyllin 300 mg, glucosamine sulfate 1500 mg, GABA 100 mg, ubiquinol 100 mg, NMN 250 mg, PQQ 20 mg, berberine 900 mg, quercetin 500 mg, citicoline 250 mg, glycine 3 g, pantethine 600 mg, urolithin A 500 mg |
| corrected | 7 | magnesium L-threonate 1500 -> 1000 mg, MSM 1500 -> 2000 mg, hyaluronic acid 80 -> 120 mg, betaine 2500 -> 1500 mg, HMB 3 -> 1.5 g, beta-alanine 3.2 -> 1.6 g, bovine colostrum 10 -> 3.2 g |
| supported_uncontrolled | 1 | DIM 100 mg (single-arm study only) |
| not_established | 10 | GLA, evening primrose oil, citrulline malate, L-citrulline, melatonin, NAC, SAMe, 5-HTP, essential amino acids, L-glutamine |

Every decision, quote and reason is in `anchor_verification.json`. Notable findings:

- **Hyaluronic acid cited the wrong evidence**: an injection-versus-NSAID review and a
  multi-ingredient krill product. Oral placebo-controlled trials are positive at 120 mg/day.
- **L-glutamine's own reference contradicted it**: the meta-analysis found effects only
  above 30 g/day; 5 g/day is unsupported.
- **The first pass wrongly verified betaine at 2.5 g.** A benefit at the anchor dose does
  not make it the lowest effective dose; Olthof 2003 (PMID 14652361) lowered homocysteine at
  1.5 g/day. Every eligible anchor was then re-searched for lower effective doses, which also
  corrected HMB, beta-alanine and colostrum.
- **NMN and PQQ were first verified on the wrong trials.** The first pass cited a biomarker-only
  NMN trial (blood NAD+) and a 21.5 mg/day PQQ trial. A follow-up audit rightly rejected that
  evidence, but it raised the anchors to 300 mg and 21.5 mg without searching lower doses. Two
  trials supported the original doses, so both anchors are back at those values with the new
  evidence:
  - **NMN, 250 mg/day (PMID 38789831):** placebo-controlled; the NMN group had a shorter 4-m walking
    time and better sleep scores than placebo. Its primary stepping-test endpoint was null, and other 250 mg/day
    trials were null or only nominally significant, so this evidence is mixed.
  - **PQQ, 20 mg/day (PMID 26782228):** placebo-controlled; Stroop-test benefit over placebo.

## Files

- `anchor_verification.json` — decisions, evidence quotes (PMID, location, exact text), reasons.
- `verify_anchor_citations.py` — live gate: every quote must appear in the PubMed abstract or
  Europe PMC full text, and the ledger must cover exactly the 30 no-DRI entries.
  Last run: 51 PMIDs, 71 quotes, 0 failures.
- `apply_anchor_verification.py` — dry run by default; checks each entry still carries the
  reviewed (or already corrected) value, applies corrections and references, writes one dated
  review sentence per entry, and restamps the reference data contract (5.1.2-2026-09-15).

```bash
python3 scripts/audits/clinical_anchor_verification_2026_09_15/verify_anchor_citations.py
python3 scripts/audits/clinical_anchor_verification_2026_09_15/apply_anchor_verification.py
```

## Scoring effect (quality_score 1.5.1)

The production config's `_clinical_anchor_reference_by_canonical` map (loaded by
`generic_dose`) lists only verified or corrected anchors that appear in product adequacy rows
(quercetin, betaine, glycine, GABA, berberine, beta-alanine, glucosamine, hyaluronic acid,
NMN, PQQ, colostrum, urolithin A). Those earn credit in proportion to the anchor up to 100%;
every other anchor keeps the legacy full-credit-at-25% rule. The test
`test_clinical_anchor_map_lists_only_pubmed_verified_anchors` ties that single production map
to this evidence ledger and to the reference values.

Projected effect after a re-enrich (every catalog adequacy row for a graduating anchor, its
percentage rescaled from the old anchor to the corrected one; raw window credit out of 22):

| Anchor | Rows | Legacy credit | New credit | Rows lower |
|---|---:|---:|---:|---:|
| betaine | 328 | 14.27 | 11.60 | 211 |
| hyaluronic acid | 201 | 12.36 | 7.91 | 159 |
| quercetin | 189 | 10.86 | 7.09 | 142 |
| beta-alanine | 157 | 18.56 | 17.68 | 41 |
| glucosamine | 234 | 21.52 | 18.70 | 70 |
| GABA | 102 | 18.69 | 16.86 | 31 |
| glycine | 83 | 13.84 | 7.17 | 69 |
| berberine | 38 | 20.01 | 11.56 | 31 |
| PQQ | 35 | 22.00 | 15.87 | 19 |
| colostrum | 18 | 6.70 | 5.23 | 18 |
| NMN | 14 | 21.69 | 19.17 | 3 |
| urolithin A | 2 | 22.00 | 11.00 | 2 |

All 1,401 rows: mean 15.86 -> 12.55; none higher. The drops are doses below the lowest
effective dose found (for example 50-100 mg hyaluronic acid, 250-400 mg quercetin, 500 mg
glycine inside blends). The NMN and PQQ rows were computed against 250 mg and 20 mg, the
values the anchors carry again. Extra searches for a positive controlled trial of PQQ at 10 mg
or GABA below 100 mg found none.

Enriched products carry `pct_rda` computed against the anchors at enrichment time, so the new
values only take effect after a re-enrich. The packet diff (pass 2 vs dc359c4d) therefore shows
the betaine product at 1500 mg dropping 10 points against the old 2.5 g anchor; against the
corrected 1.5 g anchor it earns full credit.
