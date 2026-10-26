# Submission correction repair implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Track each proven outcome below.

**Goal:** Repair the independently reported submission correction integration defects and reconcile the shared migration deployment stream.

**Architecture:** Extend the existing import, storage upload, submission transition, evidence, deletion, and client presentation owners. Preserve immutable deployed migration SQL; apply database behavior through a forward migration. Preserve production timestamp aliases in the assembled migration stream.

**Tech Stack:** Python, PostgreSQL/Supabase, Deno TypeScript, Flutter/Dart.

Owner: `scripts/product_submission_import.py::materialize_approved_submissions`, `scripts/supabase_client.py::upload_file`, `scripts/sync_to_supabase.py`, app submission RPCs, evidence revisions, `ProductSubmissionSummary`, and existing migration history/deployment scripts. Evidence: report source traces and `rg` of names and stems in both repositories, matrix and glossary. Will NOT create another identity, scoring, points, evidence store, or review system.

- [x] Reproduce release discovery signature, historical version collision, unpromoted revision supersession, and label/receipt crash failures; fix owners with behavioral regressions and named tests.
- [x] Reproduce approved-user deletion; allow only the auth-user cascade while rejecting direct approval or parent destruction. Test synthetic account deletion and unchanged ordinary immutability.
- [x] Distinguish pending submitter retakes from reviewer uploads in queue and client. Test mixed queue, first approval copy, correction copy, exclusive contribution counts and actionable photo request priority.
- [x] Fix evidence revision allocation after abandonment, cleanup/finalization race, promoted retake request/open, and pending target exclusion using approval revisions. Test all transitions and concurrency.
- [x] Repair retention fixture with actual old timestamps and positive cleanup control.
- [x] Assemble complete migration history reproducibly from pinned repository sources, hashes and aliases. Verify recorded SQL, matching history, empty history-only dry run and disposable schema replay before forward deployment.
- [x] Run focused SQL/Deno/Flutter/Python checks, corpus local gate, independent spec and adversarial quality review, and exact candidate CI. Fix findings before merging.
- [x] Merge both repositories under existing authorization; deploy forward migration and affected functions; verify backend state, grants, synthetic stale refusal and unchanged business baseline. Keep current catalog and defer pipeline/publication to Sean.

Acceptance detail: simulated full sync must execute real discovery through activation. Every versioned DB/index path uses create-only writes with exact-byte retries and concurrent collision coverage. Import tests retain rollback, same-revision hash, manual-edit refusal and last-promoted-artifact protections. Capture production migration statements, approval payload hashes/mappings, points, manifest and Storage metadata before deployment; compare the disposable schema's functions, constraints, policies, grants and triggers with expected production definitions and verify the business baseline afterward. The corpus gate is `scripts/test.sh local` against existing artifacts, without generating a corpus.

## Verified delivery

Integrated via app PR149 (merge11b53739; tested4c477302, CI40362086808) and pipeline PR252 (merge44f252ac; tested738b1d2a, CI40361539272 all four shards). Independent review findings were reproduced and fixed; the alleged evidence-request race was ruled out by the existing helper lock and a disposable two-session probe.

Final named importer/sync192 and privacy recovery3 pass; pipeline local546 pass24 declared opt-in skips. SQL137 incl concurrency, Edge76, affected Flutter72 plus reviewer access17, clean analysis. Six local golden differences reproduce unchanged on app main e7255417; CI passes with the existing platform-sensitive golden exclusion.

Canonical stream applied only forward20261026160229 and historical active-stack index repair20261026164414. All65 prior migration ledger records/SQL unchanged;67 versions match, no pending SQL. Full disposable replay passes and live schema matches1017 distinct public definitions/access records, named columns and indexes; historical physical column order is excluded. Deployment config/SQL hash verification included.

Reviewer Edge37 ACTIVE/JWT; all14 deployed files match merged source; unauthenticated401 and synthetic stale55000 refusal pass.25 approvals,15 ledger entries150points and149 private evidence objects unchanged; all retained business hashes match. Existing security advisor classes/counts unchanged; one expected unused-index info added for the restored index. Reviewer-account provenance RESTRICT constraints remain outside approved-submitter cascade repair.

No corpus generation, catalog publication, or App Store release performed. Recovery receipts/logs remain at /Users/seancheick/.codex/submission-repair-*. Private primary inputs and unrelated editing lane preserved.
