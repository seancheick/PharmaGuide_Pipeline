# SP-2 Adoption Inventory

**Date:** 2026-05-21
**Scope:** every consumer of `supplement_type`, `primary_category`,
`category_breakdown`, or product-name heuristics for class/module decisions
in v4 routing, scoring, gates, confidence, and final export.

**Source-of-truth contract (per `docs/plans/2026-05-20-pipeline-stability-vocab-expansion-design.md`):**
1. `enrich` computes `supplement_taxonomy` once.
2. `score`, v4 shadow scoring, `build_final_db` consume taxonomy.
3. Legacy fields only as fallback when taxonomy is absent (old batches).
4. Physical-fact overrides (e.g. disclosed EPA/DHA canonical) allowed only when
   clinically necessary and tested.

## Verdict legend

- ✅ **COMPLIANT** — already taxonomy-first or non-routing.
- 🔄 **MIGRATE** — should switch to taxonomy.
- 🟡 **LEGACY-FALLBACK** — explicit fallback for old enriched batches.
- 🟢 **PHYSICAL-FACT** — overrides taxonomy via canonical-ID panel signal.
- 📝 **NON-ROUTING** — docstring / SQL column / audit label / string constant.

## v4 surface

| File:Line | Site | Reads | Verdict | Action |
|---|---|---|---|---|
| `scoring_v4/router.py:181-182` | `_is_omega_class` primary_category check | `primary_category` | 🟢 PHYSICAL-FACT | keep — enricher canonicalizes omega-3 / fish_oil primary_category from panel composition |
| `scoring_v4/router.py:255-262` | `_read_legacy_supp_type` helper | `supplement_type.type` | 🟡 LEGACY-FALLBACK | keep — used only for pre-2026-05-20 batches |
| `scoring_v4/router.py:334-335` | Priority 5 multivitamin fallback | `supplement_type.type`, `primary_category` | 🟡 LEGACY-FALLBACK | keep — gated by `if not primary_type:` |
| `scoring_v4/router.py:663` | Themed multivitamin broad-panel fallback | `supplement_type.type` | 🟡 LEGACY-FALLBACK | keep — only fires when legacy type is multivitamin AND the physical panel has ≥8 positive rows, ≥5 multi nutrients, and ≥3 nutrient groups |
| `scoring_v4/confidence.py:246-252` | `supplement_type_low_confidence` driver | `supplement_type.confidence` | 🔄 MIGRATE (ADOPT-1) | Add `taxonomy.classification_confidence` driver; legacy as fallback |
| `scoring_v4/modules/generic_helpers.py:200-209` | `supp_type_of()` helper | `supplement_type.type` | 🔄 MIGRATE (ADOPT-2) | Add `primary_type_of()` companion helper. Do NOT remove `supp_type_of()` — callers migrate progressively |
| `scoring_v4/modules/generic_trust.py:185-202` | `_is_omega_like` marine cert gate | `supplement_type.type == "specialty"` | 🔄 MIGRATE (ADOPT-3) | Read `primary_type == "omega_3"` first. Keep ingredient-text fallback (existing, fine) |
| `scoring_v4/modules/generic_transparency.py:404-439` | `_b5_class_for_product` parallel classifier | `supplement_type.type`, `primary_category`, name regex | 🔄 **MIGRATE (ADOPT-4, CRITICAL)** | **Parallel classifier — duplicates router. Delegate to `router.class_for_product`.** This is Sean's central constraint ("Do not create a parallel classifier") |
| `scoring_v4/modules/__init__.py:7` | Docstring | — | 📝 NON-ROUTING | none |
| `scoring_v4/modules/probiotic.py:1,197` | Docstrings | — | 📝 NON-ROUTING | none |

## Shadow scorer surface

| File:Line | Site | Reads | Verdict |
|---|---|---|---|
| `score_supplements_v4_shadow.py:63,176` | Imports + calls `router.class_for_product` | (delegates) | ✅ COMPLIANT |

## v3 score_supplements surface (out of SP-2 v4 scope but inventoried)

| File:Line | Site | Reads | Verdict | Notes |
|---|---|---|---|---|
| `score_supplements.py:480-501` | `_classify_supplement_type` | taxonomy first, legacy fallback | ✅ COMPLIANT | already migrated |
| `score_supplements.py:1343-1355` | Probiotic strict-gate inputs | `supplement_type.type`, `active_count` | 🟡 LEGACY-FALLBACK | gate diagnostic; legacy active_count is correct here. Could optionally read `taxonomy.quantified_active_count` for consistency |
| `score_supplements.py:1395-1405` | Probiotic dominant-formula heuristic | `supplement_type.active_count` | 🟡 LEGACY-FALLBACK | same as above |
| `score_supplements.py:1494` | `"reason": "supplement_type_probiotic"` string | — | 📝 NON-ROUTING | audit-trail label |
| `score_supplements.py:2384-2452` | `_b5_class_for_product` v3 version | `supplement_type.type`, `primary_category`, name regex | 🔄 MIGRATE (deferred to SP-2.x) | **Same parallel-classifier pattern as v4 ADOPT-4.** v3 scope; recommend follow-up patch after v4 ADOPT-4 lands |
| `score_supplements.py:2662` | Calls `_b5_class_for_product` | — | (consumer) | inherits ADOPT-4 v3 follow-up |
| `score_supplements.py:3911-3925` | Percentile-category derivation | `supplement_type.category`, `subtype`, `type`, `product_category`, `category`, `primary_category` | 🔄 MIGRATE (deferred to SP-2.x) | Should prefer `taxonomy.percentile_category`. v3 scope |
| `score_supplements.py:4436-4441` | `_classify_supplement_type` call | (delegates) | ✅ COMPLIANT |

## build_final_db surface

| File:Line | Site | Reads | Verdict |
|---|---|---|---|
| `build_final_db.py:14,56` | Comments | — | 📝 NON-ROUTING |
| `build_final_db.py:438-460` | `build_supplement_type_audit` | taxonomy first, legacy as `enriched_type` field | ✅ COMPLIANT |
| `build_final_db.py:462-478` | `resolve_export_supplement_type` | taxonomy first, legacy fallback | ✅ COMPLIANT |
| `build_final_db.py:1071,1147,1222,1224` | SQL schema columns | — | 📝 NON-ROUTING (storage) |
| `build_final_db.py:2728,3559,3897` | Audit dict access | uses resolved audit | ✅ COMPLIANT |
| `build_final_db.py:4210-4301` | `categorize_product` | taxonomy `primary_type` first, legacy fallback | ✅ COMPLIANT |
| `build_final_db.py:4812` | Calls `resolve_export_supplement_type` | (delegates) | ✅ COMPLIANT |
| `build_final_db.py:4997` | Reads `categories["primary_category"]` | (consumer) | ✅ COMPLIANT |

## Summary counts

| Verdict | Count | v4-scope |
|---|---|---|
| ✅ COMPLIANT | 11 | 5 |
| 🔄 MIGRATE | 6 | 4 (ADOPT-1..4) |
| 🟡 LEGACY-FALLBACK | 6 | 4 |
| 🟢 PHYSICAL-FACT | 1 | 1 |
| 📝 NON-ROUTING | 6 | 2 |
| **Total** | **30** | **16** |

## SP-2 atomic commits (this skill, this session)

| Commit | What | File(s) | Risk |
|---|---|---|---|
| T1 | This inventory + audit script + regression test (no behavior change) | `scripts/audits/sp2_adoption/`, `scripts/tests/test_v4_taxonomy_adoption.py` | low |
| T3 | ADOPT-3 fix | `generic_trust.py` + tests | medium |
| T5 | ADOPT-1 fix | `confidence.py` + tests | low |
| T6 | ADOPT-2 fix | `generic_helpers.py` + tests | low |
| T4 | ADOPT-4 fix (kills v4 parallel classifier) | `generic_transparency.py` + tests | **high** |

## Deferred (v3 scope, separate follow-up)

- `score_supplements.py:2384-2452` `_b5_class_for_product` v3 parallel classifier
- `score_supplements.py:3911-3925` percentile-category derivation

These mirror the v4 ADOPT-4 pattern but live in v3 (shipped production). Migration
should happen AFTER the v4 ADOPT-4 lands and proves the pattern, and AFTER
running a full v3 scoring regression on real-catalog canaries.
