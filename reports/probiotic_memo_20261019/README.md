# Probiotic strain-identity memo — October 19, 2026

Branch `claude/probiotic-strain-perf`, on main `fd51b5828` (after PR #175). Class: behavioral code
(performance); no intended output change.

## Change

Probiotic labels were the slowest Score inputs (~0.5 s each after PR #175). Every
`studied_formulas.clinical_strain_matches_source_row` call rebuilt the label's owner rows and re-ran
`has_nonlive_microbial_derivative_evidence` on every row (1.31M checks for 107 labels), and
`label_owned_strain_identities` re-matched every row against the whole strain registry on each of
~6 calls per label.

- The label owner rows with their nonlive set (`_label_owners`) and the strain identities are now
  per-pass views of the existing `scoring_input_contract.scoring_input_scope` (its helper is now the
  public `scoped_product_view`; no new cache module).
- Both views read only `activeIngredients`, declared with `fields=("activeIngredients",)`: a
  `{**product, "probiotic_data": ...}` variant holding the very same `activeIngredients` list is the
  same input. `test_label_strain_views_read_only_active_ingredients` proves, with a read-recording
  product, that no other top-level field is touched.
- `_source_live_eligible` looks the nonlive set up instead of recomputing it. The ids in that set
  name objects of the owner list it is paired with (both come from one view); representations are
  members of that list, and a row outside it is checked directly.
- Outside a scope every call derives as before.

## Equivalence receipt (isolates this diff)

Cohort: 2,562 frozen raw labels (`ids.json`): every probiotic label in the corpus (865:
`probiotic_ids.json`, 539 on the probiotic route + 326 other routes with `probiotic_data`; 848
scored, 11 not_scored, 6 suppressed_safety) plus the 1,865-label control cohort of
`reports/score_memo_20261019/` (168 overlap). Frozen from
`~/pg_quality/full_artifact_baseline_20261018/frozen_raw` into `~/pg_quality/probiotic_memo_20261019/`.

`replay.py snapshot --full --blob --workers 4`, unpinned: base `6aaa9e874` vs candidate `329d1335b`
(this diff on top of PR #175 head `5dfb13767`; the rebased patch onto `fd51b5828` is byte-identical,
checked with `cmp` on the two `git diff`s).

| Receipt | exit | products | source_unchanged | output sha256 |
|---|---|---|---|---|
| `base_6aaa9e874.jsonl.meta.json` | 0 | 2,562/2,562 | true | `5f81df28…` |
| `cand_329d1335b.jsonl.meta.json` | 0 | 2,562/2,562 | true | `5f81df28…` |

`compare --all-paths` → `{"products": 2562, "changed": 0}`; independent hash check: 0 differences in
cleaned, enriched, scored and blob, every hash present. The snapshot files are byte-identical.

## Revalidation on current main

Main gained the #176/#177 cleaner changes after `6aaa9e874`, so the same 2,562 labels were replayed
again: base main `fd51b5828` vs this branch head `1aa8c060e`, `--full --blob --workers 4`, unpinned.

| Receipt | exit | products | source_unchanged | output sha256 |
|---|---|---|---|---|
| `main_fd51b5828.jsonl.meta.json` | 0 | 2,562/2,562 | true | `5f81df28…` |
| `cand_1aa8c060e.jsonl.meta.json` | 0 | 2,562/2,562 | true | `5f81df28…` |

`compare --all-paths` (`compare_main_all_paths.json`) → `{"products": 2562, "changed": 0}`;
independent hash check: 0 differences in cleaned, enriched, scored and blob. (On this cohort the
main snapshot also equals the `6aaa9e874` snapshot.)

## Score time, probiotic-route labels (107 in the control cohort, one process each, concurrent)

Base PR #175 head `1b5b3bf10`: 523.7 ms/product; candidate: 151.1 ms/product (3.5×), scored
artifacts byte-identical. Machine busy with other sessions (load 15–17). cProfile over the same 107
labels: `has_nonlive_microbial_derivative_evidence` calls 1,310,360 → 35,977 (801,841 before the
`fields=` declaration, when evidence assessment's `probiotic_data` variants still missed the scope);
`_label_strain_identity_candidates` 6,061 → 1,041; strain-identity derivations 639 calls → 103
derivations for 107 labels; profiled ms/label 1,326 → 369.

## Tests

Fail-first `test_one_scoring_pass_reads_each_label_strain_row_once` (36 nonlive checks for a 3-row
label before; now one per row), extended with a postbiotic parent whose nested LGG must be neither
matched nor live-eligible, a probiotic_data variant that differs from the scoped product, and a
copied `activeIngredients` list that must not reuse the view.
`test_label_strain_views_read_only_active_ingredients`. 43 probiotic/strain test files plus
assessment_readiness, evidence_resolver and clinical_applicability: 2,005 passed, 16 skipped (all
need the local product corpus or rebuilt canaries).
