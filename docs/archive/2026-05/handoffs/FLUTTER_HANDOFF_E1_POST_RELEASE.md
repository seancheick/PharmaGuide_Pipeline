# Flutter Handoff — E1 Release (2026-04-22)

**Pipeline release:** `v2026.04.22.184608` (Supabase live)
**Addendum:** `v2026.04.22.E1.5.X-4` (in-flight; adds fields below)
**From:** Pipeline team
**To:** Flutter team
**Purpose:** Six UI bugs + one UX redesign surfaced during post-release smoke test. Four pipeline-side fields change shape in E1.5.X-4 (small, backward-compatible).

---

## 🔴 FLTR-1 — CRITICAL: profile filter is broken

**What users see:** A male user (no pregnancy in profile) sees "Do not use during pregnancy" warnings on Vitamin A products. Same issue will fire for any profile-gated condition (lactation, liver disease, kidney disease, bleeding disorders, etc.) against users who don't match.

**Root cause:** Pipeline emits warnings with `display_mode_default='suppress'` and `condition_ids=[...]` metadata, expecting Flutter to filter on device. Flutter is ignoring the filter and rendering all warnings regardless of profile.

**Pipeline contract (already in blob):**

```json
{
  "type": "interaction",
  "severity": "contraindicated",
  "display_mode_default": "suppress",     ← key field
  "condition_ids": ["pregnancy"],
  "drug_class_ids": [],
  "authored_body": "..."
}
```

**Flutter rendering rule (what it should be):**

```
if warning.display_mode_default == "suppress":
    # Only show if user's profile matches at least one tag
    show = any(cid in user.conditions for cid in warning.condition_ids)
         or any(did in user.drug_classes for did in warning.drug_class_ids)
else:
    # "informational" / "alert" / "critical" → always show
    show = True
```

**Test cases:**
- Male user, no conditions → sees zero pregnancy warnings on Thorne Vit A (DSLD 15640)
- Female user with `pregnancy` in profile → sees the contraindicated warning
- User with `liver_disease` in profile → sees the liver warning on Vit A

**Priority:** HIGH — safety UX. Ship before next internal test cycle.

---

## 🔴 FLTR-2 — use `display_label` instead of `name`

**What users see:** Label on bottle says "Vitamin A Palmitate". App shows "Vitamin A" (generic). Loses form specificity that drives safety decisions (retinyl palmitate has different UL profile than beta-carotene).

**Root cause:** Flutter is reading `ingredients[].name`. Should read `ingredients[].display_label` which is populated by E1.2.2.

**Pipeline fields per ingredient (in blob):**

| Field | Current Flutter reads | Correct | Example |
|---|---|---|---|
| `name` | ✅ (legacy) | — | "Vitamin A" (canonical) |
| `display_label` | ❌ | ✅ | **"Vitamin A Palmitate"** (as-labeled) |
| `display_dose_label` | ❌ | ✅ | "25000 IU" (pre-formatted) |
| `standardization_note` | ❌ | ✅ | null OR "Standardized to 95% curcuminoids" |
| `display_badge` | ❌ | ✅ | "no_data" / "well_dosed" / "under_dosed" / etc |

**Priority:** MEDIUM. Landing makes the app feel much more honest.

---

## 🟡 FLTR-3 — three-tier UX redesign (noise reduction)

**What users see:** 4 inactive ingredients rendered as prominent green "Safe" chips ("inert cellulose filler", "anti-caking agent", etc.) competing for attention with real safety/trust info.

**User quote:** *"we should skip the safe one, it's just extra noise"*

**Recommended pattern:** five-layer hierarchy that decouples **severity from data type**. This is how a "smart pharmacist" communicates — alerts are serious, tradeoffs are neutral, concerns are soft.

### Five-layer product-detail structure

```
┌─ 🧠 DECISION (prominent, top) ──────────────────────────────────
│  Score: 87 / 100
│  Verdict: Safe  ·  Grade: Good
└─────────────────────────────────────────────────────────────────

┌─ ⚡ WHY THIS SCORE (the evidence) ───────────────────────────────
│  ✓ High-quality ingredient forms
│  ✓ Strong clinical backing
│  ✓ Third-party tested
│  ✓ Trusted manufacturer
│  — Minor transparency gaps
└─────────────────────────────────────────────────────────────────

┌─ ⚖️ TRADEOFFS (decision caveats, neutral tone) ─────────────────
│  • Uses proprietary blend
│  • Limited dose disclosure
└─────────────────────────────────────────────────────────────────

┌─ ⚠️ CONSIDER (soft signals, small, grey) ──────────────────────
│  • Product discontinued · Nov 28, 2017   ← product_status.display
│  • Contains added sugar
│  • High filler load (1 active, 4 fillers)
└─────────────────────────────────────────────────────────────────

┌─ 🚨 ALERTS (ONLY real safety, profile-filtered) ────────────────
│  Interaction with Warfarin
│  Exceeds UL for Vitamin A
└─────────────────────────────────────────────────────────────────

┌─ INGREDIENTS (ordered by importance) ───────────────────────────
│  Actives:
│    › Vitamin A Palmitate · 25000 IU · no_data    ← display_label
│  Inactives (collapsed):
│    ▸ 4 inactive ingredients — all recognized  [tap to expand]
└─────────────────────────────────────────────────────────────────
```

**Layer semantics (critical — don't mix):**

| Layer | Data type | Tone | Sources |
|---|---|---|---|
| 🧠 Decision | Score + verdict | Declarative | `score_100_equivalent`, `verdict`, `grade` |
| ⚡ Why | Positive scoring signals | Affirmative | `score_bonuses[]`, certifications, D1 trust |
| ⚖️ Tradeoffs | Quality caveats | Neutral | `score_penalties[]` (B1/B2/B5 low-severity) |
| ⚠️ Consider | Soft context signals | Calm | `product_status`, `proprietary_blend_detail`, sugar level |
| 🚨 Alerts | Safety + interactions | Serious | `warnings[]` (after profile filter), UL exceeded |

**Why this works:**
- Decision reads like a pharmacist's summary, not a spreadsheet
- Real safety alerts stand out because they're not buried under 12 green chips
- Discontinued status lands in Consider (where it belongs) — not mixed with interaction warnings
- Transparency preserved (excipients collapsed, expandable)
- Mirrors patterns users already trust: Labdoor, Examine, Perfect Supps

**Anti-pattern to avoid:** a single grid of "safe/warning" chips flattens all severities to equal visual weight — users can't tell a banned substance from an anti-caking agent at a glance. Hierarchy IS the message.

**Priority:** MEDIUM — biggest user-perceived quality improvement.

---

## 🟢 FLTR-4 — use new `product_status` top-level dict (E1.5.X-4 change)

**Pipeline change (coming in E1.5.X-4 sync):** Discontinued/off-market products no longer emit a `type='status'` warning. Instead, a dedicated top-level blob field:

```json
{
  "product_status": {
    "type":    "discontinued",              // "discontinued" | "off_market" | future: "reformulated" | "limited_availability" | "seasonal"
    "date":    "2022-12-13",                // ISO date string, may be null
    "display": "Discontinued · 2022-12-13"  // pre-formatted for verbatim rendering
  }
}
```

**Schema note:** field is `product_status` (dict). Inner key is `type` (not `status`) so the contract can grow beyond discontinuation without breaking. `display` is pre-formatted by the pipeline so Flutter renders verbatim — no locale-dependent date logic needed.

For active products: `"product_status": null` → Flutter hides the chip entirely.

**Why it changed:** Status was mis-rendering as a green SAFE chip ("discontinue product" shown next to "third-party tested"). Availability is neither a safety warning nor a positive signal — it's a neutral concern. Belongs in the "⚠️ Consider" (soft-signal) UI layer.

**Flutter rendering rule:**
```
if product_status != null:
    render small concern chip: product_status.display
    // Styling: grey/neutral, small, single-line
    // Placement: "⚠️ Consider" soft-signal layer
    // Grouping: merge with other concerns (proprietary blend, etc.)
    //          — SAME visual layer, NOT a separate section
    // NEVER style as alert / red / warning banner
else:
    hide entirely
```

**Transitional note:** During the overlap period (before all Supabase versions rerun with E1.5.X-4), cached blobs may still carry `type='status'` warnings from v2026.04.22.184608. Safe to filter both ways:
```
warnings = [w for w in warnings if w.type != 'status']  // drop legacy
if product_status != null: render concern chip
```

**Priority:** MEDIUM. Pairs with FLTR-3 (Consider tier).

---

## 🟢 FLTR-5 — UL fallback uses `highest_ul` (E1.5.X-4 fix)

**What E1.5.X-4 fixes on pipeline side:** Previously `rda_ul_data.ingredients_with_rda[*].highest_ul` was `null` for ~57% of entries (every time the pipeline's own UL check was skipped due to form ambiguity). This broke Flutter's anonymous-user fallback on those products.

**After E1.5.X-4:** `highest_ul` is ALWAYS populated when the nutrient exists in the RDA table. Flutter's existing logic at [lib/services/fit_score/e1_dosage_calculator.dart:126](lib/services/fit_score/e1_dosage_calculator.dart:126) and [lib/services/stack/stack_ul_checker.dart:54](lib/services/stack/stack_ul_checker.dart:54) continues working — the field is simply reliable now.

**New companion field:** `ul_for_default_profile` — the pipeline's age-specific UL (19-30 / both) used when the pipeline computed a score. Distinguishes "profile-specific UL" from "absolute max UL" for consumers that want both.

**No Flutter code change required** — the behavior is already correct. The blob gets more trustworthy.

**Priority:** AUTO-FIXED by E1.5.X-4 sync.

---

## 🟡 FLTR-6 — inactive ingredient tags rendered multiple times

**What users see:** "inert cellulose filler", "anti-caking agent", "discontinue product" all appear **two or three times** in the inactives section.

**Root cause (suspected):** Flutter side — iteration bug rendering the same list twice, or rendering `inactive_ingredients[]` + `dietary_sensitivity_data.additives[]` both as the same visual type.

**Pipeline verification:** `inactive_ingredients[]` in the blob for DSLD 15640 has 4 unique items, no duplicates. The duplication is a Flutter rendering issue.

**Priority:** LOW — cosmetic, not safety.

---

## 🟢 FLTR-7 — housekeeping: remove stale RDA file

File `data/rda_optimal_uls.json` in the Flutter repo root is a stale dev copy (hash `91f64e5e…`) that doesn't match the bundled `assets/reference_data/rda_optimal_uls.json` (hash `202a3b49…`, which does match the pipeline's source). The app uses the `assets/` version at runtime; the `data/` copy is unused.

**Action:** delete `data/rda_optimal_uls.json` to prevent future drift + developer confusion.

**Priority:** LOW — cleanup.

---

## 🧠 Architectural context — dose-threshold gating (user-raised)

User raised an important clinical point after smoke test:

> *"It's not because one ingredient is found in a multivitamin that it should automatically flag it. Vitamin A is a warning for pregnant women. It still comes with a limit before it flags. It could be 2 mg, it could be 5 mg. We cannot just flag it and just fire."*

**Current behavior (pipeline side):** Condition-specific warnings like "avoid high-dose Vitamin A in pregnancy" fire based on **presence of the ingredient**, regardless of dose. A prenatal multivitamin at 800 mcg RAE (adequately dosed) gets the same red alert as a 25,000 IU retinol supplement.

**Correct behavior:** Warnings that are dose-sensitive must check the user's daily dose against a `dose_threshold` before firing.

**Pipeline-side work (separate ticket — E1.5.X-6):**
- Populate `dose_thresholds` in `ingredient_interaction_rules.json` for dose-sensitive rules (already partial — caffeine has it; Vit A, B6, D, berberine, magnesium, iron all need them)
- Scorer gates warning emission on `dose_threshold` when the rule specifies one
- No threshold defined → fall back to `highest_ul` for the condition's UL (conservative)

**Flutter-side work (parallel — NO NEW FIELDS NEEDED):** When condition-matched warnings DO fire (profile filter from FLTR-1), render them trusting the pipeline's gate decision. The dose check is upstream.

**Timing:** This ticket blocks "warning quality" more than "release safety". Schedule post-E1.5.X.

---

## 📦 Summary table

| ID | Issue | Owner | Priority | Blocks |
|---|---|---|---|---|
| FLTR-1 | Profile filter broken (display_mode_default='suppress') | Flutter | 🔴 HIGH | next release |
| FLTR-2 | Use `display_label` not `name` | Flutter | 🟡 MED | — |
| FLTR-3 | Three-tier UX redesign | Flutter | 🟡 MED | — |
| FLTR-4 | Use `product_status_detail` (new E1.5.X-4 field) | Flutter | 🟢 MED | pairs with FLTR-3 |
| FLTR-5 | `highest_ul` now reliable | Flutter | auto | — |
| FLTR-6 | Inactive tag duplication (iteration bug) | Flutter | 🟢 LOW | — |
| FLTR-7 | Delete stale `data/rda_optimal_uls.json` | Flutter | 🟢 LOW | — |
| E1.5.X-4 | Pipeline: always emit `highest_ul` + `product_status_detail` | Pipeline | ✅ in-flight | FLTR-4/5 |
| E1.5.X-6 | Pipeline: dose-threshold gating on warnings | Pipeline | MED | warning quality |

---

## 🔄 Sync points

**When FLTR-1 ships:** coordinate with pipeline team on any missing `condition_ids` or `drug_class_ids` in warnings — Flutter's filter only works if the pipeline tagged the warning correctly.

**When E1.5.X-4 syncs to Supabase:** Flutter needs the new `product_status_detail` field handler (FLTR-4) ideally same deploy cycle. The legacy `type='status'` warning stops appearing on that version forward.

**When FLTR-3 (three-tier UX) ships:** consider a coordinated release — it's the biggest perceived-quality jump since the app was built. Worth a changelog line.

---

## Contact

- Pipeline + blob questions: see `scripts/FINAL_EXPORT_SCHEMA_V1.md` + `scripts/PIPELINE_OPERATIONS_README.md`
- Warning taxonomy: see [`scripts/data/clinical_risk_taxonomy.json`](../scripts/data/clinical_risk_taxonomy.json) for the canonical `condition_ids` / `drug_class_ids` enums Flutter's profile should match against
- Release ledger: [`docs/SPRINT_E1_RELEASE_CHECKPOINT.md`](SPRINT_E1_RELEASE_CHECKPOINT.md)
