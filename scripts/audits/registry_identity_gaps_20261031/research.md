# Registry identity gaps — research receipts (October 31, 2026)

Agent research (Claude); no clinician review is claimed. One receipt per entry.

## Batch 1 — `ingredient_quality_map.json::l_cystine` (added)

| Field | Source and result (verified 2026-10-31) |
|---|---|
| Chemistry | PubChem (`verify_pubchem.py --search "L-cystine"`): CID 67678, CAS 56-89-3, C6H12N2O4S2, IUPAC (2R)-2-amino-3-[[(2R)-2-amino-2-carboxyethyl]disulfanyl]propanoic acid, InChIKey LEVWYRKDKASIDU-IMJSIDKUSA-N. |
| UNII | GSRS API `substances(48TCX9A1VT)`: CYSTINE, chemical, stereochemistry ABSOLUTE; codes CAS 56-89-3, PubChem 67678, RxCUI 3036. D- and DL-cystine are separate GSRS names. |
| RxCUI | RxNav `rxcui.json?name=cystine`: 3036. |
| CUI | UMLS (`verify_cui.py --cui C0010682`): "cystine", Amino Acid / Pharmacologic Substance, status R. |
| Distinctness | L-cysteine is UNII K848JZ4886 (IQM `l_cysteine`); NAC is IQM `nac`. Both already carry `negative_match_terms: ["cystine"]`; `l_cystine` carries `["acetyl", "cysteine"]` so the GNC 78327 misprint "N-Acetyl-L-Cystine" stays unresolved. |
| Absorption | No reviewed source establishes a human absolute fraction for supplemental L-cystine. `bio_score` 5 is the existing unknown-absorption amino acid anchor (`l_asparagine`, `l_aspartic_acid`); no clinical or bioavailability claim is written. |
| Labels | Solgar 213846 (corrected printed row "L-Cystine"), Thorne 328818 and 337851, Garden of Life 297638. |

## Batch 2 — `ingredient_quality_map.json::ginseng` form `american ginseng (panax quinquefolius)` (changed)

| Field | Source and result |
|---|---|
| Owner | IQM `ginseng` holds the species form "american ginseng (panax quinquefolius)" (bio 9). Sean's October 29 attested Dose scopes key American root, rhizome and leaf preparations to canonical `ginseng` (`test_attested_botanical_dose_scopes.py`, `test_exact_approved_botanical_dose_scopes.py`), so moving rows to `botanical_ingredients::american_ginseng` would orphan approved scopes. Not done. |
| Defect | Rows whose declared form prints the Panax quinquefolius binomial ("Panax quinquefolius Rhizome Extract", "... Root Extract") fell to "ginseng (unspecified)" or no form: 330196–330199 (multi-part rhizome+root) and 329914 (rhizome). 310646–310649 already matched through the reviewed clue "panax quinquefolium l. rhizome extract". |
| Change | Two parent-scoped `source_form_aliases` on that form: "panax quinquefolius rhizome extract", "panax quinquefolius root extract". Per `GLOSSARY.md`, these act only after the parent is established and are absent from global identity indexes, so cleaner identity and the botanical `american_ginseng` owner are untouched. |
| Identity | The label's own Latin binomial names the species (identity by organism). Rhizome and root are both Panax quinquefolius material; no part-specific claim is added and the leaf row (312858) is not given the species form. |
| Not changed | Interaction subjects: `american_ginseng` already twins to IQM `ginseng` (`identity/interaction.py`). Evidence: no Panax ginseng record applies (replay). |

## Batch 3 — enricher recognition kept the cleaner's part-matched botanical identity (code)

| Field | Finding and result |
|---|---|
| Two owners | Cleaner (`EnhancedDSLDNormalizer._resolve_canonical_identity`) resolves "Butcher's Broom Leaf Extract" / "Leaf, Stem Extract" to part-less `standardized_botanicals::butcher_s_broom`. Enricher fast-path recognition (`SupplementEnricherV3._is_recognized_non_scorable`) indexes normalized names to the first-written record; `botanical_ingredients::butchers_broom_root` carries the part-less alias "butcher's broom" and is indexed first, so `_restamp_recognized_non_scorable_identity` overwrote the cleaner's identity with a root entry for a leaf/stem row. |
| Change | In `_restamp_recognized_non_scorable_identity`, when both identities are botanical, they differ, and the recognized record names a plant part the row did not declare (`_names_undeclared_plant_part`), the row keeps its cleaner botanical identity. Organs are compared, not spellings (leaves = leaf, berry = fruit). |
| Not changed | Part-less rows (251524 "Butcher's Broom", plantPart none) and root rows keep `butchers_broom_root`. No data file changed; no part-specific credit added (`butcher_s_broom` and the root entry both lack qualifying studies). |
| Blast radius | Census over 2,761 cleaned botanical rows with a declared plantPart: 0 rows change identity outside the butcher's broom leaf/stem rows (ginkgo leaves and schisandra fruit false positives were removed by the organ normalization before commit). |

## Bamboo — no data change (recorded honest state)

- Sean's October 29 exact Dose scope keys bamboo stem/leaf extract to IQM `silica` form "bamboo silica" (literature record `bamboo_stem_leaf_extract`, pinned by `test_exact_approved_botanical_dose_scopes.py`). Moving bamboo to a new organism owner would orphan that approved scope.
- GSRS has only species-specific bamboo substances (for example Bambusa vulgaris leaf, UNII EMY54R518C; Phyllostachys edulis whole) and no generic "bamboo" substance. Most labels print no species, so a generic bamboo organism entry would be identity by name. Not created.
- Honest state: the cleaner leaves organism-named bamboo rows unmapped under the multi-part organism rule (a constituent such as silica establishes no organism identity), while the IQD row uses the approved `silica` bamboo form. Decision for Sean if an organism owner is wanted: a species-specific entry needs a labelled species.

## Sensoril — no data change

- Already registered: IQM `ashwagandha` form "sensoril ashwagandha" (bio 11) and `backed_clinical_studies::BRAND_SENSORIL` (PMIDs 27647541, 38732539) supply its Formulation and Evidence; the brand is not unmapped at the IQM layer.
- A KSM-66-style `standardized_botanicals` branded_extract bonus entry was not added. PubMed abstracts of 27647541 and 38732539 describe a standardized aqueous root-plus-leaf extract but print no standardization percentage, and BRAND_SENSORIL notes record unresolved preparation overlap. A bonus would be unsupported Formulation credit.
- Finding, not fixed here: the Sensoril IQM form carries generic aliases ("leaf and root extract", "low odor ashwagandha", "high withanolide ashwagandha", "patented ashwagandha", "bioactive ashwagandha", "stress-relief ashwagandha"). Probe: unbranded "Ashwagandha Leaf, Root Extract" resolves to the Sensoril form, so an unbranded label can borrow the brand form's bio 11.
