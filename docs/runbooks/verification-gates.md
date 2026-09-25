# Verification gates and API verifiers

Reference moved out of `AGENTS.md` so it no longer loads every session. Counts are deliberately
absent — run the script and read its output.

## Data-integrity gates

Run against `scripts/final_db_output` or a fresh `/tmp/pharmaguide_release_build*/`.

| Script | What it gates |
|---|---|
| `scripts/audit_source_of_truth_contract.py matrix\|cleaner\|clinical` | One owner per concept (`scripts/contracts/source_of_truth_matrix.json`), cleaner-first row contract, clinical drift |
| `scripts/audit_contract_sync.py` | Blob-contract emit rates (GREEN/YELLOW/RED) and undeclared blob top-level keys |
| `scripts/audit_raw_to_final.py` | Raw → blob reconciliation with a canary set |
| `scripts/audit_inactive_safety.py` | Banned-in-inactives carry a safety signal; unknown-role counter |
| `scripts/db_integrity_sanity_check.py` | SQLite schema + data validation |
| `scripts/coverage_gate.py`, `scripts/coverage_gate_functional_roles.py` | Quality/coverage thresholds; functional-role coverage |
| `scripts/enrichment_contract_validator.py` | Enrichment output contract |

Contract tests worth knowing: `test_label_fidelity_contract.py`, `test_active_count_reconciliation.py`,
`test_inactive_ingredient_resolver.py`, `test_canonical_id_delivers_markers_emit.py`,
`test_vitamin_a_form_aware_normalization.py` (all under `scripts/tests/`).

## API verifiers (`scripts/api_audit/`, keys from `.env`)

| Script | Verifies |
|---|---|
| `verify_all_citations_content.py` | PMIDs exist **and** the article matches the claimed topic |
| `verify_cui.py` | UMLS CUIs |
| `verify_interactions.py` | RxNorm RXCUIs in interaction rules |
| `verify_unii.py` | FDA UNII + CFR |
| `verify_pubchem.py` | PubChem CID + CAS |
| `verify_clinical_trials.py` | ClinicalTrials.gov NCT IDs |
| `verify_rda_uls.py` | RDA/AI/UL against NASEM DRI tables + USDA FDC |
| `verify_efsa.py` | EU ADI / opinions |
| `fda_weekly_sync.py` | FDA recall tracking (openFDA, RSS, DEA) — see the `fda-weekly-sync` skill |
| `audit_banned_recalled_accuracy.py` | Release gate for banned/recalled data |
| `audit_clinical_evidence_strength.py` | Evidence-strength classification |

Tooling reference: `scripts/api_audit/README.md`.

## Key documents (verify against code before trusting)

`scripts/DATABASE_SCHEMA.md` (every data file) · `scripts/SCORING_ENGINE_SPEC.md` (formulas) ·
`scripts/SCORING_README.md` (scorer implementation) · `scripts/PIPELINE_ARCHITECTURE.md` (stage
contracts) · `scripts/FINAL_EXPORT_SCHEMA_V1.md` (Flutter data contract).
