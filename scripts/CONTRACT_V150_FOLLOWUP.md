# Contract v1.5.0 — Follow-up Plan

> Owner: Sean
> **Status: COMPLETE 2026-05-05 — kept as a historical runbook. v1.6.0 has since shipped on top of this (profile_gate passthrough, coverage gate enforcement, canonical_id + delivers_markers at blob level).**
> Created: 2026-05-05 · Closed: 2026-05-05 · Doc refreshed: 2026-05-12
> Related: `FINAL_EXPORT_SCHEMA_V1.md` (now v1.6.0), `build_final_db.py`, Flutter repo at `/Users/seancheick/PharmaGuide ai`

This was the ordered runbook for landing the canonical ingredient
contract end-to-end. All six steps (Pipeline rebuild, Real-blob
verification, Flutter surgical migration, Widget tests, Deprecation
cleanup, Refactor sequencing) landed on 2026-05-05 — see the
Definition-of-done checklist at the bottom. Subsequent work
(v1.6.0 — profile_gate passthrough, coverage gate, identity-vs-bioactivity
split) is tracked in `reports/identity_vs_bioactivity_impact_report.md`
and `FINAL_EXPORT_SCHEMA_V1.md`.

---

## What shipped on the pipeline side (already done)

- **Phase A** — `build_final_db.py` emits the canonical contract on every active and inactive ingredient row. Single source of truth, Flutter renders directly without local inference.
- **Phase B** — `enhanced_normalizer.py` cleaner regex now extracts trailing form tokens for vitamin A esters, K isoforms, folate forms, mineral salt long tail, B1/B2/B3/B5/B6 active-vs-synthetic forms, plus selenium/CoQ10/choline.
- **Phase C** — Release gate `test_form_sensitive_nutrient_gate.py` walks the live blob corpus and asserts no form-sensitive nutrient has a real `matched_form` with empty `display_form_label`. Skipped automatically until the corpus is rebuilt.
- **Schema doc** — `FINAL_EXPORT_SCHEMA_V1.md` bumped to v1.5.0 with full contract documentation and the deprecation roadmap.
- **Tests** — 91 new tests across 4 new test files, all green. 527 tests total in the form/dose/build pipeline pass.

---

## Step 1 — Run fresh pipeline

```bash
# From dsld_clean repo root
python3 scripts/run_pipeline.py <dataset_dir>
python3 scripts/build_final_db.py <scored_input> scripts/final_db_output

# Confirm release gate now runs and passes
python3 -m pytest scripts/tests/test_form_sensitive_nutrient_gate.py -v

# Sync to Supabase (dry-run first)
python3 scripts/sync_to_supabase.py scripts/final_db_output --dry-run
python3 scripts/sync_to_supabase.py scripts/final_db_output
```

Expected outcome: every blob carries the new contract fields, the form-sensitive gate runs (no skip), and the live Supabase corpus reflects the rebuild.

---

## Step 2 — Inspect real blobs (verification before Flutter changes)

Pull these specific products and confirm the new fields are present and correct. Use `python3 -c "import json; b=json.load(open('scripts/final_db_output/detail_blobs/<id>.json')); ..."` or jq.

| Product | DSLD ID | What to verify |
|---|---|---|
| Thorne Basic Prenatal | `328830` | `Vitamin A Palmitate` row: `display_form_label="Retinyl Palmitate"` (or "Palmitate"), `form_status="known"`, `form_match_status="mapped"`. `Vitamin A` row: `form_status="unknown"`, `display_form_label=null`. Both rows: `display_dose_label` matches the label dose. |
| A magnesium glycinate product | TBD | `display_form_label` matches "Glycinate" or "Bisglycinate", `form_status="known"`. |
| A magnesium oxide product | TBD | `display_form_label="Oxide"` or similar, `form_status="known"`. |
| A product with proprietary blend | TBD | Blend members with no individual dose: `dose_status="not_disclosed_blend"`, `display_dose_label="Amount not disclosed"`. |
| A silicon dioxide inactive | any Thorne (e.g. `15906`) | Inactive row: `display_label="Silicon Dioxide (E551)"`, `display_role_label="Anti-caking agent"`, `severity_status="suppress"`, `is_safety_concern=false`, `is_harmful=true` (provenance). |
| A product with no form disclosed | TBD | Active row with bare nutrient name: `form_status="unknown"`, `display_form_label=null`. Confirms the cleaner doesn't hallucinate. |

Capture findings in a short audit note. Any field mismatch blocks the Flutter PR.

---

## Step 3 — Flutter surgical migration

Repo: `/Users/seancheick/PharmaGuide ai`

### Active row — `lib/features/product_detail/product_detail_screen.dart`

| Concern | File:line | Replace with |
|---|---|---|
| Dose label | `:2258-2263` | `display_dose_label` only. Drop the `"$quantity $unit"` fallback. |
| Dose empty state | `:2258-2263` | Conditional on `dose_status == "missing"` (or `"not_disclosed_blend"` if you want a different copy). |
| Form helper line | `:2321-2329` | `display_form_label`. Render only when `form_status == "known"`. If `form_status == "unknown"` and you want to surface it in the explain modal, render "Form not disclosed" intentionally. |
| Form quality chip | `:2265` | Keep `bio_score` (orthogonal — quality grade, not safety). |
| Safety concern chip | `:2266-2268` | Add `is_safety_concern` read. Distinct from `bio_score`. |

### Inactive row — `lib/features/product_detail/widgets/`

| Concern | File:line | Replace with |
|---|---|---|
| Name | `ingredients_card.dart:268-271` | `display_label` (single read). |
| Role helper | `ingredients_card.dart:246-260` (`_roleHelper()`) | `display_role_label` direct read. Delete the `functional_roles[]` vocab lookup logic — the pipeline ships the prettified string now. |
| Severity dot color | `inactive_color.dart:38-53` | `severity_status` enum → color: `critical`→red, `informational`→orange, `suppress`→grey, `n/a`→no dot. Delete `severity_level` mapping. |
| RBU vs Tradeoffs split | `tradeoffs_section.dart:113-131` | Filter `severity_status == "critical"` for RBU; `"suppress"` and `"informational"` for Tradeoffs. Silicon dioxide auto-routes correctly. Delete the `severity_level` high+moderate counter. |

### Optional but worth it

Introduce a typed `Ingredient` Freezed model so future contract additions surface as compile-time errors instead of silent drops. Today Flutter reads `Map<String, dynamic>` and any field rename ships unnoticed. Scope creep but pays for itself the next time we add a contract field.

---

## Step 4 — Flutter widget tests

Minimum tests pinning the new contract reads. Add to `/Users/seancheick/PharmaGuide ai/test/features/product_detail/`.

| Test | Given | Expect |
|---|---|---|
| Active form helper renders contract | blob with `display_form_label="Retinyl Palmitate"` | row shows "Retinyl Palmitate" |
| Active dose label renders contract | `display_dose_label="1.05 mg"`, `dose_status="disclosed"` | row shows "1.05 mg", does NOT show "Dose not disclosed" |
| Active unknown form is explicit | `form_status="unknown"`, `display_form_label=null` | helper line is hidden OR shows "Form not disclosed" intentionally — never a blank slot |
| Inactive role label renders contract | inactive with `display_role_label="Anti-caking agent"` | row shows "Anti-caking agent" |
| Inactive severity routing is correct | inactive with `severity_status="suppress"`, `is_safety_concern=false` | NOT routed to Review-Before-Use; appears only in Tradeoffs |
| Inactive critical routing is correct | `severity_status="critical"`, `is_safety_concern=true` | DOES appear in Review-Before-Use |

---

## Step 5 — Deprecation cleanup (one delete commit per field)

**Status (2026-05-05): COMPLETE.** All four legacy fields deleted from
`build_final_db.py` with regression-test pins. Flutter consumers
migrated in tandem.

| Field | Pipeline commit | Flutter commit |
|---|---|---|
| `form` (active row) | `7cac39c` | `66ec68b` |
| `match_method` + `matched_alias` (inactive) | `8b0f9ea` | n/a — zero Flutter reads |
| `severity_level` (inactive only) | `7a9748e` | `8354c01` (fallback to harmful_severity) |
| `is_harmful` (active + inactive) | `8483b0c` | n/a — zero Flutter reads |

### Active ingredient row

| Field | Replacement |
|---|---|
| `form` | `display_form_label` |

### Inactive ingredient row

| Field | Replacement |
|---|---|
| `severity_level` | `harmful_severity` (same value, picked one — duplicate semantics) |
| `match_method` | move to `_debug` subkey, Flutter never reads it |
| `matched_alias` | move to `_debug` subkey, same |

### Both

| Field | Replacement |
|---|---|
| `is_harmful` (legacy semantics) | `is_safety_concern` for routing decisions; keep `is_harmful` as renamed `is_in_harmful_db` provenance flag if useful, else delete entirely |

### Empty-string vs null cleanup

Convert empty-string defaults to `null` on inactive fields where unpopulated:
- `category`, `additive_type`, `severity_level`, `match_method`, `matched_alias`, `notes`, `mechanism_of_harm`

This eliminates the empty-vs-null ambiguity Flutter has to handle today.

### Snapshot refresh — DONE 2026-05-05

The 31 stale snapshot drift failures (`E_dose_adequacy.max: 3.0 -> 2.0`)
from the omega-3 bonus cap (commit `7ceac0d`) refreshed via
`python3 scripts/tests/freeze_contract_snapshots.py`. Manifest changelog
entry added. All 32 snapshot tests pass.

---

## Step 6 — Resume product-detail refactor

Sequencing matters: the contract migration MUST land before Phase 4 (ingredient row redesign) because Phase 4 depends on the new dose/form fields rendering correctly.

| Step | Status | Note |
|---|---|---|
| Contract migration (this doc, Steps 1-5) | LANDED 2026-05-05 | Pipeline + Flutter both shipped; deprecation deletes deferred until two remaining Flutter consumers migrate |
| Sticky CTA fix | next | Independent of contract |
| Personalized warnings provider | next | Independent of contract |
| ReviewBeforeUseCard | UNBLOCKED — severity_status routing live | |
| LabelConfidenceCard | next | Independent of contract |
| Ingredient row redesign (Phase 4) | UNBLOCKED — contract fields populated | |

---

## Open questions — RESOLVED 2026-05-05

- For the `_debug` subkey on inactives — should `match_method` / `matched_alias` move there, or just delete? → **DELETED** (commit `8b0f9ea`). Flutter never read them.
- For `is_harmful` — keep as a renamed provenance flag (`is_in_harmful_db`) or delete? → **DELETED** (commit `8483b0c`). No consumer needed the provenance signal.
- For empty-string-vs-null cleanup — sweep all data-file emit sites or just the inactive row builder? → **Scoped to inactives** as planned. Wider sweep stays deferred until a concrete need surfaces.

---

## Probiotic UX follow-ups (dev audit 2026-05-05)

| # | Item | Status |
|---|---|---|
| 1 | `ProbioticDetailSection` reads non-existent `strains` / `survivability` keys; `total_cfu` via `safeString` on a numeric | ✅ Fixed — Flutter `f190890` |
| 2 | CFU not formatted for display | ✅ Fixed — pipeline emits `total_cfu_label` (`2a3b893`); Flutter has numeric fallback for older blobs |
| 3 | Per-strain `cfu_per_day` / `evidence_level` not consumed | ✅ Fixed — Flutter `f190890` (`_StrainRow` renders `clinical_strains[]` with CFU + evidence + postbiotic badge) |
| 4 | Active-row "Amount not disclosed" wording on probiotic blend members reads as opacity | ✅ Fixed — pipeline overrides to "Per-strain dose not listed" when ingredient is a probiotic strain in a probiotic product |
| 5 | DSLD source gaps for some SKUs (e.g. PureProbiotic) — DSLD's structured import didn't capture CFU even though the label shows it | ⏸ DEFERRED — out of session scope. Two paths: (a) manual override JSON for popular SKUs (small, durable); (b) manufacturer-feed enrichment (bigger lift, right answer long-term). Re-evaluate after T7D rebuild surfaces how many real products are affected. |

---

## Definition of done — status as of 2026-05-05

- [x] Fresh pipeline run completes; corpus carries v1.5.0 contract fields. (8331 blobs in `scripts/dist/detail_blobs/`, schema v1.5.0)
- [x] All six target products in Step 2 verified by hand. (Vitamin A Palmitate / Vitamin A unspecified / Mg oxide / Mg glycinate / prop-blend not_disclosed_blend / EPA form_status=unknown — all confirm contract fields populate as designed)
- [x] Flutter PR merged: 8 surgical edits + new widget tests green. (commit `f9181e6` on Flutter main; 49 widget tests pass)
- [x] Release gate `test_no_form_sensitive_violations_in_build_output` runs (no skip) and passes on the rebuilt corpus. (commit `f18c895` patched the gate to probe both `dist/` and `final_db_output/` paths)
- [x] Snapshot refresh — 30 fixtures regenerated via `freeze_contract_snapshots.py`, manifest changelog entry added.
- [x] Deprecation cleanup commits — DONE 2026-05-05. Four per-field deletes shipped with regression test pins (see Step 5 table for commit hashes).
- [x] Phase 4 ingredient row redesign unblocked — contract fields are live in production blobs.
