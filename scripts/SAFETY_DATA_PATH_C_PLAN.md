# Safety Data Path C + Interaction Profile Gating — Execution Plan

**Status:** In progress (Sprint 2026-04-17)
**Owner:** Pipeline
**Cross-repo coordination:** Flutter repo at `/Users/seancheick/PharmaGuide ai/`
**Source handoff:** `../HANDOFF_PIPELINE_SAFETY_DATA.md`

---

## Problem

Two independent but related classes of silent-safety bug were identified:

1. **Derived medical copy in `banned_recalled_ingredients.json`**
   The bundled Flutter asset inherited a `warning_message` string derived from
   `"{standard_name} is {status}: {reason.split('.')[0]}"`. For ~30-40 of 139 entries
   the derived text was medically wrong (e.g., "Metformin is banned: ..." implying
   that the prescribed medication itself was banned, rather than the adulterant
   context). Flutter stripped the field in Sprint 27.6 Path A; authored replacement
   is owed upstream.

2. **Unfiltered interaction warnings firing "scary" in Flutter**
   `ingredient_interaction_rules.json` has 129 rules, 59 of which emit
   `severity: avoid` or `contraindicated` at the drug-class or condition level.
   Berberine + hypoglycemics is `avoid` — clinically correct — but the Flutter
   app renders this to *every* user scanning a berberine product, regardless of
   whether they've declared diabetes or hypoglycemic meds. The warning copy is
   also pulled straight from the rule `action` field (clinician-targeted prose),
   which reads as an alarm to a layperson.

## End-goal

User scans a product. Warnings appear **only when the user's declared profile
matches** the rule's trigger (condition, drug class, pregnancy/lactation).
Unmatched rules are either suppressed entirely or shown as neutral
informational notes. Authored, tone-calibrated copy replaces derived prose.

---

## Phased delivery

### Phase 1 — Pipeline infrastructure (no clinical authoring needed)

Goal: ship the schema, validators, and invariants so downstream authoring is
safe-by-construction.

- **1.1** Extend `banned_recalled_ingredients.json` schema (5.0.0 → 5.2.0) with
  three new optional fields per entry: `ban_context`, `safety_warning`,
  `safety_warning_one_liner`. Fields are optional during authoring transition;
  validator flips them to required on the release gate once authoring complete.
- **1.2** Extend `ingredient_interaction_rules.json` schema (5.1.0 → 5.2.0) with
  three new optional authored copy fields per `condition_rule` and
  `drug_class_rule`: `alert_headline`, `alert_body`, `informational_note`.
- **1.3** Build `scripts/validate_safety_copy.py` — shared validator for both
  files. Rules mirror the handoff doc + adds interaction-rule checks.
- **1.4** Add canonical_id lowercase invariant across all `scripts/data/*.json`
  files (Footgun C).
- **1.5** Add `_metadata.flutter_top_level_key` + `flutter_schema_version` to
  every Flutter-bundled JSON (Footgun D).
- **1.6** Tests for all of the above.

### Phase 2 — Pipeline profile-gated emission (no clinical authoring needed)

Goal: change what the pipeline writes to the detail blob so Flutter receives
profile-gated output by default.

- **2.1** Add per-hit `display_mode` enum to interaction emission in
  `build_final_db.py`: `suppress` (no profile, non-substance rule),
  `informational` (no profile but rule is material), `alert` (profile matches,
  severity caution/monitor), `critical` (profile matches, severity
  avoid/contraindicated).
- **2.2** Add per-hit `severity_contextual` — rule severity downgraded when no
  profile match (`avoid` → `informational`, `caution` → `informational`). Keep
  `severity` untouched for stack-report aggregation.
- **2.3** Emit a new `warnings_profile_gated[]` array in the detail blob —
  the subset Flutter should render by default. `warnings[]` remains as the
  superset for a future "show all interactions" toggle.
- **2.4** Regression tests for the berberine canonical case and 4 other
  representative rules (pregnancy/contraindicated, drug-class/avoid,
  condition/caution, generic/no-tag).

### Phase 3 — Flutter render contract (cross-repo)

Goal: consume the new pipeline output and fix the filter bug that causes
"fires for random conditions."

- **3.1** Fix `product_detail_screen.dart:1586` — the `return true` fallback
  means generic warnings with null `condition_id` AND null `drug_class_id`
  always render. Replace with `display_mode`-driven decision.
- **3.2** Audit every render path that reads `warnings[]` from the detail blob
  — product detail, stack screen, scanner result. Ensure each applies the
  filter or switches to `warnings_profile_gated[]`.
- **3.3** Wire `display_mode` → severity pill color/label (tone calibration:
  informational = neutral gray, monitor = blue, caution = yellow, alert/avoid
  = amber, critical/contraindicated = red).
- **3.4** "Set your health profile for personalized warnings" empty-state card
  when user has no conditions/drug classes declared and a suppressed warning
  exists.

### Phase 4 — Clinical authoring (safety-team required, NOT me)

Goal: land the authored medical copy that replaces derived prose.

- **4.1** Author `ban_context` + `safety_warning` + `safety_warning_one_liner`
  for each of 139 `banned_recalled_ingredients.json` entries, batched by
  `ban_context`:
  - `substance` family (~50 entries — DMAA, ephedra, phenibut, etc.)
  - `adulterant_in_supplements` family (~15 entries — metformin, meloxicam,
    sibutramine, sildenafil, tadalafil, phenolphthalein, etc.)
  - `watchlist` family (~20 entries — octopamine, deterenol, orange B, etc.)
  - `substance_risk` / `recalled_*` remainder (~55 entries)
- **4.2** Author `alert_headline` + `alert_body` + `informational_note` for
  each `condition_rule` and `drug_class_rule` in
  `ingredient_interaction_rules.json` (approximately 129 rules × up to 3
  copy fields per rule). Priority: the 59 avoid/contraindicated rules first,
  caution/monitor second, info last.
- **4.3** Each batch goes through safety-team review before merge. Validator
  is the enforcement gate — no entry merges if it fails the rule set.
- **4.4** Exemplar drafts provided by this plan in
  `scripts/safety_copy_exemplars/` to seed authoring.

### Phase 5 — Flutter Path C consumption

Goal: Flutter renders the new authored fields verbatim once they land.

- **5.1** `RecalledIngredientAlert` model gains `banContext`, `safetyWarning`,
  `safetyWarningOneLiner`. `bannerMessage` uses `safetyWarningOneLiner`
  verbatim, new `detailMessage` getter returns `safetyWarning`.
- **5.2** `InteractionWarning` model gains `alertHeadline`, `alertBody`,
  `informationalNote`. Render picks the field matching `display_mode`.
- **5.3** `test/core/reference_data_contract_test.dart` flips back to a
  positive assertion for the new fields AND keeps the negative assertion for
  `warning_message` (the old derived field must never return).
- **5.4** Integration tests per `ban_context` branch and per `display_mode`.

---

## Authored field contracts

### `banned_recalled_ingredients.json` per-entry

```json
{
  "ban_context": "substance" | "adulterant_in_supplements" | "watchlist" | "export_restricted",
  "safety_warning": "string, 50-200 chars, authored, risk/action verb required, no bad opener template",
  "safety_warning_one_liner": "string, 20-80 chars, ends with . or !, no semicolons"
}
```

Validator rules (Path C spec, handoff doc):
- `safety_warning` must NOT start with `"{standard_name} is "` (blocks
  derivation-template regressions).
- Must NOT start with `"<name> is a prescription"`, `"... a synthetic"`,
  `"... an FDA"` (encyclopedic openers).
- Must contain ≥ 1 verb in: `stop|avoid|consult|risk|linked|caused|associated`.
- For `ban_context == "adulterant_in_supplements"`: must contain
  `(in|within|found in|as an adulterant in).{0,40}(supplement|product|dietary)`.
- `safety_warning_one_liner` must end with `.` or `!`, no semicolons.

### `ingredient_interaction_rules.json` per-rule copy

Each `condition_rule` and `drug_class_rule` gets optional authored copy:

```json
{
  "alert_headline": "string, 20-60 chars, used as scan banner headline when profile matches",
  "alert_body": "string, 60-200 chars, shown in detail pane when profile matches",
  "informational_note": "string, 40-120 chars, shown when rule is material but no profile match"
}
```

Validator rules:
- `alert_headline` must NOT contain all-caps words of length ≥ 3 (no SCREAMING).
- `alert_body` for rules with `severity ∈ {avoid, contraindicated}` must
  contain conditional framing: `if you|when you|people who|do not combine|talk to`.
- `informational_note` must NOT contain imperative verbs like `stop`, `avoid`,
  `do not` — it's informational, not directive.

---

## Display-mode matrix

| User profile matches | Rule severity | `display_mode` | Flutter treatment |
|---|---|---|---|
| No | contraindicated | `critical` | Always shown (substance-level hazard overrides missing profile) |
| No | avoid | `informational` | Shown as neutral note or suppressed (config) |
| No | caution / monitor | `suppress` | Not rendered without profile |
| No | info | `suppress` | Not rendered without profile |
| Yes | contraindicated | `critical` | Red pill, expanded by default |
| Yes | avoid | `alert` | Amber pill |
| Yes | caution | `alert` | Yellow pill |
| Yes | monitor | `informational` | Blue pill |
| Yes | info | `informational` | Neutral pill |

Rationale: ban_context = "substance" hazards (DMAA, ephedra) should always
alarm; drug-class/condition rules should only alarm when the user is at risk.

---

## Testing discipline (from handoff doc §Testing Invariants)

Every change in this plan must ship with at least:
1. **Contract test** — positive assertion on new fields, negative assertion on
   removed/legacy fields (`warning_message` must never return).
2. **Unit test with injected fixture** — 1-3 entry synthetic payload, not a
   real-file load.
3. **Case-insensitive match test** — canonical_id comparison must be lowercase.

---

## Authoring SOP (for Phase 4)

1. Author works from `scripts/safety_copy_exemplars/*.md` templates.
2. Drafts go into a PR branch, one family per PR (substance / adulterant /
   watchlist / ...).
3. Validator runs in pre-commit; any failure blocks the commit.
4. Safety-team reviewer signs off in `scripts/data/safety_warning_review_checklist.md`.
5. After merge, sync re-runs the full pipeline so blobs regenerate with
   authored copy.
6. **No LLM-only authoring.** LLM can draft; human must review and approve.
