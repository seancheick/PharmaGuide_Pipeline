# Handoff: Retire V3 scoring, finish V4, fix blend grouping, align tests

> **Historical handoff — implementation superseded 2026-07-16.** Production
> Stage 3 now uses `score_products_v4.py` and
> `scoring_v4/scored_artifact.py`; final export consumes the v4-native artifact
> directly. Do not use the runtime/path claims below as current instructions.
> The remaining deletion/test-disposition work is tracked in
> `SUPP_TYPE_CONSOLIDATION_PLAN.md` Phase 5.

**Audience:** an engineer/agent taking over the V3→V4 cutover.
**Author context:** written 2026-06-24 after verifying Codex's
`05433a3c` (pipeline) / `4874d41` (Flutter) "centralize primary active
contract" work and fixing the V3 A6 bonus (`2d90bcb7`).
**Goal (user's words):** *"fully retire v3 … what to build for v4, no more
shadow bullshit and other overloading stuff we don't need anymore,"* and
align the pytest suite to V4.

Truth priority: the **code** is the source of truth (`scripts/*.py`), then a
fresh `build_final_db.py` blob, then tests. Do not trust historical `.md`.

---

## 0. Current state (what's already true)

- **V4 is already the shipped score.** `build_final_db.py:~6632` hardcodes
  `score_model = "v4"`. `quality_score_v4_100` → `score_100_equivalent`.
  The 6-pillar breakdown (`quality_pillars_v4`) is the Flutter Score-Breakdown
  source and has **no V3 fallback** (`score_breakdown_section.dart:~70`,
  gates on `hasAllV4Pillars`). This part is DONE — do not touch.
- **V3 is still fully computed for every product ("the shadow").**
  `score_supplements.py` computes sections A–E, then V4 is *overlaid* on top
  (`build_final_db.py:~6708` `overlay_v4_scored`). Every product pays for both.
- **What still leaks V3 to users:** only the Tradeoffs "what's good / what's
  bad" — `score_bonuses` / `score_penalties` — which are built **from the V3
  section breakdown** (`build_final_db.py:~4900-5033`) and read by
  `tradeoffs_section.dart:~38-66`. **V4 emits no itemized equivalent.** This is
  the one hard blocker to full retirement.
- **Dead V3 weight in the blob (Flutter never reads it):** `section_breakdown`
  (`build_final_db.py:~4578-4672`), `audit.section_a_audit` (`~5085-5094`),
  `score_80` used only inside `decision_highlights` (`~2255-2261`).

---

## Track A — Build the V4 bonus/penalty derivation (the blocker)

This unblocks everything else. Today `score_bonuses`/`score_penalties` are V3
A/B sub-scores (A2/A5b/**A6**/B0–B8). V4 has only six pillars, each
`{score, max, reason, components}`.

**Build:** a `derive_v4_tradeoffs(quality_pillars_v4, …) -> {bonuses, penalties}`
that maps pillar components → the same `{id,label,score,detail}` shape Flutter
already consumes, so `tradeoffs_section.dart` needs no structural change.
- Source the "what's good" items from each pillar's `components` + `reason`
  (formulation → premium forms / standardized botanicals / delivery; dose →
  clinical-strength; verification → third-party/GMP; evidence → strong-evidence).
- Source "what's bad" from pillar deductions + the safety gate (banned/recalled,
  harmful additive, opaque blend, dose-over-UL, CAERS).
- **Requirements:** every item must be reconstructable from the V4 pillar that
  actually scored it (no re-deriving from V3). Items with no V4 home (A5e
  natural-source, B_hypoallergenic) are **dropped — they're not scored in V4.**
- Add `scripts/tests/test_v4_tradeoffs_derivation.py`: for a fixture product,
  assert the derived bonuses/penalties match the pillar components and contain
  **no V3 A/B codes**.

**Exit:** `build_final_db.py` builds `score_bonuses`/`score_penalties` from
`derive_v4_tradeoffs(...)`, not from `section_breakdown`.

---

## Track B — Delete the dead V3 surfaces (safe, do first)

Flutter never reads these; remove from the blob + their builders:
1. `section_breakdown` block — `build_final_db.py:~4578-4672` (+ the `blob[...]`
   assign ~4672). Confirm no audit/test consumer; redirect any to the
   `products_core` `score_*` columns or `quality_pillars_v4`.
2. `audit.section_a_audit` — `~5085-5094`.
3. `score_80` in `decision_highlights` — `~2255-2261`: switch the cutoffs to
   `quality_score_v4_100` (/100), delete the `/80` path.
4. Flutter: drop the unused `sectionBreakdown:` arg passed to
   `buildScoreBreakdownSection` in `product_detail_v2_connected.dart` (dead).

---

## Track C — Stop computing "shadow" V3 (the overloading)

Once Tracks A/B land, V3 section A–E computation is no longer needed for export.
- Make `score_product` / the section A–E path **not run** when
  `score_model == "v4"`, or delete the V3 scorer path entirely if nothing else
  depends on it. Keep ONLY what V4 + the safety gate (B0) + the derivation need.
- The B0 banned/recalled gate is **presence-based and independent** of scoring
  (`score_supplements.py:_evaluate_safety_gate`, reads
  `contaminant_data.banned_substances`) — it must keep firing regardless. Do not
  couple it to V3.
- Retire the **shadow-diff infrastructure**: `scripts/tests/shadow_diff_snapshots.py`
  and the V3/V4 shadow comparison plumbing — that's the "shadow bullshit." Verify
  nothing in CI depends on it before deleting.

---

## Track D — Blend grouping fix (scoring change — validate, do NOT rush)

Investigated on Paradise Earth "Vitamin D3 + K2" (dsld **336897**). Three
distinct root causes:

1. **Duplicate blend.** `_merge_blend_evidence` dedupe key is
   `(name, mg_bucket, nested_count)` — `enrich_supplements_v3.py:~11509-11516`.
   The same blend parsed once as a header (0 children) and once with children
   (17) gets different keys → not merged → 336897 ships two
   "Nature's C Veggie Berry Blend" (0 + 17 children).
   **Fix:** drop `nested_count` from the key (same name+weight = same blend); the
   merge already prefers the richer child payload (`~11555`).
   **⚠ BLAST RADIUS / SCORING:** `enriched["proprietary_blends"]` (the B5
   opaque-blend penalty input, `score_supplements.py:727`) **is the same
   `merged_blends`** (`enrich:11808`). Codex's scan: **~1,491 products** have
   duplicate blend names. Merging them changes B5 → re-scores ~1.5k products
   (mostly removing a spurious opaque-blend penalty → small score *up*). This is
   a correctness fix but MUST be validated: re-build, diff verdict distribution,
   regenerate scoring snapshots, eyeball a sample.

2. **Missing blends.** The cleaner sets `parentBlend="Organic Alkalizing Green
   Juice Powder"` on nested rows, but that blend is **absent from
   `proprietary_data.blends`** (only Adaptogen + 2×Nature's C present). So its
   members (Wheat Grass, Kamut, Barley Grass) can't be grouped. Trace
   `_collect_proprietary_data` / the detector + cleaning extraction
   (`enrich:~11160-11400`) to find why this blend is dropped.

3. **Loose / 0-child blends.** "Adaptogen & Stress Support Blends" exports with
   0 children (detected, no children attached). Same extraction gap as #2.

**Note — the "grasses as primary actives" are NOT a leak.** They export because
they're **wheat/barley allergen sources**, and
`_active_row_has_explicit_safety_export_signal` (`build_final_db.py:~1265-1289`)
intentionally keeps allergen-bearing rows visible (correct — don't hide
allergens). The fix is to **group** them under their blend (once #2 captures it),
keeping the allergen flag — not to drop them.

**Exit:** 336897 shows D3 + K2 + grouped blends (no duplicate, children
attached, grasses under their blend with allergen flag); verdict-distribution
diff reviewed; snapshots regenerated.

---

## Track E — Align pytest to V4 (the stale stuff)

- **~71 test files** reference V3 fields (`score_80`, `section_breakdown`,
  `score_quality_80`, A/B codes). Inventory:
  `grep -rlE "score_80|section_breakdown|score_quality_80" scripts/tests/`.
  For each: if it asserts a V3 field that Track B removes, migrate the assertion
  to the V4 pillar / `quality_score_v4_100`, or delete if obsolete.
- **Scoring snapshots:** `test_scoring_snapshot_v1.py` currently has standing
  `XFAIL/XPASS` churn ("regenerate after identity_bioactivity_split Phase 7").
  After the blend re-score (Track D) and V3 removal, regenerate via
  `freeze_contract_snapshots.py` and clear the stale xfails.
- **Shadow snapshots:** `shadow_diff_snapshots.py` — retire with Track C.
- Keep the A6 guards (`test_a6_single_nutrient_v3.py`,
  `test_v4_generic_formulation_p131.py`) — fold the V3 one into the V4 module
  once the V3 scorer is gone.

---

## Verification (every track)

- Pipeline backstop (gentle, ~17–20 min):
  `nice -n 15 python3 -m pytest scripts/tests/ -n 4 -q -p no:cacheprovider`.
  Baseline is **12,572 passed, 0 failed** on `2d90bcb7`.
- Single-product end-to-end (no full rebuild) — pattern used throughout this
  investigation: load cleaned product → `SupplementEnricherV3().enrich_product` →
  `SupplementScorer.score_product` → `build_detail_blob` → inspect. Canaries:
  336897 (blend), 204468 (BLOCKED banned still exports), a maltodextrin product.
- Audits: `db_integrity_sanity_check.py`, `audit_contract_sync.py`,
  `audit_inactive_safety.py`, `coverage_gate.py` — run against a fresh build.
- Flutter: `flutter test` (baseline 1850 passed) + `flutter analyze`.

## The rebuild

None of this ships until a full **re-clean → enrich → score → build → Supabase
sync** (~1 hr). The currently shipped blobs are the old build (336897.json still
72 actives, mtime Jun 23). Do Tracks A–E, validate, then ONE rebuild.

## Suggested order

B (delete dead V3, safe) → A (V4 derivation, unblocks) → C (kill shadow V3) →
D (blend re-score, validate) → E (test alignment) → rebuild.
