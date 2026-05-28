# IQM Identifier Sweep — Master Report

- **Generated:** 2026-05-28T18:50:11.703732+00:00
- **IQM snapshot SHA-256:** `420cd8652cd47b374102e6833e10dc2acf54e82e28be1a0e8d67e479a1209d79`
- **Parents audited:** 691 of 691
- **Run duration:** 1753.1s

## Per-field verification totals

| Field | verified_clean | mismatched | unresolvable | ambiguous_authority | skipped_intentional_null |
|---|---|---|---|---|---|
| `cui` | 388 | 49 | 243 | 7 | 4 |
| `external_ids.cas` | 683 | 5 | 3 | 0 | 0 |
| `external_ids.inchi_key` | 691 | 0 | 0 | 0 | 0 |
| `external_ids.pubchem_cid` | 687 | 4 | 0 | 0 | 0 |
| `external_ids.unii` | 650 | 41 | 0 | 0 | 0 |
| `rxcui` | 677 | 13 | 1 | 0 | 0 |

## Severity breakdown (non-seed findings)

- **high:** 14
- **medium:** 66
- **low:** 36
- **informational:** 0

## Status breakdown (non-seed findings)

- **ambiguous_authority:** 7
- **mismatched:** 112
- **unresolvable:** 247

## Authority API call counts

- **umls:** 1612
- **pubchem:** 451
- **gsrs:** 263
- **rxnorm_in_memory_cache_size:** 212

## Seed findings (pre-known content-verified bugs)

These are pre-populated per spec §'Existing seed findings' so re-runs prove the methodology catches known cases. Two are still pending IQM correction (`coq10`, `5_htp`); the third (`genistein`) is sanity-check only.

- **coq10** / `cui`: resolved_to_disease_or_syndrome (severity=high)
- **5_htp** / `cui`: resolved_to_branded_or_clinical_drug (severity=high)
- **genistein** / `agent2_id (in curated_interactions_v1.json, not IQM)`: previously_corrupted_in_curated_interactions_now_fixed (severity=informational)

## High-severity findings (this run)

- **NHA_FLAVANOLS** / `cui` (no_token_overlap_with_iqm_name): current=`C2348678`
- **NHA_FRUIT_VEG_POWDERS** / `cui` (no_token_overlap_with_iqm_name): current=`C1145672`
- **NHA_GLYCOSAPONINS** / `cui` (no_token_overlap_with_iqm_name): current=`C0036189`
- **NHA_LACTOTRIPEPTIDES** / `cui` (no_token_overlap_with_iqm_name): current=`C0063506`
- **NHA_POLYGLYCERYL_ESTER** / `cui` (no_token_overlap_with_iqm_name): current=`C0982350`
- **NHA_VEGETABLE_FRUIT_JUICE_COLORS** / `cui` (resolved_to_multi_compound_or_combo_product): current=`C4042943`
- **OI_CORN_PROTEIN** / `cui` (no_token_overlap_with_iqm_name): current=`C0043458`
- **PII_BRAND_COMPLEX_DESCRIPTOR** / `cui` (no_token_overlap_with_iqm_name): current=`C1269100`
- **PII_CANOLA_SOURCE_DESCRIPTOR** / `cui` (no_token_overlap_with_iqm_name): current=`C5703431`
- **PII_LACTOSE_MONOHYDRATE** / `cui` (resolved_to_disease_or_syndrome): current=`C0022951`
- **PII_MICA_COLORANT** / `cui` (resolved_to_disease_or_syndrome): current=`C0700319`
- **PII_PITUITARY_TISSUE** / `cui` (resolved_to_disease_or_syndrome): current=`C0032002`
- **PII_POLYVINYL_ALCOHOL** / `rxcui` (rxcui_not_found_in_rxnav): current=`8570`
- **PII_SUNFLOWER_SOURCE_DESCRIPTOR** / `cui` (no_token_overlap_with_iqm_name): current=`C0018874`

## Outputs

- `findings.jsonl` — every non-clean finding, one JSON per line, sorted seed→severity→canonical_id
- `queue.csv` — high-severity findings (incl. seeds) ready for clinician review
- `per_parent/<canonical_id>.json` — full audit record per IQM parent with `iqm_snapshot_sha256`
- `_cache/` — raw authority API response snapshots (UMLS / PubChem / GSRS / RxNav)

## Next step

Clinician walks `queue.csv` and authorizes corrections per row. This sweep writes nothing to `scripts/data/`. The follow-up workflow per spec §'Do NOT auto-fix' takes one finding at a time with a failing-test-first guard.
