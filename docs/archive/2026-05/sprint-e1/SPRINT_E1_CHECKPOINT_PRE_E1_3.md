# Sprint E1 — Pre-E1.3 Checkpoint

**Date:** 2026-04-22
**Status:** ✅ CLEAN — proceed to E1.3.1
**Golden baseline:** `reports/baseline_pre_e1_3/` (7 canary blobs, frozen)

## Mindset shift

Phase E1.2 rule was: **"Don't lose data."** (representation correctness)
Phase E1.3 rule is: **"Don't over-interpret data."** (interpretation + scoring)

E1.3 changes scoring behavior — higher silent-regression risk than E1.2.

## E1.3 tasks ahead + risk annotation

| Task | Scope | Risk |
|---|---|---|
| E1.3.1 | `is_additive` classifier — source-section + dose-aware | Low-medium (logic correction) |
| E1.3.2 | Probiotic CFU-based A1 adequacy path + confidence hybrid | **HIGHEST** (introduces clinical_support_level, cfu_confidence, dose_basis, ui_copy_hint) |
| E1.3.3 | Fish oil EPA/DHA nested-NP propagation | Medium (data-shape cascade, similar to E1.2.1) |
| E1.3.4 | Enzyme recognition credit | Low (gated by config flag) |
| E1.3.5 | Plant-part preservation closeout | Low (test-coverage closeout only) |

## Invariants to preserve through E1.3

1. **No ingredient loss** — `raw_actives_count` vs `len(ingredients)` gap must stay ≤ current level; `raw_inactives_count` preserved.
2. **No label mutation** — pre-flight invariant `test_ingredient_existing_fields_are_byte_identical` must stay at 35/35.
3. **No inference leakage** — `display_badge` activates ONLY when scorer emits a recognized `adequacy_tier`. Dose label never computes from blend totals. `standardization_note` regex stays tight.
4. **Zero `PARSE_ERROR` sentinels** in `ingredients_dropped_reasons`.

## Canary expected badge transitions (post-E1.3)

Currently all 7 canaries badge as `no_data` (adapter-correct — scorer silent).

E1.3.2 will make probiotic strains carry `adequacy_tier`, which will activate badges:

- **19067 Nature Made probiotic** — badge should transition `no_data` → `well_dosed` (10 billion CFU L. plantarum 299v is adequate per Dr Pham's thresholds)

All other canaries should stay `no_data` — they are not probiotics and their other ingredients don't get adequacy signals in E1.3 scope.

## Pre-flight status at checkpoint

- Pre-flight invariant: **35/35** green
- Full-suite: **4,777 passed / 32 skipped** in 155s
- Baseline roll count through Phase E1.2: **4** (one per sub-task that added a top-level field) — no mutations escaped in any roll
- Drop-reason distribution across canaries: `AS_INACTIVE=7`, `STRUCTURAL_HEADER=1`, `PARSE_ERROR=0`

## Golden baseline integrity

SHA256 of each canary blob pinned at the dir root. Recompute with:

```bash
shasum -a 256 reports/baseline_pre_e1_3/*.json
```

Do NOT edit these files. They are the forever reference for "last-known correctness" before E1.3 touches any scoring code.

## Go decision

✅ Proceed with E1.3.1. State verified clean across the 7-canary slice; invariants hold; drop-reason distribution is low-entropy with zero bug sentinels.
