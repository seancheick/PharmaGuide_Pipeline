# Display Ledger Design

**Date:** 2026-03-09

## Goal

Add a user-facing display ledger that preserves what the user saw on the label without reintroducing structural rows, summary wrappers, or source descriptors into scoring logic.

## Problem

The cleaner and enricher are intentionally suppressing some rows to protect scoring accuracy:

- summary rows like `Other Omega-3's`
- wrapper/source rows like `High Choline Lecithin`
- structural parents like `Humectant`, `Soft Gel Shell`, `Acidity Regulator`

That is correct for normalization and scoring, but it creates a trust problem in UI if a user cannot find a label-visible row they saw on the bottle.

## Design Principles

- Preserve exact label text for user trust.
- Keep scoring-safe normalized ingredients separate from display-only rows.
- Never make a UI fidelity feature change scoring behavior.
- Make every suppressed row explainable.
- Prefer additive contract changes over rewriting existing scoring payloads.

## Proposed Model

Add a new top-level product field:

- `display_ingredients`

Each item in `display_ingredients` represents one label-visible row that the user may reasonably expect to see in the app.

### Display Ingredient Fields

- `raw_source_text`
  - Exact label text as seen on the panel.
- `display_name`
  - Usually equal to `raw_source_text`; reserved for future formatting-only cleanup.
- `source_section`
  - `activeIngredients`, `inactiveIngredients`, `otheringredients`, or `nested`.
- `display_type`
  - One of:
    - `mapped_ingredient`
    - `summary_wrapper`
    - `suppressed_parent`
    - `structural_container`
    - `source_descriptor`
    - `inactive_ingredient`
    - `blend_parent`
- `score_included`
  - Boolean.
- `mapped_to`
  - Canonical ingredient reference when applicable.
  - Includes:
    - `standard_name`
    - `canonical_id`
    - `category`
- `resolution_type`
  - One of:
    - `direct`
    - `alias`
    - `ingredient_group_fallback`
    - `descriptor_fallback`
    - `wrapper_suppressed`
    - `summary_suppressed`
    - `structural_unwrapped`
    - `display_only`
- `children`
  - Zero or more child display entries for wrappers and structural parents.
- `notes`
  - Short user-safe explanation such as:
    - `Shown on label but not scored directly; scored via child omega-3 components.`
    - `Shown on label as a lecithin wrapper; scored via phosphatidylcholine child.`

## Inclusion Rules

### Include in Main Display Ledger

- active ingredient rows
- inactive ingredient rows
- proprietary blend parents
- summary rows like `Other Omega-3's`
- branded/source wrappers like `High Choline Lecithin`
- structural parents if a user would reasonably recognize them from the label

### Exclude From Main Display Ledger

- nutrition facts rows such as `Calories`, `Total Fat`, `Calories from Fat`
- panel headers such as `Other Ingredients`, `Active Ingredients`
- parser artifacts

### Optional Expanded View Only

- purely structural shell/container rows such as `Soft Gel Shell`
- structural system rows like `Humectant`, `Acidity Regulator`

These should still exist in the ledger, but the UI can collapse them by default.

## UX Recommendation

Default presentation:

- show all mapped ingredients
- show summary/wrapper rows with a muted badge:
  - `Not scored directly`
  - `Label summary`
  - `Source wrapper`
- show the canonical explanation underneath mapped rows

Expanded presentation:

- reveal structural/container rows
- show the child relationship tree

### Example

Label row:

- `High Choline Lecithin`

Display behavior:

- shown in ledger
- badge: `Source wrapper`
- `score_included=false`
- child row:
  - `Phosphatidyl Choline`
  - mapped canonically to `Choline`

Label row:

- `Other Omega-3's`

Display behavior:

- shown in ledger
- badge: `Label summary`
- `score_included=false`
- linked to explicit EPA/DHA children

## Cleaner Contract Changes

The cleaner should emit `display_ingredients` in addition to current normalized `activeIngredients` / `inactiveIngredients`.

Cleaner responsibilities:

- capture every label-visible ingredient row before suppression
- classify why a row is display-only or scoring-safe
- preserve parent/child relationships
- preserve exact raw label text

The cleaner remains the source of truth for display provenance.

## Enricher Contract Changes

The enricher should not rebuild display rows from scratch.

Enricher responsibilities:

- enrich `display_ingredients` with canonical references when available
- propagate scoring inclusion status
- add a short resolution explanation

The enricher should continue scoring only normalized active/inactive inputs, not display-only rows.

## Backward Compatibility

- Keep `activeIngredients` and `inactiveIngredients` unchanged for downstream scoring.
- Add `display_ingredients` as an additive contract field.
- Existing scorers and validators should ignore it until explicitly upgraded.

## Risks

- Payload growth:
  - Mitigation: keep display rows compact and collapse structural rows in UI.
- Duplicate-looking rows:
  - Mitigation: explicit `display_type` and `score_included` flags.
- Contract drift:
  - Mitigation: add provenance and contract tests before UI rollout.

## Testing Strategy

- cleaner regression tests for preserved display rows
- contract tests ensuring suppressed/scored separation
- enrichment tests ensuring `mapped_to` and `score_included` stay consistent
- snapshot tests on representative products:
  - summary row product
  - structural container product
  - proprietary blend with nested children
  - inactive wrapper/source product

## Recommendation

Implement `display_ingredients` as a cleaner-owned additive ledger, enrich it in place, and keep scoring logic untouched.

That gives the app a trust-preserving “what you saw on the label” view without weakening normalization quality.
