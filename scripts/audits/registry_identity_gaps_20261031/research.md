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
