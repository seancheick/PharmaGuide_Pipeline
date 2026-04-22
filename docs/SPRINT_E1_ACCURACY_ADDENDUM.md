# Sprint E1 — Accuracy Addendum

> **Status:** planning
> **Type:** addendum to [`AUTOMATION_ROADMAP.md`](AUTOMATION_ROADMAP.md) — not on the Phase 1→5 main path. Prerequisite to public beta.
> **Trigger:** dual audit on 2026-04-21 (pipeline-side label-fidelity scan + Flutter device-testing handoff) surfaced 10 accuracy/safety defects affecting ~5,000 products across 8,288 (~60% of catalog). Cannot ship public beta in current state.
> **Duration estimate:** ~14 working days across 5 phases.
> **Dependencies:** Dr Pham authored-copy pass for 2 new banned-substance fields (Phase E1.1.4).
> **Exit criteria:** all 7 label-fidelity invariants + 5 safety-copy invariants pass in CI; shadow-diff reviewed and approved; release ledger entry.

---

## 0. Agent access — both repos, no guessing

This sprint spans the pipeline and the Flutter app. Both repos are on this machine; agents (Claude Code, Codex CLI, any task-running agent) are granted read access to both so they can verify alignment, not guess at it.

| Repo                     | Local path                               | Role in this sprint                                                                                      |
| ------------------------ | ---------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Pipeline** (this repo) | `/Users/seancheick/Downloads/dsld_clean` | Primary — 18 of 20 tasks live here                                                                       |
| **Flutter app**          | `/Users/seancheick/PharmaGuide ai`       | Cross-reference — rendering logic, Drift schema, field-consumption patterns, Sprint 27.7 defensive layer |

**Non-negotiable rule for every agent working Sprint E1:**

Before touching a pipeline field (adding, renaming, changing shape, changing semantics), the agent **must**:

1. Grep the Flutter repo for every consumer of that field (e.g., `grep -r "display_label\|standardDoseLabel\|displayBadge" /Users/seancheick/PharmaGuide\ ai/lib/`)
2. Read the widget/parser that consumes it
3. Confirm the Flutter side will render the new shape correctly — or document the Flutter change needed in the task's DoD and notify the Flutter team

No "pipeline ships a new field and hopes Flutter catches up." No "Flutter adds a parser and hopes the pipeline emits the right shape." Both sides get verified every time.

**Key Flutter reference paths to grep/read during Sprint E1:**

- `lib/features/product_detail/product_detail_screen.dart` — ingestion of `ingredients`, `inactive_ingredients`, `warnings`, `warnings_profile_gated`, `decision_highlights`, `section_breakdown`
- `lib/features/product_detail/widgets/interaction_warnings.dart` — `InteractionWarning.fromJson`, 10 Dr Pham fields, `condition_id`/`drug_class_id` parsing (Defect #7)
- `lib/features/product_detail/widgets/score_breakdown_card.dart` — Section A rendering, B7 UL safety banner
- `lib/features/product_detail/widgets/safety_check_sheet.dart` — stack-add preflight (Defect #4 target)
- `lib/data/database/tables/products_core_table.dart` — Drift schema (91 columns; must match pipeline 1:1)
- `HANDOFF_2026-04-21.md` + `SPRINT_TRACKER.md` — Flutter team's findings and parallel Sprint 27.7 scope

**Cross-repo contract tests:** any new `display_*` field added pipeline-side must have a matching "Flutter parser exists and consumes it" check. Sprint E1 ships this as part of E1.0.1 (add a Flutter-repo grep-based smoke test invoked from the pipeline CI).

---

## 1. Purpose

Ship one coherent release that closes every accuracy / safety-copy leak found on 2026-04-21 across two independent audit paths. No cosmetic work. No scope creep. No partial fixes held over.

## 2. Why this is an addendum, not a reorder of the roadmap

The [`AUTOMATION_ROADMAP.md`](AUTOMATION_ROADMAP.md) phases (Phase 1 CI → Phase 1.5 FDA short-path → Phase 2 web editor → …) are about _operationalizing_ the pipeline. They assume the data content is already correct. This sprint fixes the _content_ correctness before we let CI automate further releases — otherwise Phase 1 automates the propagation of the same bugs.

Keep the roadmap intact. Treat Sprint E1 as a prerequisite checkpoint tacked on between "Sprint D closed" and "Phase 1 begins."

## 3. Non-negotiables (Karpathy-style discipline)

These apply to every task in this sprint. No exceptions, no "we'll do it next sprint":

1. **Measure before you build.** Every task starts by capturing a pre-fix baseline number (affected-product count, shadow-diff of a specific field). If the number doesn't change after the fix, the fix didn't work.
2. **Define the eval first.** Before writing fix code, write the regression test that would have caught the bug. See it fail against current `main`. Only then write the fix.
3. **Smallest honest fix wins.** Don't build a full enzyme-potency scoring model when a "recognition credit + honest 'not disclosed' badge" closes the user-facing bug. Ship the smallest change that makes the product label match what the user sees.
4. **One-task-one-scope.** Each task touches ≤3 files (prefer 1–2). If you're in a 4th file, the task is mis-scoped — split it.
5. **Shadow-diff every change.** No task merges without running the enriched→scored shadow-diff harness against the previous build and reviewing the delta. Unexpected changes = repair subtask, not "interesting, carry on."
6. **Contract tests are first-class.** Each accuracy invariant ships as a pytest that runs in CI forever. If a future change re-introduces the bug, CI catches it in minutes.
7. **Repair budget:** max 3 passes per task. After pass 2, escalate (consult Dr Pham for clinical calls, pause for human review on data decisions).
8. **Anti-drift checkpoint** after every 3 completed tasks: are we still fixing accuracy, or did we drift into feature work?

## 4. Entry conditions (block sprint start if not satisfied)

- [x] Full test suite green on `main` (4,479 + 90 new safety tests as of 2026-04-21)
- [x] Supabase prod marked `is_current=true` on `v2026.04.21.164306`
- [x] Snapshot baseline captured at `/tmp/pharmaguide_release_build`
- [x] **Dr Pham authoring pass delivered 2026-04-21** — all 4 tasks complete: 143/143 banned copy, 77/77 interaction copy (Path A + B), 68/68 depletion copy, 42/42 probiotic CFU thresholds with verified PMIDs. 252/252 bonus coverage on harmful_additives / synergy / manufacturer_violations. `validate_safety_copy --strict`: clean. Tone audit: 0 findings (was 63). See `docs/DR_PHAM_AUTHORING_QUEUE.md`.
- [x] Dr Pham's schema impact audited — `cfu_thresholds` is pipeline-internal; no `products_core` column change, no Drift migration, no `schema_version` pipeline bump. `banned_recalled_ingredients.json` and friends bumped 5.0.0 → 5.1.0 (authoring only). Flutter schema stays at 91 columns.
- [x] `docs/RELEASES.md` created (append-only release ledger)
- [ ] **42 probiotic strains reviewed — sign-off status updated per strain** (handled by user's agent during sprint kickoff; Dr Pham kept `dr_pham_signoff: false` pending verification)

**Green-light summary:** Every upstream content dependency is resolved. Sprint E1 can start immediately after the strain sign-off review lands (~1 hour of work).

## 5. Global success criteria (Definition of Done — sprint-level)

Sprint E1 ships only when **all** of the following are true:

| Criterion                                                                                                                | How to verify                                                     |
| ------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| All 7 label-fidelity invariants pass                                                                                     | `pytest scripts/tests/test_label_fidelity_contract.py` 100% green |
| All 5 safety-copy invariants pass                                                                                        | `pytest scripts/tests/test_safety_copy_contract.py` 100% green    |
| 0 products with `raw_actives > 0 AND blob_actives == 0`                                                                  | Scan report (E1.0.3 tool)                                         |
| 0 products with `raw_inactives > 0 AND blob_inactives == 0`                                                              | Scan report                                                       |
| Prop-blend-mass recovery: ≥ 95% of raw-disclosed blends preserve `total_weight` in blob                                  | Scan report                                                       |
| Branded-identity preservation: ≥ 99% of branded names (KSM-66 / Meriva / BioPerine / etc.) survive to `display_label`    | Scan report                                                       |
| Standardization-note preservation: ≥ 95% of raw standardization strings (X% Y pattern) survive to `standardization_note` | Scan report                                                       |
| No `decision_highlights.positive` string matches danger deny-list                                                        | Build-time validator passes                                       |
| No `display_mode_default="critical"` warning with condition-specific copy                                                | Build-time validator passes                                       |
| Every emitted warning has ≥1 non-empty authored-copy field                                                               | Build-time validator passes                                       |
| Shadow-diff vs `v2026.04.21.164306` reviewed and every delta explained                                                   | Human review ledger in PR description                             |
| Release ledger entry in `docs/RELEASES.md` with version, date, contents                                                  | Grep-verifiable                                                   |

---

## 6. Working method (per-task lifecycle)

Every task in Phases E1.0 through E1.4 follows this exact sequence. No shortcuts.

**Phases E1.0 and E1.1 (test-infra + validators):** the 8-step lifecycle below.

**Phases E1.2, E1.3, E1.4 (code changes touching data transformation):** the **9-step** lifecycle with mandatory per-subtask mini-rebuild + manual eyeball of 3 canary products. Added 2026-04-21 per external-dev review — E1.2+ touches core normalization/enrichment and requires shadow-diff after **each subtask**, not just at phase boundary.

```
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. Capture baseline  →  run scope-report on current main    │
  │ 2. Write regression test  →  see it fail                    │
  │ 3. Implement fix  →  minimum viable diff                    │
  │ 4. Rerun regression test  →  see it pass                    │
  │ 5. Run targeted pytest (phase-boundary full suite)          │
  │ 6. Mini-rebuild 3 canary products (E1.2+ only)              │
  │ 7. Shadow-diff blob delta  →  classify every field change   │
  │     as expected / unexpected                                │
  │ 8. QA eyeball  →  "does the product page read correctly?    │
  │     does it mislead?" (E1.2+ required, E1.0/E1.1 optional)  │
  │ 9. Commit  →  atomic, one task per commit                   │
  └─────────────────────────────────────────────────────────────┘
```

If step 7 reveals unexpected deltas: create `T{n}.fix{m}` subtask, max 3 repair passes. After pass 2 without resolution, escalate.

### 6.1 Canary QA set (locked 2026-04-21)

Every E1.2+ subtask rebuilds and eyeballs these 3 products:

| Product                    | DSLD ID | Why this one                                                                   |
| -------------------------- | ------- | ------------------------------------------------------------------------------ |
| Plantizyme (Thorne)        | 35491   | Prop-blend parent-mass cascade (E1.2.1) + enzyme credit (E1.3.4)               |
| KSM-66 Ashwagandha product | TBD     | Branded-token preservation + standardization (E1.2.2 / E1.3.5)                 |
| VitaFusion CBD Mixed Berry | TBD     | Warning dedup (E1.2.3) + decision_highlights danger bucket (E1.1.1 validation) |

**Baseline source (decided 2026-04-21, option C):** reuse existing Supabase snapshot `v2026.04.21.164306` as the pre-E1 baseline — zero-cost, no external API calls. Blobs pulled from Storage bucket `shared/details/sha256/` into a local `reports/baseline_v2026.04.21.164306/` for diffing. For subtasks that touch only `build_final_db.py` (E1.2.2 display fields, E1.2.3 dedup), re-run just the final-build stage against cached enriched+scored outputs — no re-enrichment needed. For subtasks that touch `enhanced_normalizer.py` or `enrich_supplements_v3.py` (E1.2.1, E1.2.4, E1.2.5), re-enrich the 3 canary products only (not the full 8,288 catalog).

Filename ledger captured in `docs/SPRINT_E1_BUILD_BASELINE.md` (created at E1.2.1 kickoff).

### 6.2 Manual eyeball checklist (step 8)

For each canary product after each subtask:

1. Open the detail blob JSON
2. Grep for the field the subtask changed
3. Ask: does the value match what's on the physical label / the source DSLD JSON?
4. Ask: would this read correctly in Flutter? Would it mislead?
5. Record a one-line verdict in the commit message: `canary QA: {plantizyme / ksm-66 / vitafusion}: pass | flagged reason`

Not a substitute for unit tests — a complement. Contract tests prove structure; eyeball proves meaning.

---

## 7. Phase-by-phase task breakdown

### Phase E1.0 — Instrumentation (2 days)

We build the measurement tools before fixing anything. Can't fix what we can't see.

#### E1.0.1 — Label-fidelity contract tests

**Scope:** Create `scripts/tests/test_label_fidelity_contract.py` with 7 invariants stubbed (skipping until target fields exist in blobs).

**Files:** `scripts/tests/test_label_fidelity_contract.py` (new)

**Invariants to encode:**

1. `display_name_never_canonical` — ingredient `display_label` must not equal its scoring-group canonical name when source differs
2. `no_false_well_dosed_on_undisclosed` — if `is_in_proprietary_blend AND NOT individually_disclosed` then `display_badge != "well_dosed"`
3. `no_np_leaks_to_display` — `display_dose_label` must not contain `"NP"`
4. `branded_identity_preserved` — if raw has branded token (KSM-66 / Meriva / BioPerine / Ferrochel / etc.) then `display_label` contains it
5. `plant_part_preserved` — if raw `forms[].name` matches `/root|leaf|seed|bark|rhizome/i`, `display_label` preserves it
6. `standardization_note_preserved` — if raw `notes` matches the standardization pattern, `standardization_note` is non-null
7. `inactive_ingredients_complete` — for every raw `otheringredients.ingredients[i]`, blob `inactive_ingredients` contains an entry with matching `name` or alias

**Definition of Done:**

- File exists, imports cleanly, all 7 tests present
- Each test runs but `pytest.skip("waiting on E1.2.x")` until its target field is implemented
- Each test has a docstring citing the invariant's medical/UX justification
- Uses the same `_find_blob_dir()` pattern as `test_d53_detail_blob_top_level_contract.py`

**Regression test:** N/A (this IS the test infrastructure)

**Shadow-diff:** N/A

#### E1.0.2 — Safety-copy contract tests

**Scope:** Create `scripts/tests/test_safety_copy_contract.py` mirroring E1.0.1 for the safety-copy axis.

**Files:** `scripts/tests/test_safety_copy_contract.py` (new)

**Invariants to encode:**

1. `no_danger_in_positives` — `decision_highlights.positive[]` cannot contain any string matching danger deny-list regex (keywords: `not lawful|banned|talk to your doctor|arsenic|trace metals|undisclosed|high glycemic|contraindicated`)
2. `critical_warnings_are_profile_agnostic` — if `display_mode_default == "critical"`, warning copy cannot reference a specific condition (regex: `during pregnancy|for liver disease|breastfeeding|kidney disease|heart disease|while nursing`)
3. `no_raw_enum_leaks` — no warning has `type` as its only populated field; ≥1 of `(alert_headline, alert_body, safety_warning, safety_warning_one_liner, detail)` must be non-empty
4. `banned_substance_has_preflight_copy` — if `has_banned_substance == 1`, both `banned_substance_preflight_one_liner` and `banned_substance_preflight_body` must be non-empty
5. `no_duplicate_warnings` — `warnings[]` and `warnings_profile_gated[]` each contain no duplicates under key `(severity, canonical_id, condition_id, drug_class_id)`

**Definition of Done:** same shape as E1.0.1.

#### E1.0.3 — Scope-report generator

**Scope:** Wrap the ad-hoc scan script into a reusable tool: `scripts/reports/label_fidelity_scope_report.py`. Output a tabular markdown + JSON report showing affected-product counts per invariant.

**Files:** `scripts/reports/label_fidelity_scope_report.py` (new), `scripts/reports/__init__.py` (new if missing)

**Inputs:** pointer to a build-output dir (`detail_blobs/`) + raw DSLD staging dir.

**Outputs:**

- `reports/label_fidelity_scope_{timestamp}.md` — human-readable table
- `reports/label_fidelity_scope_{timestamp}.json` — machine-readable for CI gates

**Definition of Done:**

- Runs in < 60s on full 8,288 products (use local disk, not iCloud-synced paths)
- Reports counts for all 7 fidelity axes + all 5 safety-copy axes
- Idempotent: second run on same inputs produces identical output (no wall-clock in output)
- Exit code 0 if all invariants pass, 1 if any fail — usable as a CI gate

**Regression test:** `scripts/tests/test_scope_report_runs.py` — feeds a fixture with 1 known-good and 1 known-bad product, asserts counts.

---

### Phase E1.1 — Safety-copy integrity (3 days, CRITICAL)

Flutter handoff items #1, #2, #4, #5. These are the bugs that actively harm users right now — green thumbs-up on "not lawful," pregnancy warnings to men, raw enum leaks, silent banned-substance stack-adds.

#### E1.1.1 — `decision_highlights` re-classification + `danger` bucket

**Scope:** Audit `decision_highlights` generation in the pipeline. Add 4th bucket `danger`. Re-route any string matching danger deny-list. Add build-time validator that fails the build on violation.

**Files:**

- `scripts/enrich_supplements_v3.py` (or wherever `decision_highlights` is generated — locate via `grep`)
- `scripts/build_final_db.py` (validator invocation)
- `scripts/tests/test_decision_highlights_categorization.py` (new)

**Definition of Done:**

- `decision_highlights` dict now has keys: `positive`, `caution`, `danger`, `trust`
- 0 strings in `positive` match the danger deny-list across all 8,288 products (verify via scope report)
- Build-time validator in `build_final_db.py` raises `ValueError` if any `positive` contains a deny-listed token
- Regression test: feed 5 known-bad examples (including the VitaFusion CBD strings from the Flutter handoff), assert they land in `danger`, not `positive`
- Shadow-diff shows expected migrations: `N` positive→danger moves, 0 danger→positive
- Flutter team notified: `danger` bucket is new; their `_DecisionHighlights` widget needs a red-tinted renderer

**Sample evidence to verify fix against (from Flutter handoff):**

- "Not lawful as a US dietary supplement. Talk to your doctor."
- "Concentrated added sugar. Some can carry trace arsenic."
- "Undisclosed colorant. Transparency concerns."
- "Diabetes. Contains high glycemic sweetener."

#### E1.1.2 — `warnings_profile_gated` display_mode vs copy audit

**Scope:** For every warning, verify that copy and `display_mode_default` are consistent:

- `critical` → copy must be profile-agnostic ("May affect pregnancy — consult physician")
- `suppress` → copy is free to reference a specific condition (that's why it's gated)

**Path A (preferred):** rewrite warning copy generation so critical-mode strings are always profile-agnostic.
**Path B:** re-classify any warning with condition-specific copy to `display_mode_default="suppress"`.

Per Flutter team, Path A preferred. Decision to be made at task kickoff by whoever owns warning-copy authoring.

**Files:**

- Warning copy source: locate via `grep "display_mode_default" scripts/`
- `scripts/build_final_db.py` (validator)
- `scripts/tests/test_warning_display_mode_consistency.py` (new)

**Definition of Done:**

- 0 products where `display_mode_default == "critical"` AND copy matches `/(during pregnancy|for liver disease|breastfeeding|kidney disease|heart disease|while nursing)/i`
- Build-time validator fails the build on violation
- Regression test: 10 known condition-specific warnings from current output, assert they either have agnostic copy or are suppress-gated
- Shadow-diff: expected migrations documented (N warnings rewritten from condition-specific → agnostic, OR M warnings re-classified critical→suppress)

#### E1.1.3 — `ban_ingredient` raw-enum leak + fallback validator

**Scope:** Audit every warning-emission site. If any path can emit a warning with empty authored copy (all of `alert_headline`, `alert_body`, `safety_warning`, `safety_warning_one_liner`, `detail` are empty), that path must raise at build time.

**Files:**

- `scripts/enrich_supplements_v3.py` (warning-emission sites)
- `scripts/build_final_db.py` (validator)
- `scripts/tests/test_warning_has_authored_copy.py` (new)

**Definition of Done:**

- 0 warnings in any blob with all 5 copy fields empty
- Build-time validator fails on any missing-copy warning, emitting `dsld_id + warning_type` for triage
- Dr Pham authoring queue populated with any missing-copy warnings surfaced by the validator (handoff artifact)

#### E1.1.4 — Banned-substance preflight copy — wire existing Dr Pham fields

> **Scope reduced 2026-04-21:** Dr Pham authored the preflight copy using the _existing_ `safety_warning_one_liner` + `safety_warning` fields on `banned_recalled_ingredients.json` rather than introducing two new fields. 143/143 banned entries now carry the authored copy, validator-clean. No `products_core` schema change, no Drift migration.

**Scope:** Verify Dr Pham's authored copy propagates end-to-end to the detail blob, then wire into Flutter's stack-add preflight sheet.

**Files:**

- `scripts/enrich_supplements_v3.py` (confirm Sprint D5.4 propagation still intact — it was fixed for banned entries)
- `scripts/build_final_db.py` (emit `safety_warning_one_liner` + `safety_warning` on every product where `has_banned_substance=1`)
- `scripts/tests/test_banned_preflight_contract.py` (new)
- **Flutter:** `lib/features/product_detail/widgets/safety_check_sheet.dart` — render red-banner CRITICAL state when `has_banned_substance=1`, populate from the two fields

**Definition of Done:**

- For every product with `has_banned_substance=1`, both fields non-empty in the detail blob (validator fails build otherwise)
- Char-limit validators pass (80 / 200 on Dr Pham's authored copy; she delivered strict-clean)
- Regression test: 5 sample banned products (covering CBD, ephedra, DMAA, kratom, higenamine), assert both fields propagate
- Flutter stack-add preflight sheet renders the red banner using these fields
- Contract test `banned_substance_has_preflight_copy` (E1.0.2 #4) unskipped and green

**Cross-team coordination:** Dr Pham = delivered. Pipeline = wiring validator + propagation test. Flutter = Sprint 27.7 widget wiring.

---

### Phase E1.2 — Label fidelity (4 days, HIGH)

My scan findings A, B, D, E, F + Flutter handoff #3. Roughly 1,100–4,800 products per axis.

#### E1.2.1 — Proprietary blend parent-mass propagation

**Scope:** Fix the two-point strip identified in [earlier investigation](#). Cleaner propagates parent-row mass to children; enricher reads it.

**Files:**

- `scripts/enhanced_normalizer.py` (~lines 3298–3350, `_flatten_nested_ingredients`)
- `scripts/enrich_supplements_v3.py` (~line 8180, `_aggregate_proprietary_blends`)
- `scripts/tests/test_prop_blend_mass_propagation.py` (new)

**Definition of Done:**

- Plantizyme (Thorne 35491) `proprietary_blend_detail.blends[0].total_weight == 850.0`, `blend_total_mg == 850.0`
- ≥ 95% of raw-disclosed blend masses survive to blob (scope report metric A)
- Regression test: 5 fixture products covering enzyme blends, mushroom complexes, "Herbal Blend", "Chondroitin/MSM Complex", "Kids Probiotic Blend"
- Shadow-diff: only `proprietary_blend_detail.blends[].total_weight|blend_total_mg|unit` fields change; no score or warning deltas

#### E1.2.2 — Pre-computed display fields

**Scope:** Make Flutter a dumb renderer. Compute user-facing strings pipeline-side.

Add per-ingredient to the detail blob:

- `display_label` — branded + base + form (e.g. "KSM-66 Ashwagandha Root Extract")
- `display_dose_label` — "600 mg" | "Amount not disclosed" | "—"
- `display_badge` — "well_dosed" | "low_dose" | "high_dose" | "not_disclosed" | "no_data"
- `standardization_note` — "Standardized to 5% total withanolides" | null

**Files:**

- `scripts/build_final_db.py` (add 4 helper functions + invoke in ingredient serializer)
- `scripts/tests/test_display_field_computation.py` (new)

**Definition of Done:**

- All 4 fields populated on every ingredient in every blob (validator)
- Contract tests from E1.0.1 (#1–4, #6) now unskipped and green
- ≥ 99% branded-name preservation (scope report metric B)
- ≥ 95% standardization-note preservation (scope report metric D)
- Regression test: 10 fixture products covering:
  - KSM-66 Ashwagandha (branded + form + standardization)
  - Meriva Curcumin
  - BioPerine
  - Ferrochel Iron (Albion brand)
  - Thorne Silybin/Phytosome
  - A generic mineral (Magnesium Citrate)
  - A generic vitamin (Vitamin D3)
  - An enzyme in a prop blend (Amylase)
  - A fish-oil EPA entry
  - A probiotic strain
- Shadow-diff: only 4 new fields on every ingredient; no existing fields modified

#### E1.2.3 — Warning dedup at build-time

**Scope:** Collapse `warnings[]` and `warnings_profile_gated[]` where the tuple `(severity, canonical_id, condition_id, drug_class_id, source_rule)` is identical. Prefer the entry with most-complete authored copy; fall back to first.

**Files:**

- `scripts/build_final_db.py` (new helper `_dedup_warnings`)
- `scripts/tests/test_warning_dedup.py` (new)

**Definition of Done:**

- VitaFusion CBD Mixed Berry: 6× pregnancy warnings → 1
- Contract test E1.0.2 #5 unskipped and green
- Regression test: fixture with known 6-copy warning set, assert post-dedup count
- Shadow-diff: warning count decreases; no new/changed warnings

#### E1.2.4 — Active and Inactive-ingredient dropping audit

**Scope:** Investigate why 118 products have `raw_inactives > 0` but blob `inactive_ingredients == []`. Likely a cleaner filter too aggressive. Fix.

**Files:**

- `scripts/enhanced_normalizer.py` (locate via `grep "otheringredients"`)
- `scripts/tests/test_inactive_ingredient_preservation.py` (new)

**Definition of Done:**

- 0 products with `raw_inactives > 0 AND blob_inactives == 0` (scope report metric E)
- Contract test E1.0.1 #7 unskipped and green
- Regression test: 5 fixture products previously affected, assert all inactives survive
- Shadow-diff: inactive counts increase on affected products, no other deltas

#### E1.2.5 — Active-count reconciliation

**Scope:** Investigate the 58% active-count mismatch. Classify into:

- **Legitimate** (structural headers like "Total Fat" intentionally dropped) — document in blob as `ingredients_dropped_reasons[]`
- **Bug** (real actives lost, e.g. `raw=8 → blob=0`) — fix

**Files:**

- `scripts/enhanced_normalizer.py` (dropping logic)
- `scripts/build_final_db.py` (emit `ingredients_dropped_reasons[]`)
- `scripts/tests/test_active_count_reconciliation.py` (new)

**Definition of Done:**

- 0 products with `raw_actives > 0 AND blob_actives == 0`
- Every drop documented with a reason code in `ingredients_dropped_reasons[]`
- Regression test: fixture products previously at `raw=N, blob=0`, assert blob now matches raw minus documented drops
- Shadow-diff: ingredient counts change on ~4,800 products; each delta has a reason code

---

### Phase E1.3 — Scoring correctness (4 days, MEDIUM)

My findings H, I, J + plant-part preservation (C).

#### E1.3.1 — `is_additive` classifier: source-section and dose-aware

**Scope:** Tocopherol as active (335 mg serving of Vitamin E) must NOT be skipped with `skip_reason=is_additive`. The classifier needs to check source-section context + dose magnitude.

**Files:**

- `scripts/enrich_supplements_v3.py` (locate additive classifier via `grep "is_additive"`)
- `scripts/tests/test_additive_classifier_context.py` (new)

**Definition of Done:**

- Nature Made E 400 IU (DSLD 266975) Section A > 0
- Pure Encapsulations Ultra-Synergist E (DSLD 188715) Section A > 0
- Nature Made Triple Omega (DSLD 26689) Vitamin E scorable, not skipped
- Regression test: fixture of 10 dual-use ingredients (tocopherols, lecithin, gelatin, rice flour) in both active and inactive contexts, assert classifier correctly distinguishes
- Shadow-diff: Section A increases on affected products; no change on products where additive is legitimately an excipient

#### E1.3.2 — Probiotic CFU-based A1 adequacy path

> **Reference data delivered 2026-04-21:** Dr Pham authored `cfu_thresholds` blocks on all 42 clinically-relevant strains in `scripts/data/clinically_relevant_strains.json` (schema 5.0.0 → 5.1.0). Each block has industry-default tier boundaries (1B / 10B / 50B CFU/day), PubMed-verified evidence citation, and an honest `evidence_strength` flag: 15 strong / 15 medium / 12 weak. She also shipped tooling: `scripts/api_audit/probiotic_dose_search.py`, `probiotic_batch_verify.py`, `author_probiotic_thresholds.py`. All 42 PMIDs API-verified (33 direct title-match, 7 indirect review matches, 2 non-direct). Per-strain `dr_pham_signoff` flag pending user review — see sprint kickoff task.

**Scope:** Wire the delivered `cfu_thresholds` blocks into the scorer. `_compute_probiotic_cfu_adequacy` reads the strain's threshold block, compares product's per-strain CFU dose, maps to low/adequate/good/excellent tier → Section A points.

**Files:**

- `scripts/score_supplements.py` (new `_compute_probiotic_cfu_adequacy`, called from `_compute_probiotic_category_bonus` path)
- `scripts/tests/test_probiotic_cfu_scoring.py` (new)
- (No new data file — Dr Pham's thresholds live on `clinically_relevant_strains.json` already)

**Definition of Done:**

- ≥ 150 of 194 probiotic-A=0 products now have Section A > 0 (remaining ~44 are strain-missing or below-adequacy-threshold, documented in their `zero_score_diagnostic`)
- **Weak-evidence strains respected:** scorer reads `evidence.clinical_support_level` (NOT just `evidence_strength`) and applies tiered caps:
  - `high` — full tier points
  - `moderate` — 75% of tier points
  - `weak` OR missing — 50% of tier points + emit flag `probiotic_strain_evidence_weak`
- **Clinical-validation gate:** every strain used for scoring MUST carry `evidence.clinical_validation` block with all 4 sub-scores (`q1_strain_explicit` / `q2_outcome_relevant` / `q3_human_clinical` / `q4_dose_mentioned`) and `evidence.clinical_support_level` non-null. Build fails otherwise.
- Regression test: fixture of 8 products covering all 4 threshold bands × 3 support-level paths (high/moderate/weak)
- 42-strain sign-off review complete (either flipped to `true` after verification, or kept `false` with documented `clinical_support_level`)
- Shadow-diff: Section A increases on probiotic products; no change on non-probiotic products

##### E1.3.2.2 — Confidence-model hybrid (added 2026-04-21 per external-dev review)

**Problem the hybrid addresses:** scoring math uses tier caps (100% / 75% / 50% of points by `clinical_support_level`), which is clinically honest on the math side. The **blob-level surfacing**, however, currently encourages precise-sounding UX copy ("Adequate dose", "Excellent dose") against evidence that is probabilistic, not absolute. Probiotic dosing literature is directional — strain effects are context-dependent, meta-analyses disagree, full-text dose validation is often unavailable.

**The hybrid (keep the math, fix the framing):**

1. **Keep** the current 4-tier CFU bands (`low` / `adequate` / `good` / `excellent`).
2. **Keep** the 3-level scoring cap on `clinical_support_level`.
3. **Add** two fields to each strain entry in the probiotic_detail blob:
   - `cfu_confidence`: `"high" | "moderate" | "low"` — derived from `clinical_support_level` + whether full-text dose was verified (vs abstract-only).
   - `dose_basis`: `"clinical" | "inferred" | "industry_standard"` — `clinical` when the CFU threshold is directly supported by a trial's dosing arm, `inferred` when extrapolated from a review, `industry_standard` when the 1B/10B/50B tier boundaries are default industry convention rather than strain-specific.
4. **Add** a `ui_copy_hint` per strain — Flutter renders this instead of generating its own adjective ("Excellent dose"). Pipeline-generated honest copy:
   - "Within typical studied CFU range"
   - "Above typical studied range — limited evidence for marginal benefit"
   - "Below typical studied range — may be underdosed"
   - "CFU claim not independently verified"
5. **Language sweep** during implementation: grep the blob and remove/rephrase any instance of: `"optimal dose"`, `"clinically proven"`, `"adequate dose"` (as standalone hero copy), `"excellent dose"`. Replace with evidence-confidence framing.

**Emitted shape per strain (blob addition):**

```json
"probiotic_detail": {
  "strains": [{
    "strain_id": "L. rhamnosus GG",
    "cfu_per_day": 10000000000,
    "cfu_tier": "within_typical_studied_range",
    "cfu_confidence": "moderate",
    "dose_basis": "industry_standard",
    "evidence_strength": "moderate",
    "clinical_support_level": "moderate",
    "ui_copy_hint": "High CFU relative to typical products"
  }]
}
```

**Rationale (external-dev review, 2026-04-21):** "You don't win by being perfectly precise. You win by being the most honest + structured system in a messy domain." Avoids legal/clinical risk of "optimal" / "clinically proven" language while preserving the scoring signal. Downside accepted: slightly less punchy UX copy; upside: user trust holds when a clinician scrutinizes the claim.

**Additional DoD items for E1.3.2 (hybrid):**

- Every strain in `probiotic_detail.strains[]` carries `cfu_confidence`, `dose_basis`, `ui_copy_hint` fields (validator fails build otherwise).
- `cfu_confidence` derivation uses BOTH `clinical_support_level` AND `clinical_validation.q4_dose_mentioned` — "high" requires both `high` support + dose explicit in abstract (or full-text verified).
- Build-time language-scrub validator: grep `ui_copy_hint` + any blob-emitted strings for `{optimal dose, clinically proven, adequate dose}`. Fail build on match.
- Regression test: 3 strains covering all 3 confidence levels + assertion that `ui_copy_hint` text never contains banned phrases.

##### E1.3.2.1 — Clinical validation invariant (added 2026-04-21 per clinical-reviewer feedback)

**Scope:** Encode the 4-question clinical validation framework as a permanent build-time invariant applied to every probiotic strain citation:

1. **Q1 Strain explicit** — strain code appears in abstract (not just title)
2. **Q2 Outcome relevant** — abstract discusses claimed `indication_primary`
3. **Q3 Human clinical** — pubtype includes RCT / Clinical Trial / Meta-Analysis / Systematic Review AND abstract does not indicate animal/in-vitro-only study
4. **Q4 Dose mentioned** — abstract quantifies a specific CFU dose

**Files:**

- `scripts/api_audit/probiotic_clinical_validation.py` (new — generalize the pass we ran on 14 strains to all 42; idempotent)
- `scripts/tests/test_probiotic_clinical_validation_contract.py` (new)

**Definition of Done:**

- Validator runs against every strain in `clinically_relevant_strains.json`; writes `evidence.clinical_validation` + `evidence.clinical_support_level`
- Contract test: build fails if any strain used in scoring has `clinical_support_level` missing
- Scorer reads `clinical_support_level` for tier-cap logic (documented in E1.3.2 above)
- **Known limitation:** Q4 (dose) scored from abstract only. Full-text PDF review required to lift strains from weak → moderate on dose grounds alone. Documented in the validation doc as a Phase 5 follow-up (backlog item: `probiotic_fulltext_dose_extraction`).

#### E1.3.3 — Fish oil EPA/DHA nested-NP propagation

**Scope:** Same pattern as E1.2.1 but for fish-oil structures. Parent row carries total oil mass; EPA/DHA nested with qty=0 NP on many products. Propagate parent mass so scorer has a usable denominator.

**Files:**

- `scripts/enrich_supplements_v3.py` (aggregation logic; may share code with E1.2.1)
- `scripts/tests/test_fish_oil_nested_propagation.py` (new)

**Definition of Done:**

- Spring Valley Enteric Coated Fish Oil 1290 mg (DSLD 19055) Section A > 0
- Regression test: 5 fish-oil fixture products covering common DSLD structures
- Shadow-diff: Section A increases on affected fish-oil products; no non-fish-oil deltas

#### E1.3.4 — Enzyme recognition credit (Tier 2 from earlier plan)

**Scope:** Small recognition credit (0.5 pts per mapped enzyme, capped at 3 pts) when dose is `NP` but enzyme is recognized. Prevents misleading 0/25 display on enzyme-dominated products. Does NOT replace the future full enzyme-potency model (Tier 3 / backlog).

**Files:**

- `scripts/score_supplements.py` (new A-section sub-metric behind config flag)
- `scripts/config/scoring_config.json` (add config toggle)
- `scripts/tests/test_enzyme_recognition_credit.py` (new)

**Definition of Done:**

- Plantizyme Section A ≥ 2.5/25 (up from 0.0)
- Behind config flag so it can be disabled/tuned without code changes
- Regression test: 5 enzyme products, assert expected score increase
- Shadow-diff: Section A increases on ~42 enzyme products; no other deltas

#### E1.3.5 — Plant-part preservation in `display_label`

**Scope:** Already partially handled in E1.2.2 — this task is the validation + test coverage closeout.

**Files:**

- `scripts/tests/test_label_fidelity_contract.py` (unskip invariant #5)

**Definition of Done:**

- Contract test #5 (`plant_part_preserved`) green
- Scope report shows ≥ 95% plant-part preservation (metric C)
- Fixture: 10 products covering root/leaf/seed/bark/rhizome/aerial-parts

---

### Phase E1.4 — Schema / data-contract fixes (1 day, LOW)

#### E1.4.1 — `condition_id` vs `condition_ids` audit

**Scope:** Walk every warning-emission site. Document which emits singular `condition_id` vs plural `condition_ids`. Standardize on **plural array** everywhere (backward-compatible: singular consumers can still read `array[0]`).

**Files:**

- `scripts/enrich_supplements_v3.py` (audit emission sites)
- `scripts/FINAL_EXPORT_SCHEMA_V1.md` (document the shape)
- `scripts/tests/test_condition_id_shape_consistency.py` (new)

**Definition of Done:**

- Every warning entry emits `condition_ids: List[str]` and `drug_class_ids: List[str]` (plural, array)
- Schema doc updated
- Flutter team notified of migration
- Regression test: sample warnings, assert shape

#### E1.4.3 — Deprecate legacy probiotic scoring components (backlog, post-E1.3)

**Context:** E1.3.2.a/b/c established per-strain CFU adequacy + `clinical_support_level` + `cfu_confidence` as the primary probiotic quality signal. The legacy components inside `_compute_probiotic_category_bonus` (aggregate CFU tiers, diversity weighting, clinical-token matching) are now redundant and risk double-counting when stacked on the new adequacy uplift.

**Follow-up scope (no code change in this sprint, tagged here so it isn't lost):**

- Total-CFU thresholds → replaced by per-strain adequacy
- Clinical-strain-token matching → replaced by structured strain validation in `_collect_probiotic_data`
- Diversity weighting → downgrade to secondary signal (or remove)
- Prebiotic + survivability → keep as additive formulation signals (they're orthogonal)

**Delivery path:** Run the same diagnostic harness we built for E1.3.2.c against a proposed config with legacy components removed / reweighted; ship behind a feature flag; shadow-diff full catalog before/after; phase out via config-only change.

#### E1.4.2 — Fix HANDOFF smoke-test product reference

**Scope:** `HANDOFF_2026-04-21.md` in Flutter repo references Thorne DSLD 16037 as "Silybin Phytosome" but the actual catalog row is "Planti-Oxidants." Minor doc fix.

**Files:**

- `/Users/seancheick/PharmaGuide ai/HANDOFF_2026-04-21.md`

**Definition of Done:**

- Product name corrected in smoke-test table
- Commit to Flutter repo

---

### Phase E1.5 — Release (2 days)

#### E1.5.1 — Full pipeline rerun

**Scope:** Clean → Enrich → Score → Build Final DB for all 20 brands with the E1 fixes in place.

**Definition of Done:**

- All 20 brands process successfully
- `coverage_gate.py` passes on all brands
- Full test suite green (expected ≥ 4,479 + ~50 new E1 regression tests)

#### E1.5.2 — Shadow-diff review

**Scope:** Compare new build against `v2026.04.21.164306`. Every delta must be explainable.

**Definition of Done:**

- Shadow-diff report generated
- Every product with a score delta has a linked E1 task ID explaining why
- Human review sign-off in PR description

#### E1.5.3 — Final DB + Supabase sync

**Scope:** Standard 10-step release playbook with E1 artifacts.

**Definition of Done:**

- New catalog version on Supabase (expected `v2026.04.28.*` or similar)
- `is_current=true` flipped
- Storage blobs uploaded
- Old `v2026.04.21.164306` kept as rollback

#### E1.5.4 — Flutter catalog bundle update

**Scope:** Bundle new SQLite via LFS; ship Flutter Sprint 27.7 patches alongside.

**Definition of Done:**

- Flutter `assets/db/pharmaguide_core.db` updated
- Sprint 27.7 defensive-layer patches merged
- Canary passes on device (3 smoke-test products: Plantizyme, KSM-66, VitaFusion CBD)

#### E1.5.5 — Release ledger + handoff

**Scope:** Append entry to `docs/RELEASES.md`. Close Sprint E1.

**Definition of Done:**

- Release ledger entry with version, date, contents, affected-product counts
- Sprint E1 marked SHIPPED in `AUTOMATION_ROADMAP.md`
- `HANDOFF_NEXT.md` updated to point back at Phase 1

---

## 8. Risk register

| Risk                                                       | Likelihood | Impact | Mitigation                                                                          |
| ---------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------- |
| Dr Pham authoring pass delayed                             | Med        | High   | Start authoring queue Day 1; Pipeline work in parallel can complete without content |
| Probiotic CFU thresholds require clinical review           | High       | Med    | Ship with conservative starter set (top 20 strains); expand post-sprint             |
| Shadow-diff surfaces unexpected deltas                     | High       | Med    | Repair subtask, max 3 passes per task; escalate on pass 2                           |
| Active-count reconciliation reveals more bugs              | Med        | Med    | Add repair tasks to E1.2.5 scope; don't ship until all deltas explained             |
| `decision_highlights` rewrite requires schema version bump | Low        | Low    | Already bumping to 5.2.0 for banned preflight fields; piggyback                     |

## 9. Cross-team asks

**Dr Pham (authoring): ✅ DELIVERED 2026-04-21**

- ✅ 143/143 banned entries — `safety_warning_one_liner` + `safety_warning` (E1.1.4)
- ✅ 77/77 interaction-rule warnings — Path A (profile-agnostic rewrites) + Path B (suppress-gate) (E1.1.2)
- ✅ 68/68 depletion warnings — strict-clean (E1.1.3 backfill)
- ✅ 252/252 bonus coverage — harmful_additives / synergy / manufacturer_violations
- ✅ 42/42 probiotic strain `cfu_thresholds` with API-verified PMIDs (E1.3.2)
- ⏳ Post-sprint optional: review the 9 stronger-evidence candidates PubMed surfaced for the 12 weak strains (see [`SPRINT_E1_STRAIN_VERIFICATION.md`](SPRINT_E1_STRAIN_VERIFICATION.md)); decide keep-or-swap per strain

**Flutter team:**

- E1.2.2: wire new fields (`display_label`, `display_dose_label`, `display_badge`, `standardization_note`) — dumb rendering
- E1.1.1: add `danger` bucket rendering (red-tinted) to `_DecisionHighlights` widget
- E1.1.4: wire existing `safety_warning_one_liner` + `safety_warning` into the stack-add confirmation sheet CRITICAL state (Sprint 27.7) — no new fields needed
- E1.4.2: fix the HANDOFF smoke-test product reference

## 10. Rollback plan

If Sprint E1's release (v2026.04.28.\*) regresses anywhere unexpectedly:

```bash
python3 scripts/sync_to_supabase.py --force v2026.04.21.164306
```

Flutter ships previous `assets/db/pharmaguide_core.db` from git history.

Keep `v2026.04.21.164306` bundled + Storage blobs intact until E1.5 has been in production ≥ 7 days without incident.

## 11. Post-sprint

On sprint close:

1. Mark Sprint E1 SHIPPED in this doc + `AUTOMATION_ROADMAP.md`
2. Add the 12 new contract tests to `PIPELINE_OPERATIONS_README.md` required-CI-checks list
3. Update `HANDOFF_NEXT.md` to point back at Phase 1 (pipeline CI)
4. Retro: capture any new net-new items in `AUTOMATION_ROADMAP.md` backlog

### Post-sprint backlog — Interaction Rules Tightening (added 2026-04-22)

Separate clinical reviewer audited `scripts/data/ingredient_interaction_rules.json` during E1 execution. Architecture grade: 9.5/10. Clinical accuracy grade: 8.5/10. Product readiness: 10/10. Five concrete tightening items surfaced — none are E1 blockers (audit done while E1.4 was closing); they belong in a follow-up sprint ("Sprint F — Interaction Rules Tightening").

Two items (IIR-2, IIR-3) are small and fit naturally into Sprint E1 if time permits before E1.5 ships; otherwise roll to Sprint F.

| ID | Item | Scope | Effort | Sprint |
|---|---|---|---|---|
| **IIR-1** | Tighten evidence-level taxonomy | Reclassify `evidence_level` across all rules per strict hierarchy: `established` (guideline consensus — rare for supplements), `strong` (multiple RCTs / meta-analysis), `moderate` (some human data), `limited` (theoretical / animal / in-vitro). Migrate existing tags. Dr Pham authoring pass. | ~3 days | **Sprint F** |
| **IIR-2** | Split `mechanism` into `internal_mechanism` + `user_mechanism` | Full scientific detail stays pipeline-side; user-facing simplified text computed pipeline-side, rendered Flutter-side. Prevents `4-hydroxynonenal / troxis necrosis` leaking to phone screens. | ~1 day stub + Dr Pham authoring | **E1.2.2 add-on OR Sprint F** |
| **IIR-3** | Severity enum + consistency validator | Hard-define `contraindicated` / `avoid` / `caution` / `monitor` with enforcement rules. Build-time validator: severity value matches authored alert_body tone (no "contraindicated" language in a "caution"-severity rule). | ~4 hours | **E1.0.2 add-on OR Sprint F** |
| **IIR-4** | Expand `dose_thresholds` coverage | Currently populated on caffeine and a handful; missing on berberine, magnesium, vitamin D, and ~25 other ingredients where dose drives safety. Dr Pham authoring with API-verified clinical thresholds. | ~5 days | **Sprint F** |
| **IIR-5** | Soften overreaching claims (tone sweep) | Examples: "berberine comparable to metformin" → "has shown glucose-lowering effects comparable in some studies". Same methodology as Dr Pham's banned + depletion tone passes. | ~2 days | **Sprint F** |

**Decision rule for IIR-2 + IIR-3 inclusion in current E1:**
- If E1.5.1 (full pipeline rerun) is > 2 days out and E1.0/E1.2 task owners have bandwidth → fold in as small add-ons
- If E1.5 release prep is imminent → defer both to Sprint F (do NOT destabilize release)

Sprint F draft (`docs/SPRINT_F_INTERACTION_RULES_TIGHTENING.md`) can be stubbed immediately after E1 ships. Same sprint-doc template as E1: atomic tasks, Karpathy DoD, contract tests, cross-team asks (Dr Pham authoring), shadow-diff gates.

**Grade trajectory (mirrors probiotic pattern):**
- Pre-Sprint F: 8.5/10 clinical / 9.5/10 architecture / 10/10 product (operational, production-shippable)
- Post-Sprint F: 10/10 / 10/10 / 10/10 (clinical decision layer, competitive moat)

---

_Last updated: 2026-04-22 (Sprint F backlog added during E1 execution)_
