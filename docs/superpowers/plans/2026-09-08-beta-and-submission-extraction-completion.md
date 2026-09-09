# PharmaGuide Beta and Submission-Extraction Completion — Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or superpowers:subagent-driven-development for an assigned batch; bounded independent review is required before integration. Checkboxes track work, not intentions. This is the consolidated plan for operator review, not permission to deploy, spend money, send photos to providers, or approve submissions.

**Goal:** Close submission identity/retry gaps, qualify an inexpensive human-reviewed label extractor, and retain an explicit ledger for clinical validation and the remaining original-plan work.

**Architecture:** One product-identity contract, one approved-label contract, one existing Clean → Enrich → Score pipeline, and one human approval path. An extraction-only worker prepares a provenance-bound draft automatically for the existing reviewer console; it never supplies scores, clinical judgments, ingredient identifiers, or approval authority. Beta hardening, extraction, clinical validation, and payload maintenance have independent completion gates.

**Tech Stack:** Existing Flutter/Riverpod/Drift app, Supabase Postgres and Deno review function, Python 3.13 reviewer console/worker, existing manual_label_v1 validators and shared fixtures, Ollama local inference or one qualifying paid API. One small durable preparation-job queue, not a new message-broker platform. Pilot defaults to local execution; an always-on host needs a separate operating decision.

**Status:** SCOPED IDENTITY CODE IMPLEMENTED; DEPLOYMENT PENDING, 2026-09-08. The operator approved starting submission identity and duplicate handling. Paired `codex/submission-identity-hardening` branches implement A1's bounded intake behavior and A2's canonical receipt/current-source guards; deployment and physical-device closure are still pending. Pipeline fast: 13,626 passed / 167 skipped; local SQL: 24 groups passed; Flutter analysis clean, full tests 3,401 passed / one pre-existing bundled-vinpocetine gate failure reproduced on unchanged main. See `docs/release_candidates/submission_identity_hardening_2026_09_08.md` on the pipeline branch for exact implementation evidence and remaining boundaries. No production mutation, extraction, clinical, or scoring work was performed in this batch. The remaining plan is still a draft; numeric pilot targets below remain proposed engineering acceptance criteria, not established clinical standards or measured performance.

**Explicit amendment after the operator's follow-up:** The August spec limited extraction to reviewer-triggered runs. The requested target is now automatic preparation, photo-slot mistake tolerance, simpler capture, historical/discontinued products, and optional batch approval of already-reviewed items. This draft replaces that trigger/UI restriction only after approval; it preserves private evidence, explicit processor consent, extraction-only worker authority, missing-product-only pilot scope, and human approval. Do not treat an automated worker as a human reviewer. The operator accepts a low-volume local command/skill initially and eventual cloud automation. Local inference cannot run on a sleeping/closed host; local-only mode durably queues jobs until the worker returns. Continuous processing while the Mac is off requires an actually provisioned remote worker, not a different prompt or skill.

## 1. Verified starting point and reconciliation of older messages

- Pipeline main `8f9c8c74`; app main `53518fa5`; both fetched and synchronized at inspection.
- Release `2026.09.08.205846`, schema 2.4.0, scoring 4.4.0: 15,103 catalog products, comprising 15,093 scored and ten safety-suppressed records; 312 source exclusions remain outside the catalog.
- The operator reports using the latest phone build. Do not ask for another whole-corpus rebuild simply to start this work.
- The previously failing structural-total/owned-active case is corrected. The recorded baseline source-ownership plus botanical form/reachability check passed: 36 tests in 1.94 seconds; this is prior verification, not a new test run for this document.
- The bounded botanical correction pass, independent reviews, full-corpus comparisons, operational identity re-clean, certification-order repair, and export integration corrections are recorded in `docs/release_candidates/identity_quarantine_gate_2026_09_08.md` and `scripts/audits/probiotic_rubric_review_2026_09_04/CONTINUATION_RETURN_2026_09_05.md`. Do not reinstate the superseded 1-failed/3-passed status or restore deliberately excluded botanical evidence.
- The old 180 additional holds are an earlier cohort, not an extra count to add to today's 312. Reconcile by product and reason, not by subtracting incompatible totals.
- Clinical curation and independent validation are NOT closed: 202 backed-study registry entries; 16 new native probiotic contexts on eight of 49 identities all marked `source_verified_pending_clinical_review`; 195 remaining Excellent-form evidence records. Counts are dated, not invariants.
- Probiotic CFU/count rubric alternatives were measured, not ratified or deployed as a replacement rubric. Global config SHA remains `18b7ff59dc1c4baa4e89562492ffa9338491bb618da42e4044900f805beae9e1`.
- Submission Batches 1/2 have a recorded physical-device closure. Batch 3's holdout and extraction package do not exist. The deployed `record_extraction` action stores a supplied draft; it does not produce one.

### This evening's submission test

Live read-only inspection found one ready/submitted attempt at 2026-09-08 22:33 UTC (18:33 EDT), barcode `0850051911561` / canonical `00850051911561`. Four photos are registered: front, combined facts/ingredients, directions/warnings, barcode. It has no match check, extraction, approval, or resubmission link yet. Its content has not been visually adjudicated in this audit.

The earlier rejected attempts are stored under `0810071800573` / canonical `00810071800573`, including one `photo_quality` rejection and one `product_identity_mismatch` rejection. Therefore the newest attempt is NOT a same-GTIN dedupe test. Do not repair that historical mismatch by guessing which submission it belongs to. Preserve the evidence and review history.

Observed starting server behavior, BEFORE deploying the new local identity migration:

| Situation | Observed implementation |
|---|---|
| Same owner/kind/GTIN already ready and open | Trigger plus unique index prevent a second ready/open attempt; width-equivalent GTINs compare equally. |
| Prior attempt rejected, new submission button used | Permitted; no automatic retry lineage is created. |
| Explicit Resubmit with equivalent barcode width | Parent check still compares stored digits exactly: a 12/13-digit mismatch can reject legitimate lineage. This is a confirmed contract gap; reproduce before correcting. |
| Two incomplete drafts | Existing uniqueness applies when ready; duplicate draft creation/resume behavior needs adversarial testing. |
| Different users submit the same product | Per-user receipts are not globally deduplicated by the open-attempt index. Reviewer/product resolution must prevent duplicate catalog publication without exposing another user's data. |
| Same barcode later arrives from DSLD | Existing review index includes catalog and manifest-owned corpus; export deliberately preserves ambiguous barcode candidates rather than picking the highest score. Future-source collision behavior needs explicit end-to-end fixtures. |

## 2. One remaining-work ledger

| Track | Required closure | Relationship to beta |
|---|---|---|
| A. Submission hardening | Batch 0 closes existing identity/device work; Batches 1/2/4/5 extend evidence, capture, review and retakes | Close Batch 0 and relevant Track F checks before enabling outside submissions; later enhancements have their own gates |
| B. Original Batch 3 extraction | New Batches 1/3/4/6: frozen holdout, qualifying extractor, reviewed-draft integration, private pilot | Can follow or run alongside a manual-review beta; not a prerequisite for manual submissions |
| C. Clinical curation | Current quarantine dispositions; priority native contexts; botanical/preparation questions; IQM evidence backlog; benchmark actives classified | No guessing to increase availability; incomplete assessment must be honest on beta surfaces |
| D. Rubric/benchmark/calibration | Ratified rubric concepts; fixed independent panel; locked analysis; only then justified weight changes | A beta is not evidence of clinical validation; health-use claims require separate clinical review |
| E. Schema/performance/maintenance | Schema-3 payload and warning equivalence, low reuse investigation, clean-label coverage decisions, gated storage maintenance | Separate changes, not reasons for another immediate 37-brand run |
| F. Beta release assurance | Current-build device matrix, access/privacy/safety review, operator support, rollback, feedback/monitoring | Explicit invitation-only beta go/no-go; not a blanket public-launch approval |

## 3. Consolidated submission implementation plan

This replaces the earlier Track A/Batch 3 ordering and incorporates Claude's
2026-09-08 revised submission-workflow proposal. It is the single execution
checklist; the August spec and pasted proposals are design history, not competing
task lists. The existing Tracks C–F below remain open.

### Non-negotiable design decisions

- Reuse `get_product_submission_intake`, the canonical GTIN comparison helpers,
  the current review console, and the existing approved-label importer.
  Do not implement a second preflight or a second scoring engine.
- One contribution can have multiple immutable evidence revisions. Revising evidence
  is not rejecting the submission, deleting history, or mutating an old manifest.
- New-label approval and duplicate resolution are DIFFERENT actions. A verified
  duplicate is never eligible for "approve as new", even if the UI groups both
  as ready for a human decision.
- A partial extraction is a valid draft with explicit unknowns. Only the final
  human-verified payload must pass `manual_label_v1`. A failed or abstained model
  must never prevent manual transcription or verified manual batch approval.
- Candidate barcode matches are not label-equivalence findings. No automatic
  PG_SUB-to-DSLD merging, highest-score selection, or bulk duplicate disposition.
- All asynchronous work is bound to submission, evidence revision, immutable
  photo snapshot, preparation configuration and a current lease token.
  Authenticated worker identity alone does not authorize a stale write.
- Capture guidance may precede extraction qualification; server evidence requirements
  remain unchanged until a tested revision-aware replacement is deployed.
- One local model and one inexpensive hosted comparator are enough for the pilot.
  No optional third/fourth provider adapters unless a measured limitation justifies
  them. Local has no per-token API charge, but still consumes hardware time.
- Budget amounts and provider-photo use require explicit operator approval.
  A configured privacy flag records reviewed account controls; it does not prove
  provider retention behavior or grant permission by itself.
- No claim of universal 100% extraction accuracy. Preserve raw error counts,
  unknowns and uncertainty. Human approval is required for every catalog label.

### Ownership and operating rules

**Recommended arrangement:** Claude Code implements one assigned batch; Codex
independently reviews the exact commit range, then owns integration/deployment
verification after ownership is handed back. Claude addresses review findings on
that batch before integration. If Codex takes over a fix, Claude stops editing
those files first. Either agent may be the implementer, but never two simultaneous
owners of the same modules or migrations.

No "build everything, audit at the end" handoff. Each batch returns:
- base/head commit hashes in both repositories and exact migration names;
- completed/remaining checkboxes and files changed;
- failing-test reproduction, green focused tests and broader verification;
- screenshots/device evidence where UI changes;
- authorization/grant results for database changes;
- known limitations, deployment ordering and rollback behavior.

Current identity work is LOCAL ONLY:
- Pipeline: `worktrees/submission-identity`, branch
  `codex/submission-identity-hardening`, code commits
  `d8513897`, `13314173`, `a0d3a6aa`; handoff `2db43114`.
- App: `.worktrees/submission-identity`, same branch name,
  `0c02f9d` (SQL/harness), `01b01a5` (Flutter).
- Local Claude can inspect these worktrees. Cloud Claude cannot see them until
  the branch/plan is pushed and both repository checkouts are configured.
  Private photos, .env files, local generated corpora, Ollama and the phone are
  not supplied merely by repository access or a chat subscription.
- Cloud work may use synthetic fixtures and repository tests. Real-photo benchmarks,
  local-model runs, production migrations and physical-device checks stay on an
  explicitly configured/authorized host. Never commit credentials or private photos.
- After authorization, publish the existing branches before delegating cloud work;
  do not reconstruct or cherry-pick guessed commits from a prose handoff.

**Every implementation task follows five tracked actions:**
1. Write a behavior/contract regression, with exact expected failure.
2. Run the focused test and retain its RED output.
3. Change the existing owner or add the smallest required component.
4. Run focused GREEN tests and the task's adversarial/real-case gate below.
5. Review the diff, obtain independent review for the completed batch, commit a
   scoped change, and update this file. Do not check a deployment box after tests alone.

### Batch 0 — Integrate identity and establish the real baseline

**Dependencies:** none. **Suggested owner:** Codex integrates its existing work;
Claude independently checks the paired range before merge.
**Files:** existing identity handoff; app migration
`supabase/migrations/20260908230736_harden_submission_identity_and_intake.sql`;
`scripts/test_submission_identity.sh`; existing submission, scanner and
`test/release_gate/quick_check_catalog_interaction_test.dart` tests.

- [x] Implement canonical receipt comparisons, intake, immutable retry concurrency,
  owner privacy and current-source reviewer checks. See the identity handoff.
- [x] Record focused/SQL/simulator evidence; broad results are in the status header.
- [ ] Diagnose the vinpocetine bundle-gate failure from actual current source exclusions,
  export and test intent. Do not assume it requires a policy change. If the catalog
  lost eligible products, fix the producer; if the canary's availability premise is
  stale, repair that premise while retaining meaningful safety/interaction assertions.
  Do not force eligibility, remove assertions blindly, or change weights.
- [ ] Fetch both repositories, reconcile unrelated work, review and merge/push the
  paired branches only when authorized. Preserve unmerged work; no broad branch deletion.
- [ ] Inspect linked migration history and the complete pending set. Apply only the
  reviewed new migration in the normal deployment sequence; no blind `db push`,
  no historical migration editing, no metadata-history surgery.
- [ ] Verify live RPC permissions and owner isolation, then build the new phone app
  and restart the reviewer console. The database RPC must precede its Flutter client.
- [ ] Run the identity/device matrix: same actual GTIN while pending; rejected-as-new; explicit
  width-variant retry; interrupted upload; second account; known/ambiguous catalog
  lookup; promotion; correct contribution deep link; notification supersession and
  retries; ten points once; operator new-submission notification separately.
  Use authorized test receipts; do not approve unreviewed labels as a test shortcut.
- [ ] Record a narrow identity/device closure. No 37-brand rebuild is needed for the
  identity code. If the separate catalog diagnosis needs rebuilding, run targeted
  producers first and retain ordinary release gates.

**Gate:** identity behavior verified on target server/build; the independent catalog
failure explained and resolved before claiming a green app/release.

### Batch 1 — Consent, human draft authorization, benchmark and evidence foundations

**Dependencies:** Batch 0 source integration. Synthetic tests/benchmark design may be
prepared earlier in a separate branch.
**Files:** app `supabase/functions/review-product-submissions/index.ts`,
`schema.ts`, associated Deno tests, new forward migrations in app
`supabase/migrations/`, `supabase/tests/submission_identity/`;
`lib/services/product_submission_service.dart` and shared consent copy;
pipeline `scripts/submission_review/HOLDOUT.md`,
`scripts/submission_review/extraction/envelope.py`, `benchmark.py`,
`scripts/tests/test_submission_extraction.py`.

- [ ] B1.1: Version the consent contract. Record authenticated owner, accepted consent
  version/purposes, server time, and evidence revision. Require explicit client
  acceptance; never assign consent retroactively because a row exists.
  Recheck eligibility when enqueuing, claiming and sending photos, not just once.
  Define manual-review behavior for legacy/no-extraction-consent receipts.
- [ ] B1.2: Fix the HUMAN extraction writer first: derive recorder from `auth.uid()`
  and the human reviewer allowlist, forward validated usage, revoke the obsolete
  caller-supplied-recorder signature and naked service-role path.
  Deploy the paired RPC/Edge action coherently. Do not add job-dependent parameters
  referencing tables that do not exist yet; worker signatures arrive in Batch 3.
- [ ] B1.3: Define and test the revision contract BEFORE either new client or worker
  depends on it: append-only revision records with a frozen manifest, active revision,
  owner, state, timestamps and digest; revision membership refers to immutable photo IDs.
  Unchanged photos may be referenced without being counted as independent corroboration.
  New bytes receive new IDs/paths. Do not simply add an integer and reopen the old row.
- [ ] B1.4: Migrate existing evidence as revision 1 without changing bytes/history.
  Resolve all consumers through one revision-aware manifest function: create/finalize,
  photo signing/RLS, extraction hash checks, match checks, product-image selection,
  review records, release import/promotion, cleanup and audit reports.
  Preserve schema compatibility deliberately; an old client must not write into a
  newer revision through a legacy overload.
- [ ] B1.5: Keep user-visible status coherent when a new revision is pending: old
  approval/rejection checks cannot authorize it, stale pushes are superseded, active
  review claims and approved/promoted receipts cannot be reopened by a worker.
  A revision-opening request uses an expected revision and idempotency key; concurrent
  requests create one revision or a typed conflict, not two active manifests.
- [ ] B1.6: Freeze 20 development and 40 held-out PRODUCTS, grouped by brand/family,
  with independently checked gold labels. No original photos or answers in public
  git/app assets. The model under test cannot write its own gold answers.
  Include glare, curvature, tiny print, split/combined panels, wrong-slot photos,
  mismatched bottles, ambiguity, nested blends, multiple forms, mg/mcg/g/IU/CFU/AFU,
  percent-DV-only rows, serving/daily ranges and intentionally unreadable images.
- [ ] B1.7: Define `label_draft_v1` with a versioned envelope: job/revision/snapshot,
  provider/model/config fingerprints, actual sent-input references, precise usage,
  declared/inferred photo roles, typed discrepancies and explicit abstention.
  Fields carry value/status, source photo/text/region and optional extraction-confidence
  metadata. Cover label identity, serving basis, amounts/units/%DV, forms, nesting,
  other ingredients and printed statements. Confidence is not a scoring pillar.
  Draft validation permits unknowns; approved validation does not. Preserve
  source amounts/units/forms/ownership verbatim and source photo/region. Never invent
  `ingredientGroup`, clinical identifiers, safety claims, conversions or scores.
  Build shared Python/Deno fixtures before connecting a provider.

**Qualification criteria to approve and freeze BEFORE model results:** schema-safe
draft or typed failure; ≥99% readable ingredient-row recall; ≥99% exact
amount/unit/serving-owner tuples; zero observed invented actives, wrong-product
substitutions or order-of-magnitude errors; zero critical errors after human review.
Report per-product/per-family n/N, confidence intervals/uncertainty and abstentions
as missing coverage. Target ≥30% median reviewer-time reduction without worse p95
review time. Proposed bounded-set p95 draft latency ≤60 seconds, cold start separate.
These are pilot targets, not clinical standards or a universal accuracy guarantee.
A separate OCR/retake set measures false positives; its cutoffs must also be frozen
before enabling automatic user-facing decisions.

**Gate:** local executable migration/auth/replay tests, coherent existing manual
draft flow, reviewed revision schema and frozen evaluation set. No live worker yet.

### Batch 2 — Durable drafts and simpler capture

**Dependencies:** Batch 1 consent/revision contract. Does NOT require a qualified extractor.
**Files:** app `lib/features/scanner/missing_product_submission_sheet.dart`,
`scanner_screen.dart`, `lib/services/product_submission_photo_service.dart`,
`product_submission_service.dart`, `photo_quality_gate.dart`;
new `photo_panel_classifier.dart`, draft store/service and a Drift table in the
existing user database; contribution screen; corresponding scanner/service/database
tests; `pubspec.yaml` only for approved camera/OCR dependencies.

- [ ] B2.1: Write recovery tests before UI changes: kill/relaunch, OS camera activity
  loss, partial upload, missing local file, account switch/logout, expiry, cancellation,
  two concurrent resumes, and a server receipt that became ready elsewhere.
- [ ] B2.2: Persist sanitized bytes in app-private storage (not temporary picker paths)
  plus immutable submission ID, owner, original barcode/symbology, lineage, revision,
  photo IDs/hashes/categories and upload progress. Use OS file protection, keep private
  evidence out of unintended backups, define deletion/retention after success or cancel.
  Reuse existing idempotent create/finalize/upload sequence; one uploader/lease per draft.
- [ ] B2.3: Offline capture may save a LOCAL draft, never claim server acceptance.
  On reconnect, run the existing intake before creating/uploading it and resolve
  conflicts without overwriting evidence. Verify real requests, not connectivity
  notifications alone. Account changes never resume another owner's draft.
- [ ] B2.4: Present capture → review/send, with intake as an inline check rather than
  an extra screen. Prototype the actual persistent still-camera session, focus,
  orientation, memory, startup and image quality; retain system-camera/gallery fallback.
  Barcode preview frames are not automatically adequate label photographs.
- [ ] B2.5: Add multi-select within current caps and sha256 dedupe. Reuse the original
  scanner image only after sanitization, quality checks and successful decoding to
  the established GTIN. Otherwise request a barcode shot.
- [ ] B2.6: Add on-device OCR behind one adapter after measuring platform size/startup
  tradeoffs. Installed Dart scanner is 7.2.0; its pod's 7.0.0 metadata is not the Dart
  dependency version. iOS currently uses Apple Vision, so text OCR is new work.
  OCR suggests roles; detecting a heading does not prove the whole panel or ingredients
  list is present. Record/confirm declared roles; inferred roles remain distinct.
  Unknown/cut-off/foreign-language cases retain manual confirmation and required evidence.
- [ ] B2.7: Benchmark false suggestions; enable qualified assistance only. Check
  wrong-slot photos, blank/unrelated shots, multiple barcodes, permission denial,
  lens changes, small screens, 2x text, VoiceOver and accessibility targets.
  Record before/after taps, capture time and incomplete-upload rate.

**Gate:** simulator/screenshots AND real-device capture/recovery matrix. No weaker
server evidence gate, no immediate-AI claim while the worker is offline.

### Batch 3 — One secure queue/worker and the extraction experiment

**Dependencies:** Batch 1 revision/consent/auth foundations. May be implemented independently
of Batch 2 UI once the shared contract is frozen.
**Files:** new app forward migrations, extraction-job SQL tests,
`supabase/functions/review-product-submissions/index.ts` and its tests;
pipeline `scripts/submission_review/extraction/{extractor,photo_prep,envelope,checks,to_manual_label}.py`,
`ollama_adapter.py`, ONE hosted adapter, `fake_adapter.py`,
`scripts/prepare_product_submissions.py`, repo-owned
`.claude/skills/prepare-product-submissions/SKILL.md`, focused extraction tests.
The proposed new commands do not exist yet.

- [ ] B3.1: Create one durable preparation queue, locked worker allowlist/settings,
  and fractional-cost reservations/settlements. Keep points tables out of this migration.
  Enqueue once when the current consent-eligible missing-product revision becomes ready.
  No inference/network calls inside database transactions.
- [ ] B3.2: Job identity binds revision's canonical full manifest (including roles),
  preparation/model/prompt/schema/privacy configuration; result fingerprint also binds
  actual sent inputs/crops and model digest. Role changes invalidate appropriate results.
- [ ] B3.3: Claims use bounded leases, attempt limits, backoff and fencing tokens.
  Every heartbeat, evidence-check write, result record, completion and budget settlement
  checks actor, active job/lease token, revision and snapshot. Reject stale attempts
  after lease reacquisition even by the SAME worker. Make retries/cancellations idempotent.
- [ ] B3.4: Worker uses its own authenticated principal, never a human allowlist entry
  or production service key. Permit private photo access only to its leased revision.
  Cap signed-URL lifetime; never imply revoking a lease retroactively erases an issued URL.
  Bound fetch bytes/pixels/time/decompression; verify hashes; reject foreign paths,
  redirects, hostile URLs and cross-submission evidence. Redact logs and protect any
  locally spooled model output with bounded retention.
- [ ] B3.5: Add worker draft writing through the SAME private validator/persistence
  function as human draft writing. Revoke stale/public overloads. Test anon, user,
  spoofed human, unleased/revoked worker, expired token and naked service-role attempts.
  Worker may not approve, reject, mint a product, publish or edit clinical data.
- [ ] B3.6: Benchmark one installed, digest-pinned local vision model, then one
  authorized hosted comparator. No unapproved paid calls, silent provider fallback,
  consumer-UI automation, or free provider access that violates photo privacy.
  Run deterministic photo/hash/barcode checks and the EXISTING identity index before
  inference; require a configured current index/artifact, not a second matching table.
  A hit supplies comparison context, never an automatic duplicate/new-product decision.
  Excluded state/kind/consent and already-completed job replays make zero provider calls.
  Preserve suspicious label text as data; model has no tools/credentials.
  Validate draft schema, ownership, raw values and provenance before storage.
- [ ] B3.7: Freeze adapters/prompts on development data, then run the untouched holdout.
  Select by errors → review time → total accepted-label cost. Include human correction,
  retries, image billing, cold start and hosted compute; do not call local compute free.
  If a model fails, keep manual review and document extraction NOT qualified.
  Tuning after holdout failure requires a fresh untouched evaluation set.
- [ ] B3.8: Implement one CLI for status/dry-run/bounded run/triage, with count/time/
  spend limits and safe resume. Display human-friendly currency; store precise integer
  units internally with a declared scale. Enforce global budget reservations before
  provider calls, handle uncertain billed outcomes explicitly, and preserve manual review.
- [ ] B3.9: Thin skill calls the CLI and summarizes actionable results; no improvised
  labels, approve/reject/publish calls, secrets or photo URLs in chat.
  Local catch-up runs when the Mac is awake. Configure a schedule only on explicit
  request; a sleeping laptop is not an always-on host.

**Gate:** executable SQL lease/budget/privacy tests; fake-adapter negative cases;
frozen local/hosted benchmark with denominators. No provider qualifies completes
the feasibility experiment, NOT the requested extraction feature.

### Batch 4 — Reviewer workstation and verified batch actions

**Dependencies:** revision/consent foundations; partial-draft contract.
Manual-only workstation work can precede a qualified model.
**Files:** pipeline `scripts/submission_review/static/{app.js,index.html,styles.css}`,
`serve.py`, existing behavioral server/browser tests; app review Edge action/schema;
new forward migration for field verifications and action-specific review receipts.

- [ ] B4.1: One queue with readiness filters plus age/overdue ordering so difficult
  labels do not starve. Show duplicates only to authorized reviewers. Metrics endpoints
  and photo/draft routes require the existing reviewer/origin protections.
- [ ] B4.2: Side-by-side evidence/draft, source-region zoom, unknown/conflicting fields,
  exact units/forms/blend nesting and serving basis. Late extraction never replaces human
  edits. Keyboard shortcuts ignore typing fields and require deliberate decision confirmation.
  Show field confidence as an extraction-review cue only when its relationship to
  held-out errors is measured; raw model self-ratings are not validated probabilities.
  Keep extraction confidence separate from clinical evidence, product quality and safety.
  Restrict AI drafts/working notes to reviewers; submitters see typed photo guidance,
  history and final decisions, not unverified ingredient or health claims.
- [ ] B4.3: Verify critical fields against the current payload AND evidence snapshot.
  Persist actor, revision, payload hash, source photo/region and check scope. Bind hashes
  consistently in Python/JS/SQL; row reorder/source change cannot transplant verification.
  Editing invalidates dependent checks, not merely a visual checkbox.
- [ ] B4.4: Separate eligibility: "ready to approve new" needs fresh no-match/allowed
  reviewed resolution, complete evidence/field checks and a valid product image.
  "ready to resolve duplicate" needs verified label equivalence and a specific target,
  but must NEVER enter new-label approval. Manual labels can satisfy checks without AI.
- [ ] B4.5: Reuse the EXISTING public human authorization/approval boundary (including
  match/image gates), not merely a direct call to a lower-level internal helper.
  Batch submits bounded, idempotent per-item transactions with independent results;
  one conflict cannot silently roll back or duplicate other completed items.
- [ ] B4.6: Recheck revision, payload, field checks, human authority and identity evidence
  at commit. The database cannot inspect local catalog files: bind the recorded match
  proof to its actual index generation and define its authoritative freshness check.
  Never claim server-side recomputation of a local index. Before batch release,
  test a source update between displayed matches and the final decision.
- [ ] B4.7: Show candidates side by side. Record equivalence before resolving twins,
  quarantined DSLD matches, different strengths or old editions. Preserve reference IDs;
  any PG_SUB→DSLD alias/edition support needs a reviewed explicit contract and targeted
  import/export/app-lookup fixtures before implementation. Until then, hold ambiguous cases.
- [ ] B4.8: Measure active review minutes, correction rate, queue age, abstention,
  failed preparations and accepted-label costs; avoid counting idle tabs as review work.
  Browser tests cover stale data, errors, session expiry, keyboard, lost edits,
  partial batch success and replay. Take screenshots of actual rendering.

**Gate:** independent authorization/identity review; verified manual and AI-draft
paths both work; duplicates cannot mint another product.

### Batch 5 — Evidence revision retakes and actionable notifications

**Dependencies:** Batches 1/3/4; qualified per-reason retake evaluation.
**Files:** revision/evidence-check RPCs and tests, existing submission push queue/drain,
reviewer console, Flutter contributions/capture/draft store, corresponding tests.

- [ ] B5.1: Record photo findings in observation mode first. Distinguish model failure,
  unreadability, missing panel, identity conflict, foreign language, handwriting,
  visible date and discontinued availability. None is an automatic safety verdict.
- [ ] B5.2: Adjudicate false-retake rates on the frozen set and an authorized shadow
  pilot. Enable validated reasons individually only after the predeclared criterion passes.
- [ ] B5.3: "Retake now" opens a NEW immutable evidence revision of the SAME contribution,
  with retained history and unchanged product identity. "Send for human review" always
  available. Cap automated requests, bind the cap increment to a unique finding event,
  and respect active human review/approved/promoted states.
- [ ] B5.4: Notification events bind revision and event key. Retry cannot send the same
  stale request again or multiply counts/points; coalesce superseded events and clear
  errors after success. FCM is not an end-to-end exactly-once guarantee.
- [ ] B5.5: Test old-revision results, offline phone, token rotation, denied permission,
  push opening the correct current receipt, capped loops and override races. Verify
  operator queue-ready/new-submission alerts separately from submitter status pushes.

**Gate:** qualified retake reasons plus physical-device retake→upload→review loop,
including a deliberately wrong automated suggestion handled without a dead end.

### Batch 6 — Operator end-to-end pilot and beta decision

**Dependencies:** relevant completed batches above. Automatic retakes may stay off
without blocking the initial extraction pilot.
**Files:** benchmark/closure reports, targeted Product_Submissions pipeline runner,
existing import/export/release audits and Flutter catalog tests; no alternate scorer.

- [ ] B6.1: Enable only authorized operator submissions under explicit model/privacy/
  spend settings. Verify actual consent and hashes; never approve intentionally corrupt
  test labels just to satisfy end-to-end coverage.
- [ ] B6.2: Compare human-approved extracted labels with independently transcribed labels
  through isolated importer → clean → enrich → score → export outputs. Identical approved
  labels must produce identical ingredients, doses, routes, scores and verdicts.
  Preserve pipeline readiness holds for legitimately incomplete label/clinical information.
- [ ] B6.3: Exercise duplicate imports, interruptions and later DSLD collisions. Different
  editions remain explicit candidates until their identity-resolution contract is implemented.
- [ ] B6.4: Run ordinary catalog release gates, one deliberate approved release, phone
  import and barcode lookup; verify product image, receipt promotion, notifications and
  ten points once. Batch Product_Submissions work; never rebuild 37 brands per upload.
- [ ] B6.5: Independent review, full affected tests and final corpus/release checks AFTER
  corpus work. Report skipped/unavailable checks honestly. Only claim Batch 3 extraction
  complete when qualified extraction and the human-reviewed real canary pass.
- [ ] B6.6: Complete Track F: deployment/rollback, support, privacy/account deletion,
  safety/warning failures, clinician-reviewed beta wording and invited-user go/no-go.
  Code-complete submission UI is not proof of clinical validation or public-launch readiness.

### Batch 7 — Points, scheduled operations and growth

**Dependencies:** proven manual/extracted promotion path. Does not gate the initial
extraction experiment. Ship as separate, testable changes.
**Files:** new app forward ledger migration/RLS, existing promotion RPC/importer,
contribution provider/screen/tests, worker CLI/skill and optional container/runbook.

- [ ] B7.1: Server append-only contribution ledger, unique promotion event key and
  atomic receipt/award write. Ten points per legitimately catalog-added contribution,
  never per evidence revision/retry/duplicate. Audit old conflicting receipts before backfill.
  Reversals are explicit events, not history edits.
- [ ] B7.2: Reconcile/backfill and freeze cutover; new client reads the ledger as the
  sole points producer. No per-row fallback that mixes derived/server totals.
  Preserve user history and non-redeemable/future-rewards wording. No redemption promises.
- [ ] B7.3: Choose an explicit local cadence and notify only on useful changes,
  failures or decisions. No schedule is created by this plan. Add an opt-in reviewer
  notification with a queue link and no sensitive content.
- [ ] B7.4: If the Mac-off backlog exceeds the agreed service target, deploy the SAME
  worker to a configured always-on runtime. Verify secret access, leases, budgets,
  concurrency, retention and alerts there; cloud subscription alone supplies none of these.
  Start concurrency from measurements, not an assumed eight-worker setting.
- [ ] B7.5: Load-test queue/database behavior with synthetic jobs, measure real provider
  throughput separately, plan reviewer staffing. At two human minutes per genuinely new
  label, 1,000/day needs about 33 reviewer-hours; extraction concurrency cannot erase that.

### Verification commands and commit gates

Use repository-root commands only in the named checkout; never raw pytest.

Pipeline development:
```bash
scripts/test.sh fast scripts/tests/test_product_submission_import.py scripts/tests/test_submission_review_server.py scripts/tests/test_submission_lineage_e2e.py
scripts/test.sh fast -k "submission or review or gtin"
```

When new extraction tests exist, include them through the same runner. Run full
`scripts/test.sh fast` once per integrated material batch, not after every tiny edit.
Use `scripts/test.sh release` and `scripts/test.sh full` for final shipping after
the corpus pipeline; never alongside it. Existing corpus skips in a worktree are
not a full-corpus proof.

App development:
```bash
flutter test test/services/product_submission_service_test.dart test/services/product_submission_retry_contract_test.dart test/features/scanner/missing_product_submission_sheet_test.dart
flutter analyze
scripts/test_submission_identity.sh --advisors
```

The SQL harness exists on the identity branch; it uses disposable local Docker,
not a linked production project. Extend it for the new migration chain. Run the
affected Deno/SQL tests by verified repository command and app `make check` once
at a substantial batch end; use the project's Flutter runtime and initialize
ignored codegen/assets in fresh worktrees. New UI needs screenshot/device checks.
Do not quote expected test counts as actual results.

**Deployment sequence:** reviewed commit and migration set → authorized backend
deployment with features OFF → permissions/current-manifest smoke checks → paired
client/console → operator canary → enable qualified features → later normal release.
Only the operator grants new production/spend/photo-sharing authority. No blind
migration push, destructive cleanup, production fixture corruption or clinical
signoff performed by an AI agent.

## 4. Tracks C/D — clinical work stays explicit

- [ ] Reconcile every current excluded product to corrected source evidence, permanent out-of-scope disposition, or an actionable waiting-for-label/clinical-policy hold. Start with fixable families and operator-supplied labels. Retaining a hold safely is not the same as resolving its ingredient.
- [ ] Finish high-impact evidence/preparation reviews and qualify the 16 native contexts; expand from measured unmet demand (including the handoff's BB536/HN001/DE111/formula candidates), not a target registry count. Verify each source and isolate branded edition, preparation, population, outcome and dose.
- [ ] Retain conservative primary-owner selection until a reviewed alternative earns adoption. Cranberry urinary support remains disabled until reviewed preparation/dose applicability and any CranRx source-label change are approved; do not resurrect a universal 500 mg rule.
- [ ] Work the 195 form-evidence records in prioritized batches. Correct free text as well as structured values. Re-audit clean-label coverage separately; a candidate ingredient does not become a US safety block without reviewed policy.
- [ ] Ratify the probiotic rubric's CFU/strain-count/disclosure/evidence responsibilities and incomplete-assessment wording. Inspect consumer rendering so “not yet reviewed” does not masquerade as “bad quality” or “safe for you.”
- [ ] Ratify the independent benchmark protocol, recruit the fixed three-rater panel with at least two qualified licensed clinicians, finalize review of its material actives, freeze current label facts and sealed keys, collect independent responses, then lock analysis. No AI-written clinical signoff; historical assisted responses remain exploratory.
- [ ] Only if that analysis supports it, propose a separate calibrated scoring/config version. Choose reliability/agreement and robust category behavior, not a target Seed score or prettier tier histogram. No weight tuning in Batch 3.

## 5. Tracks E/F — maintenance and external-beta gate

- [ ] Diagnose this release's zero-reuse detail upload from content and uploader behavior; separate real data changes from volatile fields, index/path changes and upload decisions. Do not promise the earlier projected churn saving was realized without a new measurement.
- [ ] Execute schema 3 as a separate compatibility/payload project: prove every removed family unused by all consumers, consolidate RDA projections, preserve profile-specific warning equivalence, generate intended app projections, and retire legacy code only after caller/fixture proof. 2.4 fixtures alone do not close it.
- [ ] Refresh storage maintenance inventories when due. The major drain/RPC/stale-dir work is closed; expiring quarantine and new release orphans are recurring operations. Every irreversible sweep still needs its own fresh identity-bound approval. Do not run cleanup as a side effect of this plan.
- [ ] Before inviting outsiders: close Batch 0's identity/device gate or disable contributions; verify current-build scan/ambiguous-bottle/offline/profile warning paths, fail-closed incomplete interactions, data reset/account deletion/privacy, reviewer isolation, push auth and queue failures. Independently verify whether previously exposed signing credentials were rotated; do not claim this happened without evidence.
- [ ] Confirm support/feedback route and owner queue coverage, privacy-safe error telemetry, rollback catalog/app path, feature-off controls and sensible storage/rate/spend limits. Beta users' medications/conditions remain on device under existing policy.
- [ ] Conduct clinical-owner review of health-facing claims and unresolved-risk presentation before health-use beta. An invitation-only usability beta is not permission to market validated efficacy or rely on the app for treatment decisions. A disclaimer does not repair incorrect safety logic.
- [ ] Record a narrow beta go/no-go with known limitations and tested build; do not call the entire app “perfect” or “100% accurate.” AI extraction, full IQM curation, schema 3 and optional recalibration need not all block a manual-review usability beta, but all remain on this ledger until explicitly completed.

## 6. Execution handoff and remaining whole-project work

The submission sequence is Batches 0–7 above. Its numbered batches replace the older
A1/A2/A3/B1–B7 task ordering, not the Tracks C–F completion ledger. Simplified capture
and a manual-review workstation can precede a qualified extractor; unattended
preparation and retake enforcement cannot precede their authorization/benchmark gates.

- Finish Batch 0 integration first. Claude can prepare Batch 1 fixture/spec work on an
  explicit separate branch while Codex integrates, but no overlapping migration edits.
- Once ownership is assigned, Claude implements one batch and sends its exact range
  to Codex. Findings go back to that batch's owner; switch owners explicitly if needed.
- Independent clinical curation/benchmark recruitment can continue alongside submission
  engineering. Clinical policy needs qualified human review, not a model's signoff.
- Reconcile current holds and review evidence/rubric interpretation before weight calibration.
  Schema 3, payload efficiency and storage operations remain separate tested releases.
- Before external beta, close the relevant Track F checks and document limitations.
  Full public-launch readiness and clinical validation are not implied by closing Batch 3.
- Do not claim any unrun gate complete. Each deployment, benchmark and device closure
  records actual versions, artifacts, results, failures and remaining decisions.

### Evidence anchors

- Original scope: `scripts/audits/probiotic_rubric_review_2026_09_04/CLAUDE_HANDOFF_2026_09_04.md`, sections 7–8.
- Accepted engineering/integration results: `docs/release_candidates/identity_quarantine_gate_2026_09_08.md` and continuation return package.
- Submission design: app repo `docs/superpowers/specs/2026-08-25-submission-ai-review-design.md`, especially Batch 3, and current executable reviewer/RPC code.
- Current duplicate guard: app migration `20260903065755_canonicalize_open_submission_gtin_dedupe.sql`; historical explicit retry comparison: `20260903064547_require_missing_product_barcode_evidence.sql`. The new identity migration on the local branch fixes its width comparison; it is not deployed yet.
- Current numerical targets/provider choice are proposals in THIS draft; no earlier completion note or provider marketing benchmark supersedes the frozen pilot evaluation.
