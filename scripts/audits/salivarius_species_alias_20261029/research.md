# Salivarius species-name aliases — receipts (2026-10-29, agent review)

Entry: `ingredient_quality_map.json` → `lactobacillus_salivarius`. Four aliases move from form
`lactobacillus salivarius ha-118` (bio_score 7) to `generic lactobacillus salivarius` (bio_score 6).
Before the move, a species-only label ("Ligilactobacillus salivarius") got the HA-118 strain form.

| Alias | Receipt | Verdict |
|---|---|---|
| ligilactobacillus salivarius | Zheng et al. 2020, IJSEM 70(4) "A taxonomic note on the genus Lactobacillus…" (PMID 32293557, title checked live via PubMed esummary 2026-10-29) renamed the species *Lactobacillus salivarius* to *Ligilactobacillus salivarius*. GSRS UNII 7A4S6N2EG2 (the parent's own `external_ids.unii`, checked live 2026-10-29) is named "Ligilactobacillus salivarius". The name carries no strain designation. | Species → generic form |
| ligilactobacillus salivarius supplement | Same as above, plus a generic product-descriptor suffix. | Species → generic form |
| lactobacillus salivarius strain | The word "strain" names no strain; there is no designation such as HA-118. | Species → generic form |
| lactobacillus salivarius strain supplement | Same. | Species → generic form |

Siblings were checked by scanning every strain-coded probiotic IQM form for species-only aliases. The only other hit, `bacillus_coagulans` MTCC 5856 ← "LactoSpore", is that strain's brand and is unaffected. Strain-coded salivarius names in `clinically_relevant_strains.json` and `backed_clinical_studies.json` (SD-LS1-IT, Ls-33) are unaffected.
