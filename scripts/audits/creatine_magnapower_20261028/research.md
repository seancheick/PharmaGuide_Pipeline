# Creatine MagnaPower composition (2026-10-28)

Entry: `ingredient_quality_map.json` → `creatine_monohydrate` → form `creatine magnesium chelate`
(aliases include `magnapower`, `creatine magnapower`). Agent review; no clinician or Sean review.
Question from PR #279: the chelate also supplies magnesium, and nothing recorded how much.

## Sources (verified 2026-10-28)

| Source | What it says | Applicability |
|---|---|---|
| Albion/Balchem product data sheet 03465 "Creatine MagnaPower (Magnesium Creatine Chelate)", rev. 22-AUG-2024. Third-party upload of the manufacturer document: scribd.com/document/1000407229 (page text read from its text layer). | Guaranteed analysis: magnesium not less than 8.0 %, nitrogen 12.0–15.0 %. Nutritional data per 100 g as-is (lot averages): magnesium 9,033 mg, creatine 50 g. Ingredients: magnesium creatine chelate, citric acid, phosphoric acid. | The manufacturer's own specification for the branded ingredient. Not hosted on balchem.com; Balchem's product page gives no percentage. |
| U.S. Patent 6,114,379, "Bioavailable chelates of creatine and essential metals" (Albion; Wheelwright, Ashmead). patents.google.com/patent/US6114379A | Ligand:metal molar ratio about 1:1 to 3:1, 1:1 preferred for magnesium. Example 1: 50.78 g creatine monohydrate + 14.26 g MgO (with citric and phosphoric acid) → 100 g product, which computes to 8.6 % Mg and 44.6 % creatine. | Label 220208 states "Chelate covered by U.S. Patent 6,114,379". The patent's other worked examples imply 5–7.6 % Mg, so the patent supports the 1:1 design, not one product percentage. |
| Retail labels (Swanson; Trueprotein), from the PR #279 ledger | 400–420 mg Mg per 5 g (8.0–8.4 %). | Consistent with the ≥ 8.0 % guarantee. |
| PubMed: Zajac 2020 (PMID 32998206, full text PMC7600931); Brilla 2003 (PMID 14506619) and Andres 2017 (PMID 28019093), abstracts | Trials and a safety review of the chelate. None of the texts read states its magnesium fraction; Brilla dosed 800 mg Mg + 5 g creatine per day as chelate or as MgO + creatine. | No peer-reviewed composition figure found. The full texts of Brilla and Andres were not read. |

Consistency check: the PDS typical values give a Mg:creatine molar ratio of (9.033/24.305)/(50/131.13) = 0.975, about 1:1, matching the patent's preferred design.

Not used: CAS 1430842-65-1 (printed on the PDS) has no PubChem record and CAS Common Chemistry needs
authentication, so it is unverified and was not added as an identifier.

## Decision and change

- Identity: unchanged. MagnaPower is a distinct creatine compound and stays a separate form under the
  creatine parent (`standard_name` "Creatine"), not creatine monohydrate.
- Composition: recorded in the form's existing `notes` field (the manufacturer guarantee, typical
  values, patent ratio, and that a label amount may be chelate mass). The run-together typo
  "measure99%absolute F" was fixed in the same sentence. No numeric composition field was added:
  that would be a new semantic owner (Sean decides), and no consumer would read it.
- Magnesium link: no mirror form under `magnesium` (the `cross_ref` pattern used for magnesium
  ascorbate/taurate). No corpus label has a magnesium row whose form names the chelate (all 10
  labels list a separate unformed "Magnesium" total), and a mirror form needs a magnesium bio_score
  that no reviewed evidence supports.
- No automatic partition: a label's magnesium total is not split into chelate and food magnesium.

## Verification

- Raw corpus census (`PharmaGuide_Datasets/staging/brands`): only the 10 GNC Re-Built Mass XP labels
  mention the chelate (211339, 220140, 220208, 220238, 220239, 244276, 244288, 244298, 244301, 83268).
- Production Clean → Enrich on 220208 with the old vs new notes: enriched output identical apart from
  the two `notes` copies and run timestamps. No score, amount, route or safety field moves.
- Tests: `scripts/tests/test_creatine_magnapower_composition.py` (fixture: raw DSLD 220208).

## Leads (not applied; need their owners)

1. Magnesium UL (PR #279 / Sean): 2.5 g of chelate supplies at least 200 mg supplemental Mg
   (≥ 8.0 %), typically about 226 mg (9.03 %). If the label's 2.5 g instead states creatine content,
   the chelate would be about 5 g and about 450 mg Mg. Either reading leaves the food share of the
   490–600 mg label totals unstated, so "unresolved + review" stands.
2. Creatine dose (`/pg-scoring-change` owner): the chelate is about 50 % creatine as-is. If 2.5 g is
   chelate mass, it delivers about 1.25 g creatine. The enriched row carries 2.5 g under the
   creatine parent; how the Dose pillar credits it was not traced here.
3. Dormant matcher case: a row "Magnesium" whose form text is "Creatine MagnaPower" enriches to
   magnesium with `matched_form` None. A form of "Magnesium Creatine Chelate" gives
   `magnesium (unspecified)`. No corpus label has either today.

## Independent retained-source check (Codex, 2026-10-28)

Recovered the original two gzip-compressed Scribd JSONP page text layers from the previous
agent's temporary scratchpad and retained exact bytes durably at
`/Users/seancheick/pg_quality/magnesium_ul_20261028/magnapower_source_receipts/`.
The document itself identifies Albion/Balchem, product 03465, Creatine MagnaPower (Magnesium
Creatine Chelate), and revision 22-AUG-2024. Page 1's guaranteed analysis states magnesium
not less than 8.0%; page 2's per-100-g nutritional table states magnesium 9,033 mg and creatine
50 g, with the disclaimer that nutritional values are averaged sampled-lot results on an as-is
basis and subject to change. These are manufacturer document claims, not a measured partition
of the DSLD labels. The original source was the third-party mirror
<https://www.scribd.com/document/1000407229>; no official-host retrieval is claimed.

Exact retained-source SHA-256:

- `pds_1-54422b5676.jsonp`: `b2065c79fc4ad2661dc2be97ad39495516596ed7cf76d23fabbc3de0d73940d7`
- `pds_2-3610bfa9f5.jsonp`: `d0859a2f9c9cbd6c7a005ddfdafca1caf572115dcaba4e8e8be6a91c68dcf22a`

This independent content inspection supports the existing notes; no numerical, identity,
clinical-credit, or automatic-partition change was made during takeover. Official hosting
was not required to inspect the retained manufacturer-authored document.
