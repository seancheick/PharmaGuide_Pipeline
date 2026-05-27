# IQM Identifier Sweep — Master Report

- **Generated:** 2026-05-27T16:05:57.561163+00:00
- **IQM snapshot SHA-256:** `7a68a890b34e2a50a9611f05f0d078c7ed28bd25286480e1e5c9f26e80de3772`
- **Parents audited:** 627 of 627
- **Run duration:** 576.4s

## Per-field verification totals

| Field | verified_clean | mismatched | unresolvable | ambiguous_authority | skipped_intentional_null |
|---|---|---|---|---|---|
| `cui` | 540 | 42 | 0 | 0 | 45 |
| `external_ids.cas` | 619 | 0 | 8 | 0 | 0 |
| `external_ids.inchi_key` | 627 | 0 | 0 | 0 | 0 |
| `external_ids.pubchem_cid` | 627 | 0 | 0 | 0 | 0 |
| `external_ids.unii` | 620 | 7 | 0 | 0 | 0 |
| `rxcui` | 598 | 25 | 4 | 0 | 0 |

## Severity breakdown (non-seed findings)

- **high:** 41
- **medium:** 40
- **low:** 5
- **informational:** 0

## Status breakdown (non-seed findings)

- **mismatched:** 74
- **unresolvable:** 12

## Authority API call counts

- **umls:** 610
- **pubchem:** 55
- **gsrs:** 409
- **rxnorm_in_memory_cache_size:** 283

## Seed findings (pre-known content-verified bugs)

These are pre-populated per spec §'Existing seed findings' so re-runs prove the methodology catches known cases. Two are still pending IQM correction (`coq10`, `5_htp`); the third (`genistein`) is sanity-check only.

- **coq10** / `cui`: resolved_to_disease_or_syndrome (severity=high)
- **5_htp** / `cui`: resolved_to_branded_or_clinical_drug (severity=high)
- **genistein** / `agent2_id (in curated_interactions_v1.json, not IQM)`: previously_corrupted_in_curated_interactions_now_fixed (severity=informational)

## High-severity findings (this run)

- **5_htp** / `cui` (resolved_to_multi_compound_or_combo_product): current=`C5815882`
- **acacia_catechu** / `cui` (no_token_overlap_with_iqm_name): current=`C0949533`
- **alpha_gpc** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5762292`
- **bilberry** / `rxcui` (rxcui_not_found_in_rxnav): current=`11155`
- **borage_seed_oil** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5982013`
- **branched_chain_amino_acids** / `cui` (resolved_to_branded_or_clinical_drug): current=`C0359316`
- **cayenne_pepper** / `cui` (no_token_overlap_with_iqm_name): current=`C0006909`
- **citrus_bergamot** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5762301`
- **cla** / `cui` (no_token_overlap_with_iqm_name): current=`C0055856`
- **coq10** / `cui` (resolved_to_disease_or_syndrome): current=`C1843920`
- **cryptoxanthin** / `rxcui` (rxcui_not_found_in_rxnav): current=`1116063`
- **cynarin** / `cui` (no_token_overlap_with_iqm_name): current=`C0056848`
- **ecdysterones** / `cui` (no_token_overlap_with_iqm_name): current=`C0013495`
- **english_ivy** / `cui` (no_token_overlap_with_iqm_name): current=`C0949841`
- **flower_pollen** / `cui` (resolved_to_branded_or_clinical_drug): current=`C4073752`
- **fluoride** / `cui` (no_token_overlap_with_iqm_name): current=`C0016327`
- **french_oak** / `cui` (no_token_overlap_with_iqm_name): current=`C0330306`
- **gamma_oryzanol** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5979108`
- **goldenseal** / `rxcui` (rxcui_not_found_in_rxnav): current=`253171`
- **gypenosides** / `cui` (no_token_overlap_with_iqm_name): current=`C0905527`
- **hemp_seed_oil** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5777771`
- **horse_chestnut_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0001443`
- **lions_mane** / `cui` (resolved_to_branded_or_clinical_drug): current=`C6011652`
- **lychee_polyphenol** / `cui` (no_token_overlap_with_iqm_name): current=`C1072272`
- **maqui_berry** / `cui` (no_token_overlap_with_iqm_name): current=`C1067051`
- **mastic_gum** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5709624`
- **neem** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5670607`
- **noni** / `cui` (resolved_to_branded_or_clinical_drug): current=`C1814348`
- **olive_fruit_extract** / `cui` (resolved_to_multi_compound_or_combo_product): current=`C6017333`
- **omega_6_fatty_acids** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5918245`
- **phosphatidylinositol** / `cui` (no_token_overlap_with_iqm_name): current=`C0031621`
- **protein** / `cui` (no_token_overlap_with_iqm_name): current=`C0033684`
- **purple_corn_extract** / `cui` (no_token_overlap_with_iqm_name): current=`C1446590`
- **saccharomyces_exiguus** / `cui` (no_token_overlap_with_iqm_name): current=`C1940772`
- **shilajit** / `cui` (resolved_to_branded_or_clinical_drug): current=`C3709449`
- **silicon** / `cui` (no_token_overlap_with_iqm_name): current=`C0037114`
- **split_gill_polypore** / `cui` (no_token_overlap_with_iqm_name): current=`C0319679`
- **sulforaphane** / `rxcui` (rxcui_not_found_in_rxnav): current=`1116060`
- **theacrine** / `cui` (resolved_to_branded_or_clinical_drug): current=`C5778236`
- **turkey_tail** / `cui` (resolved_to_branded_or_clinical_drug): current=`C6011676`
- **white_willow_bark** / `cui` (resolved_to_branded_or_clinical_drug): current=`C0936557`

## Outputs

- `findings.jsonl` — every non-clean finding, one JSON per line, sorted seed→severity→canonical_id
- `queue.csv` — high-severity findings (incl. seeds) ready for clinician review
- `per_parent/<canonical_id>.json` — full audit record per IQM parent with `iqm_snapshot_sha256`
- `_cache/` — raw authority API response snapshots (UMLS / PubChem / GSRS / RxNav)

## Next step

Clinician walks `queue.csv` and authorizes corrections per row. This sweep writes nothing to `scripts/data/`. The follow-up workflow per spec §'Do NOT auto-fix' takes one finding at a time with a failing-test-first guard.
