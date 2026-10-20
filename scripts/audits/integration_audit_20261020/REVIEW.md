# Identity and interaction audit — 2026-10-20

Scope: read-only review of merged source diff `3c45aa69c..30a1e2f73`, focusing on identity, normalization, interactions, botanical aliases, retained nonscorable identities, nested-member preservation and standardization form context. Reviewed relevant production seams and named regression tests, plus raw-label end-to-end probes. No pipeline, release, broad suite, source edit or commit.

Owner: `scripts/identity_integrity.py::resolve_identity` for the enricher's identity decision; `scripts/identity/interaction.py::interaction_subject_refs` for authored family/twin/constituent linkage; `scripts/enrich_supplements_v3.py::_collect_interaction_profile` for rule emission. Evidence: source diff, callers, source-of-truth matrix, accepted ADR-0005, tests and probes below. Will NOT create another identity matcher or change the accepted branded-blend policy.

## Confirmed unresolved owner conflict: Senactiv advisory misses a label that explicitly names Senactiv

**Impact: under-warning, high confidence in current behavior.** `scripts/tests/fixtures/notoginseng_309960_raw.json`, `ingredientRows[8]`, prints `Senactiv`, 50 mg, with forms `Panax notoginseng` and `Rosa roxburghii`. Clean identifies `NHA_SENACTIV`; enrichment repairs it to `BLEND_GENERAL` because DSLD groups it as `Proprietary Blend`. The final interaction profile omits `RULE_OTHER_SENACTIV_ANTIPLATELET`, including its antiplatelet, bleeding-disorder and surgery cautions. No ingredient in that probe emits the Senactiv/notoginseng rule.

Reproduced using the repository Python environment, `EnhancedDSLDNormalizer().normalize_product(raw)` then `SupplementEnricherV3().enrich_product(cleaned)`. Result:

```text
raw_source_path: ingredientRows[8]
raw_source_text: Senactiv
canonical_id_before: NHA_SENACTIV
canonical_id: BLEND_GENERAL
identity_disposition: repaired
skip_reason: blend_header_total_weight_only
rationale: Unambiguous structured line identity replaced the supplied canonical ID 'NHA_SENACTIV' with 'BLEND_GENERAL'.
rule_ids: RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS,
          RULE_IQM_L_TYROSINE_THYROID,
          RULE_IQM_POTASSIUM_HYPERTENSION, RULE_IQM_SODIUM
```

Relevant owners:

- `scripts/identity_integrity.py:985`: the label-over-group exception explicitly excludes `BLEND_GENERAL`, and `CanonicalIdentityRegistry.is_role_record` treats other-ingredient-only records as role records.
- `scripts/data/other_ingredients.json:17067`: `NHA_SENACTIV`, an existing branded-complex owner, explicitly says it is not treated as a product-level proprietary blend container by default.
- `scripts/data/ingredient_interaction_rules.json:23961`: the new rule explicitly targets that owner.
- `docs/adr/0005-one-ingredient-identity-owner.md`: accepted decision 2 explicitly lets the group decide when either side is the general blend owner, using TamaFlex as its example.
- `scripts/tests/test_panax_notoginseng_identity.py`: checks both Senactiv labels are not ginseng, but checks positive Senactiv advisory emission only for 295773/Seneactiv. It therefore passes while 309960 misses the new advisory.
- `reports/panax_notoginseng_identity_20261020/README.md`: already acknowledges 309960 and 329215 as `For Sean` after the independent audit.

This is a confirmed unresolved product gap and a policy/owner inconsistency, not a newly introduced coding regression that can safely be fixed by silently changing identity precedence. The accepted ADR and current code intentionally choose BLEND_GENERAL. A second raw-name match solely for interaction lookup is not the #203/#217 mechanism: those mechanisms use the identity already retained by `resolve_identity`. `_blend_header_scope_row` only enriches forms when its match canonical equals the existing header canonical. Additional subject links are authored botanical twins/constituents or separately grounded banned/recalled safety flags. A new generic branded-blend relationship or exception requires the explicit owner decision described by AGENTS.md. No edit made.

## Generic omega-3 identity: bounded reproduced limitation

`scripts/tests/fixtures/q35_323711_raw.json` has `ingredientRows[7]` named `Omega-3 Fatty Acids`, 330 mg, with a `Docosahexaenoic Acid` form. It enriches to `fish_oil`, marked clean, and emits `RULE_INGREDIENT_FISH_OIL`. The fixture says vegan capsule, but contains no algal/Schizochytrium literal anywhere. Thus this probe establishes the generic-total assumption, **not independently verified algal provenance**.

`scripts/enrich_supplements_v3.py::_is_generic_unspecified_omega3` explicitly documents generic totals as the conservative `fish_oil (unspecified)` compatibility bucket, avoiding a fabricated minor omega-3 fatty acid. The match path forces fish_oil before form matching and the identity resolver callback also returns fish_oil for this case. `reports/omega3_oil_family_20261020/README.md` acknowledges this remaining class. The merged oil-family changes correctly preserve explicitly named algal/krill identity and add shared advisories; removing the generic compatibility mapping requires the actual source-grounded raw cohort and its existing owner policy. No unsupported algal identity inferred and no edit made.

## Verification and coverage

Named fast test invocation 1: identity integrity, label-named-over-group, nonscorable keeps, interaction blend headers, species-swap aliases, binomial forms, notoginseng, oil family and native strain provenance: **302 passed in 43.13 s**.

Named fast test invocation 2: nested blend members, nutrition-fact nutrient roles, label-first standardization notes, standardization wordings, green-tea EGCG contains relation, star-anise separation, tart-cherry canonical equivalence and interaction-rule source corrections: **100 passed in 30.48 s**.

Both used `scripts/test.sh fast` with explicit file paths. No broad collection invocation. The shared worktree had the integrator's in-progress cleaner/allergen changes; these results cover that working copy during the audit, not an immutable clean SHA receipt.

Additional reviewed safeguards: label-named identities cannot lose group-carried rules without a reviewed linkage; retained nonscorable identities are hidden from scoring through the shared score-eligible view; blend-header amounts are cleared for threshold evaluation; declared markers from headers carry unknown amount; nested rescued members do not borrow an ancestor's undisclosed total; enzyme source organisms remain provenance unless live/CFU context contradicts that treatment; botanical species restatements consult the canonical parent's recorded Latin names and identity aliases; renamed aliases retain species/preparation separation.

No additional confirmed regression found in these reviewed seams. This is not exhaustive corpus or clinical-source certification. I did not rerun all topic-specific replay cohorts, full stages, CI or release, inspect every exported catalog/app row, or independently re-fetch every changed clinical citation/identifier. Existing research receipts were inspected as historical supporting evidence; no claim that their current APIs were reverified here.


---

# Scoring/evidence audit — 2026-10-20

Reviewed merged candidate 30a1e2f73 against 3c45aa69c in `/Users/seancheick/.codex/worktrees/pipeline-integration-audit/dsld_clean`. No broad suite or pipeline run. The parent integrator subsequently authorized the narrow confirmed defect fix below; changes remain uncommitted. Other agents' edits were preserved.

## Confirmed finding F1 — declared grape resveratrol silently lost below 1% (P2)

Owner: `scripts/enrich_supplements_v3.py::_compute_delivers_markers` and `scripts/data/botanical_marker_contributions.json::botanicals/grape` — evidence: `rg 'min_standardization_pct_required|declared_standardization_pct' scripts/enrich_supplements_v3.py`, marker data, source-of-truth matrix/glossary inspection, callers `_derived_marker_interaction_rows`, existing `test_grape_resveratrol_marker.py`.
Will NOT create: a new clinical rule, registry, field, status, warning copy, or scorer.

The #199 implementation required grape's explicitly declared resveratrol concentration to be at least 1%. A 1,000 mg grape extract declaring 0.5% trans-resveratrol (5 mg) emitted no marker and no resveratrol advisory, while real BioVin's 60 mg at 5% (3 mg) did. This conflicts with the quoted Sean instruction in `reports/grape_resveratrol_marker_20261019/README.md`: a qualified advisory for explicit declarations, no arbitrary cutoff. The current ADR's implementation prose described the floor, but did not establish clinical evidence for it. Commit eb1763073 deliberately pinned the sub-1% suppression during re-audit; that is its origin, not threshold evidence.

Direct old-owner probe: `(quantity=1000, notes='0.5% trans-resveratrol') => markers=[], derived interaction rows=[]`; `(quantity=60, notes='5% trans-resveratrol') => 3mg resveratrol interaction row`. Unknown mass also loses the 0.5% declaration. Knotweed's separate source relationship rescues its advisory; its scoring concentration gate was left unchanged.

Fix: grape's existing concentration field 1.0 -> 0.0. The marker owner already supports this and the interaction-row owner requires positive quantity or a truthy declaration. Existing schema test now permits a nonnegative concentration threshold, preserving required numeric configuration and citation guards. Tests cover known/unknown parent mass, zero percent, no percentage, wrong constituent, and full Clean/Enrich warning propagation. ADR implementation wording and #199 receipt updated. No production Python changes.

Sources read live on 2026-10-20:
- [MSK Resveratrol](https://www.mskcc.org/cancer-care/integrative-medicine/herbs/resveratrol): antiplatelet interaction section describes laboratory platelet findings, unknown clinical relevance and discussing use with the physician. No concentration threshold.
- [PMID 12926863](https://pubmed.ncbi.nlm.nih.gov/12926863/): HPLC measurement of trans-resveratrol in grape/wine/byproducts establishes constituent identity, not a human interaction threshold. Automated content verifier returns PARTIAL, 0 mismatch, 0 unresolved, one live request. Receipt `grape_citations.json`.

Validation class: behavioral data/safety applicability. Required combined local/whole-fast CI checkpoint belongs to integrator and remains outstanding for the completed combined batch.

Fail-first: `scripts/test.sh fast scripts/tests/test_grape_resveratrol_marker.py::test_any_positive_declared_resveratrol_percentage_reaches_the_presence_advisory` => 2 failures (missing markers) before correction.

After correction: named grape/marker test files pass (final count recorded below); end-to-end additional test passes. `data_batch.py check ... --since HEAD --expect botanicals/grape` => 1 changed entry, 0 problems. `git diff --check` passed. Interaction citation verifier checks zero rules because interaction-rule data is unchanged; it is not clinical verification of the entire registry.

Bounded before/after runtime probe (same raw fixture, in-memory original/corrected grape reference only), saved in `grape_bounded_probe.json`:

| Case | Old/new resveratrol alerts | Quality old/new | Safety old/new |
|---|---|---|---|
| Actual BioVin 269265 | 1 / 1 | 56.1 / 56.1 | no_known_catalog_concern / same |
| Synthetic same label, 1,000mg @0.5% | 0 / 1 | 56.1 / 56.1 | no_known_catalog_concern / same |
| Synthetic zero percent | 0 / 0 | 56.1 / 56.1 | no_known_catalog_concern / same |
| Synthetic bare keyword, no percentage | 0 / 0 | 56.1 / 56.1 | no_known_catalog_concern / same |

This proves the shared cause and real-label control, not a corpus incidence count or release validation. Existing artifacts need regeneration at the integrator's candidate checkpoint. The historical 1,478-label replay receipt reports zero sub-1% cohort cases, but that count was not independently re-established here.

## Four tart cherry citations — verified by content

- [22038497](https://pubmed.ncbi.nlm.nih.gov/22038497/): 20 volunteers, randomized double-blind placebo-controlled crossover, juice concentrate for seven days; increased urinary melatonin, total sleep time and sleep efficiency. Supports the updated juice scope.
- [35790450](https://pubmed.ncbi.nlm.nih.gov/35790450/): 44 participants with sleep records; juice or powdered capsules for 30 days; no between-group sleep benefit or BP benefit. Does not establish powder efficacy. Abstract mentions within-capsule-group body-mass changes; the record's broad body-composition shorthand should not be used to assert every measured body endpoint was unchanged.
- [33440334](https://pubmed.ncbi.nlm.nih.gov/33440334/): 14-study recovery meta-analysis, small soreness and moderate strength/power recovery effects. Correctly replaces the former wrong recovery characterization of 35790450. Its abstract does not establish preparation equivalence.
- [40964149](https://pubmed.ncbi.nlm.nih.gov/40964149/): seven interventional studies in a sleep systematic review; limited, heterogeneous evidence. Correctly graded systematic review.

22038497 and 40964149 PubMed browser pages failed to expose abstracts; live Europe PMC core API retrieval returned the corresponding PubMed records, retained in `tart_cherry_sources.json`. 33440334/35790450 were read on live PubMed pages. No independent UNII/UMLS/chemical identity API re-verification; the claim checked here is trial form/population/outcome applicability. No claim that all dry-preparation trials have been exhaustively reviewed. Retaining a conservative unresolved powder/extract applicability is supported by the evidence actually represented; it is not proof powders never work.

## Other reviewed owners and test coverage

Read relevant merged diffs/current callers for multi/prenatal material-role formulation, vitamin A provitamin/label declaration roles, generic B2 contradiction/severity, scoring-eligible identity projection, scoped probiotic source-owner memo, protein taxonomy, and retired constant scoring metadata. No additional confirmed correctness regression from these changes in this slice.

- Six named files: tart cherry one-brain/literature/clinical record, multi-prenatal formulation, role classification, native clinical strain provenance: **172 passed**.
- Four named files: protein powder typing, free-from rule, grape resveratrol, interaction rule source corrections: **94 passed** on original audit candidate.
- Final changed grape/marker slice: see final appended receipt; includes real BioVin/knotweed controls and new low-percentage cases.

Limits: not a full clinical registry audit; no broad scoring corpus, final pipeline, app runtime, release or current whole-fast CI validation. Exact-output artifacts from older fingerprints do not establish the corrected candidate. All four tart cherry abstracts verified; recovery meta-analysis full text not reviewed. Other lanes own broader allergen parsing/identity/raw reconciliation findings and merged validation. Parent integrator should update shared LEDGER/handoff once this batch is combined.

Final changed-slice receipt: `scripts/test.sh fast scripts/tests/test_grape_resveratrol_marker.py scripts/tests/test_botanical_marker_contributions.py` => **58 passed in 5.66s**. No skips. This includes the full normalization/enrichment low-concentration warning regression.


---

# Infrastructure / export independent audit — 2026-10-20

Candidate inspected: `3c45aa69c..30a1e2f73`, in `/Users/seancheick/.codex/worktrees/pipeline-integration-audit/dsld_clean`. No corpus pipeline, catalog build, release or publication ran.

## Confirmed finding, fixed locally pending integration

**P2: Raw-to-final dose gate accepted lost/non-numeric analysis quantities and did not inspect the app dose surface.**

Owner: `scripts/audit_raw_to_final.py::_check_line_integrity` — evidence: direct call with a raw Magnesium 100 mg row and an otherwise reconciled ledger. Exported quantity `None` or string `"999"` yielded `[]`; numeric `999` yielded `AMOUNT_CHANGE_WITHOUT_EVIDENCE`. The `isinstance(amount, (int, float))` precondition skipped precisely the malformed/missing values it needed to reject.

The same owner iterated only `blob.ingredients` for dose checks. `build_final_db.py::_build_canonical_label_ledger` preserves source `exact_dose_text` and `serving_variants` for `display_ingredients`; Flutter `lib/features/product_detail/label_ingredient_presenter.dart::_doseLabelFor` prefers exact dose text, and `ingredients_section.dart` reads serving variants. Changing only the app's exact dose from 50 mg to 500 mg, or removing/changing its serving variant doses, produced no findings. This is a gate coverage defect; no assertion that today's generated catalog contains these corruptions.

Fail-first evidence: three failing cases (missing quantity, string quantity, changed exact dose) followed by two failing serving-variant cases. Controls for non-finite numeric quantities already passed and remain guarded.

Local fix: remove the exported-numeric skip; reconstruct the expected app ledger through the existing exporter canonicalization and serving-fold helpers, compare nonempty exact doses and serving variants, and require each expected app row. Reuse existing `AMOUNT_CHANGE_WITHOUT_EVIDENCE` and retain raw row, field and source/exported values. Empty source exact text may still receive the exporter's documented analysis fallback. Cleaner-reviewed corrections remain valid because the app fields compare with the existing cleaned display owner, while numeric analysis quantities retain selected-column / source-correction / DV allowances.

Will NOT create: new field, registry, semantic owner, policy or status. Only production file changed by this reviewer: `scripts/audit_raw_to_final.py`; only test file: `scripts/tests/test_audit_raw_to_final_reconciliation.py`. No commit created.

## Verification

Initial named-file slice on merged candidate: **357 passed, 57.48 seconds**:

```
scripts/test.sh fast scripts/tests/test_audit_raw_to_final_reconciliation.py scripts/tests/test_clean_fail_closed.py scripts/tests/test_enrich_fail_closed_handlers.py scripts/tests/test_reference_loaders_fail_closed.py scripts/tests/test_preflight_fail_closed.py scripts/tests/test_release_artifact_promotion.py scripts/tests/test_batch_run_all_datasets.py scripts/tests/test_rebuild_dashboard_snapshot_order.py scripts/tests/test_standardization_note_label_first_20261020.py scripts/tests/test_standardization_note_wordings_20261020.py scripts/tests/test_cleaner_dead_outputs_removed.py scripts/tests/test_native_clinical_strain_provenance.py
```

After fixes: **36 passed, 0.60 seconds**, `scripts/test.sh fast scripts/tests/test_audit_raw_to_final_reconciliation.py`. `git diff --check` passed. These are focused checks, not the broad fast rung or release validation. Other agents are editing other files concurrently; final candidate CI/local checks belong to integrator.

## Inspected coverage and limits

Reviewed infrastructure/existing consumer changes across #176/#178/#180/#183/#184/#190/#191/#201/#208 and adjacent #179 performance: raw availability/preflight and snapshot ordering; raw label catalog input binding; raw-path/identity/amount reconciliation; fail-closed Clean state/report writes, Enrich handlers and contract K.1; shared unit-conversion/UNII loader initialization and shape checks; removed dead outputs/arguments/counters; label-first standardization claims and parent percentage guard; bounded pure-string caches and per-pass probiotic views. Existing named tests cover malformed/missing references, failure propagation, submission identity buckets, empty target arguments, raw content fingerprint changes, snapshot gate placement, standardization wordings and parent-share mismatch, dead output removal, and activeIngredients-only probiotic ownership.

No additional confirmed runtime regression was established in those infrastructure changes. This does not prove corpus parity, clinical correctness, release readiness, actual performance at corpus scale, or real app rendering. No live clinical-source audit was part of this infrastructure lane. The gate's app-dose extension compares the cleaner's existing display contract; it does not independently reimplement label-dose formatting or introduce a second dose owner.


## Follow-up stabilization and allergen parser assignment

Integrator review identified that checking only existing app rows would miss deletion and that raw cleaned display rows can legitimately fold (folate; alternate probiotic/general servings). The gate now calls the existing exporter helpers `_reconcile_display_source_rows`, `_build_canonical_label_ledger`, `_fold_probiotic_serving_headers`, `_fold_general_serving_variants` on a deep copy. It checks expected canonical paths exist and compares expected exact doses/serving variants. A folate parent/child fold control passes; no second folding owner was introduced. Current gate test file: 38 cases (included in the 154-pass combined check below).

Additional assigned owner: `scripts/enrich_supplements_v3.py::_parse_allergen_statement`; existing tests `scripts/tests/test_allergen_statement_audit_188.py`. Confirmed mixed inline lists incorrectly promoted cross-contact into `contains`: `Contains milk and may contain soy`; `Manufactured in a facility that contains milk and soy`; `Contains Fish Processed in a facility that also processes milk and soy`. Four new tests failed before the first fix (the punctuation-separated control already passed).

A first regex splitter caused a regression for OLLY 293779's `Processed in a facility with products that may contain, soy...`. A direct baseline AST probe confirmed baseline B2 -1.5 versus first fix -2.0, so no stale fixture was changed. Review added fail-first cases for dedicated facility followed by independent `contains`, double-spaced `not manufactured`, `packaged in a facility`, and relative `products that may contain`. All four failed against the first fix. The final owner now scans independent cue starts, preserving relative/negated cue attachment, then uses the existing recursive clause parser; facility-relative `contains` never becomes a product declaration. Existing multiline-list handling remains.

Combined gate plus four allergen owner/consumer files: 154 passed in 15.64s before the final scanner refinement. Final five-file allergen slice is recorded in the handoff message once complete. Changes are uncommitted; no pipeline/build/release was run.

Final scanner check: `scripts/test.sh fast scripts/tests/test_allergen_statement_audit_188.py scripts/tests/test_allergen_statement_phrasings.py scripts/tests/test_allergen_species_phrases.py scripts/tests/test_gluten_claim_cross_contact.py scripts/tests/test_free_from_claim_rule.py` — **177 passed in 23.21s**. `git diff --check` clean. Source stable for integrator replay/CI.

## Final review closure

Reviewer mutation probes identified two remaining app dose representations: `parenthetical_dose_text` and `folded_label_components`. Both now compare with the same canonical expected ledger; direct amount mutation regressions fail before the fix. App fallback dose fields (`display_dose_label`, `quantity`, `unit`) are compared too, including unsupported field injection when canonical data has no such amount. Existing legitimate folate fold remains green.

Production cue vocabulary is now one private `_STATEMENT_PRODUCTION_VERBS` used by line boundaries, inline boundaries and negation. It includes manufactured/produced/processed/made/packaged/bottled, with both not and never. Parameterized known-class probes covered all 12 negator/verb combinations plus the positive bottled facility control. Final fail-first slice: 11 failed, 4 passed. After fixes the six-file reconciliation/allergen consumer slice passed **230 tests in 22.06s**; final gate-only check including fallback injection cases passed **43 tests**. Source is frozen for integrator measurement/CI; no commit or pipeline run was performed by this reviewer.

## CI runtime availability repair

Run 39431996588 failed before tests at setup-python after `ubuntu-latest` moved to Ubuntu 26.04. The project still correctly requests exact Python 3.13.3 through `.python-version`. Current primary [actions/python-versions manifest](https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json), checked 2026-10-20, lists `python-3.13.3-linux-24.04-x64.tar.gz` under release `3.13.3-14344076652`; its 3.13.3 file list includes no Ubuntu 26.04 build. Pinned `.github/workflows/pipeline-tests.yml::jobs.fast.runs-on` to `ubuntu-24.04`, leaving interpreter, test shards and skip/artifact enforcement unchanged.

Fail-first existing-harness regression: `scripts/tests/test_ci_skip_guard.py::test_fast_workflow_pins_runner_compatible_with_project_python` failed with actual `ubuntu-latest`. After fix, `scripts/test.sh fast scripts/tests/test_ci_skip_guard.py` — **40 passed in 0.55s**. `git diff --check` clean. Infrastructure-only change; no runtime pipeline code/data changed for this CI repair. Remote CI rerun remains the integrator's required confirmation; no commit made by reviewer.

## Nine-product replay side effects — read-only causal investigation

IDs: 2512, 25624, 25694, 27807, 31063, 63923, 64382, 64387, 801. Every added legacy blob ingredient is a soy-bearing nested member. Candidate allergen provenance is product-wide `source=label_parsed`, `presence_type=contains`, `matched_text=soy` (`Contains: Soy`), while baseline text used other wordings that did not match nested soy names.

Observed call chain: `build_detail_blob` builds `allergen_patterns`; `_active_row_allowed_for_primary_export` reaches `_active_row_has_explicit_safety_export_signal`; `matching_allergen_hits` phrase matching provides a safety exception to the strict primary contract. That adds legacy analysis rows despite unchanged scored and IQD input. `_build_canonical_label_ledger` fills previously empty source `exact_dose_text` with the analysis `display_dose_label`, here `Amount not disclosed`; `label_record_contract.formula_fingerprint` hashes that display text. No measured/known amount changed. Product 2512's existing IQD decision is already `BLEND_GENERAL` with repaired identity, `inactive_non_scorable`, `blend_header_total`; the cleaner display identity is `isoflavones`. The newly selected analysis row changes row_ledger projection, rather than a new upstream identity decision.

Controlled direct-function probe: load frozen candidate enriched/scored records, replace ONLY candidate `allergen_hits` with frozen baseline `allergen_hits`, then call `build_detail_blob` on deep copies. For all nine products this restores baseline legacy ingredient count and leaves **zero non-allergen blob difference paths**. Counts candidate→baseline/swapped: 2512 2→1; 25624 14→10; 25694 13→9; 27807 46→45; 31063 45→44; 63923 10→9; 64382 2→1; 64387 3→2; 801 43→42. This rules out process seed/shared mutation/source drift as the cause of these nine changes. No pipeline, snapshots or replay captures were modified.

Proposed mechanical correction sent to integrator: restrict the allergen safety-export exception to existing row-specific ingredient provenance, retaining explicit bans/harmful additives, structured allergens and full nested label ledger. Product-wide parsed/statement declarations should not choose a primary analysis projection or formula fingerprint. Awaiting lane coordination; no source edit in this read-only investigation yet.

## Export projection owner correction applied

Integrator authorized the bounded mechanical correction. Owner: `scripts/build_final_db.py::_active_row_has_explicit_safety_export_signal`. Generic product allergen declarations no longer supply the strict-primary-export bypass. Existing matching findings must carry the same `raw_source_path`, or `presence_type=ingredient_list` with an exact ingredient-name match. Banned/recalled identifiers, explicit ingredient safety flags, contaminant and harmful-additive branches remain. No public field, policy or registry added. Existing `matching_allergen_hits` still owns label matching; this correction constrains the kind of provenance that can select a primary analysis row.

Fail-first existing-test regression: three product-wide Soy declaration cases (contains/may-contain/facility) failed; 11 controls passed. After owner fix, 457 tests passed in 10.32s across existing `test_nonscorable_label_active_ships.py`, `test_export_gate.py`, `test_build_final_db.py`, and `test_audit_raw_to_final_reconciliation.py`. Controls preserve direct ingredient-specific allergen evidence, same-source-row evidence, banned/recalled and harmful row visibility.

Controlled nine-product current export probe: baseline-versus-candidate `allergen_hits` substitution now leaves **zero non-allergen differences for all nine IDs**. All corrected candidate structured allergen arrays and every canonical display source path remain. Seven products exactly regain frozen baseline non-allergen output/fingerprint. Products 25624 and 25694 each additionally lose four legacy Milk Protein isolate analysis rows that baseline had promoted through its generic Milk declaration; these remain in the canonical nested label ledger. Their fingerprint movement is explained by removing the same pre-existing declaration-driven `Amount not disclosed` fallback. Preserving those stale legacy rows would retain the root defect. No actual ingredient dose was gained/lost: every changed dose string was empty versus generic unknown wording, while corrected allergen facts remain.

Machine-readable controlled probe: `/Users/seancheick/pg_quality/integration_audit_20261020/export_soy_projection_owner_probe.json`. No frozen captures were changed. Source is ready for integrator's bounded recapture of nine affected products and controls; final CI must cover this new exporter source.

## All 79 direct-export changes classified

Read-only current exporter re-evaluation aligned legacy ingredients by `raw_source_path`, avoiding false quantity/identity diffs from shifted array positions. Detailed receipt: `/Users/seancheick/pg_quality/integration_audit_20261020/export_all_933_projection_classification.json`; raw full positional differences: `export_all_933_changed_paths.json` in that directory.

- **43 products:** only score-explanation tie selection/order changed when persisted scored-map keys were sorted. Same pillar scores and reasons, but stable sorting by gap inherited dictionary insertion order and selected a different third item. Confirmed 1060's third drag verification versus safety_hygiene. Fixed the existing `_build_v4_score_explanation` sort to use the existing quality-score config pillar order as the tie break. This preserves fresh runtime assembly behavior; no score or warning changes. Fail-first full-credit and below-credit map permutation cases failed; all 720 permutations per case now agree. Existing copy honesty/consumer + export checks: **312 passed in 10.22s**.
- **36 products:** strict-primary projection corrected. Removed 97 legacy rows; 96 are nested rows/forms, and one is 259814's top structural total `ingredientRows[4]` (2020 mg Fish Oil/Krill Blend, IQD `blend_header_total`/`inactive_non_scorable`, not an individual dose). **Every retained legacy row is byte-equivalent by source path: zero retained analysis field changes.** Full canonical display source paths, structured allergens and warning/safety results remain retained (the original all-933 receipt proves these checks).
- Dose copy changes are exhaustive: 89 `Amount not disclosed` → empty; one empty → em dash; one em dash → empty. No known printed quantity changed. Those fallback strings account for 32 label formula fingerprint changes. The canonical display changes also remove 89 namespaced analysis objects; five unresolved canonical IDs change empty string → null. Two row-ledger identities revert from analysis to the preserved printed source (`BLEND_GENERAL` → `isoflavones` at 2512; `lecithin` → `PII_LECITHIN_SOY` at 31062). A single display identity state repaired → clean and a form state assessed → listed_not_assessed follow removal of legacy analysis; no upstream IQD identity changed.
- **228849:** same legacy count hides one expected projection swap. Nested `ingredientRows[4].nestedRows[0]` Dietary Fiber 5 g is IQD `excluded_nutrition_fact`/`inactive_non_scorable`; removing its generic-allergen bypass unmasks an already-allowed zero-dose Fiber Blend (`ingredientRows[10]`, IQD `blend_header_total`, 0 NP) because existing `_suppress_zero_dose_duplicate_active_rows` no longer sees a positive same-canonical legacy row. Potassium's 40 mg row remains identical. All label paths/printed amounts remain in the canonical display ledger. The added row was not newly admitted by the correction; it stopped being suppressed by the existing duplicate owner.
- **259814:** export `product_role` general_multi → targeted_gap_filler is the existing `_classify_product_role`/`_has_multivitamin_shape` six-disclosed-row heuristic falling below six after removing the above 2020 mg structural total and 400 mg phosphatidylcholine additive legacy projections. IQD still has choline, krill oil, EPA, DHA as its four scorable rows; upstream taxonomy remains omega_3. No scoring/clinical role policy was changed; the role remains the existing export classification. Preserving general_multi would preserve the false count caused by the removed bypass.

There are no unexplained paths among these 79 products after the tie-order repair. No products/dist symlink effect was found: all retained per-source analysis objects match, and observed changes resolve to the above explicit owners. Final exporter source includes the tie-order repair and therefore needs the integrator's final bounded source-qualified measurement/CI rather than reusing an older source receipt.


---

# Evidence/provenance closeout review — 2026-10-20

Reviewed `scripts/audits/integration_audit_20261020/README.md`, its `measurement.json`, and external capture/projection receipts. Read-only; no source, docs, captures or pipeline execution changed.

## Findings requiring the planned final metadata update

1. The six-root measurement claims are consistent with receipts: 933 unique raw replay products; final 138 full raw capture at 5d15a3f2 with source_unchanged=true and exit=0; all-933 final direct exporter receipt has head 5d15a3f2, source_unchanged=true, 36 projection changes, no warning/safety changes and no `_check_line_integrity` findings. The all-79 classification agrees with the README: 43 explanation-order-only cases and 36 strict-primary projection corrections, 97 removed legacy rows plus one existing zero-dose header unmasked. Retained source-path analysis objects are identical. No correction to these counts is needed.
2. `measurement.json.final_ci_status` still says `in_progress` for 39435832646. Parent reports both 39435832646 and 39436298392 succeeded; update the saved status/link together with the final integration record. No rerun was performed by this reviewer.
3. The README now includes the approved Senactiv amendment as finding 7, while final_runtime_sha and the zero-identity/zero-interaction measurement block still describe the six-root 5d15a3f2 candidate. This is expected during the ongoing closeout, but final prose must explicitly scope the zero-change/933+138 receipts to that earlier candidate and report the Senactiv amendment's own final SHA/source-qualified measurements separately. Do not relabel the older 933/138 receipts as proving a later runtime without verified source equivalence. The parent has already identified this pending work.
4. “0 raw-to-final integrity findings” is accurate for the direct `_check_line_integrity` function probe of all 933; it is not evidence of a complete catalog/release gate run. The README's explicit no-catalog/no-release boundary keeps this appropriately bounded. Preserve that boundary.

No additional evidence inaccuracies were confirmed in this review. The raw-label, source and projection claims do not imply a qualified catalog release; the one stale-catalog local failure is explicitly and correctly retained.

## Safe cleanup candidates, after parent closeout

Do not delete current qualified 933 captures (`qualified_main`, `qualified_extra`, `qualified_grape`), their baseline captures (`base`, `extra_base`, `grape_base`), final qualified 138 and its `export_base`, raw manifests/frozen labels, checksum metadata, comparison/projection reports, primary_preservation, or Senactiv evidence.

Confirmed incomplete/rejected outputs safe to remove while retaining compact receipts:

- `extra_cand.jsonl.records/` — 23 MiB, only 159 records against expected 779, no completed snapshot metadata; retain `extra_cand.log` and `interrupted_capture.json`.
- `final_cand.jsonl` and `final_cand.jsonl.records/` — approximately 21 MiB total; metadata explicitly has source_unchanged=false. Retain `final_cand.jsonl.meta.json`, `final_cand.log` and `interrupted_capture.json` to document rejection.

These two removals recover approximately 44 MiB. No files were removed. Other completed snapshots such as `cand` and `export_final` are superseded but contain distinct historical outputs; do not describe them as proven duplicates or remove automatically without a separately recorded retention decision. `base_wt`/`candidate_wt` are source checkouts rather than capture data and should be cleaned with the integrator's worktree lifecycle after no live job uses them.


---

# Independent Senactiv review — 2026-10-20

Scope: current uncommitted `identity_integrity.py` Senactiv exception, only Senactiv interaction-rule changes, ADR0005 bounded amendment, and notoginseng tests. Reviewed against Sean's approved bounded scope, not a generic branded-complex policy. No edits or commits by reviewer.

## Initial blocking finding (P2): nested contradictory members bypass the guard

`identity_integrity.resolve_identity::reviewed_senactiv_header` compares only `form_evidence` to the two required strings. A raw Senactiv header can retain those two forms while also printing an additional ingredient in `nestedRows`. On real309960, append nestedRows[0] Caffeine (name/category/group, no quantity), leave exact Senactiv name and its two original forms. Current runtime retains headerNHA_SENACTIV and the qualified Senactiv advisory while separately exposing the caffeine child. This violates the approved ADR statement 'with no other constituent'. Probe ran complete current normalize/enrich, no output artifacts written. Reported to integrator; identity agent owns failing regression and correction.

The initial named notoginseng slice passed18 tests, demonstrating why an additional contradictory nested-member negative is required. Existing negatives only mutate the forms list.

Nonblocking documentation correction: the test docstring calling Senactiv 'the material of PMID33370633' incorrectly equates branded mixture with another PNS preparation. It should describe extrapolation, consistent with the new honest clinical copy.

## Clinical source assessment

Read external `senactiv_research.md` then independently retrieved all four actual rule PMIDs by live EuropePMC core API on2026-10-20. Exact returned records/abstracts retained in `senactiv_review_primary.json`.

- [33370633](https://pubmed.ncbi.nlm.nih.gov/33370633/): randomized assessor-blinded42-person stableCHD/chronic-gastritis study, PNS+aspirin versus aspirin for2months. Platelet inhibition endpoints, no identified Senactiv mixture or Senactiv clinical bleeding estimate.
- [31471773](https://pubmed.ncbi.nlm.nih.gov/31471773/): clopidogrel/TCM interaction review. Not a Senactiv interaction trial.
- [39364700](https://pubmed.ncbi.nlm.nih.gov/39364700/):57-year-old woman after five notoginseng capsules; temporal hematoma case, no Senactiv identification.
- [34307625](https://pubmed.ncbi.nlm.nih.gov/34307625/):60-year-old man after homemade hirudin+notoginseng capsules; confounded preparation, not a Senactiv-alone causal risk estimate.

Current proposed Senactiv mechanism/alert/body/action appropriately distinguish other notoginseng preparations, unknown applicability to Senactiv and unestablished clinical bleeding risk. Existing monitor/limited profile gates remain bleeding-disorder/surgery/antiplatelet-targeted. No clinical stop-use interval, anticoagulant expansion, drug dose adjustment or constituent-dose inference added. No source provides a threshold or50mg Senactiv bleeding estimate, and none is asserted. Supplier identity evidence is separate from clinical preparation applicability. The unchanged generic notoginseng rule was not re-audited beyond these cited source facts.

## Guard and scoring review

The intended guard uses exact curated standard brand name plus curated Seneactiv spelling, same existing canonical NHA_SENACTIV, unscored blend-total role, general-blend taxonomy, and both exact printed forms. Near names/incomplete/extra/mismatched forms are denied. It does not add registry fields, a second safety raw-name matcher, or a constituent dose. The identified nested-member hole must close before approval. Identity agent's eight-raw replay owns the final observed score/quality/safety changes; a green unit slice alone does not prove those unchanged.

Final disposition pending fresh review of the nested-member guard correction and regression results.

## Fresh review after correction — approved within bounded scope

Reviewed final internal `nested_member_names` parameter and the skipped-header caller's production plumbing. The caller reads the existing printed label-source ledger by the exact header source-path prefix; all deeper descendants are included, so a contradictory nested member cannot disappear when the cleaner flattens its active rows. The guard allows only names from the exact two required constituents; their presence in separate agreeing nested rows is allowed, while any extra/unknown/empty nested name fails the exception. No new persisted/public field or registry is introduced. Anonymous/near-brand/incomplete/mismatched/extra-form controls remain denied. The false trial-material docstring is corrected.

Fresh reviewer execution: `scripts/test.sh fast scripts/tests/test_panax_notoginseng_identity.py` — **20 passed in4.32s**, no skips. Includes failing-then-fixed nested-extra negative, agreeing nested-member positive, three real raw labels, score-exclusion assertions and clinical-copy applicability assertions. `git diff --check` passed.

**Disposition: no remaining actionable finding in the reviewed bounded Senactiv diff.** F1 is fixed. Approval is for code/source correctness within Sean's explicit amendment; integrator still owns exact-source CI/local checkpoint and identity agent's eight-raw before/after receipt. No pipeline/release approval implied.

## Follow-up: copy length repair after strict-validator failure

Independently reviewed shortened bodies/notes only. The three bodies preserve the other-preparation boundary, explicitly unknown applicability to Senactiv, unestablished bleeding risk and the matching bleeding-disorder/antiplatelet/surgical-team action. The notes preserve both applicability and risk uncertainty. The full mechanism, action fields, severity/evidence levels, profile gates, sources and thresholds are unchanged. No dose, scoring credit or stop-use period added. Body lengths184/182/194 and note length105 meet existing200/120 limits. The tests now assert equivalent shorter uncertainty wording plus the unchanged limits; no validator was weakened.

Fresh focused regression `scripts/test.sh fast scripts/tests/test_panax_notoginseng_identity.py::test_senactiv_advisory_discloses_preparation_extrapolation` — **1 passed in0.09s**. Parsed before/after comparison found only RULE_OTHER_SENACTIV_ANTIPLATELET changed, and only alert_body/informational_note within its three affected subrules. `git diff --check` passed. **Approved the bounded copy length repair; no actionable finding.** The integrator owns final combined CI; this focused pass does not substitute for it.
