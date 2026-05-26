# A2 Branded Blend Anchor Slice — 2026-05-26

## Scope

Current post-A.2b corpus still has 33 products in the `A2_branded_blend`
inventory. This slice does **not** make branded blends generically scorable.
It adds an exact-match, evidence-backed curated anchor layer for branded blend
headers whose children are display-only / undisclosed.

## Live-Verified Anchors Added

| Anchor | Products | PMID Evidence | Outcome |
|---|---:|---|---|
| Urox | 1 | PMID 29385990 | anchor eligible |
| Xanthigen | 3 | PMID 19840063 | anchor eligible |
| Metabolaid | 1 | PMID 33810049 | anchor eligible |
| Univestin | 2 | PMID 24611484 | anchor eligible |
| Indolplex / BR-DIM | 4 | PMID 22075942, PMID 28560655 | anchor eligible |

All PMIDs were checked live through PubMed EFetch before adding the data file.

## Guardrails

- Exact alias match only (`name` or `standard_name` after normalization).
- Optional source DB and canonical ID allowlists per anchor.
- Existing IQD child-dose guard still applies.
- New proprietary-blend child-dose guard also applies, so headers do not get
  anchor credit when blend evidence exposes individually dosed child rows.
- Anchor products use the existing `blend_header_anchor` score basis and
  `SCORED_VIA_BLEND_HEADER_ANCHOR` flag, with the existing never-SAFE verdict
  ceiling.

## Simulated Impact On Current Enriched Outputs

11 of 33 A2 products promote to conservative anchor scoring:

| DSLD | Product | Anchor | Simulated Verdict | Score |
|---|---|---|---|---:|
| 251549 | Nature's Way DIM-plus | Indolplex / BR-DIM | POOR | 25.6 |
| 251551 | Nature's Way DIM-plus | Indolplex / BR-DIM | POOR | 25.6 |
| 333910 | Nature's Way DIM-plus | Indolplex / BR-DIM | POOR | 25.6 |
| 333911 | Nature's Way DIM-plus | Indolplex / BR-DIM | POOR | 25.6 |
| 328295 | Life Extension Body Trim and Appetite Control | Metabolaid | POOR | 35.6 |
| 220275 | GNC Mega Men Joint Health | Univestin | POOR | 32.5 |
| 243676 | GNC Women's Joint Health | Univestin | POOR | 32.5 |
| 81811 | Doctor's Best Bladder Support With Urox | Urox | POOR | 22.5 |
| 241286 | Garden of Life FucoThin | Xanthigen | POOR | 26.9 |
| 274270 | Garden of Life fucoTHIN | Xanthigen | POOR | 26.9 |
| 63044 | Garden Of Life FucoThin | Xanthigen | POOR | 25.6 |

The remaining 22 stay `NOT_SCORED` because they are generic opaque blends,
unverified brand descriptors, or out-of-scope categories:

- General proprietary blends: 11
- Superfood / herbal generic blends: 5
- Aloelax: 2
- Seditol: 1 (no PubMed match found for the brand token)
- BioCore Recovery Enzymes: 1 (blend evidence carries individually dosed HUT
  enzyme children; needs enzyme-activity-unit workstream, not header anchor)
- Trisynex: 1
- Herbal Extract Generic: 1

## Data Quality Cleanup

The existing Univestin note in `other_ingredients.json` cited DOI
`10.1186/1472-6882-12-8`, which PubMed resolves to a burdock-root rat study,
not Univestin / joint support. This slice replaces it with the verified
joint-support RCT reference: PMID 24611484 / DOI `10.1089/jmf.2013.0010`.
