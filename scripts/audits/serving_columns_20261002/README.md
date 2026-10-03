# Q39 alternate-serving closure (2026-10-02)

## Owner check

Owner: `scripts/enhanced_normalizer.py::EnhancedDSLDNormalizer._merge_alternate_serving_rows` — evidence: `source_of_truth_matrix.json` assigns source normalization to `enhanced_normalizer.py`, and `rg '_merge_alternate_serving_rows' scripts` finds the one production merge before active-ingredient processing.

Will NOT create: a second serving selector, ingredient-role owner, score adjustment, export field, or app-side merge.

## Raw-corpus result

Read-only census command:

```bash
python3 scripts/audits/serving_columns_20261002/census.py \
  /Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands
```

The census reads all 15,414 staged DSLD JSON files and calls the production merge directly. It does not clean, enrich, score, export, or write into the source corpus.

| Measure | Before | Candidate |
|---|---:|---:|
| Multi-column labels inspected | 323 | 323 |
| Labels with repeated top-level normalized names | 108 | 1 |
| Labels with repeated names anywhere in the ingredient tree | 141 | 19 |

The one retained top-level repeat is product `250086`: vitamin E is declared once as DL-alpha-tocopheryl acetate and once as DL-alpha-tocopherol acetate. The forms conflict, so the cleaner preserves both declarations.

The 19 retained all-tree cases are not unresolved serving alternatives. Apart from `250086`, every repeated name has overlapping serving contexts and occurs in distinct authored branches, such as source forms repeated beneath several amino acids or quinoa listed in both carbohydrate and protein blends. Merging them would discard label structure. The census output is `result.json`.

## Corrected defect classes

- Audience-specific columns now use serving notes when an ingredient has no distinguishing Daily Value group.
- Compatible columns can differ by missing children; every printed child remains preserved.
- A narrow spelling repair is allowed only for the same non-generic DSLD group and category.
- Rows interleaved beneath the other serving column's parent reconcile across the panel.
- Top-level and nested placements reconcile when their serving contexts are disjoint alternatives.
- Literal duplicate source rows with the same DSLD ingredient identity and source fact count once.
- Ingredient-group wording drift between columns does not split an otherwise identical name, category, forms, and tree.

The analysis row remains the largest/adult serving selected by the existing serving owner. All printed quantities remain in `quantityVariants`, and the immutable display-source ledger still carries the original rows and source paths.
