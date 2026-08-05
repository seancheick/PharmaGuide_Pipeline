# V4 absorbed-penalty policy audit

This is an analysis artifact only. It does not change scoring.

## Corpus result

- Products scanned: **14,193**
- Products with absorbed penalties: **62**
- Raw penalty points absorbed: **68.2213**
- Alternative public-score movement if every affected penalty moved post-cap: **-71.8** points
- Products crossing a quality tier: **5**

## Policy split

- Material-defect population: **10** products containing a contradicted allergen-free claim.
- Soft-debt-only population: **52** products carrying proprietary-blend opacity.

Recommendation: do not globally reverse penalty ordering. A later policy change should move contradicted allergen-free claims after the cap while leaving blend-opacity ordering unchanged until the reviewer benchmark.

The complete per-product table is in `affected_products.csv`; the exact machine-readable evidence and input fingerprint are in `report.json`.

## Tier movements under the global alternative

- Acceptable -> Weak: **2**
- Strong -> Acceptable: **2**
- Weak -> Poor: **1**
