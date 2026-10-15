# Release delay audit and WorkOS follow-up — October 15, 2026

## What this audit establishes

This records the release diagnosis and the subsequently authorized infrastructure corrections. No pipeline, publication, mobile build or authentication-setting change was performed. The staging-only WorkOS request was sent with Sean's explicit authorization. The latest local integration handoff supersedes yesterday's delivery-context hold: its fixes are integrated, while further approved scoring work and final release acceptance remain open. An old successful catalog is not evidence for today's source.

Owner check: `scripts/release_full.sh`, `scripts/rebuild_dashboard_snapshot.sh`, `scripts/preflight.py`, `scripts/pipeline_freshness.py`, `scripts/audits/run_verification_gate.py`; app `scripts/import_catalog_artifact.sh`, `scripts/validate_ios_release.sh`, and `lib/data/supabase/sync_service.dart`. Evidence: inspected calls, receipt schema, freshness inputs and app activation code. Will NOT create: another release command, scorer, readiness status, registry or receipt authority. Extend the existing owners if implementation is authorized.

## WorkOS follow-up

Sean authorized the staging-only request on October 15. It was sent successfully in the existing support thread after a temporary Gmail quota failure and a Sent check to avoid duplicates. Environment/client/message identifiers and the private support exchange are deliberately excluded from this public repository. Production personal access remains disabled. Setting activation and fresh-grant testing are pending; exact snapshot-consent authorization remains a separate unresolved requirement.

## Implemented release infrastructure (verification in progress)

- The existing verification runner owns one policy for four expensive read-only corpus checks: cleaner, enrichment, clinical and RDA/UL stamp parity. Cheap IQM checks rerun (measured0.068seconds) because binding reuse costs more. Snapshot and release now use identical command paths and share sealed exit/log-bound results. Changed source, references, enriched batches/manifests, runtime packages, environment or command invalidate reuse; expired, interrupted, failed or damaged receipts cannot pass. Inputs must remain unchanged throughout execution. Receipt writers serialize per gate.
- Every strict gate gets a preserved log, actual exit status and timing. Child output streams immediately rather than waiting for a large buffer. Artifact/live/mutating gates run every time; publication keeps its existing idempotent state checks. This is not a cache of uploads or a new release runner.
- The app importer now has a read-only compatibility mode using the SAME accepted-schema helpers as actual import. Producer versions come from the actual Python constants without executing the producer. Full `--pipeline-only` runs check this before aggregate preparation; targeted runs and explicit `--skip-flutter` retain standalone operation. Final candidate integrity/import gates remain mandatory.
- Publishing preflight checks the importer's tool availability and performs actual read-only Supabase manifest/bucket access before corpus/publication work. It proves read access, not future write success. The final upload owner still checks capacity and publication state.
- No stage/scorer/reference input owner was changed. The edited release files do not belong to any Clean/Enrich/Score code closure, so this batch adds no stage regeneration requirement. Existing scoring changes still require their own final fingerprint decision.

Initial 133 pipeline harness/owner tests passed. The app importer suite passed 11 tests with one explicitly private-candidate opt-in skipped; no bundled assets were changed. Real producer compatibility and Supabase read-only preflight passed. Independent review found and then cleared four relative/absolute command mismatches; a real-call parity regression now covers them. The actual cleaner corpus check passed: first verified run72.913seconds, unchanged retry6.025seconds (receipt scripts/reports/release-resume-20261015/real-gate-timing.json). This does not establish a whole-release duration. Final CI status is recorded at handoff, not inferred from focused checks.

## Why release keeps becoming another development session

The work currently mixes unfinished scoring changes, corpus regeneration, catalog construction, live clinical checks, cloud publication, app asset import and phone validation. Source fixes discovered after the corpus invalidate outputs. Several source/corpus checks repeat across the snapshot and release wrappers. Some predictable consumer incompatibilities have historically surfaced late. These are sequencing and orchestration issues, not a reason to remove safety checks.

The preserved preparation report records source tests at 712.8 seconds, raw canaries at 17.384 seconds, and one live check at 143.8 seconds. It does not establish an eight-hour post-pipeline runtime. `release_full.sh::run_strict_gate` logs start/pass messages but does not produce per-gate timing/resume receipts. We need measured critical-path timing before promising a release-duration target.

## Prioritized correction list

| Priority | Problem and observed evidence | Correction / acceptance criterion |
|---|---|---|
| P0 | Current source work is still open. The integration handoff explicitly leaves production missing-data/completion, bound-aware dietary consumers, purpose/exposure, remaining approved pillar/config changes and probiotic copy unfinished; D28 EGCG/polyphenol policy is undecided. | Close one bounded source batch first. Separate the unresolved policy decision from implementation. Publish an explicit blocker list; no corpus go-ahead while known output-changing work remains. |
| P0 | Source changes after a corpus make its artifacts stale. Previous delivery-context defects illustrate why delta-only review was insufficient; the latest handoff records their integrated repair. | Validate the shared source interpretation with affected labels AND retained-credit controls before the final corpus. Freeze the candidate's real input fingerprints; a later change invalidates only evidence it actually affects. |
| P0 | Historical interaction-schema incompatibility reached app consumption late. Current importer supports schema 4 and release already has a dry-run import gate. | Preserve that fix. Add a cheap pre-corpus producer/consumer compatibility check using existing contract owners, then retain the actual new-artifact import check before upload. Don't invent a second schema allowlist. |
| P1 | `--preflight-only` checks clean release bases, manufacturer freshness and import-script availability, then exits. It does not exercise all downstream publishing prerequisites. | Fail early on deterministically checkable runtime, credentials/access, importer/schema compatibility, storage/disk and phone build/signing prerequisites when a phone build is requested. Avoid uploads or device mutations in preflight. Final state checks still run immediately before publication. |
| P1 | Snapshot and release both call matrix, IQM audit, cleaner, enrichment and clinical checks. Scoring snapshot has a limited already-ran optimization, not general verified reuse. | Reuse one successful result only when command, runtime, source and actual corpus/candidate hashes match. Extend existing preparation/verification receipt owners; never skip merely because a command ran previously. Mutation or failed/incomplete evidence invalidates reuse. |
| P1 | Release gates are sequential shell calls with no durable per-step completion/timing ledger. Retrying can repeat successful earlier work. | Add timings and resumability through existing receipt machinery. An intentional failed-final-step harness must resume the same candidate without redoing unchanged work or repeating publication. Record failed attempts honestly. |
| P1 | Every stage hashes the same broad reference-data set, including nearly every top-level `scripts/data/*.json`. | Audit real stage dependencies, then narrow reference fingerprints only with proven read coverage and invalidation tests. A Score-only input change should not force Clean if Clean demonstrably cannot read it. Preserve conservative invalidation until proven. Never restamp old artifacts. |
| P1 | Live identity/content checks run during preparation and again late in release. API metadata retrieval already uses a shared cache. | Reuse verified source-content results within explicit freshness rules; changed identifiers/claims rerun. Do not build another cache or disable network verification globally. Keep a final freshness check for time-sensitive FDA/revocation state. |
| P1 | A normal release may fetch approved submissions and introduce fresh processing after the founder's completed corpus; `--prepared-inputs` exists for a fixed prepared set. | Make the chosen input set explicit in the readiness plan. Prepare approved intake before the final corpus and publish the same validated set. Newly approved labels wait for the next candidate unless deliberately included. Preserve stale-manifest rejection. |
| P1 | Catalog build, cloud upload, app bundle and phone executable are being discussed as one release. The app already has OTA catalog download and compatibility/integrity activation gates. | Document which updates need catalog publication versus a new installed app. Compatible catalog-only changes should use the existing OTA path and be tested on the phone. Schema/reader/UI/code changes still need a new compatible app build. |
| P2 | Release auto-detection includes mtime comparisons even though source fingerprints and artifact checksums exist. | Use existing content identities for reuse decisions where possible; touching a file should not force identical expensive assembly. Preserve cross-repo/freshness gates. |
| P2 | Images and version cleanup remain inside the release wrapper; full orphan reconciliation has already been moved out. | Measure before changing. Keep only correctness-critical publication dependencies on the phone-update path. Move optional maintenance only after proving no image/pin/retention requirement is lost. Do not claim the existing orphan sweep is still causing this delay. |
| P2 | Multiple agent lanes can alter shared source while a candidate is being validated. | One integrator owns the final source checkpoint. Integrate all planned output changes first, then one necessary corpus and one candidate acceptance. Independent unrelated work must not mutate the frozen candidate. |

## Checks to keep

Keep actual source/data freshness, label identity and serving amounts, clinical applicability, warning retention, SQLite integrity, complete blob/core parity, consumer schema compatibility, checksums, minimum app version, and explicit publication authorization. Ordinary score/tier changes are already report-only in catalog comparison; do not add per-product approval queues. Removing checks would reduce detection without repairing these causes.

## Intended simple workflow after these corrections

1. Finish and verify the bounded source batch; report all unresolved blockers together.
2. Run cheap readiness checks and identify the earliest genuinely stale stage.
3. Sean runs the necessary pipeline once.
4. Build one immutable candidate; validate it once and reuse matching receipts.
5. Publish that same candidate, then verify remote version and phone activation.
6. Build/install a new app only when executable or compatibility changes require it.

The current catalog release remains held for the independent scoring completion/integration and final corpus acceptance. Do not run the pipeline yet. This infrastructure batch does not resolve scoring-policy decisions or establish phone acceptance. Measure timings before promising a whole-release duration; retain time-sensitive live checks and final candidate validation.
