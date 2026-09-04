# Exact probiotic identity aliases — 2026-09-03

Scope: repair exact label spellings rejected by the independent clinical-strain
identity gate. Each existing registry identity was checked individually against
the primary sources below. These are identity checks, not new efficacy, dose,
safety, or clinician-approval claims. No clinical references, review status,
benchmarks, evidence levels, or existing aliases were changed.

The registry gained 26 exact aliases across 16 existing entries. Matching still
requires whole-name/alias equality after existing text normalization and removal
of punctuation; it does not infer identity from a shared species or partial code.

## First bounded corpus batch: 16 aliases, seven identities

| Registry identity | Added exact aliases | Primary identity verification |
| --- | --- | --- |
| STRAIN_LGG | `Lactobacillus rhamnosus LGG`; `L. rhamnosus LGG`; `L. rhamnosus GG, LGG` | [Novonesis LGG](https://www.novonesis.com/en/biosolutions/human-health/l-rhamnosus-lgg) identifies LGG as the rhamnosus strain and describes its taxonomic renaming. [Novonesis respiratory-support page](https://www.novonesis.com/en/biosolutions/human-health/dietary-supplements/immune-health/upper-respiratory-support) also uses the older Lactobacillus rhamnosus LGG name. |
| STRAIN_LACTIS_BB12 | `Bifidobacterium animalis lactis BB-12`; `Bifidobacterium animalis subsp. lactis BB-12` | [Novonesis BB-12](https://www.novonesis.com/en/biosolutions/human-health/b-lactis-bb-12) identifies animalis subspecies lactis BB-12 and explicitly distinguishes taxonomic-name changes from the unchanged strain. |
| STRAIN_ACIDOPHILUS_NCFM | `HOWARU Lactobacillus acidophilus NCFM`; `HOWARU L. acidophilus NCFM` | [IFF NCFM](https://www.iff.com/health-sciences/our-products/howaru-ncfm/) pairs the HOWARU brand with the full acidophilus NCFM identity. |
| STRAIN_LACTIS_BI07 | `Bifidobacterium animalis lactis Bi-07`; `B. animalis lactis Bi-07` | [IFF Bi-07](https://www.iff.com/health-sciences/our-products/howaru-bi-07/) uses Bifidobacterium lactis Bi-07. [IFF's 2025-10-31 article](https://www.iff.com/media/stories/exploring-the-microbiome-the-key-to-unlocking-your-health-potential/) uses animalis subsp. lactis Bi-07 for that same named strain. |
| STRAIN_LACTIS_BL04 | `Bifidobacterium animalis lactis Bl-04`; `B. animalis lactis Bl-04`; `Bifidobacterium lactis strain Bl-04` | [IFF Bl-04](https://www.iff.com/health-sciences/our-products/howaru-bl-04/) identifies Bifidobacterium lactis Bl-04. [IFF's 2025-10-31 article](https://www.iff.com/media/stories/exploring-the-microbiome-the-key-to-unlocking-your-health-potential/) also uses the animalis subsp. lactis name. The literal word `strain` does not change this exact species/code pairing. |
| STRAIN_LACTIS_HN019 | `Bifidobacterium lactis strain HN019`; `HOWARU Bifidobacterium animalis lactis HN019`; `HOWARU B. lactis HN019` | [IFF HN019](https://www.iff.com/health-sciences/our-products/howaru-hn019/) identifies HOWARU Bifidobacterium lactis HN019. The registry already includes the full animalis lactis HN019 identity; additions retain the exact code and add the verified brand or the literal word `strain`. |
| STRAIN_PARACASEI_LPC37 | `Lactobacillus paracasei strain Lpc-37` | [IFF Lpc-37](https://www.iff.com/health-sciences/our-products/howaru-lpc-37/) identifies the paracasei Lpc-37 strain; the older Lactobacillus spelling also appears in [IFF's 2025-10-31 article](https://www.iff.com/media/stories/exploring-the-microbiome-the-key-to-unlocking-your-health-potential/). |

## Final bounded corpus batch: 10 aliases, nine identities

| Registry identity | Added exact aliases | Primary identity verification |
| --- | --- | --- |
| STRAIN_RHAMNOSUS_HN001 | `HOWARU L. rhamnosus HN001`; `HOWARU Lactobacillus rhamnosus HN001` | [IFF HN001](https://www.iff.com/health-sciences/our-products/howaru-hn001/) identifies HOWARU Lacticaseibacillus rhamnosus HN001. Both genus spellings were already paired in the existing registry; these aliases retain the exact species/code while adding the verified brand. |
| STRAIN_K12 | `BLIS K12 S. salivarius K12` | [BLIS Technologies K12](https://blis.co.nz/blis-k12/) explicitly identifies BLIS K12 as Streptococcus salivarius K12. |
| STRAIN_M18 | `BLIS M18 S. salivarius M18` | [Australian TGA compositional guideline](https://www.tga.gov.au/resources/resources/compositional-guidelines/streptococcus-salivarius-m18), dated 2019-08-19, lists BLIS M18 and Streptococcus salivarius M18 as synonyms. |
| STRAIN_COAGULANS_MTCC5856 | `Lactospore Bacillus coagulans MTCC5856` | [LactoSpore manufacturer](https://lactospore.com/) explicitly pairs the trade name and MTCC 5856. [Health Canada](https://www.canada.ca/en/health-canada/services/food-nutrition/genetically-modified-foods-other-novel-foods/approved-products/lactospore/document.html) independently describes the same identity. |
| STRAIN_PLANTARUM_299V | `Lactobacillus plantarum Lp299v` | [Probi LP299V](https://www.probi.com/about-us/lp299v-probiotic-strain/) identifies LP299V as plantarum 299v and explicitly gives the former Lactobacillus name. Case-only `LP299v` needs no second alias. |
| STRAIN_PLANTARUM_HEAL9 | `Lactobacillus plantarum DSM 15312` | [Probi ClinBac booklet](https://www.probi.com/media/luqcopej/probi_booklet_selectedstudies_clinbac.pdf), page 12, explicitly pairs HEAL9 with DSM 15312. The rendered strain panel was visually inspected to confirm the number belongs to this strain. |
| STRAIN_PARACASEI_8700 | `Lactobacillus paracasei DSM 13434` | [Probi ClinBac booklet](https://www.probi.com/media/luqcopej/probi_booklet_selectedstudies_clinbac.pdf), page 12, explicitly pairs paracasei 8700:2 with DSM 13434. This is separate from HEAL9/DSM 15312. |
| STRAIN_CASEI_431 | `L. paracasei, L. CASEI 431` | [Novonesis L. CASEI 431](https://www.novonesis.com/en/biosolutions/human-health/dietary-supplements/l-casei-431) uses this exact paired species/trade-code wording. |
| STRAIN_LACTIS_UABla12 | `Bifidobacterium animalis lactis UABla-12` | [FDA GRN 872 submission](https://www.fda.gov/media/135325/download), section 2.1, identifies UAS Labs' animalis subspecies lactis UABla-12. This maps to its own existing signed registry entry, not BB-12; its existing weak support classification remains unchanged. |

## Verification and bounded impact

- First batch: 16 failing alias cases before the data changes. Manifest-selected
  read-only corpus check: 58 files, 15,415 products; 99 rows restored across 74
  products, independently eligible clinical rows 638 → 737.
- Final batch: 11 failing spelling cases for 10 distinct aliases, then all 84
  native provenance tests passed. The enumerated remaining 22 rows comprise 20
  confirmed aliases and the two unresolved rows below. Thus, on those previously
  enriched rows, both alias batches restore 119 rows and yield 757 independently
  eligible rows. These are consumer-gate comparisons, not a fresh pipeline score
  diff or a claim about the final producer-recollected corpus.
- Remaining previously signed exclusions: 284 observed species-only/different-code
  rows (generic acidophilus and CUL60/CUL21, generic coagulans, generic cerevisiae),
  plus the two unresolved reuteri rows. Do not label all 286 as proven wrong-strain
  mappings: the two unresolved identities lack equivalence evidence.
- Producer/export regression: four wrong mappings failed first (species-only
  acidophilus, acidophilus CUL60, wrong-genus rhamnosus GG, reuteri 1E1).
  The shared exact predicate now prevents those candidates from being emitted,
  while preserving total label counts, CFU amounts and disclosure credit.
- Final focused verification: 159 tests passed via `scripts/test.sh fast` across
  native provenance, research approval, CFU provenance, confidence and AFU tests.
  No full suite or generated corpus writes were performed in this subtask.

## Unresolved identity queue — no aliases added

| Label identity | Existing emitted candidate | Products | Disposition |
| --- | --- | --- | --- |
| `L. reuteri 1E1` | STRAIN_REUTERI_DSM17938 | 332922; 333915 | No primary identity-equivalence evidence found connecting 1E1 to DSM 17938. The [manufacturer's 1E1 product description](https://rightremedies.in/product/unicflora-rt/) identifies 1E1 as such, not DSM 17938. Preserve the label organism and disclosed dose, but emit no candidate research badge or independent clinical benchmark from DSM 17938. |

For the final pipeline audit, rerun `_collect_probiotic_data` using the current
registry before scoring/export. Reusing old `clinical_strains` would test only
the consumer filter and miss changes to producer identity/status and app badges.
