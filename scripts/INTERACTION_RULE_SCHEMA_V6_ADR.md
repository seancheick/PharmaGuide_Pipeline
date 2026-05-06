# ADR — Interaction Rule Schema v6.0 (`profile_gate`)

**Status:** APPROVED with revisions (2026-05-05) — ready for implementation
**Date:** 2026-05-05
**Authors:** PharmaGuide pipeline + clinical team, ADR draft by Claude, revisions per clinical reviewer feedback
**Affects:** `scripts/data/ingredient_interaction_rules.json`, `clinical_risk_taxonomy.json`, `enrich_supplements_v3.py`, `build_final_db.py`, Flutter app `assets/db/` consumer
**Schema bump:** rule file 5.3.3 → **6.0.0**; catalog DB 1.5.0 → **1.6.0**
**Related:** `scripts/INTERACTION_RULE_AUTHORING_SOP.md`, `scripts/CONTRACT_V150_FOLLOWUP.md`

---

## Problem statement

The current rule file (5.3.3) relies on **implicit gating**: Flutter is expected to know that a sub-rule with `condition_id: "diabetes"` should only fire when the user's profile has `diabetes`. There is no explicit field that says *"fire this only if the user is X"*.

That works for the four rule shapes we have today (condition / drug-class / pregnancy-lactation / dose-threshold) but breaks down as soon as we want any of:

- **Medication-aware escalation** (e.g., berberine: caution by default, avoid only with insulin/sulfonylurea) — currently force-encoded by duplicating sub-rules across `condition_rules` AND `drug_class_rules`, which is fragile and untestable.
- **Form exclusions** (e.g., topical aloe should not trigger oral-aloe pregnancy alerts) — currently expressed only in `mechanism` prose, which Flutter cannot evaluate.
- **Nutrient-form gating** (e.g., vitamin A pregnancy UL applies to retinol, not beta-carotene) — partially solved with `form_scope` but inconsistent across rules.
- **Cross-source dose summation** (e.g., total daily caffeine across all products in a stack) — currently `per_day` per supplement only.
- **Diagnosis specificity** (e.g., heart_disease as a broad bucket vs. specific subconditions like prior-MI) — clinical review (5.3.3 batch) flagged that future profile depth needs a clean upgrade path.

5.3.x has been a series of content patches that paper over these gaps. v6.0 is the schema migration that makes the contract explicit so Flutter stops guessing and the rule file becomes mechanically enforceable.

---

## Decision

Add a single new field, **`profile_gate`**, to every sub-rule in `condition_rules[]`, `drug_class_rules[]`, the migrated pregnancy/lactation rules, and to each `dose_thresholds[]` entry. The gate is a structured, deterministic predicate: Flutter (or any consumer) evaluates it against the user profile + product context to decide whether a rule fires.

```jsonc
"profile_gate": {
  "gate_type": "condition | drug_class | profile_flag | dose | nutrient_form | combination",
  "requires": {
    "conditions_any":     [],   // user has ANY of these conditions
    "drug_classes_any":   [],   // user takes a drug in ANY of these classes
    "profile_flags_any":  []    // user has ANY of these lifecycle/risk flags
  },
  "excludes": {
    "conditions_any":     [],
    "drug_classes_any":   [],
    "profile_flags_any":  [],
    "product_forms_any":  [],   // product form excluded from this rule
    "nutrient_forms_any": []    // nutrient form excluded (e.g. beta_carotene from vitamin A pregnancy rule)
  },
  "dose":  null   // optional dose predicate; replaces / unifies dose_thresholds[]
}
```

### Semantics

- **`requires` is AND across populated keys, OR within each list.** A rule fires only when every populated key has at least one match against the user profile/product.
- **`excludes` is OR — any match suppresses the rule.** Use for product-form exclusions (topical aloe), nutrient-form exclusions (beta-carotene from vitamin A retinol gate), or contraindication carve-outs.
- **`dose` is optional.** When present, it modifies `severity` after the gate matches; when absent, severity is taken as the sub-rule's static `severity` field.

### Gate type semantics + strict validator rules

The validator MUST enforce that each `gate_type` populates only its expected `requires` keys. This prevents accidental under-firing from misconfigured gates.

| `gate_type` | When to use | `requires` keys allowed |
|---|---|---|
| `condition`     | Patient-condition rule (diabetes, hypertension, etc.) | **only** `conditions_any` |
| `drug_class`    | Drug-class interaction (anticoagulants, statins) | **only** `drug_classes_any` |
| `profile_flag`  | Pregnancy / TTC / breastfeeding / surgery / post-op / hypoglycemia history / bleeding history | **only** `profile_flags_any` |
| `dose`          | Pure dose-threshold with no profile predicate | (none required); `dose` field required |
| `nutrient_form` | Nutrient-form-specific gate (rare standalone; usually appears as `excludes.nutrient_forms_any` on another gate) | typically composed with `combination` |
| `combination`   | Multi-axis gate (e.g., diabetes AND insulin) | any 2+ of `conditions_any` / `drug_classes_any` / `profile_flags_any` |

Failure modes the validator catches:
- `gate_type=condition` with `drug_classes_any` populated → ERROR (must use `combination`)
- `gate_type=drug_class` with `conditions_any` populated → ERROR (must use `combination`)
- `gate_type=profile_flag` with `conditions_any` populated → ERROR (must use `combination`)
- `gate_type=combination` with only one populated `requires` key → WARN (downgrade to specific gate type)
- `gate_type=dose` with `dose` field absent → ERROR
- Any `nutrient_forms_any` value missing from `form_keywords_vocab.json` → ERROR
- Any `product_forms_any` value missing from `clinical_risk_taxonomy.product_forms[]` → ERROR

### Profile flag vocabulary (initial)

Flat list. **No trimester logic** per project decision (2026-05-05). **No subconditions yet** (heart_disease, kidney, liver remain conditions, not flags, because Flutter already captures them as conditions).

```
pregnant
trying_to_conceive
breastfeeding
post_op_recovery
surgery_scheduled
hypoglycemia_history       # for medication-aware escalation
bleeding_history           # for anticoagulant escalation
```

Lives in `clinical_risk_taxonomy.json` under a new `profile_flags[]` array (additive; does not affect existing taxonomy).

### Product-form vocabulary (initial)

New `product_forms[]` block in `clinical_risk_taxonomy.json`. Start small:

```
topical_only
oral
capsule
tablet
powder
liquid_oral
culinary_turmeric
high_potency_extract
unknown
```

Used by `excludes.product_forms_any` (e.g., topical aloe excluded from pregnancy alert).

---

## What `profile_gate` is NOT

Important boundary calls so this doesn't bloat:

1. **Not a clinical explanation.** Mechanism / action / alert_body stay where they are. The gate only carries the *decision predicate*.
2. **Not a severity modifier on its own.** Severity is on the sub-rule. `dose` block can override severity, but the gate cannot.
3. **Not an action prescription.** The action field stays where it is.
4. **Not a Flutter UI hint.** No display-priority, no styling.
5. **No trimester sub-flags** (per your call). When the engine eventually carries trimester data, it can be added additively.
6. **No subcondition refinement** (e.g., `heart_failure` under `heart_disease`). Future-proofed via `requires.conditions_any` — when subconditions land in the taxonomy, rules are updated additively without schema change.
7. **No backend-side user-profile evaluation in Phase 2.** The pipeline emits the gate; Flutter evaluates it at render time against the local user profile. Backend is the authoring + transport layer only. **A shared deterministic evaluator test fixture** (defined in Python first, mirrored in Dart) MUST exist so the clinical gate logic does not drift between platforms — this is required as part of Step 6.

---

## Two-rule escalation pattern (no `escalate_if`)

Medication-aware severity escalation uses **two sub-rules** with different gates, where the most-specific applicable gate wins by precedence (highest severity among matching gates).

Example — berberine + diabetes meds:

```json
// Rule A — caution baseline for any diabetic
{
  "condition_id": "diabetes",
  "severity": "caution",
  "profile_gate": {
    "gate_type": "condition",
    "requires": { "conditions_any": ["diabetes"] }
  }
  // mechanism, action, alert_headline, etc. unchanged
}

// Rule B — avoid escalation for higher-hypoglycemia-risk meds
{
  "condition_id": "diabetes",
  "severity": "avoid",
  "profile_gate": {
    "gate_type": "combination",
    "requires": {
      "conditions_any":   ["diabetes"],
      "drug_classes_any": ["insulin", "sulfonylureas", "meglitinides"]
    }
  }
}
```

Flutter evaluation:
1. Iterate sub-rules; collect all whose `profile_gate` matches the user.
2. Among matches, take the highest severity (and dedupe by subject).
3. Render that one alert.

This keeps the schema flat, makes precedence testable, and avoids a special escalation engine.

> **Phase 3 TODO**: split the broad `hypoglycemics` drug class into specific subclasses — `insulin`, `sulfonylureas`, `meglitinides` (high-hypoglycemia-risk) vs `metformin`, `glp_1_receptor_agonists`, `sglt2_inhibitors`, `dpp_4_inhibitors` (lower-risk). For Phase 2, keep `hypoglycemics` for backward compatibility but mark for splitting.

---

## Migration plan (deterministic, mechanical)

A migration script `scripts/tools/migrate_to_profile_gate.py` populates `profile_gate` on every sub-rule by reading the existing structure. **No clinical judgment in the migration.** All 145 rules covered.

| Source location | Generated `profile_gate` |
|---|---|
| `condition_rules[].condition_id="diabetes"` | `{gate_type:"condition", requires:{conditions_any:["diabetes"]}}` |
| `condition_rules[].condition_id="hypertension"` | `{gate_type:"condition", requires:{conditions_any:["hypertension"]}}` |
| `condition_rules[].condition_id="pregnancy"` | `{gate_type:"profile_flag", requires:{profile_flags_any:["pregnant","trying_to_conceive"]}}` |
| `condition_rules[].condition_id="lactation"` | `{gate_type:"profile_flag", requires:{profile_flags_any:["breastfeeding"]}}` |
| `condition_rules[].condition_id="ttc"` | `{gate_type:"profile_flag", requires:{profile_flags_any:["trying_to_conceive"]}}` |
| `condition_rules[].condition_id="surgery_scheduled"` | `{gate_type:"profile_flag", requires:{profile_flags_any:["surgery_scheduled"]}}` |
| `drug_class_rules[].drug_class_id=*` | `{gate_type:"drug_class", requires:{drug_classes_any:[<id>]}}` |
| `pregnancy_lactation` block | Split into two sub-rules: one with `profile_flags_any:["pregnant","trying_to_conceive"]`, one with `["breastfeeding"]`, each carrying severity from the source block's `pregnancy_category` / `lactation_category` |
| `dose_thresholds[].scope="condition"` | `{gate_type:"combination", requires:{conditions_any:[target_id]}, dose:{...}}` |
| `dose_thresholds[].scope="drug_class"` | `{gate_type:"combination", requires:{drug_classes_any:[target_id]}, dose:{...}}` |
| `dose_thresholds[].scope="profile_flag"` (new) | `{gate_type:"combination", requires:{profile_flags_any:[target_id]}, dose:{...}}` |
| `dose_thresholds[].scope=None / pure-dose` | `{gate_type:"dose", dose:{...}}` |

Hand-applied refinements (post-migration, separate commits):
- **Vitamin A pregnancy** — add `excludes.nutrient_forms_any:["beta_carotene","mixed_carotenoids"]`. Validator confirms IDs exist in `form_keywords_vocab.json`.
- **Aloe pregnancy** — add `excludes.product_forms_any:["topical_only"]`.
- **Curcumin pregnancy** — add `excludes.product_forms_any:["culinary_turmeric"]`.
- **Berberine diabetes** — split into baseline `caution` rule + escalation `avoid` rule (two-rule form, see above).

---

## Coordination with v1.5.0 Flutter migration

User's in-progress v1.5.0 catalog migration (`CONTRACT_V150_FOLLOWUP.md`) must ship FIRST. **Sequence is non-negotiable** — mixing the two migrations creates debugging hell.

1. Finish v1.5.0 Flutter migration → ship → users on v1.5.0
2. Update Flutter `APP_SUPPORTED_SCHEMAS` to include `1.5.0`
3. Re-run release step 6/7 (Supabase already has v1.5.0 catalog from earlier today)
4. **Begin Phase 2** — pipeline-side work proceeds in parallel through Step 8
5. Coordinate Flutter v1.6.0 read of `profile_gate` (Step 9)
6. Add `1.6.0` to `APP_SUPPORTED_SCHEMAS`
7. Ship

Pipeline-side Steps 2–8 do not depend on Flutter and can land on `main` immediately. Step 9 waits for the Flutter team.

---

## Implementation steps (post-ADR approval)

Each step is its own atomic commit. No commit modifies more than one stage.

### Step 1: Schema design (this ADR)
**Status: APPROVED with revisions (2026-05-05).**

### Step 2: Taxonomy expansion
- `scripts/data/clinical_risk_taxonomy.json`: add `profile_flags[]` and `product_forms[]` blocks.
- Bump taxonomy schema (additive change).
- Add `scripts/tests/test_profile_flags_vocab_contract.py` and `test_product_forms_vocab_contract.py`.

### Step 3: Migration script + dry-run
- `scripts/tools/migrate_to_profile_gate.py` produces a **diff preview** (does not write) by default; `--apply` flag writes.
- Includes structural test that asserts every sub-rule gets a non-null `profile_gate` after migration, and that `gate_type` matches the source structure.

### Step 4: Apply migration to rule file
- Run `--apply`.
- Bump schema 5.3.3 → **6.0.0** (major bump because `profile_gate` is required).
- Add migration entry to `_metadata`.

### Step 5: Hand-applied refinements
- One commit per refinement: vitamin A excludes carotenoids, aloe excludes topical, curcumin excludes culinary, berberine two-rule escalation.
- Authoring helper `add_rule.py` updated to emit `profile_gate` automatically (defaults from `--condition` / `--drug-class` / new `--profile-flag` flag).

### Step 6: Validator + shared evaluator fixture
- `validate_safety_copy.py`: every sub-rule MUST have `profile_gate`; `gate_type` must match the strict-keys table above; referenced IDs must exist in their vocabularies.
- New tests:
  - `test_profile_gate_contract.py` (every sub-rule has valid gate; strict per-type validation).
  - `test_profile_gate_taxonomy_contract.py` (all referenced IDs exist).
  - `test_profile_gate_migration.py` (round-trip on fixture).
- **Shared evaluator fixture** (`scripts/data/profile_gate_test_cases.json`): a Python+Dart-readable spec of `(user_profile, product_context, rule, expected_fires)` triples. Both languages MUST pass the same fixture to prevent drift.

### Step 7: Enricher passthrough
- `enrich_supplements_v3.py:_collect_interaction_profile` (line 11781): copy `profile_gate` from rule into emitted `safety_hits[]` entries and `interaction_profile.condition_summary[]`.
- Test fixture: scan a known product, assert `profile_gate` present on every emitted safety hit.

### Step 8: Final-DB export
- `build_final_db.py` (lines 2427/2462/2824/2850): include `profile_gate` in detail_blobs.
- Bump catalog DB schema **1.5.0 → 1.6.0**.
- Update `APP_SUPPORTED_SCHEMAS` whitelist in `import_catalog_artifact.sh` (Flutter repo).

### Step 9: Flutter consumer
- Drift contract: add `profile_gate` JSON column to safety_hits / condition_summary tables (or store as embedded JSON if simpler).
- Alert-rendering layer: implement the same evaluator the Python fixture defines:
  1. Iterate sub-rules; collect those whose `profile_gate.requires` matches user + `excludes` does NOT match.
  2. Take highest severity per subject.
  3. Render.
- Widget tests for both directions:
  - User with `profile_flags_any=["pregnant"]` → CBD pregnancy alert renders
  - User without `pregnant` flag → CBD pregnancy alert does NOT render
  - User with `topical_only` aloe product → no aloe pregnancy alert
  - User with insulin in `drug_classes` → berberine renders `avoid` alert (escalation rule wins)
  - User with vitamin A retinol form → pregnancy alert renders; user with beta-carotene → does NOT render
- Run shared evaluator fixture in Dart — must pass identically to Python.

### Step 10: End-to-end verification
- Pipeline run on 6 target products with known interaction profile (CBD, retinol-form vitamin A, oral aloe, topical aloe, ginger, fish-oil).
- Detail blobs inspection: confirm `profile_gate` present in expected shape.
- Flutter staging: simulate 4–5 user profiles, verify alert firing matrix.
- Promote to production.

---

## Decisions locked (per clinical review 2026-05-05)

✅ **Field shape**: `gate_type`, `requires`, `excludes`, optional `dose` — approved
✅ **Enum**: `condition | drug_class | profile_flag | dose | nutrient_form | combination` — replaces `reproductive_status` with broader `profile_flag`
✅ **Strict validator** per gate_type — approved
✅ **Surgery_scheduled** is a `profile_flag`, not a `condition`
✅ **Two-rule escalation form** — approved, no `escalate_if`
✅ **Profile flag vocabulary** — pregnant, trying_to_conceive, breastfeeding, post_op_recovery, surgery_scheduled, hypoglycemia_history, bleeding_history (no trimesters; kidney/liver stay as conditions)
✅ **`form_keywords_vocab.json`** is source of truth for `nutrient_forms_any`; validator must check membership
✅ **`product_forms[]`** new taxonomy block: topical_only, oral, capsule, tablet, powder, liquid_oral, culinary_turmeric, high_potency_extract, unknown
✅ **v1.5.0 Flutter migration first**, then Phase 2
✅ **Cross-product dose summation deferred to Phase 3** (schema permits `total_daily_exposure` basis but Flutter MUST NOT claim full support until Phase 3)
✅ **Shared evaluator fixture** required (Python+Dart) to prevent drift
✅ **`hypoglycemics` split** TODO Phase 3 — keep current broad class for v6.0; split into high-risk (insulin, sulfonylureas, meglitinides) vs lower-risk (metformin, GLP-1 RAs, SGLT2i, DPP-4i) post-launch

---

## Risk + rollback

- **Migration script bug** → produces wrong gates. Mitigation: dry-run mode, fixture round-trip test, manual diff review of a sample.
- **Pipeline regression** → enricher fails to propagate. Mitigation: pre-PR test fixture comparison.
- **Flutter parsing failure** → app crashes on missing `profile_gate`. Mitigation: defensive null check in Flutter's parser; Flutter ships one beta build that handles both pre/post-v6.0 shapes during the transition.
- **Production rollback** → revert the catalog DB to 1.5.0 in Supabase; Flutter falls back to its bundled 1.5.0. Pipeline can keep authoring 6.0.0 in source files; only the export step is rolled back.
- **Evaluator drift** → Python and Dart implementations diverge silently. Mitigation: shared `profile_gate_test_cases.json` fixture executed in both CI suites; CI fails if either language disagrees with the fixture.

---

## Success criteria

1. Every sub-rule in `ingredient_interaction_rules.json` has a non-null `profile_gate`.
2. Migration script produces deterministic output (same input → same output, byte-stable).
3. All existing 224+ tests still pass.
4. New `test_profile_gate_*` tests pass.
5. Pipeline run on a fixture product emits `profile_gate` in detail_blobs.
6. Flutter widget tests prove a non-pregnant user does NOT see pregnancy alerts that previously fired by structural inference alone.
7. Flutter end-to-end test: user toggles a profile flag → alert visibility changes accordingly without app restart.
8. Shared evaluator fixture passes identically in Python and Dart.

---

**Ready for implementation. Pipeline-side Steps 2–8 can begin immediately after this ADR commits. Step 9 (Flutter) waits for the v1.5.0 Flutter migration to ship.**
