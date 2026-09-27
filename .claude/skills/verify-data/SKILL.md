---
name: verify-data
description: Run API verification scripts against data files to catch hallucinated identifiers (PMIDs, CUIs, UNIIs, etc.)
---

# /verify-data — Clinical Data Verification

Run the PharmaGuide API verification suite against data files. Use this BEFORE committing any data file changes.

## Usage

- `/verify-data` — run all verification scripts
- `/verify-data pmid` — verify PubMed citations only
- `/verify-data cui` — verify UMLS CUIs only
- `/verify-data interactions` — verify interaction RXCUIs + CUIs
- `/verify-data unii` — verify FDA UNIIs only

## Procedure

1. Check that `.env` exists at repo root with API keys (UMLS_API_KEY, PUBMED_API_KEY, OPENFDA_API_KEY)
2. Run the appropriate verification script(s) based on the argument
3. Report results clearly — any FAIL or MISMATCH is a blocker
4. Do NOT commit data changes until all verifications pass

## Script Map

| Argument | Script | What it checks |
|----------|--------|---------------|
| `pmid` | `scripts/api_audit/verify_all_citations_content.py --baseline scripts/data/citation_content_backlog.json` | PMID exists AND article title matches claimed topic; fails only on a new mismatch or an unresolved PMID (the backlog is listed, not blocking) |
| `rules` | `scripts/api_audit/verify_interaction_rules_citations.py --strict` | Interaction-rule citations name the rule's subject and topic (release gate) |
| `cui` | `scripts/api_audit/verify_cui.py` | UMLS CUI resolves to correct concept |
| `interactions` | `scripts/api_audit/verify_interactions.py` | RXCUIs + CUIs + drug class refs valid |
| `unii` | `scripts/api_audit/verify_unii.py` | FDA UNII + CFR references valid |
| `pubchem` | `scripts/api_audit/verify_pubchem.py` | PubChem CID + CAS numbers valid |
| `nct` | `scripts/api_audit/verify_clinical_trials.py` | ClinicalTrials.gov NCT IDs valid |
| `rda` | `scripts/api_audit/verify_rda_uls.py` | RDA/AI/UL values match National Academies DRI |
| `depletions` | `scripts/api_audit/verify_depletion_timing_pmids.py` | Depletion/timing PMIDs content-verified |
| (all) | Runs pmid + rules + cui + unii + interactions | Full suite |

For a curated-data batch, add `--changed-since origin/main` (or the batch's base ref) to the `pmid`
and `rules` verifiers: they check only the entries the batch changed and print one line each.

## Steps

<step>
Check .env exists with required API keys:
```bash
test -f .env && grep -c "API_KEY" .env
```
If missing, tell the user: "API keys not found in .env — cannot verify. Do NOT commit unverified data."
</step>

<step>
Parse the argument to determine which scripts to run. If no argument, run the full suite (pmid, rules, cui, unii, interactions).
</step>

<step>
Run each verification script with the project interpreter and capture output. Pipe through
`| tail -30` to keep context lean. Example:
```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/api_audit/verify_all_citations_content.py --baseline scripts/data/citation_content_backlog.json 2>&1 | tail -30
```
</step>

<step>
Report results:
- **ALL PASS**: "Verification complete. All identifiers verified against live APIs. Safe to commit."
- **ANY FAIL**: List every failure with the identifier, expected value, and actual value. State: "DO NOT commit until these are resolved."
</step>
