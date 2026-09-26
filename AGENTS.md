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
scripts/test.sh fast -k <kw>   # iterating: only the topic you touched
scripts/test.sh fast           # checkpoint: completed batch or shared-code change
scripts/test.sh release        # release gates before a ship
scripts/test.sh full           # post-pipeline backstop, never alongside a pipeline run
```

Pick the rung by what changed and say which rung ran. Docs/config-only changes need no pytest.
"Done" without output from the rung that covers the change is not done.

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
- Verdict precedence: BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE.
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
  data, pushes, releases.
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
- **One entry at a time.** Never bulk-apply API results or batch-edit curated data; batch
  operations skip entries silently.
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
  touch) early in your worktree's `.claude/state/CURRENT_HANDOFF.md`. Every agent reads the other
  lanes there before editing a shared owner (scoring config, matrix, rule files, export contract).

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
