# Release readiness audit — October 15, 2026

## Completed delivery — October 15

Catalog **2026.10.15.235610** is published with 15,426 products; interaction DB **1.0.15** is published and pinned. Sean’s completed 38 dataset runs were reused; Codex did not rerun the corpus. App bundle `8d4bfb1d` passes clean analysis, 3,923 tests and `make verify-bundle` (full checksum plus 20 remote details). Fresh Codex testing passes **38 calls/29 records**, with all **51 magnesium capsule candidates** paged in quality order. Live testing found an older deployed public handler; it was corrected after 41 targeted tests. The comparison SQL was already current. Physical phone acceptance is unchecked. Personal/snapshot access still returns 503; WorkOS authorization remains unresolved.

PR151 fixes a measured release cost: the image inventory requested 10,000 objects once, but the API returned only 1,500. The existing uploader now reads 1,000-object pages through completion. Fail-first regressions, 93 targeted tests, independent review and CI `38839654956` passed; merged as `9a16a932b`. No stage dependency changed, so no additional corpus run is required. The release reused assembly and four heavy audit receipts. Detail transfer took 3,769 seconds; the image phase took another 1,803 seconds. These are separate from pipeline/preparation time. Old-version cleanup was interrupted after publication and reported nonfatal/deferred; orphan cleanup was not attempted. Neither housekeeping completion nor instant publication is claimed. See the current LEDGER and local `reports/post_pipeline_20261015/README.md` for full receipts and limits.

## Historical source qualification and readiness

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
| Images/cleanup slow the critical path | **Correctness dependencies preserved; optional maintenance already separated.** Image processing binds image URLs/indexes before upload and therefore stays before publication; it now has its own timing/log. Version and orphan cleanup are now separate gated maintenance commands, printed after the bundle step and not executed during publication. No evidence justifies removing image correctness or retention controls. Measure the next actual release before further optimization. |
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

## Completed delivery workflow (historical)

1. PR148 is integrated after final CI/local qualification. Existing unresolved clinical holds remain explicit; they are not silently recalibrated.
2. **Completed October15:** Sean ran Clean → Enrich → Score with publication disabled:38successful stage runs (37brands plus prepared Product Submissions), no failures.
3. Post-run stage fingerprints are current and36scoring-snapshot checks pass. Keep the prepared intake fixed; no new corpus rerun is required by the optional-precheck infrastructure change.
4. Assemble one candidate. Changed inputs stop it before promotion. On retry, unchanged catalog assembly and eligible source checks reuse verified work; actual candidate/live checks still execute.
5. Publish the validated candidate through the existing release command. Confirm remote catalog version/checksum and installed-app OTA activation, then repeat magnesium name search and all-glycinate comparison in Codex against that actual published catalog.
6. Build/install a new phone app only when app executable/UI/reader or compatibility changes require it. Catalog-only scoring/data updates can use the existing compatible OTA path. Bundled fallback updates and live catalog publication are distinct from IPA distribution.

Do not delete validation because a run failed late. Fix the ordering, preserve matching work, and stop treating unfinished source work as a release candidate. Source checks do not replace actual artifact, clinical, warning, core/blob parity, minimum-app/schema, checksum or phone acceptance checks.

## WorkOS: separate external dependency

The authorized staging retest and sanitized support follow-up were completed October 15. Explicit-resource binding now passes the manual-client staging cases. Two authorization blockers remain: a resource-less grant can still obtain a resource through refresh, and the observed reusable/mutable consent claims do not identify one immutable authorization attempt for an exact snapshot. WorkOS must provide a supported enforcement and binding contract; production personal access and snapshot uploads remain disabled. Both production containment probes still returned 503 after public catalog publication. No private environment/client identifiers are published here.

Public catalog search works independently. No WorkOS runtime or personal-account end-to-end success is claimed. The next step is the provider’s technical resolution, then fresh grant/refresh/concurrency tests before any production enablement.

## Routine preparation correction — October 15

The reported 811.9-second failure occurred before Clean/Enrich/Score. The broad developer
suite passed 23,303 cases but its batch-entry fixture omitted the newly required compatibility
script. That release-only test was outside whole-fast CI. The fixture is now isolated against
both existing entry boundaries, strengthened for compatibility pass/fail/skip, and moved into
the CI-covered release-entry test file.

Sean authorized removing the repeated broad suite from routine pipeline preparation. The normal
command now retains input/reference/runtime/compatibility/canary and source/live prerequisites,
without running all developer tests. `--include-source-tests` remains an explicit developer
preparation option. Final catalog/artifact checks still run after outputs exist; pre-checks do
not guarantee that a future build, network write or catalog will succeed. No scoring policy,
clinical data, stage output or publication gate changes in this correction.

## Historical user-owned pipeline command (completed)

The final read-only prerequisites passed on pipeline main `6259c5f34` and app main `5652e7d5`: clean repository bases, current manufacturer deductions, schemas/tools, remote read access and disk. No artifact was rebuilt or published. The subsequent closeout changes documentation only. Sean completed the following pipeline-only command. It is retained as a reference; do not rerun it for this delivered catalog:

```bash
cd /Users/seancheick/Downloads/dsld_clean
source scripts/python_env.sh
PYTHON="$PG_PYTHON" bash batch_run_all_datasets.sh \
  --root /Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands \
  --stages clean,enrich,score \
  --pipeline-only
```

This rebuilds the necessary stage outputs and stops before snapshot assembly or publication. Do not remove source/provenance checks or add a release flag. The new outputs still need catalog parity, release validation, published-version verification and app/Codex acceptance.

## Enricher/config follow-up audit

Current source follow-up: PR152. Clean/Enrich fingerprints remain current; the config/audit-metadata change makes Score artifacts stale for this new source. Existing published artifacts remain bound to the prior qualified source. No immediate rerun or republication is required for a numerical change: the measured numerical change is zero. To regenerate metadata later, start at Score only if fingerprints remain current.

Claude's historical audit was checked against current production owners, not applied as a list of assumed defects. Sugar substring matching and sports/Casein routing were already corrected before the published catalog. Generic Formulation already evaluates mapped forms without requiring a dose; missing amount remains a Dose concern. Existing regressions verify these boundaries.

The clean-label role multipliers still feed the public assessment and must remain. The older scoring config still serves the legacy dashboard. Evidence vocabulary multipliers explicitly describe legacy v3, while v4's evidence owner applies its own accepted policy; changing those numbers to match would be an unapproved policy change. App vocabulary models parse the legacy values but no production consumer reads their multiplier.

This bounded batch removes only the unused safety/hygiene `base_max`, versions the config and its fingerprint history, and corrects module metadata that incorrectly called a rubric subtotal the production score. The public six-pillar assembler and all arithmetic remain unchanged. The same 46 actual enriched products across all five routes have exactly identical scores, pillars, tiers, assessment states and safety results. Only audit method, timestamps and provenance/version fields differ.

Release fixes measure complete sync time, make Python progress visible through log pipes, and keep optional storage inventories/deletion outside publication. Cleanup remains available through existing gated commands; it has not been performed by this audit. No pipeline or new catalog publication is authorized by these source-only checks.

Unbenchmarked probiotic CFU scoring and the D28 EGCG lower-bound proposal remain specific policy questions, not silently recalibrated under cleanup. No numerical or clinical policy changes are part of this batch. Current validation and integration evidence is recorded in the LEDGER; local detailed receipts are in `reports/enricher_config_audit_20261015/`.
