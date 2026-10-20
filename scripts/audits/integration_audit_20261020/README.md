# October 20 merged-PR integration audit

## Scope and ownership

Independent review of all 40 first-parent merged PRs between the previously qualified
`3c45aa69c` and fetched main `30a1e2f73`. The inventory is exact, not an estimate of
45 PRs. Reviewed current production owners, callers, focused tests, source receipts,
and representative frozen raw labels. Previous #175/#176 seams were also rechecked.
No claim that a code audit proves an absence of every possible bug.

Owner: `enhanced_normalizer::EnhancedDSLDNormalizer.normalize_product` and
`enrich_supplements_v3::SupplementEnricherV3._parse_allergen_statement` for clause
scope; `audit_raw_to_final::_check_line_integrity` for reconciliation, reusing
`build_final_db` canonical ledger and serving folds; `botanical_marker_contributions.json`
`botanicals/grape` and the existing marker owner for declared-resveratrol applicability;
`.github/workflows/pipeline-tests.yml` for the runner; `identity_integrity::resolve_identity`
and the existing Senactiv rule for Sean's approved bounded identity/advisory amendment. Evidence: matrix/glossary,
full source diffs, fail-first probes, raw fixtures, and [independent reviews](REVIEW.md).
Will NOT create another scorer, normalizer, identity matcher, clinical registry,
public field, status, reference exception, or hash restamp.

## Findings and fixes

1. **Allergen cross-contact laundered into Contains.** The cleaner captured beyond
   `Contains: Fish` into a following facility clause, synthesizing false Contains
   warnings as well as a parsed list. It now stops at cross-contact cues while
   preserving multiline ingredient lists, actual `made with milk`, and soybean
   declarations. The existing statement owner separately scopes inline Contains,
   May contain and facility clauses, including relative and negated production
   wording. A shared production-verb vocabulary prevents packaging/bottling drift.
   Original 230194 plus true declarations 1060/248755/222850 are frozen fixtures.
   The supplied examples were approximate: 1060 actually declares milk, soybeans
   and wheat; 248755 declares soy, with milk only a facility risk. Tests assert
   the actual raw labels, not the approximate descriptions.
2. **Raw-to-final gate skipped missing/nonnumeric amounts and app dose surfaces.**
   The existing amount blocker now catches lost/string/nonfinite quantities.
   App rows, exact/parenthetical/fallback doses, quantities/units, serving variants
   and folded components are compared to the existing exporter-owned canonical
   ledger, including legitimate folate and probiotic folds. Deletion/injection
   mutations fail. No evidence was found that the current catalog contains these
   mutations; the confirmed defect was missing validation coverage.
3. **Unsupported grape-resveratrol concentration floor.** An implementation-only
   1% floor hid positive declarations despite Sean's recorded no-arbitrary-cutoff
   advisory policy. The existing grape reference accepts any positive declared
   percentage; zero, no percentage and wrong constituents remain excluded. Grape
   identity and qualified, uncertain-human-relevance wording remain. All 15,414
   frozen raw products were scanned: zero positive sub-1% declarations, so the
   regression is proven with a source-derived synthetic boundary and real controls.
4. **CI runner drift.** Run39431996588 failed before tests because ubuntu-latest
   resolved to26.04 and exact Python3.13.3 had no matching build. Pinning24.04 keeps
   the interpreter unchanged. The official actions/python-versions manifest
   confirms its compatible build. No test or skip gate was disabled.

5. **Product-wide allergen declarations selected primary analysis rows.** The
   first replay exposed nine soy-dependent exports. Restricting the existing
   safety-export exception to row-specific findings removes the alias-dependent
   promotion. Canonical nested label rows and all structured allergens remain.
   Banned/recalled/harmful visibility is unchanged. Across all 933 re-exports,
   36 products change projection:97 unsupported primary rows leave and one existing
   zero-dose header becomes visible through the existing duplicate suppressor.
   Every retained primary analysis row keeps its identity, amount and other
   fields. Printed5g dietary fiber remains in228849's label ledger; its nutrition
   total is not promoted into analysis.259814's existing export role heuristic
   moves below six disclosed rows; its omega-3 scoring taxonomy is unchanged.
   These are cause-based owner corrections, not per-product score exceptions.
6. **Explanation ties depended on JSON object order.** Re-exporting canonical
   saved records exposed43 explanation-only differences. Ties now use the existing
   quality config's pillar order, preserving fresh runtime selection and making
   all 720 map permutations equivalent for strengths and drags. No score math or
   clinical rule changed.

7. **Senactiv brand identity lost under blend precedence.** Sean approved a bounded
   amendment after supplier and primary clinical research. Only the exact curated
   Senactiv/Seneactiv brand with both matching printed constituents can retain its
   curated identity under the proprietary-blend group. The total remains an
   unscored blend header; no constituent dose or trial credit is inferred. The
   existing advisory explicitly concerns other notoginseng preparations, with
   unknown applicability to Senactiv and no established clinical bleeding risk.
   Anonymous, incomplete and contradictory compositions remain outside the exception.
   Independent review exposed an extra nested-constituent bypass before integration;
   its regression and final review are part of the source qualification.

## Validation and measurement

Behavioral code/data/safety applicability plus CI infrastructure. Final runtime:
`ab50c2c3c4380792f2922e346fdf0ad2d27371e7`. The preceding six-fix runtime
was `5d15a3f2383af92b59995d96360f1ef961efed1c`. Fail-first regressions, focused
owner/consumer checks and independent review are complete. Owner slices overlap
and must not be summed:402identity,357initial infrastructure,58grape/marker,
230gate/allergen,43finalgate,180changedfiles,40CIharness,457export/gate and
312copy/export checks. Four tart-cherry abstracts were checked live; juice-only
credit is consistent with the represented evidence. [Reviews](REVIEW.md) describe
scope and limitations, including the initial findings and their final closure.

The six-fix measurements below qualify5d15a3f2; Senactiv is measured separately.
Raw census:15,414 frozen products,0 parse errors. Full raw replay:129initial labels,
779additional potential declaration cases and26grape/knotweed controls,
933 unique products. `freeze-raw` → `snapshot --full --blob` → `compare --all-paths`.
No scorings/status/upstream identity/clinical warning/safety/interaction changes;
no allergens lost or added.68 false Contains entries on16 products become29 May
contain and39 facility warnings. Another6 May-contain entries on3 products are
scoped correctly to their facility clauses. Source230194 keeps Fish asContains
and all six other allergens asMay contain; all three real declaration controls
retain their actual presence types.

Final raw138-label recapture includes all nine initially exposed export cases
and the original controls, against30a1e2f73. All full captures complete with
unchanged source/input bindings.0scored record/upstream identity/safety/clinical
warning/interaction changes and no lost allergens. The final-only changes after
the933raw capture are confined to `build_final_db.py`; existing Clean/Enrich/Score
records were reused for a canonical final re-export of all 933. That re-export
has36fully classified projection changes, all printed source paths and structured
allergens retained,0warning/safety changes and0raw-to-final integrity findings.
The final 138full raw replay independently exercises that six-fix source.
[Machine-readable measurements](measurement.json) retain precise results.

The approved Senactiv addition has a separate eight-label full raw replay from
5d15a3f2 to the exact runtime files committed as ab50c2c3c. All 8scores, pillars,
quality statuses and product safety statuses stay unchanged.309960/329215 retain
NHA_SENACTIV and gain the already-authored, now explicitly extrapolated advisory;
295773 changes advisory wording only. Five botanical/blend controls stay unchanged.
Two scored-record hashes change only canonical readiness identity/rationale/order,
not numerical scores or status. The runtime file hashes match the final commit;
both captures completed with unchanged source and inputs.168 owner/consumer checks,
20 independent focused tests and fresh independent clinical/source review pass.
The extra nested-member bypass was reproduced before its production-owner fix.
CI on e117f7768 correctly caught six body/note length violations in two strict
production-copy tests. The same rule was shortened without changing its clinical
meaning, sources, gates, severity or action fields; existing length limits stayed
unchanged. All79focused copy/identity checks and fresh independent review pass;
the eight-label capture was repeated on the shortened final copy, with zero raw
integrity findings and the same bounded changes. Failed CI is retained as a failed
checkpoint, never acceptance evidence.


Local rung onfc20ede1:545 passed,24 explicit live-service opt-ins,1failure against old
stored catalog folate limits (127 rows1667 vs current1700DFE). A missing canary
mount in the first attempt was corrected; all 81 missing-data skips became passes.
Current raw1060 exports1700;26 runtime folate/reference checks pass. The test is
retained, artifacts unchanged. This is a source qualification with an explicit
stale-catalog limitation, not a green release/local artifact checkpoint. The
subsequent display-only tie-order correction has named consumer/permutation
checks and final raw/re-export evidence. No broad local rerun was needed for it. After the Senactiv addition, Sean started
his own exploratory pipeline in the primary checkout and explicitly asked to
leave it running. A broad local rerun is therefore deferred under the machine
concurrency rule; current focused owner checks and whole-fast CI qualify source.
The earlier local artifact limitation remains explicit; no green release claim.

Whole-fast CI39435832646 and39436298392 both passed on six-fix runtime5d15a3f2.
The final expanded runtime ab50c2c3c passed [CI39440889610](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/39440889610):
all four groups and every declared-skip guard succeeded. This is the final source
checkpoint for authorized PR218 integration; subsequent changes are audit documentation only. Earlier9bb5fd31 CI39432504463 passed;
the intermediatefc20ede1 run was cancelled when the explanation defect needed a
fix. A cancelled or pending run is never acceptance evidence.

Durable captures and full checksum/probe receipts:
`~/pg_quality/integration_audit_20261020/`. Rejected unfinished captures are recorded
ininterrupted_capture.json: committing changedHEAD and invalidated provenance.
Qualified captures were restarted from a fixed source; no receipt was restamped.

## Remaining boundaries

- The Senactiv correction was explicitly approved by Sean after the
  [supplier and clinical research](SENACTIV_RESEARCH.md). Its limited evidence is
  retained as uncertainty in the advisory, not converted into a bleeding claim.
- The stable pre-run census found all 114 stored stage manifests stale. Sean’s
  exploratory job is now rewriting those artifacts; that moving census is not a
  final-candidate receipt. The next operator rebuild starts at
  Clean. Existing curated policy holds remain explicit. Catalog regeneration,
  publication/release gates and real app acceptance remain separate.
- Four original primary-checkout drafts, 14 submission input hashes and untracked
  research are preserved. They are not part of this public source batch.

No agent corpus pipeline, catalog upload, release, Flutter import or IPA occurred.
Sean's separate exploratory primary-checkout pipeline is not a capture of this final source;
he intends to rebuild after integration.
