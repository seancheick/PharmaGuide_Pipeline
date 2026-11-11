# Liver/antioxidant batch receipts — ADR-0007 one-pass review (2026-11-10)

Agent review by Claude; independent agent check recorded below. Not clinician review.
Cohort from `/Users/seancheick/pg_quality/evidence-v1-closeout-20261110/ZERO_AUDIT.md` (milk thistle,
alpha-lipoic acid, NAC, resveratrol). Census: `~/pg_quality/catalog-release-20261105/CENSUS_ALL.json.gz`.

## Finding: the audit's "missing credit" class was wrong for all four

Every material row of all four ingredients already finishes as `reference_only_clinical_record`
(a completed Evidence zero, not a hold): milk thistle 128 material rows, ALA 119, NAC 116,
resveratrol 80 (census `ingredient_assessments`, roles major/claim_prominent). Each record carries a
documented, signed or reconciled conclusion, so under ADR-0007 the zero is a justified finding.
Live probe (`evidence_resolver.resolve_evidence_for_canonical`) on the candidate base confirms
`research_present_applicability_unestablished` / `reference_only_clinical_record` for each.

| Ingredient | Record | Existing conclusion | Decision | Data change |
|---|---|---|---|---|
| Milk thistle | INGR_MILK_THISTLE | Signed A092 (Dr. Pham, 2026-10-28): rejects "liver protection and enzyme normalization"; narrow NAFLD/NASH research reading only; both contexts `rejected_source` | Zero confirmed. Record text was never reconciled with A092. | notes, notable_studies, effect_direction (positive_strong → mixed), rationale, chips emptied, published_studies → PMIDs, unsupported enrollment/registry counts → null |
| Alpha-lipoic acid | INGR_ALPHA_LIPOIC_ACID | Signed A036: limited diabetic-neuropathy symptom evidence only; no generic credit | Zero confirmed; text already consistent | none |
| NAC | INGR_NAC | Signed A094: limited oral exercise-soreness findings only; other uses nonaffirmative reference | Zero confirmed; one sentence overstated its source | first notes sentence scoped to its sources |
| Resveratrol | PRECLIN_RESVERATROL | Reconciled 2026-10-23/28: mixed, outcome-specific biomarker evidence | Zero confirmed; text already consistent | none |

## Milk thistle sources (read 2026-11-10)

1. NCCIH milk thistle fact sheet (updated February 2025, nccih.nih.gov/health/milk-thistle): liver-disease
   trial results "conflicting or too limited to allow conclusions"; two NCCIH-funded trials (hepatitis C,
   NASH) showed no benefit; small studies on blood sugar in type 2 diabetes, mostly Middle Eastern.
2. PMID 38579127, Ann Hepatol 2024, first author Li S (PubMed esummary). The record's old
   "Kalopitas et al." attribution was wrong. 26 RCTs, 2,375 NAFLD/NASH patients; no silymarin dose;
   mostly add-on therapy (verified context, A092).
3. PMID 17943794, Rambaldi 2007 Cochrane (PubMed efetch): 18 RCTs, 1,088 patients, low quality; no effect on
   mortality (RR 0.78, 0.53-1.15), complications or histology; authors "question the beneficial effects".

## NAC sentence (PubMed efetch 2026-11-10)

Old: "Human evidence supports NAC as a glutathione precursor that measurably lowers oxidative-stress markers".
PMID 39632267 (2024 meta-analysis, 20 studies) measured these markers **after exercise** only (TBARS lower,
GSH higher; TNF-alpha, CK, GSSG unchanged). PMID 9230243 (De Flora 1997): 262 adults, 78% aged 65+, 600 mg
twice daily for 6 months; fewer and milder influenza-like episodes; did not prevent infection. The new
sentence states exactly that.

## Not changed, noted

- BRAND_MEDIHERB_SILYMARIN: `key_endpoints` still say "hepatoprotection ↑" although its notes report null
  primary endpoints. No corpus label names MediHerb (`grep -rli mediherb` over the raw brands: 0), so it
  reaches no product; left for a later reconciliation.

## Output impact (measured)

Reference-only records are exported only as `rejected_clinical_matches` (id and reason code), never with
notes or chips (product 18296: `evidence_data.rejected_clinical_matches[0]`). Replay of 58 unique frozen labels
(sampled for milk thistle, NAC, ALA and resveratrol plus controls; the per-ingredient samples overlap
because multi-ingredient labels carry more than one cohort ingredient, so they do not sum to 58;
IDs in `replay_ids.json` beside this file), `snapshot --full --blob`,
base 8c47db63a vs candidate: 0 records differ in cleaned, enriched, scored or blob hashes. This batch is a
record-consistency correction with no current product-output change.

## Independent check



A fresh-context agent reviewer (2026-11-10) checked every number against PubMed efetch for all four PMIDs
and against the NCCIH page. It found no blockers and three wording items, all applied:
(1) the Cochrane result now reads "no significant effect" (source: RR 0.78, 0.53-1.15);
(2) `notable_studies` now names the lipid directions (TC, LDL and TG lower, HDL higher) rather than "lower lipids";
(3) the NCCIH fact sheet was added as an `nccih` reference (an allowed source type in `db_integrity_sanity_check.py`).
After the fixes: data_batch check 2 changed / 0 problems; sanity check 0 findings; test file 414 passed.
