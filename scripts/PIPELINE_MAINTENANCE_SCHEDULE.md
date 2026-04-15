# Pipeline Maintenance Schedule

**Owner:** Sean Cheick Baradji
**Last Updated:** 2026-04-14
**Repo:** PharmaGuide_Pipeline (`dsld_clean`)

This is the single source of truth for keeping the PharmaGuide pipeline healthy. Every recurring task, every script, exact commands, what to do with results, and how to fix problems.

**For Claude Code:** If you're an AI agent running maintenance, follow each task sequentially. After running each command, check the output against the "Success looks like" criteria. If it doesn't match, follow the "If it fails" instructions before moving on.

---

## Quick Reference

| Frequency | Task | Time | Priority |
|-----------|------|------|----------|
| **Weekly** | [1. FDA recall sync](#1-fda-recall--enforcement-sync) | ~2 min | Critical |
| **Weekly** | [2. Manufacturer violations sync](#2-manufacturer-violations-sync) | ~1 min | High |
| **Monthly** | [3. CAERS adverse event refresh](#3-caers-adverse-event-refresh) | ~3 min | High |
| **Monthly** | [4. UNII cache refresh](#4-unii-cache-refresh) | ~1 min | Medium |
| **Monthly** | [5. Citation content verification](#5-citation-content-verification) | ~10 min | Critical |
| **Monthly** | [6. SUPPai re-ingestion check](#6-suppai-re-ingestion-check) | ~5 min | Medium |
| **Quarterly** | [7. Drug label interaction mining](#7-drug-label-interaction-mining) | ~5 min | Medium |
| **Quarterly** | [8. Drug class expansion check](#8-drug-class-expansion-check) | ~5 min | Medium |
| **Quarterly** | [9. Clinical evidence discovery](#9-clinical-evidence-discovery) | ~15 min | Medium |
| **Quarterly** | [10. ChEMBL bioactivity enrichment](#10-chembl-bioactivity-enrichment) | ~10 min | Low |
| **Quarterly** | [11. IQM alias expansion](#11-iqm-alias-expansion) | ~10 min | Low |
| **Quarterly** | [12. Botanical enrichment](#12-botanical-enrichment) | ~10 min | Low |
| **Before release** | [13. Preflight checks](#13-preflight-checks) | ~1 min | Critical |
| **Before release** | [14. Full pipeline run](#14-full-pipeline-run) | ~30 min | Critical |
| **Before release** | [15. Enrichment contract validation](#15-enrichment-contract-validation) | ~1 min | Critical |
| **Before release** | [16. Coverage gate](#16-coverage-gate) | ~1 min | Critical |
| **Before release** | [17. Shadow score comparison](#17-shadow-score-comparison) | ~5 min | High |
| **Before release** | [18. Build final DB](#18-build-final-db) | ~10 min | Critical |
| **Before release** | [19. DB integrity check](#19-db-integrity-check) | ~2 min | Critical |
| **Before release** | [20. Build interaction DB](#20-build-interaction-db) | ~3 min | Critical |
| **Before release** | [21. Assemble release artifact](#21-assemble-release-artifact) | ~2 min | Critical |
| **Before release** | [22. Test suite](#22-test-suite) | ~5 min | Critical |
| **After release** | [23. Sync to Supabase](#23-sync-to-supabase) | ~10 min | Critical |
| **After release** | [24. Regression snapshot](#24-regression-snapshot) | ~2 min | High |

---

## Weekly Tasks

### 1. FDA Recall & Enforcement Sync

**What:** Downloads new FDA supplement recalls, enforcement actions, and DEA scheduling. Updates `banned_recalled_ingredients.json`.

**Why:** A recalled supplement could be in your app right now showing "SAFE."

```bash
bash scripts/run_fda_sync.sh
```

**Options:**
```bash
bash scripts/run_fda_sync.sh --days 14      # Look back 14 days
bash scripts/run_fda_sync.sh --no-commit     # Report only, don't auto-commit
bash scripts/run_fda_sync.sh --no-claude     # Skip AI review
```

**Success looks like:**
- Output file: `scripts/reports/fda_weekly_sync_report.json`
- Report shows 0-3 new entries (normal week) or 10-20 (enforcement wave)
- No API errors in output

**What to do with results:**
1. Open the report: `cat scripts/reports/fda_weekly_sync_report.json | python3 -m json.tool | head -50`
2. For each new entry, verify:
   - Is the ingredient name correct? (not a brand name or product name)
   - Is the status right? (`banned`, `recalled`, `high_risk`, `watchlist`)
   - Is the severity appropriate for the harm level?
3. If entries look correct → `git add scripts/data/banned_recalled_ingredients.json && git commit -m "chore: FDA weekly sync $(date +%Y-%m-%d)"`
4. If an entry looks wrong → edit it manually, then commit
5. After committing → run `python3 -m pytest scripts/tests/test_banned_schema_v3.py -v` to verify schema

**If it fails:**
- `OPENFDA_API_KEY` missing → add to `.env` at repo root
- 429 rate limit → wait 1 hour, retry
- Schema mismatch → check `DATABASE_SCHEMA.md` section 5 for the current schema

---

### 2. Manufacturer Violations Sync

**What:** Pulls FDA warning letters against supplement manufacturers. Updates `manufacturer_violations.json` for Section D brand trust scoring.

```bash
python3 scripts/api_audit/fda_manufacturer_violations_sync.py
```

**Success looks like:**
- Script completes without errors
- Reports how many new violations found

**What to do with results:**
1. Review each new violation — is it a real supplement manufacturer? (Some FDA letters are for food/cosmetic companies)
2. If valid → commit the updated `manufacturer_violations.json`
3. Run `python3 -m pytest scripts/tests/ -k "manufacturer" -v` to verify

**If it fails:**
- Same API key fix as task 1
- Duplicate manufacturer name → check existing entries first

---

## Monthly Tasks

### 3. CAERS Adverse Event Refresh

**What:** Re-downloads FDA CAERS bulk data and regenerates adverse event signals. Updates the B8 scoring penalty data.

```bash
python3 scripts/api_audit/ingest_caers.py --refresh
```

**Success looks like:**
- Downloads ~8.5 MB zip
- Output: `scripts/data/caers_adverse_event_signals.json`
- Shows "Ingredients with signals: 159+" and "Supplement reports: 48,000+"
- Top 15 ingredients listed with serious report counts

**What to do with results:**
1. Compare signal counts to last run — any big jumps?
   ```bash
   python3 -c "
   import json
   with open('scripts/data/caers_adverse_event_signals.json') as f:
       d = json.load(f)
   strong = [k for k, v in d['signals'].items() if v['signal_strength'] == 'strong']
   print(f'Strong signals: {len(strong)}')
   for s in sorted(strong): print(f'  {s}: {d[\"signals\"][s][\"serious_reports\"]} serious')
   "
   ```
2. Check for NEW strong signals (ingredients that crossed the 100-serious threshold)
3. Any new strong signal → check if it's in `banned_recalled_ingredients.json`. If not, consider adding it.
4. Commit: `git add scripts/data/caers_adverse_event_signals.json && git commit -m "chore: CAERS monthly refresh $(date +%Y-%m-%d)"`
5. Run tests: `python3 -m pytest scripts/tests/test_caers_integration.py -v`

**If it fails:**
- Download URL changed → check `https://api.fda.gov/download.json` under `/food/event`
- Match rate drops below 25% → OpenFDA may have changed product name format; update `MULTI_INGREDIENT_KEYWORDS` in `ingest_caers.py`

---

### 4. UNII Cache Refresh

**What:** Re-downloads the FDA UNII substance registry (172K+ substances) for offline lookups.

```bash
python3 scripts/api_audit/build_unii_cache.py --refresh
```

**Success looks like:**
- Downloads ~3.4 MB zip
- Validation: 4/4 known substances pass
- Output: `scripts/data/fda_unii_cache.json` (gitignored, ~15 MB)

**What to do with results:**
- No action needed — the cache is used automatically by `verify_unii.py` and `unii_cache.py`
- If substance count increased significantly → run IQM alias expansion (task 11) to fill newly-available UNIIs

**If it fails:**
- URL changed → check `https://api.fda.gov/download.json` under `/other/unii`
- Corrupt cache → `rm scripts/data/fda_unii_cache.json` and re-run

---

### 5. Citation Content Verification

**What:** Verifies every PMID across all data files matches the claimed topic (not just exists).

```bash
python3 scripts/api_audit/verify_all_citations_content.py
```

**Success looks like:**
- Output: `76/76 pass, 0 mismatch` (or higher if new PMIDs added)
- 100% pass rate is the ONLY acceptable result

**What to do with results:**
1. If 100% pass → no action needed
2. If ANY PMID fails:
   - Look up the failed PMID: `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`
   - Read the paper title — does it match the claimed interaction/evidence?
   - If wrong → find the correct PMID via PubMed search
   - Replace ONE PMID at a time in the data file
   - Re-run this script to verify the fix
   - NEVER batch-replace PMIDs
3. After fixing → commit: `git commit -m "fix: replace hallucinated PMID <old> with verified <new>"`

**Mandatory triggers:** Run after ANY change to: `curated_interactions_v1.json`, `med_med_pairs_v1.json`, `medication_depletions.json`, `backed_clinical_studies.json`

**If it fails:**
- `PUBMED_API_KEY` missing → add to `.env`
- Rate limited → reduce batch size or wait

---

### 6. SUPPai Re-ingestion Check

**What:** Re-ingests the SUPPai research pairs database and checks if coverage improved since last run.

```bash
python3 scripts/ingest_suppai.py
```

**Success looks like:**
- Shows research pair count (30K+ as of Sprint 22)
- Shows supplement anchor count (537+)

**What to do with results:**
1. If pair count increased → IQM aliases may need updating to capture new matches
2. If pair count decreased → data format changed; investigate
3. Commit if changed: `git add scripts/data/curated_interactions/ && git commit -m "chore: SUPPai re-ingestion"`

---

## Quarterly Tasks

### 7. Drug Label Interaction Mining

**What:** Scans FDA drug labels for supplement-drug interaction mentions. Finds gaps in our interaction rules.

```bash
# Download data (first time or refresh — 130 MB per partition, 3 is enough)
mkdir -p scripts/data/fda_drug_labels
cd scripts/data/fda_drug_labels
for i in 0001 0002 0003; do
  curl -L -o "drug-label-${i}-of-0013.json.zip" \
    "https://download.open.fda.gov/drug/label/drug-label-${i}-of-0013.json.zip"
  unzip -o "drug-label-${i}-of-0013.json.zip"
done
cd ../../..

# Run the miner
python3 scripts/api_audit/mine_drug_label_interactions.py
```

**Success looks like:**
- Output: `scripts/reports/drug_label_interaction_candidates.json`
- Shows "Unique supplements: 40+, Already in rules: 36+ (90%+)"
- Lists new candidates with drug names and context

**What to do with results:**
1. Open the report: `cat scripts/reports/drug_label_interaction_candidates.json | python3 -m json.tool | head -100`
2. Focus on `new_candidates` section — these are gaps in your rules
3. For each new candidate:
   - Read the `context` — is it a REAL interaction warning or just a passing mention?
   - Passing mention (e.g., "grape seed oil" in a cosmetic ingredient list) → SKIP
   - Real interaction (e.g., "omega-3 may prolong bleeding time") → ADD RULE
4. To add a rule: edit `scripts/data/ingredient_interaction_rules.json`, follow the existing rule format (see `RULE_IQM_FISH_OIL_BLEEDING` as a template)
5. After adding rules → verify: `python3 scripts/api_audit/verify_interactions.py`
6. Re-run the miner to confirm the gap closed

**If it fails:**
- Memory error → use `--file` flag to process one partition at a time
- No files found → check `scripts/data/fda_drug_labels/` directory exists

---

### 8. Drug Class Expansion Check

**What:** Verifies all drug classes referenced by interaction rules actually exist.

```bash
# List current classes
python3 -c "
import json
with open('scripts/data/drug_classes.json') as f:
    d = json.load(f)
classes = d.get('classes', {})
print(f'Drug classes: {len(classes)}')
for cid in sorted(classes.keys()):
    print(f'  {cid}')
"

# Check for orphaned references (rules referencing non-existent classes)
python3 -c "
import json
with open('scripts/data/ingredient_interaction_rules.json') as f:
    rules = json.load(f)
with open('scripts/data/drug_classes.json') as f:
    classes = set(json.load(f).get('classes', {}).keys())
missing = set()
for r in rules['interaction_rules']:
    for dc in r.get('drug_class_rules', []):
        cid = 'class:' + dc['drug_class_id']
        if cid not in classes:
            missing.add(dc['drug_class_id'])
if missing:
    print(f'MISSING CLASSES: {missing}')
else:
    print('All referenced drug classes exist.')
"
```

**Success looks like:**
- "All referenced drug classes exist."
- 28+ drug classes listed

**What to do with results:**
1. If all classes exist → no action needed
2. If missing classes found:
   ```bash
   python3 scripts/api_audit/seed_drug_classes.py --class-id <MISSING_CLASS_NAME>
   ```
3. After adding → run: `python3 -m pytest scripts/tests/test_drug_classes_schema.py -v`
4. Also update `SchemaIds.dart` in Flutter if users need to select the new class

---

### 9. Clinical Evidence Discovery

**What:** Queries ClinicalTrials.gov for completed supplement trials. Cross-refs with PubMed for published results.

```bash
python3 scripts/api_audit/discover_clinical_evidence.py discover --min-trials 3
```

**Success looks like:**
- Shows candidates with NCT IDs, enrollment, PMIDs
- Typical: 5-15 new candidates per quarter

**What to do with results:**
1. Review each candidate — does the ingredient have enough evidence to add to `backed_clinical_studies.json`?
2. If yes, use `--apply` flag to auto-add the skeleton entry
3. **CRITICAL:** After `--apply`, run `python3 scripts/api_audit/verify_all_citations_content.py` to verify all new PMIDs
4. Manually review each added entry for:
   - `study_type` classification (rct_single, observational, etc.)
   - `effect_direction` (positive_strong, mixed, null, etc.)
   - `key_endpoints` accuracy
5. Commit one entry at a time if doing manual additions

---

### 10. ChEMBL Bioactivity Enrichment

**What:** Queries ChEMBL for mechanism-of-action data on IQM ingredients. Adds pharmacological context.

```bash
python3 scripts/api_audit/enrich_chembl_bioactivity.py
```

**What to do with results:**
- Review suggested enrichments — is the mechanism of action correct for the supplement context (not the pharmaceutical context)?
- ChEMBL data is pharma-oriented; sometimes the mechanism is for a different use
- Add verified mechanisms to IQM entries manually

---

### 11. IQM Alias Expansion

**What:** Find IQM entries missing aliases/UNII codes and fill them.

```bash
# Check coverage
python3 -c "
import json
with open('scripts/data/ingredient_quality_map.json') as f:
    iqm = json.load(f)
no_alias = [k for k,v in iqm.items() if k!='_metadata' and not v.get('aliases')]
no_unii = [k for k,v in iqm.items() if k!='_metadata' and not (v.get('external_ids',{}) or {}).get('unii')]
print(f'No aliases: {len(no_alias)}/{len(iqm)-1}')
print(f'No UNII: {len(no_unii)}/{len(iqm)-1}')
"

# Verify UNII mappings (uses local cache + GSRS API)
python3 scripts/api_audit/verify_unii.py --file scripts/data/ingredient_quality_map.json --mode iqm

# Audit alias accuracy
python3 scripts/api_audit/audit_alias_accuracy.py
```

**What to do with results:**
- `NAME_EXACT` and `SYNONYM_EXACT` matches → safe to batch-add as aliases
- `TOKEN_OVERLAP_80` matches → **manual chemistry review required** (e.g., "linolenic acid" vs "gamma_linolenic_acid" are different compounds)
- New UNII codes → add to `entry["external_ids"]["unii"]`
- Run tests after: `python3 -m pytest scripts/tests/test_ingredient_quality_map_schema.py -v`

---

### 12. Botanical Enrichment

**What:** Enriches botanical ingredient entries with taxonomy, traditional use, and standardization data.

```bash
python3 scripts/api_audit/enrich_botanicals.py
```

**What to do with results:**
- Review each botanical enrichment for accuracy
- Verify genus/species names are correct
- Do NOT auto-apply — review each entry individually

---

## Before Every Release

### 13. Preflight Checks

**What:** Validates data file consistency, detects schema mismatches, and checks for known issues before running the pipeline.

```bash
python3 scripts/preflight.py
```

**Success looks like:** All checks pass, no warnings except intentional dual-classifications.

**If it fails:** Fix the reported issue before proceeding. Do NOT skip preflight.

---

### 14. Full Pipeline Run

**What:** Run Clean → Enrich → Score on the latest dataset.

```bash
python3 scripts/run_pipeline.py <dataset_dir>
```

**Success looks like:**
- No errors in output
- All products processed
- Score distribution is reasonable

**What to do with results:**
1. Check the enrichment summary in `<output>/reports/`
2. Check the scoring summary
3. Compare verdict distribution to previous run:
   ```bash
   python3 -c "
   import json
   with open('<output>/scored_output.json') as f:
       products = json.load(f)
   from collections import Counter
   verdicts = Counter(p.get('verdict','?') for p in products)
   for v, c in verdicts.most_common():
       print(f'  {v}: {c}')
   "
   ```

---

### 15. Enrichment Contract Validation

**What:** Verifies the enricher output matches the expected contract schema.

```bash
python3 scripts/enrichment_contract_validator.py <enriched_file>
```

**Success looks like:** All contract checks pass.

**If it fails:** The enricher produced unexpected output. Check enricher logs for the failing product.

---

### 16. Coverage Gate

**What:** Checks that quality thresholds are met (mapping rate, score distribution, etc.).

```bash
python3 scripts/coverage_gate.py <scored_file>
```

**Success looks like:** "PASS" with coverage ≥ 99.5%.

**If it fails:** Report shows which metric is below threshold. Fix the pipeline issue, don't lower the threshold.

---

### 17. Shadow Score Comparison

**What:** Compares current scores against a baseline to detect unexpected shifts.

```bash
python3 scripts/shadow_score_comparison.py <current_scored> <baseline_scored>
```

**What to do with results:**
1. Products with score changes > 5 points → investigate why
2. If change is from B8 CAERS → expected (new penalty)
3. If change is unexplained → check what data files changed since baseline

---

### 18. Build Final DB

**What:** Builds the SQLite database and detail blobs for Flutter and Supabase.

```bash
python3 scripts/build_final_db.py <scored_input> <output_dir>
```

**Success looks like:**
- `pharmaguide_core.db` created
- `detail_blobs/` directory with one JSON per product
- `export_manifest.json` with row counts and checksums

**What to do with results:**
1. Run integrity check (task 19)
2. Spot-check a few products: `python3 -c "import sqlite3; ..."`

---

### 19. DB Integrity Check

**What:** Validates final SQLite schema and data.

```bash
python3 scripts/db_integrity_sanity_check.py
```

**Success looks like:**
- Column count = 90
- No NULL in required fields
- Score ranges valid (0-80 for score_80, 0-100 for score_100)

---

### 20. Build Interaction DB

**What:** Builds the interaction database SQLite artifact for Flutter.

```bash
bash scripts/rebuild_interaction_db.sh --offline --import
```

**Or step by step:**
```bash
python3 scripts/build_interaction_db.py
python3 scripts/release_interaction_artifact.py
```

**Success looks like:**
- `interaction_db.sqlite` created with 129+ rules
- Checksum matches

**What to do with results:**
- Copy to Flutter: `cp scripts/interaction_db_output/interaction_db.sqlite "/Users/seancheick/PharmaGuide ai/assets/db/"`
- Run Flutter interaction tests

---

### 21. Assemble Release Artifact

**What:** Packages the final DB, manifest, and metadata into a release bundle.

```bash
python3 scripts/assemble_final_db_release.py <build_output_dir>
```

**Or for all datasets:**
```bash
python3 scripts/build_all_final_dbs.py
```

**Success looks like:**
- Release artifact created in `scripts/dist/`
- Manifest includes checksums and row counts

---

### 22. Test Suite

**What:** Run all tests.

```bash
python3 -m pytest scripts/tests/ -v
```

**Success looks like:** 598+ tests pass. Only known failures are Python 3.9 `datetime.UTC` import errors (41 files, not data issues).

**If new tests fail:**
1. Read the error message — is it a test bug or a real data issue?
2. Data issue → fix the data, re-run
3. Test bug → fix the test assertion
4. NEVER skip failing tests for a release

---

## After Release

### 23. Sync to Supabase

**What:** Uploads the built DB and detail blobs to Supabase for the Flutter app.

```bash
# Dry run first
python3 scripts/sync_to_supabase.py <build_output_dir> --dry-run

# If dry run looks good
python3 scripts/sync_to_supabase.py <build_output_dir>
```

**Success looks like:**
- All products uploaded
- All detail blobs uploaded
- Zero sync errors

**What to do with results:**
1. Check the sync report for errors
2. Verify a product in the Flutter app — does the score match?
3. If sync fails mid-way → it's safe to re-run (idempotent)

---

### 24. Regression Snapshot

**What:** Captures the current score state as a baseline for future comparisons.

```bash
python3 scripts/regression_snapshot.py <scored_file>
```

**What to do with results:**
- The snapshot is saved automatically
- Use it with shadow_score_comparison.py (task 17) in the next release cycle

---

## API Audit Scripts Reference

Run these when you modify the corresponding data file.

| Script | Data File | External API | When to Run |
|--------|-----------|-------------|-------------|
| `verify_cui.py` | `ingredient_quality_map.json` | UMLS | After IQM changes |
| `verify_pubchem.py` | `ingredient_quality_map.json` | PubChem | After adding CAS/CID |
| `verify_unii.py` | `ingredient_quality_map.json` | GSRS / local cache | After IQM changes |
| `verify_rda_uls.py` | `rda_optimal_uls.json` | USDA FoodData Central | After dosing changes |
| `verify_efsa.py` | `harmful_additives.json` | EFSA | After additive changes |
| `verify_clinical_trials.py` | `backed_clinical_studies.json` | ClinicalTrials.gov | After evidence changes |
| `verify_interactions.py` | `curated_interactions_v1.json` | RxNorm + UMLS | After interaction changes |
| `verify_depletion_timing_pmids.py` | `medication_depletions.json` | PubMed | After depletion changes |
| `verify_pubmed_references.py` | Multiple files | PubMed | After any PMID changes |
| `verify_comptox.py` | IQM / harmful_additives | EPA CompTox | After adding chemical IDs |
| `verify_all_citations_content.py` | All PMID files | PubMed | **Before EVERY release** |
| `audit_banned_recalled_accuracy.py` | `banned_recalled_ingredients.json` | openFDA | Before release |
| `audit_clinical_evidence_strength.py` | `backed_clinical_studies.json` | PubMed | Quarterly |
| `audit_clinical_sources.py` | `backed_clinical_studies.json` | — | Quarterly |
| `audit_alias_accuracy.py` | `ingredient_quality_map.json` | — | After alias changes |
| `audit_notes_alignment.py` | Multiple data files | — | Before release |
| `normalize_clinical_pubmed.py` | `backed_clinical_studies.json` | PubMed | After evidence changes |

---

## DSLD API Data Sync

**What:** Downloads fresh product data from the NIH DSLD API for processing.

```bash
# Sync new/updated products
python3 scripts/dsld_api_sync.py --output <dataset_dir>

# Check API status
python3 scripts/dsld_api_client.py --status
```

**When to run:** Before a new pipeline run if you want the latest DSLD data.

---

## API Keys

All keys are in `.env` at the repo root. **Never commit this file.**

| Key | Source | Used By |
|-----|--------|---------|
| `UMLS_API_KEY` | [UMLS License](https://uts.nlm.nih.gov/) | verify_cui.py, verify_interactions.py |
| `OPENFDA_API_KEY` | [openFDA](https://open.fda.gov/apis/authentication/) | fda_weekly_sync.py, fda_manufacturer_violations_sync.py, ingest_caers.py |
| `PUBMED_API_KEY` | [NCBI](https://www.ncbi.nlm.nih.gov/account/) | All PubMed verification scripts |

---

## Troubleshooting

### "enricher takes too long"
- Rebuild UNII cache: `python3 scripts/api_audit/build_unii_cache.py --refresh`
- Check for API rate limits (429 errors in `scripts/logs/`)

### "test_score_supplements fails with datetime.UTC"
- You're on Python 3.9. Use Python 3.13 for full test coverage.
- This is a runtime issue, not a data issue. The 41 affected test files all pass on 3.13.

### "CAERS signals file is empty or missing"
- Re-run: `python3 scripts/api_audit/ingest_caers.py --refresh`
- The raw data is in `scripts/data/fda_caers/` (gitignored — must download locally)

### "UNII cache not found"
- Run: `python3 scripts/api_audit/build_unii_cache.py`
- Gitignored — each machine builds its own cache

### "Drug label files missing"
- Download partitions from `https://download.open.fda.gov/drug/label/`
- Place in `scripts/data/fda_drug_labels/` (gitignored, ~130 MB per file)

### "Score distribution shifted unexpectedly"
- Run shadow comparison: `python3 scripts/shadow_score_comparison.py <current> <baseline>`
- If B8 CAERS is the cause → expected, verify via dashboard CAERS tab
- If unexplained → check what data files changed: `git diff --stat HEAD~5`

### "Coverage gate fails"
- Check which metric is below threshold
- Usually: unmapped ingredients → add to IQM or update aliases
- Never lower the threshold to pass

### "Supabase sync errors"
- Check `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`
- Re-run is safe (idempotent uploads)
- If specific products fail → check their detail blob JSON for invalid characters

---

## Full Maintenance Cycle (copy-paste checklist)

Run this monthly or before any release:

```bash
# 1. Weekly syncs
bash scripts/run_fda_sync.sh
python3 scripts/api_audit/fda_manufacturer_violations_sync.py

# 2. Monthly refreshes
python3 scripts/api_audit/ingest_caers.py --refresh
python3 scripts/api_audit/build_unii_cache.py --refresh
python3 scripts/api_audit/verify_all_citations_content.py

# 3. Preflight
python3 scripts/preflight.py

# 4. Pipeline run
python3 scripts/run_pipeline.py <dataset_dir>

# 5. Quality gates
python3 scripts/enrichment_contract_validator.py <enriched_file>
python3 scripts/coverage_gate.py <scored_file>

# 6. Build
python3 scripts/build_final_db.py <scored_input> <output_dir>
python3 scripts/db_integrity_sanity_check.py
bash scripts/rebuild_interaction_db.sh --offline --import

# 7. Tests
python3 -m pytest scripts/tests/ -v

# 8. Deploy
python3 scripts/sync_to_supabase.py <build_output_dir> --dry-run
python3 scripts/sync_to_supabase.py <build_output_dir>

# 9. Snapshot
python3 scripts/regression_snapshot.py <scored_file>
```
