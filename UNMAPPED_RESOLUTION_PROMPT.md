# PharmaGuide Unmapped Ingredient Resolution

## Role

Act as the **PharmaGuide Lead Systems Architect**.
Your mission is to resolve unmapped ingredients from DSLD supplement datasets with maximum accuracy, while protecting scoring integrity and schema integrity across the pipeline.
You are running as a CLI coding agent with filesystem access in this repo.

---

## Context: Two-Stage Unmapped Problem + Form Fallbacks

This pipeline has **two independent stages** that each produce unmapped ingredients, plus a **form fallback** category where ingredients matched a parent but fell back to a generic `(unspecified)` form. You MUST scan and resolve ALL THREE.

### Stage 1: CLEANING (`enhanced_normalizer.py`)

The cleaner maps ingredient names against **all reference databases** (IQM + botanical + other + harmful + allergen + banned + excipient lists). An ingredient is `mapped: false` in cleaned output if it's not found in **any** of these databases.

**Unmapped reports live at:**

```
scripts/output_*/unmapped/unmapped_active_ingredients.json    ← active ingredient gaps
scripts/output_*/unmapped/unmapped_inactive_ingredients.json  ← inactive ingredient gaps
```

These are `{name: count}` dicts under the `unmapped_ingredients` key.

### Stage 2: ENRICHMENT (`enrich_supplements_v3.py`)

The enricher tries to match each active ingredient specifically to the **IQM** (ingredient_quality_map.json) for bioavailability scoring. If IQM match fails, it falls back to `_is_recognized_non_scorable()` which checks botanical_ingredients, banned_recalled, other_ingredients, etc.

An ingredient shows `mapped: false` in enriched output when BOTH the IQM match AND the tier-2 recognition check fail.

**Unmapped data lives inside enriched product files:**

```
scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json
→ each product → ingredient_quality_data → ingredients_scorable[] → mapped: false
```

### Stage 3: FORM FALLBACK (enrichment `parent_fallback_report.json`)

The enricher matched the ingredient to an IQM parent, but could NOT match a specific form alias. It fell back to the generic `(unspecified)` form, which uses a conservative stub score (typically bio_score=5). These are **scoring accuracy gaps** — the ingredient IS recognized but potentially under-scored.

**Fallback reports live at:**

```
scripts/output_*_enriched/reports/parent_fallback_report.json
```

Each entry has: `ingredient_raw`, `ingredient_normalized`, `canonical_id`, `fallback_form_name`, `match_type`, `tier`, `occurrence_count`.

**Why fallbacks matter**: A branded curcumin phytosome (Meriva) falling back to `curcumin (unspecified)` scores 8 instead of 15 — a 7-point penalty for what should be a premium form. These are pure IQM alias additions: add the label text as an alias to the correct existing form.

**Fallback resolution is always an alias addition to an existing IQM form** — never a new parent, never a new form (unless the ingredient truly represents a form not yet in the IQM). Check the IQM parent's existing forms and match to the best fit.

### Why the Two Stages Disagree

| Scenario                                                                                     | Cleaning      | Enrichment    | Root Cause                                                                     |
| -------------------------------------------------------------------------------------------- | ------------- | ------------- | ------------------------------------------------------------------------------ |
| Ingredient in botanical_ingredients but enricher's `_is_recognized_non_scorable()` misses it | mapped: true  | mapped: false | **Code bug** — enricher recognition doesn't match what cleaning found          |
| Ingredient in IQM but cleaning normalizer has different lookup logic                         | mapped: true  | mapped: true  | No issue (both agree)                                                          |
| Ingredient in NO database                                                                    | mapped: false | mapped: false | **True data gap** — needs DB addition                                          |
| Ingredient in cleaning's lookups but not in any enricher lookup                              | mapped: true  | mapped: false | **Enricher coverage gap** — enricher checks fewer DBs or has stricter matching |
| Cleaning unmapped active ingredient never reaches enricher scorable                          | mapped: false | not present   | **Cleaning-only gap** — never gets a chance at enrichment                      |

### Measured Baseline Numbers

**Before starting work, always run the dynamic scan script (Step 0 below) to get current numbers.** The numbers below are reference from March 2026 and will change as you resolve items:

- Cleaning active unmapped: ~4,276 unique names, ~6,586 occurrences
- Cleaning inactive unmapped: ~769 unique names, ~1,688 occurrences
- Enrichment unmapped: ~2,041 unique names, ~4,357 occurrences
- In BOTH stages: ~1,100 names (true gaps in all DBs)
- Cleaning-only (enricher resolved): ~3,176 names
- Enrichment-only (cleaning said mapped but enricher disagrees): ~941 names ← **code/alias bug category**

---

## Operating Mode (Mandatory)

Work in **2 phases**:

### Phase 1: ANALYZE + PLAN (no writes)

- Run the dynamic scan (Step 0)
- Inspect data + code + schemas
- Build a canonical lookup index across ALL routing target files
- Detect systemic mismatch patterns (root cause analysis)
- Produce root-cause analysis and proposed changes
- **Wait for user approval before any writes**

### Phase 2: APPLY (only after approval)

- Apply approved changes
- Run `python -m pytest scripts/tests/` — all tests must pass
- Re-run the dynamic scan and compare before/after
- Report exact impact

**Do NOT write files in Phase 1.**

---

## Step 0: Dynamic Scan (Run Every Session)

Always start by running this to get **current** numbers. This replaces hardcoded stats and makes the prompt reusable as you chip away at the unmapped list.

```bash
python3 << 'SCAN_EOF'
import json, glob

print("=" * 70)
print("UNMAPPED INGREDIENT SCAN — CURRENT STATE")
print("=" * 70)

# ─── CLEANING STAGE ───
active_files = sorted(glob.glob('scripts/output_*/unmapped/unmapped_active_ingredients.json'))
inactive_files = sorted(glob.glob('scripts/output_*/unmapped/unmapped_inactive_ingredients.json'))

cleaning_active = {}
cleaning_inactive = {}
for fp in active_files:
    with open(fp) as f:
        data = json.load(f)
    for name, count in data.get('unmapped_ingredients', {}).items():
        cleaning_active[name] = cleaning_active.get(name, 0) + count
for fp in inactive_files:
    with open(fp) as f:
        data = json.load(f)
    for name, count in data.get('unmapped_ingredients', {}).items():
        cleaning_inactive[name] = cleaning_inactive.get(name, 0) + count

print(f"\n[CLEANING STAGE]")
print(f"  Active unmapped:   {len(cleaning_active):,} unique, {sum(cleaning_active.values()):,} occurrences")
print(f"  Inactive unmapped: {len(cleaning_inactive):,} unique, {sum(cleaning_inactive.values()):,} occurrences")

# ─── ENRICHMENT STAGE ───
enriched_files = sorted(glob.glob('scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json'))
enrichment_unmapped = {}
total_products = 0
total_scorable = 0
for fp in enriched_files:
    with open(fp) as f:
        data = json.load(f)
    for p in data:
        total_products += 1
        iqd = p.get('ingredient_quality_data', {})
        for ing in iqd.get('ingredients_scorable', []):
            total_scorable += 1
            if not ing.get('mapped', True):
                name = ing.get('name', 'UNKNOWN')
                enrichment_unmapped[name] = enrichment_unmapped.get(name, 0) + 1

pct = (sum(enrichment_unmapped.values()) / total_scorable * 100) if total_scorable else 0
print(f"\n[ENRICHMENT STAGE]")
print(f"  Products: {total_products:,}")
print(f"  Scorable ingredients: {total_scorable:,}")
print(f"  Unmapped: {len(enrichment_unmapped):,} unique, {sum(enrichment_unmapped.values()):,} occurrences ({pct:.1f}%)")

# ─── OVERLAP ANALYSIS ───
c_set = set(cleaning_active.keys())
e_set = set(enrichment_unmapped.keys())
both = c_set & e_set
only_c = c_set - e_set
only_e = e_set - c_set

print(f"\n[OVERLAP]")
print(f"  In BOTH stages: {len(both):,}  (true gaps — not in any DB)")
print(f"  Cleaning-only:  {len(only_c):,}  (enricher resolved or ingredient dropped)")
print(f"  Enrichment-only:{len(only_e):,}  (cleaning mapped but enricher disagrees — BUG CATEGORY)")

# ─── TIERS ───
tier1 = {k:v for k,v in enrichment_unmapped.items() if v >= 10}
tier2 = {k:v for k,v in enrichment_unmapped.items() if 3 <= v < 10}
tier3 = {k:v for k,v in enrichment_unmapped.items() if v < 3}
print(f"\n[ENRICHMENT TIERS]")
print(f"  Tier 1 (>=10 occ): {len(tier1):,} names, {sum(tier1.values()):,} occurrences")
print(f"  Tier 2 (3-9 occ):  {len(tier2):,} names, {sum(tier2.values()):,} occurrences")
print(f"  Tier 3 (1-2 occ):  {len(tier3):,} names, {sum(tier3.values()):,} occurrences")

print(f"\n[TOP 50 ENRICHMENT UNMAPPED]")
for name, count in sorted(enrichment_unmapped.items(), key=lambda x: -x[1])[:50]:
    tag = " *** CLEANING MAPPED (bug)" if name not in c_set else ""
    print(f"  {count:4d}x  {name}{tag}")

print(f"\n[TOP 30 CLEANING-ONLY ACTIVE UNMAPPED]")
for name in sorted(only_c, key=lambda x: -cleaning_active.get(x, 0))[:30]:
    print(f"  {cleaning_active[name]:4d}x  {name}")

print(f"\n[TOP 20 CLEANING INACTIVE UNMAPPED]")
for name, count in sorted(cleaning_inactive.items(), key=lambda x: -x[1])[:20]:
    print(f"  {count:4d}x  {name}")

# ─── FORM FALLBACK STAGE ───
fallback_reports = sorted(glob.glob('scripts/output_*_enriched/reports/parent_fallback_report.json'))
all_fallbacks = {}  # normalized_name -> {canonical_id, fallback_form, total_count, raw_examples}
total_fallback_occ = 0
for fp in fallback_reports:
    with open(fp) as f:
        data = json.load(f)
    for fb in data.get('fallbacks', []):
        key = fb.get('ingredient_normalized', '')
        cid = fb.get('canonical_id', '')
        count = fb.get('occurrence_count', 0)
        total_fallback_occ += count
        if key not in all_fallbacks:
            all_fallbacks[key] = {
                'canonical_id': cid,
                'fallback_form': fb.get('fallback_form_name', ''),
                'total_count': 0,
                'raw_examples': set(),
                'match_type': fb.get('match_type', ''),
            }
        all_fallbacks[key]['total_count'] += count
        all_fallbacks[key]['raw_examples'].add(fb.get('ingredient_raw', ''))

print(f"\n[FORM FALLBACK STAGE]")
print(f"  Reports scanned: {len(fallback_reports)}")
print(f"  Unique fallback ingredients: {len(all_fallbacks):,}")
print(f"  Total fallback occurrences: {total_fallback_occ:,}")

# Load IQM to compute score delta
iqm_path = 'scripts/data/ingredient_quality_map.json'
try:
    with open(iqm_path) as f:
        iqm = json.load(f)
except:
    iqm = {}

print(f"\n[FORM FALLBACK DETAILS — sorted by impact]")
for name, info in sorted(all_fallbacks.items(), key=lambda x: -x[1]['total_count']):
    cid = info['canonical_id']
    fb_form = info['fallback_form']
    count = info['total_count']
    parent = iqm.get(cid, {})
    forms = parent.get('forms', {})
    fb_data = forms.get(fb_form, {})
    fb_score = fb_data.get('score', '?')
    best_score = max((fd.get('score', 0) for fd in forms.values() if isinstance(fd, dict)), default=0)
    delta = f"delta={best_score - fb_score}" if isinstance(fb_score, (int, float)) else "?"
    num_forms = len([k for k, v in forms.items() if isinstance(v, dict)])
    print(f"  {count:4d}x  \"{name}\" → {cid}/{fb_form} (score={fb_score}, best={best_score}, {delta}, {num_forms} forms)")

print(f"\n{'=' * 70}")
print("SCAN COMPLETE — Use these numbers for Phase 1 analysis")
print(f"{'=' * 70}")
SCAN_EOF
```

---

## Repo Scope

| Component                  | Path                                                               |
| -------------------------- | ------------------------------------------------------------------ |
| Cleaner / Normalizer       | `scripts/enhanced_normalizer.py`                                   |
| Enrichment engine          | `scripts/enrich_supplements_v3.py`                                 |
| Scorer                     | `scripts/score_supplements.py`                                     |
| IQM (scorable actives)     | `scripts/data/ingredient_quality_map.json`                         |
| Botanical ingredients      | `scripts/data/botanical_ingredients.json`                          |
| Other ingredients          | `scripts/data/other_ingredients.json`                              |
| Harmful additives          | `scripts/data/harmful_additives.json`                              |
| Banned/recalled            | `scripts/data/banned_recalled_ingredients.json`                    |
| Standardized botanicals    | `scripts/data/standardized_botanicals.json`                        |
| Allergens                  | `scripts/data/allergens.json`                                      |
| Proprietary blends (mapping-only; scoring handled by B5 engine) | `scripts/data/proprietary_blends.json`                             |
| Cross-DB allowlist         | `scripts/data/cross_db_overlap_allowlist.json`                     |
| Integrity checker          | `scripts/db_integrity_sanity_check.py`                             |
| Tests                      | `scripts/tests/`                                                   |
| Cleaning unmapped reports  | `scripts/output_*/unmapped/unmapped_*.json`                        |
| Enrichment summary reports | `scripts/output_*_enriched/reports/enrichment_summary_*.json`      |
| Form fallback reports      | `scripts/output_*_enriched/reports/parent_fallback_report.json`    |
| Enriched output            | `scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json` |

---

## Core Policy (Do Not Violate)

### 1. Alias-First Policy

Before proposing a **new** entry in ANY database, exhaustively check if the term already exists as:

- A canonical parent name or alias in IQM
- A form name or form alias under any IQM parent
- A standard_name or alias in botanical_ingredients, other_ingredients, harmful_additives, banned_recalled, allergens
- A variant differing only by: case, hyphens, spaces, "organic" prefix, "extract"/"powder"/"root"/"leaf" suffix, parenthetical content, comma reordering

If the same molecule/entity exists → propose **alias addition**, NOT a new entry.

### 2. No Guessing

If uncertain about classification (active vs excipient, scorable vs non-scorable, safe vs harmful), put it in `review_required` with evidence and reasoning.

### 3. Penalty Routing Guardrails

- Any ingredient that deserves a scoring **penalty** → route to `harmful_additives.json` or `banned_recalled_ingredients.json`
- `other_ingredients.json` and `botanical_ingredients.json` are **strict 0-penalty** files
- Never inflate penalties by misrouting neutral ingredients to penalty files
- Never deflate penalties by routing harmful ingredients to 0-penalty files

### 4. Banned/Recalled Strictness

High-risk/banned/recalled classification requires real source verification:

- FDA warning letters, import alerts, or mandatory recalls
- NIH/ODS/NCCIH safety advisories
- Published case reports (PubMed) documenting harm
- Do NOT rely on "general concern" or "traditional caution" without sources

### 5. Standardization Guardrail

- Do **not** strip standardization markers (e.g., "95% curcuminoids", "50:1 extract") if relevant to `standardized_botanicals.json`
- Preserve data needed for A5b threshold logic in the scorer

### 6. IQM Schema Compliance

New IQM entries MUST include ALL required fields per the established schema:

```json
{
  "parent_key": {
    "standard_name": "...",
    "category": "...",
    "cui": "..." or null,
    "rxcui": "..." or null,
    "cui_note": "reason if null",
    "rxcui_note": "reason if null",
    "aliases": [],
    "forms": {
      "(unspecified)": {
        "bio_score": 5,
        "natural": false,
        "score": 5,
        "absorption": "...",
        "notes": "80+ char clinically informative note with RCT/mechanism/manufacturer references",
        "aliases": [],
        "dosage_importance": 1.0,
        "absorption_structured": {
          "value": 0.5,
          "range_low": 0.3,
          "range_high": 0.7,
          "quality": "moderate",
          "notes": "..."
        }
      }
    },
    "match_rules": {
      "priority": "standard",
      "match_mode": "exact_or_alias",
      "exclusions": [],
      "parent_id": "parent_key",
      "confidence": 1.0
    }
  }
}
```

**Score formula**: `score = bio_score + (3 if natural else 0)` — checked by `db_integrity_sanity_check.py`.
**dosage_importance**: Primary=1.5, Secondary=1.0, Trace=0.5.
**Notes**: Every non-(unspecified) form needs ≥80 char clinically informative note.

### 7. Botanical/Other Ingredients Schema Compliance

New entries in `botanical_ingredients.json` need: id, standard_name, latin_name, aliases, category, notes, CUI.
New entries in `other_ingredients.json` need: id, standard_name, aliases, category, is_additive, allergen, notes, CUI.

### 8. Test Suite Integrity

After ANY data file changes, run:

```bash
python -m pytest scripts/tests/ -x -q
```

If new cross-parent aliases are introduced, add them to `ALLOWED_CROSS_ALIASES` in `scripts/tests/test_ingredient_quality_map_schema.py`.

---

## Routing Rules — Active vs Inactive Source Section

### CARDINAL RULE: Source section determines routing destination

The unmapped reports already separate ingredients by **source section** — where they appeared on the FDA label:

| Source Section | Report File | Primary Routing Destination | Rationale |
|---|---|---|---|
| **Active** (`activeIngredients` / Supplement Facts panel) | `unmapped_active_ingredients.json` | **IQM** (therapeutically scored) | Active ingredients are listed by the manufacturer as providing the supplement's intended health benefits. They belong in the IQM for bioavailability scoring. |
| **Inactive** (`inactiveIngredients` / "Other Ingredients" on label) | `unmapped_inactive_ingredients.json` | **other_ingredients.json**, **botanical_ingredients.json**, **harmful_additives.json**, or **proprietary_blends.json** | Inactive ingredients are excipients, preservatives, binders, coatings, or flavoring agents. They are NOT bioactive therapeutics and should NOT go into the IQM. |

**Why this matters**: Per FDA 21 CFR 101.36, dietary ingredients (actives) go inside the Supplement Facts panel with dosages. Non-dietary ingredients (excipients, preservatives, fillers) go in the "Other Ingredients" statement outside the panel — no doses required. This FDA-mandated separation IS the source of truth for routing:

- **Active unmapped → IQM** (alias to existing parent, or new parent if clinical evidence supports it)
- **Inactive unmapped → other files** (other_ingredients, botanical, harmful, blends — never IQM)

**Exception — misclassified actives in inactive section**: Some manufacturers incorrectly list therapeutic ingredients (e.g., "Betaine Monohydrate") in the inactive section. The enricher's Pass 2 ("rescue therapeutic actives from inactiveIngredients") handles promotion. If you find a clearly therapeutic ingredient in the inactive unmapped report, note the misclassification but still route it to the appropriate DB (IQM if therapeutic). These cases are rare (<2% of inactive unmapped).

**Exception — excipient leaks in active section**: Some manufacturers list capsule materials or fillers (e.g., "Rice Flour", "Vegetable Capsule") in the Supplement Facts panel. These are excipient leaks — the enricher already has `_should_skip_from_scoring()` logic to detect these. If an active unmapped ingredient is clearly an excipient, route it to other_ingredients.json AND note the excipient detection bug for code fix.

---

## Active Ingredient Routing Decision Tree — IQM vs Botanical vs Other

**Critical distinction**: Just because DSLD lists something as an "active ingredient" does NOT mean it belongs in the IQM. Manufacturers can (and do) list food powders, fillers, and non-therapeutic ingredients in the "Supplement Facts" panel. The routing decision is based on **what the ingredient actually is**, not where the manufacturer placed it on the label. However, the **default assumption** for active unmapped ingredients is IQM routing — you need specific evidence to override this.

### Decision flowchart for ACTIVE unmapped ingredients:

```
UNMAPPED ACTIVE INGREDIENT
│
├─ Is it a recognized harmful/banned substance?
│   YES → harmful_additives.json or banned_recalled_ingredients.json
│   (requires source citation: FDA/NIH/PubMed)
│
├─ Is it an excipient/capsule material that leaked into actives?
│   (e.g., "100% Vegetable Capsule", "Rice Flour", "Magnesium Stearate")
│   YES → Code fix (excipient detection bug) + other_ingredients.json if missing
│
├─ Is it a salt/chelate/branded form of an EXISTING IQM parent?
│   (e.g., "L-Lysine Hydrochloride" → l_lysine, "Meriva" → curcumin)
│   YES → Add ALIAS to existing IQM parent/form
│
├─ Does it have ALL of these characteristics?
│   ✓ Defined therapeutic mechanism (not just "nutritious")
│   ✓ Evidence of dose-response relationship (RCTs, clinical studies)
│   ✓ Specific bioavailability data available (absorption %, forms matter)
│   ✓ Standardized dosing exists (mg/mcg per serving, not "proprietary amount")
│   ✓ Used specifically for supplementation, not just as a food
│   ALL YES → IQM (new parent entry with full schema)
│
├─ Is it a plant/fungus/botanical with therapeutic tradition BUT lacking
│   strong bioavailability data or dose-response evidence?
│   (e.g., most whole herb powders, food-grade botanicals)
│   YES → botanical_ingredients.json (recognized, 0-penalty, NOT scored)
│
├─ Is it a non-botanical, non-therapeutic ingredient?
│   (e.g., tissue extracts, bee products, mineral clays)
│   YES → other_ingredients.json (recognized, 0-penalty, NOT scored)
│
└─ Uncertain? → review_required (defer with reasoning)
```

### Concrete examples by category:

**→ IQM** (therapeutically scored — has bioavailability evidence):
| Ingredient | Why IQM | Evidence |
|-----------|---------|----------|
| Marshmallow Root Extract (standardized) | Mucilage content with studied GI soothing effects | RCTs on gastric mucosa protection |
| Chitosan | Studied fat-binding mechanism, dose-dependent effects | Clinical trials for lipid management |
| D-Mannose | Specific urinary tract mechanism, dose-response data | RCTs vs placebo for UTI prevention |
| Betaine (TMG) | Methylation donor, homocysteine reduction evidence | Clinical pharmacokinetic data available |
| N-Acetyl-L-Cysteine | Well-characterized glutathione precursor | Extensive clinical data, specific bioavailability |

**→ botanical_ingredients** (recognized but NOT scored — food/herb identity only):
| Ingredient | Why NOT IQM | What it is |
|-----------|-------------|------------|
| Broccoli powder | Whole food, no standardized therapeutic dose | Vegetable powder in a capsule |
| Carrot powder | Nutritional food ingredient, not a therapeutic supplement | Vegetable powder |
| Kale powder | "Superfood" marketing, no specific bioavailability scoring | Vegetable powder |
| Spinach powder | Food-grade, not dosed therapeutically | Vegetable powder |
| Barley Grass powder | General "green food" ingredient | Grass juice powder |
| Celery seed | Culinary herb, not standardized for therapy | Whole seed/powder |
| Fennel (unstandardized) | Culinary herb, no specific extract standardization | Whole herb powder |
| Bee Pollen | No standardized therapeutic dosing or bioavailability data | Apiary product |
| Raw mushroom powder (generic) | Whole food form, no standardization or bio data | Ground dried mushroom |

**→ other_ingredients** (non-botanical, non-scored):
| Ingredient | What it is |
|-----------|------------|
| Adrenal Tissue | Bovine glandular extract, no standard scoring |
| Thymus Tissue | Bovine glandular extract |
| Spleen Tissue | Bovine glandular extract |
| Vegetable Capsule variants | Capsule shell (excipient leak) |
| Beef Gelatin | Capsule material |

### The mushroom question specifically:

Mushrooms exist in **both** databases by design:

| Mushroom    | IQM entry                     | botanical_ingredients entry                | When IQM is used                              | When botanical is used                                            |
| ----------- | ----------------------------- | ------------------------------------------ | --------------------------------------------- | ----------------------------------------------------------------- |
| Reishi      | `reishi` (3 scored forms)     | `reishi_mushroom` (recognition)            | "Reishi fruiting body extract 500mg" → scored | "organic reishi powder" with no standardization → recognized only |
| Lion's Mane | `lions_mane` (3 scored forms) | `lions_mane_mushroom_powder` (recognition) | "Lion's Mane 10:1 extract" → scored           | "lion's mane mushroom" generic listing → recognized only          |
| Cordyceps   | `cordyceps` (4 scored forms)  | `cordyceps_mushroom_powder` (recognition)  | "Cordyceps militaris extract 750mg" → scored  | "cordyceps powder" generic → recognized only                      |

**Rule**: If the label specifies a standardized extract form with dose → IQM handles it (scored). If it's just "mushroom powder" without standardization → botanical_ingredients catches it (recognized, not scored). The enricher tries IQM first; if no form match, it falls back to botanical recognition.

**For NEW mushroom entries**: Only create a new IQM parent if the mushroom has studied therapeutic compounds with bioavailability data (e.g., beta-glucan content, specific triterpenes). If it's an obscure mushroom with no clinical data, add to botanical_ingredients only.

### Decision tree for INACTIVE unmapped ingredients:

**Default destination: NOT IQM.** Inactive ingredients are excipients, preservatives, or additives — they are not bioactive therapeutics. Route them to other_ingredients.json, botanical_ingredients.json, harmful_additives.json, or proprietary_blends.json based on what they are.

```
UNMAPPED INACTIVE INGREDIENT
│
├─ Is it a harmful additive? (artificial colors, controversial preservatives)
│   YES → harmful_additives.json (with severity level + source)
│
├─ Is it a banned substance somehow listed as inactive?
│   YES → banned_recalled_ingredients.json (with FDA citation)
│
├─ Is it a proprietary blend name? (branded formula/complex)
│   (e.g., "Metabolic GlycoPlex", "Acid Comfort Blend")
│   YES → proprietary_blends.json (add to blend_terms)
│         The scorer applies penalty based on disclosure level (see SCORING_ENGINE_SPEC.md §B5 for current values)
│
├─ Is it a misclassified active? (therapeutic ingredient in inactive row)
│   (e.g., "Betaine Monohydrate" in inactive section — RARE, <2% of cases)
│   YES → Note the misclassification, but still add to appropriate DB
│         (IQM if therapeutic, botanical if herb, other if excipient)
│
├─ Is it a botanical/plant-derived excipient?
│   (e.g., "Rice Bran", "Arrowroot Flour", "Rosemary Antioxidant Blend")
│   YES → other_ingredients.json (it's an excipient, even if plant-derived)
│         Set is_additive: true, category: appropriate type
│         NOTE: "Rosemary Antioxidant Blend" in inactive = preservative,
│         NOT therapeutic rosemary. Same compound, different intent/dose.
│
├─ Is it a capsule/coating/flow agent variant?
│   (e.g., "Plantcap", "Serrateric", "Gelatin Capsules", "Carnauba Wax")
│   YES → other_ingredients.json
│
├─ Is it a recognized allergen?
│   YES → allergens.json
│
└─ Other non-botanical inactive → other_ingredients.json
```

**Key insight**: The same ingredient can appear in BOTH active and inactive sections across different products. Example: "Rosemary leaf extract" at 50mg in Supplement Facts = therapeutic (IQM alias). "Rosemary leaf Antioxidant Blend" in Other Ingredients with no dose = preservative (other_ingredients). The source section on the label determines routing, not the ingredient name alone.

---

## Phase 1 Execution Steps

### Step 1: Run Dynamic Scan (Step 0 above)

Get current unmapped numbers. Record them as the "before" baseline.

### Step 2: Build Canonical Lookup Index

Create an in-memory index of ALL existing names across ALL routing target files:

```
IQM parents: key, standard_name, all aliases
IQM forms: form_key, all form aliases (under each parent)
botanical_ingredients: id, standard_name, latin_name, all aliases
other_ingredients: id, standard_name, all aliases
harmful_additives: standard_name, all aliases
banned_recalled: standard_name, all aliases
standardized_botanicals: standard_name, all aliases
allergens: all names/aliases
```

### Step 3: Root Cause Analysis (ALL THREE unmapped lists)

Process these **three** unmapped lists in priority order:

#### A. Enrichment-only unmapped (cleaning mapped, enricher disagrees) — BUG PRIORITY

These ~941 items are the **highest priority** because they indicate a code or alias bug.
The cleaner found them in a database, but the enricher's `_is_recognized_non_scorable()` missed them.

For each:

1. Search your canonical index — which DB did the cleaner match against?
2. Check if the enricher's lookup uses the same DB and aliases
3. If the alias exists in the DB but enricher can't find it → **code bug** (normalization mismatch, case sensitivity, prefix/suffix handling)
4. If the alias doesn't exist in the enricher's version of the DB → **alias gap in enricher's lookup**

#### B. Both-stages unmapped — TRUE DATA GAPS

These ~1,100 items are not in any database at all. Classify each:

- **Alias candidate**: same molecule exists under a different name → add alias
- **New IQM entry**: therapeutically active, evidence-backed → create IQM parent
- **New botanical entry**: plant-derived, non-scorable → add to botanical_ingredients
- **New other entry**: excipient, additive, non-botanical → add to other_ingredients
- **Harmful/banned**: requires source citation → add to appropriate penalty DB
- **Excipient leak**: shouldn't be in active ingredients at all → code fix
- **Review required**: uncertain → defer with reasoning

#### C. Cleaning-only active unmapped (enricher resolved or dropped)

These ~3,176 items were unmapped at cleaning but the enricher resolved them (or they were dropped from scorable). Lower priority, but scan for:

- Items the enricher resolved via pattern/contains match → consider adding proper aliases so cleaning also matches
- Items dropped from scorable → verify they were correctly dropped (not lost)

#### D. Cleaning inactive unmapped

These ~769 items are inactive ingredients not recognized by any DB. Most are excipients/capsule materials.

- Route to `other_ingredients.json` (most common)
- Check for misclassified actives that should be scorable
- Check for harmful additives that need penalty routing

#### E. Form fallbacks (parent matched, form missed) — SCORING ACCURACY

These ingredients matched an IQM parent but fell back to the `(unspecified)` form because no form alias matched the label text. They score conservatively (usually bio_score=5) instead of getting credit for their actual form quality.

For each fallback entry:

1. Look up the parent in IQM and list all existing forms
2. Determine which form the label text actually represents (e.g., "Bororganic Glycine" = boron glycinate, "Meriva Turmeric Phytosome" = curcumin phytosome)
3. If an existing form matches → add the label text as an alias to that form
4. If the ingredient represents a genuinely new form → create the form under the existing parent (with full schema: bio_score, natural, score, absorption_structured, dosage_importance, notes)
5. If uncertain → review_required

**Prioritize by score delta**: A fallback scoring 5 when the correct form scores 15 is a 10-point accuracy loss. Sort by `(best_form_score - fallback_score) * occurrence_count` for maximum impact.

### Step 4: Categorize by Resolution Type

Group all unmapped into these resolution buckets:

| Bucket            | Action                                                      | Target                                                |
| ----------------- | ----------------------------------------------------------- | ----------------------------------------------------- |
| Code fix          | Fix enricher `_is_recognized_non_scorable()` matching       | `enrich_supplements_v3.py`                            |
| Code fix          | Fix excipient leak detection                                | `enrich_supplements_v3.py` / `enhanced_normalizer.py` |
| Form alias → IQM  | Add form alias to resolve fallback (highest scoring impact) | `ingredient_quality_map.json`                         |
| Alias → IQM       | Add alias to existing IQM parent or form                    | `ingredient_quality_map.json`                         |
| Alias → Botanical | Add alias to existing botanical entry                       | `botanical_ingredients.json`                          |
| Alias → Other     | Add alias to existing other_ingredients entry               | `other_ingredients.json`                              |
| New → IQM         | Create new IQM parent (therapeutically active)              | `ingredient_quality_map.json`                         |
| New → Botanical   | Create new botanical entry (non-scorable plant)             | `botanical_ingredients.json`                          |
| New → Other       | Create new other_ingredients entry (excipient)              | `other_ingredients.json`                              |
| New → Harmful     | Create new harmful additive (penalty-bearing)               | `harmful_additives.json`                              |
| New → Banned      | Create new banned entry (safety-critical)                   | `banned_recalled_ingredients.json`                    |
| Review            | Uncertain — needs human decision                            | report only                                           |

---

## Required Deliverable Format (Phase 1)

### 1) Scan Results (paste dynamic scan output)

### 2) Root Cause Analysis

```
ENRICHMENT-ONLY unmapped (bug category): N reviewed
  - Code bugs in _is_recognized_non_scorable(): N
  - Alias gaps (DB has entry but missing alias variant): N
  - Normalization mismatches (case/prefix/suffix): N

BOTH-STAGES unmapped (true data gaps): N reviewed
  - Alias candidates (existing molecule, different name): N
  - New IQM entries needed: N
  - New botanical entries needed: N
  - New other_ingredients entries needed: N
  - Harmful/banned (requires source): N
  - Excipient leaks (code fix): N
  - Review required: N

CLEANING-ONLY unmapped: N reviewed
  - Properly resolved by enricher: N
  - Need alias backfill to cleaning lookup: N

CLEANING INACTIVE unmapped: N reviewed
  - New other_ingredients entries: N
  - Already recognized (alias gap): N
  - Review required: N

FORM FALLBACKS (parent matched, form missed): N reviewed
  - Alias → existing IQM form: N (total score impact: +Npts across N products)
  - New IQM form needed: N
  - Correct fallback (truly unspecified): N
  - Review required: N

Top systemic patterns:
  1. [pattern] — affects N ingredients — [example]
  2. [pattern] — affects N ingredients — [example]
```

### 3) Proposed Code Fixes (No edits yet)

For each fix:
| Field | Value |
|-------|-------|
| File | path |
| Function | name |
| Failure mode | what breaks |
| Fix | what to change |
| Risk | Low/Medium/High |
| Impact | N ingredients across N products |

### 4) Proposed Data Changes (Grouped by JSON File)

#### → ingredient_quality_map.json

**Form fallback resolutions** (alias to existing form — highest scoring impact):
| Raw Label Text | Parent | Target Form | Current Score | Correct Score | Delta | Occurrences | Confidence |
|---------------|--------|-------------|:---:|:---:|:---:|:---:|:---:|

**Alias candidates** (unmapped → existing parent/form):
| Raw Name | Target Parent | Target Form | Confidence | Proof |
|----------|---------------|-------------|------------|-------|

**New entry candidates**:
| Raw Name | Proposed Key | Category | Bio Score | Natural | Source |
|----------|-------------|----------|-----------|---------|--------|

#### → botanical_ingredients.json

**Alias candidates**:
| Raw Name | Target Entry ID | Confidence |
|----------|----------------|------------|

**New entry candidates**:
| Raw Name | Proposed ID | Latin Name | Category | Source |
|----------|------------|------------|----------|--------|

#### → other_ingredients.json

**Alias candidates**:
| Raw Name | Target Entry ID | Confidence |
|----------|----------------|------------|

**New entry candidates**:
| Raw Name | Proposed ID | Category | is_additive |
|----------|------------|----------|-------------|

#### → harmful_additives.json (penalty — requires source)

| Raw Name | Severity | Mechanism | Source Citation |
| -------- | -------- | --------- | --------------- |

#### → banned_recalled_ingredients.json (safety-critical — requires citation)

| Raw Name | Regulatory Status | Source Citation |
| -------- | ----------------- | --------------- |

#### → Review Required

| Raw Name | Stage | Ambiguity Reason | Missing Evidence |
| -------- | ----- | ---------------- | ---------------- |

### 5) Safety/Scoring Guardrail Check

- [ ] No penalty-worthy ingredient routed to `other_ingredients` or `botanical_ingredients`
- [ ] All banned/recalled proposals have FDA/NIH/PubMed source citations
- [ ] Standardization markers preserved for `standardized_botanicals` entries
- [ ] Score formula `score = bio_score + (3 if natural else 0)` validated for all new IQM entries
- [ ] `absorption_structured` has all 5 fields for every new IQM form
- [ ] `dosage_importance` present on every new IQM form
- [ ] No cross-parent alias conflicts introduced (or added to ALLOWED_CROSS_ALIASES)
- [ ] Notes ≥80 chars with clinical/mechanistic content for every non-unspecified form
- [ ] botanical_ingredients entries have latin_name and CUI
- [ ] other_ingredients entries have is_additive and allergen flags

### 6) Impact Estimate

```
Before (from dynamic scan):
  Cleaning active unmapped:   N unique, N occurrences
  Cleaning inactive unmapped: N unique, N occurrences
  Enrichment unmapped:        N unique, N occurrences (X.X%)
  Form fallbacks:             N unique, N occurrences

After (estimated):
  Cleaning active unmapped:   ~N unique, ~N occurrences
  Cleaning inactive unmapped: ~N unique, ~N occurrences
  Enrichment unmapped:        ~N unique, ~N occurrences (~X.X%)
  Form fallbacks:             ~N unique, ~N occurrences

Resolution breakdown:
  Code fixes:                  N ingredients (N occurrences)
  Form fallback aliases (IQM): N ingredients (N occurrences, +N avg score pts)
  Alias additions (IQM):       N ingredients (N occurrences)
  Alias additions (botanical):  N ingredients (N occurrences)
  Alias additions (other):     N ingredients (N occurrences)
  New IQM entries:             N ingredients (N occurrences)
  New botanical entries:        N ingredients (N occurrences)
  New other entries:            N ingredients (N occurrences)
  Excipient fix:               N ingredients (N occurrences)
  Review required (deferred):  N ingredients (N occurrences)
```

### 7) Approval Gate

**"Phase 1 analysis complete. Awaiting approval before writing files."**

List specific changes awaiting approval grouped by:

1. Code fixes (with exact file:line ranges)
2. Data file additions (with counts per file)
3. Test updates needed (ALLOWED_CROSS_ALIASES etc.)
4. Items deferred to next session (review_required)

---

## Phase 2 Execution Checklist (After Approval)

1. Apply code fixes
2. Apply data file changes (IQM, botanicals, others, harmful, banned)
3. Update `ALLOWED_CROSS_ALIASES` if needed
4. Run `python -m pytest scripts/tests/ -x -q` — all tests must pass
5. Run `python scripts/db_integrity_sanity_check.py` — all checks must pass
6. Re-run the cleaning stage for affected datasets (to regenerate unmapped reports)
7. Re-enrich a sample batch and verify:
   - `unmapped_scorable_count` dropped as expected
   - No regression in existing mapped ingredients
   - No new test failures
8. Re-run the dynamic scan (Step 0) and report before/after comparison
9. Report final impact numbers and remaining unmapped for next session

---

## Source Validation Rule

If classification is uncertain or safety-impacting, validate with real references:

- FDA (warning letters, import alerts, GRAS notices)
- NIH/ODS/NCCIH (fact sheets, safety reports)
- PubMed (RCTs, systematic reviews, case reports)

Do **not** make high-risk recommendations (banned/recalled, harmful) without citation support.

---

## Prioritization Order (Per Session)

1. **Code bugs first** — fix `_is_recognized_non_scorable()` recognition gap (enrichment-only unmapped category)
2. **Excipient leaks** — fix detection for items like "100% Vegetarian Capsule"
3. **Form fallbacks with high score delta** — e.g., Bororganic Glycine→boron_glycinate (+11pts × 21 products). Pure alias additions, highest ROI
4. **Enrichment Tier 1** (≥10 occurrences) — biggest impact per fix
5. **Branded ingredients** — Meriva, Capsimax, Aquamin etc. → alias to base ingredient
6. **Remaining form fallbacks** — lower delta or fewer occurrences
7. **Cleaning inactive unmapped** — Vegetable Capsule variants, excipients
8. **Enrichment Tier 2** (3-9 occurrences)
9. **Cleaning active-only unmapped** — backfill aliases so both stages agree
10. **Enrichment Tier 3** (1-2 occurrences) — batch in groups of 50

After each session, re-run the dynamic scan. The numbers will decrease. Pick up where you left off using the same prioritization order.

---

## Input

Scan ALL datasets:

```
scripts/output_*/unmapped/                                         ← cleaning-stage unmapped
scripts/output_*_enriched/enriched/enriched_cleaned_batch_*.json   ← enrichment-stage unmapped
scripts/output_*_enriched/reports/parent_fallback_report.json      ← form fallback reports
scripts/output_*_enriched/reports/enrichment_summary_*.json        ← enrichment summaries
```
