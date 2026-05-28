# IQM Identifier Sweep — Master Report

- **Generated:** 2026-05-28T15:21:26.052562+00:00
- **IQM snapshot SHA-256:** `57b2748f6784dfe9752e1e9c6e7f11084315b7f57d6048ac18c2064a3303d705`
- **Parents audited:** 116 of 116
- **Run duration:** 371.8s

## Per-field verification totals

| Field | verified_clean | mismatched | unresolvable | ambiguous_authority | skipped_intentional_null |
|---|---|---|---|---|---|
| `cui` | 99 | 2 | 0 | 0 | 15 |
| `external_ids.cas` | 93 | 2 | 21 | 0 | 0 |
| `external_ids.inchi_key` | 116 | 0 | 0 | 0 | 0 |
| `external_ids.pubchem_cid` | 115 | 1 | 0 | 0 | 0 |
| `external_ids.unii` | 110 | 5 | 1 | 0 | 0 |
| `rxcui` | 115 | 0 | 1 | 0 | 0 |

## Severity breakdown (non-seed findings)

- **high:** 2
- **medium:** 29
- **low:** 2
- **informational:** 0

## Status breakdown (non-seed findings)

- **mismatched:** 10
- **unresolvable:** 23

## Authority API call counts

- **umls:** 110
- **pubchem:** 228
- **gsrs:** 95
- **rxnorm_in_memory_cache_size:** 77

## Seed findings (pre-known content-verified bugs)

These are pre-populated per spec §'Existing seed findings' so re-runs prove the methodology catches known cases. Two are still pending IQM correction (`coq10`, `5_htp`); the third (`genistein`) is sanity-check only.

- **coq10** / `cui`: resolved_to_disease_or_syndrome (severity=high)
- **5_htp** / `cui`: resolved_to_branded_or_clinical_drug (severity=high)
- **genistein** / `agent2_id (in curated_interactions_v1.json, not IQM)`: previously_corrupted_in_curated_interactions_now_fixed (severity=informational)

## High-severity findings (this run)

- **ADD_POLYSORBATE_20** / `external_ids.unii` (unii_not_found_in_gsrs): current=`4R0MI3KBZF`
- **ADD_SENNA** / `rxcui` (rxcui_not_found_in_rxnav): current=`237929`

## Outputs

- `findings.jsonl` — every non-clean finding, one JSON per line, sorted seed→severity→canonical_id
- `queue.csv` — high-severity findings (incl. seeds) ready for clinician review
- `per_parent/<canonical_id>.json` — full audit record per IQM parent with `iqm_snapshot_sha256`
- `_cache/` — raw authority API response snapshots (UMLS / PubChem / GSRS / RxNav)

## Next step

Clinician walks `queue.csv` and authorizes corrections per row. This sweep writes nothing to `scripts/data/`. The follow-up workflow per spec §'Do NOT auto-fix' takes one finding at a time with a failing-test-first guard.
