---
name: data-fix
description: Use when correcting or adding PharmaGuide curated data (chemical aliases, ingredient forms, clinical citations, interaction rules, identifiers, label corrections, overrides), one entry or a batch of related entries.
---

# Curated data correction

**Batch by topic, verify per entry.** Related entries go in one batch; every entry gets its own
evidence review and its own result; the batch is applied, verified, tested and fixed together.
**One brain:** canonical pipeline owners decide; consumers render. Correct known errors without
inventing replacement facts or preserving an incorrect score.

## Batch recipe

1. **Scope.** One file or topic, small enough to review line by line. List the entry keys;
   `$PG_PYTHON scripts/data_batch.py check FILE --since origin/main` prints the key format.
2. **Research, per entry.** One receipt per entry (section 2). Up to 3 subagents may gather
   receipts in parallel. A receipt is a hypothesis: the main model checks each one before it is
   applied, and reads the source itself for every safety-bearing entry.
3. **Regression first.** Tests that fail for the batch's defects (section 3).
4. **Apply.** One script: `data_batch.load` → an explicit patch per entry → `data_batch.save`
   (canonical JSON, `_metadata` recount). Never loop API output into data (`--apply` included).
5. **Prove it landed.** `data_batch.py check FILE --since <ref> --expect <keys>`: every expected
   entry changed, nothing else did, the counts match.
6. **Verify the changed entries.** `verify_all_citations_content.py --changed-since <ref>` and
   `verify_interaction_rules_citations.py --strict --changed-since <ref>` print one line per changed
   citation; `verify_cui.py` / `verify_unii.py` / `verify_pubchem.py` for each new identifier.
7. **Test surgically.** Follow `AGENTS.md`'s fix loop: explicit failing nodes, defect-class edge
   cases, then relevant changed-entry/owner files. Fix every failure class before requesting the
   integrator's combined checkpoint; do not run a whole suite for each edit or atomic commit.
8. **Measure** when a score, warning or verdict can move: `scripts/audits/quality_redesign/replay.py`
   `freeze-raw` once, `snapshot` on both trees, `compare` (see `/pg-scoring-change`).
9. **Commit once per batch.** The message lists the entries and anything left pending. Receipts go
   in the register's `research.md` (or `scripts/audits/<batch>/research.md`).

## 1. Establish the actual checkout and owner

Use the active task's repository/worktree, not a hardcoded directory. Inspect `pwd`, `git status --short` and the relevant diff; fetch before asserting branch/main state. Preserve other agents' edits. Tests and edits must use the same checkout. Do not switch branches, stash, reset, stage unrelated files or run a release as an incidental cleanup.

Read the actual entry, neighboring forms and runtime loader. Check metadata/migration history if two files look canonical. Distinguish curated error from matcher, converter, extractor or exporter error. Trace label image → retained raw → cleaned → enriched when identity/quantity is disputed; do not reconstruct a fact missing upstream. Fix a shared generator at its owner rather than compensating in data or Flutter.

## 2. Establish evidence before changing meaning

Use available repository API clients/verifiers and primary sources. Record the exact record/field, source URL or identifier, verification date, relevant result, applicability and unresolved facts in one bounded receipt per entry. Reuse still-applicable verified receipts; do not repeat research merely because a new agent started.

- **Chemical identity and aliases:** verify the exact compound, salt, stereochemistry, hydrate, species/part or preparation using appropriate identifiers and source content. An API search hit, synonym list or similar name alone is not equivalence. “Natural,” “animal-based,” generic nutrient names and marketing wording alone do not establish a specific chemical form. Preserve raw names/provenance. Verify reused identifiers as well as new ones.
- **Clinical claims:** identifier resolution is not content verification. Check intervention/formula, route, population, dose/course, endpoint role and direction. Combination, surrogate, null or post-hoc findings cannot become positive single-ingredient efficacy.
- **Known wrong mapping, unknown replacement:** remove or contain the false identity at the canonical owner now; keep unresolved form/eligibility explicit. Use an existing unspecified form only if its semantics honestly fit. A separate, correctly identified salt must not be silently relabeled as free nutrient. Replacement efficacy points may remain pending. Do not retain a proven wrong alias solely because live scores might change or a new form lacks a bio score.
- **Schema pressure:** never invent a synonym, identifier or score to satisfy a minimum-count constraint. Use a genuinely verified specific synonym if appropriate; otherwise review the schema's legitimate empty/unknown representation.

## 3. Reproduce and make the smallest complete correction

Write regressions that fail for the intended defects before editing. A fixture/setup error or skipped test is not that failure. Keep portable invariants separate from optional corpus tests.

Correct each canonical entry together with its dependent contract: alias destination, related prose, review attribution and generated ownership as needed. Leave no contradictory sibling mapping behind. Update free text that asserts the old value and assert the obsolete phrase is gone. Do not attribute agent review to Sean, Claude or a clinician who did not perform it.

Search siblings once and record dispositions: fixed, confirmed unaffected, uncertain pending, or separately queued. Do not turn every correction into an unbounded neighboring-data audit. If the defect is shared matching/precedence, fix and test that owner rather than adding ingredient-specific exceptions.

## 4. Verify behavior and impact

From the active checkout use `scripts/test.sh` (never raw pytest or an unverified system interpreter) and `$PG_PYTHON` from `scripts/python_env.sh` for verifiers; inspect their supported arguments and write reports to explicit paths. Verifier availability does not prove the particular claim was checked.

For aliases/routing: test cleaner and enricher, explicit versus generic forms, parent/child quantity ownership and source preservation. For shared precedence/conversion changes, inspect all changed lookup owners and measure a full-corpus diff at the batch checkpoint. Verify real affected labels; stale enriched rows do not change merely because the source registry changed. Record required regeneration separately.

Synthetic green and a broad pass do not establish clinical correctness or release readiness. Full/release gates and fresh-corpus review still apply before release; never run the full backstop alongside a corpus run.

## 5. Checkpoint and report honestly

Report one result per entry (key, before → after, receipt, verdict), root causes, exact checks/counts/skips, affected real products, unresolved siblings, regeneration need and whether anything was released. For coverage distinguish purpose-resolved, each pillar assessed, all six complete, and safety-suppressed. What-if rules are not reviewed production coverage.

Commit only completed, reviewed, verified owned files. Known-failing work is unfinished, not a completed checkpoint. Release remains a separate explicit task through the canonical release owner; no silent upload or score fallback.

Preserve existing safety verdict precedence and explicit clinician-review holds. Clinical evidence and editorial numerical policy are distinct: a UL is not automatically an optimal supplemental target, and a score must not override a safety gate. Seek only approval actually required by an applicable hold or undelegated decision; do not invent a new clinician gate for every routine factual correction. Document warning/eligibility changes and the actual authority used.
