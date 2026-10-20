# Allergen ingredient-variant matching (2026-10-19)

Ingredient rows that name an allergen source with extra wording ("Whey Protein Isolate",
"Purified Deep Sea Fish Oil", a row with form "Fish Oil") shipped no allergen flag. The enricher
now matches an allergens.json alias as a whole word in the row name or forms; reviewed exceptions
live in each entry's `match_rules.negative_match_terms`.

- `research.md`: defect, FDA source, per-entry receipts, replay result, open policy question.
- `impact.py`: corpus rows that name an alias without a hit (reads `scripts/products/output_*_enriched/`).
- `apply.py`: the data batch (`data_batch` load/patch/save), re-run from origin/main.
- Test: `scripts/tests/test_allergen_ingredient_variants.py`.
