# Submission foundations (Batch 1) — handoff for Codex review

Date: 2026-09-08. Branches: `claude/submission-foundations` in both repos,
based on `codex/submission-identity-hardening` (pipeline `2db43114`, app
`01b01a5`). Nothing is merged, pushed, deployed, or run against a remote
database. Codex reviews before any merge; merge/push only when authorized.

## Commits

Pipeline (`/Users/seancheick/Downloads/dsld_clean`, worktree `worktrees/submission-foundations`):

| Commit | Content |
|---|---|
| `14856bc2` | `label_draft_v1` contract: `scripts/submission_review/extraction/envelope.py`, shared fixture `scripts/submission_review/fixtures/label_draft_v1_cases.json` (32 cases, 6 valid, sha256 `6e7e5499…d924`), `scripts/tests/test_label_draft_v1_schema_fixture.py` |
| `aacc3322` | Frozen holdout protocol `scripts/submission_review/HOLDOUT.md`; scorer `scripts/submission_review/extraction/benchmark.py`; `scripts/tests/test_submission_extraction_benchmark.py` |

App (`/Users/seancheick/PharmaGuide ai`, worktree `.worktrees/submission-foundations`):

| Commit | Content |
|---|---|
| `5949521` | Deno mirror `validateLabelDraftV1` + identical fixture + two tests in `schema_test.ts` |
| `19f33c1` | Migration `20260909013000_submission_foundations_consent_revisions_extraction.sql`; `supabase/tests/submission_identity/foundations.sql`; existing SQL cases now attest a consent version; harness runner applies the migration |
| `6bcd531` | Edge `record_extraction` via the reviewer's client with draft validation, usage and revision; Dart `productSubmissionConsentVersion` sent as `p_consent_version`; safety-invariant and service tests |

## What changed (contract level)

1. **Consent recorded by the server.** `create_product_submission` gained a
   trailing `p_consent_version text DEFAULT NULL` and now requires it
   (`^[A-Za-z0-9._-]{1,80}$`, else `22023 consent version required`). It is
   written once with `consented_at = now()`; an idempotent replay with a
   different version keeps the first. The old 7-argument signature is
   dropped so a legacy client cannot bypass consent through an overload.
   Pinned app value: `pharmaguide.submission_consent.2026-08-25.v1`.
2. **Evidence revisions, append-only.** `product_submissions.evidence_revision`
   (default 1), `evidence_revision_opened_at`, `evidence_ready_at`;
   `product_submission_photos.revision` (default 1, so existing evidence is
   revision 1 with unchanged bytes and paths). Owner RPCs:
   `open_product_submission_evidence_revision(uuid)` (ready + submitted/under_review
   → pending, revision + 1; replay returns the open revision; anything else
   `55000 open ready submission required`) and
   `add_product_submission_evidence(uuid, jsonb)` (pending and revision ≥ 2;
   sequence continues after all earlier photos; per-revision manifest replay
   rules; up to 12 photos in total; identical bytes rejected by the existing
   sha256 uniqueness). `finalize_product_submission` finalizes the new
   revision, keeps the first `submitted_at`, stamps `evidence_ready_at`.
   Photos are never deleted or rewritten.
3. **A pending revision stays open.** The duplicate-open trigger and partial
   unique index now treat `upload_state = 'ready' OR evidence_revision > 1`
   as open; `get_product_submission_intake` returns
   `resume_evidence_revision` (with `evidence_revision`) for the owner's
   pending retake and keeps Codex's minimal-receipt shape for every other
   action. Approval and draft recording require `upload_state = 'ready'`, so
   an old approval check cannot authorize a revision that is mid-upload.
4. **One authorized human draft writer.** The 10-argument
   `record_product_submission_extraction(…, p_recorded_by uuid, …)` is dropped.
   The 11-argument replacement derives the recorder from `auth.uid()` ∈
   `product_submission_reviewers` (`42501 reviewer access required`), accepts
   `p_usage jsonb` (object only) and `p_evidence_revision` (must equal the
   current revision, else `22023 extraction evidence revision is stale`),
   binds the hash map to **all** photos of the submission (so new evidence
   invalidates old drafts), stores `actor_kind = 'reviewer'`, and is revoked
   from `PUBLIC, anon, service_role`, granted to `authenticated`. The edge
   action `record_extraction` validates `schema_version = label_draft_v1`
   and the draft body, then calls the RPC through `userClient`.
5. **`label_draft_v1`.** Partial, provenance-bound draft: every field is
   `{value, status ∈ read|partial|unreadable|not_present, confidence,
   sources[{photo_id, supporting_text, region?}]}` and every `photo_id` must
   be in `evidence_snapshot`; amounts keep `unit_text` verbatim; blend
   ownership is `parent_index` to an earlier blend header; typed
   discrepancies; explicit `abstained`; forbidden keys (`canonical_id`,
   `cui`, `rxcui`, `unii`, `pmid`, `score`, `verdict`, `benefit`, …) are
   rejected anywhere in the object. The validator returns the value
   unchanged (no normalisation) and the same fixture pins both validators.
6. **Holdout protocol frozen** (`HOLDOUT.md`): 20 development / 40 held-out
   products grouped by brand/family, required case families, private
   storage layout under git-ignored `reports/submission_holdout/`, gold
   format with two independent human checkers, the gates from Codex's B1
   list, the one-evaluation rule with an append-only ledger, and the
   OCR/retake cutoffs (proposals to ratify: ≤ 2% unnecessary retakes,
   ≥ 95% per-reason precision, ≥ 90% wrong-slot recall).

## Tests run (all local, no remote)

```bash
# app worktree
bash scripts/test_submission_identity.sh        # 29 cases PASS, "Submission identity SQL tests passed."
deno test --allow-env --allow-read .            # in supabase/functions/review-product-submissions: 15 passed
flutter test test/safety_invariants/product_submission_pipeline_contract_test.dart \
  test/safety_invariants/product_submission_reviewer_access_test.dart \
  test/services/product_submission_service_test.dart   # 66 passed
flutter analyze <touched files>                 # No issues found
# pipeline worktree
bash scripts/test.sh fast -k "benchmark or label_draft or submission or review or gtin"  # 631 passed, 4 skipped
```

The Flutter run needed the git-ignored `assets/db/*` copied from the main
checkout into the worktree (asset bundle build); those files are not
committed.

## Deployment coupling (decide before `supabase db push`)

- **Old app builds fail closed after this migration.** Installed versions
  that do not send `p_consent_version` receive `22023 consent version
  required` on every create. That is the intended policy (no retroactive
  consent), but it means the app release carrying `6bcd531` must reach users
  before, or together with, the migration, and the Dart error surface for
  that code is the generic submission failure today.
- **Migration and edge function deploy together.** The deployed
  `record_extraction` still calls the dropped 10-argument RPC; deploying
  one without the other breaks draft recording (human path only; no worker
  exists yet).
- Legacy receipts with `consent_version IS NULL` are untouched. Nothing
  consumes consent yet; the Batch 3 enqueue trigger must treat null as
  "manual review only" (recorded here so it is not forgotten).

## Limitations and open items for review

1. **Revision model is a counter, not a revision table.** Codex's B1.3 asked
   for append-only revision records with a frozen manifest digest, expected
   revision and idempotency key. This branch implements the approved plan's
   additive columns instead: photos carry `revision`, the submission carries
   the active revision, `FOR UPDATE` on the owner row serialises concurrent
   opens (second caller replays the open revision rather than creating a
   second one), and the manifest replay rules apply per revision. There is no
   `p_expected_revision` parameter and no per-revision digest column. If
   Codex wants the stricter shape, it is an additive follow-up before Batch 2
   depends on the RPCs.
2. **Consumers were not re-pointed through a manifest function** (B1.4).
   Photo RLS, signing, match checks, product-image selection, export and
   cleanup read the photo table directly and therefore see every revision's
   photos as one set; approval requires the product image to be one of those
   photos. Nothing filters by revision yet. Review whether export/import
   should record the revision number (the exporter is unchanged).
3. **Consent purposes are not itemised** (B1.1 asked for version/purposes).
   Only the version string is stored; purposes are implied by the pinned
   copy for that version.
4. **No app UI or client call for revisions yet.** The RPCs are exercised
   only by the SQL harness; Batch 2 adds the capture UI and the Dart calls.
5. **The holdout set does not exist yet.** The protocol, storage layout,
   gold format and scorer are frozen; assembling 60 products with photos and
   two-checker gold labels is physical work for the owner. `benchmark.py`
   refuses unfrozen manifests, single-checker gold, model-named checkers and
   families leaking across splits.
6. `scripts/test_submission_identity.sh --baseline` (skips Codex's and this
   migration) is no longer coherent with the SQL cases, which now call
   functions from both migrations. It already referenced intake before this
   branch; leave or delete as Codex prefers.
7. The intake RPC keeps Codex's five-field receipt; `evidence_revision` is
   added only on the `resume_evidence_revision` action so the "minimal
   receipt" case still holds.
