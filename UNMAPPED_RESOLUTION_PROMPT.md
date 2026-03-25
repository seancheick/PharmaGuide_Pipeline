# PharmaGuide Unmapped Ingredient Resolution — v2.0 Batch Protocol

## Role

Act as the **PharmaGuide clinical data + pipeline resolution agent**.
Your job is to resolve unmapped ingredients and form fallbacks with maximum identity accuracy while protecting:

- clinical correctness
- scoring integrity
- database schema integrity (no duplicate entries across files)
- identifier accuracy (CUI, UNII, CAS, PubChem CID must be API-verified)
- cleaner/enricher contract integrity
- user-facing trust

You are working inside this repo with filesystem access.
You must use the actual pipeline outputs, actual database contents, and real raw DSLD source files.
Do not guess. Do not improvise chemistry. Do not treat weak fallback matches as solved.

---

## Non-Negotiable Rules

### 1. Source of truth order

1. Raw DSLD source file
2. Current cleaner output in `scripts/output_*/cleaned/`
3. Current unmapped reports in `scripts/output_*/unmapped/`
4. Current enriched output in `scripts/output_*_enriched/enriched/`
5. Current fallback reports in `scripts/output_*_enriched/reports/`
6. Current database files in `scripts/data/`
7. Primary external sources for identity / safety / clinical claims
8. API verification tools (UMLS, GSRS, PubChem) for identifier validation

If raw DSLD contradicts cleaned output, raw wins.
If current code behavior contradicts stale documentation, code wins.

### 2. No guessing — verify everything with APIs

If identity is uncertain, do not add the alias or entry.
Mark it `needs_verification` and explain exactly what evidence is missing.

**Every identifier must be API-verified before writing to a data file:**

- CUI → `python3 scripts/api_audit/verify_cui.py --search "<name>"` or `--cui <CUI>`
- UNII → `python3 scripts/api_audit/verify_unii.py --search "<name>"`
- CAS → `python3 scripts/api_audit/verify_pubchem.py --search "<name>"` or `--cid <CID>`

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

### 6. No batch fixes on data files

Fix entries one at a time. Verify each change. Run targeted tests after each edit.
Batch operations skip entries and introduce errors. This is a medical-grade product.

### 7. No duplicate entries across files

Before adding ANY alias or new entry, search ALL routing databases:

- `ingredient_quality_map.json` (549 parents)
- `other_ingredients.json` (656 entries)
- `harmful_additives.json` (112 entries)
- `banned_recalled_ingredients.json` (~850 entries)
- `botanical_ingredients.json` (428 entries)
- `standardized_botanicals.json` (239 entries)

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

## What Counts as "Unmapped" in This Pipeline

There are **3 distinct surfaces**. Do not mix them.

### Surface A: Cleaning unmapped

Files:

- `scripts/output_*/unmapped/unmapped_active_ingredients.json`
- `scripts/output_*/unmapped/unmapped_inactive_ingredients.json`

Meaning: The cleaner could not map the ingredient against any known database or protection logic.
This is the **primary backlog for database growth**.

### Surface B: Enrichment unmapped

Files: `scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json`
Path: `product.ingredient_quality_data.ingredients_scorable[].mapped == false`

Meaning: The cleaner let the ingredient through as scorable, but enrichment failed to resolve it to IQM.
Usually: IQM alias gap, enricher routing bug, precedence bug, cleaner/enricher mismatch.

### Surface C: Form fallback

Files:

- `scripts/output_*_enriched/reports/parent_fallback_report.json`
- `scripts/output_*_enriched/reports/form_fallback_audit_report.json`

Meaning: The ingredient matched an IQM parent, but not the correct form alias, so it fell back to a conservative form.
Usually: IQM form alias gap, branded-token or normalization bug.

---

## Dynamic Scan — Run Every Session

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

| Database               | File                               | Purpose                                                                                            | Entry count |
| ---------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------- | ----------- |
| IQM                    | `ingredient_quality_map.json`      | Scorable actives                                                                                   | 549 parents |
| Other Ingredients      | `other_ingredients.json`           | Neutral excipients / carriers / shell                                                              | 656         |
| Harmful Additives      | `harmful_additives.json`           | Penalty-bearing inactive ingredients                                                               | 112         |
| Banned/Recalled        | `banned_recalled_ingredients.json` | Disqualification gate and penalty (watchlist and high_risk)                                        | ~850        |
| Botanical              | `botanical_ingredients.json`       | Basic botanical mapping                                                                            | 428         |
| Standardized Botanical | `standardized_botanicals.json`     | Standardized botanical extracts (bonus file if map meets threshold and standardization is present) | 239         |
| Proprietary Blends     | `proprietary_blends.json`          | Mapping-only descriptors - the enricher does not score these, the scorer handles penalty           | 14          |

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

1. Create both entries with consistent identifiers (same CUI, UNII, CAS)
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
Action: Add new entry with full schema + API-verified identifiers.

**IQM new entry requirements (critical — tests will fail if missing):**

- `category` and `category_enum` must be from the allowed enum: `amino_acids | antioxidants | enzymes | fatty_acids | fibers | functional_foods | herbs | minerals | other | probiotics | proteins | vitamins`
- Each form must have: `bio_score`, `natural`, `score` (= bio_score + 3 if natural, else bio_score), `absorption`, `absorption_structured` (with `quality` field), `notes`, `aliases`, `dosage_importance`
- Parent-level must have: `standard_name`, `category`, `cui`, `rxcui`, `forms`, `match_rules`, `category_enum`, `data_quality`, `aliases`, `external_ids`, `gsrs`
- If ingredient appears in both IQM and harmful_additives, must add to `cross_db_overlap_allowlist.json` — and add ALL shared alias terms, not just the entry name
- Update `_metadata.total_entries` and `_metadata.last_updated`

**harmful_additives new entry requirements:**

- Must match the full v5.1 schema (see Harmful_additive_audit_prompt.md)
- `severity_level`: high (-2pts), moderate (-1pt), low (-0.5pts) — based on evidence, not guessing
- Update `_metadata.total_entries` and `_metadata.last_updated`

### Bucket 6: Form fallback gap

Meaning: Parent is correct, but form alias is missing.
Action: Add alias to the correct existing IQM form.

### Bucket 7: Misspelling / typo

Meaning: Raw label has a typo (e.g., "Magnesuim" for "Magnesium", "Calcuim" for "Calcium").
Action: Add the misspelled variant as an alias to the correct entry. The pipeline normalizer should catch it, but adding as alias is the safety net.

### Bucket 8: Needs verification

Meaning: Identity unclear after DB + raw inspection.
Action: Do not write. Report what must be verified.

---

## Identifier Verification for Alias Additions

**This is the critical new step.** Before adding any alias, run this checklist:

### Step 1: Find the target entry

```bash
# Search all DBs for the canonical ingredient
python3 -c "
import json, sys
term = sys.argv[1].lower()
files = [
    ('scripts/data/ingredient_quality_map.json', 'iqm'),
    ('scripts/data/other_ingredients.json', 'other_ingredients'),
    ('scripts/data/harmful_additives.json', 'harmful_additives'),
    ('scripts/data/banned_recalled_ingredients.json', 'ingredients'),
    ('scripts/data/botanical_ingredients.json', 'botanical_ingredients'),
    ('scripts/data/standardized_botanicals.json', 'standardized_botanicals'),
]
for fpath, key in files:
    d = json.load(open(fpath))
    if key == 'iqm':
        for k, v in d.items():
            if k == '_metadata': continue
            if not isinstance(v, dict): continue
            sname = (v.get('standard_name') or '').lower()
            aliases = [a.lower() for a in v.get('aliases', []) if isinstance(a, str)]
            if term in sname or any(term in a for a in aliases):
                print(f'  IQM: {k} ({v.get(\"standard_name\")})')
    else:
        for e in d.get(key, []):
            sname = (e.get('standard_name') or '').lower()
            aliases = [a.lower() for a in e.get('aliases', []) if isinstance(a, str)]
            if term in sname or any(term in a for a in aliases):
                print(f'  {fpath.split(\"/\")[-1]}: {e.get(\"id\")} ({e.get(\"standard_name\")})')
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

| UMLS match?   | GSRS match?    | PubChem match? | Action                                                                      |
| ------------- | -------------- | -------------- | --------------------------------------------------------------------------- |
| Same CUI      | Same UNII      | Same CAS       | **Safe to add alias**                                                       |
| Same CUI      | Different UNII | —              | Investigate: may be different form/salt                                     |
| Different CUI | Same UNII      | —              | Investigate: UMLS may have separate concepts for form vs parent             |
| Different CUI | Different UNII | Different CAS  | **DO NOT add alias** — different compound                                   |
| No result     | No result      | No result      | Add alias only if strong textual evidence (brand name for known ingredient) |

### Step 4: Check for cross-DB collisions

```bash
# Verify the alias doesn't already exist in another DB file
python3 -c "
import json, sys
alias = sys.argv[1].lower()
# ... search all files for this exact alias text
" "<alias_text>"
```

If alias exists in another file → do NOT duplicate. Either:

- The alias is already covered (no action needed)
- The alias is in the wrong file (move it)
- Both files legitimately need it (add to `cross_db_overlap_allowlist.json`)

---

## Raw DSLD Verification Workflow

For any suspicious item, compare across the full pipeline:

1. **Raw DSLD**: What does the original label say?
2. **Cleaned output**: How did the cleaner normalize it?
3. **Enriched output**: Did enrichment resolve it? To what?
4. **Unmapped report**: Why is it unmapped?

Key fields to compare:

- `name` / `raw_source_text` / `ingredientGroup`
- `forms` / `nestedIngredients`
- Active vs inactive placement
- Whether the parent label is structural and child forms are the real ingredients

If raw shows a blend/container/header and cleaned surfaces it as unmapped ingredient text → code issue first.

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

| Script              | API      | What it checks                           | Key flags                           |
| ------------------- | -------- | ---------------------------------------- | ----------------------------------- |
| `verify_cui.py`     | UMLS     | CUI validity, concept name               | `--cui C0000000`, `--search "name"` |
| `verify_unii.py`    | FDA GSRS | UNII, CFR, DSLD, metabolic relationships | `--search "name"`                   |
| `verify_pubchem.py` | PubChem  | CAS, PubChem CID, molecular identity     | `--search "name"`, `--cid 12345`    |

Curated override files (prevent known bad auto-matches):

- `scripts/data/curated_overrides/cui_overrides.json` (66 entries)
- `scripts/data/curated_overrides/gsrs_policies.json` (88 entries)
- `scripts/data/curated_overrides/pubchem_policies.json` (17 entries)

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
4. **No duplicate entries across files.** Search all 6+ routing databases before adding anything.
5. **No hallucinated references.** If you can't find a real source, write "needs verification."
6. **Fix code bugs with code, not data.** Do not paper over parser/normalizer/precedence bugs with aliases.
7. **Raw DSLD verification is mandatory** for any suspicious or ambiguous case.
8. **Cross-check CAS numbers** — wrong CAS = wrong substance = patient safety risk.
9. **When in doubt → defer, don't guess.** A larger unmapped list with clean logic is better than a smaller list with bad aliases.
10. **The goal is correct identity resolution, not fewer unmapped names.**
