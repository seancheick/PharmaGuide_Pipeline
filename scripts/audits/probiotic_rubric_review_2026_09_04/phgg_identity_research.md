# PHGG identity research — 2026-09-04

Scope: bounded support for scorer-side PHGG identity handling in the
fiber/digestive formulation module. No new canonical IDs or clinical claims.
This note supports stable recognition of already-curated PHGG material such
as `NHA_SUNFIBER`, `NHA_SUNFIBER_AG`, and
`partially_hydrolyzed_guar_gum`. The existing Sunfiber AG record's copy was
also corrected as described below; no numeric quality rating changed.

## Verified identity points

- Thorne identifies FiberMend's ingredient as Sunfiber, a patented partially hydrolyzed guar gum (PHGG), and contrasts it with non-hydrolyzed guar gum because the hydrolyzed material dissolves without the usual gumminess.
  - https://uk.thorne.com/ingredients/hydrolyzed-guar-gum

- Sunfiber's manufacturer states that PHGG is produced by hydrolyzing guar gum, which greatly decreases viscosity, while plain guar gum is the viscous/gelling material.
  - https://sunfiber.com/partially-hydrolyzed-guar-gum-phgg/
  - https://sunfiber.com/frequently-asked-questions/

- Taiyo's product table and technical sheet independently identify Sunfiber AG
  as **agglomerated** PHGG, not a different plant fiber. This confirms that
  canonical's inclusion without relying on the old registry note's unsupported
  expansion of AG as "agricultural/food-grade". The existing registry note now
  says "agglomerated"; its unsupported FDA GRAS assertion was removed, not
  treated as verified by this scoring-boundary review.
  - https://www.taiyointernational.com/products/
  - https://www.taiyointernational.com/wp-content/uploads/2016/09/SF_Data-Supplement_2015.pdf

- Public literature aligns with that preparation distinction:
  - PMID 16413751 — PHGG described as water-soluble, non-gelling fiber with prebiotic properties.
    - https://pubmed.ncbi.nlm.nih.gov/16413751/
  - PMID 26855665 — randomized placebo-controlled IBS trial describing PHGG as a known prebiotic fiber.
    - https://pubmed.ncbi.nlm.nih.gov/26855665/

## Implication for scorer policy

- PHGG and native guar gum share botanical origin but not the same preparation properties.
- The prior 10-point scorer branch label `viscous_or_gel_fiber` was not truthful for PHGG.
- This change keeps the existing 10-point magnitude for PHGG but gives it a preparation-specific class (`hydrolyzed_guar_fiber`) and renames the remaining generic 10-point branch to the neutral `soluble_fiber`.

## Row-owned signals allowed by this change

- Verified PHGG canonical IDs:
  - `NHA_SUNFIBER`
  - `NHA_SUNFIBER_AG`
  - `partially_hydrolyzed_guar_gum`
- Existing `OI_GUAR_GUM` remains a guar-family compatibility anchor in scorer
  logic only. It is not a new PHGG identity and should gain PHGG credit only
  when the same row carries row-owned PHGG/Sunfiber preparation signals.

- Explicit row-owned preparation signals:
  - `phgg`
  - `partially hydrolyzed guar`
  - `hydrolyzed guar gum`
  - `Guar Gum, Hydrolyzed`

Non-goals:

- no product-title inference
- no sibling-row borrowing
- no generic prebiotic-to-PHGG promotion
- no calibration change to the 10-point PHGG magnitude

## Final regression review

The first shared-text rewrite was rejected in independent review: it could
crash on non-string values and drop existing generic acacia form signals.
The final patch retains the normalized generic text path, keeps PHGG recognition
source-owned, and prevents stale PHGG text from leaking through generic guar
matching. Word boundaries reject `Guarana` and `Guaranteed Fiber` as guar.
The final focused run and independent re-review each passed **22 tests**.
