# IQM & Scoring Pipeline — Master Audit Prompt

> **Purpose:** Run this prompt with Claude Code quarterly (or monthly) to ensure the supplement scoring engine remains the most accurate, clinically rigorous, and schema-complete system in existence. Copy the full prompt below into a new Claude Code session in this repo.

---

## THE PROMPT

```
You are auditing a supplement scoring pipeline that powers a consumer health app. This is the most important data quality job — accuracy directly affects health decisions for real users. You must be thorough, evidence-based, and never rush.

## CODEBASE ORIENTATION

- **IQM file:** `scripts/data/ingredient_quality_map.json` — the master ingredient database (~500+ parents, each with scored forms)
- **Scoring range:** bio_score is 0-15. If natural=True, score = bio_score + 3 (max score = 18). If natural=False, score = bio_score (max score = 15). bio_score MUST NOT exceed 15.
- **Scoring engine:** `scripts/score_supplements.py` — reads IQM scores to produce final product grades
- **Enrichment pipeline:** `scripts/enrich_supplements_v3.py` — resolves raw labels → IQM parents/forms
- **Scoring spec:** `scripts/SCORING_ENGINE_SPEC.md` (v3.1.0) — authoritative scoring rules
- **Scoring config:** `scripts/config/scoring_config.json` — caps, gates, coefficients
- **Tests:** `python -m pytest scripts/tests/` — ALL tests must pass after every change
- **Supporting data files (in `scripts/data/`):**
  - `banned_recalled_ingredients.json` — hard-fail blocked substances (127 entries)
  - `harmful_additives.json` — penalty substances (110 entries, severity: critical/high/moderate/low)
  - `top_manufacturers_data.json` — trusted brands (77 entries, fuzzy threshold 0.90)
  - `allergens.json` — allergen detection
  - `backed_clinical_studies.json` — evidence database
  - `absorption_enhancers.json` — pairing bonuses (+3 pts)
  - `enhanced_delivery.json` — delivery tier scoring
  - `rda_optimal_uls.json` — RDA/UL reference values
  - `clinically_relevant_strains.json` — probiotic strain bonuses
  - `synergy_cluster.json` — synergy detection
  - `standardized_botanicals.json` — botanical standardization markers
  - `other_ingredients.json` — recognized non-scorable ingredients
  - `proprietary_blends.json` — blend recognition mapping
  - `manufacturer_violations.json` — brand deductions (cap -25)

## TASK 1: IQM 5-POINT AUDIT (PRIMARY — ~70% of effort)

Audit EVERY parent in `ingredient_quality_map.json` in batches of 3-4 (large parents like probiotics solo). For each batch:

### Step 1: Read Current State
Read the parent's forms, scores, aliases, absorption_structured, notes, and dosage_importance.

### Step 2: Clinical Research
Launch a research agent to verify EVERY claim against PubMed/NIH clinical data:
- **bio_score accuracy:** Is the bioavailability claim backed by human PK data? Search for isotope tracer studies, RCTs, and pharmacokinetic papers. The #1 error pattern is confusing intestinal absorption (~85-95% for most amino acids) with systemic bioavailability (often 20-60% after splanchnic first-pass extraction). Always find the SYSTEMIC number.
- **Score formula:** Verify `score = bio_score + (3 if natural else 0)` for every form.
- **natural flag:** Is this form genuinely naturally-derived? Probiotics = True (live organisms). Most supplemental amino acids = False (fermentation-synthesized). Botanical extracts = True. Synthetic vitamins = False.
- **absorption_structured values:** Every value must have range_low and range_high. The quality enum must be one of: unknown|poor|low|moderate|good|very_good|excellent|variable. Values must be 0-1 (proportion, not percentage).

### Step 3: Apply Evidence-Based Corrections
Use Python scripts to modify the JSON (load → modify → save → verify). NEVER hand-edit the JSON.

**Correction types to look for:**
- **Inflated bio_scores:** Marketing claims like "95% absorption" that cite intestinal uptake, not systemic bioavailability. Cross-reference with splanchnic extraction data (glutamate=88-96%, alanine=69%, glutamine=50-75%, arginine=20-68% dose-dependent).
- **NALT-type inversions:** Forms where the notes say "inferior to X" but the bio_score is HIGHER than X. The score and notes must agree.
- **Fake/phantom forms:** "X from food" forms that cannot appear on a supplement label. Delete these — they inflate scores with false natural bonuses. Exception: forms like "vitamin D from lichen" that ARE real supplement forms.
- **Missing Nitrosigine-type entries:** Patented branded forms with distinct PK mechanisms (arginase inhibition, PepT-1 bypass, liposomal encapsulation) that deserve their own form entry with proper scoring.
- **Stub notes:** Generic notes like "Supports digestive health" with no citations. Every non-unspecified form needs 80+ character notes with specific RCT citations, manufacturer/brand identification, and mechanism description.
- **Suffix aliases:** Remove all aliases ending in " supplement" — the normalizer doesn't need them.
- **Duplicate/scattered parents:** Scan the ENTIRE IQM file for parents that cover the same ingredient but are scattered in different positions (e.g., `prebiotics` at index 200 AND `inulin` at index 450 with overlapping forms/aliases). Merge them into a single canonical parent. This happened with prebiotics — beta-glucan and psyllium were forms under prebiotics but also had their own top-level parents. The rule: one ingredient = one parent. If strain-specific forms exist under an umbrella parent AND under species-level parents (like probiotics), audit for score mismatches and merge down to the more specific parent using the higher bio_score.
- **Cross-listed forms:** Forms that exist under two different parents (e.g., magnesium glycinate under both `magnesium` and `l_glycine`) must be removed from the secondary parent. The primary parent (the one the enricher routes to) owns it.
- **bio_score cap enforcement:** bio_score must be 0-15. No form should exceed bio_score=15. If natural=True, max score=18. If natural=False, max score=15.

### Step 4: Run Full Self-Audit (MANDATORY — do NOT skip)
After applying changes to each batch, run ALL 8 checks before reporting done:

1. **Score formula:** `score = bio_score + (3 if natural else 0)` — check every form. bio_score must be 0-15. Score must be 0-18. Any bio_score > 15 is a bug.
2. **nat accuracy:** Verify each form's natural flag is chemically correct
3. **absorption_structured complete:** All 5 fields (value, range_low, range_high, quality, notes) present. Range must exist when value exists.
4. **Notes quality:** Every non-unspecified form has 80+ char note that is:
   - **Scientifically true:** Every claim must be backed by a real published study. NO guessing, NO "may help with", NO vague marketing language. If you don't have a citation, don't make the claim.
   - **User-friendly:** Written for a health-conscious consumer scanning their supplement on a phone. No jargon without explanation. Example: "Absorbed via PepT-1 dipeptide transporter, bypassing gut enzymes that destroy free glutamine" is good — it explains the mechanism simply.
   - **Specific:** Include manufacturer/brand name (e.g., "Sustamine by Kyowa Hakko"), key RCT citation (e.g., "Harris 2012 RCT"), specific numbers (e.g., "2.24× plasma AUC vs free-form"), and mechanism of action.
   - **Honest about limitations:** If a form is inferior, say so clearly (e.g., "56% excreted unchanged even by IV — deacetylation is saturable at supplement doses").
5. **dosage_importance:** Present on every form (Primary=1.5 for essential vitamins/minerals, Secondary=1.0 for botanicals/antioxidants, Trace=0.5 for minor minerals)
6. **Schema fields:** cui_note when CUI is null, rxcui_note when RxCUI is null, match_rules complete (priority, match_mode, exclusions, parent_id, confidence)
7. **Alias integrity:** No cross-parent conflicts (check ALLOWED_CROSS_ALIASES whitelist in test_ingredient_quality_map_schema.py), no intra-parent duplicates, no typos
8. **Run test suite:** `python -m pytest scripts/tests/ -x -q` — ALL tests must pass

### Step 5: Batch Summary
Report a table of changes: form, old_bio, new_bio, reason (with citation).

### Step 6 (Once per audit): Parent Deduplication & Architecture Scan
Run ONCE at the start of the audit before batch work begins:

1. **Scan for duplicate parents:** Load the full IQM and check if any two parents have overlapping aliases. If aliases from parent A appear in parent B, they likely need to be merged. Example: `prebiotics` parent had forms like beta-glucan and psyllium, but `beta_glucan` and `psyllium_husk` also existed as separate top-level parents — the forms were deleted from prebiotics and left in the dedicated parents.

2. **Scan for umbrella vs. specific parent conflicts:** When an umbrella parent (like `probiotics`) has strain-specific forms AND a species-level parent (like `lactobacillus_rhamnosus`) has overlapping strains, check for score mismatches. The enricher uses alphabetical tie-breaking when priority is equal, which can silently route products to the wrong parent. Merge strain forms DOWN to the more specific parent, keeping the higher bio_score.

3. **Scan for scattered entries:** Parents added over time may be scattered at the end of the file instead of grouped logically. Check if late-index parents (indices 400+) should actually be forms under an existing parent rather than standalone entries. Example: a `phosphatidylserine_sharp_ps_gold` parent at index 490 should just be a form under the existing `phosphatidylserine` parent.

4. **Verify parent count:** Report the total parent count and compare to previous audit. Large jumps (+20) or drops (-10) should be explained.

---

## TASK 2: SUPPORTING DATA FILES AUDIT (~15% of effort)

### 2A: Banned & Recalled Ingredients
- Read `banned_recalled_ingredients.json`
- Search FDA MedWatch, Health Canada, EU RASFF for NEW recalls/bans since last audit
- Verify every entry has: id, standard_name, aliases (non-empty), legal_status_enum, clinical_risk_enum
- legal_status must be one of: banned_federal|banned_state|not_lawful_as_supplement|controlled_substance|restricted|under_review|lawful|high_risk|adulterant|contaminant_risk|wada_prohibited
- clinical_risk must be one of: critical|high|moderate|low|dose_dependent
- Add any new banned substances found in regulatory databases
- Verify aliases catch common label misspellings and brand names

### 2B: Harmful Additives
- Read `harmful_additives.json`
- Cross-reference with CSPI Chemical Cuisine database, EWG, EFSA opinions
- Verify severity levels: critical(3.0)|high(2.0)|moderate(1.0)|low(0.5)
- Check for new additives flagged by regulatory bodies since last audit
- Ensure no false positives (e.g., "natural flavors" should not be critical)

### 2C: Top Manufacturers
- Read `top_manufacturers_data.json`
- Search for new GMP violations, FDA warning letters, recalls affecting listed manufacturers
- Any manufacturer with a recent FDA warning letter should be REMOVED or flagged
- Check for brand acquisitions/mergers that change alias mappings
- Verify aliases include all known DBA names, subsidiaries, and label variations

### 2D: Clinical Studies
- Read `backed_clinical_studies.json`
- Search PubMed for new systematic reviews and RCTs published since last audit
- Add new high-quality studies (systematic_review_meta, rct_multiple)
- Verify study_type and evidence_level enums are correct
- Check that health_goals_supported and key_endpoints are populated

### 2E: Absorption Enhancers
- Read `absorption_enhancers.json`
- Verify pairings are clinically supported (e.g., piperine + curcumin, vitamin C + iron)
- Search for new clinically validated enhancer pairings
- Remove any pairings lacking RCT support

### 2F: RDA/UL Reference Values
- Read `rda_optimal_uls.json`
- Cross-reference with latest NIH ODS fact sheets (updated annually)
- Check for any updated UL values from IOM/NASEM
- Verify unit conversions match current standards

---

## TASK 3: ENRICHMENT PIPELINE INTEGRITY (~10% of effort)

### 3A: Unmapped Ingredient Analysis
- Run enrichment on a sample batch and check for unmapped active ingredients
- For each unmapped ingredient appearing 10+ times across products:
  - Determine if it belongs to an existing IQM parent (missing alias)
  - Or if it needs a new IQM parent entry
  - Add aliases or create new parents as needed

### 3B: Cross-Parent Alias Collision Scan
- Run `test_no_cross_ingredient_duplicate_aliases` and verify no new collisions
- Any intentional cross-parent aliases must be added to ALLOWED_CROSS_ALIASES in test_ingredient_quality_map_schema.py
- Fix unintentional collisions by removing the alias from the wrong parent

### 3C: Scoring Regression Check
- Run the full scoring pipeline on a known product set
- Verify scores haven't shifted unexpectedly from IQM changes
- Check that `unevaluated_records == 0` invariant holds
- Verify `ingredients_scorable + ingredients_skipped = activeIngredients + promoted_from_inactive`

### 3D: Proprietary Blend Detection
- Verify the three-tier model works correctly: full/partial/none
- Check that blend_total_mg and total_active_mg are populated in proprietary_data
- Verify penalty calculations match SCORING_ENGINE_SPEC.md v3.1

---

## TASK 4: SCHEMA & INFRASTRUCTURE (~5% of effort)

### 4A: Schema Version Consistency
- All data files should have consistent schema versions (currently 4.1.0)
- Verify schema_version fields match across all JSON files

### 4B: Test Suite Health
- Run full test suite: `python -m pytest scripts/tests/ -v`
- Any skipped tests should be investigated — are they stale or blocked?
- Any xfailed tests should be reviewed — can they be fixed?
- Check test count hasn't decreased (currently 1828+)

### 4C: Constants Freshness
- Review `scripts/constants.py` EXCLUDED_NUTRITION_FACTS list
- Search for new nutrition fact label formats (FDA label updates)
- Review EXCIPIENT_NEVER_PROMOTE for completeness
- Check EXCLUDED_LABEL_PHRASES for new generic descriptor patterns

### 4D: Scoring Config Alignment
- Verify `scripts/config/scoring_config.json` matches SCORING_ENGINE_SPEC.md
- Check all section caps, penalty coefficients, and feature gates are consistent
- Verify feature gates reflect intended production state

---

## AUDIT WORKFLOW RULES

1. **Work in batches of 3-4 IQM parents.** Larger parents (probiotics, vitamins with 10+ forms) get their own batch.
2. **Always launch PubMed research BEFORE making changes.** Never correct a bio_score based on memory — get the citation first.
3. **Never hand-edit JSON.** Always use Python scripts: `json.load() → modify → json.dump(indent=2, ensure_ascii=False)`.
4. **Run the 8-point self-audit after every batch.** This is not optional.
5. **Run `python -m pytest scripts/tests/ -x -q` after every batch.** All tests must pass.
6. **Delete phantom forms** ("X from food", "X from collagen") that cannot appear on supplement labels. Exception: real supplement forms like "vitamin D from lichen" or "omega-3 from algae."
7. **Remove suffix aliases** ending in " supplement" — the normalizer doesn't use them.
8. **New branded forms** (Nitrosigine, Sustamine, MagTein, Quatrefolic, etc.) with distinct PK mechanisms deserve their own form entry, not just an alias on the base form.
9. **Cross-parent aliases** must be added to ALLOWED_CROSS_ALIASES whitelist if intentional.
10. **Commit after each major task** (not after each batch) with a descriptive message.

## KEY ERROR PATTERNS TO WATCH FOR

| Pattern | Example | Fix |
|---------|---------|-----|
| Intestinal absorption cited as systemic bioavailability | "L-glutamine 90-95%" (actual systemic: 25-50%) | Find isotope tracer/PK study for SYSTEMIC number |
| Score contradicts notes | NALT bio=15 but notes say "inferior to L-tyrosine" | Align score with evidence — notes are usually right |
| Phantom "from food" forms | "lysine from food" nat=True score=15 | Delete — not a supplement label form |
| Missing absorption ranges | value=0.85 but range_low=None | Add ±0.05-0.10 range based on study variance |
| Stub notes | "Supports immune function" (45 chars) | Replace with 80+ char note citing RCTs, brand, mechanism |
| Cross-listed forms | Magnesium glycinate under both magnesium AND l_glycine | Keep in primary parent only (magnesium owns it) |
| Suffix aliases | "l-glutamine supplement", "NAG supplement" | Remove — normalizer doesn't need " supplement" suffix |
| nat=False on natural organisms | Probiotics marked nat=False | Fix to nat=True, recalculate score (+3) |
| bio_score exceeds 15 | Some form with bio_score=16 or higher | Cap at 15. Max score = 18 (15 + 3 natural bonus) |
| Duplicate/scattered parents | `beta_glucan` as standalone AND as a form under `prebiotics` | Merge into one canonical parent; delete from the other |
| Umbrella vs. species score mismatch | B. bifidum bio=5 in species parent but bio=12 in umbrella `probiotics` | Merge down to species parent keeping higher bio_score |
| Vague/unverifiable notes | "May support cognitive function" | Replace with specific RCT citation or delete the claim entirely |

## FINAL DELIVERABLE

After completing all tasks, provide:
1. **IQM Audit Summary Table:** parent, forms_audited, bio_score_changes, forms_added, forms_deleted, aliases_changed
2. **Supporting Data Changes:** file, entries_added, entries_modified, entries_removed
3. **Test Results:** total_passed, total_failed, any new failures investigated
4. **Known Remaining Gaps:** unmapped ingredients, missing parents, stale data needing future attention
5. **Commit** all changes with a descriptive message

Remember: This system directly affects health decisions. Every bio_score must be backed by a human PK study. Every note must cite real research. Every alias must map correctly. Accuracy over speed, always.
```

---

## CHANGELOG

| Date | Auditor | Parents Audited | Key Changes |
|------|---------|----------------|-------------|
| 2026-02 | Claude + Sean | Vitamins A-K, Ca, P, Mg, Fe, Zn, Slippery Elm, Chromium-Glutathione, Choline-Taurine, PI-TMG, Probiotics/Prebiotics (architecture refactor), L-Glutamine through L-Ornithine | 498→508 parents, 10 species-level probiotic parents created, 37 strain forms migrated, 200+ bio_score corrections, 300+ notes rewritten with PubMed citations, 150+ suffix aliases removed, 8 phantom "from food" forms deleted, Nitrosigine form added |
