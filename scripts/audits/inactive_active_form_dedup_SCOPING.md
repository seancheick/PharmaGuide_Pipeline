# Scoping: product-aware active-form-duplicate inactives

**Status:** implemented as B2 product-aware tagging. B1 product-blind tagging
was rejected after corpus validation.
**Date:** 2026-06-16

## Problem

Some DSLD products duplicate a nutrient form into `inactiveIngredients` while
the active panel already carries the parent nutrient. Example:

| Actives (`ingredients`) | Inactives (`inactive_ingredients`) |
| --- | --- |
| Vitamin C, Thiamine, Niacin, **Vitamin B6**, **Vitamin B12**, Pantothenic Acid | Ascorbic Acid, Thiamine Mononitrate, Nicotinamide, **Pyridoxine HCl**, **Cyanocobalamin**, Calcium D-Pantothenate |

Those duplicate form rows inflate the inactive-safety CHECK 3 "unknown inactive
roles" metric. They are not scoring inputs; the active parent is already scored.

## Rejected approach: B1 resolver-level tagging

The first prototype added an IQM active-form branch directly to
`InactiveIngredientResolver.resolve()`. Unit tests passed, but corpus validation
showed the approach was wrong.

The resolver has no product context, so it cannot distinguish:

- `Pyridoxine Hydrochloride` in a B-complex: duplicate B6 form.
- `Leucine` in a zinc product: not a duplicate active.
- `Potassium Chloride` in an omega/joint product: not a duplicate potassium active.
- `Rosemary Leaf Extract` in a CoQ10 softgel: preservative-style inactive.

On the current built blobs, the product-blind prototype would tag 2,751 inactive
rows as `active_form_duplicate`; 916 of those had no matching active parent in
the same product. Counts will drift by corpus version, but the failure mode is
structural.

## Implemented approach: B2 product-aware tagging

The resolver now keeps the IQM active-form index as a lookup helper only:

- `resolve()` remains safety/excipient/unknown only.
- `active_form_candidates()` returns possible IQM active-form parents.
- `build_final_db.build_detail_blob()` decides whether an unmatched inactive row
  is truly an active-form duplicate by comparing the candidate parent(s) with
  the same product's exported active ingredient identities.

Rules:

1. Banned, harmful, and known `other_ingredients` matches always win.
2. Product-aware active-form duplicate tagging is considered only for unmatched
   inactive rows.
3. The inactive raw label term must hit an IQM active-form candidate.
4. The candidate parent, equivalent parent, or parent identity term must appear
   in the same product's active ingredient set.
5. Upstream inactive `standardName` is not used as proof, because it may already
   contain broad active normalization and would recreate the product-blind bug.

When all conditions pass, the row stays visible for label fidelity but carries:

- `matched_source: "active_nutrient_form"`
- `inactive_policy: "active_form_duplicate"`
- `is_active_only: true`
- `label_row_disposition: "active_only"`
- `functional_roles: []`

## Adjacent data fixes

The corpus audit also exposed genuine inactive mapping gaps. These were fixed
as data-root causes rather than hidden by active-form tagging:

- `Dicalcium Phosphate` exact label alias -> `PII_DICALCIUM_PHOSPHATE`
- `Calcium Carbonate` exact label alias -> `PII_CALCIUM_CARBONATE`
- `Rosemary Leaf Extract` -> `NHA_NATURAL_PRESERVATIVES`
- `Natural & Artificial Flavors` -> new mixed-flavor class with both
  `flavor_natural` and `flavor_artificial`

No CUI/UNII/CID/PMID was invented for the mixed-flavor class; it is a
label-disclosure class, not a compound identity.

## Tests

Pinned by:

- `scripts/tests/test_inactive_active_form_duplicate_2026_06.py`
- `scripts/tests/test_inactive_excipient_alias_coverage_2026_06.py`
- `scripts/tests/test_inactive_ingredient_resolver.py`
- `scripts/tests/test_b04_functional_roles_integrity.py`

Core canaries:

- Positive: Vitamin B6 active + Pyridoxine Hydrochloride inactive tags duplicate.
- Positive: generic Vitamin K active + Phytonadione inactive honors IQM
  parent-equivalence.
- Negative: Zinc active + Leucine inactive does not tag.
- Negative: EPA active + Potassium Chloride inactive does not tag.
- Negative: CoQ10 active + Rosemary Leaf Extract inactive resolves as preservative.
