# PharmaGuide Unmapped Ingredient Resolution — v3.2 Batch Protocol

Updated: 2026-05-21 (refresh — SP-0..SP-6 vocab/taxonomy state; canonical fields in enriched output; alias-misplacement detection)

## Role

Act as the **PharmaGuide clinical data + pipeline resolution agent**.
Your job is to resolve unmapped ingredients and form fallbacks with maximum identity accuracy while protecting:

- clinical correctness
- scoring integrity
- database schema integrity (no duplicate entries across files)
- identifier accuracy (exact identifiers must be API-verified; governed-null cases must be documented)
- cleaner/enricher contract integrity
- canonical vocab discipline (SP-0..SP-6 — no parallel taxonomies)
- user-facing trust

You are working inside this repo with filesystem access.
You must use the actual pipeline outputs, actual database contents, and real raw DSLD source files.
Do not guess. Do not improvise chemistry. Do not treat weak fallback matches as solved.

---

## Pipeline Architecture Context (post-SP-6, shipped 2026-05-21)

Before adding anything, understand the layer contract. Every axis is answered by exactly **one** canonical vocab. No vocab does two jobs. No layer has two competing canonical forms.

| Axis | Vocab file | What it answers | Locked? |
|---|---|---|---|
| Product class | `data/product_type_vocab.json` (SP-1, 20 IDs) | WHICH class of product | No (additions need clinician review) |
| Physical state | `data/form_factor_vocab.json` (SP-3, 18 IDs) | HOW it's delivered | No |
| Ingredient identity | `canonical_id` / IQM parent (in `ingredient_quality_map.json`) | WHO it is | — |
| Ingredient category | `data/ingredient_category_vocab.json` (SP-4, 17 singular IDs) | WHAT it is | No |
| Functional role | `data/functional_roles_vocab.json` (SP-5, 32 IDs) | WHY it's in the product | **LOCKED v1.0.0** (clinician-signed) |
| Safety role | `banned_status` / `clinical_risk` (per entry) | Is it safe | — |
| Evidence (study design) | `data/evidence_level_vocab.json` (SP-6, 5 IDs) | How strong is the study | **LOCKED** |
| Evidence (qualitative) | `data/evidence_strength_vocab.json` (SP-6, 6 IDs) | How established is the rule | **LOCKED** |
| Evidence (study type) | `data/study_type_vocab.json` (SP-6, 7 IDs) | What kind of study | **LOCKED** |
| IQM parent UI label | `data/iqm_category_vocab.json` (12 LOCKED PLURAL IDs) | Display-only parent category | **LOCKED** |

**SP-0 source-of-truth contract:** `enrich` computes normalized vocab IDs **once**; downstream stages consume them; legacy fields only fallback for old batches. Never invent off-vocab values. Never create a parallel classifier.

### Canonical fields in fresh enriched output

After SP-1..SP-6 ship, every enriched product carries these new top-level fields:

```json
{
  "primary_type": "herbal_botanical",                      // SP-1 — one of 20 IDs
  "form_factor_canonical": "tablet",                       // SP-3 — one of 18 IDs
  "form_factor": "tablet",                                 // legacy preserved for old-batch fallback
  "supplement_taxonomy": {
    "primary_type": "herbal_botanical",
    "secondary_type": "...",
    "percentile_category": "...",
    "classification_confidence": 0.93,
    "classification_reasons": ["..."]
  }
}
```

**Per-ingredient-row state (intentional):**

- `category` is still the **IQM-plural** form (e.g. `"herbs"`, `"vitamins"`, `"minerals"`) — that's what `ingredient_quality_map.json` ships in `category_enum`.
- `category_canonical` is **NOT shipped at row level**. Downstream consumers call `scripts.supplement_type_utils.canonical_category(value)` at read time — that function is now a thin wrapper that delegates to `scripts.ingredient_category_normalizer.canonicalize_ingredient_category(value)` (vocab-driven). The hardcoded `CATEGORY_ALIASES` map is no longer the source of truth.
- `functional_roles` is populated for inactive rows by the existing system; `None` for active rows is expected.

When you propose alias/entry edits, your changes flow into this contract. **Any new IQM `category_enum` value MUST canonicalize cleanly via `canonicalize_ingredient_category()` — verify by calling that function on your proposed value before approval.**

### v4 routing depends on taxonomy

`scripts/scoring_v4/router.py` reads `supplement_taxonomy.primary_type` first, then maps to one of 4 v4 modules:

- omega (`omega3_marine_oil`, `omega3_plant_oil`, ...)
- multi_or_prenatal (`multivitamin`, `prenatal_multi`, ...)
- probiotic (`probiotic_blend`, `probiotic_single_strain`, ...)
- generic (everything else falls through)

If you propose a fix that should change the routed module, verify by re-running enrich+score on a slice and confirming the routed module matches the clinical class. **Do NOT add a new primary_type without clinician sign-off.**

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
4. Current database files in `scripts/data/` (data files + canonical vocab files)
5. Canonical vocab JSONs (`product_type_vocab`, `form_factor_vocab`, `ingredient_category_vocab`, `functional_roles_vocab`, `evidence_*_vocab`, `study_type_vocab`, `iqm_category_vocab`) — these are the contract
6. Primary external sources for identity / safety / clinical claims
7. API verification tools in `scripts/api_audit/`

If the exact run folder contradicts canonical corpus, inspect both and explain why.
If raw DSLD contradicts cleaned output, raw wins.
If current code behavior contradicts stale documentation, code wins.
**If a proposed value contradicts a LOCKED vocab (`functional_roles_vocab`, `evidence_*_vocab`, `iqm_category_vocab`), the vocab wins.** Adding to a LOCKED vocab requires clinician review — flag as deferred, never sneak in.

### 2. No guessing — verify exact identity with APIs when the schema expects it

If identity is uncertain, do not add the alias or entry.
Mark it `needs_verification` and explain exactly what evidence is missing.

**UNII lookups are offline-first via the local cache (~172K substances):**

```bash
# The unii_cache.py module is used automatically by verify_unii.py
# To rebuild/refresh the local cache from FDA bulk download:
python3 scripts/api_audit/build_unii_cache.py

# Direct lookup (offline, instant for ~172K known substances):
python3 -c "
from scripts.unii_cache import UniiCache
cache = UniiCache()
print(cache.lookup('ascorbic acid'))       # → 'PQ6CK8PD0R' (offline)
print(cache.reverse_lookup('PQ6CK8PD0R')) # → 'ASCORBIC ACID'
"
```

Use API verification whenever adding or changing:

- CUI → `python3 scripts/api_audit/verify_cui.py --search "<name>"` or `--cui <CUI>`
- UNII → `python3 scripts/api_audit/verify_unii.py --search "<name>"` (uses offline cache first, falls back to GSRS)
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
- cases where `primary_type` in supplement_taxonomy looks wrong vs the actual formula

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

If the root cause is a cleaner bug, enricher bug, precedence bug, structural-header bug, normalization bug, or **a taxonomy/vocab routing bug**, fix the code first.
Do not paper over a code bug by stuffing labels into a database.

### 6. No blind batch edits on data files

You may ANALYZE large batches and group them by confidence level, but do not apply JSON or code edits blindly in bulk.
Apply only highly confident approved changes, and verify each changed entry or tightly related micro-batch with tests and integrity checks.
This is a medical-grade product.

### 7. No duplicate entries across files

Before adding ANY alias or new entry, search ALL routing databases (counts are illustrative — always read `_metadata.total_entries` from the live file):

- `ingredient_quality_map.json` (~621 IQM parents — schema 5.4.0)
- `other_ingredients.json` (~684 entries, schema 5.4.0)
- `harmful_additives.json` (~116 entries, schema 5.4.0)
- `banned_recalled_ingredients.json` (~156 entries, schema 5.4.1)
- `botanical_ingredients.json` (~482 entries, schema 5.2.0)
- `standardized_botanicals.json` (~239 entries)
- `botanical_marker_contributions.json` (source botanical → bioactive marker contributions for scoring)
- `proprietary_blends.json` (~19 entries)
- `cross_db_overlap_allowlist.json` (~39 entries — read live)

Do not rely on hard-coded entry counts in this prompt; counts evolve. Always read `_metadata.total_entries` from the live file.

### 7.5. Identity vs Bioactivity boundary

A specific class of mapping bug has dedicated handling:

- **Source botanicals (kelp, marigold, citrus extract, broccoli sprout, etc.) must route to `botanical_ingredients.json`**, NOT to an IQM marker entry (iodine, lutein, bioflavonoids, sulforaphane).
- The cleaner's reverse-index uses an exclusion list to prevent source-botanical aliases from being added to IQM markers. If the canonical_crossing audit finds a source-only alias inside an IQM marker, the fix is to relocate it to the botanical canonical and (if a real marker contribution exists) configure it in `botanical_marker_contributions.json`.
- This was the 8-phase Identity-vs-Bioactivity split landed in May 2026 — see `reports/identity_vs_bioactivity_impact_report.md`. 133 kelp/marigold/citrus identity leaks were fixed; auditors should treat new occurrences of this pattern as critical-severity findings.

If the ingredient already exists in another file, do NOT create a duplicate. Either:

- Add the alias to the existing entry in the correct file
- Or add to `cross_db_overlap_allowlist.json` if legitimate overlap is needed (allowlist now has ~39 entries — read live)

### 8. Identifier-backed alias verification (HARDENED)

Before adding an alias to an existing entry, verify the alias actually refers to the **same compound**:

1. Search the alias in UMLS → does it resolve to the same CUI as the target entry?
2. Search the alias in GSRS (offline cache first, then API) → does it resolve to the same UNII?
3. Search the alias in PubChem → does it resolve to the same CAS/CID?

**All three identifiers must agree** (or be governed-null with documentation). If ANY identifier disagrees → **do not add the alias**. Instead:

- The alias may belong to a different compound → investigate, propose moving to correct entry
- The alias may be a derivative/salt/different form → create a separate entry or decouple
- The alias may be misspelled → fix the spelling, then verify
- **The alias may already be wrongly placed in another entry → see §8.5 alias-misplacement detection**

**Common traps:**

- "Ashwagandha" vs "Ashwagandha root extract" → different GSRS substances
- "Vitamin B12" vs "Cyanocobalamin" vs "Methylcobalamin" → different forms, different CUIs
- "Magnesium" vs "Magnesium Oxide" vs "Magnesium Glycinate" → different compounds entirely
- Plant common name vs latin binomial → same plant, OK as aliases
- Branded name vs generic → OK if same compound (verify via UNII)
- `from S. cerevisiae` source text → triggers cerevisiae yeast aliases in `_CEREVISIAE_YEAST_ALIAS` dict in `enrich_supplements_v3.py`; missing alias = bio_score fallback, not a true new entry
- "Marine collagen" is **not** omega-3 — historical bug — `_is_omega_like` should only match `\b(epa|dha)\b` word-boundary, not substring "dha"

### 8.5. Alias misplacement detection (NEW — required workflow)

**Scenario:** While inspecting an entry to add an alias, you notice an existing alias that looks suspicious (different ingredient identity, different botanical, different active form). This is a sign of a prior false match that needs to be fixed before any new aliases are added.

**Required workflow** the moment you suspect misplacement:

1. **API-verify the suspicious alias against the entry's CUI/UNII/CAS:**
   - `verify_unii.py --search "<suspicious_alias>"` → does it return the entry's UNII?
   - `verify_cui.py --search "<suspicious_alias>"` → does it return the entry's CUI?
   - `verify_pubchem.py --search "<suspicious_alias>"` → does it return the entry's CAS?

2. **If identifiers disagree → flag the misplacement.** Do NOT add your new alias yet. The entry has a contamination that may have caused downstream scoring/routing errors.

3. **Propose the correct home:**
   - Look up where the suspicious alias *should* live (using UNII/CUI/CAS against the right DB)
   - Document: which file, which entry, which canonical_id should own it
   - Check if relocating it would create or fix a cross-DB overlap (update `cross_db_overlap_allowlist.json` if so)

4. **Report the misplacement in TABLE 4 (Code/Data Bugs):**
   - Source entry that has the misplaced alias
   - The misplaced alias text
   - Identifier mismatch evidence (UNII/CUI/CAS diff)
   - Proposed correct destination
   - Whether this likely caused upstream scoring/routing issues (run a quick check on enriched output)

5. **Do not silently move aliases.** Misplaced aliases get the same Phase 1 → approval → Phase 2 treatment as any other change. They go through `db_integrity_sanity_check.py` and shadow-run validation because they may shift product scores.

**Example trap:** "Kelp" found as an alias of "Iodine" (IQM marker) is the Identity-vs-Bioactivity bug — same class as §7.5. Kelp's UNII is `XXXX` (the seaweed), Iodine's UNII is `9679TKL0H6`. Disagreement → flag, relocate to `botanical_ingredients.json`, configure marker contribution in `botanical_marker_contributions.json` if iodine is a real marker contribution from kelp.

### 9. Shadow-run after code fixes

If you change cleaner, normalizer, enricher, batch processor, scorer contract, matching logic, **or any canonical vocab**, you must run a small shadow verification on an affected dataset slice and compare before/after.

Use `scripts/shadow_score_comparison.py` and `scripts/regression_snapshot.py` for automated before/after diffing.

**Vocab-change shadow check:** if you touch any canonical vocab JSON, also run:

```bash
python3 -m pytest scripts/tests/ -k "vocab or taxonomy or canonical or sp1 or sp2 or sp3 or sp4 or sp5 or sp6" -q
```

This catches drift across Flutter parity, canonical-ID enforcement, and v4 routing tests.

### 10. Verification loop is mandatory

For every approved batch, follow this exact order:

1. Add targeted failing tests first
2. Implement the narrowest correct fix
3. Run targeted tests
4. Run `python3 scripts/db_integrity_sanity_check.py --strict`
5. Run `python3 -m pytest scripts/tests/ -k "overlap or integrity or schema or vocab" -q`
6. Run a real shadow clean on the exact raw DSLD source files for the affected labels
7. Confirm the target labels are cleared from the intended unmapped surface
8. Confirm prior fixes did not regress (`primary_type`, `form_factor_canonical`, `category_canonical` stable for unrelated products)

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
  - API verification agrees (CUI + UNII + CAS) or current repo-governed identity already supports the mapping
  - no cross-DB collision
  - no code bug suspected
  - no canonical vocab conflict (new value canonicalizes via existing vocab)
- **Lane B: Probable but not yet production-safe**
  - likely same identity, but API evidence is incomplete or mixed
  - or the alias appears to collide with another DB/file
  - or active vs inactive routing needs careful review
  - or `primary_type` / `form_factor_canonical` would shift in a way that needs taxonomy review
- **Lane C: Likely bug / structural issue**
  - parser artifact, blend header, shell/container row, normalization drift, precedence mismatch, cleaner/enricher disagreement, **alias misplacement (§8.5)**, **taxonomy mis-route**, or **vocab gap**

Allowed speed strategy:

- Start with Lane A cases first
- Keep Lane B in `needs_verification`
- Escalate Lane C to code review / bug-fix workflow

Never promote Lane B or Lane C items into production data just to clear backlog counts.

### Phase 1: Analyze only (do NOT write anything)

1. Run the dynamic scan
2. Inspect the relevant raw DSLD source files
3. Inspect current DB coverage across all routing targets
4. **API-verify identifiers** for each candidate (CUI, UNII via offline cache, CAS)
5. **Check canonical vocab compatibility:**
   - For active IQM additions: verify proposed `category_enum` canonicalizes via `canonicalize_ingredient_category()`
   - For active IQM additions: verify the IQM parent's `iqm_category_vocab` parent label exists in `data/iqm_category_vocab.json` (LOCKED — do not invent)
   - For inactive additions: verify `functional_roles[]` entries are all in `data/functional_roles_vocab.json` (LOCKED)
   - Check if `supplement_taxonomy.primary_type` would shift for affected products and whether that's correct
6. Classify each unmapped case by root cause
7. Identify code bugs separately from data gaps
8. For alias additions: verify the alias resolves to the same CUI/UNII/CAS as the target entry
9. **Run §8.5 alias-misplacement check on every entry you touch**
10. Propose exact fixes in a batch of 8-12
11. **Stop and wait for approval**

### Phase 2: Apply only after approval

After approval, for each approved item:

1. Pin a failing test for the expected state
2. Make the approved JSON or code change (one entry at a time)
3. Verify the test passes
4. Run integrity checks (`db_integrity_sanity_check.py --strict`)
5. If any canonical vocab touched, run vocab parity tests
6. Move to next item

After the batch:

1. Run full integrity suite
2. Run shadow rerun for affected cases
3. Confirm canonical fields stable (`primary_type`, `form_factor_canonical`, `category`) on unrelated products
4. Report before/after deltas

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
                                     #   Top-level fields now include:
                                     #     primary_type (SP-1, one of 20 IDs)
                                     #     form_factor_canonical (SP-3, one of 18 IDs)
                                     #     supplement_taxonomy.{primary_type, secondary_type,
                                     #       percentile_category, classification_confidence,
                                     #       classification_reasons}
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

### Surface C validation rule (HARDENED for taxonomy)

For every fallback case, do not only check that a fallback occurred.
Also verify whether the fallback-selected form is actually the correct conservative form, **AND whether the product's `supplement_taxonomy.primary_type` makes clinical sense for that ingredient**.

Required check:

1. Inspect raw DSLD label text and any explicit form wording
2. Compare the raw form wording to the matched IQM parent and all existing IQM forms
3. Read `supplement_taxonomy.primary_type` for the affected product — does it match the ingredient class?
   - Omega-3 ingredient in a `multivitamin` product → check if the v4 router is mis-routing
   - Multivitamin ingredient in a `specialty` product → check classifier
   - If primary_type looks wrong, this is a Lane C taxonomy bug, not a Surface C form gap
4. Decide whether:
   - the fallback form is correct and acceptable
   - the parent is correct but the specific form alias is missing
   - the fallback chose the wrong form
   - the parent match itself may be wrong
   - **the product's primary_type is wrong and the form fallback is just a downstream symptom**

**Cerevisiae yeast enricher trap:** When raw label text contains "from S. cerevisiae culture" or similar, the enricher's `_CEREVISIAE_YEAST_ALIAS` dict maps the ingredient to a yeast-specific form. If the alias is missing, the ingredient falls back to `(unspecified)` form losing the bio_score bonus — this is an alias gap, not a form fallback bug.

**`prefix='from'` enricher trap:** Forms whose text begins with "from" are treated as source-descriptors and skipped by the enricher. If a chelate-class form name begins with "from", it will not match even if an alias exists. This requires a narrow code fix in the enricher, not just an alias addition.

If the fallback-selected form is wrong, do not treat the case as resolved.
Classify it as either:

- IQM form alias gap (Surface C, alias-only)
- enricher/scoring form-selection bug (Lane C, code fix)
- parent-match bug (Lane C, code fix)
- taxonomy mis-route (Lane C, taxonomy fix — affects v4 routing)

---

## Dynamic Scan — Run Every Session

```bash
python3 <<'SCAN_EOF'
import glob, json, os

os.chdir(os.path.expanduser('~/Downloads/dsld_clean/scripts'))

print('=' * 72)
print('UNMAPPED / FALLBACK SCAN — CURRENT STATE')
print('=' * 72)

active_files = sorted(glob.glob('products/output_*/unmapped/unmapped_active_ingredients.json'))
inactive_files = sorted(glob.glob('products/output_*/unmapped/unmapped_inactive_ingredients.json'))
needs_active_files = sorted(glob.glob('products/output_*/unmapped/needs_verification_active_ingredients.json'))
needs_inactive_files = sorted(glob.glob('products/output_*/unmapped/needs_verification_inactive_ingredients.json'))
enriched_files = sorted(glob.glob('products/output_*_enriched/enriched/enriched_cleaned_batch_*.json'))
parent_fallback_files = sorted(glob.glob('products/output_*_enriched/reports/parent_fallback_report.json'))
form_audit_files = sorted(glob.glob('products/output_*_enriched/reports/form_fallback_audit_report.json'))

def safe_load(fp):
    try:
        with open(fp) as f:
            return json.load(f)
    except Exception as e:
        print(f'  WARNING: Failed to load {fp}: {e}')
        return {}

def brand_from_path(fp):
    parts = fp.replace('\\', '/').split('/')
    for p in parts:
        if p.startswith('output_') and not p.endswith('_enriched') and not p.endswith('_scored'):
            return p.replace('output_', '')
    return 'unknown'

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

enrich_unmapped = {}
products = 0
scorable = 0
primary_type_counts = {}
form_factor_canonical_counts = {}
for fp in enriched_files:
    data = safe_load(fp)
    if isinstance(data, list):
        batch = data
    else:
        batch = data.get('products', [])
    for p in batch:
        products += 1
        ptype = p.get('primary_type') or p.get('supplement_taxonomy', {}).get('primary_type') or 'MISSING'
        primary_type_counts[ptype] = primary_type_counts.get(ptype, 0) + 1
        ffc = p.get('form_factor_canonical') or 'MISSING'
        form_factor_canonical_counts[ffc] = form_factor_canonical_counts.get(ffc, 0) + 1
        for ing in p.get('ingredient_quality_data', {}).get('ingredients_scorable', []):
            scorable += 1
            if not ing.get('mapped', True):
                name = ing.get('name', 'UNKNOWN')
                enrich_unmapped[name] = enrich_unmapped.get(name, 0) + 1

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

vocab_files = {
    'product_type (SP-1)': 'data/product_type_vocab.json',
    'form_factor (SP-3)': 'data/form_factor_vocab.json',
    'ingredient_category (SP-4)': 'data/ingredient_category_vocab.json',
    'functional_roles (SP-5, LOCKED)': 'data/functional_roles_vocab.json',
    'evidence_level (SP-6, LOCKED)': 'data/evidence_level_vocab.json',
    'evidence_strength (SP-6, LOCKED)': 'data/evidence_strength_vocab.json',
    'study_type (SP-6, LOCKED)': 'data/study_type_vocab.json',
    'iqm_category (LOCKED)': 'data/iqm_category_vocab.json',
}

print('\n[DATABASE STATUS]')
for label, fp in db_files.items():
    try:
        d = json.load(open(fp))
        total = d.get('_metadata', {}).get('total_entries', '?')
        ver = d.get('_metadata', {}).get('schema_version', '?')
        updated = d.get('_metadata', {}).get('last_updated', '?')
        print(f'  {label:20s}: {total:>5} entries (schema {ver}, updated {updated})')
    except Exception as e:
        print(f'  {label:20s}: ERROR - {e}')

print('\n[CANONICAL VOCAB STATUS]')
for label, fp in vocab_files.items():
    try:
        d = json.load(open(fp))
        meta = d.get('_metadata', {})
        ver = meta.get('schema_version') or meta.get('version', '?')
        # Count entries — different vocabs use different keys
        n = 0
        for k, v in d.items():
            if k == '_metadata': continue
            if isinstance(v, list):
                n = len(v)
                break
            if isinstance(v, dict):
                n = len(v)
                break
        print(f'  {label:32s}: {n:>3} IDs (v{ver})')
    except Exception as e:
        print(f'  {label:32s}: ERROR - {e}')

# UNII cache status
try:
    uc = json.load(open('data/fda_unii_cache.json'))
    m = uc.get('_metadata', {})
    n = len([k for k in uc if k != '_metadata'])
    print(f'\n[UNII CACHE]: {n:,} substances loaded (source: {m.get("source","?")})')
    if n < 1000:
        print('  WARNING: Cache appears empty — run: python3 api_audit/build_unii_cache.py')
except Exception as e:
    print(f'\n[UNII CACHE]: not found or error ({e}) — run: python3 api_audit/build_unii_cache.py')

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

print('\n[TAXONOMY DISTRIBUTION — SP-1 primary_type]')
for ptype, count in sorted(primary_type_counts.items(), key=lambda x: -x[1])[:15]:
    flag = ' ← MISSING' if ptype == 'MISSING' else ''
    print(f'  {count:5d}  {ptype}{flag}')

print('\n[FORM FACTOR DISTRIBUTION — SP-3 form_factor_canonical]')
for ffc, count in sorted(form_factor_canonical_counts.items(), key=lambda x: -x[1])[:15]:
    flag = ' ← MISSING' if ffc == 'MISSING' else ''
    print(f'  {count:5d}  {ffc}{flag}')

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

### Raw DSLD physicalState codes (SP-3 mapping)

Real DSLD products carry `physicalState.langualCode` values. SP-3 form_factor_normalizer canonicalizes these:

| LangualCode (uppercase or lowercase) | Maps to `form_factor_canonical` |
|---|---|
| E0159 | `capsule` |
| E0161 | `softgel` |
| E0155 | `tablet` |
| E0162 | `powder` |
| E0176 | `gummy` |
| E0165 | `liquid` |
| E0172 | `other` (catch-all; text "Tea Bag" maps to `tea_bag`) |
| E0177 | `unknown` |

If you see a product where `form_factor_canonical` is `MISSING` or wrong vs the raw DSLD physicalState, the normalizer needs a code fix — not a data fix.

### Pipeline repo root

`/Users/seancheick/Downloads/dsld_clean`

Important subpaths:

| Path                                 | Purpose                                                                           |
| ------------------------------------ | --------------------------------------------------------------------------------- |
| `scripts/`                           | All pipeline scripts                                                              |
| `scripts/data/`                      | Reference JSON databases + canonical vocab JSONs                                  |
| `scripts/data/fda_unii_cache.json`   | Offline UNII substance cache (~172K substances, built by `build_unii_cache.py`)   |
| `scripts/data/product_type_vocab.json`        | SP-1 — 20 IDs                                                            |
| `scripts/data/form_factor_vocab.json`         | SP-3 — 18 IDs                                                            |
| `scripts/data/ingredient_category_vocab.json` | SP-4 — 17 singular IDs                                                   |
| `scripts/data/functional_roles_vocab.json`    | SP-5 — 32 LOCKED IDs                                                     |
| `scripts/data/evidence_level_vocab.json`      | SP-6 — 5 LOCKED IDs                                                      |
| `scripts/data/evidence_strength_vocab.json`   | SP-6 — 6 LOCKED IDs                                                      |
| `scripts/data/study_type_vocab.json`          | SP-6 — 7 LOCKED IDs                                                      |
| `scripts/data/iqm_category_vocab.json`        | 12 LOCKED PLURAL parent-display IDs                                      |
| `scripts/data/curated_overrides/`    | Manual CUI/PubChem/GSRS policy overrides                                          |
| `scripts/data/curated_interactions/` | Drug-supplement interaction data                                                  |
| `scripts/data/fda_caers/`            | FDA CAERS adverse event data                                                      |
| `scripts/data/fda_drug_labels/`      | FDA drug label data                                                               |
| `scripts/data/suppai_import/`        | SuppAI import data                                                                |
| `scripts/api_audit/`                 | API verification scripts                                                          |
| `scripts/tests/`                     | Test suites (incl. SP-0..SP-6 vocab/parity tests)                                 |
| `scripts/config/`                    | cleaning_config.json, enrichment_config.json, scoring_config.json                 |
| `scripts/products/`                  | Pipeline output per dataset (brands, categories — clean/enriched/scored triplets) |
| `scripts/supplement_taxonomy.py`     | SP-1 classifier → primary_type                                                    |
| `scripts/form_factor_normalizer.py`  | SP-3 → form_factor_canonical                                                      |
| `scripts/ingredient_category_normalizer.py` | SP-4 → canonical category (read-time, vocab-driven)                       |
| `scripts/supplement_type_utils.py`   | Thin wrapper — `canonical_category()` delegates to SP-4 normalizer                |
| `scripts/scoring_v4/router.py`       | Taxonomy-first router (primary_type → omega/multi_or_prenatal/probiotic/generic)  |

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

| Database               | File                               | Approx Entries | Schema | Purpose                                           |
| ---------------------- | ---------------------------------- | -------------- | ------ | ------------------------------------------------- |
| IQM                    | `ingredient_quality_map.json`      | ~621           | 5.4.0  | Scorable active ingredients (bonuses)             |
| Other Ingredients      | `other_ingredients.json`           | ~684           | 5.4.0  | Neutral excipients / carriers / shell             |
| Harmful Additives      | `harmful_additives.json`           | ~116           | 5.4.0  | Penalty-bearing inactive ingredients              |
| Banned/Recalled        | `banned_recalled_ingredients.json` | ~156           | 5.4.1  | Disqualification gate and penalty                 |
| Botanical              | `botanical_ingredients.json`       | ~482           | 5.2.0  | Basic botanical mapping                           |
| Standardized Botanical | `standardized_botanicals.json`     | ~239           | 5.x    | Standardized botanical extracts (bonus)           |
| Proprietary Blends     | `proprietary_blends.json`          | ~19            | 5.x    | Descriptor-level mapping (scorer handles penalty) |
| Cross-DB Overlap       | `cross_db_overlap_allowlist.json`  | ~39            | 5.x    | Legitimate multi-file entries                     |

**Always read `_metadata.total_entries` and `_metadata.schema_version` from the live file** — counts and schemas evolve. Numbers above reflect state at 2026-05-21.

### Canonical vocab references (NOT routing targets — they govern downstream contracts)

| Vocab file                          | Count | Locked? | What you must check |
|-------------------------------------|-------|---------|---------------------|
| `product_type_vocab.json` (SP-1)    | 20    | No      | If your fix would change `supplement_taxonomy.primary_type` on existing products, run shadow score comparison. Adding a new primary_type needs clinician + v4 router update. |
| `form_factor_vocab.json` (SP-3)     | 18    | No      | New form factors require updates to `form_factor_normalizer.py` mapping table and Flutter parity test. |
| `ingredient_category_vocab.json` (SP-4) | 17 | No      | Any new IQM `category_enum` must canonicalize via `canonicalize_ingredient_category()`. |
| `functional_roles_vocab.json` (SP-5)| 32    | **YES** | Inactive `functional_roles[]` entries MUST be vocab IDs. Adding/removing roles requires clinician review. |
| `evidence_level_vocab.json` (SP-6)  | 5     | **YES** | Study-design tiers. Locked. |
| `evidence_strength_vocab.json` (SP-6)| 6    | **YES** | Qualitative evidence tiers. Locked. |
| `study_type_vocab.json` (SP-6)      | 7     | **YES** | Study types. Locked. |
| `iqm_category_vocab.json`           | 12    | **YES** | PLURAL parent-display labels for IQM. Do not invent new ones. |

### Supporting data files (not routing targets, but referenced during resolution)

| File                                   | Purpose                                                           |
| -------------------------------------- | ----------------------------------------------------------------- |
| `absorption_enhancers.json`            | Absorption enhancer classification                                |
| `allergens.json`                       | Big 8 allergen classification                                     |
| `backed_clinical_studies.json`         | PMID-backed clinical evidence bonuses (all content-verified)      |
| `synergy_cluster.json`                 | Tiered synergy bonuses with canonical_ids for IQM matching        |
| `rda_optimal_uls.json`                 | RDA/AI/UL dosing benchmarks                                       |
| `medication_depletions.json`           | Drug-induced nutrient depletions                                  |
| `ingredient_classification.json`       | Active/inactive classification rules                              |
| `ingredient_interaction_rules.json`    | Interaction rule engine                                           |
| `drug_classes.json`                    | Drug class definitions                                            |
| `timing_rules.json`                    | Dosing timing guidance                                            |
| `clinically_relevant_strains.json`     | Probiotic strain specificity                                      |
| `color_indicators.json`                | Color additive classification                                     |
| `enhanced_delivery.json`               | Enhanced delivery system bonuses                                  |
| `functional_ingredient_groupings.json` | Functional grouping definitions                                   |
| `manufacturer_violations.json`         | Brand trust penalties                                             |
| `rda_therapeutic_dosing.json`          | Therapeutic dosing ranges                                         |
| `fda_unii_cache.json`                  | Offline UNII substance cache — instant lookup, no API call        |
| `botanical_marker_contributions.json`  | Source botanical → bioactive marker contributions                 |

### Curated override files (prevent known bad auto-matches)

| File                                      | Content                                    |
| ----------------------------------------- | ------------------------------------------ |
| `curated_overrides/cui_overrides.json`    | CUI override entries                       |
| `curated_overrides/gsrs_policies.json`    | GSRS lookup suppression list               |
| `curated_overrides/pubchem_policies.json` | PubChem lookup suppression list            |

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
2. Add the ingredient to `cross_db_overlap_allowlist.json` (~39 entries currently)

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
Action: Patch code, add regression test, shadow-run via `shadow_score_comparison.py`.

### Bucket 3: Routing / precedence bug

Examples: Cleaner maps but enricher misses, IQM beats harmful when harmful should win, `prefix='from'` blocking a chelate form, v4 router gets wrong module because `primary_type` is wrong
Action: Patch code, add regression test, shadow-run.

### Bucket 4: True alias gap (MOST COMMON)

Meaning: The identity already exists in the correct DB, but the exact raw label text is not covered.
Action: Add alias only — **after identifier verification confirms same compound** (use offline UNII cache first). Also: §8.5 misplacement check on the target entry before adding.

### Bucket 5: True new canonical entry

Meaning: Ingredient does not exist anywhere in any target DB.
Action: Add new entry with full schema + verified identifiers where exact identity is available.

**IQM new entry requirements (critical — tests will fail if missing):**

- `category` and `category_enum` must be from the allowed enum: `amino_acids | antioxidants | enzymes | fatty_acids | fibers | functional_foods | herbs | minerals | other | probiotics | proteins | vitamins`
- **`category_enum` MUST canonicalize via `canonicalize_ingredient_category()`** — verify by calling the function on your proposed value before approval
- Each form must have: `bio_score`, `natural`, `score` (= bio_score + 3 if natural, else bio_score), `absorption`, `absorption_structured` (with `quality` field), `notes`, `aliases`, `dosage_importance`
- Parent-level must have: `standard_name`, `category`, `cui`, `rxcui`, `forms`, `match_rules`, `category_enum`, `data_quality`, `aliases`, `external_ids`, `gsrs`
- If ingredient appears in both IQM and harmful_additives, must add to `cross_db_overlap_allowlist.json` — and add ALL shared alias terms, not just the entry name
- Update `_metadata.total_entries` and `_metadata.last_updated`
- If an exact UMLS concept does not exist, use reviewed null-governance fields instead of forcing a wrong CUI
- If the entry has a parent-display category, it must be one of the 12 LOCKED IDs in `iqm_category_vocab.json`

**harmful_additives new entry requirements:**

- Must match the current schema version (5.4.0 as of 2026-05-21) — see live `_metadata.schema_version`
- `severity_level`: high (-2pts), moderate (-1pt), low (-0.5pts) — based on evidence, not guessing
- `functional_roles[]` MUST be IDs from the LOCKED SP-5 vocab — no invented roles
- Update `_metadata.total_entries` and `_metadata.last_updated`

**other_ingredients / botanical_ingredients new entry requirements:**

- `functional_roles[]` MUST be IDs from the LOCKED SP-5 vocab
- Verified identifiers (CUI/UNII/CAS) where exact identity exists

### Bucket 6: Form fallback gap

Meaning: Parent is correct, but form alias is missing.
Action: Add alias to the correct existing IQM form only after confirming the fallback-selected form is not already the correct conservative match.

If the fallback-selected form itself is wrong, do not treat this as alias-only.
Escalate to:

- enricher/scoring form-selection bug
- or parent-match bug
- or taxonomy mis-route (v4 router using wrong primary_type)

### Bucket 7: Misspelling / typo

Meaning: Raw label has a typo (e.g., "Magnesuim" for "Magnesium", "Calcuim" for "Calcium").
Action: Add the misspelled variant as an alias to the correct entry. The pipeline normalizer should catch it, but adding as alias is the safety net. Identifier verification still required (same CUI/UNII as target).

### Bucket 8: Alias misplacement (NEW)

Meaning: An existing alias in an entry resolves (via API) to a DIFFERENT compound than the entry. The entry has been silently contaminated and is potentially mis-scoring products.
Action: §8.5 workflow — flag in TABLE 4, propose correct destination, do not silently move. May require shadow-score comparison to measure downstream impact.

### Bucket 9: Needs verification

Meaning: Identity unclear after DB + raw inspection.
Action: Do not write. Report what must be verified.

---

## Identifier Verification for Alias Additions

**This is the critical step.** Before adding any alias, run this checklist.

### Step 1: Find the target entry

```bash
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
# Check UNII (offline cache first — no API call needed for ~172K known substances)
python3 scripts/api_audit/verify_unii.py --search "<alias_text>"
# Compare UNII with the target entry's external_ids.unii

# If not in cache, rebuild the cache first:
# python3 scripts/api_audit/build_unii_cache.py

# Check UMLS
python3 scripts/api_audit/verify_cui.py --search "<alias_text>"
# Compare CUI with the target entry's CUI

# Check PubChem
python3 scripts/api_audit/verify_pubchem.py --search "<alias_text>"
# Compare CAS/CID with the target entry's external_ids
```

### Step 2b: Audit existing aliases on the target entry (§8.5)

Before adding your new alias, scan the entry's existing aliases for misplacements. If any existing alias has a SUSPECT name (e.g., a botanical inside a mineral entry, a salt form inside a base compound entry, a different brand inside a generic entry), API-verify it:

```bash
# For each suspect alias on the target entry:
python3 scripts/api_audit/verify_unii.py --search "<suspect_alias>"
# Does it return the target entry's UNII?
# If NO — flag in TABLE 4 with proposed correct destination
```

### Step 3: Decision matrix

| UMLS match?   | GSRS match?    | PubChem match? | Action                                                                                              |
| ------------- | -------------- | -------------- | --------------------------------------------------------------------------------------------------- |
| Same CUI      | Same UNII      | Same CAS       | **Safe to add alias** (after §8.5 check on target entry passes)                                     |
| Same CUI      | Different UNII | —              | Investigate: may be different form/salt                                                             |
| Different CUI | Same UNII      | —              | Investigate: UMLS may have separate concepts for form vs parent                                     |
| Different CUI | Different UNII | Different CAS  | **DO NOT add alias** — different compound                                                           |
| No result     | No result      | No result      | Keep in `needs_verification` unless current repo-governed identity already proves exact equivalence |

### Step 4: Check for cross-DB collisions

```bash
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
- The alias is in the wrong file (move it — see §8.5)
- Both files legitimately need it (add to `cross_db_overlap_allowlist.json`)

### Step 5: Canonical-vocab compatibility check (NEW)

If your edit affects an entry's `category_enum`, `functional_roles[]`, or any field that feeds the canonical contract:

```bash
# Test category_enum canonicalizes
python3 -c "
from scripts.ingredient_category_normalizer import canonicalize_ingredient_category
result = canonicalize_ingredient_category('<your_proposed_value>')
print(f'Canonicalizes to: {result}')  # None means it would break the contract
"

# Test functional_roles are vocab IDs
python3 -c "
import json
vocab = json.load(open('scripts/data/functional_roles_vocab.json'))
canonical_ids = {r['id'] for r in vocab['functional_roles']}
your_roles = ['<role1>', '<role2>']
unknown = set(your_roles) - canonical_ids
print(f'Unknown roles (LOCKED vocab — DO NOT ADD): {unknown}' if unknown else 'All roles canonical')
"
```

If your value does not canonicalize OR your role is not in the LOCKED vocab → **do not approve**. Flag as needs_verification or as a vocab-gap escalation.

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
   - Check top-level: `primary_type`, `form_factor_canonical`, `supplement_taxonomy.*`
   - Check per-row: `category`, `mapped`, `functional_roles[]` (inactives only)
5. **Unmapped / needs-verification / fallback reports**: `scripts/products/output_<Brand>/unmapped/` and `scripts/products/output_<Brand>_enriched/reports/`

Key fields to compare:

- `name` / `raw_source_text` / `ingredientGroup`
- `forms` / `nestedIngredients`
- Active vs inactive placement
- fallback-selected form vs expected correct form
- Whether the parent label is structural and child forms are the real ingredients
- `physicalState.langualCode` (raw) vs `form_factor_canonical` (enriched) — SP-3 mapping must agree

If raw shows a blend/container/header and cleaned surfaces it as unmapped ingredient text → code issue first.
Prefer the exact current run folder first, because that is the operator's working set. Use canonical `forms/` as the long-term reference copy.

---

## Key Pipeline Scripts Reference

| Script                             | Purpose                                       | When to use during resolution    |
| ---------------------------------- | --------------------------------------------- | -------------------------------- |
| `run_pipeline.py`                  | Orchestrates Clean → Enrich → Score           | Shadow-run verification          |
| `clean_dsld_data.py`               | Stage 1: normalize raw DSLD JSON              | Investigate cleaning bugs        |
| `enrich_supplements_v3.py`         | Stage 2: match, classify, enrich              | Investigate enrichment bugs      |
| `score_supplements.py`             | Stage 3: arithmetic scoring                   | Investigate scoring bugs         |
| `enhanced_normalizer.py`           | Core text normalization engine                | Investigate normalization bugs   |
| `supplement_taxonomy.py`           | SP-1 classifier → primary_type                | Investigate taxonomy mis-routes  |
| `form_factor_normalizer.py`        | SP-3 → form_factor_canonical                  | Investigate form_factor drift    |
| `ingredient_category_normalizer.py`| SP-4 → canonical ingredient category          | Verify category_enum values      |
| `supplement_type_utils.py`         | Thin wrapper around SP-4 normalizer           | Read-time canonicalization       |
| `scoring_v4/router.py`             | Taxonomy-first v4 module routing              | Investigate v4 routing bugs      |
| `constants.py`                     | Shared constants and mappings                 | Check canonical aliases/mappings |
| `fuzzy_matcher.py`                 | Fuzzy string matching                         | Investigate match failures       |
| `unii_cache.py`                    | Local-first UNII lookup (~172K offline)       | Fast UNII resolution without API |
| `unmapped_ingredient_tracker.py`   | Track unmapped ingredient state               | Audit unmapped backlogs          |
| `functional_grouping_handler.py`   | Functional grouping logic                     | Investigate grouping bugs        |
| `proprietary_blend_detector.py`    | Blend detection                               | Investigate blend routing        |
| `rda_ul_calculator.py`             | RDA/UL dose calculations                      | Investigate dose scoring         |
| `dosage_normalizer.py`             | Dose normalization                            | Investigate dose parsing         |
| `match_ledger.py`                  | Match tracking/auditing                       | Trace match decisions            |
| `shadow_score_comparison.py`       | Before/after scoring diff                     | Verify shadow-run deltas         |
| `regression_snapshot.py`           | Regression baseline snapshots                 | Guard against regressions        |
| `db_integrity_sanity_check.py`     | Schema and data validation                    | Mandatory after every edit       |
| `coverage_gate.py`                 | Quality/coverage threshold enforcement        | Quality gate checking            |
| `enrichment_contract_validator.py` | Enrichment output validation                  | Verify enrichment contracts      |
| `build_final_db.py`                | Final export for Flutter app                  | Build release SQLite DB          |
| `build_interaction_db.py`          | Build drug-supplement interaction DB          | Interaction data releases        |
| `preflight.py`                     | Pre-pipeline validation checks                | Catch data issues before run     |
| `backfill_upc.py`                  | UPC backfilling for products                  | UPC normalization tasks          |
| `extract_product_images.py`        | Product image URL extraction                  | Image asset pipeline             |

---

## Best-Practice Answer Format

When answering from this prompt, structure the response like this:

1. **Current batch summary**
   - Which raw source folder was inspected
   - Which pipeline output folders were inspected
   - Counts for unmapped, needs-verification, and fallback surfaces
   - UNII cache status (populated or needs rebuild)
   - Canonical vocab status (SP-1..SP-6 schemas + IDs counts)
   - Top primary_type and form_factor_canonical distribution (sanity check for taxonomy drift)
2. **High-confidence fixes (Lane A)**
   - exact aliases, misspellings, form aliases, or obvious DB-entry gaps
   - each with raw evidence, DB target, identifier evidence (UNII offline verified where possible), and canonical-vocab compatibility check
3. **Needs verification (Lane B)**
   - ambiguous identity, mixed API evidence, cross-DB collision risk, or canonical-vocab gap pending clinician review
4. **Likely code bugs (Lane C)**
   - parser/header/precedence/normalization/routing issues (including `prefix='from'`, cerevisiae alias gaps, taxonomy mis-routes, alias misplacements)
5. **Recommended next actions**
   - approved JSON edits
   - required tests
   - shadow-run target

Always separate:

- safe alias/data fixes
- true new canonical entries
- likely code bugs
- alias misplacements (§8.5)
- unresolved items that should stay in `needs_verification`

For each fallback item, report:

- raw form text
- fallback-selected form
- expected correct form
- whether this is alias-only or code-bug risk
- product's `supplement_taxonomy.primary_type` — sanity-check vs ingredient class

---

## Evidence Standards

### Identity evidence

Use at least one of:

- NIH ODS fact sheet, NCCIH monograph, FDA/USDA/regulator source
- PubChem / FDA UNII (offline cache sufficient for known substances) / NCBI reference
- API verification (CUI, UNII, CAS cross-match)

### Clinical notes

- Include mechanism, form relevance, bioavailability
- Include PMID/DOI if available
- No vague filler text or invented effect sizes

### Safety evidence

- FDA / NIH / NCCIH first
- PubMed / DOI-backed second
- Branded site never as sole safety evidence

### Evidence vocab discipline (SP-6)

When citing evidence on any data file entry:

- `evidence_level[]` MUST be IDs from `evidence_level_vocab.json` (5 IDs, LOCKED)
- `evidence_strength` MUST be one of `evidence_strength_vocab.json` (6 IDs, LOCKED)
- `study_type` MUST be one of `study_type_vocab.json` (7 IDs, LOCKED)
- These are clinician-signed and pre-date SP-6. Adding new values requires a fresh clinician review cycle.

---

## API Verification Tools

| Script                             | API                             | What it checks                                            | Key flags                           |
| ---------------------------------- | ------------------------------- | --------------------------------------------------------- | ----------------------------------- |
| `verify_cui.py`                    | UMLS                            | CUI validity, concept name                                | `--cui C0000000`, `--search "name"` |
| `verify_unii.py`                   | FDA GSRS + offline cache        | UNII, CFR, DSLD, metabolic relationships (cache-first)    | `--search "name"`                   |
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

| Script                                          | Purpose                                                                |
| ----------------------------------------------- | ---------------------------------------------------------------------- |
| `api_audit/build_unii_cache.py`                 | Build/refresh local UNII cache from FDA bulk (run before UNII lookups) |
| `api_audit/enrich_botanicals.py`                | Botanical enrichment with standardization markers                      |
| `api_audit/enrich_chembl_bioactivity.py`        | ChEMBL mechanism of action enrichment                                  |
| `api_audit/audit_alias_accuracy.py`             | Alias accuracy audit (helps surface §8.5 misplacements)                |
| `api_audit/audit_banned_recalled_accuracy.py`   | Release gate for banned/recalled data                                  |
| `api_audit/audit_clinical_evidence_strength.py` | Evidence strength classification                                       |
| `api_audit/audit_clinical_sources.py`           | Clinical source validation                                             |
| `api_audit/audit_notes_alignment.py`            | Notes alignment check                                                  |
| `api_audit/discover_clinical_evidence.py`       | Clinical evidence discovery                                            |
| `api_audit/normalize_clinical_pubmed.py`        | PubMed citation normalization                                          |
| `api_audit/pubmed_client.py`                    | PubMed API client (used by citation verify tools)                      |
| `api_audit/ingest_caers.py`                     | Ingest FDA CAERS adverse event data                                    |
| `api_audit/mine_drug_label_interactions.py`     | Mine FDA drug labels for interactions                                  |
| `api_audit/seed_drug_classes.py`                | Seed drug class definitions                                            |
| `api_audit/fda_weekly_sync.py`                  | FDA recall tracking (openFDA, RSS, DEA)                                |
| `api_audit/fda_manufacturer_violations_sync.py` | Manufacturer violation sync                                            |
| `api_audit/valyu_evidence_discovery.py`         | Valyu-powered evidence discovery for ingredients                       |
| `api_audit/valyu_domain_targets.py`             | Valyu domain target extraction                                         |
| `api_audit/valyu_query_planner.py`              | Valyu query planning for evidence search                               |
| `api_audit/valyu_report_writer.py`              | Valyu evidence report generation                                       |

Curated override files (prevent known bad auto-matches):

- `scripts/data/curated_overrides/cui_overrides.json` (CUI override entries)
- `scripts/data/curated_overrides/gsrs_policies.json` (GSRS skip names)
- `scripts/data/curated_overrides/pubchem_policies.json` (PubChem skip names)

**NEVER use `--apply` in bulk.** Dry-run only, verify each result individually.

---

## Output Format

### Phase 1 Outputs (stop after these)

#### TABLE 1: Findings

| #   | Label text | Occ | Surface | Bucket | Raw verified? | Proposed action | Target DB | Identifier match? | Confidence |
| --- | ---------- | --- | ------- | ------ | ------------- | --------------- | --------- | ----------------- | ---------- |

#### TABLE 2: Alias Additions (identifier-verified)

| #   | Alias text | Target file | Target entry ID | CUI match? | UNII match? | CAS match? | §8.5 entry clean? | Evidence |
| --- | ---------- | ----------- | --------------- | ---------- | ----------- | ---------- | ----------------- | -------- |

#### TABLE 3: New Entries

| #   | Standard name | Target file | CUI | UNII | CAS | CID | Category (canonicalizes?) | Functional roles (LOCKED?) | Evidence |
| --- | ------------- | ----------- | --- | ---- | --- | --- | ------------------------- | -------------------------- | -------- |

#### TABLE 4: Code / Data Bugs (incl. alias misplacements)

| #   | File / Entry | Function / Field | Root cause | Why alias won't fix it | Proposed fix | Downstream impact (shadow needed?) |
| --- | ------------ | ---------------- | ---------- | ---------------------- | ------------ | ---------------------------------- |

#### TABLE 5: Deferred / Needs Verification

| #   | Label text | Missing evidence | Next verification step |
| --- | ---------- | ---------------- | ---------------------- |

#### TABLE 6: Misspelling / Typo Aliases

| #   | Raw label (misspelled) | Correct form | Target entry | Verified same CUI/UNII? |
| --- | ---------------------- | ------------ | ------------ | ----------------------- |

#### TABLE 7: Fallback Form Validation (with taxonomy sanity-check)

| #   | Ingredient | Raw form text | Fallback-selected form | Expected correct form | Product primary_type | Taxonomy correct? | Alias-only or bug? | Confidence |
| --- | ---------- | ------------- | ---------------------- | --------------------- | -------------------- | ----------------- | ------------------ | ---------- |

#### BATCH SUMMARY

```
Batch N — Items [X] to [Y]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total analyzed:           XX
Alias additions:          XX (all identifier-verified + §8.5 clean)
New entries:              XX
Code bugs found:          XX
Alias misplacements:      XX (relocation pending)
Misspellings:             XX
Deferred:                 XX
Cross-DB collisions:      XX (prevented)
UNII cache hits:          XX (no API call needed)
Vocab-compat failures:    XX (deferred — needs clinician)
Taxonomy mis-routes:      XX (Lane C — code fix required)
```

### Phase 2 Outputs (after approval)

1. Files changed (exact list)
2. Tests run (integrity + targeted + vocab parity)
3. Shadow-run verification (before/after unmapped deltas via `shadow_score_comparison.py`)
4. Canonical-field stability check: `primary_type`, `form_factor_canonical`, `category_canonical` unchanged on unrelated products
5. Residual risk (anything still deferred)

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
Also: a "successful" enrichment with the wrong `primary_type` is worse than an unmapped — it silently mis-routes through v4 modules.

### Display ledger rule

Rows that are label-visible but should not score: keep in display ledger, mark non-scoring, preserve real mapped/scorable children separately.

### UNII cache hygiene

The `fda_unii_cache.json` contains ~172K substances but must be rebuilt periodically to stay current.
Run `python3 scripts/api_audit/build_unii_cache.py` before any large batch session if the cache is stale or has fewer than 10K entries.
The `unii_cache.py` module logs a warning when a lookup misses the cache and falls back to the GSRS API.

### Cerevisiae yeast routing rule

When a label contains "from S. cerevisiae" or "from Saccharomyces cerevisiae" source language, the enricher uses `_CEREVISIAE_YEAST_ALIAS` to route to a yeast-specific IQM form. If the route fails and the ingredient falls to `(unspecified)`, first check whether the alias exists in `_CEREVISIAE_YEAST_ALIAS` before assuming an IQM form gap.

### `prefix='from'` enricher rule

Forms whose text begins with "from" are treated as source-descriptors and skipped by the enricher. If a chelate-class form name begins with "from", it will not match even if an alias exists. Code-level narrow fix required, not a data-level alias addition.

### Omega word-boundary rule

`_is_omega_like` must use `\b(epa|dha)\b` regex — substring matching "dha" inside "ashwagandha" or "ECHINACEA" causes false-positive omega routing. If you find an ashwagandha or other non-omega product being routed to the omega module, this is the bug.

### Marine ≠ omega

"Marine collagen" is NOT omega-3. Do not add "marine" to omega multi-char term lists.

### Taxonomy-first v4 routing rule

The v4 router reads `supplement_taxonomy.primary_type` FIRST, then maps to omega / multi_or_prenatal / probiotic / generic. If you propose a data fix that would shift a product's `primary_type`, check whether downstream v4 routing should follow — and run shadow scoring to confirm.

### LOCKED vocab discipline

`functional_roles_vocab.json`, `evidence_level_vocab.json`, `evidence_strength_vocab.json`, `study_type_vocab.json`, and `iqm_category_vocab.json` are LOCKED. Adding/removing IDs requires clinician sign-off. If your fix needs a new role/level/category, defer to clinician review — do NOT sneak one in via a data file alias.

---

## Critical Rules

1. **No batch fixes.** 8-12 items per batch. Verify each individually. Test-pin before editing data.
2. **API-verify all identifiers** before adding aliases or new entries. UNII via offline cache first (~172K fast), then GSRS API. CUI via UMLS. CAS via PubChem.
3. **No alias should match a different compound** — verify via CUI/UNII/CAS. If identifiers disagree, decouple. If you spot an EXISTING alias that doesn't match — §8.5 misplacement workflow.
4. **No duplicate entries across files.** Search all 7+ routing databases before adding anything.
5. **No hallucinated references.** If you can't find a real source, write "needs verification."
6. **Fix code bugs with code, not data.** Do not paper over parser/normalizer/precedence/taxonomy bugs with aliases.
7. **Raw DSLD verification is mandatory** for any suspicious or ambiguous case.
8. **Cross-check CAS numbers** — wrong CAS = wrong substance = patient safety risk.
9. **When in doubt → defer, don't guess.** A larger unmapped list with clean logic is better than a smaller list with bad aliases.
10. **The goal is correct identity resolution, not fewer unmapped names.**
11. **Rebuild the UNII cache** (`build_unii_cache.py`) before any large batch if cache entries < 10K or cache is older than 30 days.
12. **Canonical-vocab compatibility is mandatory.** Any new IQM `category_enum` must canonicalize via SP-4 normalizer. Any inactive `functional_roles[]` must be in the SP-5 LOCKED vocab. Any evidence field must use SP-6 LOCKED vocabs.
13. **Taxonomy sanity-check is mandatory** for fallback validation. A "form alias gap" that's actually a taxonomy mis-route is a Lane C code bug, not a Surface C data gap.
14. **Misplaced aliases are bugs** — §8.5 workflow applies. They go through the same Phase 1 → approval → Phase 2 cycle as any other change.
15. **No parallel classifiers.** SP-0 contract: enrich computes vocab IDs once, downstream consumes. Never invent a second classification path.
