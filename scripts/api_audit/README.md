# API Audit Runbook

This folder contains the external-verification, regulatory, and literature-audit tooling for PharmaGuide.

Keep these utilities here so they stay separate from the cleaning, enrichment, and scoring pipeline under `/scripts`.

## How to run these tools

- Always use the project virtual environment:
  - `.venv/bin/python ...`
- Use dry-run/report mode first.
- Use live network mode when the tool depends on FDA, PubMed, or UMLS.
- Treat generated reports as audit artifacts, not source-of-truth data.
- Treat retracted PubMed references, invalid CUIs, and broken FDA report contracts as blockers.

## Recommended operator sequence

1. Regulatory audit
   - Run `fda_weekly_sync.py` to produce the current FDA signal report.
2. Identity layer audit
   - Run `verify_cui.py` on the relevant database (UMLS CUIs).
   - Run `verify_pubchem.py` on the relevant database (CAS + PubChem CIDs).
   - Run `verify_unii.py` on the relevant database (FDA UNII + CFR + metabolic data).
   - Run `audit_banned_recalled_accuracy.py` as the banned/recalled release gate.
3. Literature audit
   - Run `verify_pubmed_references.py` on the file you are auditing.
   - Run `normalize_clinical_pubmed.py` on `backed_clinical_studies.json`.
   - Run `audit_clinical_evidence_strength.py` after normalization.
   - Run `verify_clinical_trials.py` on `backed_clinical_studies.json` (NCT ID verification).
   - Run `discover_clinical_evidence.py audit` to check all entries for internal consistency.
   - Run `discover_clinical_evidence.py discover --limit 20` to find missing high-value compounds.
   - Run `discover_clinical_evidence.py discover --limit 50 --apply` to add qualifying compounds with auto-populated key_endpoints and PubMed PMIDs.
   - Run `discover_clinical_evidence.py enrich --apply` to update enrollment data and registry completed-trial counts from ClinicalTrials.gov.
   - Run `discover_clinical_evidence.py backfill-auditability --limit 50 --apply` to add rationale/confidence/tags on the highest-impact entries first.
4. Bioactivity validation
   - Run `enrich_chembl_bioactivity.py` on `banned_recalled_ingredients.json` (mechanism of action confirmation).
5. EU regulatory validation
   - Run `verify_efsa.py` on `harmful_additives.json` (ADI/genotoxicity/EFSA opinion validation).
6. EPA toxicology validation
   - Run `verify_comptox.py` on `harmful_additives.json` (NOAEL/LOAEL/RfD, genotoxicity, cancer data from ToxValDB).
7. Alias accuracy audit
   - Run `audit_alias_accuracy.py` on each data file to check for wrong-molecule aliases and collisions.
8. Notes alignment audit
   - Run `audit_notes_alignment.py --all` to check prose fields against structured data across all files.
9. Apply curated fixes only after reviewing the reports.

## Script index

### `fda_weekly_sync.py`

Purpose:

- Pulls recall and warning signals from openFDA, FDA RSS, and DEA.
- Produces the FDA sync report used to review new recalls, already-tracked entries, and stale recall records.

Inputs:

- `.env` API keys and feed config.
- `scripts/data/banned_recalled_ingredients.json`.

Outputs:

- JSON report with new review records, tracked records, stale recalls, and source counts.

Common commands:

```bash
.venv/bin/python scripts/api_audit/fda_weekly_sync.py --days 7
.venv/bin/python scripts/api_audit/fda_weekly_sync.py --days 30 --output scripts/fda_sync_report_latest.json
```

Use it when:

- you want the weekly or monthly FDA review queue
- you want a fresh input report for `audit_banned_recalled_accuracy.py`

### `verify_cui.py`

Purpose:

- Verifies CUIs against UMLS.
- Confirms exact matches, flags mismatches, and respects intentional-null governance.
- Supports safe exact fills without blindly overwriting questionable existing CUIs.
- Supports both flat list files and the IQM top-level ingredient map.

Inputs:

- flat JSON files with a top-level list and `id` + `cui` fields
- `ingredient_quality_map.json` via `--mode iqm` so `_metadata` is skipped automatically and ingredient keys become IDs

Outputs:

- console summary and optional in-file safe updates when explicitly requested

Common commands:

```bash
.venv/bin/python scripts/api_audit/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --id-field id --cui-field cui
.venv/bin/python scripts/api_audit/verify_cui.py --file scripts/data/harmful_additives.json --list-key harmful_additives --id-field id --cui-field cui
.venv/bin/python scripts/api_audit/verify_cui.py --file scripts/data/ingredient_quality_map.json --mode iqm
.venv/bin/python scripts/api_audit/verify_cui.py --search "sildenafil"
```

Use it when:

- a file has missing, questionable, or newly added CUIs
- you want to confirm a synonym before deciding a null CUI is intentional
- you want to audit IQM directly without building a temporary flattened file

Key behavior:

- `--mode flat` expects a list-style file and uses `--list-key`
- `--mode iqm` reads the top-level IQM map directly, skips `_metadata`, and treats each ingredient key as the logical entry ID
- intentional-null entries should carry both `cui_status` and `cui_note`
- `--apply` remains conservative and only writes safe exact-match fills by default

### `audit_banned_recalled_accuracy.py`

Purpose:

- One-command release gate for `banned_recalled_ingredients.json`.
- Combines schema/integrity checks, entry-quality rules, CUI verification, and FDA-report ingestion.

Inputs:

- `scripts/data/banned_recalled_ingredients.json`
- optional FDA sync report
- optional live UMLS access

Outputs:

- JSON accuracy report with status `pass`, `warn`, or `fail`

Common commands:

```bash
.venv/bin/python scripts/api_audit/audit_banned_recalled_accuracy.py --fda-report-in scripts/fda_sync_report_latest.json
.venv/bin/python scripts/api_audit/audit_banned_recalled_accuracy.py --release --fda-report-in scripts/fda_sync_report_latest.json
.venv/bin/python scripts/api_audit/audit_banned_recalled_accuracy.py --release-strict-cui --fda-report-in scripts/fda_sync_report_latest.json
```

Use it when:

- you want a release/no-release answer for the banned/recalled DB
- you need the strict CUI gate before shipping

### `audit_clinical_sources.py`

Purpose:

- Audits `backed_clinical_studies.json` for source breadcrumbs and obvious contradiction patterns.
- This is the lightweight source-presence audit, not the PubMed normalization pass.

Use it when:

- you want a quick check that human-evidence entries actually cite something traceable

### `pubmed_client.py`

Purpose:

- Shared NCBI E-utilities client for PubMed work.
- Handles env loading, retry, timeout, cache, batching, DOI lookup, `efetch`, `esearch`, `esummary`, `elink`, `epost`, and `ecitmatch`.

Key behavior:

- uses `NCBI_API_KEY` or `PUBMED_API_KEY`
- uses `.env` values for `tool` and `email` when available
- batches large PMID fetches so clinical normalization does not fail with `414 URI Too Long`

### `verify_pubmed_references.py`

Purpose:

- Verifies DOI/PMID references in a JSON file.
- Resolves DOI -> PMID where possible.
- Flags broken PMIDs, broken DOIs, and retracted PubMed references.
- Enriches each entry’s references in the report with PubMed metadata.

Inputs:

- any JSON file
- top-level list key

Outputs:

- JSON report with:
  - `broken_pmids`
  - `broken_dois`
  - `retracted_references`
  - `enriched_entries`

Common commands:

```bash
.venv/bin/python scripts/api_audit/verify_pubmed_references.py --file scripts/data/harmful_additives.json --list-key harmful_additives
.venv/bin/python scripts/api_audit/verify_pubmed_references.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients
.venv/bin/python scripts/api_audit/verify_pubmed_references.py --file scripts/data/backed_clinical_studies.json --list-key backed_clinical_studies
```

Use it when:

- you need to catch hallucinated or stale PubMed references
- you want to confirm that recently edited PMIDs/DOIs still resolve

### `normalize_clinical_pubmed.py`

Purpose:

- Normalizes `backed_clinical_studies.json` into structured evidence refs.
- Extracts PMIDs from `notable_studies`, including `PMID:` and `PMIDs:` blocks.
- Uses ECitMatch for certain structured citation patterns.
- Preserves curated non-PubMed refs such as NIH ODS or formulary references.
- Fetches PubMed metadata in batches and writes normalized `references_structured`.

Inputs:

- `scripts/data/backed_clinical_studies.json`

Outputs:

- report with:
  - `entries_with_pmids`
  - `entries_updated`
  - `missing_pmids`
  - `unresolved_entries`

Common commands:

```bash
.venv/bin/python scripts/api_audit/normalize_clinical_pubmed.py --file scripts/data/backed_clinical_studies.json
.venv/bin/python scripts/api_audit/normalize_clinical_pubmed.py --file scripts/data/backed_clinical_studies.json --apply
```

Use it when:

- `backed_clinical_studies.json` has prose PMIDs that need structured refs
- new clinical entries were added
- you need the unresolved clinical review queue

### `audit_clinical_evidence_strength.py`

Purpose:

- Compares claimed `study_type` values against the structured PubMed evidence currently attached to each clinical entry.
- Flags:
  - overstated study types
  - missing structured support
  - retracted references
- Ignores curated non-PubMed refs for evidence-strength grading so nutrient/formulary entries are not penalized for lacking PubMed RCTs.

Inputs:

- `scripts/data/backed_clinical_studies.json`

Outputs:

- JSON report with:
  - `mismatches`
  - `issues`
  - summary counts

Common commands:

```bash
.venv/bin/python scripts/api_audit/audit_clinical_evidence_strength.py --file scripts/data/backed_clinical_studies.json
```

Use it when:

- you want the real clinical review queue after PubMed normalization
- you need to confirm that study-type downgrades or evidence replacements worked

### `verify_pubchem.py`

Purpose:

- Verifies and fills CAS numbers and PubChem CIDs using the PubChem PUG REST API.
- Validates existing CAS numbers against PubChem's records.
- Supports flat files (harmful_additives, banned_recalled) and nested IQM (ingredient → forms).
- Skips umbrella/proprietary/multi-compound entries by design.
- In IQM mode, skips formulation-style forms that are not single PubChem compounds, such as unspecified buckets, blends, extracts, coated/liquid delivery systems, and probiotic-style formats.
- No API key needed — PubChem PUG REST is free and open.

Inputs:

- any JSON file (flat or IQM structure)

Outputs:

- console report with verified, filled, mismatched, ambiguous, not-found, and skipped counts
- optional in-file CAS/CID fills when `--apply` is used for accepted single-compound matches only
- explicit `governed_null` handling for curated polymer/mixture entries that should keep null PubChem CID or curated CAS-only values

Common commands:

```bash
# Dry-run harmful_additives
.venv/bin/python scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives

# Dry-run banned/recalled
.venv/bin/python scripts/api_audit/verify_pubchem.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients

# Dry-run IQM (forms-level verification)
.venv/bin/python scripts/api_audit/verify_pubchem.py --file scripts/data/ingredient_quality_map.json --mode iqm

# Apply safe CAS/CID fills
.venv/bin/python scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply

# Search a single compound
.venv/bin/python scripts/api_audit/verify_pubchem.py --search "magnesium glycinate"

# Look up a CID
.venv/bin/python scripts/api_audit/verify_pubchem.py --cid 11177
```

Use it when:

- a file has missing CAS numbers or PubChem CIDs
- you need to validate existing CAS numbers against PubChem's registry
- you want to build the chemical identity layer (CAS + CID) alongside CUI

Key behavior:

- rate-limited to ~4.5 req/s (PubChem limit is 5/s)
- caches responses for 30 days in `.cache/pubchem_cache.json`
- circuit breaker after 3 consecutive failures
- rejects unsafe short-alias matches instead of auto-filling them
- skips known polymer / umbrella / mixed entries such as PEG, PVP, nitrite+nitrate buckets, and IQM formulation placeholders
- classifies known polymer/mixture edge cases such as HFCS, PEG, PVP, carrageenan, maltodextrin, polydextrose, and CMC under curated `governed_null` policy instead of noisy `not_found`

### `fda_manufacturer_violations_sync.py`

Purpose:

- Automatically sync manufacturer violation entries from FDA/openFDA feeds into `scripts/data/manufacturer_violations.json`.
- Includes attention to supplement-specific substance signal detection and existing DB deduplication.
- Calculates derived fields (recency, deduction, manufacturer scoring flags) to keep the manual penalties table fresh.
- Recalculates existing entries against the deduction framework on each run (`days_since_violation`, recency, repeat flags, total deduction).
- Preserves curated `manufacturer_family_*` score-bearing fields and non-scoring `related_brand_cluster_*` fields when present.
- Emits a structured report with full new-entry details.

Inputs:

- `scripts/data/manufacturer_violations.json` (current DB)
- openFDA feed data from `food/enforcement` and `drug/enforcement`
- optionally FDA RSS (via `--include-rss`)
- `.env` openFDA API key (`OPENFDA_API_KEY`) or `--api-key`

Outputs:

- Updated `scripts/data/manufacturer_violations.json` (appended with new entries, metadata updated)
- JSON report at `scripts/api_audit/reports/fda_manufacturer_violations_sync_report_<YYYYMMDD>.json` (or `--report` custom path)

Notes:

- `manufacturer_family_id` is score-bearing and only for explicit, high-confidence family relationships.
- `related_brand_cluster_id` is non-scoring metadata for operator review and explainability; it should not drive repeat penalties by itself.

Common commands:

```bash
.venv/bin/python scripts/api_audit/fda_manufacturer_violations_sync.py --days 30 --dry-run
.venv/bin/python scripts/api_audit/fda_manufacturer_violations_sync.py --days 30 --include-rss --dry-run
.venv/bin/python scripts/api_audit/fda_manufacturer_violations_sync.py --days 30 --include-rss --confirm
.venv/bin/python scripts/api_audit/fda_manufacturer_violations_sync.py --days 30 --include-rss
.venv/bin/python scripts/api_audit/fda_manufacturer_violations_sync.py --days 30 --report scripts/api_audit/my_mfr_sync_report.json
```

Use it when:

- you want to keep `manufacturer_violations.json` synchronized with the latest FDA recall activity
- you need a proactive manufacturer-risk signal pipeline for review
- you want traceable evidence in a per-run report for audit and PR chain of custody

- IQM mode uses the form name first and only one non-ambiguous alias fallback to keep first-run latency bounded
- CAS mismatches are reported but NOT auto-fixed (require manual review)
- CID mismatches are reported but NOT auto-fixed
- "ambiguous match" means the lookup produced a candidate that was deliberately rejected as unsafe for auto-fill
- "not found" entries are typically polymers, mixtures, extracts, or proprietary blends — PubChem tracks single compounds

### `verify_unii.py`

Purpose:

- Queries the FDA GSRS (Global Substance Registration System) API to populate UNII codes and extract regulatory/metabolic data.
- Persists:
  - `external_ids.unii`
  - top-level `rxcui` when GSRS provides one
  - top-level `gsrs` block with `substance_name`, `substance_class`, `cfr_sections`, `dsld_count`, `dsld_info_raw`, `active_moiety`, `salt_parents`, `metabolic_relationships`, and `metabolites`
- Does not overwrite:
  - CAS or PubChem CID (PubChem remains authority)
  - CUI (UMLS remains authority)
- Supports flat files (harmful_additives, banned_recalled) and nested IQM.
- No API key needed — GSRS is free and public.

Inputs:

- any JSON file (flat or IQM structure)

Outputs:

- console report with filled, rejected, governed-null, not-found, and skipped counts
- optional in-file UNII/RxCUI/GSRS enrichment when `--apply` is used

Common commands:

```bash
# Dry-run harmful_additives
.venv/bin/python scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives

# Dry-run banned/recalled
.venv/bin/python scripts/api_audit/verify_unii.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients

# Dry-run IQM
.venv/bin/python scripts/api_audit/verify_unii.py --file scripts/data/ingredient_quality_map.json --mode iqm

# Apply safe fills
.venv/bin/python scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply

# Search a substance
.venv/bin/python scripts/api_audit/verify_unii.py --search "curcumin"
```

Use it when:

- you need UNII codes to enable deterministic FDA recall matching in fda_weekly_sync.py
- you want to verify or populate 21 CFR regulatory references
- you need metabolic enzyme/substrate data for drug interaction warnings
- you want salt/parent form mappings for identity resolution
- you want active-moiety context to connect salts/esters/prodrugs back to the core ingredient
- you want RxCUI where GSRS exposes it, especially for IQM actives and banned/recalled drug adulterants

Key behavior:

- rate-limited to 2 req/s (conservative for government API)
- caches responses for 30 days in `.cache/gsrs_cache.json`
- circuit breaker after 3 consecutive failures
- **match validation gate**: CAS cross-reference required when available — rejects if our CAS ≠ GSRS CAS
- rejects short/ambiguous name matches (PEG, PVP, etc.) using word-boundary checks
- skips polymer, class, umbrella, and multi-compound entries
- validates existing UNIIs against live GSRS before treating them as verified
- IQM mode searches by ingredient name, then key fallback, then form aliases, and still applies the same post-match CAS gate
- CAS mismatches are reported as "rejected" and NOT auto-applied (require manual review)
- known mixture/proprietary/non-exact records can be classified as `governed_null` so future runs stay deterministic instead of repeatedly surfacing the same unsafe GSRS near-match
- retries transient GSRS `500/502/503/504/429` failures with backoff

Recommended field usage in PharmaGuide:

- `UNII`:
  Use broadly. This is GSRS's strongest contribution and the best FDA-aligned substance identifier for identity resolution.
- `21 CFR sections`:
  High value for harmful additives and food-additive/regulatory substances. Lower value for general clinical/nutrient entries.
- `Metabolic relationships`:
  Use where interaction logic matters. Most useful for active drugs, adulterants, and ingredients with known enzyme/target relationships.
- `Salt/parent mapping`:
  Use where form normalization matters. High value for banned/recalled adulterants and IQM active-ingredient identity.
- `Active moiety`:
  Use where different salts/esters/prodrug-like forms should roll up to one core ingredient.
- `RxCUI`:
  Useful when GSRS exposes a real RxNorm concept, especially for IQM pharmaceutical actives and banned/recalled drug ingredients. Do not force it onto supplement-only or class records.

### `verify_clinical_trials.py`

Purpose:

- Verifies NCT IDs found in `backed_clinical_studies.json` against ClinicalTrials.gov API v2.
- Cross-checks study design (interventional/observational) against claimed `study_type`.
- Flags broken NCT IDs, study type mismatches, and entries without NCT IDs.

Inputs:

- `scripts/data/backed_clinical_studies.json`

Outputs:

- Console summary and optional JSON report.

Common commands:

```bash
.venv/bin/python scripts/api_audit/verify_clinical_trials.py --file scripts/data/backed_clinical_studies.json
.venv/bin/python scripts/api_audit/verify_clinical_trials.py --nct NCT03675724
.venv/bin/python scripts/api_audit/verify_clinical_trials.py --file scripts/data/backed_clinical_studies.json --output /tmp/ct_verify_report.json
```

Use it when:

- clinical entries reference ClinicalTrials.gov NCT IDs that need verification
- you want to confirm that study_type claims match the actual trial design

Key behavior:

- Free API, no key needed
- Rate-limited to ~2.8 req/s
- Caches responses for 30 days in `.cache/clinical_trials_cache.json`
- Circuit breaker after 3 consecutive failures

### `enrich_chembl_bioactivity.py`

Purpose:

- Enriches `banned_recalled_ingredients.json` with ChEMBL bioactivity and mechanism of action data.
- Flags explicit prose contradictions when notes/reason say the mechanism is unknown but ChEMBL has known mechanism/target data.
- Adds `chembl_id`, mechanism, and target data for drug adulterants, SARMs, steroids, and stimulants.

Inputs:

- `scripts/data/banned_recalled_ingredients.json`

Outputs:

- Console summary and optional JSON report.
- Optional in-file enrichment when `--apply` is used (adds `external_ids.chembl_id` and `chembl` block).
- Report includes `claim_review_needed` for entries whose prose explicitly conflicts with known ChEMBL mechanism data.

Common commands:

```bash
.venv/bin/python scripts/api_audit/enrich_chembl_bioactivity.py --file scripts/data/banned_recalled_ingredients.json
.venv/bin/python scripts/api_audit/enrich_chembl_bioactivity.py --search "sildenafil"
.venv/bin/python scripts/api_audit/enrich_chembl_bioactivity.py --file scripts/data/banned_recalled_ingredients.json --apply
```

Use it when:

- you want to confirm that drug adulterants have the pharmacological activity described in clinical_notes
- you want to catch explicit prose contradictions before publishing mechanism language
- you want ChEMBL IDs for cross-referencing with other chemical databases
- you need mechanism of action data for banned/recalled substances

Key behavior:

- Free API, no key needed
- Rate-limited to ~4 req/s
- Caches responses for 30 days in `.cache/chembl_cache.json`
- Circuit breaker after 3 consecutive failures
- Only processes pharmacologically active entries (adulterants, SARMs, steroids, stimulants)

### `discover_clinical_evidence.py`

Purpose:

- **Three-in-one tool** for clinical evidence discovery, auditing, and enrichment.
- **DISCOVER**: Finds IQM compounds missing from `backed_clinical_studies.json`, queries ClinicalTrials.gov and ChEMBL for trial count, enrollment, phase data, safety flags, and **primary/secondary outcome measures**, then generates candidate entries. With `--apply`, auto-populates `key_endpoints` from registered outcome measures, records `registry_completed_trials_count`, derives coarse `endpoint_relevance_tags`, and carries conservative `effect_direction` auditability fields for human review.
- **AUDIT**: Cross-references ALL existing entries for internal consistency — catches notes-vs-classification contradictions, enrollment plausibility issues, BRAND* misclassification, PRECLIN* entries with human trial data.
- **ENRICH**: Populates `total_enrollment` for entries with missing or low values and refreshes `registry_completed_trials_count` broadly by querying ClinicalTrials.gov for the completed trial set per compound.
- **BACKFILL-AUDITABILITY**: Prioritizes the highest-impact entries missing auditability fields, queries ClinicalTrials.gov for outcome text and completed-trial counts, and writes `effect_direction_rationale`, `effect_direction_confidence`, and `endpoint_relevance_tags` without changing score math.

APIs used:

- ClinicalTrials.gov API v2 (free, no key) — trial search, outcome measures, enrollment
- ChEMBL REST API (free, no key) — compound safety flags, max_phase
- NCBI PubMed E-utilities (requires `NCBI_API_KEY` in `.env`) — NCT-to-PMID cross-referencing

Inputs:

- `scripts/data/backed_clinical_studies.json`
- `scripts/data/ingredient_quality_map.json` (for discover mode gap detection)

Outputs:

- JSON reports auto-saved to `scripts/api_audit/reports/` (timestamped, no `--output` needed).
- Optional in-file updates when `--apply` is used (discover adds entries with auto-populated `key_endpoints`, enrich updates enrollment).
- Entries with auto-populated endpoints note "Key endpoints auto-populated from registered outcome measures with PubMed cross-references."
- Entries where no outcome measures were found note "Requires human review for key_endpoints."

Common commands:

```bash
# Discover top 20 missing compounds (dry-run — report only)
python3 scripts/api_audit/discover_clinical_evidence.py discover --limit 20

# Discover and auto-add qualifying compounds (>= 5 completed trials)
# Key endpoints auto-populated with PubMed PMIDs when available
python3 scripts/api_audit/discover_clinical_evidence.py discover --limit 50 --apply --min-trials 5

# Discover a single compound
python3 scripts/api_audit/discover_clinical_evidence.py discover --compound "spirulina"

# Audit entire clinical DB for consistency issues
python3 scripts/api_audit/discover_clinical_evidence.py audit

# Enrich enrollment data (dry-run)
python3 scripts/api_audit/discover_clinical_evidence.py enrich

# Enrich enrollment data (apply changes)
python3 scripts/api_audit/discover_clinical_evidence.py enrich --apply

# Backfill auditability on the top 50 highest-impact entries
python3 scripts/api_audit/discover_clinical_evidence.py backfill-auditability --limit 50 --apply

# Save report to custom path
python3 scripts/api_audit/discover_clinical_evidence.py audit --output scripts/reports/my_audit.json
```

Use it when:

- you want to grow the clinical evidence DB by finding well-studied compounds not yet covered
- you need a health check on all existing entries (run after any manual edits)
- you want to improve enrollment accuracy for the enrollment quality multiplier
- you added new entries manually and want to verify internal consistency
- you want `key_endpoints` auto-filled instead of empty arrays (the `--apply` flag now handles this)

Key behavior:

- Free APIs, no keys needed (ClinicalTrials.gov v2 + ChEMBL REST)
- Rate-limited to ~2.8 req/s
- 30-day disk cache in `.cache/` (avoids redundant API calls)
- Circuit breaker after 3 consecutive failures
- Dry-run by default — `--apply` required to write changes
- `--min-trials` (default 3) controls the quality floor for auto-added entries
- Auto-added entries include: `id`, `standard_name`, `aliases`, `evidence_level`, `study_type`, `effect_direction`, `effect_direction_confidence`, `effect_direction_rationale`, `registry_completed_trials_count`, `total_enrollment`, `primary_outcome`, `endpoint_relevance_tags`, `references_structured`, `notable_studies`
- `backfill-auditability` is intentionally explainability-only: it does not change score math, verdicts, or the curated `effect_direction` label itself
- Metadata (`total_entries`, `last_updated`, `changelog`) updated automatically on `--apply`
- Reports always saved to `scripts/api_audit/reports/` (never just printed to stdout)
- Compounds with ChEMBL `withdrawn_flag` or `black_box_warning` are skipped by `--apply` (require manual review)

### `verify_efsa.py`

Purpose:

- Validates EU regulatory claims in `harmful_additives.json` against the curated EFSA OpenFoodTox reference dataset.
- Checks ADI values, genotoxicity status, EFSA opinion staleness, IARC classifications, and EU/US regulatory divergence.

Inputs:

- `scripts/data/harmful_additives.json`
- `scripts/data/efsa_openfoodtox_reference.json` (curated EFSA reference)

Outputs:

- Console summary and optional JSON report.
- Flags: ADI mismatches, stale opinions (>8 years), genotoxicity gaps, EU/US divergence, available enrichments.

Common commands:

```bash
.venv/bin/python scripts/api_audit/verify_efsa.py --file scripts/data/harmful_additives.json
.venv/bin/python scripts/api_audit/verify_efsa.py --search "aspartame"
.venv/bin/python scripts/api_audit/verify_efsa.py --update-reference /path/to/openfoodtox.csv
```

Use it when:

- you want to validate EU regulatory data in harmful_additives.json
- you need to check if ADI values match current EFSA/JECFA evaluations
- you want to identify substances with genotoxicity concerns not mentioned in our notes
- EFSA has published new opinions that may update ADI values

Key behavior:

- No API calls (local reference dataset comparison)
- EFSA reference can be refreshed from downloaded OpenFoodTox CSV via `--update-reference`
- 10% tolerance on ADI value comparison (floating point differences)
- Flags opinions older than 8 years as potentially stale

### `verify_comptox.py`

Purpose:

- Verifies and enriches `harmful_additives.json` with EPA CompTox ToxValDB data.
- Fills the empty `dose_thresholds` field with NOAEL, LOAEL, RfD, BMD/BMDL values.
- Validates our ADI values against EPA IRIS, ATSDR, and other ToxValDB sources.
- Fetches genotoxicity assay results and cancer slope factors.
- Resolves CAS → DTXSID for cross-referencing with the full CompTox dashboard.

Inputs:

- `scripts/data/harmful_additives.json`
- Requires `COMPTOX_API_KEY` environment variable.

Outputs:

- Console summary and optional JSON report.
- Optional in-file enrichment when `--apply` is used (fills `dose_thresholds` + adds `dtxsid` to `external_ids`).

How to get the API key:

- Email `ccte_api@epa.gov` with subject "API Key Request".
- Free, no justification needed. Takes 1-2 business days.
- Add to your `.env` file: `COMPTOX_API_KEY=your_key_here`

Common commands:

```bash
# Dry-run on harmful_additives
.venv/bin/python scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json

# Look up a single substance
.venv/bin/python scripts/api_audit/verify_comptox.py --cas 80-05-7
.venv/bin/python scripts/api_audit/verify_comptox.py --search "bisphenol A"

# Apply dose_thresholds enrichment
.venv/bin/python scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json --apply

# Save report
.venv/bin/python scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json --output /tmp/comptox_report.json
```

Use it when:

- you want to fill the 105 empty `dose_thresholds` fields with authoritative NOAEL/LOAEL/RfD values
- you want to cross-validate ADI values against EPA IRIS reference doses
- you need cancer slope factors for IARC-classified entries
- you want quantitative genotoxicity assay results (not just positive/negative)

Key behavior:

- Requires free API key (email ccte_api@epa.gov)
- Rate-limited to ~2 req/s
- Caches responses for 30 days in `.cache/comptox_cache.json`
- Circuit breaker after 3 consecutive failures
- Resolves CAS → DTXSID via Chemical API, then queries Hazard/Genetox/Cancer endpoints
- Only processes entries with CAS numbers (71/112 harmful additives)
- 50% tolerance on ADI comparison (different methodologies produce different values)

### `audit_alias_accuracy.py`

Purpose:

- Checks whether each alias in a data file actually refers to the correct molecule.
- Cross-references aliases against GSRS names and PubChem synonyms for the entry's UNII/CID.
- Detects alias collisions (same alias in 2+ entries = false mapping risk).
- Detects duplicate aliases within entries.

Common commands:

```bash
# Check a file (collisions + duplicates only, fast)
.venv/bin/python scripts/api_audit/audit_alias_accuracy.py --file scripts/data/harmful_additives.json --mode flat --list-key harmful_additives --no-external

# Full external API verification (checks every alias against GSRS/PubChem)
.venv/bin/python scripts/api_audit/audit_alias_accuracy.py --file scripts/data/harmful_additives.json --mode flat --list-key harmful_additives

# IQM mode
.venv/bin/python scripts/api_audit/audit_alias_accuracy.py --file scripts/data/ingredient_quality_map.json --mode iqm
```

### `audit_notes_alignment.py`

Purpose:

- Cross-references prose fields (notes, mechanism_of_harm, notable_studies, reason) against structured fields and external data.
- Catches five categories of misalignment: CONTRADICTION, OVERSTATEMENT, STALE_CLAIM, NUMERIC_MISMATCH, UNSUPPORTED_CLAIM.
- Deterministic pattern-matching — no AI or LLM dependency.
- Auto-detects database type from file structure, or accepts `--db` override.
- JSON output now includes a top-level `summary` plus per-database `results` for easier release gating.

Inputs:

- Any PharmaGuide JSON data file (clinical, additives, banned, or generic).

Outputs:

- Console summary grouped by issue type.
- Optional JSON report via `--output`.

Common commands:

```bash
# Audit all three core files
.venv/bin/python scripts/api_audit/audit_notes_alignment.py --all

# Audit a single file (auto-detects type)
.venv/bin/python scripts/api_audit/audit_notes_alignment.py --file scripts/data/harmful_additives.json

# Audit any JSON file with explicit list key
.venv/bin/python scripts/api_audit/audit_notes_alignment.py --file scripts/data/ingredient_interaction_rules.json --list-key interaction_rules

# Save report
.venv/bin/python scripts/api_audit/audit_notes_alignment.py --all --output /tmp/notes_alignment_report.json
```

Use it when:

- after editing prose fields (notes, mechanism_of_harm, reason) to catch inconsistencies before commit
- as a release gate alongside the structured-field verification scripts
- when new entries are added and you want to verify notes match the structured data

What it checks:

- study_type says rct but prose only mentions animal/in-vitro evidence
- prose says "no RCT" but study_type is rct_single/rct_multiple
- severity_level is low but prose mentions fatal/organ-failure outcomes
- high severity but prose says "no safety concern"
- ADI values in prose don't match regulatory_status numbers
- causal language ("causes", "proven to") on weak/observational evidence
- preclinical evidence_level but prose implies human-level confidence
- percentage claims or study references without PMID/DOI backing
- GRAS/FDA-approved claims on banned entries without historical context
- banned status but reason text suggests watchlist-level assessment

## Curated overrides

Curated override files are stored in `data/curated_overrides/`:

- `cui_overrides.json` — CUI overrides for verify_cui.py
- `pubchem_policies.json` — PubChem entry policies and skip names for verify_pubchem.py
- `gsrs_policies.json` — GSRS/UNII entry policies and skip names for verify_unii.py

To add a new curated override, edit the relevant JSON file directly. No Python changes needed. Each script falls back to its hardcoded defaults if the JSON file is missing.

## PubMed workflow

For `backed_clinical_studies.json`, use this order:

```bash
.venv/bin/python scripts/api_audit/verify_pubmed_references.py --file scripts/data/backed_clinical_studies.json --list-key backed_clinical_studies --output /tmp/backed_clinical_pubmed_verify.json
.venv/bin/python scripts/api_audit/normalize_clinical_pubmed.py --file scripts/data/backed_clinical_studies.json --output-report /tmp/clinical_pubmed_normalization_report.json
.venv/bin/python scripts/api_audit/audit_clinical_evidence_strength.py --file scripts/data/backed_clinical_studies.json --output-report /tmp/clinical_evidence_strength_report.json
```

Interpretation:

- `verify_pubmed_references.py`
  - `retracted_references > 0` is a blocker
  - `broken_pmids > 0` means references need repair
- `normalize_clinical_pubmed.py`
  - `unresolved_entries > 0` means entries still need better citation seeds or curated non-PubMed refs
- `audit_clinical_evidence_strength.py`
  - `mismatches > 0` means the file is over-claiming the current evidence level

## What each tool verifies (and what it does not)

### Structured-field verification (automated)

Each script validates a specific slice of the data against an authoritative external source:

| Tool                                  | What it verifies                                                                                               | External source                                                  |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `verify_cui.py`                       | CUI identity — does this UMLS concept ID resolve to the intended substance?                                    | UMLS REST API                                                    |
| `verify_unii.py`                      | UNII codes, 21 CFR sections, salt/parent/moiety relationships, metabolic data                                  | FDA GSRS API                                                     |
| `verify_pubchem.py`                   | CAS numbers, PubChem CIDs — is the chemical identity correct?                                                  | PubChem PUG REST                                                 |
| `verify_pubmed_references.py`         | PMIDs/DOIs exist, papers are not retracted, metadata is fetchable                                              | PubMed E-utilities                                               |
| `verify_clinical_trials.py`           | NCT IDs exist, trial design matches claimed study_type                                                         | ClinicalTrials.gov API v2                                        |
| `enrich_chembl_bioactivity.py`        | Mechanism of action and pharmacological targets for drug-like adulterants                                      | ChEMBL REST API                                                  |
| `discover_clinical_evidence.py`       | Clinical evidence gaps, entry consistency, enrollment accuracy, auto-populated key_endpoints with PubMed PMIDs | ClinicalTrials.gov API v2 + ChEMBL REST API + PubMed E-utilities |
| `verify_efsa.py`                      | ADI values, genotoxicity, EFSA opinion currency, EU/US regulatory divergence                                   | Curated EFSA OpenFoodTox reference                               |
| `fda_weekly_sync.py`                  | Recall and safety signal truth — new FDA/DEA actions affecting our DB                                          | openFDA, FDA RSS, DEA Federal Register                           |
| `audit_clinical_evidence_strength.py` | study_type claims match PubMed publication type metadata                                                       | PubMed publication types                                         |
| `audit_banned_recalled_accuracy.py`   | Schema integrity, FDA report alignment, CUI governance for banned/recalled DB                                  | Internal + UMLS + FDA report                                     |
| `verify_comptox.py`                   | NOAEL/LOAEL/RfD dose thresholds, genotoxicity assays, cancer slope factors, ADI cross-validation               | EPA CompTox ToxValDB (249K records, 51 sources)                  |
| `audit_alias_accuracy.py`             | Wrong-molecule aliases, alias collisions across entries, duplicate aliases                                     | GSRS names + PubChem synonyms cross-reference                    |
| `audit_notes_alignment.py`            | Prose-vs-structured contradictions, overstatements, stale claims, numeric mismatches, unsupported claims       | Pattern matching against own structured fields                   |

### What these tools do NOT verify

The automated pipeline checks **structured fields and identifiers** against external APIs. It does not judge whether your **free-text prose** (notes, mechanism_of_harm, notable_studies, clinical_notes) is:

- **Overstated** — claiming stronger effects than the cited evidence supports
- **Missing nuance** — omitting dose-dependence, population-specificity, or confidence intervals
- **Mixing evidence levels** — citing a single mouse study alongside RCTs without distinguishing strength
- **Implying unsupported causality** — using "causes" when evidence only shows "associated with"
- **Inconsistent with structured fields** — notes describing an RCT while study_type says observational

### Recommended approach for prose review

Free-text validation requires human or AI-assisted review. When editing prose fields:

1. **Cross-check notes against cited PMIDs.** Read the actual abstract (use `verify_pubmed_references.py --file ... --output` to get metadata) and confirm the notes accurately summarize the findings.
2. **Match strength language to evidence level.** Use "may", "suggests", or "associated with" for observational data. Reserve "demonstrates" or "shows" for well-powered RCTs.
3. **Flag when no-match diagnostics suggest missing data.** If `verify_efsa.py` or `verify_cui.py` reports "not found" with a hint like "missing CAS" or "no E-number alias", the entry may need an alias or identifier added — not a prose rewrite.
4. **Use AI review for batch prose auditing.** These tools surface the entries that need attention; a Claude or GPT pass over the flagged entries' notes can efficiently check for the issues listed above.

## Operator rules

1. Run dry-run/report mode first, then apply curated changes.
2. Treat retracted PubMed references as release blockers.
3. Do not force a CUI onto class, umbrella, proprietary, or ambiguous records.
4. Prefer adding missing exact aliases before accepting a null CUI.
5. Preserve non-PubMed structured refs when those are the correct evidence source, especially for nutrient fact-sheet or formulary entries.
6. Keep compatibility wrappers in `/scripts` only to avoid breaking older commands and tests; new docs and operator habits should point here.
7. When a script reports "not found", check the diagnostic hints before assuming the data is absent. Missing aliases, CAS numbers, or E-numbers are the most common cause of false negatives.
