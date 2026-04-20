# Pipeline Refactor Handoff — 2026-04-20 (Phase 3 + 6 landed)

---

## Period D — Sprint D1 complete (critical verdict bugs fixed)

**State at close of D1**: All four critical verdict bugs from the deep accuracy audit are fixed and test-validated. 90 new regression tests added (Sprint D1 alone). Pre-Sprint-D1 cross-DB leaks, wrong BLOCKED verdicts, Nutrition-Facts panel leaks, and active-ingredient misclassifications are all guarded at code + data + test levels.

### D1 deliverables

- **D1.1 Amaranth plant-vs-dye disambiguation** — removed bare "amaranth" alias from banned dye entry; botanical grain now wins reverse-index resolution. `test_amaranth_disambiguation.py` (21 tests). 66 products unblock.
- **D1.2 Banned_recalled alias audit** — code-side: `_norm_for_negmatch` strips parens/trademark before negative-match substring check; data-side: expanded negative_match_terms on Green Tea Extract (High Dose) with matcha/leaf/culinary, and on Bitter Orange with orange-peel-oil/essence/flavor variants. `test_banned_recalled_strict_match.py` (22 tests). ~30 false positives resolved.
- **D1.3 Nutrition-Facts panel leak** — cleaner `_is_nutrition_fact` extended: accepts bare `Gram(s)`/`Calories` units (DSLD renders both with and without braces), filters DSLD categories {sugar, fat, complex carbohydrate, cholesterol, calories} as panel disclosures while preserving fiber/protein as real supplements. Data-side: sugar/sweetener/fat formulation additives in harmful_additives.json marked `severity_level="low"` so the scorer applies a small B1 penalty (not the full hammer). `test_nutrition_facts_extended.py` (27 tests). ~150 leaks resolved.
- **D1.4 D-Mannose + branded fiber DB routing** — `d_mannose` added to IQM (bio_score=9, Kranjcec 2014 RCT, CUI C0024742 API-verified); VitaFiber + CreaFibe added to other_ingredients.json; cross-DB overlap allowlist documents the D-Mannose multi-DB pattern (IQM + harmful_additives + standardized_botanicals). `test_d_mannose_iqm_routing.py` (20 tests). 19+ D-Mannose rows now score correctly; 8 branded-fiber rows mapped.

### Test state at D1 close

- 90 new tests added (21 + 22 + 27 + 20) — all passing
- Existing suites including IQM schema, xylitol routing, and snapshot stay green
- Full suite pending (running alongside Phase 7 pipeline)

### Remaining sprint D work

- **D2**: contract fix (is_mapped ⇒ canonical_id) + alias/DB expansion for ~833 silently-mapped rows
- **D3**: form-specificity (30,807 unspecified forms)
- **D4**: scorer dedup verification
- **D5**: full pipeline re-run + release gate

See docs/SPRINT_D_ACCURACY_100.md for the full sprint plan.

---

## Period C — Phase 0, 3, 4, 6 + cleaner raw-name hardening (prior session)

**State at close of Period C**: Phase 0, 3, 4, 6 complete and test-validated. Cleaner gains a raw-name-first reverse-index lookup so the fish-oil-vs-omega-3 class of bugs stays resolved. Full suite **4,105 tests passing, 12 skipped, 0 failed**. Shadow-run validated on **Pure_Encapsulations + CVS + Thorne** (14 snapshot products covered: 11 UNCHANGED, 3 EXPECTED, **0 UNEXPECTED**). Silybin Phytosome (16037) — the canonical Phase 3 target — scored +0.3 pts in shadow, confirming the medical-accuracy fix lands correctly.

### What was delivered

1. **Phase 0 — scoring-snapshot harness** (mandatory prerequisite).
   - `scripts/tests/fixtures/contract_snapshots/` with 30 diverse frozen products + manifest.
   - `scripts/tests/freeze_contract_snapshots.py` — CLI to re-freeze fixtures after reviewed score changes (with changelog entry).
   - `scripts/tests/test_scoring_snapshot_v1.py` — 32 tests (30 per-product + 2 meta) diffing current scored output against fixtures on every run.
   - `scripts/tests/shadow_diff_snapshots.py` — shadow-run classifier: UNCHANGED / EXPECTED / UNEXPECTED / MISSING.

2. **Phase 4 — Silybin/Milk Thistle alias audit** → no work needed. All 260 silybin-family rows across 20 brands already route to `canonical_id='milk_thistle'` at cleaner time. The bug that remained was purely enricher-side (Phase 3).

3. **Phase 3 — enricher reads `canonical_id` authoritatively**.
   - `_match_quality_map` gained `cleaner_canonical_id: Optional[str]` parameter. When supplied AND it's a top-level IQM key, it is a **hard filter** on the candidate pool (not a soft tie-breaker) so text-inferred cross-parent matches can no longer win.
   - Parent-level fallback: when the constrained pool is empty, a conservative parent-level (unspecified-form) match under the cleaner's canonical wins — never silently routes to the wrong parent.
   - Constraint propagates through `_match_multi_form` into per-form recursive matches so `forms[]="Silybin Phytosome"` can't lose to `lecithin`-parent's `phospholipid complex` alias.
   - Telemetry: result carries `cleaner_canonical_id`, `cleaner_canonical_enforced`, `cleaner_canonical_fallback` for audit.
   - Call sites wired: Pass-1 actives, Pass-2 inactive-promoted, both pass `ingredient.get('canonical_id')` only when `canonical_source_db == 'ingredient_quality_map'`.
   - `scripts/tests/test_phase3_cleaner_canonical_authority.py` — 8 regression tests (Silybin → milk_thistle, DCP → phosphorus, constrained-pool fallback, legacy preservation).

4. **Phase 6 — plant-part name inference** (branded-token + plant-part tissue fidelity).
   - `_infer_plant_part_from_name` helper in `enhanced_normalizer.py` with longest-first token list (`aerial parts` beats `aerial`) and plural normalization (`leaves` → `leaf`).
   - Called as fallback when `_parse_botanical_details(notes)` doesn't produce a structured `PlantPart:` — fixes "KSM-66 Ashwagandha root extract" from GNC/Goli where DSLD notes omit the qualifier.
   - Emits `plantPart_source: "name_inference"` when the fallback fires, preserving audit trail.
   - `scripts/tests/test_phase6_plant_part_inference.py` — 19 regression tests including false-positive guard (Rooster Comb ≠ root).

5. **Cleaner raw-name-first canonical resolution** (bonus fix surfaced during Phase 3 shadow validation).
   - `_resolve_canonical_identity(standard_name, raw_name=...)` — probes `raw_name` in the reverse index FIRST, falls back to `standard_name`.
   - Why: the cleaner's fuzzy matcher collapses "Fish Oil concentrate" to `standard_name="Omega-3 Fatty Acids"` (umbrella IQM parent). Without raw_name priority, Phase 3 then enforces the umbrella canonical (bio=8) instead of the sharper fish_oil canonical (bio=10). Raw-name-first recovers the specific parent.
   - All three call sites updated (active, inactive, inactive-fallback).
   - `scripts/tests/test_canonical_identity_raw_name_priority.py` — 8 regression tests.

### Shadow-run validation (Period C)

Re-enriched + re-scored **Pure_Encapsulations** (2121 products), **CVS** (280 products), and **Thorne** (1715 products) with Phase 3 changes in place, diffing against frozen snapshot fixtures:

| Brand  | UNCHANGED | EXPECTED (Phase 3 targets)                          | UNEXPECTED | MISSING |
|---|---|---|---|---|
| Pure   | 4 | 1 (Athletic Pure Pack phosphorus, −0.08 pts)           | 0 | 25 |
| CVS    | 2 | 1 (Spectravite Advanced, −0.5 pts)                     | 0 | 27 |
| Thorne | 5 | 1 (Silybin Phytosome / Planti-Oxidants, **+0.3 pts**)  | 0 | 24 |
| **Σ**  | **11** | **3**                                              | **0** | (union not deduped)     |

- **Thorne Silybin Phytosome 16037 +0.3 pts** — **THE canonical Phase 3 win**. Silymarin/silybin now resolves to `milk_thistle` premium form instead of collapsing into a generic or cross-parent alias. Section A1 goes 9.8 → 10.1 (+0.3), score_80 goes 51.8 → 52.1. This is the score Pure Encapsulations + Doctor's Best + Thorne users see on their phones post-Phase-7.
- **CVS Spectravite −0.5** — NOT a Phase 3 regression. Driven by Period B cleaner improvements re-running on stale data — "Cellulose" inactive now correctly resolves to `ADD_MICROCRYSTALLINE_CELLULOSE` harmful-additive canonical (B1_penalty +0.5). CORRECT score reduction reflecting actual product quality.
- **Pure Athletic Pure Pack −0.08** — caused by pre-existing "Fish Oil concentrate" → omega_3 cleaner mis-resolution that Phase 3 then enforced. Now fixed by the raw-name-first patch; will revert on next full pipeline re-run.
- **Zero UNEXPECTED drift across all 3 shadow-run brands.**

### Test state

```
4,105 passed, 12 skipped, 0 failed  (4:28)
```

Gains since start of Period C: +32 Phase 0 snapshot + 8 Phase 3 + 19 Phase 6 + 8 canonical raw-name = 67 new tests, all green. No regressions.

### What remains — PHASE 7 full pipeline + release gate is now the NEXT step

**Phase 7 execution checklist** (run in order; ~3 hours compute on 13,236 products):

1. **Pipeline re-run on all 20 brands:**
   ```bash
   python3 scripts/run_pipeline.py <dataset_dir>   # for each brand
   ```
   Or serial per-stage per-brand: `clean_dsld_data.py` → `enrich_supplements_v3.py` → `score_supplements.py`.
2. **Full test suite (baseline green at 4,105):**
   ```bash
   python3 -m pytest scripts/tests/ -q
   ```
   Snapshot tests (`test_scoring_snapshot_v1.py`) now diff the freshly-scored output against frozen fixtures for 30 products. Silybin Phytosome 16037, Pure Athletic Pure Pack 182730, CVS Spectravite 12012 are the known-expected drifts — **regenerate their fixtures only after verifying the new score is CORRECT**:
   ```bash
   python3 scripts/tests/freeze_contract_snapshots.py 16037
   python3 scripts/tests/freeze_contract_snapshots.py 182730
   python3 scripts/tests/freeze_contract_snapshots.py 12012
   ```
   Then add a changelog entry to `scripts/tests/fixtures/contract_snapshots/_manifest.json`.
3. **Release gates** (must all pass before Supabase sync):
   ```bash
   python3 scripts/enrichment_contract_validator.py <enriched_file>
   python3 scripts/coverage_gate.py <scored_file>
   python3 scripts/db_integrity_sanity_check.py --strict
   ```
4. **Cleaner fidelity smoke test + brand audit** (post-run):
   ```bash
   python3 scripts/tests/cleaner_fidelity_smoke_test.py
   python3 scripts/tests/brand_cleaner_audit.py
   ```
   Expect zero `canonical_id=null` rows with `mapped=True` (protocol rule #4). MenaQ7 dose-provenance rows (2) close on this re-run.
5. **Shadow-diff vs old scored output** (sanity check before release):
   ```bash
   python3 scripts/score_supplements.py --input-dir <new_enriched> --baseline-dir <old_scored> --impact-report
   ```
   Any score delta > 1 pt on a non-flagged product blocks release — investigate before proceeding.
6. **Final DB export:**
   ```bash
   python3 scripts/build_final_db.py <scored_input> <output>
   ```
7. Proceed to Phase 8 (Flutter asset refresh) only after all six checks pass.

**Phase 5 ("finish")** merges into Phase 7 — post-Phase-3 brand-wide audit runs as part of the release gate (step 4 above).

**Phase 6 MenaQ7 dose-provenance fix** is in code (since Period B); Phase 7 re-run will close the remaining 2 unmapped rows automatically.

**Phase 8+** (Flutter asset refresh, Supabase sync + canary, automation, FDA weekly sync, clinical evidence freshness) continue from the original roadmap.

### Known follow-ups surfaced during Period C trace review (not blockers)

1. **Enricher candidate-pool short-circuit** (performance-only, not correctness).
   `_match_quality_map` at [enrich_supplements_v3.py:5289](scripts/enrich_supplements_v3.py:5289) builds candidates across all ~600 IQM parents, THEN filters to `cleaner_iqm_canonical`. The filter is correct (hard constraint); the upstream pool build is wasted work. Short-circuiting to iterate only the target parent would cut ~30-50% off enricher runtime per scorable row. Estimated savings: 5-10 min per brand re-run. Does NOT affect score correctness. Defer until after Phase 7 validates Period C state on production data.

2. **`plantPart` data emitted but not consumed downstream.**
   The Phase 6 cleaner fix populates `plantPart` (structured from DSLD notes OR inferred from name). Enricher currently reads 0 `plantPart` references. For tissue-specific form selection (ashwagandha root ≠ leaf withanolide profile), wiring this into `_match_multi_form` would let the enricher prefer root-specific forms when cleaner tagged `plantPart="root"`. Data is ready; downstream use is the open item.

3. **`raw_category` emitted but not consumed.**
   Cleaner emits DSLD's raw category (vitamin/mineral/fatty_acid/…); enricher reads 0 references. Could cheaply disambiguate cross-alias cases (e.g., "Phosphorus" as mineral vs as fatty-acid derivative) without running the full text matcher.

4. **Normalization duplication.**
   `_normalize_text` is called 86× inside the enricher matcher. Cleaner already computed `normalized_key` per ingredient. Passing that through would trim redundant string-processing work. Cheap ops, low priority.

None of these four affects medical-grade correctness — all are optimization or incremental-fidelity opportunities to track for Period D.

### Files touched in Period C

- `scripts/enrich_supplements_v3.py` — `_match_quality_map` cleaner_canonical_id param + hard-constraint filter + parent-level fallback + telemetry; `_match_multi_form` propagation; 2 ingestion call sites.
- `scripts/enhanced_normalizer.py` — `_resolve_canonical_identity(raw_name=...)` priority; 3 call sites updated; `_infer_plant_part_from_name` helper + cleaner row-builder integration.
- `scripts/tests/fixtures/contract_snapshots/` — 30 frozen product fixtures + `_manifest.json`.
- `scripts/tests/freeze_contract_snapshots.py` (NEW)
- `scripts/tests/shadow_diff_snapshots.py` (NEW)
- `scripts/tests/test_scoring_snapshot_v1.py` (NEW, 32 tests)
- `scripts/tests/test_phase3_cleaner_canonical_authority.py` (NEW, 8 tests)
- `scripts/tests/test_phase6_plant_part_inference.py` (NEW, 19 tests)
- `scripts/tests/test_canonical_identity_raw_name_priority.py` (NEW, 8 tests)

---

# Pipeline Refactor Handoff — 2026-04-20 (updated end-of-day, Periods A+B)

**Mission:** Make the DSLD pipeline clinical-grade accurate from the raw NIH label all the way to the consumer's phone. Every byte of data that reaches a Flutter user must be traceable to an authoritative source (FDA, UMLS, PubMed, NCBI, Korean/EU regulators) and reproducible via API verification scripts. One wrong identifier or misrouted ingredient is a red flag for the entire product.

**End state (session close):**

- **99.998% canonical_id coverage** across 126,383 active ingredients in 13,236 products (20 brands)
- **18 of 20 brands at 100% coverage** (10 already 100%, + 8 additional after today's session)
- Only **2 unmapped rows remain**, both blocked on a known Phase 6 prefix bug
- **Full test suite green: 3,814 passed, 0 failed, 12 skipped**
- All schema tests (41) green; `db_integrity_sanity_check --strict` clean
- Every new identifier API-verified against UMLS / GSRS / NCBI / RxNorm

---

## Full session arc (two contiguous work periods, same day)

### Period A — Foundation (pre-compaction)

Built the cleaner→enricher contract, canonical_id resolution, coverage from ~97% → 99.26%.

### Period B — Near-100% push (post-compaction, this continuation)

Drove coverage from 99.924% → **99.998%**, fixed three session-introduced regressions, verified 7 probiotic CUIs, added 2 new API-verified botanicals. Full test suite now green.

---

## What the pipeline now does (reality as of today)

### Stage 1 — Cleaner (`enhanced_normalizer.py`)

Reads raw DSLD JSON. Emits per ingredient row:

| Field | Purpose |
|---|---|
| `canonical_id` | Parent key in one of 8 routing DBs. Authoritative — enricher trusts it. |
| `canonical_source_db` | Which DB resolved the identity |
| `label_nutrient_context` | For vitamin/mineral rows — disambiguates cross-aliases (DCP → phosphorus vs calcium) |
| `raw_category`, `ingredientGroup`, `uniiCode` | DSLD provenance preserved |
| `forms[].{category, ingredientGroup, uniiCode}` | DSLD forms[] fields no longer stripped |
| `nutritionalInfo` | Calories/Carbs/Fat/Protein/Sodium/Fiber/Cholesterol/Sugars as structured `{amount, unit}` |

**Key routing decisions baked in:**

- **Dual-context minerals** (Sodium, Chloride, Salt): row routes to `activeIngredients` only when `forms[]` names a supplement-source salt; bare "Sodium" with no forms[] is Nutrition Facts disclosure → routed to `nutritionalInfo`.
- **Rollup / summary rows** (`Total Omega-6 Fatty Acids`, `Total DPA`, `Total Turmerones`): excluded from actives even when DSLD tags them vitamin/mineral/fatty-acid.
- **Standardization markers** (`Standardized to >95% Curcuminoids`, `Supplying 8% Cordycepic Acid`, `6% Terpene Lactones`): excluded via regex — they're potency descriptors on a parent botanical, not discrete supplements.
- **Source descriptors** (`Rooster Comb Cartilage`, `Animal Proteins`, `Flavonol Glycosides`): excluded via `_BYPASS_EXCLUDE_NAMES` set.
- **Marketing-suffix fuzzy match** (`XYZ Complex`, `XYZ Formula`, `XYZ Blend`, `XYZ Matrix`): trailing suffix stripped once and retried. Eliminates need for ~40 bespoke aliases.
- **Reverse index (17k entries)** spans all 8 routing DBs. `_resolve_canonical_identity(std_name)` → `(canonical_id, source_db)` at cleaner time.

### Stage 2 — Enricher (`enrich_supplements_v3.py`)

Reads cleaner output. For every active ingredient:

1. Looks up forms against IQM / botanicals / other / harmful_additives / banned_recalled / allergens / standardized_botanicals / proprietary_blends.
2. Short-circuits `forms[]` rows that are source descriptors (`dsld_category ∈ {animal part or source, plant part, source material}` or `dsld_prefix ∈ {from, culture of, …}`) — **except** delivery technologies (MicroActive cyclodextrin, phytosome, liposome, chelate) which remain real forms even with `prefix='from'`.
3. Scores per `ingredient_quality_map` bio_score / dosage_importance / form type.
4. Applies standardized-botanical bonus via `_collect_standardized_botanicals` — scans all_product_text for `standardized to N%` + marker words, doesn't require the marker to be its own row.

**Phase 3 is NOT done yet**: the enricher currently still infers parents by text, ignoring the cleaner's `canonical_id`. This is the most important remaining step.

### Stage 3 — Scorer (`score_supplements.py`)

80-point arithmetic model (frozen naming):

- Ingredient Quality (25) — bioavailability × dosage
- Safety & Purity (30) — banned/recalled gate, allergens, UL%
- Evidence (20) — clinical backing (PMID-verified only)
- Brand Trust (5)
- Dose Adequacy (2)

Output: `score_quality_80`, `score_display_100_equivalent`, deterministic verdict precedence `BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE`.

### Stage 4 — Build → Sync → Phone

- `build_final_db.py` → Flutter-ready SQLite (`pharmaguide_core.db`)
- `sync_to_supabase.py` → production DB with `cleanup_keep=5` rollback window
- Flutter app (`/Users/seancheick/PharmaGuide ai`) loads local cache first, hydrates from Supabase on miss

---

## Coverage snapshot — Period B end

```text
Brand                      Prods  Active  Gaps    Cov%
-------------------------------------------------------
Thorne                      1715   17339     0  100.00%
Pure_Encapsulations         2121   13771     0  100.00%
Spring_Valley                443    1909     0  100.00%
CVS                          280    2219     0  100.00%
Goli                          10      61     0  100.00%
Hum                           22     244     0  100.00%
Legion                        45     445     0  100.00%
Ritual                         3      26     0  100.00%
Transparent_Labs               9      95     0  100.00%
Nutricost                    795    2451     0  100.00%
Olly                         186    1452     0  100.00%
Ora                           71     945     0  100.00%
Sports_Research              168     587     0  100.00%
Vitafusion                   285    2036     0  100.00%
Equate                       143    1666     0  100.00%
Double_Wood                  151     270     0  100.00%
Garden_of_life              1131   31642    ~2  ~99.99%
GNC                         3945   42722     0  100.00%
Nature_Made                  826    4150     0  100.00%
Doctors_Best                 887    2353     0  100.00%
-------------------------------------------------------
TOTAL                      13236  126383     2  99.998%
```

The 2 remaining rows: `from 45 mcg of menaq7(r)` and `from 45 mcg of menaq7(tm)` — both blocked on the same cleaner bug where `prefix='from'` with a branded K2 token is treated as source descriptor. Fix lives in Phase 6.

---

## What changed in Period B (this session)

### Coverage closures (94 rows closed)

**Cleaner-level exclusions (55 rows)** — rollups / standardization markers / source descriptors now filtered out properly:

- Rollup prefix override in `_is_nutrition_fact` when bypass applies
- Standardization-marker regex: `^standardized to`, `^supplying`, `^N%`, `^min N%`
- `_BYPASS_EXCLUDE_NAMES`: flavonol glycosides, terpene lactones, animal proteins, rooster comb cartilage

**IQM alias additions (39 newly mapped rows)** — all duplicate-checked, schema-verified:

| Canonical | Form | New aliases |
|---|---|---|
| `vitamin_d` | vitamin D3 from lichen | vitashine vitamin d3, vitashine d3 |
| `curcumin` | curcumin (unspecified) | curcumin and other curcuminoids |
| `phytosterols` | phytosterol esters | cardioaid, cardioaid plant sterols 95% |
| `olive_leaf` | olive leaf extract standardized | bonolive, emed-ole, emed-ole(tm) olive leaf extract |
| `diindolylmethane` | indole-3-carbinol (i3c) | indole-3 carbinol, indole 3 carbinol, l3c |
| `diindolylmethane` | diindolylmethane (dim) | diindoylmethane (OCR typo) |
| `pine_bark_extract` | pycnogenol | pycnogenol maritime pine extract |
| `vitamin_e` | tocotrienols | tocosource palm tocotrienols |
| `mct_oil` | c8-mct | c8:0 caprylic acid variants |
| `mct_oil` | c10-mct | c10:0 capric acid variants |
| `l_arginine` | l-arginine akG | AAKG release variants (immediate/sustained) |
| `citrus_bioflavonoids` | citrus bioflavonoids complex | pmf-source citrus flavones, polymethoxyflavones |
| `resveratrol` | trans-resveratrol | biovin advanced red wine extract |
| `glucosamine` | glucosamine (unspecified) | glucosamine hydrochloride potassium sulfate |
| Kanna (botanical DB) | — | zembrin (sceletium tortuosum) aerial parts extract |

### New botanical entries (API-verified identifiers)

| ID | CUI | UNII | Notes |
|---|---|---|---|
| `cynanchum_wilfordii` | C1463421 | 0YW1513318 | Korean women's-health herb. ⚠️ Adulteration risk: confused with hepatotoxic Polygonum multiflorum on US market. |
| `phlomoides_umbrosa` | C4576738 | 8J1RE3K5G5 | Formerly *Phlomis umbrosa*. Aliases include both names for back-compat. Korean "Sok-Dan" vernacular overlaps TCM Xu Duan (Dipsacus). |

### Null-CUI backfills (7 probiotics, UMLS-verified)

| IQM entry | CUI | UMLS concept |
|---|---|---|
| `lactobacillus_kefirgranum` | C1265212 | Lactobacillus kefiranofaciens subsp. kefirgranum |
| `lactobacillus_parakefir` | C1072849 | Lactobacillus parakefiri |
| `leuconostoc_mesenteroides` | C0317708 | Leuconostoc mesenteroides |
| `leuconostoc_lactis` | C0317712 | Leuconostoc lactis |
| `leuconostoc_cremoris` | C0317710 | Leuconostoc mesenteroides subsp. cremoris |
| `saccharomyces_turicensis` | C1908843 | Kazachstania turicensis (reclassified) |
| `saccharomyces_exiguus` | C1940772 | Kazachstania exigua (reclassified) |

All 7 entries now carry `cui_verified_source: "UMLS/NCBI via verify_cui.py (2026-04-20)"` for audit trail.

### Bug fixes (session-introduced regressions resolved)

1. **CoQ10 MicroActive misrouting** — `MicroActive CoQ10-cyclodextrin Complex` was on `ubiquinone softgel`; moved to `ubiquinone crystal-dispersed` (MicroActive *is* cyclodextrin tech). Plus enricher fix: delivery-tech `from` prefixes (cyclodextrin, phytosome, liposome, chelate) no longer treated as source descriptors.
2. **PreticX XOS regression** — removed redundant full-name alias that was winning exact-match over branded-token preference. Branded-token fallback now correctly returns `matched_alias='preticx'`.
3. **Bifidobacterium longum strain aliases** — `r0175` / `bi-26` deduped to strain-specific forms only; `b. longum r0175` removed from `(unspecified)` form.
4. **`lactobacillus_bulgaricus` cross-ingredient dup** — aliases removed from `probiotics` parent (now owned by dedicated canonical).
5. **`Digestive Support Blend`** — removed from BLEND_PROBIOTIC and BLEND_ENZYME (kept only on BLEND_GENERAL for non-ambiguous matching).
6. **Aliases inadvertently removed earlier** restored: `l3c`, `flaxseed oil`, `alcar`, `quercetin dihydrate`.

### Constants / rule changes

- `EXCLUDED_NUTRITION_FACTS` extended with `flavonol glycosides`, `terpene lactones`, `animal proteins`, `animal protein`, `plant proteins`
- Smoke test harness (`cleaner_fidelity_smoke_test.py`) now treats intentionally-excluded rollup rows (`total/other/typical/all other` prefix) as covered

---

## What remains — from labels to the user phone

### Phase 0 — Snapshot test harness  `(1 session, MANDATORY before Phase 3)`

Build `scripts/tests/fixtures/contract_snapshots/` with scored output for 30 diverse products. Any score drift during Phase 3 becomes a visible diff, not a user bug report.

**Products to snapshot (minimum):**

- Silybin Phytosome (PID 16037) — Phase 3 canonical bug target
- Phosphorus-containing multivitamins (182730, 12012) — Phase 3 label_nutrient_context target
- Catalyte electrolyte (64058) — Sodium/Chloride dual-context routing
- Garden of Life Vitamin Code Men (288344) — whole-food vitamins
- Pancreatin (241306) — glandular / source-descriptor
- KSM-66 Ashwagandha (245156) — branded-token + plant-part
- Thorne probiotic w/ strain claims — canonical_id on strain forms
- Pure CoQ10 MicroActive — Period B fix coverage
- Doctor's Best Curcumin C3 — standardization marker bonus flow
- CVS Spectravite, Ritual Essential — mainstream multivitamin baseline
- At least one each: single-ingredient, proprietary-blend-heavy, phytosome, glandular, fish oil, yeast-fermented, kefir synbiotic, standardized botanical, Korean herbal (Estromon), banned-recalled trigger

**New test file:** `scripts/tests/test_scoring_snapshot_v1.py` — re-run pipeline end-to-end, diff against fixture, fail on any score/verdict shift that isn't explicitly acknowledged in a changelog.

### Phase 3 — Enricher reads `canonical_id` authoritatively  `(1.5 sessions, THE big medical-accuracy step)`

Touch points in `enrich_supplements_v3.py`:

- **Ingestion (lines ~2040-2055 and ~2105-2135)** — when `ingredient['canonical_id']` is present and exists in the target DB, use it as hard-constraint `preferred_parent`. Legacy text-inference path stays gated for `canonical_id=null` rows.
- **`_match_quality_map` / `_match_multi_form`** — accept `preferred_parent` as authoritative when sourced from cleaner, not a heuristic.
- **`label_nutrient_context`** becomes secondary tie-breaker for cross-aliases that span multiple canonicals (DCP, dolomite, niacinamide ascorbate, etc.).

**Medical-accuracy bugs this fixes immediately:**

- **Silybin Phytosome** → cleaner emits `canonical_id='milk_thistle'` → enricher scores as milk thistle (currently scores as lecithin because enricher text-matches "phospholipid complex").
- **Phosphorus (from DCP)** → cleaner emits `canonical_id='phosphorus'`, `label_nutrient_context='phosphorus'` → enricher scores as phosphorus (currently scores as calcium because DCP alias exists on both).

**Shadow-run protocol:** run old + new enricher on all 20 brands, diff scored output, every score change must be explainable (Silybin/Phosphorus expected to change and be verified correct; others identical).

### Phase 4 — Silybin/Milk Thistle final alias sweep  `(0.25 session)`

Re-audit milk_thistle/silymarin aliases against GoL and Doctor's Best Silybin Phytosome labels. Any remaining unmapped variants get added pre-Phase-3 so the fix lands clean.

### Phase 5 (finish) — Close the final 2 rows + long-tail verification  `(0.5 session)`

- Fix the MenaQ7 `from` prefix bug as part of Phase 6.
- Re-run brand_cleaner_audit across all 20 brands post-Phase-3 to catch any canonical_id=null rows where mapped=True (should be zero after Phase 3).
- Verify **allergen**, **banned_recalled**, and **harmful_additives** routing hasn't regressed (these are safety-critical — blocker for release).

### Phase 6 — Branded-token + plant-part tissue fidelity  `(0.5 session)`

Two linked cleaner gaps:

1. **`from X of menaq7®/™`** (2 rows) — currently loses the MenaQ7 branded vitamin K2 identity because `prefix='from'` + numeric token routes to source-descriptor. Fix: let numeric-mcg + branded-K2 patterns pass through as delivery tech, same way we fixed MicroActive in Period B.
2. **"KSM-66 Ashwagandha root extract"** — cleaner currently collapses to `name='KSM-66'`, losing "root extract" plant-part info. Preserve qualifier suffix (root/leaf/extract/seed/bark) as `forms[]` entry or new `plantPart` field. Branded-token extraction keeps brand + generic name + part.

### Phase 7 — Full pipeline + release gate  `(1 session)`

- `run_pipeline.py` on all 20 brands with new cleaner + Phase-3 enricher.
- `build_final_db.py` → Flutter-ready SQLite.
- Gates:
  - `coverage_gate.py` quality thresholds
  - `enrichment_contract_validator.py`
  - `db_integrity_sanity_check.py --strict`
  - **All 3,814+ tests green** (currently 3,814 — should stay ≥ that)
  - `forms_differ` residual under 10
  - banned/recalled routing verified against latest FDA openFDA sync
  - cross-DB allowlist clean
  - Section-A (dose gap) report reviewed
- Shadow-diff old vs new scored output; any unexplained score change blocks release.

### Phase 8 — Flutter asset refresh  `(0.5 session)`

- Regenerate `pharmaguide_core.db` from Phase-7 output
- Regenerate `interaction_db.sqlite`
- Deploy to `/Users/seancheick/PharmaGuide ai` assets
- Smoke test Flutter app on Silybin Phytosome + Phosphorus products — scores must CHANGE and be verified correct.
- Run Flutter's 478+ tests; regression = blocker.
- **Medical-accuracy checkpoint**: user-facing score on a Silybin product must reflect the correct milk-thistle bioactivity, not lecithin. If it doesn't, Phase 3 shipped wrong.

### Phase 9 — Supabase sync + canary  `(0.5 session + monitoring window)`

- `sync_to_supabase.py --dry-run` → review diff size; any mass score changes trigger a pause.
- Full sync with `cleanup_keep=5`.
- Canary: monitor Flutter analytics + safety alerts for 48h. Score-distribution shift is normal for Silybin/Phosphorus products; flag anything else.
- Document release in next `docs/HANDOFF_<date>.md`.

### Phase 10 — Automated brand ingest CLI  `(1 session + iterations)`

`python3 scripts/ingest_brand.py <Brand>`:

1. Download staging from DSLD.
2. Run cleaner; emit gap report.
3. Classify gaps (IQM alias missing / botanical missing / blend header / rollup / source descriptor / typo).
4. **Halt for human review** on any new canonical (protocol rule #2 — no auto-adding identifiers).
5. Post-approval: re-clean, score, generate brand-level diff report.
6. Commit with audit trail.

### Phase 11 (new) — FDA weekly sync automation  `(0.25 session setup, ongoing)`

`scripts/run_fda_sync.sh` already exists. Schedule it weekly (GitHub Actions or cron). Every sync:

- Updates `banned_recalled_ingredients.json` with new openFDA recalls.
- Runs `audit_banned_recalled_accuracy.py` release gate.
- Auto-opens PR on any new recall; humans approve before merge.

### Phase 12 (new) — Clinical evidence freshness  `(0.5 session quarterly)`

- Re-run `verify_all_citations_content.py` against all PMID citations in `backed_clinical_studies.json`, `medication_depletions.json`, `curated_interactions.json`.
- Any citation where the paper title no longer mentions the claimed topic (evidence drift) → flag for review.
- Any new PMIDs published on active canonicals → surface for potential evidence-strength upgrade.

---

## Key files touched (cumulative, both periods)

### Cleaner
- `scripts/enhanced_normalizer.py`
  - `_build_canonical_id_reverse_index` (NEW, ~80 lines)
  - `_resolve_canonical_identity` (NEW)
  - `_is_nutrition_fact` — new `dsld_category`, `has_forms` params; dual-context-mineral routing; rollup-prefix override; standardization-marker regex; `_BYPASS_EXCLUDE_NAMES`
  - `_perform_ingredient_mapping` — generic marketing-suffix fallback
  - 3 row-build sites emit canonical_id / canonical_source_db / label_nutrient_context / raw_category / preserved forms[] DSLD fields

### Enricher
- `scripts/enrich_supplements_v3.py`
  - `_build_form_info_from_cleaned` — carries `dsld_category`, `dsld_prefix`, `dsld_ingredient_group`, `dsld_unii_code`
  - `_match_multi_form` — source-descriptor short-circuit, now with delivery-tech exemption (`_should_keep_from_prefixed_form_as_actual`)
  - `_is_source_material_descriptor_for_fallback_audit` — expanded term lists
  - *(Phase 3 not yet done: canonical_id-authoritative ingestion)*

### Constants
- `scripts/constants.py`
  - `EXCLUDED_NUTRITION_FACTS` — probiotic culture totals, fatty-acid totals, typical-composition rollups, `flavonol glycosides`, `terpene lactones`, `animal proteins/protein`, `plant proteins`

### Data
- `scripts/data/ingredient_quality_map.json` — 588 → 622 entries, ~60 alias additions, 16 cross-ingredient/within-ingredient collisions resolved, 7 probiotic CUIs backfilled
- `scripts/data/botanical_ingredients.json` — 433 → 453 entries (+2 in Period B: cynanchum, phlomoides; +Zembrin alias on Kanna)
- `scripts/data/other_ingredients.json` — +5 entries
- `scripts/data/proprietary_blends.json` — ~40 new blend terms, `Digestive Support Blend` dedup
- `scripts/data/ingredient_interaction_rules.json` — rule #117 silymarin→milk_thistle
- `scripts/data/harmful_additives.json` — MCC aliases
- `scripts/data/fda_unii_cache.json` — rebuilt 172,558 substances

### Tests
- `scripts/tests/test_form_fallback_audit_source_descriptors.py` (NEW, 78 tests)
- `scripts/tests/test_form_fallback_audit_noise.py` — updated
- `scripts/tests/test_ingredient_quality_map_schema.py` — ALLOWED_CROSS_ALIASES extended
- `scripts/tests/cleaner_fidelity_smoke_test.py` (NEW) — 20-product smoke harness (updated Period B for rollup exclusions)
- `scripts/tests/brand_cleaner_audit.py` (NEW) — brand-scale audit

---

## Non-negotiable protocol rules (carry forward)

1. **IQM = scorable active ingredients only.** Botanicals → `botanical_ingredients.json`. Inactive → `other_ingredients.json`. Penalized → `harmful_additives.json`. Banned → `banned_recalled_ingredients.json`. Blend headers → `proprietary_blends.json`. Allergens → `allergens.json`. Standardized extracts with marker thresholds → `standardized_botanicals.json`.

2. **Every identifier MUST be API-verified.** Run `verify_cui.py`, `verify_unii.py`, `verify_pubchem.py`, `verify_interactions.py`, `verify_pubmed_references.py`. Never guess — AI hallucinates valid-looking identifiers for completely different compounds. Period B caught the Chloride CUI hallucination; do not regress.

3. **Duplicate-check before adding any new canonical.** Iterate all 8 routing DBs. This session alone caught 12+ would-be duplicates (bamboo, schizophyllan, zinc_carnosine, lychee, lactium, 6 whole-food mis-routes, 6 botanical mis-routes).

4. **`mapped=True` must imply a resolved `canonical_id`.** If the reverse index returns None, either the alias is missing, the entry needs creating, or the row shouldn't have been classified as mapped. Zero tolerance for "silently mapped" rows.

5. **Root-cause over symptom.** If a label pattern like "XYZ Complex" isn't matching, don't add 50 aliases — fix the fuzzy matcher once. Period A replaced ~40 would-be aliases with one code change. Period B replaced ~50 rollup aliases with a regex override.

6. **Schema tests are load-bearing.** `test_ingredient_quality_map_schema.py` catches cross-ingredient duplicate aliases, within-ingredient collisions, category/category_enum mismatches, null rxcui without note, form-name/UNII duplicates. Run after every batch.

7. **`db_integrity_sanity_check.py --strict` after every data change.** Catches orphan canonical_id references in interaction rules, synergy clusters, clinical studies.

8. **Supplement Facts vs Nutrition Facts.** Supplement minerals need `forms[]` to indicate real supplementation (Sodium as Sodium Chloride = active; bare Sodium = Nutrition Facts disclosure → nutritionalInfo only).

9. **Blend members without individual dose aren't scored individually.** `_has_usable_individual_dose()` in scorer. But they still need canonical_id for safety/allergen/cluster/synergy purposes.

10. **No evidence-overstatement.** Every mechanism / severity / clinical claim must not exceed what its cited source proves. Use `verify_all_citations_content.py` before any release — PMID existence alone is not content verification.

11. **Clinical tool = zero tolerance for corrupt data.** One bad entry is a red flag for the whole product. `PharmaGuide` is medical-grade — one wrong CUI, one wrong PMID, one wrong identifier can mislead someone taking a real medication.

---

## Recommended order for the next agent

1. ~~**Phase 0** (1 session) — snapshot harness.~~ **DONE in Period C**
2. ~~**Phase 4** (0.25 session) — Silybin final alias sweep.~~ **DONE in Period C (no-op: cleaner was already correct)**
3. ~~**Phase 3** (1.5 sessions) — enricher canonical_id authoritative.~~ **DONE in Period C**
4. ~~**Phase 6** cleaner plant-part fidelity~~ **DONE in Period C**
5. **Phase 7** (1 session compute-heavy) — full pipeline + release gate. **NOW THE TOP PRIORITY.** Re-runs cleaner + enricher + scorer on all 20 brands so the Phase 3 / raw-name / Phase 6 fixes reach scored output, then runs release gates. Phase 5 ("finish") merges into this step.
6. **Phase 8** (0.5 session) — Flutter asset refresh + on-device verification.
7. **Phase 9** (0.5 session + 48h canary) — Supabase sync + monitoring.
8. **Phase 10** (1 session + iterations) — ingest CLI.
9. **Phase 11** (0.25 session setup) — FDA weekly sync automation.
10. **Phase 12** (0.5 session quarterly) — evidence-freshness audit.

**Total remaining: ~4 focused sessions (1 compute-heavy Phase 7 + 3 UX/ops) to phone-ready release with Silybin and Phosphorus scores correct on the user's device.**

---

## Session trail of evidence (Periods A + B + C)

- `scripts/tests/cleaner_fidelity_smoke_test.py` — 0 coverage issues, 4 pre-existing proprietary-blend canonical_id gaps
- `scripts/tests/brand_cleaner_audit.py` — runs per-brand audit
- `scripts/tests/test_scoring_snapshot_v1.py` (Period C, NEW) — 30 frozen products with diff-based regression guard
- `scripts/tests/shadow_diff_snapshots.py` (Period C, NEW) — shadow-run UNCHANGED/EXPECTED/UNEXPECTED classifier
- 41 schema tests green; **4,105 pytest tests green (12 skipped, 0 failed)** after Period C
- `db_integrity_sanity_check --strict` clean
- All new CUIs / UNIIs verifiable via `scripts/api_audit/verify_cui.py` + `verify_unii.py`
- Phase 3 unit tests validate Silybin + DCP hard-constraint on synthetic input; shadow validation on Pure + CVS confirms 0 UNEXPECTED drift; Thorne shadow run pending at close of Period C

Reproducibility: every API-derived identifier can be re-verified by re-running the corresponding `verify_*.py` command against the source — the audit chain is live, not frozen-in-time.

---

*End of handoff. Next agent: start with Phase 7 (full pipeline + release gate).*
