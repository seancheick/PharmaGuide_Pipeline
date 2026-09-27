# PharmaGuide Pipeline — Release Ledger

> **Purpose:** append-only log of every shipped pipeline release. One row per release. Newest at the top.
> **Who writes here:** whoever ships the release (person or CI bot). One atomic commit per entry.
> **Never edit past entries.** If a released version later turns out to be bad, document the finding as a *new* entry noting the rollback, not a rewrite of the original row.

---

## v2026.04.21.164306 — Sprint D accuracy sprint

- **Date:** 2026-04-21
- **Pipeline commit:** `8bf65d5` (main)
- **Flutter commit:** `6e6a692` (main, [Pharmaguide.ai](https://github.com/seancheick/Pharmaguide.ai))
- **Supabase status:** `is_current=true` on export_manifest
- **Schema version:** `1.4.0` (pipeline) / `5.0.0 → 5.1.0` (reference data files — authoring only, no breaking changes)
- **Catalog size:** 8,288 unique products (deduplicated from 13,236 enriched across 20 brands)
- **Test baseline:** 4,479 pipeline + 90 safety tests + 56 Flutter test files passing

### What shipped (Sprint D + Dr Pham authoring pass)

Medical-accuracy closure work across 5 days (D1–D5.4):

- **D1:** Amaranth plant vs. dye disambiguation (66 wrong BLOCKED verdicts fixed)
- **D2:** Banned-recalled stricter match_scope + Nutrition Facts leak routing + D-Mannose / branded fiber routing + "from X" source-descriptor D2.10 routing
- **D3:** Coverage gate fixes — all 20 brands pass with 0 blocked
- **D4:** B7 UL canonical-sum aggregation (D4.3 teratogenicity protection, Rothman 1995 NEJM) — lit up on 1,929 products
- **D5:** Detail-blob top-level-key contract (D5.3), Dr Pham field propagation for banned entries (D5.4), collect_rda_ul_data config gate fix (D5.2), UPC dedup manifest fix (D5.1)

**Dr Pham authoring pass (delivered 2026-04-21):**
- 143/143 banned entries — `safety_warning_one_liner` + `safety_warning` re-authored strict-clean
- 77/77 interaction-rule warnings — Path A profile-agnostic rewrites + Path B suppress-gating
- 68/68 depletion warnings — strict-clean + chronic-tone rules
- 252/252 bonus coverage — harmful_additives / synergy / manufacturer_violations (14 jargon fixes)
- 42/42 probiotic strains — new `cfu_thresholds` blocks with API-verified PMIDs (15 strong / 15 medium / 12 weak)
- `validate_safety_copy --strict`: 0 errors, 0 warnings
- `tone_consistency_audit`: 0 findings (was 63)

### New regression tests in Sprint D
374 net-new tests in `scripts/tests/` covering every D1–D5 invariant.

### Verified medical-accuracy invariants (live on this release)
- `rda_ul_data.collection_enabled=true` on 13,236/13,236 products (100%)
- B7 OVER-UL safety_flags firing on 1,929 products (teratogenicity path live)
- Dr Pham `safety_warning` populated on 2,413/2,413 banned entries (100%)
- Dr Pham `ban_context` populated on 2,413/2,413 banned entries (100%)
- No silent mapping (`mapped=True ⇒ canonical_id != None`) — D2.1 contract enforced
- All 30 frozen snapshots match scored output

### Rollback
Previous: `v2026.04.18.*` (not formally logged — pre-ledger release). Rollback via:
```bash
python3 scripts/sync_to_supabase.py --force v2026.04.18.*
```
Local build retained at `~/Documents/DataSetDsld/builds/release_output/` (1 GB).

### Known outstanding issues at ship
Two independent audits on 2026-04-21 surfaced accuracy/safety defects requiring a follow-up sprint. See [`SPRINT_E1_ACCURACY_ADDENDUM.md`](SPRINT_E1_ACCURACY_ADDENDUM.md):

- **Pipeline-side (blast-radius projected to 8,288 catalog):**
  - ~1,158 products with stripped proprietary-blend masses (Plantizyme class)
  - ~460 products with branded names dropped (KSM-66 class)
  - ~4,812 products with active-count drift
  - ~118 products with silently-dropped inactive ingredients (silica class)
  - 612 products at Section A = 0 (includes tocopherol mis-classification, probiotic CFU gap, fish-oil EPA/DHA NP)

- **Flutter device testing (safety-copy category):**
  - Danger strings landing in `decision_highlights.positive` (green thumbs-up on "Not lawful")
  - Pregnancy warnings shown to male users (`critical` + condition-specific copy mismatch)
  - Raw enum `ban_ingredient` leaking to UI (missing-copy fallback gap)
  - 6× duplicate warning emissions
  - No authored stack-add preflight copy on banned products (Flutter has no data to render a red banner)

**Disposition:** Sprint E1 is the addendum that closes all of these. Cannot ship to public beta until E1 lands.

---

## [Future entries land above this line]

_Release ledger created 2026-04-21 alongside Sprint E1 planning._
