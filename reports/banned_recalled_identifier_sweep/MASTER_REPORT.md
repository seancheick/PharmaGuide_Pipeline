# IQM Identifier Sweep — Master Report

- **Generated:** 2026-05-28T15:02:10.154923+00:00
- **IQM snapshot SHA-256:** `09a9ea3e14378676284d2f9a2fa648aee4ea0406b64f7c06d7bad9fecf46c2eb`
- **Parents audited:** 156 of 156
- **Run duration:** 417.3s

## Per-field verification totals

| Field | verified_clean | mismatched | unresolvable | ambiguous_authority | skipped_intentional_null |
|---|---|---|---|---|---|
| `cui` | 105 | 2 | 1 | 0 | 48 |
| `external_ids.cas` | 156 | 0 | 0 | 0 | 0 |
| `external_ids.inchi_key` | 156 | 0 | 0 | 0 | 0 |
| `external_ids.pubchem_cid` | 156 | 0 | 0 | 0 | 0 |
| `external_ids.unii` | 148 | 8 | 0 | 0 | 0 |
| `rxcui` | 155 | 0 | 1 | 0 | 0 |

## Severity breakdown (non-seed findings)

- **high:** 3
- **medium:** 8
- **low:** 1
- **informational:** 0

## Status breakdown (non-seed findings)

- **mismatched:** 10
- **unresolvable:** 2

## Authority API call counts

- **umls:** 106
- **pubchem:** 12
- **gsrs:** 101
- **rxnorm_in_memory_cache_size:** 46

## Seed findings (pre-known content-verified bugs)

These are pre-populated per spec §'Existing seed findings' so re-runs prove the methodology catches known cases. Two are still pending IQM correction (`coq10`, `5_htp`); the third (`genistein`) is sanity-check only.

- **coq10** / `cui`: resolved_to_disease_or_syndrome (severity=high)
- **5_htp** / `cui`: resolved_to_branded_or_clinical_drug (severity=high)
- **genistein** / `agent2_id (in curated_interactions_v1.json, not IQM)`: previously_corrupted_in_curated_interactions_now_fixed (severity=informational)

## High-severity findings (this run)

- **ADD_COLLOIDAL_SILVER** / `rxcui` (rxcui_not_found_in_rxnav): current=`9785`
- **BANNED_DHEA** / `cui` (cui_not_found_in_umls): current=`C0011260`
- **BANNED_IGF1** / `cui` (resolved_to_disease_or_syndrome): current=`C5674892`

## Outputs

- `findings.jsonl` — every non-clean finding, one JSON per line, sorted seed→severity→canonical_id
- `queue.csv` — high-severity findings (incl. seeds) ready for clinician review
- `per_parent/<canonical_id>.json` — full audit record per IQM parent with `iqm_snapshot_sha256`
- `_cache/` — raw authority API response snapshots (UMLS / PubChem / GSRS / RxNav)

## Next step

Clinician walks `queue.csv` and authorizes corrections per row. This sweep writes nothing to `scripts/data/`. The follow-up workflow per spec §'Do NOT auto-fix' takes one finding at a time with a failing-test-first guard.
