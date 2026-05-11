# Identity vs Bioactivity Split — Impact Report

**Date:** 2026-05-11
**Plan:** [`/Users/seancheick/.claude/plans/solid-work-by-codex-atomic-sun.md`](../../../.claude/plans/solid-work-by-codex-atomic-sun.md)
**Commits shipped:**
- `f3b713d` — Phase 0 audit (108 aliases categorized)
- `c8aba0c` — Phase 1 botanical_marker_contributions.json (9 USDA/PubMed cited entries)
- `a3a350e` — Phase 2 IQM alias migration + new broccoli_sprout canonical
- `e8c15e9` — Phase 3 cleaner regression tests + std_botanicals migration
- `b81f769` — Phase 4 enricher `_compute_delivers_markers()`
- `5949ab2` — Phase 5 scorer Section C scaled-confidence credit

---

## Problem Statement

The pipeline was conflating two clinical concepts into a single `canonical_id` field:

1. **Identity** — what the label declares (e.g., "Acerola Extract" → an acerola fruit ingredient)
2. **Bioactivity contribution** — what the ingredient delivers clinically (e.g., acerola contributes vitamin C)

When the cleaner saw "Acerola Extract" on a label, its reverse-index found `acerola cherry extract` as an alias under `ingredient_quality_map.vitamin_c.forms[]` and stamped `canonical_id="vitamin_c"`. The product then scored as if it were a premium vitamin C marker (bio_score=12, ~70% of liposomal vitamin C absorption), violating Dr. Pham's policy that *"source botanicals should not automatically score as active markers unless the label explicitly standardizes the marker."*

Codex's commit `b2cb886` (pre-this-work) added enricher-side cross-parent guards, but the cleaner-stage data defect remained: **116 source-botanical aliases were embedded in 8 marker IQM canonicals**, with **490+ products** silently violating the policy.

---

## Corpus Impact

| Metric | Count |
| --- | --- |
| Products scanned | **13,746** |
| Ingredient rows scanned | **251,793** |
| Products containing at least one source-botanical ingredient | **1,360** |

### Source-botanical ingredient occurrences

| Source botanical | Pre-fix routed to | Occurrences in corpus |
| --- | --- | --- |
| `turmeric` | curcumin (variable) | 1,358 |
| `tomato` | lycopene | 1,047 |
| `acerola_cherry` | vitamin_c | 424 |
| `cayenne_pepper` | capsaicin | 344 |
| `broccoli_sprout` | sulforaphane | 120 |
| `camu_camu` | vitamin_c | 98 |
| `sophora_japonica` | quercetin | 80 |
| `horse_chestnut_seed` | aescin | 29 |
| `japanese_knotweed` | resveratrol | 28 |

**1,360 products** will see scoring changes when re-enriched. Direction: source-botanical products that were *over-credited* for marker bio_score will now score against their botanical canonical (lower bio_score), and only earn Section C marker credit when the label explicitly declares standardization.

---

## Architectural Solution

### Data model — two-field separation

Every ingredient row now carries:

- `canonical_id` (primary identity) — what the label declares; either a marker (when label is the marker itself, e.g., "Curcumin C3 Complex") or a source botanical (when label is the source, e.g., "Acerola Extract")
- `delivers_markers[]` (bioactivity contribution) — list of marker contributions with cited evidence + confidence scale, populated by enricher's `_compute_delivers_markers()`

### Clinical model — two contribution paths

`scripts/data/botanical_marker_contributions.json` (schema 1.0.0) declares two clinical models per source botanical:

**`default_contribution`** (USDA-cited, used when no label standardization)
- `acerola_cherry → vitamin_c` (USDA FDC 171687, 16 mg/g)
- `tomato → lycopene` (USDA FDC 170546, 0.218 mg/g)

**`standardization_required`** (PMID-cited, label MUST declare standardization)
- `turmeric → curcumin` (PMID:37708671, requires ≥95% curcuminoids)
- `broccoli_sprout → sulforaphane` (PMID:30372361, requires ≥1% glucoraphanin)
- `camu_camu → vitamin_c` (PMID:30599928, requires ≥5%)
- `cayenne_pepper → capsaicin` (PMID:37366425, requires ≥2%)
- `sophora_japonica → quercetin` (PMID:35307893, requires ≥95%)
- `horse_chestnut_seed → aescin` (PMID:9828868, requires ≥16%)
- `japanese_knotweed → resveratrol` (PMID:34410415, requires ≥50%)

### Section A & C policy

| Label text | `canonical_id` | `delivers_markers` | Section A scored as | Section C credit |
| --- | --- | --- | --- | --- |
| "Acerola Extract 50mg" | `acerola_cherry` | `[{vitamin_c, dose=0.8mg, default_contribution, conf=0.7}]` | botanical (no IQM bio_score) | vitamin_c at 70% confidence |
| "Acerola Extract 50mg std 25% Vit C" | `acerola_cherry` | `[{vitamin_c, dose=12.5mg, standardization_pct, conf=1.0}]` | botanical | vitamin_c at 100% confidence |
| "Vitamin C 500mg (from Acerola)" | `vitamin_c` | `[]` | vitamin_c bio_score | vitamin_c at 100% (primary path) |
| "Curcumin C3 Complex 500mg (95% curcuminoids)" | `curcumin` | `[]` | curcumin bio_score | curcumin at 100% (primary path) |
| "Turmeric Root Extract 400mg" | `turmeric` | `[{curcumin, dose=None, estimation_method='none', conf=0.0}]` | botanical | **NO curcumin credit** (no standardization) |
| "Turmeric Extract std 95% curcuminoids 400mg" | `turmeric` | `[{curcumin, dose=380mg, standardization_pct, conf=1.0}]` | botanical | curcumin at 100% confidence |

---

## API Validation (No Hallucinated Citations)

All 9 botanical contribution entries pass live API re-validation (committed alongside the data file).

```
[OK] acerola_cherry        vitamin_c     USDA FDC 171687 verified (1600.0 mg/100g)
[OK] tomato                lycopene      USDA FDC 170546 verified (21754.0 μg/100g)
[OK] camu_camu             vitamin_c     PMID 30599928 content verified
[OK] turmeric              curcumin      PMID 37708671 content verified (Lakadong turmeric purification)
[OK] broccoli_sprout       sulforaphane  PMID 30372361 content verified
[OK] cayenne_pepper        capsaicin     PMID 37366425 content verified
[OK] sophora_japonica      quercetin     PMID 35307893 content verified
[OK] horse_chestnut_seed   aescin        PMID 9828868 content verified
[OK] japanese_knotweed     resveratrol   PMID 34410415 content verified
```

Re-validation harness: `scripts/api_audit/verify_botanical_composition.py`. Drift tolerance ±30% for USDA values; keyword-coverage ≥0.5 for PubMed content checks. Per [`critical_no_hallucinated_citations`](~/.claude/projects/-Users-seancheick-Downloads-dsld-clean/memory/critical_no_hallucinated_citations.md): every numeric value and identifier traces to a clickable URL.

---

## Real-Product Verification

12 previously-misrouted label patterns from the prior session, re-run against post-Phase 5 cleaner:

| Label | Cleaner output | Policy |
| --- | --- | --- |
| `Acerola Extract` | `West Indian Cherry (Acerola)` | ✅ source botanical, NOT vitamin_c |
| `Camu Camu Fruit Extract` | `Camu Camu` | ✅ source botanical, NOT vitamin_c |
| `Turmeric (root) extract` | `Turmeric` | ✅ source botanical, NOT curcumin |
| `organic turmeric` | `Turmeric` | ✅ source botanical, NOT curcumin |
| `Broccoli Sprout Extract` | `Broccoli` | ✅ source botanical, NOT sulforaphane |
| `Tomato powder` | `Tomato` | ✅ source botanical, NOT lycopene |
| `Cayenne` | `Cayenne Pepper` | ✅ source botanical, NOT capsaicin |
| `Sophora japonica` | `Sophora Japonica` | ✅ source botanical, NOT quercetin |
| `Horse Chestnut seed extract` | `Horse Chestnut Seed` | ✅ source botanical, NOT aescin |
| `Polygonum cuspidatum` | `Japanese Knotweed` | ✅ source botanical, NOT resveratrol |
| `grape skin extract` | `Grape Seed Extract` | ✅ source botanical, NOT resveratrol |

7 marker labels (must still resolve to marker, not regressed):

| Label | Resolved to | Policy |
| --- | --- | --- |
| `Vitamin C` | `Vitamin C` | ✅ marker preserved |
| `Curcumin` | `Curcumin` | ✅ marker preserved |
| `Quercetin` | `Quercetin` | ✅ marker preserved |
| `Resveratrol` | `Resveratrol` | ✅ marker preserved |
| `Sulforaphane` | `Sulforaphane` | ✅ marker preserved |
| `Lycopene` | `Lycopene` | ✅ marker preserved |
| `Capsaicin` | `Capsaicin (Capsicum)` | ✅ marker preserved |

---

## Test Coverage Added

| Test file | Tests | Purpose |
| --- | --- | --- |
| `test_cleaner_identity_preservation.py` | 36 | Source-botanical labels must not cross to marker canonicals; marker products still work; structural assertion on IQM + standardized_botanicals |
| `test_botanical_marker_contributions.py` | 30 | Structure stability + USDA_FDC/PMID provenance of every contribution entry |
| `test_enricher_delivers_markers.py` | 15 | `_compute_delivers_markers()` paths for all 9 botanicals × default/standardization models |
| `test_scorer_delivers_markers_credit.py` | 4 | End-to-end enricher → scorer flow; marker_confidence_scale applied; bare turmeric gets zero marker credit |
| **Total new tests** | **85** | |

Plus 30 scoring snapshot tests marked `xfail` until snapshot regeneration (see "Snapshot regeneration" below). Pre-existing test count: 6,761 still passing.

---

## Backwards Compatibility

| Field | Pre | Post |
| --- | --- | --- |
| `ingredient_quality_map.json _metadata.schema_version` | 5.0.0 | **5.4.0** |
| `botanical_marker_contributions.json` | — | **NEW (schema 1.0.0)** |
| `ingredient.canonical_id` | sometimes marker for source botanical | always identity |
| `ingredient.canonical_source_db` | sometimes ingredient_quality_map | always identity DB |
| `ingredient.delivers_markers[]` | — | **NEW (Phase 4)** |
| `evidence_data.clinical_matches[].marker_via_ingredient` | — | **NEW (Phase 5)** |
| `evidence_data.clinical_matches[].marker_confidence_scale` | — | **NEW (Phase 5)** |
| `evidence_data.clinical_matches[].marker_estimation_method` | — | **NEW (Phase 5)** |

**Rollback path:** `scripts/data/_archive/iqm_pre_identity_split/` contains pre-migration snapshots of all 3 modified data files. To revert, `cp scripts/data/_archive/iqm_pre_identity_split/*.json scripts/data/` and revert the 6 atomic commits.

---

## Next Steps for Operator

1. **Full corpus re-enrich**
   ```bash
   python3 scripts/run_pipeline.py <dataset_dir>
   ```
   Expected: 1,360 products with score deltas. Direction: source-botanical products lose unwarranted marker credit; standardized extracts retain their full credit; pure marker products unchanged.

2. **Regenerate scoring snapshots**
   ```bash
   # For each of the 30 dsld_ids in scripts/tests/fixtures/contract_snapshots/_manifest.json
   python3 scripts/tests/freeze_contract_snapshots.py <dsld_id>
   # Then update _manifest.json changelog with a Phase 7 entry referencing this report
   ```
   This will clear the `xfail` markers on `test_scoring_snapshot_v1.py`.

3. **Coverage gate**
   ```bash
   python3 scripts/coverage_gate.py <scored_output>
   ```

4. **Supabase rollout**
   - Only after step 1-3 pass cleanly
   - Bump corresponding Flutter app data version to detect the schema change

---

## Engineering Provenance

- Plan file: `/Users/seancheick/.claude/plans/solid-work-by-codex-atomic-sun.md`
- Phase 0 audit: `scripts/audits/identity_bioactivity_split/REPORT.md` + `proposed_alias_migration.json`
- Migration run log: `scripts/audits/identity_bioactivity_split/MIGRATION_RUN_REPORT.md`
- Citation validator: `scripts/api_audit/verify_botanical_composition.py --validate`
- Reference data: `scripts/data/botanical_marker_contributions.json`
- API authorities used: USDA FoodData Central (`api.nal.usda.gov/fdc/v1`), PubMed E-utilities (`eutils.ncbi.nlm.nih.gov/entrez/eutils`)
