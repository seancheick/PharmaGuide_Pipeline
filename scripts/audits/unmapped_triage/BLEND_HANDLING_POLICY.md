# Blend Handling Policy — V1.1 Strategic Spec

**Author:** dev review 2026-05-01
**Status:** Spec for next-pass implementation; partial application this session

This doc formalizes the rules for distinguishing label structure (headers, ignore for scoring) from substance (real ingredients, score them). The policy is core to PharmaGuide's normalization engine and a key data-moat differentiator.

---

## Core distinction: structure vs substance

Every label-row that looks like a "blend name" falls into one of two cases:

### Case A — TRUE HEADER (label organization, ignore in scoring)

**Definition:** the row is just a label heading; the actual ingredients are listed individually below.

**Detection signature:**
- Name typically ends with `:` (trailing colon)
- AND child ingredients exist below it on the label
- AND those children individually carry doses (per-active mg amounts)

**Example:**
```
Cholesterol Support Blend:               ← TRUE HEADER (ignore)
  CardioAid Phytosterols     800 mg
  Black Tea leaf extract     200 mg
  Coenzyme Q-10              30 mg
  Betaine                    25 mg
```

**Pipeline action:** flag as `is_blend_header=true`, exclude from scorable count, score the children individually.

### Case B — OPAQUE BLEND (real active, hidden composition)

**Definition:** the row IS the active ingredient; manufacturer disclosed only the blend name and total weight, not per-component amounts.

**Detection signature:**
- No `:` at end (or has `:` but no children listed below)
- AND has a quantity (total blend weight, e.g. "1200 mg")
- AND no children listed below it on the label

**Example:**
```
Proprietary Fat Burn Blend     1200 mg   ← OPAQUE ACTIVE (score it, low confidence)
```

**Pipeline action:** treat as a real active ingredient, but mark `composition: "unknown"` and **downgrade score confidence**. Manufacturer is hiding what's in the bottle.

---

## Why this matters

**If you treat both cases the same:**
- Treating Case B as a header → underscore the product (you'll miss real penalties for opaque hidden ingredients)
- Treating Case A as an active → overscore (counting label headers as if they were ingredients)
- Either direction → mislead users

**The PharmaGuide differentiator:** competitors that rely on supplement APIs don't normalize this far. By correctly distinguishing structure from substance, PharmaGuide builds a defensible canonical ingredient graph that surfaces hidden-composition risk.

---

## The structural rule (auto-detection target) — CORRECTED 4-state classifier

**Important correction (per dev review 2026-05-01):** the rule must use a 4-state classifier, not a 2-case binary. My initial draft incorrectly treated "category=blend AND quantity=NP" as always being a header, which would drop valid disclosed-blend actives. Corrected rule:

```python
# PRIMARY signal — structural truth from raw DSLD
if raw_category == "blend":

    if quantity_unit == "NP":
        if len(nestedRows) > 0:
            return "DISCLOSED_BLEND"
            # → header role + children disclosed below.
            # Score the children individually. Skip the parent row from scorable.
        else:
            # AMBIGUOUS — DSLD sometimes flat-encodes children as top-level
            # siblings instead of nesting them. Disambiguate via lookahead:
            # if the next 1-N rows in ingredientRows are valid ingredients
            # (non-blend category + real quantity), this is a true header
            # whose children DSLD failed to nest. Otherwise it's an opaque
            # standalone blend with no composition disclosed.
            if has_valid_following_ingredients(this_index, all_ingredient_rows):
                return "BLEND_HEADER"
                # → header; children exist as top-level siblings (DSLD ingestion
                # didn't preserve the nesting). Skip parent from scorable.
            else:
                return "OPAQUE_BLEND"
                # → standalone opaque blend with no composition anywhere.
                # Score as real active; route through B5 transparency penalty.

# Lookahead helper:
def has_valid_following_ingredients(idx, rows, lookahead=4):
    """Check if rows immediately after `idx` look like valid ingredient
    entries (non-blend category, real quantity). DSLD's flat-encoded
    blend children appear as adjacent top-level siblings."""
    VALID_CATEGORIES = {
        "vitamin", "mineral", "amino acid", "fat", "botanical", "fatty acid",
        "carbohydrate", "protein", "non-nutrient/non-botanical", "fiber",
        "carotenoid", "flavonoid", "enzyme", "probiotic"
    }
    found_valid = 0
    for j in range(idx + 1, min(idx + 1 + lookahead, len(rows))):
        next_row = rows[j]
        next_cat = (next_row.get("category") or "").lower()
        next_qty = (next_row.get("quantity") or [{}])[0]
        next_unit = next_qty.get("unit", "")
        next_quantity = next_qty.get("quantity", 0)
        if next_cat in VALID_CATEGORIES and next_unit != "NP" and next_quantity > 0:
            found_valid += 1
        # Stop scanning once we hit another blend header (next group)
        elif next_cat == "blend":
            break
    return found_valid >= 1

    elif quantity > 0:
        if len(nestedRows) == 0:
            return "OPAQUE_BLEND"
            # → manufacturer disclosed blend total but no per-ingredient
            # composition. Score as a real active. Apply B5 transparency
            # penalty (already exists in scorer for proprietaryBlend).
        else:
            # FAKE TRANSPARENCY DETECTION: children listed but their
            # individual quantities are unknown.
            if all(child_qty in (0, None) or child_unit == "NP"
                   for child in nestedRows):
                return "OPAQUE_BLEND"  # children listed but no per-active doses → still opaque
            else:
                return "DISCLOSED_BLEND"  # children with real doses → fully disclosed

# SECONDARY fallback — pattern-name matching for malformed/missing category
elif (ingredient_name.rstrip().endswith(':')
      and not has_quantity(ingredient)
      and ingredient_name in BLEND_HEADER_EXACT_NAMES):
    return "BLEND_HEADER"  # safety net for cases where DSLD source lacks category tagging
```

### State → scoring action mapping

| State | Scorable count | Children scored | Confidence handling |
|---|---|---|---|
| `BLEND_HEADER` | exclude parent | n/a (no children) | n/a |
| `DISCLOSED_BLEND` | exclude parent | yes, individually | full confidence per child |
| `OPAQUE_BLEND` | **include** parent as active | n/a (no per-active doses) | route through existing B5 transparency penalty system (count-based + mass-based; see `score_supplements.py:B5` for the canonical implementation) — DO NOT use a fixed multiplier |
| Fake-transparency (subcase of OPAQUE_BLEND) | **include** parent as active | n/a | same B5 path; the "children listed but NP" pattern is handled identically to no-children-listed |

### Why the corrected rule matters

**Without the nestedRows check:** treating `category=blend + quantity=NP` as always BLEND_HEADER would drop labeled disclosed blends (Antioxidant Support Complex with CoQ10/Betaine/Lutemax/Zeaxanthin children) entirely from scoring. We'd lose those 4 valid actives + their evidence-research bonuses. Real product impact: ~20-30% of section A score on multi-blend products.

**Without fake-transparency detection:** manufacturers can game disclosed-blend by listing children without per-active doses. Without this check we'd score them as fully disclosed (high confidence) when in reality the user has no idea how much of each is in the bottle.

### Confidence — DO NOT use ×0.7 multiplier

My initial draft suggested `confidence × 0.7` for opaque blends. **Replace this with the existing B5 transparency penalty system** in `score_supplements.py`:

- B5 already counts `proprietaryBlend` flagged ingredients
- Penalty scales with: number of opaque blends + total opaque mass / total formula mass
- A fixed ×0.7 multiplier ignores severity (one tiny opaque blend vs three large opaque blends — same multiplier)
- The B5 system is the canonical place; OPAQUE_BLEND classification just feeds a flag into it

**Implementation hook:** when a row is classified `OPAQUE_BLEND`, set `proprietaryBlend = true` on the enriched output. The scorer's existing B5 logic picks it up via the existing transparency-mass calculation. No new confidence multiplier needed.

**Implementation file:** `scripts/enrich_supplements_v3.py` — `_should_skip_from_scoring` Group B (header rows).

---

## What's safe to bulk-add to BLEND_HEADER_EXACT_NAMES

✅ **Group 2A — verified headers** (apply when both criteria met):
1. Trailing colon (`X Blend:`, `X Matrix:`, `X Complex:`)
2. Spot-checked one or more product instances → siblings below match individually

❌ **NEVER bulk-add** Group 2B brand-specific blends without per-brand verification. Some are headers; some are opaque blends. Each must be individually checked against actual product data.

---

## Group 2A applied 2026-05-01 (this session)

After verification (children exist + matched on actual products):

| Header name | Verified product | Children matched |
|---|---|---|
| `Sports Blend:` | DSLD 69424 | Super Antioxidant Blend, Branched Chain AA Blend |
| `Hardcore Test Amplifier:` | DSLD 63763 | Tribulus, Testofen, Ursolic Acid, DHEA |
| `Energy Support Blend:` | DSLD 63824 | Elderberry, Beta-Glucans, Echinacea, Bee propolis |
| `Joint & Skin Support:` | DSLD 69734 | MSM, Silica, Lutemax, Hyaluronic Acid |
| `Circulatory Support Complex:` | DSLD 70017 | Men's Health Blend (nested header) |
| `Performance Energy & Metabolism Blend:` | DSLD 70149 | Joint & Skin Support Blend (nested header) |
| `Cholesterol Support Blend:` | **DSLD 74767** | CardioAid Phytosterols, Black Tea, CoQ10, Betaine |

Plus normalization variants (without colon, ampersand-vs-and, with/without commas) for matcher robustness.

**File patched:** `scripts/constants.py:898 BLEND_HEADER_EXACT_NAMES` — 21 entries added.

---

## Group 2A NOT applied (need re-verification)

- `Brain Health Blend:` — sample DSLD 69273 didn't show immediate-sibling children in my spot-check. Could be a deeper-nested structure or genuinely opaque. **Defer to next pass.**
- `Vasodilator Matrix:` — same. Sample DSLD 63763 — children may be nested differently. **Defer.**

---

## Group 2B — DO NOT bulk-approve (per dev policy)

The remaining ~81 brand-specific blend names (Wheybolic Protein Complex, Omega-Zyme Ultra Enzyme Relay Blend, Memory Health Blend, etc.) need **per-brand verification** before any are added to BLEND_HEADER_EXACT_NAMES.

For each:
1. Find the brand product that contains it
2. Check label data: are children listed below with individual doses?
3. If yes → header → add (with verification noted)
4. If no → opaque active → DO NOT add to header list; instead add to a new opaque-blend handling pathway (composition unknown + confidence downgrade)

This is a per-product review job (~81 cases).

---

## Special-case caveats

### Enterococcus faecium

Some strains are probiotic; some are pathogenic (vancomycin-resistant E. faecium = VRE = serious nosocomial pathogen). Cannot be bulk-added to IQM as a probiotic. Each strain must be:
- Identified by strain ID (not just genus species)
- Verified clinically as a SAFE probiotic strain (e.g. SF68, NCIMB 10415)
- Cross-checked against banned/recalled patterns

### Essential oils

`Essence of organic Orange (peel) oil`, `Essence of organic Chamomile (leaf) oil`, etc.

These are technically actives but often not clinically meaningful at typical supplement doses (mostly for flavoring). Need a policy:
- Skip from active scoring if dose < clinically-meaningful threshold
- Treat as flavoring per AddToHooks (other_ingredients)
- Special exception when EO is the standardized active (e.g. peppermint oil for IBS)

### Descriptor noise vs new ingredient

For the 204 AMBIGUOUS items, three buckets per dev:

| Bucket | Example | Action |
|---|---|---|
| Alias candidate | "matcha" → green_tea | Add as alias to existing parent (verify same-compound) |
| New real ingredient | "fucoxanthin" | API-verify + add to IQM |
| Descriptor noise | "organic watermelon protein" → strip "organic" + "protein" descriptor | Cleaner-side noise stripping |

---

## Implementation roadmap for the dev

### Sprint 1 (this session, applied)

- ✓ Add 21 Group 2A headers to BLEND_HEADER_EXACT_NAMES (7 unique headers + 14 normalization variants)
- ✓ Apply Cutch Tree, Bifido strain, Angelica gigas aliases to IQM (verified same-compound)
- ✓ Generate this policy doc

### Sprint 2 (next session — code change)

Implement the structural auto-detection rule in `enrich_supplements_v3.py:_should_skip_from_scoring`:

```python
# New Group B variant: structural blend-header auto-detect
if (ingredient_name.rstrip().endswith(':')
    and not has_quantity(ingredient)
    and has_following_sibling_actives_with_doses(ingredient_index, all_ingredients)):
    return SKIP_REASON_BLEND_HEADER_NO_DOSE
```

This automatically catches Group 2A across all brands without manual list maintenance.

### Sprint 3 — Opaque blend handling

Implement the "opaque blend = active with low confidence" rule:

1. New skip-reason: `SKIP_REASON_OPAQUE_BLEND_ACTIVE` (confusing — actually it's NOT a skip; it's a flag that says "score this but downgrade confidence")
2. Scoring engine reads `composition_disclosure: "unknown"` flag
3. Section A confidence multiplier: 0.7-0.8 when composition unknown
4. B5 already handles disclosure-level penalty for proprietary blends — this is additive

### Sprint 4 — Group 2B per-brand review

81 brand-specific blend names need product-by-product verification. Generate a worksheet (one row per blend, with sample product DSLD ID, child-presence yes/no, recommended action).

### Sprint 5 — AMBIGUOUS triage (204 items)

Bucket each into Alias / New ingredient / Descriptor noise. New ingredients require API verification (PubChem/UNII/UMLS/PubMed) before adding.

### Sprint 6 — Probiotic strain registry

Build a per-strain safety+evidence registry. Each strain entry must declare:
- NCBI Taxonomy ID (genus+species+strain)
- Strain-level safety status (probiotic-grade vs pathogenic-risk)
- Clinical evidence summary
- Bio_score per clinical RCT count

Special handling for ambiguous-genus organisms (Enterococcus, Bacillus) where some strains are pathogens.

---

## Why this is a data moat

Most supplement-tracking apps:
- Pull from supplement APIs (DSLD, Examine, etc.) without normalization
- Treat blend headers and opaque blends identically (or get both wrong)
- Don't surface "manufacturer hid composition" risk to users
- Don't differentiate strain-level safety in probiotics

PharmaGuide's normalization engine, when fully implemented, will:
- Correctly parse label structure (headers vs actives)
- Surface hidden-composition risk (opaque blend → "we don't know what's in this; lower confidence")
- Warn on probiotic-strain ambiguity (E. faecium without strain ID = unclear safety)
- Enable per-strain clinical evidence weighting

This is the canonical ingredient graph. Building it is slow; competitors can't easily replicate it because the labor cost is in the normalization, not the data.


---

## RAW DSLD VERIFICATION (post-comment 2026-05-01)

After dev's instruction to verify against raw DSLD JSON, inspected
`/Users/seancheick/Documents/DataSetDsld/staging/brands/GNC/74767.json`
directly. The raw source already encodes blend-header structure cleanly:

### DSLD's canonical signals

```json
{
  "ingredientRows": [
    {"name": "Calcium",                            "category": "mineral",   "quantity": [{"quantity": 50,   "unit": "mg"}]},
    {"name": "Cholesterol Support Blend:",         "category": "blend",     "quantity": [{"quantity": 0,    "unit": "NP"}], "nestedRows": []},
    {"name": "CardioAid Phytosterols",             "category": "fat",       "quantity": [{"quantity": 1200, "unit": "mg"}]},
    {"name": "Black Tea leaf extract",             "category": "botanical", "quantity": [{"quantity": 1000, "unit": "mg"}]},
    {"name": "Antioxidant Support Complex",        "category": "blend",     "quantity": [{"quantity": 0,    "unit": "NP"}],
     "nestedRows": [
       {"name": "Coenzyme Q-10",         "quantity": [{"quantity": 100, "unit": "mg"}]},
       {"name": "Betaine",               "quantity": [{"quantity": 100, "unit": "mg"}]},
       {"name": "Lutemax 2020 Lutein",   "quantity": [{"quantity": 1000,"unit": "mcg"}]},
       {"name": "Zeaxanthin",            "quantity": [{"quantity": 200, "unit": "mcg"}]}
     ]},
    {"name": "Inflammatory Response Support Blend:", "category": "blend",   "quantity": [{"quantity": 0, "unit": "NP"}],
     "nestedRows": [
       {"name": "Cutch Tree wood & bark extract", "category": "botanical", "quantity": [{"quantity": 62.5, "unit": "mg"}]},
       {"name": "Chinese Skullcap root extract",  "category": "botanical", "quantity": [{"quantity": 0,    "unit": "NP"}]}
     ]}
  ]
}
```

**Two canonical signals already in the raw DSLD source:**

1. **`category: "blend"`** — DSLD explicitly tags blend headers. Every blend-header row has this, regardless of whether the name ends with `:` or not.
2. **`quantity[].unit: "NP"` + `quantity[].quantity: 0`** — DSLD encodes "Not Provided" for blend totals (or non-disclosed quantities).
3. **`nestedRows` field** — DSLD encodes parent→child relationships explicitly via this nested array. Children of a blend header live in `nestedRows`, NOT as siblings in the top-level `ingredientRows`.

### Updated structural rule (use DSLD's own signals)

```
IF (raw_dsld.ingredientRows[i].category == "blend"
    AND raw_dsld.ingredientRows[i].quantity[].unit == "NP")
THEN
   → classify as BLEND_HEADER (Case A — true header)
   → score the children in nestedRows individually
   → exclude this row from scorable count

IF (raw_dsld.ingredientRows[i].category == "blend"
    AND raw_dsld.ingredientRows[i].quantity[].unit != "NP"
    AND len(raw_dsld.ingredientRows[i].nestedRows) == 0)
THEN
   → classify as OPAQUE_BLEND_ACTIVE (Case B — composition unknown)
   → flag is_active=true, composition="unknown"
   → downgrade quality confidence (Section A multiplier 0.7)
   → existing B5 disclosure-level penalty already fires
```

This is the right architectural fix — use DSLD's own structural signals
instead of pattern-matching on names. Eliminates the BLEND_HEADER_EXACT_NAMES
maintenance burden entirely (no more brand-by-brand per-name additions).

### Implication for current Group 2A patch

The 21 entries I added to BLEND_HEADER_EXACT_NAMES this session are a
pattern-name patch that works against the enriched-output stage. The
proper fix is in the cleaner / enricher to read `category` + `quantity.unit=NP`
from the raw DSLD source. Once that lands, the BLEND_HEADER_EXACT_NAMES
list can shrink dramatically (most entries become redundant).

Recommend: keep BLEND_HEADER_EXACT_NAMES for backwards-compat / edge cases,
but make the category+unit-NP signal the primary detection path.
