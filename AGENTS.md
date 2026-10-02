# PharmaGuide Pipeline — agent constitution

Shared by Claude, Codex and every other agent; Claude loads it through `@AGENTS.md` in CLAUDE.md.
Kept short on purpose: path-specific rules live in `.claude/rules/`, procedures in skills, rationale
in `docs/adr/`, ownership in `scripts/contracts/source_of_truth_matrix.json`.

## Project

- Pipeline Clean → Enrich → Score → Export: NIH DSLD supplement labels become evidence-based scores
  plus a catalog and interaction DB for the Flutter app at `/Users/seancheick/PharmaGuide ai`.
- Repo github.com/seancheick/PharmaGuide_Pipeline is **public** (a push is publishing); the local
  dir is still `dsld_clean`. Python 3.13, pytest 9.
- `git fetch` before asserting commit/branch state: Codex, Claude and rebuild automation all commit
  here, and the session-start git snapshot goes stale. The main-checkout agent has been seen
  fast-forwarding local `claude/*` branches into `main` within seconds, so treat a commit as a
  handoff and verify before committing.

## Tests — `scripts/test.sh`, never raw pytest

Raw `python3 -m pytest` picks macOS Python 3.9 and runs every heavy test (~1 h).

```bash
scripts/test.sh fast scripts/tests/test_<topic>.py::test_<case>  # one failure / one edit
scripts/test.sh fast scripts/tests/test_<topic>.py -k <kw>      # affected defect class
scripts/test.sh local          # pipeline code or data changed: the corpus tests CI cannot run (~2 min)
scripts/test.sh fast           # whole suite: CI runs it on every push; locally only if CI is down
scripts/test.sh release        # release gates before a ship
scripts/test.sh full           # post-pipeline backstop, never alongside a pipeline run
```

- Use focused tests while iterating; run one final whole fast checkpoint in CI. Push the branch (`claude/*`, `codex/*`; Sean,
  2026-10-02) and GitHub Actions `pipeline-tests` runs it. Merge on green CI, plus `local` when
  pipeline code or data changed.
- CI has no product corpus, builds or raw DSLD datasets; it checks out the app repo for cross-repo tests (FLUTTER_REPO). A test that needs them goes in `LOCAL_ONLY_TEST_FILES`
  (`scripts/test_profiles.py`); `scripts/ci_skip_guard.py` fails CI on any other skip reason; the local rung rejects missing corpus/build skips.
- `scripts/test.sh` holds a machine-wide lock: one full/release/slow suite at a time, alone;
  broad fast/local suites share it and split the worker budget. Focused runs (named files or
  nodes) take no lock and never wait. A waiting broad run is queued, not hung.

Pick the rung by what changed and say which rung ran. Documentation-only changes need no pytest;
scoring, clinical-data and runtime configuration changes require their affected checks.
"Done" without output from the rung that covers the change is not done.

**Iteration is targeted; broad validation belongs to a finished batch, not an edit or commit.**
Never run the whole fast/full/release suite after one edit or one failed test. A bare
`fast -k <kw>` still collects the broad suite: name the test file or node first. Atomic commits
do not each require a broad checkpoint. Do not weaken an assertion merely to make a test pass.

**Fix loop: classify together, fix surgically, validate the combined candidate once.**
1. Classify every finding first; write a failing test per class, with the edge cases existing
   policy implies.
2. Reproduce the failing node, fix its production owner, rerun that node, then the nearby edge
   cases for the same defect class. Use `git grep`/`rg`, the ownership matrix and callers to
   identify affected test files; that list is discovery, not a command to rerun every consumer
   after every edit. Run the relevant owner/consumer slice when the class is stable.
3. Check the fix on the affected labels plus unaffected controls with
   `scripts/audits/quality_redesign/replay.py` (freeze-raw, snapshot, compare), never by
   rerunning whole brands.
4. The integrator schedules one combined checkpoint after the batch's source changes, focused
   tests, measurements and required review are ready: green `pipeline-tests` CI on the exact
   candidate commit, plus `scripts/test.sh local` when pipeline code or data changed. If it fails,
   record all failures, fix each class using explicit nodes/files (or `--lf` with the failing
   files), then rerun the combined checkpoint once after all fixes are ready. Do not restart it
   after each individual fix. Run the whole fast suite locally only when CI is unavailable.
5. After the last code change and the merge of main: one corpus pass from the earliest changed
   stage, then the release rung. Its preflight refuses output built by other data or code.

Before a broad job, check active jobs and lane handoffs. Full/release/slow suites run
one at a time; never run a broad suite alongside a corpus job. Broad fast/local suites
share bounded one-worker slots, reserving headroom for focused checks. Focused fast
checks naming files or nodes bypass the suite queue and use one worker.
For timeouts, inspect contention first and rerun the affected nodes in isolation; a successful
retry explains neither a source defect nor the interrupted checkpoint by itself. Reuse existing
receipts only when their source/data fingerprints cover the candidate; otherwise revalidate.

**Progress and resume:** every agent first reads this file, its current handoff, the relevant
master-plan boxes and LEDGER entries. Record goal, owned files, baseline and next unchecked item
before editing. Update the existing LEDGER and master plan at batch handoff: findings, fixes,
tested SHA, commands/results, measurements, review and remaining blockers. Check only the
deliverable its evidence proves; distinguish implemented, measured, reviewed, integrated and
release-validated. Never mark a whole phase complete from a focused test, or leave finished work
looking pending. Keep one execution register and rewrite handoffs instead of stacking history.

## Pipeline map

| Stage | Entry point |
|---|---|
| Corpus run | `batch_run_all_datasets.sh` — can publish; see "Operations safety" |
| One brand (iteration) | `scripts/run_pipeline.py` |
| Clean | `scripts/clean_dsld_data.py` → `scripts/enhanced_normalizer.py` |
| Enrich | `scripts/enrich_supplements_v3.py` (mega-file: gray box, test at the boundary) |
| Score | `scripts/score_products_v4.py` (batch I/O) → `scripts/score_supplements_v4.py::score_product_v4` → `scripts/scoring_v4/scored_artifact.py` |
| Export / release | `scripts/rebuild_dashboard_snapshot.sh` → `scripts/release_full.sh` (`build_final_db.py`, Supabase, Flutter bundle) |

Data files live in `scripts/data/` (schema: `scripts/DATABASE_SCHEMA.md`). Each has a `_metadata`
block — read counts and versions from it; never copy them into docs.

## Production score (v4) — one public scorer

- Six pillars /100: Formulation 20, Dose 20, Evidence 20, Transparency 15, Verification 15,
  Safety/Hygiene 10. `scripts/scoring_v4/config/quality_score.json` is the only production config.
  Export consumes the scored artifact directly and never runs a second scorer.
- Frozen fields: `quality_score_v4_100`, `quality_score_status` (`scored` / `suppressed_safety` /
  `not_scored`), `quality_pillars_v4`; `score_100_equivalent` and `score_display_100_equivalent` are
  compatibility mirrors. Never reintroduce `score_quality_80` / `score_display_80`.
- Consumer quality: `quality_tier` / `quality_score_status`. Consumer safety: `product_safety_status`, with banned/recalled reasons retained. A quality tier never changes safety. Legacy `verdict` is compatibility/readiness only; POOR is readable in old catalogs but never newly emitted.
- Ingredient-level safety flags are `has_banned_substance` / `has_recalled_ingredient`; never
  `is_recalled`.
- Scoring invariants: `.claude/rules/scoring.md`. Changing a score: the `/pg-scoring-change` skill.

## Truth order — memory never overrules code

1. Current code and the artifact it produces (what actually ships).
2. `scripts/contracts/source_of_truth_matrix.json` and accepted ADRs (intended ownership).
3. Tests, contracts, audit reports.
4. Docs, then memory and chat history — evidence only.

When behavior and intended ownership disagree, that is a finding: report it, don't silently pick
one. Never change code to match a memory entry. `docs/archive/`, `docs/superpowers/` and old
bug-fix notes are history, not specifications.

## Autonomy — decide, don't queue

- Before asking Sean: inspect the owner, current state and artifacts, run a safe probe, check
  history. Most "forks" already have a doctrinal answer — apply it, measure, record it in the handoff.
- **Sean decides only:** a new semantic owner (new persisted or public/export field, new status or
  verdict meaning, new scoring/clinical policy or owner, new registry), deleting curated clinical
  data, pushes to `main`, releases. Pushing a `claude/*` or `codex/*` branch for CI is routine.
- Private helpers, local names, test utilities and internal files need no approval once the
  Owner Check passes.

## Bugs you find

- Fix them: failing test first, the fix in its own atomic commit, logged in the handoff, then back
  to the task. No TODO left behind; no tangent into a redesign.
- A fix that moves shipped scores or safety verdicts still gets the measurement in the
  `/pg-scoring-change` skill.
- On an infrastructure branch (harness/config/docs) fix only infrastructure bugs. For an application
  defect: reproduce it, record `path::symbol` + probe + impact + confidence in the handoff, and spawn
  a separate fix task. A P0 stops the work and goes to Sean.

## One brain — extend the owner, never build a second one

- Before creating any field, state, status value, module, normalizer, queue, registry, skill or
  file, run an **Owner Check**: the matrix, `scripts/GLOSSARY.md`, and `rg` for the name *and* its
  stem. Extend what exists. Owners bypassed before: `scripts/normalization.py` (the only
  normalizer), IQM parent `relationships`, `form_match_status`, `rda_ul_data.adequacy_results`
  (Dose), `scripts/scoring_v4/cert_evidence.py` (certification).
- Reuse existing field names (`notes`, `name`, `category`, `aliases`); one description field, not a
  short/long pair. `score` beside `score_new` is a defect.
- Duplicated decision logic → one shared util every consumer (scorer, pillar copy, export, app)
  calls. Copies drift silently and green suites don't catch it.
- Classify before removing an apparent duplicate:
  - *false dual brain* (same decision, different rules) → delete the weaker, route callers to the
    production seam;
  - *one policy, many consumers* → keep all, share ONE result object;
  - *two policies, one topic* → keep both, unify the contract.
- **Owner Check block**, required in every plan and handoff:
  `Owner: path::symbol — evidence: <command>` or `No owner: searched <matrix, terms, glossary>`,
  then `Will NOT create: …`. Line numbers are supplementary only.

## Dead code and fields — delete once proven dead

- Proof: a key census across artifact layers, a corpus line trace of the production entry point,
  or zero references.
- Zero references alone is not proof. Also check lazy/`getattr` imports, shell and release scripts,
  JSON/config, export consumers, migrations/compat contracts, manual CLI use, and the Flutter repo:
  `rg <name> scripts/ *.sh "/Users/seancheick/PharmaGuide ai/lib"`.
- Remove the code, its docs and its tests in one commit; no "legacy" shim unless a named consumer
  is live. A dormant data-driven guard (trigger absent from today's corpus) is not dead.
- Deleting curated clinical data or a live public contract needs Sean.
- `scripts/audit_dead_code.py` lists candidates (`functions`; `keys` for values never read). The
  fast-rung ratchet fails on new unreferenced or test-only production code: delete it, or add it to
  `KEEP` with its reason. Dead code met while working in a file leaves in its own commit.

## Cross-repo contract (pipeline → Flutter)

| Seam | Owner |
|---|---|
| Blob top-level keys | `scripts/audit_contract_sync.py::BLOB_TOP_LEVEL` — the one declaration; the audit fails on undeclared keys |
| Core DB columns | `scripts/core_export_model.py` |
| Export schema doc | `scripts/FINAL_EXPORT_SCHEMA_V1.md` |
| Flutter core reader | `lib/data/database/tables/products_core_table.dart`, `lib/data/database/products_core_projection.dart` |
| Flutter blob reader | `lib/data/supabase/detail_blob_service.dart`, `lib/data/providers/detail_blob_provider.dart` |

- Adding an export field: declare it in `BLOB_TOP_LEVEL` / `core_export_model.py` and name its
  Flutter consumer. Renaming or removing one: `rg` Flutter `lib/` first and change both repos together.
- Detail-blob flags are real JSON booleans (`build_final_db.py::json_bool`). `safe_bool` (int 0/1)
  is for SQLite core columns only.
- The pipeline decides; Flutter renders. Flutter never recomputes a pipeline score or verdict.

## Non-negotiable data rules

- **No unverified clinical claim or identifier.** Every mechanism, severity or interaction needs a
  citable source; PMID/CUI/RXCUI/UNII/NCT/CAS/CID are content-verified against the live API. A real
  PMID about the wrong topic is a ghost reference — a defect. Details: `.claude/rules/clinical-data.md`.
- **Batch by topic, verify per entry.** Related entries go in one reviewable batch. Each entry gets
  its own identity and source check by content and its own result; `scripts/data_batch.py check`
  proves the applied diff matches that list exactly (batches that skip entries silently are the
  failure this guards). Then verify, test and fix the batch together. Verifier output never goes into
  data unreviewed (`--apply` included).
- **Identity by chemistry, not name.** Confirm via PubChem CID / CAS / InChI and search existing
  entries before adding one.
- **Two similar data files?** Check `_metadata.schema_version`, migration history and what the
  loader reads — never guess from the filename.
- **Changing a structured value** means fixing every free-text field that references it and
  asserting the old phrase is gone.
- **A specific clinical lock beats a generic floor.** Exempt and pin the generic test; never raise
  a score to satisfy it.
- **Banned/recalled products always ship** with their reason (BLOCKED). A withheld product answers a
  scan with "not found" and hides the ban; under-warning is the worse failure.
- **Pipeline safety copy uses risk-matched verbs.** `safety_warning_one_liner` / `safety_warning`
  in banned_recalled and harmful_additives use Stop using / Do not use / Avoid / Talk to your
  doctor by hazard context, and are never blanket-rewritten. The app renders this text verbatim
  and keeps its own strings calm-advisory (Flutter AGENTS.md).
- **Outside-agent claims** (Codex, reviews, other models) are hypotheses: reproduce each against the
  real file before agreeing or refuting.

## Operations safety

- `batch_run_all_datasets.sh` without `--targets` continues into the snapshot and `release_full.sh`
  (Supabase + Flutter) unless `--pipeline-only`; `SKIP_RELEASE=1` skips the publish but still runs
  the snapshot. `--targets` implies pipeline-only unless `--release`. Run it as
  `source scripts/python_env.sh; PYTHON="$PG_PYTHON" bash batch_run_all_datasets.sh …`.
- At most one full-corpus job at a time (16 GB Mac), never alongside the full suite. Keep durable
  inputs outside `/tmp` — a reboot wipes it.
- One worktree + branch per agent; one integrator mutates and pushes `main`. Stage explicit paths
  only. Re-check the branch tip before claiming a lane. Record your lane (goal + files you will
  touch) early in your worktree's `.claude/state/CURRENT_HANDOFF.md`, and rewrite that file on each
  update instead of appending (git keeps history; a stacked handoff costs every resume). Every agent
  reads the other lanes there before editing a shared owner (scoring config, matrix, rule files,
  export contract).

## Engineering principles

- Build lazy: shortest working diff, no speculative scaffolding. Complexity creates obligations,
  not bonuses.
- Small batches, atomic commits, localized blast radius. Deep modules with simple interfaces.
- A change that adds volume without removing complexity gets pushed back — this file included.

## Knowledge placement

| Knowledge | Lives in |
|---|---|
| Current task state of a worktree | `.claude/state/CURRENT_HANDOFF.md` (gitignored; `/handoff`, `/pg-resume`) |
| Ownership decision + rationale | `source_of_truth_matrix.json` + `docs/adr/` |
| Executable lesson | regression test |
| Path-specific invariant | `.claude/rules/` |
| Procedure repeated 3+ times | skill |
| Stable preference or correction | auto memory — never architecture, policy or branch state |
| History | git + audit artifacts |

## Navigation

- `graphify-out/` is a navigation hint, never evidence: compare `graph.json` `built_at_commit` with
  `git rev-parse HEAD`, and verify with `rg`/Read when they differ.
- New terms go into `scripts/GLOSSARY.md` first. Deeper references: `scripts/SCORING_ENGINE_SPEC.md`,
  `scripts/PIPELINE_ARCHITECTURE.md`, `docs/runbooks/verification-gates.md` (audit and API verifiers).
- API keys load via `scripts/env_loader.py` from `.env`. No linter: follow the existing style.
