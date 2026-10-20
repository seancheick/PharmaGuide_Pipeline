# B2 costs the contradicting allergen's severity (2026-10-20)

**Defect.** `generic_transparency._score_b2_false_allergen_claim_penalty` took
`max(seen.get(group) for group in matched_groups)`, but `seen` is keyed by allergen id
(`allergen_milk`) and `matched_groups` holds claim-group names (`dairy`). The lookup always missed,
so every contradicted free-from claim took `b2_cap` (2.0) and the configured
`b2_severity_points` (high 2.0 / moderate 1.5 / low 1.0, `quality_score.json`, introduced in
e945668c4 when `seen` was still keyed by names) never applied.

**Fix.** B2 takes the highest severity among the hits that contradict a matched group, through
`scoring_input_contract.free_from_claim_contradicting_hits(group, hits)` (the one rule;
`free_from_claim_contradiction` now uses it). A group matched only by conflict text (no hit) keeps
the cap. No magnitude changes.

Owner: `scoring_v4/modules/generic_transparency.py::_score_b2_false_allergen_claim_penalty` (shared
by the probiotic, omega and multi/prenatal modules) — evidence: `rg _score_b2_false_allergen_claim_penalty scripts/scoring_v4`.
Will NOT create: a new magnitude, field or severity table.

**Replay** (`~/pg_quality/lucidbanach_b2severity_20261020/`): the #187 cohort, 784 frozen labels
(484 with a free-from claim and a cross-contact signal + 300 controls), `--full --blob`, main
33f7e303e vs 520b16fd1.
- 314 records change; 0 allergen-hit, status, Gluten-Free badge or compliance changes.
- **279 products gain 0.1–1.5 points**, all B2: −2.0 → −1.5 on 266 (moderate: milk 164, wheat 100, eggs 1,
  barley 1) and −2.0 → −1.0 on 13 (soy, low). +0.5 ×158, +0.8 ×84, +0.7 ×23, +1.0 ×9.
  22 tiers up (Poor → Needs improvement 8, Needs improvement → Good 8, Good → Very good 6), 0 down.
- 35 records change B2 without moving the total: 32 at the Transparency floor, 3 rounding.
- 7 controls change, each through its own B2.
- Per product: `per_product_deltas.csv`.

Tests: `scripts/tests/test_free_from_claim_rule.py` (218190 milk −1.5, soy −1.0, highest of
milk + soy −1.5 fail first; crustaceans and conflict-only keep 2.0). Five pins that encoded the cap
move to the source severity (milk facility, 218190, 293779 wheat facility, 297644/274671 barley).
