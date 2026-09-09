# Extraction workflow audit and continuation

> Historical audit. The later
> [workstation audit and continuation](submission_workstation_audit_2026_09_09.md)
> records the current fixes, local integration evidence and candidate version.

2026-09-09. Audited pipeline `b33615ee..3fa96b55` and app
`8825941..171c4cc`. These are source fixes, **not a deployment or model
qualification**. The catalog, clinical data, scoring weights and production
extraction switch were not changed. Do not run a catalog rebuild for these
submission-only changes.

## Confirmed defects and corrections

| Boundary | Reproduced defect | Correction |
|---|---|---|
| Adapter → extractor | Real adapter returned a dictionary; the shared interface requires draft plus usage. | Returns the canonical result and is tested through the real extractor. |
| Model → draft | First photo was assigned as the source of every field. Rows without readable names were dropped; forms and blend parentage were flattened. | Model produces the existing label-draft content shape with field-specific sources. Runtime provenance remains program-owned. Canonical validation rejects missing sources; unknown rows, forms and nesting survive unchanged. No second normalization schema. |
| Private HTTP | Loopback-prefix lookalikes passed; automatic redirects/proxies and unbounded buffered responses weakened the privacy/deadline claims. | Exact parsed loopback hosts; one shared bounded HTTP transport for queue and adapter. No redirects, environment proxies, decompression or automatic write retries. Real HTTP tests exercise oversized bodies and slow-drip deadlines. DNS remains OS-managed for the configured Supabase hostname; local inference uses a literal address. |
| Local provider identity | A localhost daemon can proxy cloud models; fake output could claim an Ollama configuration. | Reject remote model metadata / missing local-weight metadata; check installed digest before and after inference; fake adapter accepts fake configurations only. Local daemon remains a trusted operator dependency. |
| Development → benchmark | No candidate id, incompatible configuration, no retained transmitted files; a run could overwrite gold. | Match one predeclared candidate including adapter-owned prompt digest; retain sanitized inputs and verify through the actual evaluator; new private run directories only, with exclusive writes. |
| Reviewer → manual label | Inserted 1 capsule / 30 servings / zero mg defaults, discarded unknown rows and parentage, hid an observed Other Ingredients list, omitted forms and warnings. | Blank/unknown values remain blank. Preserve printed serving data, forms, parent-child structure and statements. Carry %DV as explicit label notes because manual_label_v1 has no scalar %DV field. Show conflicts and role issues. Canonical approval validation remains server-owned. |
| Reviewer selection | Queue summaries contain no drafts; detail was not fetched until the signed-URL timer fired. | Immediate detail fetch, asynchronous selection guard, preservation of edits and retry scheduling. Only current-revision model drafts enter the AI panel. |
| Worker lifecycle | Downloads happened inside claim, outside heartbeat / job failure handling. | Claim registers evidence only. The shared worker fetches and prepares it inside the heartbeat scope. Validate ids before constructing any path; encode Storage object paths; reuse the preparation byte ceiling. |
| Budget / credentials | Truthy non-boolean acknowledgements could authorize spend; admin environment opt-out and admin keys in the public-key slot were accepted. | Strict acknowledgement type; public-key and endpoint checks; remove admin opt-out; refresh expiring worker sessions. |
| Uncertain completion | “Reconcile” was manual-only, returned other workers' attempt metadata, and suggested re-running a still-live attempt. | Exact worker-owned database attempt receipts, derived transactionally from queue changes. Read after a failed completion acknowledgement, never retry the write blindly. Private local attempt journal supports operator reconciliation when both requests fail. Generic SQL precondition errors are not all called lease loss. |
| Photo authorization | Turning extraction off or retiring consent did not revoke an already-leased worker's photo-read policy. | Read policy checks enabled state, current/open/ready revision and current AI-draft consent. |

The forward app migration is
`20260909190858_harden_extraction_attempt_receipts.sql`. It is **unapplied**
outside the disposable local test database. Internal receipt writes are not
granted to workers; read RPC checks the exact worker/job/fence. No provider,
reviewer or local journal can author a second queue state.

Local prompt configuration is now `label-draft-local-v2`. Obtain its immutable
digest from `OllamaAdapter.prompt_sha256`; do not copy an old `p1` candidate
under the new prompt. It has not qualified on real photos.

Ollama's own [local-only guidance](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features)
requires disabling cloud on the daemon and restarting it. Localhost alone is
not privacy proof. This audit did not change the operator's global Ollama
configuration or contact any cloud model. Supabase photo authorization follows
its [Storage RLS contract](https://supabase.com/docs/guides/storage/security/access-control).

## Verification and remaining proof boundaries

- Fast backstop: **14,019 passed, 42 skipped**, 414.44 seconds. Final affected
  suite after the last isolated lifecycle/refresh hardening: **301 passed**,
  73.30 seconds. The only warning is the intentional decompression-bomb fixture.
- Disposable real migration chain, concurrency cases and security advisors:
  **70 SQL cases passed**, no advisor errors. No linked production database
  was used.
- Real browser rendering, synthetic data: serving size 2 capsules, 60 servings,
  unknown child dose, blend nesting, glycinate form and critical multiple-bottle
  warning inspected. [Screenshot](screenshots/extraction_draft_audit_2026_09_09.png).
  This was a static fixture, not a signed-in operator or physical-device test;
  the fixture server intentionally had no auth/config API.
- Real local `qwen3.5:latest` trial, synthetic engineering label only:
  bounded failure at 60.19 seconds (`provider_unavailable`). This proves the
  timeout path, **not successful extraction or accuracy**. Do not quote
  Claude's earlier 15.8-second adapter-only trial as the new workflow's speed.
- `scripts/test.sh release` remains **blocked** by existing
  `data_vs_enriched` reference fingerprint mismatches across the 38 enriched
  manifests. No bypass and no enrichment/release run.
- Still unproven: real authenticated HTTP through **PostgREST + Storage +
  worker + model + reviewer**, real-photo accuracy, human correction time,
  coordinated deployment, phone canary. SQL function tests and fake HTTP
  transports must not be relabelled as that integration proof.

Local detailed logs: `/tmp/pg_extraction_audit_fast.log`,
`/tmp/pg_extraction_audit_final_slice.log`,
`/tmp/pg_extraction_sql_green.log`,
`/tmp/pg_extraction_audit_release.log`.
They are execution receipts, not new implementation contracts.

## Claude's next substantial milestone

Continue **Batch 3 integration proof + the Batch 4 reviewer workstation** as
one source-only milestone. Do not stop after every helper or ask the operator
to adjudicate routine engineering.

1. Fetch both repositories; verify this audit's commits are ancestors. Read
   actual public interfaces and sweep every caller before changing a contract.
   Preserve unrelated work (including the five pre-existing deleted pipeline
   artifacts); never filter untracked files out of the final state report.
2. Close the real local authenticated integration gap first. Use a disposable
   local Supabase stack and fake/synthetic labels, a real worker JWT and real
   Storage authorization. Prove claim → private download → shared preparation
   → shared extractor → complete → current-revision reviewer list. Also prove
   wrong worker, expired lease, consent retirement, disabled switch, retake
   during inference, lost completion acknowledgement and restart recovery.
   Exercise HTTP, not a regex over migration text. No admin key in the worker.
3. Investigate the local model timeout using synthetic/development fixtures.
   Test the actually installed vision-capable models, bounded responses,
   prompt and generation settings. Do not download a large model, send private
   photos externally, or enable paid inference without the operator's choice.
   Bind any tuning to a new immutable candidate configuration. A timeout or
   malformed answer stays a typed failure, never a fabricated partial success.
4. Finish the reviewer workstation against the existing draft/approval
   contracts: photo-linked fields, explicit partial/unknown/conflicting values,
   visible extraction confidence labelled as **unverified model confidence**,
   persistent human corrections and restoration, clear changed-revision
   invalidation. Never replace a person's edited draft on a background refresh.
   Make unsupported label shapes explicit; do not invent defaults to pass
   manual-label validation.
5. Implement the already-planned batch actions only for individually checked
   items. Each decision must enforce reviewer identity, expected revision,
   manifest and idempotency through the canonical database transition. Model
   confidence cannot authorize approval. Report per-item outcomes for partial
   batches without silently repeating committed decisions.
6. Test the real seams first, then the affected suites; run one broad backstop
   at the milestone end, not after every file. Inspect actual rendering.
   Commit in coherent batches and publish a single return package with exact
   heads, files, tests and outstanding gates.

**One-system acceptance rule:** one canonical envelope validator, one
preparation path, one provider-neutral extractor, one queue transition owner,
one budget authority, one human approval contract. The benchmark and worker
must consume the same implementation. No parallel script that calculates the
same result, no alternative source-key spelling, no “temporary” default that
fills missing label facts. If a contract changes, its consumers and shared
fixtures change in the same batch.

### Only stop for real boundaries

- New deployment authority / credentials, an irreversible operation, or a
  substantive clinical/product-policy choice.
- The real photo benchmark: 20 development and 40 held-out products with
  independent human gold checks. The model cannot supply either attestation.
  That blocks provider qualification, not building/testing the workstation.
- A demonstrated blocker after exhausting safe in-scope alternatives.

Keep extraction disabled and stop before production rollout, catalog rebuild,
automatic approvals or any claim that the whole submission plan is complete.
The next return should say separately **implemented / integrated / deployed /
qualified**, with evidence for each.
