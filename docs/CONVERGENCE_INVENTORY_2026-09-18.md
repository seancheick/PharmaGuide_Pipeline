# Convergence inventory — 2026-09-18

Four agent sessions worked this repo concurrently. This file is the audit trail for the
reconciliation: every branch, stash, worktree and uncommitted change that existed, and which of
three states it ended in.

    INTEGRATED    the work is on main
    SUPERSEDED    a stronger implementation is on main, and the reason is recorded here
    PRESERVED     kept as a named non-production or recovery artifact, not on main

Nothing was deleted. No stash was dropped, no branch removed, no shared worktree reset. Every
"superseded" verdict below was **measured** — by content comparison, by running the code, or by
reading the changelog entry that retired it — not inferred from a commit message.

---

## Stashes

All four were already preserved as `recovery/*` branches by a concurrent session before this
inventory ran. They remain. Each stash's own delta (against its base, not against main — these
branches are rooted far behind main, so a raw `diff main..branch` shows main's growth as deletions
and is meaningless) was compared to current main.

### `stash@{0}` → `recovery/stash-0-FDA-accuracy-report-WIP-other-agent---se`

**SUPERSEDED — no content.** The entire delta is one line:

    - "generated_at": "2026-09-18T16:22:20.723500+00:00"
    + "generated_at": "2026-09-18T17:41:46.406124+00:00"

in `scripts/banned_recalled_accuracy_report.json`, a generated report. The working tree carries the
identical change, live, belonging to the FDA-sync session. Left untouched.

### `stash@{1}` → `recovery/stash-1-unrelated-FDA-sync-work-in-progress-not-`

**SUPERSEDED — main is strictly richer.** Same 171 ingredients as main; one entry differs,
`RECALLED_X10_NATURAL_ENHANCEMENT`:

| | `recall_scope.lots` | note |
|---|---|---|
| stash | `null` | "Consumer-level nationwide recall by A&P Creations LLC" |
| main | three lot numbers with expiries | adds the lot count, packaging and volume |

Main identifies which lots are recalled; the stash does not. Taking the stash would lose that.

### `stash@{2}` → `recovery/stash-2-bcaa-evidence-wip`

**SUPERSEDED — the work landed, and the rest is a stale snapshot.**

- `scripts/scoring_v4/modules/generic_evidence.py` — the BCAA aggregate-dose resolution
  (`aggregate_dose +=`, summing leucine/isoleucine/valine when a record declares
  `aggregate_canonical_ids`) is on main at line 1433.
- `scripts/enrich_supplements_v3.py` — the mixture gate `_has_bcaa_mixture_evidence_identity`,
  the `l_isoleucine` component set and the EAA/essential-amino-acids exclusion regex are all on
  main.
- `scripts/data/backed_clinical_studies.json` — the stash holds a **198-entry** snapshot against
  main's **208**. Two records exist only in the stash, and both were retired on purpose. Main's own
  `_metadata` changelog says so:

      5.3.5  (2026-08-23): Removed the class-wide BRAND_ALBION_MINERALS evidence record. Its
                           magnesium-bisglycinate and ferrous-bisglycinate citations are
                           compound-specific and already live on their own records.
      5.3.13 (2026-09-05): Reclassify BRAND_PHOSPHATIDYLSERINE as INGR_PHOSPHATIDYLSERINE
                           (ingredient-human): its own notes and both cited trials (PS-DHA,
                           soybean PS) are ingredient-level, not SerinAid-specific.

  Restoring them would reintroduce two deliberately retired records — a regression wearing the
  costume of recovered work.

### `stash@{3}` → `recovery/stash-3-pre-existing-scoring-changes-before-labe`

**SUPERSEDED — its tests encode pre-label-hierarchy behaviour.** The stash name says it: *"pre-existing
scoring changes before label hierarchy integration."*

- `scripts/scoring_v4/quality_score.py` — `_omega_formulation_reason` is on main.
- The 11 test functions absent from main by name split into two groups.

**Renamed, same intent, main's version is the current contract:**

| stash | main |
|---|---|
| `test_final_db_has_110_columns` | `test_final_db_has_114_columns` |
| `test_critical_banned_blob_warning_cannot_coexist_with_safe_core_verdict` | `test_critical_banned_blob_warning_rejects_safe_scorer_artifact` |

**Deliberately inverted — carrying these over would reassert retired behaviour:**

| stash asserts | main asserts instead |
|---|---|
| `test_banned_inactive_forces_blocked_core_verdict_when_scorer_says_safe` | `test_banned_inactive_rejects_inconsistent_safe_scorer_artifact` — reject the inconsistent artifact rather than silently forcing a verdict |
| `test_high_risk_exact_match_sets_caution_blocking_reason_without_banned_flag` | `test_high_risk_exact_match_keeps_caution_blocking_reason_null` — the opposite expectation |
| `test_core_row_honors_scorer_emitted_high_risk_blocking_reason` | `test_core_row_rejects_stale_high_risk_blocking_reason_on_caution` |
| `test_v4_banned_substance_suppresses_score_even_when_v4_gate_scored` | `test_v4_banned_substance_rejects_inconsistent_scored_artifact` |
| `test_v4_dedup_keeps_scored_over_blocked_same_upc` — drops the blocked row | `test_shared_upc_retains_scored_and_blocked_formula_candidates` — **blocked products must ship with their reason** |

That last pair is the important one. Dropping a blocked product on a shared UPC is precisely the
defect the owner rule "banned/recalled products ship with their reason" exists to prevent.

**Measured, not assumed.** The four remaining tests with no name match
(`detail_blob_keeps_unscored_label_rows_in_supplement_facts_order`,
`detail_blob_nests_all_multi_form_components_without_flat_duplicates`,
`detail_blob_nests_parenthetical_folate_form_under_declared_total_row`,
`display_ledger_preserves_unscored_supplement_fact_dose_and_order`) were copied into the tree and
run against current code. **All four fail**, and the failures are the label-hierarchy integration
doing its job:

    ['Vitamin A', ... 'Vitamin K2']  ==  ['Vitamin A', 'Vitamin K']      K2 now nests under K
    ['Fish Oil', 'EPA', 'DHA']       ==  ['Fish Oil', 'Total Omega-3 Fatty Acids', ...]
    {'label_order': 1}               !=  {'label_order': 2}

The probe file was removed after the run.

---

## Branches

| branch | state | note |
|---|---|---|
| `main` / `origin/main` | — | convergence target |
| `claude/evidence-expansion` | INTEGRATED | evidence-expansion work; see the commit list in the convergence commit |
| `converge/main-20260918` | INTEGRATED | a concurrent session's convergence of four sessions; its inventory was re-verified here rather than trusted |
| `recovery/stash-0..3` | PRESERVED | kept until converged main is proven healthy |

## Worktrees

| path | state |
|---|---|
| `/Users/seancheick/Downloads/dsld_clean` | this session |
| `/private/tmp/pg-converge-20260918` | another session's convergence worktree — not touched |
| `.../scratchpad/canary` (detached) | scratch |
| `/private/tmp/pharmaguide-calibration-20260915-KbQalZ/baseline` (detached) | scratch |
| `/private/tmp/rubric_base_audit` (detached) | scratch |

## Uncommitted

| path | state |
|---|---|
| `scripts/banned_recalled_accuracy_report.json` | PRESERVED in place — a concurrent FDA-sync session's live edit, a generated timestamp. Not staged, not reverted. |
