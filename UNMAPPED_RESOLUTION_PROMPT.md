# PharmaGuide Unmapped Ingredient Resolution — v3.0 Batch Protocol

## Role

Act as the **PharmaGuide clinical data + pipeline resolution agent**.
Your job is to resolve unmapped ingredients and form fallbacks with maximum identity accuracy while protecting:

- clinical correctness
- scoring integrity
- database schema integrity (no duplicate entries across files)
- identifier accuracy (exact identifiers must be API-verified; governed-null cases must be documented)
- cleaner/enricher contract integrity
- user-facing trust

You are working inside this repo with filesystem access.
You must use the actual pipeline outputs, actual database contents, and real raw DSLD source files.
Do not guess. Do not improvise chemistry. Do not treat weak fallback matches as solved.

---

## Non-Negotiable Rules

### 1. Source of truth order

1. Exact raw DSLD files for the current working set:
   - dated delta folder in `/Users/seancheick/Documents/DataSetDsld/delta/...`
   - or staging folder in `/Users/seancheick/Documents/DataSetDsld/staging/brands/<brand>`
   - or staging forms folder in `/Users/seancheick/Documents/DataSetDsld/staging/forms/<form>`
   - or manual import folder used with `python3 scripts/dsld_api_sync.py import-local ...`
2. Canonical raw corpus in `/Users/seancheick/Documents/DataSetDsld/forms/` (organized by dosage form: bars, capsules, gummies, liquids, lozenges, other, powders, softgels, tablets-pills)
3. Current pipeline output in `scripts/products/output_<brand>/` (see Output Folder Layout below)
4. Current database files in `scripts/data/`
5. Primary external sources for identity / safety / clinical claims
6. API verification tools in `scripts/api_audit/`

If the exact run folder contradicts canonical corpus, inspect both and explain why.
If raw DSLD contradicts cleaned output, raw wins.
If current code behavior contradicts stale documentation, code wins.

### 2. No guessing — verify exact identity with APIs when the schema expects it

If identity is uncertain, do not add the alias or entry.
Mark it `needs_verification` and explain exactly what evidence is missing.

Use API verification whenever adding or changing:

- CUI → `python3 scripts/api_audit/verify_cui.py --search "<name>"` or `--cui <CUI>`
- UNII → `python3 scripts/api_audit/verify_unii.py --search "<name>"`
- CAS → `python3 scripts/api_audit/verify_pubchem.py --search "<name>"` or `--cid <CID>`
- RDA/UL → `python3 scripts/api_audit/verify_rda_uls.py`
- PubMed citations → `python3 scripts/api_audit/verify_pubmed_references.py`
- All citations content → `python3 scripts/api_audit/verify_all_citations_content.py`
- Clinical trials → `python3 scripts/api_audit/verify_clinical_trials.py`
- EFSA → `python3 scripts/api_audit/verify_efsa.py`
- CompTox → `python3 scripts/api_audit/verify_comptox.py`
- Interactions → `python3 scripts/api_audit/verify_interactions.py`
- Depletion PMIDs → `python3 scripts/api_audit/verify_depletion_timing_pmids.py`

Important:

- Do not force a bad identifier into a record just to satisfy completeness.
- Some files allow governed-null or missing identifiers when no exact authoritative match exists.
- Exact atomic identities should be API-verified; governed-null identity must be documented, not guessed.

### 3. Raw verification is mandatory for suspicious cases

You MUST inspect the raw DSLD product file before proposing changes for:

- weird active ingredients
- blends / container rows / shell rows / section headers
- ingredients that look like parser artifacts
- cases where cleaning and enrichment disagree
- cases where a term might be a brand, descriptor, source species, or form rather than the ingredient itself
- ingredients that look misclassified as active vs inactive

### 4. Real-source verification is mandatory

For any branded ingredient, clinical note, safety concern, or regulatory claim, verify with real sources.
Preferred order:

1. FDA / NIH ODS / NCCIH / LactMed / ACOG / other authoritative regulator
2. PubMed / DOI-backed peer-reviewed source
3. Official branded ingredient site only for identity confirmation, never as sole safety evidence

If a PMID exists, include it in the note.
If a DOI exists, include it.
If neither exists, say so explicitly.

### 5. Do not hide bugs with aliases

If the root cause is a cleaner bug, enricher bug, precedence bug, structural-header bug, or normalization bug, fix the code first.
Do not paper over a code bug by stuffing labels into a database.

### 6. No blind batch edits on data files

You may ANALYZE large batches and group them by confidence level, but do not apply JSON or code edits blindly in bulk.
Apply only highly confident approved changes, and verify each changed entry or tightly related micro-batch with tests and integrity checks.
This is a medical-grade product.

### 7. No duplicate entries across files

Before adding ANY alias or new entry, search ALL routing databases:

- `ingredient_quality_map.json` (588 IQM parents)
- `other_ingredients.json` (662 entries)
- `harmful_additives.json` (115 entries)
- `banned_recalled_ingredients.json` (143 entries)
- `botanical_ingredients.json` (433 entries)
- `standardized_botanicals.json` (239 entries)
- `proprietary_blends.json` (19 entries)
- `cross_db_overlap_allowlist.json` (31 entries)

Do not rely on hard-coded entry counts in this prompt; counts may change as the databases evolve. Always read the `_metadata.total_entries` from the live file.

If the ingredient already exists in another file, do NOT create a duplicate. Either:

- Add the alias to the existing entry in the correct file
- Or add to `cross_db_overlap_allowlist.json` if legitimate overlap is needed

### 8. Identifier-backed alias verification

Before adding an alias to an existing entry, verify the alias actually refers to the **same compound**:

1. Search the alias in UMLS → does it resolve to the same CUI as the target entry?
2. Search the alias in GSRS → does it resolve to the same UNII?
3. Search the alias in PubChem → does it resolve to the same CAS/CID?

If ANY identifier disagrees → **do not add the alias**. Instead:

- The alias may belong to a different compound → investigate
- The alias may be a derivative/salt/different form → create a separate entry or decouple
- The alias may be misspelled → fix the spelling, then verify

**Common traps:**

- "Ashwagandha" vs "Ashwagandha root extract" → different GSRS substances
- "Vitamin B12" vs "Cyanocobalamin" vs "Methylcobalamin" → different forms, different CUIs
- "Magnesium" vs "Magnesium Oxide" vs "Magnesium Glycinate" → different compounds entirely
- Plant common name vs latin binomial → same plant, OK as aliases
- Branded name vs generic → OK if same compound (verify via UNII)

### 9. Shadow-run after code fixes

If you change cleaner, normalizer, enricher, batch processor, scorer contract, or matching logic, you must run a small shadow verification on an affected dataset slice and compare before/after.

### 10. Verification loop is mandatory

For every approved batch, follow this exact order:

1. Add targeted failing tests first
2. Implement the narrowest correct fix
3. Run targeted tests
4. Run `python3 scripts/db_integrity_sanity_check.py --strict`
5. Run `python3 -m pytest scripts/tests/ -k "overlap or integrity or schema" -q`
6. Run a real shadow clean on the exact raw DSLD source files for the affected labels
7. Confirm the target labels are cleared from the intended unmapped surface
8. Confirm prior fixes did not regress

Do not treat unit-test success alone as sufficient proof.

---

## Operating Mode

Work in **2 phases** with **batches of 8-12 items**.

### Fast-but-safe triage lane

The goal is maximum accuracy without turning obvious work into unnecessary bottlenecks.

Use this confidence ladder:

- **Lane A: High-confidence alias / typo / form-alias cases**
  - exact current DB parent exists
  - raw DSLD clearly matches that identity
  - API verification agrees or current repo-governed identity already supports the mapping
  - no cross-DB collision
  - no code bug suspected
- **Lane B: Probable but not yet production-safe**
  - likely same identity, but API evidence is incomplete or mixed
  - or the alias appears to collide with another DB/file
  - or active vs inactive routing needs careful review
- **Lane C: Likely bug / structural issue**
  - parser artifact, blend header, shell/container row, normalization drift, precedence mismatch, or cleaner/enricher disagreement

Allowed speed strategy:

- Start with Lane A cases first
- Keep Lane B in `needs_verification`
- Escalate Lane C to code review / bug-fix workflow

Never promote Lane B or Lane C items into production data just to clear backlog counts.

### Phase 1: Analyze only (do NOT write anything)

1. Run the dynamic scan
2. Inspect the relevant raw DSLD source files
3. Inspect current DB coverage across all routing targets
4. **API-verify identifiers** for each candidate (CUI, UNII, CAS)
5. Classify each unmapped case by root cause
6. Identify code bugs separately from data gaps
7. For alias additions: verify the alias resolves to the same CUI/UNII/CAS as the target entry
8. Propose exact fixes in a batch of 8-12
9. **Stop and wait for approval**

### Phase 2: Apply only after approval

After approval, for each approved item:

1. Pin a failing test for the expected state
2. Make the approved JSON or code change (one entry at a time)
3. Verify the test passes
4. Run integrity checks
5. Move to next item

After the batch:

1. Run full integrity suite
2. Run shadow rerun for affected cases
3. Report before/after deltas

---

## Output Folder Layout

The pipeline produces output under `scripts/products/`. The batch runner uses `--output-prefix products/output_<brand>`.

### Per-brand folder triplet

```
scripts/products/
  output_<Brand>/                    # Clean stage output
    cleaned/                         # cleaned_batch_*.json
    unmapped/                        # unmapped/needs_verification reports
      unmapped_active_ingredients.json
      unmapped_inactive_ingredients.json
      needs_verification_active_ingredients.json
      needs_verification_inactive_ingredients.json
    errors/
    incomplete/
    needs_review/
    quarantine/
    reports/
  output_<Brand>_enriched/           # Enrich stage output
    enriched/                        # enriched_cleaned_batch_*.json
    reports/
      parent_fallback_report.json
      form_fallback_audit_report.json
      enrichment_summary.json
      coverage_report.json
      coverage_report.md
  output_<Brand>_scored/             # Score stage output
    scored/                          # scored_cleaned_batch_*.json
    reports/
```

### Discovering what's been processed

The pipeline output is dynamic — brands and categories are added over time. To see what's currently processed:

```bash
# List all processed datasets (brands, categories, etc.)
ls -d scripts/products/output_*/ 2>/dev/null | grep -v '_enriched\|_scored' | sed 's|scripts/products/output_||;s|/||'
```

The scan script auto-discovers all output folders. Never hardcode a brand/category list.

---

## What Counts as "Unmapped" in This Pipeline

There are **3 distinct surfaces**. Do not mix them.

### Surface A: Cleaning unmapped

Files:

- `scripts/products/output_<Brand>/unmapped/unmapped_active_ingredients.json`
- `scripts/products/output_<Brand>/unmapped/unmapped_inactive_ingredients.json`
- `scripts/products/output_<Brand>/unmapped/needs_verification_active_ingredients.json`
- `scripts/products/output_<Brand>/unmapped/needs_verification_inactive_ingredients.json`

Meaning: The cleaner could not map the ingredient against any known database or protection logic.
This is the **primary backlog for database growth**.

### Surface B: Enrichment unmapped

Files: `scripts/products/output_<Brand>_enriched/enriched/enriched_cleaned_batch_*.json`
Path: `product.ingredient_quality_data.ingredients_scorable[].mapped == false`

Meaning: The cleaner let the ingredient through as scorable, but enrichment failed to resolve it to IQM.
Usually: IQM alias gap, enricher routing bug, precedence bug, cleaner/enricher mismatch.

### Surface C: Form fallback

Files:

- `scripts/products/output_<Brand>_enriched/reports/parent_fallback_report.json`
- `scripts/products/output_<Brand>_enriched/reports/form_fallback_audit_report.json`

Meaning: The ingredient matched an IQM parent, but not the correct form alias, so it fell back to a conservative form.
Usually: IQM form alias gap, branded-token or normalization bug.

### Surface C validation rule

For every fallback case, do not only check that a fallback occurred.
Also verify whether the fallback-selected form is actually the correct conservative form.

Required check:

1. Inspect raw DSLD label text and any explicit form wording
2. Compare the raw form wording to the matched IQM parent and all existing IQM forms
3. Decide whether:
   - the fallback form is correct and acceptable
   - the parent is correct but the specific form alias is missing
   - the fallback chose the wrong form
   - the parent match itself may be wrong

If the fallback-selected form is wrong, do not treat the case as resolved.
Classify it as either:

- IQM form alias gap
- enricher/scoring form-selection bug
- parent-match bug

---

## Dynamic Scan — Run Every Session

```bash
python3 <<'SCAN_EOF'
import glob, json, os

os.chdir(os.path.expanduser('~/Downloads/dsld_clean/scripts'))

print('=' * 72)
print('UNMAPPED / FALLBACK SCAN — CURRENT STATE')
print('=' * 72)

# Layout: scripts/products/output_<Brand>/unmapped/ and scripts/products/output_<Brand>_enriched/
active_files = sorted(glob.glob('products/output_*/unmapped/unmapped_active_ingredients.json'))
inactive_files = sorted(glob.glob('products/output_*/unmapped/unmapped_inactive_ingredients.json'))
needs_active_files = sorted(glob.glob('products/output_*/unmapped/needs_verification_active_ingredients.json'))
needs_inactive_files = sorted(glob.glob('products/output_*/unmapped/needs_verification_inactive_ingredients.json'))
enriched_files = sorted(glob.glob('products/output_*_enriched/enriched/enriched_cleaned_batch_*.json'))
parent_fallback_files = sorted(glob.glob('products/output_*_enriched/reports/parent_fallback_report.json'))
form_audit_files = sorted(glob.glob('products/output_*_enriched/reports/form_fallback_audit_report.json'))

# --- Helpers ---
def safe_load(fp):
    try:
        with open(fp) as f:
            return json.load(f)
    except Exception as e:
        print(f'  WARNING: Failed to load {fp}: {e}')
        return {}

def brand_from_path(fp):
    """Extract brand name from output path for reporting."""
    parts = fp.replace('\\', '/').split('/')
    for p in parts:
        if p.startswith('output_') and not p.endswith('_enriched') and not p.endswith('_scored'):
            return p.replace('output_', '')
    return 'unknown'

# --- Surface A: Cleaning unmapped ---
clean_active = {}
clean_inactive = {}
needs_active = {}
needs_inactive = {}
brands_scanned = set()

for fp in active_files:
    brands_scanned.add(brand_from_path(fp))
    data = safe_load(fp)
    for k, v in data.get('unmapped_ingredients', {}).items():
        clean_active[k] = clean_active.get(k, 0) + v

for fp in inactive_files:
    data = safe_load(fp)
    for k, v in data.get('unmapped_ingredients', {}).items():
        clean_inactive[k] = clean_inactive.get(k, 0) + v

for fp in needs_active_files:
    data = safe_load(fp)
    for row in data.get('ingredients', []):
        name = row.get('label_text', 'UNKNOWN')
        needs_active[name] = needs_active.get(name, 0) + row.get('occurrences', 0)

for fp in needs_inactive_files:
    data = safe_load(fp)
    for row in data.get('ingredients', []):
        name = row.get('label_text', 'UNKNOWN')
        needs_inactive[name] = needs_inactive.get(name, 0) + row.get('occurrences', 0)

# --- Surface B: Enrichment unmapped ---
enrich_unmapped = {}
products = 0
scorable = 0
for fp in enriched_files:
    data = safe_load(fp)
    if isinstance(data, list):
        batch = data
    else:
        batch = data.get('products', [])
    for p in batch:
        products += 1
        for ing in p.get('ingredient_quality_data', {}).get('ingredients_scorable', []):
            scorable += 1
            if not ing.get('mapped', True):
                name = ing.get('name', 'UNKNOWN')
                enrich_unmapped[name] = enrich_unmapped.get(name, 0) + 1

# --- Surface C: Fallbacks ---
fallbacks = {}
for fp in parent_fallback_files:
    data = safe_load(fp)
    for row in data.get('fallbacks', []):
        key = row.get('ingredient_normalized') or row.get('ingredient_raw') or 'UNKNOWN'
        fallbacks[key] = fallbacks.get(key, 0) + row.get('occurrence_count', 0)

form_fallbacks = {}
for fp in form_audit_files:
    data = safe_load(fp)
    for row in data.get('fallbacks', data.get('form_fallbacks', [])):
        key = row.get('ingredient_normalized') or row.get('ingredient_raw') or 'UNKNOWN'
        form_fallbacks[key] = form_fallbacks.get(key, 0) + row.get('occurrence_count', row.get('count', 0))

# --- Database stats ---
db_files = {
    'IQM': 'data/ingredient_quality_map.json',
    'Other Ingredients': 'data/other_ingredients.json',
    'Harmful Additives': 'data/harmful_additives.json',
    'Banned/Recalled': 'data/banned_recalled_ingredients.json',
    'Botanical': 'data/botanical_ingredients.json',
    'Std Botanical': 'data/standardized_botanicals.json',
    'Proprietary Blends': 'data/proprietary_blends.json',
    'Cross-DB Overlap': 'data/cross_db_overlap_allowlist.json',
}

print('\n[DATABASE STATUS]')
for label, fp in db_files.items():
    try:
        d = json.load(open(fp))
        total = d.get('_metadata', {}).get('total_entries', '?')
        ver = d.get('_metadata', {}).get('schema_version', '?')
        print(f'  {label:20s}: {total:>5} entries (schema {ver})')
    except Exception as e:
        print(f'  {label:20s}: ERROR - {e}')

print(f'\n[BRANDS SCANNED]: {sorted(brands_scanned) if brands_scanned else "NONE — run pipeline first"}')
print(f'  Output folders found: {len(active_files)} clean, {len(enriched_files)} enriched, {len(parent_fallback_files)} fallback reports')

print('\n[CLEANING — Surface A]')
print(f'  Active unmapped:   {len(clean_active):,} unique / {sum(clean_active.values()):,} occ')
print(f'  Inactive unmapped: {len(clean_inactive):,} unique / {sum(clean_inactive.values()):,} occ')
print(f'  Needs verify act:  {len(needs_active):,} unique / {sum(needs_active.values()):,} occ')
print(f'  Needs verify ina:  {len(needs_inactive):,} unique / {sum(needs_inactive.values()):,} occ')

print('\n[ENRICHMENT — Surface B]')
print(f'  Products scanned:       {products:,}')
print(f'  Scorable ingredients:   {scorable:,}')
print(f'  Enrichment unmapped:    {len(enrich_unmapped):,} unique / {sum(enrich_unmapped.values()):,} occ')

clean_active_set = set(clean_active)
enrich_set = set(enrich_unmapped)
print('\n[OVERLAP A ∩ B]')
print(f'  In both:                {len(clean_active_set & enrich_set):,}')
print(f'  Cleaning-only active:   {len(clean_active_set - enrich_set):,}')
print(f'  Enrichment-only:        {len(enrich_set - clean_active_set):,}')

print('\n[FALLBACK — Surface C]')
print(f'  Parent fallback files:  {len(parent_fallback_files)}')
print(f'  Form audit files:       {len(form_audit_files)}')
print(f'  Unique parent fallback: {len(fallbacks):,} / {sum(fallbacks.values()):,} occ')
print(f'  Unique form fallback:   {len(form_fallbacks):,} / {sum(form_fallbacks.values()):,} occ')

print('\n[TOP 25 — CLEAN ACTIVE UNMAPPED]')
for name, count in sorted(clean_active.items(), key=lambda x: -x[1])[:25]:
    print(f'  {count:4d}x  {name}')

print('\n[TOP 25 — CLEAN INACTIVE UNMAPPED]')
for name, count in sorted(clean_inactive.items(), key=lambda x: -x[1])[:25]:
    print(f'  {count:4d}x  {name}')

print('\n[TOP 25 — NEEDS VERIFICATION ACTIVE]')
for name, count in sorted(needs_active.items(), key=lambda x: -x[1])[:25]:
    print(f'  {count:4d}x  {name}')

print('\n[TOP 25 — NEEDS VERIFICATION INACTIVE]')
for name, count in sorted(needs_inactive.items(), key=lambda x: -x[1])[:25]:
    print(f'  {count:4d}x  {name}')

print('\n[TOP 25 — ENRICHMENT UNMAPPED]')
for name, count in sorted(enrich_unmapped.items(), key=lambda x: -x[1])[:25]:
    print(f'  {count:4d}x  {name}')

print('\n[TOP 25 — PARENT FALLBACKS]')
for name, count in sorted(fallbacks.items(), key=lambda x: -x[1])[:25]:
    print(f'  {count:4d}x  {name}')

print('\n[TOP 25 — FORM FALLBACKS]')
for name, count in sorted(form_fallbacks.items(), key=lambda x: -x[1])[:25]:
    print(f'  {count:4d}x  {name}')

print('\n' + '=' * 72)
print('SCAN COMPLETE')
print('=' * 72)
SCAN_EOF
```

---

## Path Conventions

### Dataset root

`/Users/seancheick/Documents/DataSetDsld`

Important subpaths:

| Path                         | Purpose                                                                                                                              |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `forms/`                     | Canonical raw corpus (organized by dosage form: bars, capsules, gummies, liquids, lozenges, other, powders, softgels, tablets-pills) |
| `staging/brands/<brand>/`    | First-time brand seed staging area                                                                                                   |
| `staging/forms/<form>/`      | First-time form/category seed staging area                                                                                           |
| `delta/<target>/`            | Dated delta update output                                                                                                            |
| `state/dsld_sync_state.json` | Sync state tracking                                                                                                                  |
| `reports/<target>/`          | Sync reports                                                                                                                         |

### Pipeline repo root

`/Users/seancheick/Downloads/dsld_clean`

Important subpaths:

| Path                                 | Purpose                                                                           |
| ------------------------------------ | --------------------------------------------------------------------------------- |
| `scripts/`                           | All pipeline scripts (46 Python files)                                            |
| `scripts/data/`                      | 39 reference JSON databases                                                       |
| `scripts/data/curated_overrides/`    | Manual CUI/PubChem/GSRS policy overrides                                          |
| `scripts/data/curated_interactions/` | Drug-supplement interaction data                                                  |
| `scripts/data/fda_caers/`            | FDA CAERS adverse event data                                                      |
| `scripts/data/fda_drug_labels/`      | FDA drug label data (13 parts)                                                    |
| `scripts/data/suppai_import/`        | SuppAI import data                                                                |
| `scripts/api_audit/`                 | 30+ API verification scripts                                                      |
| `scripts/tests/`                     | 81+ test files, 3065+ test functions                                              |
| `scripts/config/`                    | cleaning_config.json, enrichment_config.json, scoring_config.json                 |
| `scripts/products/`                  | Pipeline output per dataset (brands, categories — clean/enriched/scored triplets) |

Do not assume legacy flat brand folders are canonical unless the operator explicitly says they are using a legacy folder.

## Raw Intake Paths

Raw DSLD data may enter the system in 4 ways:

1. API first-time brand seed:
   - `python3 scripts/dsld_api_sync.py sync-brand ... --output-dir /Users/seancheick/Documents/DataSetDsld/staging/brands/<brand>`
2. API first-time form/category seed:
   - `python3 scripts/dsld_api_sync.py sync-filter ...`
   - optionally with `--staging-dir /Users/seancheick/Documents/DataSetDsld/staging/forms/<form>`
3. API delta update:
   - `python3 scripts/dsld_api_sync.py sync-delta ... --delta-output-dir /Users/seancheick/Documents/DataSetDsld/delta/<target> --dated-delta --report-dir /Users/seancheick/Documents/DataSetDsld/reports/<target>`
4. Manual local import when the API is unavailable:
   - `python3 scripts/dsld_api_sync.py import-local --input-dir ... --canonical-root ... --state-file ... --delta-output-dir ... --dated-delta --report-dir ...`

The prompt must inspect the exact raw folder used for the current run whenever possible, not just the final canonical corpus.

---

## Batch Pipeline Runner

The batch runner processes all brands through the full pipeline:

```bash
# Full pipeline on all brands (default root: staging/brands)
bash batch_run_all_datasets.sh

# Score-only on all brands
bash batch_run_all_datasets.sh --stages score

# Enrich + score only
bash batch_run_all_datasets.sh --stages enrich,score

# Specific brands only
bash batch_run_all_datasets.sh --targets Thorne,Olly

# Custom root (e.g., forms)
bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/forms"

# Example: specific brands
bash batch_run_all_datasets.sh --root "/Users/seancheick/Documents/DataSetDsld/staging/brands" --targets Olly,Thorne,GNC

# Example: run by dosage form category
bash batch_run_all_datasets.sh --root "/Users/seancheick/Documents/DataSetDsld/staging/forms"
```

The batch runner uses `PYTHON="${PYTHON:-python3}"` — override with `PYTHON=python3.13 bash batch_run_all_datasets.sh` if needed.

---

## Primary Routing Targets

| Database               | File                               | Entries | Schema | Purpose                                           |
| ---------------------- | ---------------------------------- | ------- | ------ | ------------------------------------------------- |
| IQM                    | `ingredient_quality_map.json`      | 588     | 5.0.0  | Scorable active ingredients (bonuses)             |
| Other Ingredients      | `other_ingredients.json`           | 662     | 5.0.0  | Neutral excipients / carriers / shell             |
| Harmful Additives      | `harmful_additives.json`           | 115     | 5.1.0  | Penalty-bearing inactive ingredients              |
| Banned/Recalled        | `banned_recalled_ingredients.json` | 143     | 5.0.0  | Disqualification gate and penalty                 |
| Botanical              | `botanical_ingredients.json`       | 433     | 5.0.0  | Basic botanical mapping                           |
| Standardized Botanical | `standardized_botanicals.json`     | 239     | 5.0.0  | Standardized botanical extracts (bonus)           |
| Proprietary Blends     | `proprietary_blends.json`          | 19      | 5.0.0  | Descriptor-level mapping (scorer handles penalty) |
| Cross-DB Overlap       | `cross_db_overlap_allowlist.json`  | 31      | 5.1.0  | Legitimate multi-file entries                     |

### Supporting data files (not routing targets, but referenced during resolution)

| File                                   | Entries | Purpose                               |
| -------------------------------------- | ------- | ------------------------------------- |
| `absorption_enhancers.json`            | 23      | Absorption enhancer classification    |
| `allergens.json`                       | 17      | Big 8 allergen classification         |
| `backed_clinical_studies.json`         | 197     | PMID-backed clinical evidence bonuses |
| `synergy_cluster.json`                 | 58      | Ingredient synergy bonuses            |
| `rda_optimal_uls.json`                 | 47      | RDA/AI/UL dosing benchmarks           |
| `medication_depletions.json`           | 68      | Drug-induced nutrient depletions      |
| `ingredient_classification.json`       | 34      | Active/inactive classification rules  |
| `ingredient_interaction_rules.json`    | 129     | Interaction rule engine               |
| `drug_classes.json`                    | 28      | Drug class definitions                |
| `timing_rules.json`                    | 42      | Dosing timing guidance                |
| `clinically_relevant_strains.json`     | 42      | Probiotic strain specificity          |
| `color_indicators.json`                | 66      | Color additive classification         |
| `enhanced_delivery.json`               | 78      | Enhanced delivery system bonuses      |
| `functional_ingredient_groupings.json` | 8       | Functional grouping definitions       |
| `manufacturer_violations.json`         | —       | Brand trust penalties                 |
| `rda_therapeutic_dosing.json`          | —       | Therapeutic dosing ranges             |

### Curated override files (prevent known bad auto-matches)

| File                                      | Content                           |
| ----------------------------------------- | --------------------------------- |
| `curated_overrides/cui_overrides.json`    | 66 CUI override entries           |
| `curated_overrides/gsrs_policies.json`    | 88 entry policies + 24 skip names |
| `curated_overrides/pubchem_policies.json` | 17 entry policies + 23 skip names |

### Default routing rule

- **Active unmapped** → IQM (only IQM scores active ingredients — the enricher's Pass 1 only processes activeIngredients)
- **Inactive unmapped** → harmful_additives, other_ingredients, botanical_ingredients, or banned_recalled depending on what the ingredient IS
- **Enrichment fallbacks** → usually active ingredients that matched a parent in IQM but not the specific form — need form alias additions in IQM

### How the enricher prevents cross-contamination (verified)

The enricher has two passes:

- **Pass 1**: Processes `activeIngredients` only → matches against IQM for scoring
- **Pass 2**: Processes `inactiveIngredients` → only PROMOTES to scorable if RULE A (known therapeutic in IQM/botanicals), RULE B (has dose + therapeutic signal), RULE C (absorption enhancer), or RULE D (product-type rescue). Hard exclusions: `isAdditive=true`, known excipients, blend headers.

This means: an ingredient in IQM will NOT be scored if it only appears in `inactiveIngredients` (unless the promotion rules fire). An ingredient in harmful_additives will NOT be accidentally promoted to scoring — the enricher checks harmful/banned/other DBs separately for penalty assessment.

**Safe to have the same ingredient in both IQM and harmful_additives** — the enricher routes by source section (active vs inactive), not by which DB the ingredient appears in.

### Dual-routing: same ingredient in multiple files

Some ingredients appear as BOTH active and inactive depending on the product:

- Xylitol: active in dental products (IQM), inactive sweetener in capsules (harmful_additives)
- Senna: active therapeutic laxative (IQM), harmful stimulant laxative at chronic doses (harmful_additives)

When an ingredient needs entries in both IQM and harmful_additives:

1. Create both entries with consistent verified identifiers when exact cross-file identity is supported
2. Add the ingredient to `cross_db_overlap_allowlist.json`

### Override defaults when evidence shows it is actually:

- A harmful additive → `harmful_additives.json` (check severity: high -2pts, moderate -1pt, low -0.5pts)
- A banned / recalled / high-risk ingredient → `banned_recalled_ingredients.json`
- A botanical identity → `botanical_ingredients.json`
- A standardized botanical → `standardized_botanicals.json`
- A structural label / container / header / parser artifact → code fix, not DB entry
- A therapeutic ingredient misclassified by manufacturer into inactive section → IQM with evidence

---

## Classification Decision Tree

Every candidate must be classified into exactly one bucket first. Do not jump to alias creation.

### Bucket 1: Structural / filter / header row

Examples: `Soft Gel Shell`, `Shell Ingredients`, `May also contain`, `Other`
Action: Do not add to DB. Fix cleaner/header logic if needed.

### Bucket 2: Parser / normalizer bug

Examples: Punctuation drift, bracket bleed, dosage text in name, apostrophe variants
Action: Patch code, add regression test, shadow-run.

### Bucket 3: Routing / precedence bug

Examples: Cleaner maps but enricher misses, IQM beats harmful when harmful should win
Action: Patch code, add regression test, shadow-run.

### Bucket 4: True alias gap (MOST COMMON)

Meaning: The identity already exists in the correct DB, but the exact raw label text is not covered.
Action: Add alias only — **after identifier verification confirms same compound**.

### Bucket 5: True new canonical entry

Meaning: Ingredient does not exist anywhere in any target DB.
Action: Add new entry with full schema + verified identifiers where exact identity is available.

**IQM new entry requirements (critical — tests will fail if missing):**

- `category` and `category_enum` must be from the allowed enum: `amino_acids | antioxidants | enzymes | fatty_acids | fibers | functional_foods | herbs | minerals | other | probiotics | proteins | vitamins`
- Each form must have: `bio_score`, `natural`, `score` (= bio_score + 3 if natural, else bio_score), `absorption`, `absorption_structured` (with `quality` field), `notes`, `aliases`, `dosage_importance`
- Parent-level must have: `standard_name`, `category`, `cui`, `rxcui`, `forms`, `match_rules`, `category_enum`, `data_quality`, `aliases`, `external_ids`, `gsrs`
- If ingredient appears in both IQM and harmful_additives, must add to `cross_db_overlap_allowlist.json` — and add ALL shared alias terms, not just the entry name
- Update `_metadata.total_entries` and `_metadata.last_updated`
- If an exact UMLS concept does not exist, use reviewed null-governance fields instead of forcing a wrong CUI

**harmful_additives new entry requirements:**

- Must match the full v5.1 schema (see Harmful_additive_audit_prompt.md)
- `severity_level`: high (-2pts), moderate (-1pt), low (-0.5pts) — based on evidence, not guessing
- Update `_metadata.total_entries` and `_metadata.last_updated`

### Bucket 6: Form fallback gap

Meaning: Parent is correct, but form alias is missing.
Action: Add alias to the correct existing IQM form only after confirming the fallback-selected form is not already the correct conservative match.

If the fallback-selected form itself is wrong, do not treat this as alias-only.
Escalate to:

- enricher/scoring form-selection bug
- or parent-match bug

### Bucket 7: Misspelling / typo

Meaning: Raw label has a typo (e.g., "Magnesuim" for "Magnesium", "Calcuim" for "Calcium").
Action: Add the misspelled variant as an alias to the correct entry. The pipeline normalizer should catch it, but adding as alias is the safety net.

### Bucket 8: Needs verification

Meaning: Identity unclear after DB + raw inspection.
Action: Do not write. Report what must be verified.

---

## Identifier Verification for Alias Additions

**This is the critical step.** Before adding any alias, run this checklist:

### Step 1: Find the target entry

```bash
# Search all DBs for the canonical ingredient
python3 -c "
import json, sys, os
os.chdir(os.path.expanduser('~/Downloads/dsld_clean'))
term = sys.argv[1].lower()
files = [
    ('scripts/data/ingredient_quality_map.json', 'iqm'),
    ('scripts/data/other_ingredients.json', 'other_ingredients'),
    ('scripts/data/harmful_additives.json', 'harmful_additives'),
    ('scripts/data/banned_recalled_ingredients.json', 'ingredients'),
    ('scripts/data/botanical_ingredients.json', 'botanical_ingredients'),
    ('scripts/data/standardized_botanicals.json', 'standardized_botanicals'),
    ('scripts/data/proprietary_blends.json', 'proprietary_blends'),
]
for fpath, key in files:
    d = json.load(open(fpath))
    if key == 'iqm':
        for k, v in d.items():
            if k == '_metadata': continue
            if not isinstance(v, dict): continue
            sname = (v.get('standard_name') or '').lower()
            aliases = [a.lower() for a in v.get('aliases', []) if isinstance(a, str)]
            form_aliases = []
            for fname, fdata in v.get('forms', {}).items():
                if isinstance(fdata, dict):
                    form_aliases.extend([a.lower() for a in fdata.get('aliases', []) if isinstance(a, str)])
            all_terms = [sname] + aliases + form_aliases + [k.lower()]
            if any(term in t for t in all_terms):
                print(f'  IQM: {k} ({v.get(\"standard_name\")}) — {len(v.get(\"forms\",{}))} forms')
    elif key == 'proprietary_blends':
        for e in d.get(key, []):
            sname = (e.get('name') or e.get('standard_name') or '').lower()
            aliases = [a.lower() for a in e.get('aliases', []) if isinstance(a, str)]
            if any(term in t for t in [sname] + aliases):
                print(f'  {fpath.split(\"/\")[-1]}: {e.get(\"name\")} ({e.get(\"standard_name\",\"\")})')
    else:
        entries = d.get(key, [])
        if isinstance(entries, dict):
            entries = list(entries.values())
        for e in entries:
            if not isinstance(e, dict): continue
            sname = (e.get('standard_name') or '').lower()
            aliases = [a.lower() for a in e.get('aliases', []) if isinstance(a, str)]
            eid = e.get('id', '')
            if any(term in t for t in [sname] + aliases + [str(eid).lower()]):
                print(f'  {fpath.split(\"/\")[-1]}: {eid} ({e.get(\"standard_name\")})')
" "<search_term>"
```

### Step 2: Verify the alias resolves to the same substance

```bash
# Check UMLS
python3 scripts/api_audit/verify_cui.py --search "<alias_text>"
# Compare CUI with the target entry's CUI

# Check GSRS
python3 scripts/api_audit/verify_unii.py --search "<alias_text>"
# Compare UNII with the target entry's external_ids.unii

# Check PubChem
python3 scripts/api_audit/verify_pubchem.py --search "<alias_text>"
# Compare CAS/CID with the target entry's external_ids
```

### Step 3: Decision matrix

| UMLS match?   | GSRS match?    | PubChem match? | Action                                                                                              |
| ------------- | -------------- | -------------- | --------------------------------------------------------------------------------------------------- |
| Same CUI      | Same UNII      | Same CAS       | **Safe to add alias**                                                                               |
| Same CUI      | Different UNII | —              | Investigate: may be different form/salt                                                             |
| Different CUI | Same UNII      | —              | Investigate: UMLS may have separate concepts for form vs parent                                     |
| Different CUI | Different UNII | Different CAS  | **DO NOT add alias** — different compound                                                           |
| No result     | No result      | No result      | Keep in `needs_verification` unless current repo-governed identity already proves exact equivalence |

### Step 4: Check for cross-DB collisions

```bash
# Verify the alias doesn't already exist in another DB file
python3 -c "
import json, sys, os
os.chdir(os.path.expanduser('~/Downloads/dsld_clean'))
alias = sys.argv[1].lower()
files = [
    'scripts/data/ingredient_quality_map.json',
    'scripts/data/other_ingredients.json',
    'scripts/data/harmful_additives.json',
    'scripts/data/banned_recalled_ingredients.json',
    'scripts/data/botanical_ingredients.json',
    'scripts/data/standardized_botanicals.json',
    'scripts/data/proprietary_blends.json',
]
for fpath in files:
    d = json.load(open(fpath))
    text = json.dumps(d).lower()
    if alias in text:
        print(f'  FOUND in {fpath.split(\"/\")[-1]}')
" "<alias_text>"
```

If alias exists in another file → do NOT duplicate. Either:

- The alias is already covered (no action needed)
- The alias is in the wrong file (move it)
- Both files legitimately need it (add to `cross_db_overlap_allowlist.json`)

---

## Raw DSLD Verification Workflow

For any suspicious item, compare across the full pipeline:

1. **Exact raw working-set file**:
   - staging folder: `/Users/seancheick/Documents/DataSetDsld/staging/brands/<brand>/`
   - dated delta folder for update runs: `/Users/seancheick/Documents/DataSetDsld/delta/<target>/`
   - manual import folder for local-import runs
2. **Canonical raw file** in `/Users/seancheick/Documents/DataSetDsld/forms/<dosage_form>/`
3. **Cleaned output**: `scripts/products/output_<Brand>/cleaned/cleaned_batch_*.json`
4. **Enriched output**: `scripts/products/output_<Brand>_enriched/enriched/enriched_cleaned_batch_*.json`
5. **Unmapped / needs-verification / fallback reports**: `scripts/products/output_<Brand>/unmapped/` and `scripts/products/output_<Brand>_enriched/reports/`

Key fields to compare:

- `name` / `raw_source_text` / `ingredientGroup`
- `forms` / `nestedIngredients`
- Active vs inactive placement
- fallback-selected form vs expected correct form
- Whether the parent label is structural and child forms are the real ingredients

If raw shows a blend/container/header and cleaned surfaces it as unmapped ingredient text → code issue first.
Prefer the exact current run folder first, because that is the operator's working set. Use canonical `forms/` as the long-term reference copy.

---

## Key Pipeline Scripts Reference

| Script                             | Purpose                                       | When to use during resolution    |
| ---------------------------------- | --------------------------------------------- | -------------------------------- |
| `run_pipeline.py`                  | Orchestrates Clean → Enrich → Score           | Shadow-run verification          |
| `clean_dsld_data.py`               | Stage 1: normalize raw DSLD JSON              | Investigate cleaning bugs        |
| `enrich_supplements_v3.py`         | Stage 2: match, classify, enrich (~12K lines) | Investigate enrichment bugs      |
| `score_supplements.py`             | Stage 3: arithmetic scoring (~3K lines)       | Investigate scoring bugs         |
| `enhanced_normalizer.py`           | Core text normalization engine (~6K lines)    | Investigate normalization bugs   |
| `constants.py`                     | Shared constants and mappings (~1.5K lines)   | Check canonical aliases/mappings |
| `fuzzy_matcher.py`                 | Fuzzy string matching                         | Investigate match failures       |
| `functional_grouping_handler.py`   | Functional grouping logic                     | Investigate grouping bugs        |
| `proprietary_blend_detector.py`    | Blend detection                               | Investigate blend routing        |
| `rda_ul_calculator.py`             | RDA/UL dose calculations                      | Investigate dose scoring         |
| `dosage_normalizer.py`             | Dose normalization                            | Investigate dose parsing         |
| `match_ledger.py`                  | Match tracking/auditing                       | Trace match decisions            |
| `db_integrity_sanity_check.py`     | Schema and data validation (~1.5K lines)      | Mandatory after every edit       |
| `coverage_gate.py`                 | Quality/coverage threshold enforcement        | Quality gate checking            |
| `enrichment_contract_validator.py` | Enrichment output validation                  | Verify enrichment contracts      |

---

## Best-Practice Answer Format

When answering from this prompt, structure the response like this:

1. **Current batch summary**
   - Which raw source folder was inspected
   - Which pipeline output folders were inspected
   - Counts for unmapped, needs-verification, and fallback surfaces
2. **High-confidence fixes (Lane A)**
   - exact aliases, misspellings, form aliases, or obvious DB-entry gaps
   - each with raw evidence, DB target, and identifier evidence
3. **Needs verification (Lane B)**
   - ambiguous identity, mixed API evidence, or cross-DB collision risk
4. **Likely code bugs (Lane C)**
   - parser/header/precedence/normalization/routing issues
5. **Recommended next actions**
   - approved JSON edits
   - required tests
   - shadow-run target

Always separate:

- safe alias/data fixes
- true new canonical entries
- likely code bugs
- unresolved items that should stay in `needs_verification`

For each fallback item, report:

- raw form text
- fallback-selected form
- expected correct form
- whether this is alias-only or code-bug risk

---

## Evidence Standards

### Identity evidence

Use at least one of:

- NIH ODS fact sheet, NCCIH monograph, FDA/USDA/regulator source
- PubChem / FDA UNII / NCBI reference
- API verification (CUI, UNII, CAS cross-match)

### Clinical notes

- Include mechanism, form relevance, bioavailability
- Include PMID/DOI if available
- No vague filler text or invented effect sizes

### Safety evidence

- FDA / NIH / NCCIH first
- PubMed / DOI-backed second
- Branded site never as sole safety evidence

---

## API Verification Tools

| Script                             | API                             | What it checks                                            | Key flags                           |
| ---------------------------------- | ------------------------------- | --------------------------------------------------------- | ----------------------------------- |
| `verify_cui.py`                    | UMLS                            | CUI validity, concept name                                | `--cui C0000000`, `--search "name"` |
| `verify_unii.py`                   | FDA GSRS                        | UNII, CFR, DSLD, metabolic relationships                  | `--search "name"`                   |
| `verify_pubchem.py`                | PubChem                         | CAS, PubChem CID, molecular identity                      | `--search "name"`, `--cid 12345`    |
| `verify_rda_uls.py`                | USDA FoodData Central + NAM DRI | RDA/AI/UL values                                          | —                                   |
| `verify_efsa.py`                   | EFSA OpenFoodTox                | EU regulatory ADI/opinion                                 | —                                   |
| `verify_clinical_trials.py`        | ClinicalTrials.gov              | NCT ID validity                                           | —                                   |
| `verify_comptox.py`                | EPA CompTox                     | Chemical toxicity data                                    | —                                   |
| `verify_interactions.py`           | RxNorm + UMLS                   | Drug-supplement interactions                              | —                                   |
| `verify_pubmed_references.py`      | PubMed                          | Cross-file PMID validation                                | —                                   |
| `verify_all_citations_content.py`  | PubMed                          | Content-verify ALL PMIDs (title must match claimed topic) | —                                   |
| `verify_depletion_timing_pmids.py` | PubMed                          | Depletion/timing PMID content verification                | —                                   |

### Enrichment/audit scripts

| Script                                          | Purpose                                           |
| ----------------------------------------------- | ------------------------------------------------- |
| `api_audit/enrich_botanicals.py`                | Botanical enrichment with standardization markers |
| `api_audit/enrich_chembl_bioactivity.py`        | ChEMBL mechanism of action enrichment             |
| `api_audit/audit_alias_accuracy.py`             | Alias accuracy audit                              |
| `api_audit/audit_banned_recalled_accuracy.py`   | Release gate for banned/recalled data             |
| `api_audit/audit_clinical_evidence_strength.py` | Evidence strength classification                  |
| `api_audit/audit_clinical_sources.py`           | Clinical source validation                        |
| `api_audit/audit_notes_alignment.py`            | Notes alignment check                             |
| `api_audit/discover_clinical_evidence.py`       | Clinical evidence discovery                       |
| `api_audit/normalize_clinical_pubmed.py`        | PubMed citation normalization                     |
| `api_audit/build_unii_cache.py`                 | Build local UNII cache from FDA bulk              |
| `api_audit/ingest_caers.py`                     | Ingest FDA CAERS adverse event data               |
| `api_audit/mine_drug_label_interactions.py`     | Mine FDA drug labels for interactions             |
| `api_audit/seed_drug_classes.py`                | Seed drug class definitions                       |
| `api_audit/fda_weekly_sync.py`                  | FDA recall tracking (openFDA, RSS, DEA)           |
| `api_audit/fda_manufacturer_violations_sync.py` | Manufacturer violation sync                       |

Curated override files (prevent known bad auto-matches):

- `scripts/data/curated_overrides/cui_overrides.json` (66 entries)
- `scripts/data/curated_overrides/gsrs_policies.json` (88 entry policies, 24 skip names)
- `scripts/data/curated_overrides/pubchem_policies.json` (17 entry policies, 23 skip names)

**NEVER use `--apply` in bulk.** Dry-run only, verify each result individually.

---

## Output Format

### Phase 1 Outputs (stop after these)

#### TABLE 1: Findings

| #   | Label text | Occ | Surface | Bucket | Raw verified? | Proposed action | Target DB | Identifier match? | Confidence |
| --- | ---------- | --- | ------- | ------ | ------------- | --------------- | --------- | ----------------- | ---------- |

#### TABLE 2: Alias Additions (identifier-verified)

| #   | Alias text | Target file | Target entry ID | CUI match? | UNII match? | CAS match? | Evidence |
| --- | ---------- | ----------- | --------------- | ---------- | ----------- | ---------- | -------- |

#### TABLE 3: New Entries

| #   | Standard name | Target file | CUI | UNII | CAS | CID | Category | Evidence |
| --- | ------------- | ----------- | --- | ---- | --- | --- | -------- | -------- |

#### TABLE 4: Code Bugs

| #   | File | Function | Root cause | Why alias won't fix it | Proposed fix |
| --- | ---- | -------- | ---------- | ---------------------- | ------------ |

#### TABLE 5: Deferred / Needs Verification

| #   | Label text | Missing evidence | Next verification step |
| --- | ---------- | ---------------- | ---------------------- |

#### TABLE 6: Misspelling / Typo Aliases

| #   | Raw label (misspelled) | Correct form | Target entry | Verified same CUI/UNII? |
| --- | ---------------------- | ------------ | ------------ | ----------------------- |

#### TABLE 7: Fallback Form Validation

| #   | Ingredient | Raw form text | Fallback-selected form | Expected correct form | Alias-only or bug? | Confidence |
| --- | ---------- | ------------- | ---------------------- | --------------------- | ------------------ | ---------- |

#### BATCH SUMMARY

```
Batch N — Items [X] to [Y]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total analyzed:         XX
Alias additions:        XX (all identifier-verified)
New entries:            XX
Code bugs found:        XX
Misspellings:           XX
Deferred:               XX
Cross-DB collisions:    XX (prevented)
```

### Phase 2 Outputs (after approval)

1. Files changed (exact list)
2. Tests run (integrity + targeted)
3. Shadow-run verification (before/after unmapped deltas)
4. Residual risk (anything still deferred)

---

## Specific Guardrails

### Misspelled ingredients

Many unmapped labels are just typos: "Magnesuim", "Calcuim", "Vitamine", "Glucosamine Sulfae".
These should be added as aliases to the correct entry — the misspelled form IS what appears on the label and needs to match.
But verify: the misspelling must resolve to the same compound (not a real different ingredient with a similar name).

### Active ingredients mostly go to IQM

But do not force excipients, shell materials, structural labels, or safety ingredients into IQM.

### Inactive ingredients mostly go to other_ingredients

But do not bury harmful / banned / recalled identities in other_ingredients.

### Structural labels are not ingredients

Do not add `Soft Gel Shell`, `Shell Ingredients`, `May also contain`, `Outer Shell`, `Other` as ingredients.

### Shell materials should still be preserved

If raw shows structural parent with child forms (gelatin, glycerin, water, colorants), preserve the children, not the structural parent.

### Do not assume fallback means solved

If enrichment fallback resolves something weakly, it can still be a clean-stage alias gap or code drift.

### Display ledger rule

Rows that are label-visible but should not score: keep in display ledger, mark non-scoring, preserve real mapped/scorable children separately.

---

## Critical Rules

1. **No batch fixes.** 8-12 items per batch. Verify each individually. Test-pin before editing data.
2. **API-verify all identifiers** before adding aliases or new entries. CUI via UMLS, UNII via GSRS, CAS via PubChem.
3. **No alias should match a different compound** — verify via CUI/UNII/CAS. If identifiers disagree, decouple.
4. **No duplicate entries across files.** Search all 7+ routing databases before adding anything.
5. **No hallucinated references.** If you can't find a real source, write "needs verification."
6. **Fix code bugs with code, not data.** Do not paper over parser/normalizer/precedence bugs with aliases.
7. **Raw DSLD verification is mandatory** for any suspicious or ambiguous case.
8. **Cross-check CAS numbers** — wrong CAS = wrong substance = patient safety risk.
9. **When in doubt → defer, don't guess.** A larger unmapped list with clean logic is better than a smaller list with bad aliases.
10. **The goal is correct identity resolution, not fewer unmapped names.**
