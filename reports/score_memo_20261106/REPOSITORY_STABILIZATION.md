# Repository-wide efficiency and integrity follow-up — November 6, 2026

The execution register is the existing [LEDGER](../../scripts/audits/pending_items_20260926/LEDGER.md). This report records evidence; it is not a second tracker or release approval.

Owner: existing scoring scope/resolvers, configuration/reference reader, batch processor and tracker, Enrich collector, export, incremental snapshot, dashboard and storage inventory. Evidence: targeted source tracing, fail-first tests, complete frozen replay and independent review. Will NOT create another scorer, clinical registry, public state or persistent cache platform.

## Delivered changes

- Reuse exact clinical and role contexts through the existing product scope; share the existing quality configuration and identical botanical/therapeutic indexes.
- Reuse Clean workers across batches, keep diagnostics per label, bound variation caching, delegate reporting to its tracker, and index quality-row matching once per product.
- Preserve accumulated legacy-resume reporting and full summaries; refuse inconsistent snapshots, preserve fallback IDs and prevent rejected duplicates from inflating reports.
- Reuse the product contract throughout export, keep safety parity at the standalone core seam, and calculate both replay projections from one score pass.
- Capture reference data once and independently verify its bytes/inventory afterward. Preserve execution-time invalidation and fail-closed recovery.
- Research freshness, dashboard connection lifetime and complete bounded storage listing fixes were separately qualified and merged through [PR405](https://github.com/seancheick/PharmaGuide_Pipeline/pull/405).
- Clarify the current directed-daily Dose policy while retaining its superseded declared-serving history.

## Validation

All seven routes are represented. Forty full raw Clean/Enrich/Score/blob captures and one separate intentional-null-score capture have zero differing paths under the existing clock exclusions. Exporting the same frozen inputs through both versions yields **41 exactly equal whole blob/core payloads**, with no ignored export fields. The null-score control remains exportable with no quality score and `not_assessed` safety.

Local: **564 passed / 24 declared live-tool skips**, strict guard passed. Python correctness: zero new findings; dead-code ratchet: zero unapproved findings. Named fail-first and isolation guards cover each changed behavior. Independent reviews identified and corrected fallback-ID restoration, report shape validation, duplicate diagnostics, actual export-input isolation and historical replay compatibility.

The controlled 41-product warm scoring/export microbenchmark compares against qualified PR404. Export improves **2.34×** (9.698 to 4.142 seconds summed per-product medians); scoring is approximately flat (11.075 to 11.026 seconds). Peak RSS changes from 325,222,400 to 306,528,256 bytes. These are scoring/export measurements, not whole-pipeline or corpus throughput.

The initial timing flag for product70018 was investigated, not discarded: ten isolated warm repetitions measured 0.600 versus 0.598 seconds, with exact output/input parity. Targeted cache ablation also preserved output and showed the expected benefit on the complex315334 fixture. The initial flag and follow-up remain in the receipt.

Deterministic defect-level improvements include export input builds11→1/product; reference reads388→194/snapshot with an independent final check; three-batch serial worker initialization3→1 and stable pool construction2→1; forty-row identity preparation1640→80; replay score calls2→1. These are separate workloads and are not additive speedup claims.

An initial local setup attempt failed the strict skip guard because current canary inputs were absent; attaching the primary directory exposed stale canaries. The existing qualified PR404 canaries were then bound by checksum,132 owner checks passed, and the full local profile passed. Original inputs, assertions and baselines were preserved.

## Candidate dispositions and limits

Identical therapeutic/botanical indexes now share their owner (about0.568MiB of duplicate graph retention removed per process). Remaining export projections measured below0.1% of the sampled export profile; an alternate SQL join saved about0.052 seconds over15,447 synthetic rows and would complicate duplicate/unmatched accounting. Their existing implementations remain. Reference loaders with different failure/custom-path policies remain distinct; cross-gate before/after hashes and durable research-cache writes retain their integrity role. Existing candidate indexes and PubMed batch reuse are preserved. No speculative cache platform or module decomposition was added.

Legacy report restoration verifies existing schemas, counts and owned outputs; it does not invent cryptographic provenance for old reports. Completed-run state/manifests and20 untracked user files remain unchanged. PR406 passed exact-candidate CI42305303387 (all8shards and Merge readiness) and merged2247ee982 with an identical tree. Final fingerprint-selected nonpublishing regeneration, catalog/alert/signature checks and installed final-catalog acceptance remain open in the LEDGER.

Machine-readable source bindings, original benchmark flags and qualification limits: [repository_receipt.json](repository_receipt.json).

The first PR406 qualification run caught one failure: removing redundant reporting initialization also removed parent reference validation after a broken worker initializer. The existing regression reproduced locally and passes after restoring validation only on that failure path. All seven other shards passed. Corrected exact60eefc7a0 passed CI42305303387 and merged2247ee982. Fifty fail-closed/lifecycle checks plus the added cleanup-order/reset regression pass; final local564/24declared opt-ins and strictguard pass156.55s.

The existing synthetic100,000-input mechanics harness passed in576.70 seconds: all three stages retain100,000 records; selection, deterministic merge, failed-only retry, byte-exact rollback, interruption recovery and corrupt-artifact refusal pass. Clinical producers and coverage gates are simulated, so this is mechanics scaling evidence only.

Four sole-identity join regressions complete the test review follow-up:9file tests and12independent field-removal assertions pass. Production is unchanged. Fingerprint inspection shows changed code for all38datasets at Clean/Enrich/Score, with references/runtime unchanged; final selection must be repeated after the intended scientific source integrates.

Sean clarified closure scope: finish this maintenance candidate through targeted checks, exact-candidate CI and main integration; clinical work belongs to the Evidence session. PR407 independently contains the strict canary/test/documentation follow-up. Sean will run the subsequent pipeline test. The normal plan-only checkpoint covered38datasets/15449inputs per stage with0deletions; no corpus producer or new-catalog delivery is claimed.
