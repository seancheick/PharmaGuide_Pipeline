# Phase-3 clinical policy — fast tier and static audit (2026-09-21)

Measured on the Phase-3 clinical-policy candidate tree, in a clean detached
worktree at `origin/main` = **`b4ae13f6`** plus this phase's changes.

## Fast tier

Command: `bash scripts/test.sh fast` (pinned Python 3.13, 2 parallel workers).

| | |
|---|---|
| Passed | **15,928** |
| Failed | **0** |
| Skipped | 196 |
| Errors | 0 |
| Collection errors | 0 |
| Wall time | 252.5 s (4:12) |
| Result | **clean** |

Skips are the environment-gated suites (local review-stack opt-in, a plan file
that lives only in the user's plan store, and corpus/build-artifact baselines
absent from a clean worktree). No test was skipped, deleted or allowlisted to
obtain green.

## Static source-of-truth audit

Command: `"$PG_PYTHON" scripts/audit_source_of_truth_contract.py scoring-static`

```
OK: scoring-static source-of-truth audit passed
```

**0 findings.**

## Registry policy audit

Command: `"$PG_PYTHON" scripts/api_audit/audit_banned_recalled_accuracy.py --fda-report-in scripts/fda_sync_report_latest.json`

```
Status: pass
Integrity: 0 error(s), 0 warning(s)
Entry quality: ... missing_cui_annotations=0 ... review_gaps=0 ...
CUI audit: invalid=0, mismatch=0, name_variants=0 ...
```

The two new EDTA policy entries satisfy the registry's own strict accuracy
audit, including the null-CUI annotation requirement.

## Three deliberate test re-baselines

Documented in full in `PHASE3_CLINICAL_POLICY_20260921.md`:

1. `scripts/tests/test_cross_db_overlap_guard.py` — five reviewed
   `banned:harmful` allowlist entries added to
   `scripts/data/cross_db_overlap_allowlist.json` (deliberate role-scoped
   dual-recognition; the guard still fails on any unreviewed overlap).
2. `scripts/tests/test_preparation_identity_projection.py` — the two EDTA
   parametrizations' expected `recognition_source` moved from
   `harmful_additives` to `banned_recalled_ingredients`; the
   denominator/coverage/readiness assertions are unchanged.
3. `scripts/tests/test_safety_recognition_aliases.py` — the word-order variants
   now resolve to the declared-active policy identity; a new test additionally
   proves the two chelating salts do not collapse into one safety identity.
4. `scripts/tests/test_other_ingredient_alias_guard.py` — the allowlist review
   date pins advanced to the review date (the pins are the file's review stamp
   and are still asserted exactly).

## Frozen-corpus replay

See `PHASE3_CLINICAL_ROWLEVEL_REPLAY_b4ae13f6_20260921.json` and
`PHASE3_CLINICAL_SCORED_REPLAY_b4ae13f6_20260921.json`:

* row-level: 15,414 records, **0 representation changes**, 0 crashes;
* scored: 15,412 records, **0 score changes**, 16 conclusion changes,
  16 Safety changes, 0 quarantine exits, 0 quarantine entries,
  **0 changes outside the approved policy family**;
* the 16 changed ids are exactly the standalone oral EDTA set.
