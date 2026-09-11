# Source-form identity review — 2026-09-11

Scope: inositol declared from inositol niacinate, and tributyrin. No new
ingredient parents; no new efficacy or absorption assertions.

Live PubChem verification via `verify_pubchem.py --cid ... --no-cache`:

- CID 3720: inositol hexanicotinate, CAS 6556-11-2, C42H30N6O12.
  Returned synonyms include inositol nicotinate and inositol niacinate.
  https://pubchem.ncbi.nlm.nih.gov/compound/3720
- CID 6050: tributyrin, CAS 60-01-5, C15H26O6. Returned synonyms include
  glyceryl tributyrate and glycerol tributyrate.
  https://pubchem.ncbi.nlm.nih.gov/compound/6050
- NLM MeSH independently groups inositol niacinate/nicotinate/hexanicotinate:
  https://www.ncbi.nlm.nih.gov/mesh/67005193
- NCI identifies tributyrin as a triglyceride of butyric acid:
  https://www.cancer.gov/publications/dictionaries/cancer-drug/def/tributyrin
- Manufacturer identifies CoreBiome as tributyrin. This establishes brand
  identity only, not proof of superior absorption or efficacy:
  https://compoundsolutions.com/ingredients/corebiome/

Database duplicate check: niacin already owns the chemical's global aliases.
Inositol has only myo and D-chiro forms; the declared source must therefore
be parent-scoped, not a competing global chemical identity. Tributyrin aliases
currently live incorrectly on unspecified butyric acid and must move together.

Scoring policy: use the existing conservative unassessed allowance of 5,
not the unrelated D-chiro or free-acid absorption estimate. Absorption remains
unknown. This allowance is not a measured bioavailability percentage. Preserve
the label's declared nutrient/preparation quantity; do not infer released
inositol, niacin, or butyric-acid equivalents. Clinical qualification remains
separate from chemical-identity verification.

## Verification

Mapping baseline: d0c6f324 (the subsequent 6fdb76f3 console-only commit does not
change either the enricher or IQM data). Scanned all 15,415 local cleaned records; re-enriched the
1,065 records mentioning inositol, butyrate/tributyrin, or the existing Capsimax
source-preparation family with both baseline source/data and corrected source/data.
56 products changed: 55 inositol source mappings and one tributyrin mapping.
No new enrichment errors; no other form-identity changes. Recomputed v4 score
deltas for the changed products ranged from -2 to 0 points. This is an impacted
cohort comparison, not a full final-export/catalog release proof.

Seven retained private diagnostic drafts also re-enriched without errors.
Only the expected inositol (1 mg) and tributyrin (300 mg) rows changed.
Their original preview files were not overwritten or represented as approved.
Native and submission route regressions run the shared cleaner, enricher and
v4 artifact assembler and assert matching row assessments, score and pillars.

Final source backstop: 14,376 passed, 66 skipped; seven loopback-server tests
could not bind sockets in the filesystem/network sandbox (four failures, three
setup errors). Re-running both affected files with local-server access yielded
31 passed, including all seven blocked checks. No source test failure remains.
IQM integrity validator returned no findings. Release preflight still refuses
`data_vs_enriched` and `scored_vs_dist` staleness; no bypass or catalog publication.
