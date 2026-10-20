# "nut" in a free-from claim is a whole word (2026-10-20)

**Defect.** Two owners read "nut" as a substring:
- `constants.ALLERGEN_FREE_PATTERNS["nut"]`: `(nut|tree nut)[\s-]*free` matched "peanut-free", and
  the unbounded `contains no .*?nut` matched across sentences into words such as "Nutragenesis"
  (28484) or "nutrients";
- `generic_transparency._allergen_groups_from_text`: `elif "nut" in norm` mapped the evidence
  claim "peanut" (from "no peanuts", cert_claim_rules) to `tree_nut` as well.

So a tree-nut facility or "Contains: Tree nuts (coconut)" contradicted a peanut-only claim and
cost B2. Both now match `nuts?` as a whole word.

**Replay** (`~/pg_quality/lucidbanach_nutclaim_20261020/`): 523 raw labels with peanut-free wording
or where the old and new pattern disagree, + 150 controls; `--full --blob`; main 33f7e303e vs
b1d5212a0.
- 62 records change; 0 allergen-hit, status or Gluten-Free badge changes; 0 controls.
- 46 lose a false `nut` claim (compliance `allergen_free_claims`).
- **7 gain 2.0–3.0 points**, all B2 removed, 0 tier changes: 75073 (+3.0), 206267, 69313 (+2.7;
  "No dairy, no peanuts" + tree-nut facility), 321372 (+2.7), 326767 (+3.0), 74881 (+2.0)
  (peanut-free + "Contains: Tree nuts (coconut)"), 28484 (+3.0; "Nutragenesis"). Per product:
  `per_product_deltas.csv`.

Tests: `scripts/tests/test_free_from_claim_rule.py` (pattern cases, claim-group cases, 75073
fixture; all fail first).
