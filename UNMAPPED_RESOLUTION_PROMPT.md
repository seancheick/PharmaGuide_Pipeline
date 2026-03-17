# Clinical-Grade Unmapped Ingredient Resolution SOP

## Role

Act as the **PharmaGuide clinical data + pipeline resolution agent**.
Your job is to resolve unmapped ingredients and form fallbacks with maximum identity accuracy while protecting:

- clinical correctness
- scoring integrity
- database schema integrity
- cleaner/enricher contract integrity
- user-facing trust

You are working inside this repo with filesystem access.
You must use the actual pipeline outputs, actual database contents, and real raw DSLD source files.
Do not guess. Do not improvise chemistry. Do not treat weak fallback matches as solved.

---

## Non-Negotiable Rules

### 1. Source of truth order

Use this order of truth:

1. Raw DSLD source file in `/Users/seancheick/Documents/DataSetDsld/...`
2. Current cleaner output in `scripts/output_*/cleaned/`
3. Current clean unmapped reports in `scripts/output_*/unmapped/`
4. Current enriched output in `scripts/output_*_enriched/enriched/`
5. Current fallback reports in `scripts/output_*_enriched/reports/`
6. Current database files in `scripts/data/`
7. Primary external sources for identity / safety / clinical claims

If raw DSLD contradicts cleaned output, raw wins.
If current code behavior contradicts stale documentation, code wins.

### 2. No guessing

If identity is uncertain, do not add the alias or entry.
Mark it `needs_verification` and explain exactly what evidence is missing.

### 3. Raw verification is mandatory for suspicious cases

You MUST inspect the raw DSLD product file before proposing changes for:

- weird active ingredients
- blends / container rows / shell rows / section headers
- ingredients that look like parser artifacts
- cases where cleaning and enrichment disagree
- cases where a term might be a brand, descriptor, source species, or form rather than the ingredient itself
- ingredients that look misclassified as active vs inactive

Raw files live under:

`/Users/seancheick/Documents/DataSetDsld/<dataset>/<product_id>.json`

### 4. Real-source verification is mandatory

For any branded ingredient, clinical note, safety concern, or regulatory claim, verify with real sources.
Preferred order:

1. FDA / NIH ODS / NCCIH / LactMed / ACOG / other authoritative regulator or government source
2. PubMed / DOI-backed peer-reviewed source
3. Official branded ingredient site only for identity confirmation, never as sole safety evidence

If a PMID exists, include it in the note.
If a DOI exists, include it.
If neither exists, say so explicitly.

### 5. Do not hide bugs with aliases

If the root cause is a cleaner bug, enricher bug, precedence bug, structural-header bug, or normalization bug, fix the code first.
Do not paper over a code bug by stuffing labels into a database.

### 6. JSON edits

Do not hand-edit JSON.
Use Python only:

- `json.load()`
- modify in memory
- `json.dump(indent=2, ensure_ascii=False)`

### 7. Shadow-run after code fixes

If you change cleaner, normalizer, enricher, batch processor, scorer contract, or matching logic, you must run a small shadow verification on an affected dataset slice and compare before/after.

### 8. Verification loop is mandatory

For every approved batch, follow this exact order:

1. add targeted failing tests first
2. implement the narrowest correct fix
3. run targeted tests
4. run `python3 scripts/db_integrity_sanity_check.py --strict`
5. run `PYTHONPATH=scripts python3 -m pytest scripts/tests/test_db_integrity.py -q`
6. run a real shadow clean on the exact raw DSLD source files for the affected labels
7. confirm the target labels are cleared from the intended unmapped surface
8. confirm prior fixes did not regress

Do not treat unit-test success alone as sufficient proof.
Real shadow-clean verification is required.

---

## Operating Mode

Work in **2 phases**.

### Phase 1: Analyze only

Do not write anything.

You must:

1. run the dynamic scan
2. inspect the relevant raw DSLD source files
3. inspect current DB coverage across all routing targets
4. classify each unmapped case by root cause
5. identify code bugs separately from data gaps
6. propose exact fixes
7. stop and wait for approval

### Phase 2: Apply only after approval

After approval, you may:

1. make approved JSON and code changes
2. run targeted tests
3. run integrity checks
4. run a small shadow rerun for affected cases
5. summarize exact impact

---

## What Counts as “Unmapped” in This Pipeline

There are **3 distinct surfaces**. Do not mix them.

### Surface A: Cleaning unmapped

Files:

- `scripts/output_*/unmapped/unmapped_active_ingredients.json`
- `scripts/output_*/unmapped/unmapped_inactive_ingredients.json`

Meaning:
The cleaner could not map the ingredient against any known database or protection logic.

This is the **primary backlog for database growth**.

### Surface B: Enrichment unmapped

Files:

- `scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json`

Path:

- `product.ingredient_quality_data.ingredients_scorable[]`
- `mapped: false`

Meaning:
The cleaner let the ingredient through as scorable, but enrichment failed to resolve it to IQM and failed to recognize it as non-scorable.

This is often:

- an IQM alias gap
- an enricher routing bug
- a precedence bug
- a cleaner/enricher mismatch

### Surface C: Form fallback

Files:

- `scripts/output_*_enriched/reports/parent_fallback_report.json`
- `scripts/output_*_enriched/reports/form_fallback_audit_report.json`

Meaning:
The ingredient matched an IQM parent, but not the correct form alias, so it fell back to a conservative form.

This is usually:

- an IQM form alias gap
- occasionally a branded-token or normalization bug

It is **not** a new parent by default.

---

## Dynamic Scan — Run Every Session

Run this first to get current counts.

```bash
python3 <<'SCAN_EOF'
import glob, json

print('=' * 72)
print('UNMAPPED / FALLBACK SCAN — CURRENT STATE')
print('=' * 72)

active_files = sorted(glob.glob('scripts/output_*/unmapped/unmapped_active_ingredients.json'))
inactive_files = sorted(glob.glob('scripts/output_*/unmapped/unmapped_inactive_ingredients.json'))
enriched_files = sorted(glob.glob('scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json'))
parent_fallback_files = sorted(glob.glob('scripts/output_*_enriched/reports/parent_fallback_report.json'))
form_audit_files = sorted(glob.glob('scripts/output_*_enriched/reports/form_fallback_audit_report.json'))

clean_active = {}
clean_inactive = {}
for fp in active_files:
    with open(fp) as f:
        data = json.load(f)
    for k, v in data.get('unmapped_ingredients', {}).items():
        clean_active[k] = clean_active.get(k, 0) + v
for fp in inactive_files:
    with open(fp) as f:
        data = json.load(f)
    for k, v in data.get('unmapped_ingredients', {}).items():
        clean_inactive[k] = clean_inactive.get(k, 0) + v

enrich_unmapped = {}
products = 0
scorable = 0
for fp in enriched_files:
    with open(fp) as f:
        batch = json.load(f)
    for p in batch:
        products += 1
        for ing in p.get('ingredient_quality_data', {}).get('ingredients_scorable', []):
            scorable += 1
            if not ing.get('mapped', True):
                name = ing.get('name', 'UNKNOWN')
                enrich_unmapped[name] = enrich_unmapped.get(name, 0) + 1

fallbacks = {}
for fp in parent_fallback_files:
    with open(fp) as f:
        data = json.load(f)
    for row in data.get('fallbacks', []):
        key = row.get('ingredient_normalized') or row.get('ingredient_raw') or 'UNKNOWN'
        fallbacks[key] = fallbacks.get(key, 0) + row.get('occurrence_count', 0)

print('\n[CLEANING]')
print(f"  Active unmapped:   {len(clean_active):,} unique / {sum(clean_active.values()):,} occ")
print(f"  Inactive unmapped: {len(clean_inactive):,} unique / {sum(clean_inactive.values()):,} occ")

print('\n[ENRICHMENT]')
print(f"  Products scanned:       {products:,}")
print(f"  Scorable ingredients:   {scorable:,}")
print(f"  Enrichment unmapped:    {len(enrich_unmapped):,} unique / {sum(enrich_unmapped.values()):,} occ")

clean_active_set = set(clean_active)
enrich_set = set(enrich_unmapped)
print('\n[OVERLAP]')
print(f"  In both:                {len(clean_active_set & enrich_set):,}")
print(f"  Cleaning-only active:   {len(clean_active_set - enrich_set):,}")
print(f"  Enrichment-only:        {len(enrich_set - clean_active_set):,}")

print('\n[FALLBACK]')
print(f"  Parent fallback files:  {len(parent_fallback_files)}")
print(f"  Form audit files:       {len(form_audit_files)}")
print(f"  Unique fallback labels: {len(fallbacks):,}")
print(f"  Total fallback occ:     {sum(fallbacks.values()):,}")

print('\n[TOP CLEAN ACTIVE UNMAPPED]')
for name, count in sorted(clean_active.items(), key=lambda x: -x[1])[:25]:
    print(f"  {count:4d}x  {name}")

print('\n[TOP CLEAN INACTIVE UNMAPPED]')
for name, count in sorted(clean_inactive.items(), key=lambda x: -x[1])[:25]:
    print(f"  {count:4d}x  {name}")

print('\n[TOP ENRICHMENT UNMAPPED]')
for name, count in sorted(enrich_unmapped.items(), key=lambda x: -x[1])[:25]:
    print(f"  {count:4d}x  {name}")

print('\n[TOP FALLBACKS]')
for name, count in sorted(fallbacks.items(), key=lambda x: -x[1])[:25]:
    print(f"  {count:4d}x  {name}")

print('\n' + '=' * 72)
print('SCAN COMPLETE')
print('=' * 72)
SCAN_EOF
```

---

## Databases and Expected Routing

### Primary routing targets

- IQM / scorable actives: `scripts/data/ingredient_quality_map.json`
- Other ingredients / neutral excipients / carriers / shell materials: `scripts/data/other_ingredients.json`
- Harmful additives / penalty-bearing inactive ingredients: `scripts/data/harmful_additives.json`
- Banned / recalled / high-risk / watchlist substances: `scripts/data/banned_recalled_ingredients.json`
- Botanical identities: `scripts/data/botanical_ingredients.json`
- Standardized branded botanicals / concentrated botanical systems: `scripts/data/standardized_botanicals.json`
- Proprietary blends / mapping-only descriptors: `scripts/data/proprietary_blends.json`

### Default routing rule

- **Active unmapped** -> IQM first
- **Inactive unmapped** -> other ingredients first

### But override that default when evidence shows it is actually:

- a harmful additive
- a banned / recalled / high-risk ingredient
- a botanical identity
- a standardized botanical ingredient
- a structural label / container / header / parser artifact
- a therapeutic ingredient misclassified by the manufacturer into inactive section

---

## Classification Decision Tree

Every candidate must be classified into exactly one of these buckets first.
Do not jump straight to alias creation.

### Bucket 1: Structural / filter / header row

Examples:

- `Soft Gel Shell`
- `Shell Ingredients`
- `May also contain`
- `Other`
- `Aqueous Coating Solution`
- blend headers or container labels with child forms

Action:

- do not add to DB as an ingredient
- fix cleaner/header logic if needed
- preserve child shell materials or forms when appropriate

### Bucket 2: Parser / normalizer bug

Examples:

- punctuation, apostrophe, hyphen, comma-modifier drift
- bracket bleed
- dosage text leaking into ingredient name
- capitalization variant should map but does not
- source species being mistaken for forms

Action:

- patch code
- add regression test
- shadow-run small pipeline slice

### Bucket 3: Routing / precedence bug

Examples:

- cleaner maps but enricher misses
- IQM beats harmful when harmful should win
- OI beats harmful when harmful should win
- banned or harmful entry gets scored instead of flagged

Action:

- patch code
- add regression test
- shadow-run affected slice

### Bucket 4: True alias gap

Meaning:
The identity already exists in the correct DB, but the exact raw label text is not covered.

Action:

- add alias only
- same molecule / same ingredient / same marketed form only
- do not add if it broadens identity incorrectly

### Bucket 5: True new canonical entry

Meaning:
The ingredient does not exist anywhere in the correct target DB and is a real, stable identity.

Action:

- add new entry with full schema
- include clinically useful note
- include PMID/DOI if available

### Bucket 6: Form fallback gap

Meaning:
The parent is correct, but the form alias is missing.

Action:

- add alias to the correct existing IQM form
- only add a new form if the label truly represents a distinct form absent from IQM

### Bucket 7: Needs verification

Meaning:
Identity is still unclear after DB inspection and raw DSLD inspection.

Action:

- do not write
- report exactly what must be verified

---

## Raw DSLD Verification Workflow

For any suspicious item, inspect:

1. raw DSLD row in `/Users/seancheick/Documents/DataSetDsld/...`
2. cleaned row in `scripts/output_*/cleaned/cleaned_batch_*.json`
3. enriched row in `scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json`

You must compare:

- `name`
- `raw_source_text`
- `ingredientGroup`
- `forms`
- `nestedIngredients`
- active vs inactive placement
- whether the parent label is structural and child forms are the real ingredients

If raw shows a blend/container/header and cleaned surfaces it as unmapped ingredient text, treat that as a code issue first.

---

## Evidence Standards for New or Updated Entries

### Identity evidence

Use at least one of:

- NIH ODS fact sheet
- NCCIH monograph
- FDA / USDA / other regulator identity source
- official branded ingredient site for branded identity confirmation
- PubChem / FDA UNII / NCBI / recognized reference identity source

### Clinical note requirements

If adding or updating a clinically meaningful IQM note:

- include mechanism, form relevance, or bioavailability relevance
- include PMID if available
- include DOI if available
- avoid vague filler text
- do not invent effect sizes

### Safety / harmful / banned evidence

Use:

- FDA / NIH / NCCIH first
- PubMed or DOI-backed source second
- official branded site never as sole safety evidence

---

## Routing Rules by Surface

### A. Cleaning active unmapped

Default assumption: route to IQM.

But before adding anything:

1. confirm it is not a structural row or parser artifact
2. confirm it is not actually harmful / banned / recalled
3. confirm it is not an excipient leak into actives
4. confirm the same molecule does not already exist in IQM under another alias/form

Typical destinations:

- IQM alias addition
- IQM new parent
- standardized_botanicals alias/new entry
- botanical_ingredients alias/new entry
- harmful_additives or banned_recalled if safety evidence supports it
- code fix if it is actually a leak/header/bug

### B. Cleaning inactive unmapped

Default assumption: route to `other_ingredients.json`.

But first ask:

1. is it structural/header/container text?
2. is it a true excipient/carrier/shell material?
3. is it actually a harmful additive?
4. is it a botanical identity used as inactive flavor/color source?
5. is it actually a therapeutic ingredient incorrectly placed in inactive section?

Typical destinations:

- other_ingredients alias/new entry
- harmful_additives alias/new entry
- botanical_ingredients alias/new entry
- proprietary_blends mapping-only descriptor
- IQM only if raw and context prove it is a therapeutic ingredient misplaced into inactive section
- filter/header unwrap code fix

### C. Enrichment unmapped

Treat this as a QA surface.

It usually means one of:

- IQM alias gap
- cleaner/enricher mismatch
- precedence bug
- non-scorable recognition bug
- harmful/banned routing bug

Do not assume it needs a new entry.

### D. Form fallback

Treat this as a scoring-accuracy surface.

Default action:

- add alias to the correct existing form

Do not add a new parent just because a fallback exists.
Do not add a new form unless the chemistry/form is truly distinct and supported.

---

## Specific Guardrails

### Active ingredients mostly go to IQM

This is the default.
But do not force obvious excipients, shell materials, structural labels, or safety ingredients into IQM.

### Inactive ingredients mostly go to other ingredients

This is the default.
But do not bury harmful / banned / recalled identities in other ingredients.

### Structural labels are not ingredients

Do not add these as ingredients unless they are true excipient concepts with user-facing value and stable identity.

Examples that usually should be filter/header logic, not DB entries:

- `Soft Gel Shell`
- `Shell Ingredients`
- `May also contain`
- `Aqueous Coating Solution`
- `Outer Shell`
- `Other`

### Shell materials should still be preserved

If the raw row is a structural parent with real child forms like gelatin, glycerin, water, colorants, or fish gelatin, preserve those child ingredients in output.
Do not preserve the structural parent as a fake ingredient.

### ZMA-like labels

Treat structural active blend labels as containers if raw DSLD shows child nutrients underneath them.
Do not add the parent as a new ingredient if the children are the real actives.

### Do not assume fallback means solved

If enrich fallback resolves something weakly, it can still be a clean-stage alias gap or a code drift issue.

Cleaning backlog is the primary truth for database coverage.
Enrichment fallback is QA, not proof of correctness.

### Display ledger rule

Do not reintroduce structural parents, wrappers, summary rows, or constituent leaves into scoring just because users need to see them.

If a row is label-visible but should not score:

- keep it in the display ledger
- mark it non-scoring
- preserve the real mapped/scorable children separately

User-facing label fidelity and scoring-safe ingredient normalization are separate concerns.

---

## Mandatory Investigation Checklist Per Candidate

For each candidate, do all of the following:

1. Search all routing DBs for the exact text and normalized variants.
2. Decide whether it is:
   - structural/filter
   - code bug
   - alias gap
   - new canonical
   - safety route
   - fallback-only gap
3. Inspect raw DSLD if suspicious or ambiguous.
4. Confirm same-ingredient identity before adding any alias.
5. Verify clinical / branded / safety claims with real sources.
6. Decide the exact routing target.
7. If code bug: write test first, then patch, then shadow-run.
8. If JSON change: use Python only.

---

## Required Outputs in Phase 1

Return these sections and then stop.

### 1. Findings table

| Label text | Surface | Classification | Proposed action | Target DB / file | Evidence | Confidence |

### 2. Code bug list

For each bug:

- exact file and function
- root cause
- why alias/data edits would be wrong
- proposed fix
- proposed regression test
- proposed shadow-run dataset

### 3. Proposed alias additions

For each alias:

- raw text
- canonical target
- why it is the same ingredient
- whether it is parent alias or form alias
- supporting source if branded/clinical

### 4. Proposed new entries

For each new entry:

- target file
- full proposed JSON object
- note with PMID/DOI if available
- why no existing canonical matched

### 5. Deferred / needs verification

For each deferred item:

- missing evidence
- exact next verification step

### 6. Impact estimate

Summarize expected effect on:

- clean active unmapped
- clean inactive unmapped
- enrichment unmapped
- fallback counts
- any scoring-sensitive forms

Then stop and wait for approval.

---

## Required Outputs in Phase 2

After approval, apply only the approved changes.

Then return:

### 1. Files changed

Exact file list.

### 2. Tests run

At minimum:

```bash
python3 scripts/db_integrity_sanity_check.py --strict
```

Plus targeted pytest for changed logic/data.

If JSON schema changed materially, also run:

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_db_integrity.py -q
```

### 3. Shadow-run verification

If code changed, run a small affected dataset verification.
Use the smallest relevant dataset or a narrow product slice.

Preferred options:

```bash
python3 scripts/clean_dsld_data.py --input-dir /Users/seancheick/Documents/DataSetDsld/<dataset>/ --output-dir scripts/output_<dataset> --config scripts/config/cleaning_config.json
```

```bash
python3 scripts/enrich_supplements_v3.py --input-dir scripts/output_<dataset>/cleaned --output-dir scripts/output_<dataset>_enriched --config scripts/config/enrichment_config.json
```

Or use `scripts/run_pipeline.py` when an end-to-end shadow run is required.

You must compare before/after for the affected labels.

### 4. Before/after deltas

Report:

- clean active unmapped delta
- clean inactive unmapped delta
- enrichment unmapped delta
- fallback delta
- exact labels fixed

### 5. Residual risk

Anything still deferred or ambiguous.

---

## JSON Writing Rule

When changing JSON DB files, use Python only.
Pattern:

```python
import json
from pathlib import Path

path = Path('scripts/data/<file>.json')
data = json.loads(path.read_text())
# mutate data in memory
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
```

---

## Practical Heuristics

### Safe alias addition criteria

Only add an alias when all are true:

- same molecule, same ingredient, same botanical, or same branded ingredient
- not broader than the canonical identity
- not a source species, process descriptor, or formulation wrapper pretending to be identity
- not likely to collide with another parent

### Common things that are bugs, not DB gaps

- punctuation variants
- curly apostrophes
- comma-modifier order
- shell/container parents
- dosage text leaking into names
- child forms lost under headers
- harmful vs OI precedence bugs
- enrich fallback masking a clean-stage alias gap

### Common things that are true alias gaps

- branded ingredient exact label text already known clinically
- exact salt form already represented under a parent
- botanical binomial + plant part variant
- clean raw label string differing only by validated wording, not identity

### Common things that are not safe aliases

- vague descriptors
- class labels
- formula names with multiple ingredients
- species/source-only labels when the canonical is a processed oil/extract/form
- constituent names when the canonical is the whole botanical, unless the project deliberately maps that constituent to the parent

### Common things that should become display-only, not mapped actives

- constituent leaves under a real parent
- standardization markers
- summary rows
- branded active wrappers whose children are the real ingredients
- source/material disclosures that are not the actual scored ingredient

---

## Final Principle

Do not optimize for “fewer unmapped names.”
Optimize for **correct identity resolution**.

A smaller unmapped list produced by bad aliases is worse than a larger unmapped list with clean logic.

The correct order is:

1. classify
2. inspect raw
3. verify against current DBs
4. verify with real sources
5. decide whether it is a bug or data gap
6. apply the smallest correct fix
7. verify in pipeline

### Regression protection

Never replace a proven exact fix with a broader normalization rule unless raw verification shows the exact fix is insufficient.

Never broaden matching just to reduce unmapped counts.

A precise fix that resolves 10 labels is better than a broad fix that resolves 100 labels but silently mis-maps 3.
