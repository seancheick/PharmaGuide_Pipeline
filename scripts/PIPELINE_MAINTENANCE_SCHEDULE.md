# Pipeline Maintenance Schedule

**Owner:** Sean Cheick Baradji
**Last Updated:** 2026-04-14
**Repo:** PharmaGuide_Pipeline (`dsld_clean`)

This document lists every recurring maintenance task for the PharmaGuide data pipeline. Each entry includes: what to run, why, how often, what to expect, and how to fix issues.

---

## Quick Reference

| Frequency | Task | Time | Priority |
|-----------|------|------|----------|
| **Weekly** | FDA recall sync | ~2 min | Critical |
| **Weekly** | Manufacturer violations sync | ~1 min | High |
| **Monthly** | CAERS adverse event refresh | ~3 min | High |
| **Monthly** | UNII cache refresh | ~1 min | Medium |
| **Monthly** | Citation content verification | ~10 min | Critical |
| **Quarterly** | Drug label interaction mining | ~5 min | Medium |
| **Quarterly** | Drug class expansion check | ~5 min | Medium |
| **Quarterly** | Clinical evidence discovery | ~15 min | Medium |
| **Quarterly** | IQM alias expansion | ~10 min | Low |
| **Before every release** | Full pipeline run + tests | ~30 min | Critical |
| **Before every release** | Coverage gate | ~1 min | Critical |
| **Before every release** | DB integrity check | ~2 min | Critical |

---

## Weekly Tasks

### 1. FDA Recall & Enforcement Sync

**What:** Downloads new FDA supplement recalls, enforcement actions, and DEA scheduling from openFDA APIs and RSS feeds. Updates `banned_recalled_ingredients.json`.

**Why:** A recalled supplement could be in your app right now. This catches new FDA actions within 7 days of publication. Delays mean users see "SAFE" on recalled products.

**How to run:**
```bash
bash scripts/run_fda_sync.sh
```

**Options:**
```bash
bash scripts/run_fda_sync.sh --days 14      # Look back 14 days instead of 7
bash scripts/run_fda_sync.sh --no-commit     # Report only, don't commit
bash scripts/run_fda_sync.sh --no-claude     # Skip AI review (manual review)
```

**What to expect:**
- Output: `scripts/reports/fda_weekly_sync_report.json`
- Most weeks: 0-3 new entries (quiet)
- After FDA enforcement wave: 10-20 new entries (review carefully)

**If something goes wrong:**
- `OPENFDA_API_KEY` missing → set in `.env` at repo root
- API rate limit → wait 1 hour, retry
- New entry doesn't match existing schema → check `banned_recalled_ingredients.json` schema in `DATABASE_SCHEMA.md`

**Post-run:** Review the report. Each new entry needs manual verification that the name, status, and severity are correct before committing.

---

### 2. Manufacturer Violations Sync

**What:** Pulls FDA warning letters and enforcement actions against supplement manufacturers. Updates `manufacturer_violations.json`.

**Why:** Manufacturers with FDA warning letters get a brand trust penalty (Section D). Missing a violation means overscoring a bad manufacturer.

**How to run:**
```bash
python3 scripts/api_audit/fda_manufacturer_violations_sync.py
```

**What to expect:**
- Output: updates to `scripts/data/manufacturer_violations.json`
- Typical: 0-5 new violations per week

**If something goes wrong:**
- Same API key issues as FDA sync
- Duplicate manufacturer names → check for existing entries before adding

---

## Monthly Tasks

### 3. CAERS Adverse Event Refresh

**What:** Re-downloads FDA CAERS bulk data (148K+ reports) and regenerates adverse event signals for 159+ ingredients. Updates `caers_adverse_event_signals.json` which feeds B8 scoring.

**Why:** New adverse event reports are filed daily. Monthly refresh captures new hospitalizations, deaths, and ER visits. A supplement that was "weak signal" last month could become "strong signal" this month.

**How to run:**
```bash
python3 scripts/api_audit/ingest_caers.py --refresh
```

**What to expect:**
- Downloads: ~8.5 MB zip from OpenFDA
- Processing time: ~2 minutes
- Output: `scripts/data/caers_adverse_event_signals.json`
- Typical changes: report counts increase slightly, maybe 1-2 new ingredients cross signal thresholds

**What to check after:**
- New "strong" signals → review if they should also go in `banned_recalled_ingredients.json`
- Use the dashboard CAERS Audit → Cross-Reference tab to see what's NOT in banned/recalled
- Run tests: `python3 -m pytest scripts/tests/test_caers_integration.py -v`

**If something goes wrong:**
- Download fails → check `https://api.fda.gov/download.json` for URL changes
- Ingredient match rate drops → check if OpenFDA changed the product name format

---

### 4. UNII Cache Refresh

**What:** Re-downloads the FDA UNII substance registry (172K substances) and rebuilds the local lookup cache. Used by `verify_unii.py` for offline ingredient identity resolution.

**Why:** FDA adds ~100-200 new UNII codes monthly (new approved substances). The cache enables fast offline lookups instead of live GSRS API calls.

**How to run:**
```bash
python3 scripts/api_audit/build_unii_cache.py --refresh
```

**What to expect:**
- Downloads: ~3.4 MB zip from OpenFDA
- Output: `scripts/data/fda_unii_cache.json` (14.9 MB, gitignored)
- Typical changes: +100-200 new substances

**If something goes wrong:**
- Download URL changed → check `https://api.fda.gov/download.json` under `/other/unii`
- Cache file corrupt → delete and re-run

---

### 5. Citation Content Verification

**What:** Verifies that every PMID in every data file actually matches the claimed topic. Catches AI-hallucinated citations that exist in PubMed but are about completely wrong topics.

**Why:** 30% of AI-generated PMIDs pass existence checks but fail content checks. This is the only thing that catches a citation about "rat liver enzymes" being used to support "vitamin D bone health."

**How to run:**
```bash
python3 scripts/api_audit/verify_all_citations_content.py
```

**What to expect:**
- Checks all PMIDs across: `curated_interactions_v1.json`, `med_med_pairs_v1.json`, `medication_depletions.json`, `backed_clinical_studies.json`
- Output: pass/fail per PMID with content match score
- Target: 100% pass rate (76/76 as of Sprint 22)

**If a PMID fails:**
1. Look up the PMID on PubMed — read the actual paper title
2. If the paper is about a different topic → find the correct PMID
3. Replace one at a time, verify, test
4. NEVER batch-replace PMIDs

**Mandatory trigger:** Run this after ANY data file change involving PMIDs.

---

## Quarterly Tasks

### 6. Drug Label Interaction Mining

**What:** Scans FDA drug label text for mentions of dietary supplements in `drug_interactions` and `warnings` sections. Cross-references against existing interaction rules to find gaps.

**Why:** FDA drug labels are the most authoritative source for supplement-drug interactions. If warfarin's label says "avoid St. John's Wort" and we don't have that rule, users won't see the warning.

**How to run:**
```bash
# First time: download bulk data (1.7 GB total, ~130 MB per partition)
# Download partitions you want to process (at minimum 3 gives good coverage):
cd scripts/data/fda_drug_labels/
for i in 0001 0002 0003; do
  curl -L -o "drug-label-${i}-of-0013.json.zip" \
    "https://download.open.fda.gov/drug/label/drug-label-${i}-of-0013.json.zip"
  unzip -o "drug-label-${i}-of-0013.json.zip"
done
cd ../../..

# Run the miner
python3 scripts/api_audit/mine_drug_label_interactions.py
```

**What to expect:**
- Output: `scripts/reports/drug_label_interaction_candidates.json`
- From 3 partitions: ~40 supplements found, ~90% already in rules
- New candidates are listed with drug name, context, and pharm class

**What to do with candidates:**
1. Review each "new candidate" in the report
2. Read the FDA label context — is it a real interaction or just a mention?
3. For real interactions: manually create a rule in `ingredient_interaction_rules.json`
4. NEVER auto-import — each candidate must be verified for mechanism, severity, and evidence

**If something goes wrong:**
- Memory issues with large files → process one partition at a time: `--file scripts/data/fda_drug_labels/drug-label-0001-of-0013.json`
- Low match rate → check `SUPPLEMENT_TERMS` list in the script for missing common names

---

### 7. Drug Class Expansion Check

**What:** Checks if new RxClass drug classes need to be added for interaction rules to fire properly.

**Why:** Missing drug classes silently disable interaction warnings. In Sprint 22 we found SSRIs were missing — meaning St. John's Wort serotonin syndrome (potentially fatal) was invisible to users.

**How to run:**
```bash
# Check what drug classes exist
python3 -c "
import json
with open('scripts/data/drug_classes.json') as f:
    d = json.load(f)
print(f'Drug classes: {len(d.get(\"drug_classes\", []))}')
for c in d['drug_classes']:
    print(f'  {c[\"class_id\"]}: {len(c.get(\"members\", []))} members')
"

# Refresh from RxClass API if new classes needed
python3 scripts/api_audit/seed_drug_classes.py --class-id <NEW_CLASS_ID>
```

**What to check:**
- Do any interaction rules reference a drug class that doesn't exist in `drug_classes.json`?
- Are there common drug classes missing? (Check: ACE inhibitors, beta blockers, statins, benzodiazepines, opioids)

---

### 8. Clinical Evidence Discovery

**What:** Queries ClinicalTrials.gov for completed trials on IQM ingredients. Cross-references with PubMed for published results. Identifies ingredients with strong clinical evidence that aren't yet in `backed_clinical_studies.json`.

**Why:** New clinical trials complete every quarter. Section C (Evidence & Research) scores depend on this data. Missing a major trial = underscoring a well-studied ingredient.

**How to run:**
```bash
python3 scripts/api_audit/discover_clinical_evidence.py discover --min-trials 3
```

**Options:**
```bash
--apply          # Auto-add entries (still requires PMID verification after)
--min-trials 5   # Only show ingredients with 5+ completed trials
--ingredient X   # Check a specific ingredient
```

**What to expect:**
- Output: candidates with NCT IDs, enrollment counts, publication PMIDs
- Typical: 5-15 new candidates per quarter

**Post-run:** Each candidate must have its PMIDs content-verified before adding to `backed_clinical_studies.json`.

---

### 9. IQM Alias Expansion

**What:** Identifies IQM ingredients that have poor matching because they lack aliases or CUI codes. Uses SUPPai data and UMLS API to find missing mappings.

**Why:** An ingredient without aliases won't match during enrichment, leading to "unmapped active" flags and lower scores. Adding aliases is low-risk (additive-only, no scoring impact).

**How to run:**
```bash
# Check current alias coverage
python3 -c "
import json
with open('scripts/data/ingredient_quality_map.json') as f:
    iqm = json.load(f)
no_alias = [k for k, v in iqm.items() if k != '_metadata' and not v.get('aliases')]
print(f'Entries without aliases: {len(no_alias)}/{len(iqm)-1}')
"

# Run UNII verification to find new mappings
python3 scripts/api_audit/verify_unii.py --file scripts/data/ingredient_quality_map.json --mode iqm
```

**What to expect:**
- Identify entries with zero aliases
- UMLS API suggests CUI mappings
- UNII cache provides chemical identity mappings

**Rules:**
- `NAME_EXACT` and `SYNONYM_EXACT` matches → safe to batch-add
- `TOKEN_OVERLAP_80` matches → manual chemistry review required (see Lessons Learned)
- New entries → full schema validation + UMLS API verification

---

## Before Every Release

### 10. Full Pipeline Run

**What:** Run the complete Clean → Enrich → Score pipeline on the latest dataset to verify everything works end-to-end.

**How to run:**
```bash
python3 scripts/run_pipeline.py <dataset_dir>
```

**What to check:**
- Zero errors in pipeline output
- Score distribution hasn't shifted dramatically (compare to previous run)
- Verdict distribution is reasonable (most products SAFE, few BLOCKED)

---

### 11. Coverage Gate

**What:** Validates that quality thresholds are met before release.

**How to run:**
```bash
python3 scripts/coverage_gate.py <scored_file>
```

**What to expect:**
- Pass: coverage ≥ 99.5%, all thresholds met
- Fail: identifies which metrics are below threshold

---

### 12. DB Integrity Check

**What:** Validates the final SQLite database schema and data integrity.

**How to run:**
```bash
python3 scripts/db_integrity_sanity_check.py
```

**What to check:**
- Column count matches expected (90)
- No NULL values in required fields
- Score ranges are valid (0-80 for score_80, 0-100 for score_100)

---

### 13. Test Suite

**What:** Run all tests. Every release must pass.

**How to run:**
```bash
python3 -m pytest scripts/tests/ -v
```

**Current baseline:** 598+ tests pass (as of Sprint 24).

**Known Python 3.9 issues:** ~41 test files require Python 3.11+ due to `datetime.UTC`. These pass on Python 3.13 but fail on the system Python 3.9. Not a data issue — just a runtime compatibility issue.

---

## API Audit Scripts Reference

These scripts verify data accuracy against external APIs. Run them when you modify the corresponding data file.

| Script | Data File | External API | When to Run |
|--------|-----------|-------------|-------------|
| `verify_cui.py` | `ingredient_quality_map.json` | UMLS API | After IQM changes |
| `verify_pubchem.py` | `ingredient_quality_map.json` | PubChem API | After adding CAS/CID |
| `verify_unii.py` | `ingredient_quality_map.json` | GSRS API (or local cache) | After IQM changes |
| `verify_rda_uls.py` | `rda_optimal_uls.json` | USDA FoodData Central | After dosing changes |
| `verify_efsa.py` | `harmful_additives.json` | EFSA API | After additive changes |
| `verify_clinical_trials.py` | `backed_clinical_studies.json` | ClinicalTrials.gov | After evidence changes |
| `verify_interactions.py` | `curated_interactions_v1.json` | RxNorm + UMLS | After interaction changes |
| `verify_depletion_timing_pmids.py` | `medication_depletions.json` | PubMed | After depletion changes |
| `verify_pubmed_references.py` | Multiple files | PubMed | After any PMID changes |
| `verify_all_citations_content.py` | All files with PMIDs | PubMed | **Before every release** |
| `audit_banned_recalled_accuracy.py` | `banned_recalled_ingredients.json` | openFDA | Before release |
| `audit_clinical_evidence_strength.py` | `backed_clinical_studies.json` | PubMed | Quarterly |
| `audit_clinical_sources.py` | `backed_clinical_studies.json` | — | Quarterly |

---

## API Keys

All keys are in `.env` at the repo root. Never commit this file.

| Key | Source | Used By |
|-----|--------|---------|
| `UMLS_API_KEY` | [UMLS License](https://uts.nlm.nih.gov/) | verify_cui.py, verify_interactions.py |
| `OPENFDA_API_KEY` | [openFDA](https://open.fda.gov/apis/authentication/) | fda_weekly_sync.py, fda_manufacturer_violations_sync.py |
| `PUBMED_API_KEY` | [NCBI](https://www.ncbi.nlm.nih.gov/account/) | All PubMed verification scripts |

---

## Troubleshooting

### "enricher takes too long"
- The UNII cache eliminates live GSRS API calls. Rebuild: `python3 scripts/api_audit/build_unii_cache.py --refresh`
- Check if API rate limits are being hit (look for 429 errors in logs)

### "test_score_supplements fails"
- If the error is `ImportError: cannot import name 'UTC' from 'datetime'` → you're on Python 3.9. Use Python 3.13 for full test coverage. This is a runtime issue, not a data issue.

### "CAERS signals file is empty"
- Re-run `python3 scripts/api_audit/ingest_caers.py --refresh`
- Check that `scripts/data/fda_caers/` directory exists (it's gitignored — you need to download)

### "UNII cache not found"
- Run `python3 scripts/api_audit/build_unii_cache.py` (downloads 3.4 MB, builds 14.9 MB cache)
- The cache is gitignored — each dev machine needs to build it locally

### "Drug label files missing"
- Download from `https://download.open.fda.gov/drug/label/`
- Place zips in `scripts/data/fda_drug_labels/` (gitignored — 130 MB per file)
- The miner will auto-unzip

### "Score distribution shifted after CAERS update"
- Expected: B8 penalties will lower scores for products with CAERS-flagged ingredients
- Check: Run the dashboard Section B Audit → CAERS tab to see which products are affected
- If too aggressive: adjust penalties in `scoring_config.json` → `B8_caers_adverse_events`
