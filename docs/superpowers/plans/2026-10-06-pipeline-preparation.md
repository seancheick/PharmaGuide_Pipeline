# Aggregate Pipeline Preparation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** One source-grounded, aggregate preparation report before one necessary corpus run.

**Architecture:** Extend preflight.py to orchestrate existing validators and raw canaries; test_profiles.py owns test-phase coverage. Existing pipeline_freshness owns regeneration decisions; preparation receipts reuse identical successful checks without changing clinical/export policy.

**Tech Stack:** Existing Python 3.13, pytest9/scripts/test.sh, Bash batch runner, JSON internal reports. No new dependencies.

Owner: preflight.py::run_preflight; test_profiles/conftest/test.sh; existing freezer/replay and pipeline_freshness. Evidence: current definitions and matrix/glossary/caller searches. Will NOT create a second scorer, registry, public status, new clinical policy or separate owner module.

## One coupled implementation batch

Files: scripts/preflight.py, scripts/test_profiles.py, scripts/tests/conftest.py, scripts/test.sh, scripts/test_lock.py, scripts/audit_dead_code.py, batch_run_all_datasets.sh; existing preflight/profile/runtime/batch tests; only affected mixed test files where artifact dependencies need explicit existing markers. Integrator owns master/LEDGER/handoff/skill/runbook updates.

- [x] Audit existing excluded test profiles and actual generated-input dependencies; put source-only and generated-artifact cases in an explicit complete phase inventory within the existing owner. Do not infer correctness from file names or broad skips. Keep normal fast/local/release semantics intact.
- [x] Write fail-first regressions in existing owner files for multi-failure aggregation, blocked prerequisites, complete test coverage/unexpected skips, immutable inputs and receipt invalidation/reuse/tampering, and pre-brand batch abort. Use temporary fake validators/repos for orchestration and real tracked raw canary controls for the calculation boundary.
- [x] Run each red class with scripts/test.sh fast <explicit file/node>; preserve logs outside /tmp. No whole fast/full run per edit.
- [x] Implement minimal preparation mode/CLI in existing preflight.py. Use subprocess argument arrays and existing helpers. Default to one worker and source checks before corpus; accumulate independent results. Source inventory and report enumerate deferred artifact tests and known manual/publish requirements, never auto-approve scores/clinical facts. Write reports atomically. Reuse checks only when content fingerprints and command/arguments match and required completed successful fields are intact.
- [x] Add preparation test selection/reporting through existing test.sh/profile/conftest owners; avoid duplicate phase declarations. Audit mixed files and preserve meaningful source assertions. Existing artifact markers classify the genuinely generated cases; no new clinical/public state. Consider existing junit/skip guard for outcomes, not terminal-string guesses.
- [x] Replace full-batch raw-canary-only call with aggregate preparation. Keep targeted behavior and existing operations/publication guards. Extend shared fake batch dependency setup rather than fixing individual tests. Route existing redundant file checks to preflight owner where safe; report any fingerprint impact.
- [x] Run the stable owner/consumer slices and first real-data aggregate; classify its complete failures before correcting the shared owners. Preserve machine-wide lock policy and avoid corpus/export/publication jobs.
- [x] Obtain fresh spec and correctness review; fix findings by class and commit the completed source candidate.
- [ ] Final acceptance: demonstrate successful real preparation and valid unchanged-input receipt reuse; one completed-candidate whole-fast CI checkpoint; integrate via PR, verify origin/main containment and clean up. Final acceptance results live in the existing LEDGER, master plan and current handoff.

Commands: scripts/test.sh fast scripts/tests/test_preflight_fail_closed.py scripts/tests/test_batch_run_all_datasets.py scripts/tests/test_python_runtime_contract.py plus discovered profile owner files. Real preparation uses the existing staged brands root, a durable report under /Users/seancheick/pg_quality/pipeline_preparation_20261006/, and existing candidate artifacts only when checks require them. Test-only/CLI infrastructure must not require another Clean/Enrich/Score unless actual fingerprints prove it.

Review refinements:
- Inventory existing opt-in/external tests separately, with exact requirements and deferral reasons. Never enable remote writes, disposable Supabase jobs, or OCR opt-ins automatically. Run unconditional cases in mixed files early.
- Inventory non-pytest gates owned by test.sh::run_release_artifact_gates; preserve live citation freshness requirements separately from generated catalog checks.
- Bind receipts to effective runtime/environment, commands, complete input inventory and content hashes; validate evidence payloads, node coverage and outcomes independently. Recompute inventories after checks, including additions, deletions and duplicate raw discovery.
- Broad preparation uses the existing machine-wide suite lock even when passing explicit node lists. The raw owner is scripts/tests/freeze_contract_snapshots.py --check --raw-root.
- Preparation success is not release readiness; deferred post-run and publication checks remain authoritative.

Collected infrastructure refinements: skip-policy duplicate/type integrity; inherited descriptor propagation and preparation entry validation; FDA UNII source-test dependency fingerprints; taxonomy-owned condition synonyms versus deprecated ingredient/root fields; justified dynamic harness entry points under the existing dead-code audit. Diagnose the completed aggregate first, then fix these shared classes and validate one completed candidate.
