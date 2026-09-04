# Generic dried-fermentate ownership — 2026-09-04

This is an identity/citation correction, not a new efficacy assessment, form
rating, or clinical sign-off. It continues the earlier EpiCor alias audit; that
audit correctly left generic names held until their separate owners were reviewed.

## Source and registry evidence

The manifest-owned cleaned Airborne labels 178352, 178355, 180206, 180345,
202226, 242946, 64269, 64271, 64273 and 69611 declare **dried Yeast Fermentate**,
500 mg, with no named branded preparation. Examples are NIH DSLD labels
[178352](https://api.ods.od.nih.gov/dsld/s3/pdf/178352.pdf) and
[242946](https://api.ods.od.nih.gov/dsld/s3/pdf/242946.pdf). Their cleaned rows
retain ingredientId 151706, no UNII, and empty forms. The nearby yeast taxonomy
does not turn the fermentation preparation into a live organism.

The existing `NHA_YEAST_FERMENTATE_DRIED` record explicitly owns generic dried
fermentate identity. Two of its exact aliases were also in the broader IQM
`yeast_fermentate` form. That cross-registry disagreement makes the exact-label
resolver correctly refuse the name. The correction removes only those duplicate
IQM aliases; the existing, narrower NHA record remains the exact-name owner.
No generic-to-branded equivalence, registry precedence exception, or new chemical
identifier is added. Historical broader IQM aliases outside those two strings
are not endorsed by this bounded correction.

The manufacturer's [EpiCor description](https://www.cargill.com/food-beverage/emea/specialized-nutrition/epicor-postbiotic-ingredient)
describes a proprietary dried fermentation preparation. It does not establish
that an unnamed dried fermentate is EpiCor. Exact EpiCor labels retain their
separate `epicor` owner; generic labels gain no EpiCor clinical/formulation credit.

## Removed ghost citation

NCBI efetch on 2026-09-04, through the existing
`verify_all_citations_content.fetch_articles` verifier, returned
[PMID 19298191](https://pubmed.ncbi.nlm.nih.gov/19298191/) as *Effects of dietary
Spirulina on vascular reactivity*. Its abstract concerns Spirulina, rat aortic
reactivity and preliminary human lipid/blood-pressure observations—not yeast
fermentate or respiratory infections. PubMed's public record independently
confirms the title and topic. The generic IQM form's EpiCor/cold-and-flu claim
and this citation must be removed, not replaced with an unreviewed study.

## Acceptance boundary

- Exact generic dried names resolve to the existing NHA owner with the original
  500 mg, source name/path/forms, and required-active coverage intact.
- No live-organism identity, CFU, EpiCor brand, or clinical match is inferred.
- Unknown/ambiguous extract labels still fail readiness; use a genuinely unknown
  preparation as their fixture once these verified names are no longer unknown.
- IQM numeric ratings and all pillar weights stay unchanged.
- Targeted and whole-corpus replay must measure the actual score/readiness effect.
