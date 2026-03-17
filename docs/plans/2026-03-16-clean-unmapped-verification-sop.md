# Clean Unmapped Verification SOP

Date: 2026-03-16
Scope: Cleaning-stage unmapped remediation for the DSLD pipeline
Status: Active working SOP

## Purpose

This SOP defines how to resolve cleaning-stage unmapped labels without polluting the cleaner, breaking prior fixes, or creating false ingredient identities.

The goal is not to minimize unmapped counts at any cost.

The goal is:
- correct identity resolution
- stable cleaner behavior
- reproducible verification
- better auditability in the final user-facing payload

## Core Principle

Treat every unmapped label as untrusted until proven otherwise.

Do not assume it is:
- a database gap
- a new ingredient
- a safe alias
- or a cleaner bug

Every case must be classified from evidence first.

## Source of Truth Order

Use this order every time:

1. Raw DSLD source in `/Users/seancheick/Documents/DataSetDsld/...`
2. Current clean output in `scripts/output_*/cleaned/`
3. Current clean unmapped reports in `scripts/output_*/unmapped/`
4. Current DB contents in `scripts/data/`
5. Targeted external sources only when identity is niche, branded, safety-sensitive, or ambiguous

If raw DSLD and cleaned output disagree, raw DSLD wins.

## Required Case Classification

Before editing code or data, classify the label into exactly one of these buckets:

1. Structural parent
- blend parent
- shell/container row
- coating/header row
- summary row

2. Constituent or standardization leaf
- marker compound
- standardized constituent
- descriptive leaf under a real parent

3. Exact alias gap
- same real ingredient
- same chemistry or same botanical identity
- missing exact label string only

4. New canonical identity
- real stable ingredient
- not represented anywhere in current DBs

5. Wrong-route issue
- should be in `other_ingredients`, `botanical_ingredients`, `standardized_botanicals`, `harmful_additives`, or `banned_recalled_ingredients`

6. Deferred accuracy case
- raw row conflicts with common identity
- label appears malformed or misleading
- not safe to map yet

## Decision Rules

### Fix code when:
- the row is structural and should not survive as a real ingredient
- child rows should be preserved while parent should be display-only
- routing precedence is wrong
- a wrapper or container leaks into scoring

### Add an exact alias when:
- the identity already exists
- the raw label is only a missing exact synonym
- the alias does not broaden scope

### Add a new canonical when:
- the identity is real
- stable
- repeatedly encountered
- and no current canonical safely fits

### Defer when:
- mapping would rely on guesswork
- raw DSLD is inconsistent
- outside identity conflicts with raw `ingredientGroup`
- the row looks like a label artifact rather than a real ingredient

## Raw Verification Checklist

For each candidate, inspect:
- `name`
- `ingredientGroup`
- `category`
- `forms`
- `nestedRows`
- `alternateNames`
- active vs inactive placement
- note text

Key questions:
- Is this a real ingredient or a wrapper?
- Is this a child constituent rather than the actual active?
- Is this an exact identity or a marketing label?
- Is the current issue code, data, or both?

## Mapping Strategy

### For active unmapped rows

Default destination is not automatically IQM.

First ask:
- is this a real active?
- is it a constituent leaf?
- is it a branded parent with real children?
- is it actually botanical rather than nutrient-form?
- is it safety-sensitive?

### For inactive unmapped rows

Default destination is not automatically `other_ingredients`.

First ask:
- is it structural?
- is it just a generic source descriptor?
- is it a real excipient?
- is it harmful?
- is it actually an active placed in the wrong section?

## Display Ledger Rule

Do not reintroduce structural rows into scoring just because users need to see them.

Use the display ledger for:
- structural parents
- summary rows
- source wrappers
- suppressed constituent rows

Scoring-safe normalized rows remain separate.

This lets the user see exactly what was on the bottle while preserving correct scoring logic.

## Verification Loop

Every batch follows the same loop:

1. Pick a small exact batch
- usually 10 to 20 labels
- same family when possible

2. Add targeted tests first
- exact mapping tests in `scripts/tests/test_clean_unmapped_alias_regressions.py`
- structural/display tests in `scripts/tests/test_pipeline_regressions.py`

3. Implement the narrowest fix
- no broad fuzzy rules
- no speculative aliases
- no convenience collapsing

4. Run targeted tests

5. Run integrity checks
- `python3 scripts/db_integrity_sanity_check.py --strict`
- `PYTHONPATH=scripts python3 -m pytest scripts/tests/test_db_integrity.py -q`

6. Run a real shadow clean
- copy only the affected raw source files into `/tmp/...`
- rerun `scripts/clean_dsld_data.py`
- inspect the new `unmapped_active_ingredients.json` and `unmapped_inactive_ingredients.json`

7. Confirm:
- the target labels are gone from the intended unmapped surface
- child ingredients still survive where needed
- prior fixes did not regress
- unrelated leftovers are clearly separated from target wins

## Regression Protection Rules

Never:
- replace exact fixes with broader normalization if the exact fix already works
- turn display-only rows back into scoring ingredients
- collapse oil, botanical, or constituent labels into parent identities without raw support
- use new aliases to hide a cleaner bug
- treat a branded wrapper as solved if the real children are already present

Always:
- preserve prior successful exact routes
- verify against real raw files, not synthetic assumptions only
- keep fixes additive and local

## When to Use External Verification

Use external sources only when the raw row alone is not enough.

Examples:
- branded ingredients
- niche Ayurvedic/common names
- stimulant or banned-risk identities
- cases where common identity conflicts with DSLD `ingredientGroup`

Preferred evidence order:
- FDA / NIH / NCCIH / other authority
- PubMed / DOI-backed literature
- official branded identity pages for identity confirmation only

## Known Deferred-Type Examples

These are examples of labels that should not be forced without proof:
- conflicting common names vs raw `ingredientGroup`
- vague constituent names like `Phenol`
- generic placeholders like `other`
- label artifacts that only appear inside wrappers

## Output Expectations Per Batch

Each batch summary should report:
- files changed
- exact labels fixed
- whether each fix was code, alias, new canonical, or suppression
- tests run
- DB integrity result
- shadow-clean result
- unrelated leftovers still remaining

## Recommended Working Pattern

1. Fresh rerun
2. Choose next exact batch
3. Verify raw rows first
4. Add tests
5. Implement minimal fix
6. Verify with shadow clean
7. Only then move to the next batch

This is intentionally slower than broad normalization.

It is also how we avoid silent false mappings and keep user trust intact.
