# Submission foundations (Batch 1) — corrected implementation and rollout

This replaces the original handoff's counter-only revision design and its
superseded test counts. The original implementation remains in git history.
Scope: submission foundations only. No scoring, clinical, provider, model-worker,
production migration, real-photo evaluation, or catalog release was run.

## Status and ownership

Both existing `claude/submission-foundations` branches are preserved.
They are stacked on the still-separate identity-hardening work:
pipeline `2db43114`, app `01b01a5`. Main and production were not changed
by this correction pass. Do not cherry-pick the foundations migration while
omitting its identity migration or paired consumers.

The local engineering correction is implemented. The full Batch 1 acceptance
gate is **not closed**: the real 20-development/40-holdout photo/gold population
has not been assembled and independently checked. No model has qualified.

Correction commits (local, not pushed):

- Pipeline: `469c17e4` — strict provenance/evaluator; `3e5ae75f` — current-view reviewer decisions.
- App: `b3abf0b` — paired draft schema; `940b245` — revision/approval/cleanup integration and tests.
- This handoff is the final documentation commit on the pipeline branch.

## Confirmed defects closed

| Audit area | Corrected contract and permanent verification |
|---|---|
| R1 retake retention | Cleanup ages the current attempt, not the original receipt. An abandoned retake removes only its newly added bytes and restores the prior finalized revision. Current lease token and revision fence completion. |
| R2 revision ownership | Explicit revision records, immutable full photo-record digest, membership, expected revision, request-key idempotency, explicit kept photos and reviewer-requested retakes during active review. Empty retakes cannot finalize; keeping all eight photos is refused because a new photo needs capacity. Legacy one-argument finalize cannot finalize revision 2. |
| R3 current evidence | One revision producer supplies signing, photo hashing, draft binding, match checks, reviewer-image selection, approval and release consumers. Review actions echo the revision/digest actually viewed; stale state fails closed. |
| R4–R5 benchmark accuracy | Microgram spelling equivalence never becomes grams. Failures and abstentions on readable labels remain in recall/exact-tuple denominators. Known conflicting identity, invented rows, unit mismatches and material magnitude errors cannot hide behind partial status. Missing mandatory measurements cannot qualify. |
| R6 one-to-one matching | Repeated names/headers remain occurrences with explicit ownership. Serving basis, forms, %DV and other ingredients are measured as well as amount/unit. |
| R7 frozen evaluation | Real product identities, actual brands, family separation, source/gold/configuration hashes, independent human attestations and configuration-content consumption are checked. Synthetic/development sets cannot qualify. |
| R8 draft provenance | Explicit human/model origin; original photo hashes separate from exact sent-input hashes; field sources reference real declared inputs. Paired Python/Deno fixtures reject malformed types and mismatched provenance. |
| R9 consumers/rollout | Current supported intake action; reviewer session derives database actor; recognized consent copy/purposes; every changed RPC caller updated; obsolete baseline harness mode rejected. Coordinated deployment remains mandatory, below. |

Independent review also exposed and reproduced these additional defects;
the correction includes regression tests for each:

- A pending Storage metadata transaction could commit after finalization.
  Upload authorization now holds a shared parent lock through that transaction;
  finalize/cleanup use the conflicting update lock. Final byte hashing still
  occurs at review; this is not a claim about atomicity of external blob writes.
- An expired cleanup worker could delete fresh bytes at a recycled address.
  Completed cleanup permanently reserves retired object addresses in a private,
  RLS-protected table. Reusing one is rejected for evidence and reviewer images.
  Private image bytes are still deleted; only the retired address is reserved.
- Reviewer images could be re-finalized with different bytes. Identical retries
  remain idempotent; changed bytes or stale revisions fail.
- Automatic URL refresh could attach an old edited payload to a newer revision.
  Changed revision or digest now clears draft/identity/image state, blocks decisions
  and requires deliberate re-selection/review. Late responses cannot replace a
  different selection. Unchanged evidence retains edits.
- Purged historical receipts could break the reviewer list. History remains
  readable without photos; mutations still require available current evidence.
- Malformed cleanup batches are validated in full, including token and address
  scope, before any deletion is requested.

The strongest proofs are executable SQL/JS tests, not source-text assertions.
The Docker harness loads the actual migration chain and a pre-migration legacy
receipt. It proves original hashes/metadata survive without inventing consent.

## Canonical interfaces

- `get_product_submission_evidence(submission_id)` returns current
  `evidence_revision`, opaque `manifest_sha256`, photo hash map and photo
  records. Consumers echo the digest; they do not reproduce PostgreSQL JSON
  serialization independently.
- `open_product_submission_evidence_revision(submission_id, expected_revision,
  request_key, keep_photo_ids, consent_version)` opens a new attempt.
  Same-key/same-input retries return the original revision, including delayed
  retries. Changed replays conflict. At most seven old photos can be retained.
- `add_product_submission_evidence(submission_id, expected_revision, photos)`
  and `finalize_product_submission(submission_id, expected_revision)` operate
  only on that attempt. First-upload legacy finalize defaults to revision 1.
- Record-match, image creation and human transitions require the view's
  `expected_evidence_revision` and `evidence_manifest_sha256`.
  The console and Edge functions forward these fields together.
- Draft recording compares inner and outer metadata/hash maps and current
  revision. Its authenticated database actor is the reviewer, not a supplied
  UUID. Service-role credentials cannot impersonate this human writer.
- Release export retains its existing nine-field importer contract.
  Export, image fetch and promotion additionally verify approved revision binding.
- Cleanup returns `claim_token` and `evidence_revision`. Completion accepts
  `p_claims` keyed by submission UUID; old cleanup clients are incompatible.
- `label_draft_v1` remains a draft, not a catalog/scoring payload. Human
  `manual_label_v1` approval and the existing pipeline remain authoritative.

## Verification for the correction pass

| Final check | Result |
|---|---|
| Pipeline default fast backstop | 13,744 passed, 167 skipped, zero failures (283.77 seconds) |
| Affected pipeline fast selection | 738 passed, 4 missing-artifact skips |
| Actual SQL migration/behavior/concurrency groups | 39 passed |
| Disposable local Supabase security-error advisor | No issues found |
| Deno reviewer/cleanup/verified-removal tests | 57 passed; both Edge entrypoints type-check |
| Flutter focused service/contract tests | 90 passed |
| Flutter analysis of five affected files | No issues found |
| Cross-language case/mutation fixtures | Both pairs byte-identical; diff checks clean |

The fast backstop's skips are not full-corpus acceptance evidence. No clinical
validation or model qualification is inferred from these counts. The independent
contract review passed its 114 focused Python cases plus seven adversarial probes;
integration review findings became the permanent SQL and console regressions above.

Commands are reproducible from the corresponding foundations worktrees:

```bash
# Pipeline: affected fast suite; never raw pytest.
bash scripts/test.sh fast -k 'benchmark or label_draft or submission or review or gtin'

# App: disposable local PostgreSQL including concurrency and security-error checks.
bash scripts/test_submission_identity.sh --advisors

# App: Edge type and behavior checks, including verified deletion.
deno check supabase/functions/review-product-submissions/index.ts \
  supabase/functions/cleanup-product-submissions/index.ts
deno test --allow-env --allow-read supabase/functions/review-product-submissions \
  supabase/functions/cleanup-product-submissions \
  supabase/functions/_shared/verified_storage_removal_test.ts

# App: focused service and compatibility tests.
flutter test --no-pub \
  test/safety_invariants/product_submission_pipeline_contract_test.dart \
  test/safety_invariants/product_submission_reviewer_access_test.dart \
  test/services/product_submission_service_test.dart \
  test/services/product_submission_status_query_contract_test.dart \
  test/services/product_submission_retry_contract_test.dart
```

The local advisor prints "Connecting to remote database" even when passed
the harness's explicit 127.0.0.1 disposable-container URL. No linked or live
Supabase project was used. Production permissions/advisors still need verification
during the eventual authorized rollout. No full corpus or full Flutter suite
was run in this correction loop.

## Coordinated deployment — not authorized or executed here

There is no zero-downtime claim or blanket backward-compatibility claim:
the migration intentionally closes old consent/reviewer/cleanup signatures.
A new phone cannot safely be paired with an old create RPC either.

1. Review and integrate Batch 0 identity plus both Batch 1 branches together.
   Preserve the single migration owner in the app repository. Re-fetch branches
   and re-run affected checks on the integrated tree.
2. Stage the exact migration chain and all paired clients in a non-production
   environment. Keep capture-v2/automatic extraction disabled; this batch creates
   no provider job or scheduling system. No real photos leave storage.
3. Verify a legacy receipt, new create/finalize, same-UUID retry, pending retake,
   stale draft/match/approval, reviewer image, terminal history and cleanup using
   synthetic staged evidence. The reviewer console must read the new digest
   and the phone must send the recognized consent version.
4. Obtain a separate explicit production approval. Because this is currently
   an operator-only build, choose a short coordinated maintenance window:
   close intake on the test phones, stop reviewer activity and pause cleanup
   scheduling, then wait for existing cleanup invocations to finish. Do not
   rely on deploy timing while old cleanup workers still execute.
5. Apply only the reviewed identity/foundations migrations in order after
   checking deployed history. Deploy `review-product-submissions` AND
   `cleanup-product-submissions`, install the paired local reviewer console,
   and rebuild/install the compatible phone application. Do not use blind
   `db push` to apply unrelated migrations.
6. Verify production function grants and exact migration versions, then run
   the controlled phone→review→approved-export round trip. Keep automatic
   extraction off and human approval mandatory. Resume cleanup/intake only
   after the new claim shape and version-bound decisions are confirmed.
7. If any pairing fails, keep intake/review/cleanup paused and fix forward.
   Never drop evidence history, reopen private RPC grants, or restore an old
   cleanup client to force compatibility.

## Next batches and honest remaining work

- [x] Correct R1–R3 and R9 engineering contracts and paired callers.
- [x] Correct R4–R8 schema/evaluator defects with RED→GREEN regressions.
- [x] Verify local SQL races, current-view console behavior, Edge and Flutter contracts.
- [x] Preserve branches and document the coordinated rollout boundary.
- [ ] Integrate both stacked repositories and perform authorized staged/live rollout.
- [ ] Assemble and independently verify the real 20/40 photo/gold benchmark.
- [ ] Complete capture/worker/provider batches and physical-device E2E.

1. Assemble and independently verify the real 60-product development/holdout
   population using `scripts/submission_review/HOLDOUT.md`. Photo permissions,
   gold labels and human timing cannot be invented by an agent. The freeze
   machinery is ready; the population is not.
2. Batch 2: improved capture/retake UI and calls to the new revision contract,
   wrong-slot assistance and physical-device verification. No new revision UI
   is claimed in this foundations pass.
3. Batch 3: provider adapters, cost-limited durable jobs/leases, original and
   actually-sent byte provenance, observe-only evaluation, measured provider
   selection, review-draft editing and safe human-verified batch decisions.
   Local/free options may compete; no provider or price promise is frozen.
4. Then staged rollout, device E2E and operational monitoring. No AI output
   can approve or publish a catalog product by itself.

Clinical rubric ratification, evidence curation and blinded scoring calibration
remain separate workstreams. This submission correction does not close them.
