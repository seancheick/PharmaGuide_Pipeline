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
