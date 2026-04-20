# Sprint D — Accuracy 100% Or Nothing

**Start**: after Phase 7 full pipeline run finishes (so we have fresh enriched data for every brand).
**Mission**: Fix every accuracy bug found in the Period C deep audit. Nothing silently dropped. Every row on the user's label has a correct canonical, a correct verdict, and a correct score. This is a medical app — wrong verdicts harm real people.

**Evidence base**: `scripts/reports/deep_accuracy_audit.json` — the Period-C audit across 19 brands / 126,074 active ingredients. Re-run `scripts/tests/deep_accuracy_audit.py` after each sprint to verify the fix delta.

---

## Non-negotiable invariants (enforced by tests)

1. **Zero silently-mapped rows** — `mapped=True` implies `canonical_id != None`. Mechanical test, fails the suite if ever re-introduced.
2. **Zero Nutrition-Facts panel rows in activeIngredients** — sugars/sweeteners/fats/calories route to `nutritionalInfo` + `other_ingredients` with small-penalty classification.
3. **Zero false-positive banned_recalled matches on benign herbs** — every banned alias must be scoped by DSLD category + dose to avoid collisions (Amaranth plant ≠ Amaranth dye).
4. **Zero blend-header duplicates** — if a blend header and its members share a canonical, scorer counts the ingredient once.
5. **< 5% of scorable actives on "unspecified" form** — DSLD `forms[].name` must flow through the cleaner into the enricher's form-alias lookup.

---

## Sprint D1 — Critical verdict bugs (ship-blockers)

**Why first**: these produce WRONG USER VERDICTS. Someone could be told "DO NOT CONSUME" on a healthy amaranth protein shake. Fix before anything else.

### D1.1 — Amaranth plant-vs-dye disambiguation ⚠️ CRITICAL SAFETY

**Scope**: 66 products currently getting BLOCKED verdict on benign amaranth grain.

**Root cause**: `banned_recalled_ingredients.json` has an alias "amaranth" pointing to FD&C Red No. 2 (banned dye). The cleaner's reverse index matches the plant name to the dye canonical.

**Fix**:
1. In `scripts/data/banned_recalled_ingredients.json`, rename the banned entry's `standard_name` to "FD&C Red No. 2" and remove the bare "amaranth" alias. Replace with specific aliases: "amaranth red dye", "FD&C Red No. 2", "FD&C Red 2", "Red No. 2", "E123", "CI 16185".
2. Add new `amaranth_grain` entry to `botanical_ingredients.json`:
   - standard_name: "Amaranth"
   - UMLS CUI: verify via `verify_cui.py` (Amaranthus species)
   - plant_part: "seed"
   - aliases: "amaranth", "amaranthus", "amaranth grain", "amaranth seed", "amaranth protein"
3. Add a context guard in `_resolve_canonical_identity`: if raw_name contains "amaranth" AND DSLD `raw_category` is `carbohydrate` / `food` / `protein` / `fiber` OR `ingredientGroup` is NOT "Color" → route to `amaranth_grain`, NOT the dye.

**Acceptance**:
- Every one of the 66 currently-BLOCKED amaranth products scores normally.
- Any product declaring "FD&C Red No. 2" or "E123" still triggers the banned_recalled flag.
- Test `test_amaranth_disambiguation.py` covers both paths.

**Shadow-run**: 66 affected products from Nature_Made, Garden_of_life, Vitafusion. Score should change from BLOCKED → SAFE/CAUTION/POOR based on product quality.

### D1.2 — Banned_recalled alias audit ⚠️ CRITICAL SAFETY

**Scope**: ~30 rows — benign herbs getting wrongly blocked.

**Current false positives**:
- `Essence of organic Orange (peel) oil` (14) — orange peel oil is a flavor/fragrance, NOT bitter orange synephrine extract
- `Matcha Green Tea` / `organic Matcha Green Tea` / `leaf powder` (13) — matcha leaf is legal at supplement doses; banned only applies to high-EGCG liver-toxic extracts
- `Garcinia cambogia extract` (11) — FDA has warnings but not banned; blocking kills legit products
- `Silver` (2) — colloidal silver is restricted but not blanket-banned

**Fix approach** (stricter matching):
1. Audit `banned_recalled_ingredients.json` — for each entry, document the EXACT regulatory basis (FDA alert #, NDI rejection, etc.) and scope the aliases strictly.
2. Add a `match_scope` field per banned entry:
   - `"exact_only"` — only full-string match (no substring, no fuzzy)
   - `"requires_extract_form"` — only triggers when DSLD `raw_category` is "extract" AND form is "extract" or "concentrate"
   - `"requires_dose_above"` — only triggers above dose threshold (e.g., green tea banned only if EGCG > 800 mg/day)
3. Update cleaner's banned-match logic to respect `match_scope` — no more greedy aliases.
4. Bitter Orange vs sweet orange:
   - Bitter Orange (Citrus aurantium) + synephrine → banned when standardized to synephrine
   - Sweet orange peel oil, orange essential oil → NOT banned (flavor use)
   - Separate canonical entries with species-level disambiguation

**Acceptance**:
- Zero false-positive banned matches on DB audit rerun.
- Real banned ingredients (CBD as dietary supplement, 7-Keto DHEA, Vinpocetine, Ephedra) still trigger correctly.

**Shadow-run**: 30 affected products + 20 legitimately-banned products. Only the 20 should be BLOCKED.

### D1.3 — Nutrition Facts leak (sugars/sweeteners/fats) ⚠️ CRITICAL CORRECTNESS

**Scope**: ~150 rows — Sugar Alcohols, Xylitol, Cane Sugar, Dextrose, Maltodextrin, Palm Oil appearing as active ingredients.

**User clarification**: route these to `other_ingredients` with **small penalty** (sugar in supplements IS low quality — penalize, but don't hit full harmful-additive hammer).

**Fix**:
1. Extend `_is_nutrition_fact` in `enhanced_normalizer.py` to recognize sugars/sweeteners/fats by DSLD category:
   - `dsld_category` in `{"Calorie", "Carbohydrate", "Sugar", "Sugar (Added)", "Total Sugar", "Fat", "Saturated Fat", "Trans Fat", "Cholesterol"}` AND dose is a Nutrition-Facts-panel unit (g, calories) → route to `nutritionalInfo` as disclosure.
2. Separately, if these ingredient names appear with DSLD category "other"/"additive" (actually used as an additive in formulation, not a Nutrition-Facts disclosure), route to `other_ingredients.json` with `additive_type: "sweetener"` / `"sugar"` / `"fat"` and `penalty_level: "low"`.
3. Extend `other_ingredients.json`:
   - Sugar entries (Cane Sugar, Dextrose, Fructose, Sucrose) with `penalty_level: "low"` → B1 penalty 0.25 per entry (not the 0.5 full-harmful penalty)
   - Sugar alcohol entries (Xylitol, Erythritol, Sorbitol, Maltitol) with same penalty_level: "low"
   - Maltodextrin already exists; verify it has correct classification
4. Remove these from `harmful_additives.json` (move the entries over to other_ingredients with low penalty).

**Acceptance**:
- "Sugar Alcohols 3g" in a gummy's supplement facts → `nutritionalInfo.sugars = 3g`, NOT in actives.
- "Maltodextrin" listed as ingredient in formulation → `other_ingredients` with small penalty.
- B1 sugar-family penalty is ~0.5 max per product (not 5+ accumulated from 10 sugar rows).

**Shadow-run**: 150 affected products, verify B1_penalty drops appropriately and scores stabilize.

### D1.4 — D-Mannose + branded fibers correct DB routing

**Scope**: 19 products with D-Mannose misclassified; 8 with VitaFiber/CreaFibe.

**Fix**:
1. Add `d_mannose` to `ingredient_quality_map.json`:
   - standard_name: "D-Mannose"
   - UMLS CUI: verify via API (C0024691 — D-Mannose is a valid UMLS concept)
   - bio_score: 10 (well-studied for UTI prevention), dosage_importance: primary
   - RDA/UL: verify — typical 500-2000 mg/day for UTI
2. Remove D-Mannose from `harmful_additives.json`.
3. Add VitaFiber to `other_ingredients.json` (it's isomalto-oligosaccharides — a prebiotic fiber)
4. Add CreaFibe Cellulose to `other_ingredients.json` (branded cellulose fiber)
5. Test: each now resolves to correct DB.

**Shadow-run**: UTI-focused products from Nutricost, Thorne.

---

## Sprint D2 — Contract fix + silently-mapped cleanup

### D2.1 — Cleaner contract: is_mapped ⇒ canonical_id

**Fix** (`enhanced_normalizer.py:4235` + 4643 + 4852 — all three row-builder sites):

```python
# After existing is_mapped computation:
if is_mapped and not canonical_id:
    # Protocol rule #4: no silently-mapped rows. If no canonical resolved,
    # the ingredient is NOT mapped and must surface in the unmapped gap report.
    is_mapped = False
    # Record to the gap tracker so we can see what alias expansion is needed.
    if not self._is_nutrition_fact(name):
        self._record_unmapped_ingredient(name, forms, is_active=is_active)
```

**Regression test** (`test_no_silently_mapped_rows.py`):
- Scans every cleaned batch in `scripts/products/output_*/cleaned/`.
- Fails if any ingredient has `mapped=True AND canonical_id=None`.
- Also fails if `canonical_source_db='ingredient_quality_map'` but `canonical_id` is not in IQM keys.

**Acceptance**: deep audit v2 reports 0 silently-mapped rows across all 20 brands.

### D2.2 — Amino-acid qualifier-suffix strip

**Fix**: In `_resolve_canonical_identity` (before the reverse-index lookup), apply a qualifier-stripping transform:

```python
def _strip_qualifier_suffixes(name: str) -> str:
    """
    Remove trailing qualifier tokens that aren't part of the ingredient
    identity: ", Micronized", ", Organic", ", Freeze-Dried", etc.
    These qualifiers describe preparation/processing, not chemistry.
    """
    return re.sub(
        r',\s*(Micronized|Organic|Natural|Freeze[- ]Dried|Raw|Fermented|Vegan|Non-GMO|USP|Pharmaceutical Grade)\s*$',
        '',
        name,
        flags=re.IGNORECASE,
    ).strip()
```

**Acceptance**: `_resolve_canonical_identity("Phenylalanine, Micronized")` → `('phenylalanine', 'ingredient_quality_map')`. Same for Tryptophan, Methionine, Histidine.

### D2.3 — Generic blend-header entries in proprietary_blends.json

Add entries for the common generic blend names discovered by audit:
- `BLEND_AMINO_GENERIC` — aliases: "Amino Acid Blend", "Amino Acid Complex", "Amino Acceleration System", "Natural Amino Complex"
- `BLEND_BCAA` — aliases: "Branched Chain Amino Acid Blend", "BCAA Blend", "BCAA Complex"
- `BLEND_EYE_HEALTH` — "Eye Health Support Blend", "Eye Support Matrix", "Vision Support Complex"
- `BLEND_JOINT` — "Joint Cushion Support Blend", "Joint Support Matrix", "Joint Complex"
- `BLEND_SALAD_GREENS` — "Salad Extract", "Greens Blend", "Vegetable Blend"
- `BLEND_PROTEIN_GENERIC` — "100% Whey Protein Blend" (but ALSO consider if this should parse to whey_protein canonical)
- (extend as audit surfaces more)

Each entry needs:
- category (amino, eye_health, joint, etc.)
- transparency: blend_header (no individual dose info)
- is_scorable: True with blend-header scoring rules

### D2.4 — Branded proprietary compounds (Velositol/MyoTor/Tesnor/Metabolaid/ActivAIT/Vitaberry)

For each branded compound, do the research-then-DB-add workflow:

| Brand name | What it is | Target DB | Notes |
|---|---|---|---|
| Velositol | Amylopectin + chromium complex, sports performance | `proprietary_blends.json` | Nutrition21 brand; patented combo; `cui_status: governed_null` |
| MyoTor / MyoTOR | Branded sports-nutrition matrix (BCAAs + phosphatidic acid) | `proprietary_blends.json` | Compound Solutions brand |
| Tesnor | Testosterone-support branded matrix | `proprietary_blends.json` | |
| Metabolaid | Hibiscus + lemon verbena polyphenol complex | `proprietary_blends.json` or standardized_botanicals.json | |
| ActivAIT Mustard Essential Oil | Branded mustard seed EO | `botanical_ingredients.json` | plant_part: "seed"; brand alias under main mustard entry |
| Vitaberry Plus(TM) | Branded berry blend | `proprietary_blends.json` | |
| Protease Aminogen | Branded enzyme | `other_ingredients.json` | enzyme: protease, brand alias |

Each entry needs CUI verification (`verify_cui.py` — most will be `governed_null` for branded trademarks), regulatory status, mechanism note.

### D2.5 — Whole-food + uncommon plants

Add to `botanical_ingredients.json`:

| Ingredient | genus/species | CUI (verify) | plant_part |
|---|---|---|---|
| Swedish Oats Beta-Glucans | Avena sativa | C0029182 | seed |
| Blueberry juice powder | Vaccinium corymbosum | C0949240 | fruit |
| Tamarind juice powder | Tamarindus indica | C0965568 | fruit |
| Ecklonia radiata | Ecklonia radiata | — (verify) | whole |
| Ecklonia kurome | Ecklonia kurome | — (verify) | whole |
| Alaria esculenta | Alaria esculenta | — (verify) | whole |
| Brussels (sprouts powder) | Brassica oleracea | C0006081 | whole |
| Green Bean powder | Phaseolus vulgaris | C0016968 | seed |
| Lima Bean powder | Phaseolus lunatus | — (verify) | seed |
| Cherry puree powder | Prunus avium | C0008625 | fruit |
| Beef Protein isolate | Bos taurus | (animal, no botanical) | — |

For animal proteins (Beef/Chicken), route to `other_ingredients.json` as protein-source entries with bio_score reflecting quality.

### D2.6 — Parser split artifacts

**Fix 1**: Multi-ingredient rows
- Detect `X & Y` or `X and Y` patterns in a single raw ingredient row → split into two rows, each with its own canonical resolution.
- Examples: "Glutamine & Glutamic Acid" → 2 rows. "Acacia catechu wood & bark extract and Chinese Skullcap root extract" → 2 rows.

**Fix 2**: Percent/dose-only rows
- Skip rows whose `raw_source_text` matches `^(less than |≤|<)?\s*[\d.]+\s*%?\s*$` or `^[\d.]+\s*(mg|mcg|g|iu|units?)\s*$`.
- These are parser artifacts from malformed DSLD entries — not real ingredients.

**Test**: `test_cleaner_row_splitting.py` covers both patterns.

---

## Sprint D3 — Form specificity (cut 30,807 unspecified forms)

### D3.1 — Verify cleaner forms[] preservation is complete

Audit `forms_structured` emission in `_process_ingredient` — confirm ALL DSLD fields flow:
- `name`, `ingredientId`, `order`, `prefix`, `percent`, `category`, `ingredientGroup`, `uniiCode`

Plus: cleaner should also emit `forms[].standard_name` (the matcher's resolution on the form name itself), so the enricher gets direct hit without re-running the matcher.

### D3.2 — Enricher reads forms[].name as primary form signal

**Today's path**: enricher's `_match_multi_form` uses `raw_form_text` extracted from ingredient name text.

**Fix**: In `_build_form_info_from_cleaned`, elevate `form.get('name')` (DSLD's authoritative form name) to the PRIMARY `match_candidates` entry. Fall through to text extraction only if `form.name` is missing.

**Also**: use `form.ingredientGroup` and `form.category` as context hints for parent selection in `_match_multi_form` — Phase 3's `cleaner_canonical_id` works for parent; this adds form-level context propagation.

**Test**:
- "Calcium (Form: as Calcium Carbonate)" where cleaner forms[0].name="Calcium Carbonate" → enricher matches `calcium.forms["calcium carbonate"]` with bio_score=8 (not unspecified=5).
- "Vitamin D (Form: as Cholecalciferol)" → enricher matches `vitamin_d.forms["cholecalciferol"]`.
- Confirmed for all top-30 canonicals.

### D3.3 — IQM form-alias expansion for top-30 missing forms

Audit the top-30 "unspecified" canonicals (from D audit). For each:
1. List actual form names appearing on DSLD labels for products with this canonical.
2. Check IQM `forms[]` for that canonical — are the forms and their aliases covering the label variants?
3. Add missing aliases. Protocol: each alias addition must be duplicate-checked against ALL IQM parents (schema test catches collisions).

**Priority 1**: calcium (1363), lutein (1031), vitamin_b9_folate (1011), potassium (886), vitamin_c (805), iron (749), zeaxanthin (738), chromium (563), dha (530), epa (497).

Each gets ~5-15 new form-aliases typically. Schema test (`test_ingredient_quality_map_schema.py`) validates.

---

## Sprint D4 — Scorer verification (duplicate canonicals)

### D4.1 — Same-canonical dose-summing + max-bio_score selection

**Question to answer**: When "Vitamin A (Beta-Carotene) 5000 IU" + "Vitamin A Acetate 5000 IU" both map to `vitamin_a` canonical:
- Does the scorer sum doses (10,000 IU total) for RDA/UL checks? ✓ required
- Does it pick max bio_score form (premium form) for quality credit? ✓ required
- Does it NOT double-count the bio_score contribution? ✓ required

Trace the logic in `score_supplements.py` around `ingredient_points` aggregation and `A1` computation.

### D4.2 — Blend header + blend member dup

If a proprietary blend is declared as "Amino Acid Blend 5000 mg" with members "L-Leucine 500 mg, L-Isoleucine 250 mg..." both the blend header and the disclosed member canonicals may appear. Scorer should:
- Count the blend header once (for blend-transparency penalty)
- Count each disclosed member once (for individual-ingredient credit)
- NOT inflate the parent canonical just because a blend header shares its category

Fix: scorer-side dedup based on `parent_blend` relationship + `isNestedIngredient` flag.

---

## Sprint D5 — Release gate

### D5.1 — Full pipeline re-run on all 20 brands

After D1-D4 land, re-run `run_pipeline.py` on every brand. With the contract fix + DB expansions, expect:
- Silently-mapped rows: 0 (down from 833)
- Cross-DB leaks: 0 (down from 655)
- Amaranth false BLOCKS: 0 (down from 66)
- Unspecified form %: <5% (down from 29%)

### D5.2 — Deep accuracy audit v2

Run `scripts/tests/deep_accuracy_audit.py` on fresh data. Every metric must hit its invariant target.

### D5.3 — Snapshot test + shadow-diff

Run `test_scoring_snapshot_v1.py` — expect drift on many snapshot products because we've fixed form specificity and canonicalization. Use `shadow_diff_snapshots.py` + manual review to confirm each drift is IMPROVEMENT, not regression.

Then regenerate fixtures with full changelog entries documenting the D-sprint changes.

### D5.4 — Final release

- `enrichment_contract_validator.py` clean
- `coverage_gate.py` passes at 99.5%+ per brand with ZERO blocked products (meaning every product can score)
- `db_integrity_sanity_check.py --strict` clean
- `build_final_db.py` → production SQLite
- Supabase dry-run diff reviewed — any mass shift investigated before applying

---

## Test coverage addition summary

| Sprint | New test file | Count | What it guards |
|---|---|---|---|
| D1.1 | `test_amaranth_disambiguation.py` | 6 | plant vs dye routing |
| D1.2 | `test_banned_recalled_strict_match.py` | 15 | every banned entry match-scope respected |
| D1.3 | `test_nutrition_facts_extended.py` | 10 | sugars/sweeteners/fats routing |
| D1.4 | `test_d_mannose_iqm_routing.py` | 4 | D-Mannose + branded fibers |
| D2.1 | `test_no_silently_mapped_rows.py` | cross-brand | protocol rule #4 enforcement |
| D2.2 | `test_amino_acid_qualifier_strip.py` | 15 | qualifier suffixes map correctly |
| D2.6 | `test_cleaner_row_splitting.py` | 8 | `&`/`and` splitting + artifact skipping |
| D3.2 | `test_enricher_form_specificity.py` | 30 | top 30 canonicals score premium form correctly |
| D4.1 | `test_scorer_same_canonical_aggregation.py` | 10 | dose sum + max-bio_score |
| D4.2 | `test_scorer_blend_header_member_dedup.py` | 5 | no double-counting |

**Estimated new tests**: ~100. Current suite at 4,105 → target ~4,200+ after Sprint D.

---

## Order of execution (strict)

1. **D1.1 → D1.2 → D1.3 → D1.4** (verdict fixes first — these produce user-visible safety regressions if left)
2. **D2.1** (contract fix — establishes the invariant before we expand)
3. **D2.2 → D2.3 → D2.4 → D2.5 → D2.6** (parallel-safe; alias/DB expansion)
4. **D3.1 → D3.2 → D3.3** (form specificity — the biggest score-accuracy lift)
5. **D4.1 → D4.2** (scorer audit — verification)
6. **D5.1 → D5.2 → D5.3 → D5.4** (release gate)

Each sprint task: code change + regression test + targeted shadow-run + deep-audit-v2 delta report before moving on.

---

## Estimated compute

- Each D1-D4 task: 0.25-1 focused session
- D5.1 full pipeline: ~3 hours
- D5.2-D5.4: ~1 session
- **Total: ~10 focused sessions + ~3 hours compute** for medical-grade 100% accuracy baseline.

---

*End of Sprint D plan. Begin with D1.1 (Amaranth — the safety bomb) as soon as current Phase 7 pipeline run completes.*
