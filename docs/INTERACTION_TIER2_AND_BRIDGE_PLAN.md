# Interaction Tier 2 + RXCUI Bridge — Future Sprint Plan

**Document version:** 1.0.0
**Date:** 2026-04-26
**Status:** Documented — NOT for execution this session
**Owner:** future Claude Code session, Sean reviewing
**Cross-repo scope:** dsld_clean (pipeline) + PharmaGuide ai (Flutter)

---

## TL;DR for the next agent

The interaction architecture has **three data tiers**, but only **Tier 1 (curated pairs)** has both pipeline + Flutter integration. **Tier 2 (research_pairs from supp.ai)** is shipped in the bundled SQLite but has zero query consumers in Flutter — 21 MB of dead data on every install. This doc maps EVERY existing piece so you don't accidentally rebuild work that's already done, and lays out the missing pieces clearly.

**DO NOT START until:**
1. Phase 1 (PubMed verification + duplicate cleanup, this session) is shipped.
2. Sean explicitly authorizes Tier 2 surface work — it requires UX design (Tier 2 is informational, not safety-critical, so the visual treatment must NOT alarm).

---

## What's already shipped (do NOT rebuild)

### Pipeline side

| Concern | File(s) | Status |
|---|---|---|
| Per-product condition flagging | `scripts/data/ingredient_interaction_rules.json` (129 rules) + `scripts/enrich_supplements_v3.py:_collect_interaction_profile` | ✅ shipping |
| Curated pair interactions (Tier 1) | `scripts/data/curated_interactions/curated_interactions_v1.json` (138 entries) → `verify_interactions.py` → `build_interaction_db.py` → `interaction_db.sqlite` | ✅ shipping |
| Research pairs ingestion (Tier 2) | `scripts/ingest_suppai.py` → `research_pairs.json` → `interaction_db.sqlite` (30,101 rows) | ⚠️ ingested but RXCUI side empty |
| Drug-class membership | `scripts/data/drug_classes.json` (28 classes) → `drug_class_map` table | ✅ shipping |
| Drug-supplement timing rules | `scripts/data/timing_rules.json` (42 rules) | ✅ shipping (consumed by Flutter timing service) |
| Medication-induced nutrient depletion | `scripts/data/medication_depletions.json` (68 entries, schema v5.2) | ✅ shipping (consumed by Flutter depletion checker) |
| Pre-aggregated `interaction_summary` | Emitted by `enrich_supplements_v3.py` into detail blob | ✅ shipping |
| Per-product `interaction_summary_hint` | Catalog DB column `products_core.interaction_summary_hint` (JSON string) | ✅ shipping |

### Flutter side

| Concern | File(s) | Status |
|---|---|---|
| Stack nutrient aggregation (M1) | `lib/services/stack/stack_nutrient_aggregator.dart`, `stack_nutrient_models.dart`, `stack_ul_checker.dart` | ✅ shipping |
| Curated-pair lookup (M3 binding) | `lib/data/database/interaction_database.dart` + 4 lookup methods | ✅ shipping |
| Stack interaction engine (M4) | `lib/services/stack/stack_interaction_checker.dart` (3 check methods) | ✅ shipping |
| Composite safety report | `lib/services/stack/stack_safety_report.dart` | ✅ shipping |
| Product-scan warnings (M5) | `lib/features/product_detail/widgets/interaction_warnings.dart` (1204 LOC) + `_ConditionAlertBanner` + `_InteractionConditionDetails` | ✅ shipping |
| Drug-supplement timing | `lib/services/stack/timing_evaluation_service.dart` (42 rules indexed, O(N) lookups) | ✅ shipping |
| Drug-induced depletion checker | `lib/services/stack/depletion_checker.dart` | ✅ shipping |
| Depletion-add nudge UX | `lib/services/stack/medication_depletion_nudge.dart` (one-time nudge per pair) | ✅ shipping |
| Synergy detail | `lib/features/product_detail/widgets/pipeline_sections/synergy_detail_section.dart` (Sprint 27.7 FLTR-21) | ✅ shipping |
| Medication entry + RxNorm | `lib/features/medications/medication_entry_screen.dart` + `lib/services/medications/rxnorm_api_service.dart` | ✅ shipping |
| Stack safety banner | `lib/features/stack/widgets/stack_safety_banner.dart` | ✅ shipping |
| Three-layer Flutter consumption | L1: `_ConditionAlertBanner` (catalog hint) + L2: `_InteractionConditionDetails` (blob rollup) + L3: `InteractionWarningsList` (per-card detail) | ✅ shipping |
| **Drift schema for research_pairs** | `lib/data/database/tables/research_pairs_table.dart` | ⚠️ schema exists, **ZERO query consumers** |

---

## What's MISSING (this is the future-sprint scope)

### Gap 1 — `ingest_suppai.py` doesn't bridge drug CUIs to RXCUIs

**Current state** (verified via `interaction_db_output/ingest_suppai_report.json`):
```json
{ "drug_anchors": 0, "supplement_anchors": 537 }
```

The 30,101 research pairs have `cui_a` / `cui_b` populated but `rxcui_a` / `rxcui_b` are **null for every drug-side entity**. Practical impact: even if a Flutter UI tried to query research_pairs by RxNorm RXCUI (e.g. "what does PubMed say about warfarin + supplement X?"), zero rows return.

**Where to fix:** `scripts/ingest_suppai.py` — for each drug-side `ent_type: "drug"` entity, look up the CUI in UMLS, find the matching RXNORM atom, populate `rxcui_a` / `rxcui_b`. Use existing `pubmed_client.py` rate-limit pattern as reference. supp.ai's drug-side CUIs are RxNorm-derived (per their docs), so the bridge is mostly mechanical.

**Effort:** ~2-3 hours code + ~30 min API runtime (rate-limited UMLS calls).

### Gap 2 — No Flutter UI surface for Tier 2 research_pairs

**Current state:** `research_pairs_table.dart` exists in the Drift schema; nothing in `lib/services/`, `lib/features/`, or any widget queries it. The 22 MB `interaction_db.sqlite` ships with 21 MB of dead data.

**The intended UX (per `INTERACTION_DB_SPEC.md` §11.2):**
> Tier 2 — Research. Source: supp.ai. UX role: Secondary info. No severity assigned. Shown as "research available" info chip with paper count and top sentences. Does NOT block stack add or reduce scores.

**What needs to be built:**

| Layer | File | What it does |
|---|---|---|
| Service | `lib/services/stack/research_pair_lookup.dart` (NEW) | Wrapper around `db.lookupResearchPairsByCanonicalId` and `db.lookupResearchPairsByRxcui`. Returns top-N pairs by paper_count. |
| Database lookup | Extend `interaction_database.dart` with `lookupResearchPairsByCanonicalId(canonicalId)` + `lookupResearchPairsByRxcui(rxcui)` | Drift queries against `research_pairs` table |
| UI chip | `lib/features/product_detail/widgets/research_evidence_chip.dart` (NEW) | Compact "Research available — N papers" pill with neutral tone. Tap → drawer with sentences + PMID links. |
| UI drawer | `lib/features/product_detail/widgets/research_evidence_drawer.dart` (NEW) | Modal sheet listing each pair's `top_sentences[]` + `top_pmids[]` with PubMed links. |
| Integration | `lib/features/product_detail/product_detail_screen.dart` | Slot the chip below the existing `_InteractionConditionDetails` widget. Render only if `lookupResearchPairs(...)` returns non-empty. |

**UX guardrails (non-negotiable per spec):**
- Tone: neutral / informational. Never severity-coded. Never alarm.
- Always paired with disclaimer: "Research is not a recommendation."
- PMID links open external browser (no in-app rendering of medical literature).
- DO NOT count Tier 2 hits toward `StackSafetyReport.overallSeverity` — that's reserved for Tier 1 curated.

**Effort:** ~4-5 hours (2 widgets + 2 lookup methods + 1 service + integration + tests).

### Gap 3 — Decision: keep or strip research_pairs from the bundle?

Until Gap 2 is built, the 21 MB shipped to every Flutter user is **storage debt**. Three options:

| Option | Action | Pro | Con |
|---|---|---|---|
| A | Build Tier 2 surface now (Gap 1 + Gap 2) | Data finally usable | ~7 hours work + UX design needed |
| B | Strip research_pairs from `build_interaction_db.py`; keep ingest_suppai.py output as JSON-only on disk | Saves 21 MB on every binary | Have to rebuild + re-bundle when Tier 2 ships |
| C | Defer decision; keep current state | Zero work | 21 MB technical debt; supp.ai data goes more stale by the month |

**My recommendation:** **Option C until Sean greenlights Tier 2 work**, then go straight to Option A. Stripping (Option B) and rebuilding later is wasted churn. Sean has explicitly said the bridge work IS in the plan, just not this session.

---

## How everything connects (cross-repo data-flow diagram)

```
                                 PIPELINE REPO (dsld_clean)
                                 ──────────────────────────

  Source data files                           Build orchestration
  ─────────────────                           ──────────────────
  ingredient_interaction_rules.json   ──┐
  curated_interactions_v1.json        ──┤
  drug_classes.json                   ──┼──> verify_interactions.py
  timing_rules.json                   ──┤      │  ↑ NEW: PubMed check (Phase 1)
  medication_depletions.json          ──┤      ▼
  ingredient_quality_map.json         ──┤   build_interaction_db.py
  banned_recalled_ingredients.json    ──┤      │
  botanical_ingredients.json          ──┘      ▼
                                            interaction_db.sqlite
                                              │ tables: interactions, drug_class_map,
                                              │         research_pairs (DEAD), interaction_db_metadata
                                              ▼
                                          enrich_supplements_v3.py
                                              │ writes to:
                                              │   detail_blob.warnings[]
                                              │   detail_blob.warnings_profile_gated[]
                                              │   detail_blob.interaction_summary{}
                                              ▼
                                          build_final_db.py
                                              │ writes to:
                                              │   products_core.interaction_summary_hint (JSON column)
                                              │   detail_blobs/<id>.json
                                              ▼
                                          release_full.sh / batch_run_all_datasets.sh
                                              │
                                              ▼
                                          scripts/dist/ {pharmaguide_core.db, detail_blobs/, interaction_db.sqlite, manifests}
                                              │
                                              ├─ supabase sync (catalog only, NEVER interaction_db) ──> Supabase storage
                                              │
                                              └─ Flutter import_catalog_artifact.sh ──┐
                                                                                        │
                                                                                        ▼
                                  FLUTTER REPO (PharmaGuide ai)
                                  ─────────────────────────────
                                                                        assets/db/
                                                                          pharmaguide_core.db
                                                                          interaction_db.sqlite
                                                                          *_manifest.json
                                                                            │
                                                ┌───────────────────────────┴───────────────────────────┐
                                                │                                                       │
                                                ▼                                                       ▼
                                       SYSTEM A consumers                                   SYSTEM B consumers
                                       ───────────────────                                   ───────────────────
                                                                                          (interaction_db.sqlite)
                                       Tier 1 — Per-product alerts:                        ──────────────────────
                                       L1 — _ConditionAlertBanner ←─ products_core         interaction_database.dart
                                            (interaction_summary_hint JSON column)         (Drift binding, M3)
                                                                                              │ 4 lookup methods:
                                       L2 — _InteractionConditionDetails ←─ detail_blob       │   lookupByCanonicalId
                                            (interaction_summary structured rollup)            │   lookupByRxcui
                                                                                              │   lookupByDrugClass
                                       L3 — InteractionWarningsList ←─ detail_blob             │   lookupPair
                                            (warnings[] + warnings_profile_gated[])
                                                                                          ▼
                                       Plus shipping today:                              stack_interaction_checker.dart (M4)
                                          timing_evaluation_service.dart (42 rules)         │ 3 check methods:
                                          depletion_checker.dart (med-induced depletion)    │   checkSupplementPairInteractions
                                          medication_depletion_nudge.dart (one-time UX)     │   checkMedicationInteractions
                                          stack_nutrient_aggregator.dart (M1)               │   checkMedicationPairInteractions
                                          stack_ul_checker.dart (M1 ULs)                  ▼
                                          synergy_detail_section.dart (FLTR-21)        stack_safety_report.dart (composite)
                                          stack_safety_banner.dart                          │
                                                                                          ▼
                                                                                       UI: stack screen, product detail screen

                                                                                       Tier 2 — Research evidence:
                                                                                       ⚠️ NOT IMPLEMENTED. research_pairs
                                                                                          table exists in Drift schema but
                                                                                          NO consumer service / widget /
                                                                                          screen reads it. 21 MB shipped
                                                                                          dead per binary. See Gap 2 above.
```

---

## Why Tier 2 will eventually ship (don't strip the data prematurely)

The roadmap calls for a "research available" UX surface in product detail because:

1. **User trust:** when a curated rule fires, users sometimes ask "what does the literature actually say?" The Tier 2 surface answers that without inflating severity.
2. **Differentiation:** competitors typically show only marketing claims. PharmaGuide showing "47 papers, 3 human studies, recent abstract: …" is concrete clinical-grade signal.
3. **Editorial gap:** Tier 1 (curated) has 138 entries; supp.ai indexed 30,101 supplement-relevant pairs. Tier 1 cannot keep up with literature alone — Tier 2 is the breadth complement to Tier 1's depth.

When Tier 2 ships, the dependency chain is:
1. `ingest_suppai.py` populates RXCUI bridge (Gap 1)
2. `interaction_database.dart` adds two `lookupResearchPairs*` Drift methods
3. `research_pair_lookup.dart` service wraps them
4. Two new widgets render the surface
5. Product detail screen integrates below `_InteractionConditionDetails`

All five steps are sequential — no parallelism. Plan for one focused 2-day sprint when prioritized.

---

## Anti-patterns to avoid (what previous agents got wrong)

1. **DON'T re-build the depletion checker.** It exists. `depletion_checker.dart` + `medication_depletion_nudge.dart` already handle the metformin → B12 nudge pattern. If you need to extend (more depletion sources, finer-grained adequacy thresholds), edit those files; don't fork.

2. **DON'T add Tier 2 severity weighting.** Per `INTERACTION_DB_SPEC.md` §11.2, supp.ai pairs do NOT get severities. They are research evidence, not clinical guidance. Adding severity violates the architectural separation that keeps the system clinically defensible.

3. **DON'T sync interaction_db.sqlite to Supabase.** It's bundled-only. The build-time grep test enforces this; don't bypass.

4. **DON'T add a new `condition_id` to the taxonomy** without updating `clinical_risk_taxonomy.json` and Flutter's `schema_ids.dart` in lockstep. They must agree.

5. **DON'T author rules per-condition.** SOP says one rule per ingredient, all conditions + drug classes inside. See `scripts/INTERACTION_RULE_AUTHORING_SOP.md`.

6. **DON'T edit research_pairs.json by hand.** It's regenerated from supp.ai via `ingest_suppai.py`. Manual edits get clobbered.

---

## Acceptance criteria when Tier 2 ships

| Gate | Test |
|---|---|
| RXCUI bridge | `ingest_suppai_report.json: drug_anchors > 0` (target: matching the supp.ai dump's drug entity count) |
| Lookup methods | `interaction_database.dart` has `lookupResearchPairsByCanonicalId(...)` + `lookupResearchPairsByRxcui(...)` with unit tests |
| UX guardrails | Visual review confirms neutral tone, no severity coding, "Research is not a recommendation" disclaimer present |
| Tests | `flutter test` includes ≥10 widget tests for the new chip + drawer; `pytest` includes ingest tests with RXCUI bridge mock |
| Bundle size | interaction_db.sqlite size doesn't grow significantly (compression should offset RXCUI column adds; if it grows >5 MB, investigate) |
| Performance | Tier 2 lookup per product detail open: < 50 ms on mid-tier device (research_pairs has indexes on cui_a, cui_b, rxcui_a, rxcui_b — verify they work) |

---

## Pointers

- `docs/INTERACTION_DB_SPEC.md` v2.2.0 — full architecture (Tier 1 + Tier 2 split, §11.2)
- `scripts/INTERACTION_RULE_AUTHORING_SOP.md` — System A rule authoring contract
- `scripts/PROMPT_ADD_INTERACTION_RULES.md` — full agent prompt template for new rules
- `docs/INTERACTION_RULE_GAP_AUDIT_2026-04-26.md` — Pregnancy + diabetes gap list (this session)
- `lib/services/stack/stack_safety_report.dart` — start here when extending Flutter safety logic
- `INTERACTION_DB_SPEC.md` §6.2 (verifier checks) — read before adding Phase 1 PubMed check
