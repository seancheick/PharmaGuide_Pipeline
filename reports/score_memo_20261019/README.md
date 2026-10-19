# Score-stage memo — October 19, 2026

Branch `claude/gracious-knuth-b05b4b`. Base `6aaa9e874`, candidate `8c13a1bb8` (`dbdcfbe05` memo,
`8c13a1bb8` progress log). Class: behavioral code (performance); no intended output change.

## Change

`scoring_input_contract.scoring_input_scope` (the existing owner, opened by `build_scored_artifact`)
now:

- treats a shallow `dict(product)` copy holding the very same value objects as the scoped product
  (readiness, the evidence resolver and the gates read such copies, so the per-product cache missed);
- derives once per pass: the scoring input (existing), `build_scoring_classification` per
  (route_module, origin), the route decision, and `classify_ingredient_roles` when `rows` is None;
- hands each caller its own copy (deepcopy for nested results, per-role dict copies). Caller-built
  `rows` are never memoized. Inside a scope the temporary route-rows key is no longer installed: the
  scoped input already supplies the same rows.

`score_products_v4.py` logs a start line, one line every 250 products and one line per file.

## Equivalence receipt

Cohort: 1,865 frozen raw labels (`ids.json`, manifest sha256 `0b5d9f64…`) from
`~/pg_quality/full_artifact_baseline_20261018/frozen_raw`: all 7 routes, every subroute (up to 60
each), all 236 `not_scored` and 69 `suppressed_safety` labels, 150 children's labels, 12 per
brand across all 37 brands.

`replay.py snapshot --full --blob --workers 4`, unpinned hash seed, base worktree and candidate:

| Receipt | exit | products | source_unchanged | output sha256 |
|---|---|---|---|---|
| `base_6aaa9e874.jsonl.meta.json` | 0 | 1,865/1,865 | true | `11a1b55c…` |
| `cand_8c13a1bb8.jsonl.meta.json` | 0 | 1,865/1,865 | true | `11a1b55c…` |

`replay.py compare --all-paths` → `{"products": 1865, "changed": 0}` (`compare_all_paths.json` is
`[]`). Independent check of the JSONL hashes: 0 differences in cleaned, enriched, scored and blob,
with every hash present. The two snapshot files themselves are byte-identical.

## Score-stage time (same 1,865 enriched products, one process each)

The machine was not idle: other sessions were running a 4-worker job, `build_final_db.py` and an
audit (load average 11–17), so both runs are reported.

| Run | base ms/product | candidate ms/product | speedup |
|---|---|---|---|
| sequential (base, then candidate) | 139.1 | 50.7 | 2.7× |
| concurrent (same load for both) | 187.3 | 76.9 | 2.4× |

Scored artifacts from both timing runs were byte-identical. The October 19 corpus Score stage
(~1,300 s) projects to roughly 480–540 s.

cProfile, 300 random cohort products (call counts per product do not depend on load):

| per product | base | candidate |
|---|---|---|
| `_build_scoring_ingredients` builds | 47.6 | 1.0 |
| route decisions (`_classify_route_module` derivations) | 11.6 | 1.0 |
| `build_scoring_classification` derivations | 11.6 | 2.0 (two origins) |
| compiled-regex calls | 360,176 | 33,459 |
| profiled ms/product | 445.8 | 149.3 |

What remains is mostly work outside this owner: probiotic strain identity in
`studied_formulas.py` (`probiotic_label_identity_summary`, ~29% of the candidate profile) and the
defensive result copies (~11%).

## Tests

Fail-first: `test_one_scoring_pass_derives_each_product_view_once` (base: 19 builds in one pass),
`test_scoring_input_scope_reuses_views_for_a_shallow_copy_of_the_product`,
`test_scoring_input_scope_derives_classification_and_roles_once`,
`test_score_file_reports_progress_so_a_long_batch_never_looks_stalled`.
Owner/consumer files: scoring_input_contract + v4_scored_artifact 177 passed; score CLI 17;
assessment_readiness(+shadow), evidence_resolver, evidence_owner_eligibility 255;
clinical_applicability and 6 router files 232.
