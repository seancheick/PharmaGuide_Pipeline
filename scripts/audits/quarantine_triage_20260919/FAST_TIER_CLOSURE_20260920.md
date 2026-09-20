# Fast-tier closure evidence — 2026-09-20

Command: `scripts/test.sh fast`
Environment: clean dedicated worktree at the Phase-3 closure tip, no locally-built corpora
present (i.e. a fresh-clone equivalent), peer sessions' uncommitted work absent.

## Result

```
15835 passed, 196 skipped in 428.55s (0:07:08)
```

Run at the **final** closure tip `0eec550e` (on `main` = `78ad21fd`). The tier was executed
three times this session — at `236a9dc1`, at `4e5f4bda`, and at the final tip — because
`main` was under active development by a parallel session, and re-running at each new tip is
what surfaced the defect in `78ad21fd` (see *Defect found and repaired at the final tip*).

| | Count |
|---|---:|
| passed | **15,835** |
| **failed** | **0** |
| skipped | 196 |
| errors | 0 |
| collection errors | 0 |

No failure, error or collection-error lines appear anywhere in the run.

## Comparison to the intermediate state

| Ref | Result | Failure set |
|---|---|---|
| base `124982a0` | 1 failed / 15,767 passed / 191 skipped | `{static_audit}` |
| Phase-3 candidate `77cbb38c` | 2 failed / 15,786 passed / 191 skipped | `{static_audit, overlap_guard}` |
| candidate + `7ebf6c46` | 1 failed / 15,787 passed / 191 skipped | `{static_audit}` |
| integration `095d27a1` (clean worktree) | 1 failed / 15,826 passed / 152 skipped | `{static_audit, probiotic×7}` |
| `236a9dc1` tip (closure worktree) | 0 failed / 15,825 passed / 196 skipped | `{}` — empty |
| `4e5f4bda` tip (`a6086870`) | 0 failed / 15,827 passed / 196 skipped | `{}` — empty |
| `78ad21fd` tip before repair (`899cba40`) | **1 failed** / 15,834 passed / 196 skipped | `{schema_version_contract}` |
| **final tip `0eec550e`** | **0 failed / 15,835 passed / 196 skipped** | **`{}` — empty** |

### Defect found and repaired at the final tip

`78ad21fd` added `scripts/data/literature_evidence_records.json` declaring
`schema_version: "1.0.0"`. `scripts/reference_data_schema.py` documents that version 1 owns
vocabularies and small control artifacts while **every other top-level reference database
stays in the version 5 enrichment namespace**, and `validate_reference_schema_version`
enforces it, so:

```
test_pipeline_integrity.py::TestDatabaseSchemaIntegrity::test_schema_version_contract
  1 schema_version mismatch(es):
  literature_evidence_records.json: schema_version='1.0.0' belongs to namespace 1, expected 5.x
```

Repaired in `0eec550e` by declaring `5.0.0` (a brand-new file declares the namespace base).
Metadata only — `total_entries` (23) already matched the record count and no record content
changed. Confirmed by re-running the affected contracts (`test_pipeline_integrity` schema
class, `test_data_file_metadata_contract`, `test_reference_data_contract`,
`test_evidence_resolver`): **116 passed / 17 skipped**, and `preflight.py` reports
`CRITICAL CHECKS PASSED`.

The two outstanding failure classes are both closed:

1. **`static_audit`** — resolved by the evidence seam now on `main` (`a8213c63`); the
   forbidden `iqd["ingredients"]` fallback is gone from
   `scoring_v4/modules/generic_evidence.py`, replaced by the canonical contract
   `scoring_input_contract.get_assessable_evidence_ingredients`. Not allowlisted.
   Raw static-audit finding count: **0** (census command
   `scripts/audits/audit_source_of_truth_contract.py scoring-static` prints
   `OK: scoring-static source-of-truth audit passed`).
2. **`test_cross_module_probiotic_evidence.py` ×7** — the file loaded
   `scripts/products/output_*_enriched/enriched/*.json` directly and hard-failed with
   `FileNotFoundError` where the gitignored corpus is absent. Fixed by adopting the
   repository's existing convention (`pytest.skip("enriched corpus not present")`).
   Verified: **1 passed / 7 skipped / 0 failed** without the corpus, **8 passed / 0 failed**
   with it. No assertion weakened, no test removed, no path allowlisted.

## Skip census (exactly 196, by file)

Every skip is an environmental precondition. Counts below are the exact per-file totals
from the run; the three categories sum to 196. Reasons are sanitised — two reasons named
an absolute local path and are paraphrased here.

### A. Opt-in integration suites — 24

| Count | Test file | Reason |
|---:|---|---|
| 12 | `test_submission_extraction_live_stack.py` | opt in with `PG_RUN_LOCAL_EXTRACTION_TESTS=1` |
| 11 | `test_submission_review_live_stack.py` | opt in with `PG_RUN_LOCAL_REVIEW_TESTS=1` |
| 1 | `test_submission_print_fidelity.py` | needs `PG_RUN_OCR_FIDELITY_TESTS=1` and the OCR engine |

### B. Documented intentional exceptions in the data-file metadata contract — 17

All 17 are in `test_data_file_metadata_contract.py`, and each skips with an explicit
rationale naming the file, the convention it follows, and the bespoke test that pins it
(e.g. `clinical_risk_taxonomy.json` sums all seven taxonomy arrays;
`ingredient_weights.json` tracks the four dosage tiers; `unit_conversions.json` tracks
`vitamin_conversions` only). This is the contract telling you it has been reviewed, not an
environment gap.

### C. Locally-built corpora / canary blobs / build dirs absent — 155

| Count | Test file |
|---:|---|
| 45 | `test_e1_2_2_preflight_invariant.py` (eight named baseline records, ×5 each) |
| 22 | `test_cert_population_identity.py` |
| 18 | `test_plant_part_preservation_closeout.py` (canary blobs not rebuilt) |
| 9 | `test_canonical_id_delivers_markers_emit.py` |
| 8 | `test_active_count_reconciliation.py` |
| 7 | `test_cross_module_probiotic_evidence.py` ← **this session's hermetic fix** |
| 7 | `test_inactive_ingredient_preservation.py` |
| 5 | `test_probiotic_structured_form_identity.py` (synthetic ownership cases run unconditionally) |
| 4 | `test_parent_fallback_final_state_guard.py` |
| 4 | `test_pipeline_integrity.py` |
| 3 | `test_cleaner_forms_preservation.py` |
| 3 | `test_reviewer_doc_constituent_forms.py` |
| 2 | `test_e1_5_x_4_ul_fallback_and_status.py` |
| 2 | `test_no_silently_mapped_rows.py` |
| 2 | `test_inactive_penalty_ledger_parity.py` |
| 2 | `test_inactive_role_label_from_functional_roles.py` |
| 2 | `test_probiotic_confidence_hybrid.py` |
| 1 each (10 files) | `test_b04_functional_roles_integrity.py`, `test_capsimax_display_label_fidelity.py`, `test_clean_label_nested_forms.py`, `test_blend_header_member_dedup.py`, `test_condition_id_shape_consistency.py`, `test_probiotic_cfu_adequacy.py`, `test_scorer_dedup_audit.py`, `test_serving_basis_daily_servings.py`, `test_red_yeast_rice_alias_coverage.py`, `test_unii_match_path.py` |

24 + 17 + 155 = **196** ✓

Only one of these 196 was changed by this session (the 7 in
`test_cross_module_probiotic_evidence.py`, which previously hard-failed instead of
skipping); every other file already used `pytest.skip` for a missing local artifact before
the Phase-3 work began.

## Reproducing the corpus-present variant

The same suite is expected to pass with the corpus present; the two files this session
touched were re-verified in the shared checkout, where the locally-built corpus exists:

| Suite | Without corpus | With corpus |
|---|---|---|
| `test_cross_module_probiotic_evidence.py` | 1 passed / 7 skipped / 0 failed | **8 passed / 0 failed** |
| `test_scoring_source_of_truth_audit.py` | 23 passed / 0 failed | 23 passed |
| `test_standardization_marker_generalization.py` | 5 passed / 0 failed | 5 passed |

## Scope note

This run was executed **at the final closure tip itself** (`0eec550e`), not at an earlier
state, so the result describes the shipped tree exactly. Relative to `main` (`78ad21fd`) the
closure branch adds three documentation/test commits — which change no pipeline file — plus
the `literature_evidence_records.json` metadata repair described above. That repaired file is
read only by `evidence_resolver.py`, which has **zero importers** and zero references in
`clean_dsld_data.py`, `enrich_supplements_v3.py` and `score_products_v4.py`, so it cannot
affect the clean/enrich/score path the 15,412-product replay exercised.
