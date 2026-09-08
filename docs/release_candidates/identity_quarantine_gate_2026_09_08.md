# Rebuild integration corrections — 2026-09-08

The operator completed all 37 brand pipelines and refreshed Product_Submissions.
The snapshot then stopped at 297 unresolved identity rows in 231 products.
Nothing was published. The earlier scoring audit missed integration seams;
its successful scoring replay was not proof that operational enrichment and
snapshot assembly would pass end to end.

## Corrections

1. **Prove quarantine against the actual candidate.** The export contract already
   defines unresolved-identity exclusions, but the pre-build identity/scoring audits
   prevented the builder from recording them. These audits now run after
   candidate construction and before promotion. The release entrypoint also
   checks identity containment when freshness shortcuts reuse a catalog.
   A common release validator verifies the checksum, counts, exclusion receipts,
   and absence from SQLite, the detail index and physical detail blobs.
   Source findings remain failures in source-only mode; no identity is invented.
2. **Keep structural failures blocking.** Only non-scoreable identity conflicts
   with actual identity-quarantine receipts can be contained. The scoring audit
   additionally requires no public numeric score and an unavailable status.
   Strict-contract findings must be a nonempty, identity-only list with explicit
   `passed=false`. Missing/mixed/malformed contracts, forbidden fallbacks,
   missing dose records, shadow enforcement and legacy dose inference still fail.
   Independent review found the initial overly broad strict-failure exception;
   six regressions closed it. Three adjacent dose regressions were added too.
3. **Produce canonical dosage form before certification matching.** Full
   enrichment resolved certifications before producing the form information
   required by the resolver. Replay on already enriched products had that
   information, so audit replay and operational enrichment differed. The
   existing canonical form producer now runs first, once. Certification receives
   original label fields plus that form, never generated enrichment prose.
   Powder, capsule and unknown-form full-enrichment controls pin the boundary.

## Measured impact before operational refresh

Local evidence: `reports/identity_quarantine_2026_09_08/` (not bundled).
`corpus_after_cert_order.json` recomputed 15,415 products, fully re-enriched
330 canaries/affected IDs, and finished with zero errors in 351.5 seconds.

- 210 certification-record changes across 13 brands; 166 numeric changes and
  44 metadata-only changes. Routes and score statuses are unchanged.
- 20 quality verdicts change POOR→SAFE. No hard-safety verdict is downgraded.
- 164 numeric changes affect verification only. Two omega products also regain
  formulation/transparency credit under existing certification-dependent rules.
- No reference registry, clinical identity, dose benchmark, conversion factor,
  safety policy, pillar weight or calibration rule changed.
- 114 focused gate tests and 255 certification/serving tests pass. Independent
  review, including the two exception-tightening follow-ups, has no remaining
  important findings.

This is a measured impact report, not a claim of publication or clinical-policy
completion. Final operational verification is recorded below when completed.

## Operational refresh

The 13 affected brands completed the canonical `enrich,score` runner in
pipeline-only mode: 13 passed, zero failed. The other 24 brand outputs and the
completed cleaner work were reused; no 37-brand rerun was required.
Runner summary: `scripts/products/reports/batch_run_summary_20260908_124224.txt`.

`refreshed_verification.json` proves all 425 audited changed/canary products
match their expected score, route, pillars, verdict, confidence and consumer
reasons after the normal operational refresh. All 15,415 stage products remain
accounted for: 15,097 scored, 264 not scored, 54 safety suppressed. These are
stage counts, not final catalog eligibility counts. All six source-unit holds
remain unscored. Submitted products retain Seed 81.2, Ritual 73.0 and Youtheory
77.4 before whole-number export projection.

## Reviewed snapshot refresh

The next snapshot attempt reached the score fixtures and correctly stopped:
12 fixtures still represented August behavior. All twelve current results
exactly match the previously approved `corpus_dose_closure_verified.json`
(SHA-256 `97c930705071cceced31d538aa5b4eb758f3fef300cffebe67043d4d08b7f832`).
A new full-enrichment replay of these twelve completes with zero changes and
zero errors; no fixture was updated merely to accept a new output.

Only those twelve fixtures are refreshed; `_manifest.json` records every score
delta and its owning correction. Nine changes affect evidence only, one is the
required Nickel/Tin identity quarantine, one is probiotic disclosure credit,
and one combines evidence applicability with removal of a Kids certification
from a Baby product. The certificate-order fix introduces no new drift in
these twelve. This closes an omitted baseline-update step from the earlier
scoring integration; it does not change calibration.

Independent review verified fixture equality, the prior report hash, all 18
relevant input hashes, audit-runner hashes and the older live-blob pillar
deltas. The snapshot suite passes 32/32. The broad fast suite, after operational
refresh and fixture review, passes **13,725 tests, zero failures, 42 existing
skips** in 341.58 seconds (`fast.log`, `fast.xml`). Historical fixture/path skips
are not presented as successful live-corpus tests.

## Consumer assembly order and failure diagnostics

The candidate build then exposed 227 product export errors. A direct replay of
12012 reproduced `row_ledger UNRESOLVED_SCORE_ACTIVE`: the builder constructed a
consumer blob before checking the source contract that already excluded this
product. Consumer-ledger completeness is still required for shipped products;
excluded QA records must not be assembled as app records first.

The builder now validates and records source-contract issues before consumer
assembly. Eligible products still pass the unchanged ledger and safety-parity
validators. Contract issue classification is per issue, not a substring search
over their joined text: one `review_queue` reason cannot hide an unrelated
missing required field. The per-product error bucket is reset each iteration.
The removed scored-artifact rewrite/rebuild branch was unreachable under the
existing safety projection's assertion-only contract; no second scorer is added.

Four new regressions failed before the fix and pass afterward. The builder and
snapshot suites pass 213 tests; release-artifact/scoring-source/release-entry
focused suites pass another 95. Snapshot output no longer truncates away the
individual failure details. No additional brand refresh is needed for these
export-only changes. Final candidate results follow once all gates complete.

Independent review found no important issues in the order/classification fix.
The fresh manifest-owned contract preflight checks all 15,415 pairs: 15,103
eligible, 312 exclusions and zero hard contract failures. Replaying just the
excluded products reproduces exactly 227 old consumer-ledger crashes, all
`UNRESOLVED_SCORE_ACTIVE` and no other exception type or reason. This validates
the root cause across the complete affected population, not only fixture 12012.

## Final candidate assembly and exact reconciliation

The candidate-only snapshot completes successfully, including the identity,
scoring-readiness, blob-completeness, both export-contract and freshness gates.
Its version is `2026.09.08.175118`, schema `2.4.0`:

- 15,415 input products reconcile to **15,103 live candidates + 312 quarantines**.
- Live: 15,093 scored and 10 safety suppressed. Verdicts: 11,600 SAFE,
  1,362 CAUTION, 2,131 POOR and 10 BLOCKED.
- Quarantined: 264 already not scored, 44 safety-suppressed products with
  unresolved identity, and four scored products with unresolved source rows.
  The 297 identity conflicts across 231 products are contained in this ledger.
  No record receives a guessed identity, dose or score to make these gates pass.
- Exact source/core score, status, route, verdict and confidence comparison:
  zero mismatches. All six pillar values agree across source, core and blob.
  All 15,103 blob hashes match their index. Every live scored product has
  mapping coverage exactly one; every removed product has a quarantine receipt.
- All six source-unit holds remain absent. The three submissions are present:
  Seed 81.2 → display 81, Ritual 73.0 → 73, Youtheory 77.4 → 77.
- Manifest-owned files equal on-disk export inputs exactly: 58 enriched and
  58 scored files; no stray or missing files were consumed.

Candidate core SHA-256:
`5f4dc14d3d3aa9cc960d1c4468099e4a99dbf34e81be3d14c0c55329800f07a6`.
Full machine receipt: `reports/identity_quarantine_2026_09_08/candidate_verification.json`.
Candidate root: `reports/identity_quarantine_2026_09_08/candidate/`.

Compared with the unchanged **local** Sep-03 catalog (15,337 products), this
candidate adds Seed and excludes 235 previously present products, all with
quarantine receipts. Among 15,102 shared products, 3,442 rounded scores,
189 verdicts and three routes differ. That comparison includes all earlier
September scoring corrections, not just today's 210 certification changes.
It is not a measurement of the current remote Supabase catalog.

Both original `scripts/dist` hashes remain unchanged; there was no cloud upload,
Flutter import or device install. Final release/full test results and merge
receipt will be recorded after their sequential backstops complete.

## Release backstop

The candidate-targeted release profile completes: **122 passed, zero failures,
one skip** in 1,199.40 seconds, followed by passing artifact, evidence-reachability
and live identifier/citation gates. Reconstructed detail blobs equal the
candidate's complete exported records, not just their pillar values.
Evidence reachability reports zero stale native matches, unlinked recomputed
matches or recomputation errors across all 15,415 source products.
The backed-studies gate verifies 462 citations with zero title mismatches,
title drift or missing IDs; two heuristic suspects have existing reviewed
dispositions, not new waivers.

The skip is `test_live_interaction_db_has_no_orphan_canonicals`: this catalog-only
candidate does not contain `interaction_db.sqlite`. It is not an interaction
parity pass. The normal release must build and gate the interaction database,
then perform Flutter preflight/import and any separately approved publication.

The initial two-worker full backstop caused heavy swapping on this 16 GB host
and was stopped. Its incomplete results are not counted. The unfiltered full
backstop is rerun with `PG_TEST_WORKERS=1` and the same candidate root; no brand
pipeline, scoring policy or test selection was changed for this adjustment.

The unfiltered full run completed: **16,223 passed, 19 failed, 72 skipped** in
5,159.86 seconds (`full_serial_candidate.log`, `.xml`). This is not a green
full-suite result. Each failure was reproduced or independently reviewed;
corrective verification is recorded below. The completed
candidate-targeted release profile above remains separate evidence.

## Full-backstop failure review

All 19 failures were reproduced or traced individually, not waived. The first
three failed again in isolation (3 failed / 1,641 passed), ruling out parallel
test contamination. They required test-only repairs:

- Direct `label_active_projection` rows retain derivation provenance without
  becoming synthetic product totals. Identity continuity now tests both derived
  kinds and adds a source-row projection invariant.
- The exact EpiCor alias belongs to the already reviewed branded preparation;
  the older test incorrectly expected generic yeast fermentate. The adjacent
  generic control remains unchanged.
- The PureWay-C fixture omitted its label-row reference. Adding the proper
  source path preserves its form and restores existing evidence matching. The
  positive assertion is retained, plus a missing-link negative control; the
  production exact-source join is not relaxed.

Those complete three files now pass **1,646 tests**, zero failures, in 86.62 s.
An independent reviewer traced the remaining sixteen canary failures to the
already approved scoring/identity/certification corrections. All fourteen real
product summaries match the earlier approved corpus receipt, including Hair
Sweet Hair in its `changes` list. No production score, reference data, policy,
weight or candidate artifact was changed during this re-lock.

The refreshed canaries distinguish raw module scores from final six-pillar
consumer totals. Aggregate probiotic CFU is never split into invented individual
doses; exact disclosure-floor reasons and guarantee modifiers are pinned.
Seed adds a genuinely reviewed high-band case (raw 78.3, final 81.2) using native
formula AFU, preserving the high-band coverage requirement. Identity-conflicted
Ripped Rooster remains NOT_SCORED even though its separate safety policy is
CAUTION. Confidence drivers and the exact Garden of Life NSF SKU/GMP mechanism
are pinned. Synthetic SAFE/POOR boundary fixtures distinguish disclosed rows
from an aggregate-only product with certification; they do not claim clinical
adequacy from those synthetic records.

Durable independent evidence:
`docs/release_candidates/identity_quarantine_canary_review_2026_09_08.md`.
The final review found no remaining important issues in the test diff.
The five corrected canary files pass **102 tests, zero failures, three existing
historical artifact/path skips** in 187.56 seconds. Together with the 1,646-test
run above, every affected file has been rerun successfully. These are separate
runs with overlap in test coverage, not counts to add to the original full run.
The original 86-minute full run remains recorded with its 19 failures, not
silently relabeled as passing; no second unfiltered full run is claimed.
Final broad fast tier passes **13,729 tests, zero failures, 42 existing skips**
in 539.33 seconds with one worker (`final_fast.log`, `.xml`).
The checked production hashes and candidate core hash remain unchanged from
the successful release profile; the last corrections affect tests only.
Shell syntax and staged/unstaged whitespace checks pass. The companion JSON
binds the production files, candidate and corrective test receipts by SHA-256.

## Implementation receipt

The reviewed changes are split from base `2976695c` into four commits:

- `dcce045d`: canonical dosage form before certification matching.
- `3de5d7b9`: candidate-proven identity quarantine and consumer assembly order.
- `bedce089`: twelve independently reviewed scoring snapshots.
- `85619cdb`: the eight corrected full-backstop test files and mechanism locks.

The documentation commit records this evidence separately. This receipt does
not assert that a Git push publishes a catalog; production publication remains
the operator's next action. Flutter required no change in this correction pass.

## Operational boundary and next step

After corrective verification and main merge are confirmed, run only the normal
release entrypoint from the main checkout:

```bash
cd /Users/seancheick/Downloads/dsld_clean
bash scripts/release_full.sh
```

The 37-brand raw rebuild is already complete, and the 13 affected brands have
already been refreshed. Do not repeat them for these export-only fixes. The
release command owns any required snapshot/staging, interaction database,
images, Supabase publication and Flutter import; it is not a dry run. The local
candidate above is review evidence, not an already published catalog. A later
release may receive a new version stamp and corresponding hashes.

After that release, verify its final count/exclusion receipts and the remote
manifest against its actual outgoing artifact, confirm the Flutter bundle uses
the same version, and rebuild the phone. Seed, Ritual and Youtheory are the
three focused display canaries. Do not infer remote parity from the local
candidate report alone.

Still separate: remediation of 312 quarantined products (including six
source-unit holds), the conservative generic dose-owner policy decision,
preparation-specific cranberry/PAC policy and CranRx label applicability,
blinded reviewer benchmarking and any later weight calibration. No safety
policy or clinical curation is implicitly approved by a successful test suite.
