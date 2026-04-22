# Sprint E1 — Release Checkpoint (Pre-E1.5)

**Status:** READY for user to execute pipeline rerun
**Date:** 2026-04-22
**Previous release:** `v2026.04.21.164306` (Supabase) / `v2026.04.21.224445` (local dist pre-E1)
**New release label:** `v2026.04.28.E1` (or similar, whatever the user assigns)

Per external-dev guidance: Claude **does not run the pipeline**. This doc is the playbook the user runs in their terminal.

## 1. Release identity

| | Value |
|---|---|
| Previous Supabase version | `v2026.04.21.164306` |
| Previous local dist | `v2026.04.21.224445` (scoring 3.4.0, schema 1.4.0) |
| Product count (pre-E1) | 8,287 |
| Proposed new label | `v2026.04.28.E1` or current-date variant |

## 2. Pre-run sanity (verified)

All config flags checked — E1 features enabled, no debug/test gates:

| Flag | Value |
|---|---|
| `section_A_ingredient_quality.probiotic_cfu_adequacy.enabled` | ✅ `true` |
| `section_A_ingredient_quality.enzyme_recognition.enabled` | ✅ `true` |
| `section_A_ingredient_quality.omega3_dose_bonus.fish_oil_parent_mass_fallback.enabled` | ✅ `true` |
| `_calibration.shadow_mode = true` | ⚠️ dormant — zero code references, no runtime effect |
| Debug / test_mode / dry_run flags | 0 found |

## 3. Consumer-compat audit

### Supabase

SQL audit of `information_schema.columns` + `routines` confirms **no consumer column, function, or view expects singular `condition_id` / `drug_class_id`**. Supabase storage blobs are opaque JSON, so the shape migration is invisible to DB-layer consumers.

### Flutter

**Found and fixed:** `lib/features/product_detail/widgets/interaction_warnings.dart` line 229-230 was reading `json['condition_id']` / `json['drug_class_id']` (singular). Fixed in Flutter repo commit `3ebc6b3` — parser now reads plural arrays with singular fallback for cached pre-migration blobs.

## 4. Expected shadow-diff (mental model BEFORE running)

### Expected deltas (OK to see)

- `decision_highlights.danger` — NEW list on products with banned/recalled/high-risk (E1.1.1)
- `banned_substance_detail` — NEW top-level dict on banned products (E1.1.4)
- `ingredients[].display_label` — NEW (E1.2.2.a)
- `ingredients[].display_dose_label` — NEW (E1.2.2.b)
- `ingredients[].standardization_note` — NEW (E1.2.2.c, null when no claim)
- `ingredients[].display_badge` — NEW (E1.2.2.d)
- `ingredients[].adequacy_tier` / `clinical_support_level` — NEW (E1.3.2.a, null unless probiotic)
- `ingredients[].cfu_confidence` / `dose_basis` / `ui_copy_hint` — NEW (E1.3.2.b)
- `raw_inactives_count` / `raw_actives_count` — NEW ints (E1.2.4 / E1.2.5)
- `ingredients_dropped_reasons[]` — NEW list from controlled enum (E1.2.5)
- `warnings[].condition_ids` / `drug_class_ids` — NEW plural arrays (E1.4.1)
- `warnings[].condition_id` / `drug_class_id` — REMOVED (E1.4.1)
- Warning counts — DOWN on multi-warn products (E1.2.3 dedup)
- Section A score — UP on: probiotics (E1.3.2.c), fish oil (E1.3.3), enzyme products (E1.3.4), Vit E (E1.3.1)

### NOT expected (investigate if seen)

- Ingredient list changes (count shifts beyond reason-code explanations)
- Display labels regressing to bare canonical
- Warning CONTENT differences (as opposed to dedup count or shape)
- Inactive ingredient drops
- Section B/C/D score changes outside probiotic/omega3/enzyme uplift paths

## 5. Backlog flags (accepted into release)

These are under-credit / coverage issues, NOT misleading outputs:

1. **Sacro-B strain alias** — S. boulardii CNCM I-745 not matched in `clinically_relevant_strains.json`. Product shows conservative `no_data` badge instead of `well_dosed`. **Under-credit, safe.** Post-release: add CNCM I-745 alias (Dr Pham).
2. **Fish-oil parent-name whitelist** — Spring Valley 26884 parent row isn't named exactly "Fish Oil" / "Krill Oil" so fallback doesn't trigger. Stays at pre-E1 score. **Under-credit, safe.** Post-release: widen whitelist or add regex matcher.
3. **Thorne Multi-Vitamin Elite 245269 at 23.58/25** — very high score for a premium multi-vit. Eyeball verified the deltas trace to core quality signals only, not inflated by E1.3 additions. **Accepted as genuine.**

## 6. Release playbook — what the user runs

```bash
# 1. From dsld_clean repo root
cd /Users/seancheick/Downloads/dsld_clean

# 2. Full pipeline rerun (all 20 brands)
bash scripts/rebuild_dashboard_snapshot.sh
# OR per-brand via run_pipeline.py orchestrator if that's the current pattern

# 3. Scope report + shadow-diff vs current dist
python3 scripts/reports/label_fidelity_scope_report.py \
    --blobs scripts/dist/detail_blobs/ \
    --out reports/ \
    --prefix e1_release_$(date +%Y%m%d)

# 4. Canary diff check (9 canaries should match reports/canary_rebuild/ from sprint)
for id in 35491 306237 246324 1002 19067 1036 176872 266975 19055; do
  diff <(jq -S . reports/canary_rebuild/$id.json) \
       <(jq -S . scripts/dist/detail_blobs/$id.json) \
    | head -5
done

# 5. If shadow-diff clean, sync to Supabase
python3 scripts/sync_to_supabase.py scripts/dist --dry-run  # preview
python3 scripts/sync_to_supabase.py scripts/dist            # real sync

# 6. Flip is_current flag on Supabase (via sync tool or SQL RPC)
# Keep v2026.04.21.164306 intact for ≥ 7-day rollback window per sprint §10

# 7. Flutter bundle
# Bundle new assets/db/pharmaguide_core.db into Flutter repo
# Merge Sprint 27.7 defensive-layer patches alongside

# 8. Release ledger entry
# Append to docs/RELEASES.md:
#   - version
#   - date
#   - contents (E1.0 through E1.4 summary)
#   - affected product counts
#   - backlog carried forward (3 items above)
```

## 7. Rollback

If anything regresses post-release:

```bash
python3 scripts/sync_to_supabase.py --force v2026.04.21.164306
```

Flutter ships previous bundled DB from git history (tag the current bundle commit before swapping).

## 8. Claude-side summary of commits shipped

24+ commits across `dsld_clean` + `PharmaGuide ai` (Flutter) repos. Full suite at 4907 passed / 32 skipped / 0 failed. Every Sprint E1 DoD canary met:

- 35491 Plantizyme: Section A 0.0 → 2.5 ✓
- 266975 Nature Made Vit E 400 IU: Section A 0.0 → 7.0 ✓
- 19055 Spring Valley Fish Oil 1290 mg: Section A 0.0 → 1.0 ✓
- 19067 Nature Made Probiotic: Section A 18.0 → 20.0 ✓
- 246324 VitaFusion CBD: `banned_substance_detail` populated ✓

## Go/no-go

✅ All checkpoint items green. User can proceed with E1.5.1 rerun.
