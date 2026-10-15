# Release readiness audit — October 15, 2026

## What is ready, and what is not

This audit separates release-tooling repairs from scoring completion and actual publication. The earlier infrastructure batch is integrated (pipeline PR146, app PR123). The follow-up implementation below is integrated through PR147, merge `0b42496d8`, with exact runtime `3277ef6db` passing whole-fast CI `38775770313` (all four groups and skip checks). This is release-tooling readiness, not a released catalog. No pipeline, catalog build, cloud publication or phone build was run for this follow-up. Sean owns the final necessary pipeline run. Claude's finished Step4 batch and the remaining shared identity/routing fixes passed final qualification through PR148: whole-fast CI 38792484069, all four groups; 601 focused tests; local 546 passed with 24 declared optional live-service skips. PR148 merged 8d206befa; source is qualified for the user-owned pipeline, not yet a published catalog. Companion app reference-copy and owner-generated manifest closeout passed full CI 38794457811.

Owner: `scripts/promote_release_artifacts.py::promote_release_artifacts` owns the local candidate transaction; `scripts/audits/run_verification_gate.py` owns content/runtime bindings and verification receipts; `release_full.sh` and `rebuild_dashboard_snapshot.sh` orchestrate them. Existing stage freshness, app importer/schema policy, OTA activation and iOS distribution owners remain authoritative. Evidence: caller search, matrix/glossary review, candidate/promotion paths and actual reader checks. Will NOT create another scorer, public status, release runner, clinical cache policy or schema allowlist.

## Every finding, with its disposition

| Finding | Disposition and acceptance boundary |
|---|---|
| Unfinished scoring, config, fixtures/canaries and associated policy decisions | **Integrated through PR148 (8d206befa).** Approved Step4 and source-grounded sugar/routing corrections pass CI 38792484069/all four groups, local and focused checks. Paired 415-label replay, 33 raw canaries and 46 public-artifact comparisons pass. This does not establish new-catalog acceptance. |
| Source can change while a catalog is assembled | **Implemented here.** Bind source/reference/enriched/scored/manual-label content, runtime/packages and effective environment before assembly; compare before candidate preservation or live promotion. A changed binding aborts. Release also checks before outward publication, including cloud-only release. This detects boundary drift; it does not make another agent's checkout immutable. One integrator must still own the final checkpoint. |
| Late producer/consumer schema mismatch | **Already integrated.** Early read-only compatibility calls the app importer's actual supported-schema helpers and reads actual producer constants. Final candidate import validation still runs before cloud publication. No second allowlist. |
| Predictable runtime/access/disk prerequisites discovered late | **Access/tool/schema checks integrated; disk estimate added here.** Read actual Supabase manifest/bucket access before expensive work; check importer tools and compatibility. Disk check budgets existing mirrors, source bytes and working headroom before assembly, including external candidate destinations. This is an estimate, not a promise against unexpected output growth. Actual upload capacity and write success remain checked against the new artifact by the upload owner. |
| Snapshot and release repeat expensive source/corpus gates | **Already integrated.** Four heavy read-only checks share sealed, successful, log-bound receipts under matching inputs/runtime/command and a 24-hour limit. Failure, interruption, mutation, missing evidence or tampering invalidates reuse. Cheap IQM checks remain cheaper to rerun. Artifact/live/publication checks are not treated as source-only checks. |
| Retrying repeats catalog assembly or loses step diagnostics | **Implemented here.** The existing candidate owner records a sealed content receipt for both complete catalog mirrors, including DBs, manifests, detail indexes/blobs and audit artifacts. Unchanged content can reuse assembly; any changed/missing output or input rebuilds. Image backfill and final contract stamping reseal their owned mutations only with the same input binding. All final candidate/live gates still run. Catalog/interaction assembly and image extraction now use the existing timed/logged verification runner. Uploads retain their own checksum/idempotency owner. |
| `--force` can build the same catalog twice | **Confirmed and fixed here.** Step 1 already assembles and stages both mirrors. Step 2 skips after that completed assembly, even under `--force`. A shell harness asserts one assembly for both forced and ordinary stale candidates. |
| Reference fingerprints are broad across stages | **Investigated; preserve the conservative safeguard.** Clean actually reads IQM, safety, excipient, delivery, clinical and other reference tables. The release rule explicitly requires earliest-stage regeneration after shared reference edits. No proven complete per-stage read map justifies narrowing this batch. Score config already has its stage-specific owner. Do not restamp old outputs or substitute a heuristic dependency list. Broad reference binding is not itself proof of a defect. |
| Live identity/content checks repeat across preparation and release | **Measured and retained under existing policy.** The preparation report's 143.8-second check is `verify_drug_class_rxcuis.py`, resolving current RxNorm identities. Registry retirement can change without a local source edit. PubMed already has a shared 14-day retrieval cache. Do not invent another cache or turn a previous network success into indefinite clinical approval. The source-only reuse above removes proven duplication without weakening final live freshness. |
| Release can introduce new intake after Sean finishes the corpus | **Fixed here.** Standalone release now defaults to the prepared submission set and refuses stale manifests. `--prepared-inputs` remains accepted. New intake is explicit via `--refresh-submissions`; prefer preparing it before the final corpus. `--force` does not misclassify fresh prepared submissions as stale. The full publishing batch already prepares intake early and preserves it through release. |
| Catalog publication confused with a new phone executable | **Operational distinction documented below.** The installed app already has compatible OTA catalog activation with integrity/schema gates. This release command imports bundled assets; it does not compile/sign/install an IPA. Existing iOS preflight/build owners apply when executable/UI/reader changes require a new app. Signing does not belong in every catalog-only release. |
| mtime-based catalog rebuild triggers | **Replaced here.** Assembly reuse uses actual input and output content, not timestamps or a hand-maintained exporter list. Touching identical source does not invalidate it. Old catalogs without a valid receipt rebuild once; no old output is relabeled as newly built. Interaction assembly retains its existing trigger and mandatory parity gates; catalog receipt does not claim interaction provenance. |
| Images/cleanup slow the critical path | **Correctness dependencies preserved; optional maintenance already separated.** Image processing binds image URLs/indexes before upload and therefore stays before publication; it now has its own timing/log. Version cleanup runs after bundle commit and failure is nonfatal. Full orphan reconciliation is already deferred. No evidence justifies removing image correctness or retention controls. Measure the next actual release before further optimization. |
| Multiple agents or standalone snapshots can collide | **Existing lock extended to direct snapshots.** The existing release/maintenance lock serializes standalone snapshot mutation; nested release snapshots reuse that owner. Input-binding checks detect concurrent source changes at candidate boundaries. Claude's separate worktree is preserved; only the final integrator runs publication. |

## Evidence and limits

Earlier integrated source `86fc5c66` passed whole-fast CI `38760338027`, all four groups and skip guards; pipeline PR146 merged `af2d95208`. Companion app `ddc35fb2` passed CI `38758475155`; PR123 merged `c88b7e41`. Earlier validation included 248 relevant pipeline tests and 11 importer tests with one declared private-candidate opt-in skip. Actual compatibility and read-only remote access passed.

The follow-up has fail-first regressions for content reuse, output corruption/missing files, source/runtime mutation, disk exhaustion, prepared-intake defaults, force handling and publication/lock ordering. The final combined owner/harness slice passed 262 tests. Real shell-entry regressions also caught and fixed macOS Bash 3 empty-argument handling and relative-path re-entry before any build could start. Independent review is clear; exact-source whole-fast CI `38775770313` passed all four groups. PR147 is merged and the validated commits are verified in remote main; its temporary branch was removed. On merged main, the actual read-only `release_full.sh --preflight-only` also passed: clean repository bases, current manufacturer deductions, producer/consumer schemas, importer tools, remote manifest/bucket read access and disk estimate. No build or publication occurred. Superseded/duplicate CI runs were cancelled, not counted as passes. A green harness is not a new-catalog or phone acceptance result.

Measured earlier: cleaner source audit 72.913 seconds, unchanged verified retry 6.025 seconds; cheap IQM audit 0.068 seconds. Preparation source tests took 712.8 seconds and raw canaries 17.384 seconds. These figures do not establish an eight-hour post-pipeline duration or a guaranteed future duration. Logs/receipts now expose actual expensive assembly and gate time so the next release can be measured rather than guessed.

## What the source review fixed, in plain language

The system should recognize what is on a label, choose the right product category, and assess each distinct quality once. It should not reward a marketing word twice or mistake one ingredient for another.

- Claude's approved Step4 work separates pillar responsibilities and removes the reviewed duplicate/count-based credits. This changes scores across the catalog; a changed score alone is not evidence of a defect.
- The remaining dietary matcher used pieces of names. That could mistake polydextrose for dextrose, or honeysuckle for honey. Matching now respects complete names and preserves genuine sweeteners.
- A label saying “less than 1 g” must keep “less than” in its explanation. The shared formatter preserves the qualifier without changing the accepted numeric benchmark or its scoring thresholds.
- Product routing no longer treats every positive ingredient amount as a vitamin/mineral panel. It uses the canonical panel and existing protein evidence; the stored result and final exported assessment use the same classifier.
- Reference descriptions now distinguish legacy evidence weights from the actual production scorer. IDs, weights, verification policy and certification scopes remain unchanged by this reference-copy correction.

The extra source fixes were measured on 415 frozen raw labels: 180 score movements, no score-status or safety-result movements. A separate 46-product final-artifact check also preserves assessment completeness and safety. All 33 raw-label canaries pass. These are development validation results, not a new published catalog or personal clinical recommendation. Remaining existing unknowns/clinical holds stay explicit.

## Simple workflow for the next update

1. PR148 is integrated after final CI/local qualification. Existing unresolved clinical holds remain explicit; they are not silently recalibrated.
2. Actual stage fingerprints now show 114 stale manifests, including Clean code and reference mismatches. Sean must run Clean → Enrich → Score once with publication disabled.
3. Sean runs that necessary pipeline once with publication disabled. Keep the prepared intake fixed.
4. Assemble one candidate. Changed inputs stop it before promotion. On retry, unchanged catalog assembly and eligible source checks reuse verified work; actual candidate/live checks still execute.
5. Publish the validated candidate through the existing release command. Confirm remote catalog version/checksum and installed-app OTA activation, then repeat magnesium name search and all-glycinate comparison in Codex against that actual published catalog.
6. Build/install a new phone app only when app executable/UI/reader or compatibility changes require it. Catalog-only scoring/data updates can use the existing compatible OTA path. Bundled fallback updates and live catalog publication are distinct from IPA distribution.

Do not delete validation because a run failed late. Fix the ordering, preserve matching work, and stop treating unfinished source work as a release candidate. Source checks do not replace actual artifact, clinical, warning, core/blob parity, minimum-app/schema, checksum or phone acceptance checks.

## WorkOS: separate external dependency

The authorized staging-only request was sent October 15 in the existing private support thread. No new support email was found in the latest October 15 check. Identifiers and correspondence remain outside this public repository. Production personal/snapshot access remains disabled.

Next requires WorkOS confirming staging resource-binding activation and the behavior of missing-resource grants, then new-grant/refresh/concurrency tests. Exact snapshot-consent authorization is separately unresolved; neither a token audience nor reusable consent ID proves an immutable authorization attempt. Public catalog work does not depend on enabling personal access, and this release-tooling batch does not claim that authorization is fixed.

## Exact user-owned pipeline command

The final read-only prerequisites passed on pipeline main `6259c5f34` and app main `5652e7d5`: clean repository bases, current manufacturer deductions, schemas/tools, remote read access and disk. No artifact was rebuilt or published. The subsequent closeout changes documentation only. From the integrated main checkout, run:

```bash
cd /Users/seancheick/Downloads/dsld_clean
source scripts/python_env.sh
PYTHON="$PG_PYTHON" bash batch_run_all_datasets.sh \
  --root /Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands \
  --stages clean,enrich,score \
  --pipeline-only
```

This rebuilds the necessary stage outputs and stops before snapshot assembly or publication. Do not remove source/provenance checks or add a release flag. The new outputs still need catalog parity, release validation, published-version verification and app/Codex acceptance.
