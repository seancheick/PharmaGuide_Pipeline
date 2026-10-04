---
name: verify-data
description: Run API verification scripts against data files to catch hallucinated identifiers (PMIDs, CUIs, UNIIs, etc.)
---

# /verify-data — Clinical Data Verification

Run the PharmaGuide API verification suite against data files. Use this BEFORE committing any data file changes.

## Usage

- `/verify-data` — verify the active changed-entry batch with the applicable verifier(s)
- `/verify-data all` — explicitly request the complete verification suite
- `/verify-data pmid` — verify PubMed citations only
- `/verify-data cui` — verify UMLS CUIs only
- `/verify-data interactions` — verify interaction RXCUIs + CUIs
- `/verify-data unii` — verify FDA UNIIs only

## Procedure

1. Check that `.env` exists at repo root with API keys (UMLS_API_KEY, PUBMED_API_KEY, OPENFDA_API_KEY)
2. Run the appropriate verification script(s) based on the argument
3. Classify results: changed-entry failures block that batch; known triaged unrelated backlog remains reported
4. Do not accept unverified changed clinical facts. Fix all batch failure classes together; do not restart unrelated verifiers after each fix

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
Parse the argument and active diff. With no argument, use applicable changed-entry checks,
not an automatic whole-registry audit. Explicit `all` runs pmid, rules, cui, unii and interactions.
Use supported --changed-since/--file options; inspect each verifier's arguments rather than
inventing filters. If a verifier has no narrower supported scope, run that verifier once for the
completed batch. Reuse a still-applicable content-verification receipt for the identical entry,
claim and source; a new session alone does not invalidate it. New/changed clinical claims need
entry-specific verification; identity resolution alone never proves clinical applicability.
</step>

<step>
Run each verification script with the project interpreter and capture output. Pipe through
`| tail -30` only with pipefail and a durable log, so a verifier failure cannot become success. Example:
```bash
source scripts/python_env.sh
set -o pipefail
"$PG_PYTHON" scripts/api_audit/verify_all_citations_content.py --baseline scripts/data/citation_content_backlog.json 2>&1 | tail -30
```
</step>

<step>
Report results:
- **ALL PASS**: "Verification complete for the named changed entries and claims; report the exact scope and receipts."
- **ANY FAIL**: List every failure with the identifier, expected value, and actual value. Distinguish new changed-entry defects, transient API failures and declared unrelated backlog. Resolve the affected class without restarting the entire suite; do not claim a failed or unresolved changed entry passed.
</step>
