# Condition-scope rule — October 28, 2026

## Candidate and scope

Behavioral scoring change. Codex continued PR280's existing branch after Sean authorized takeover;
root owns integration, the shared LEDGER and master plan. This report replaces obsolete pre-integration
measurements; historical captures remain under `~/pg_quality/condition_scope_20261028/`.

Baseline: integrated main `e923cb2337858f2eceee748704be3136cfe819eb` (#273, #277 and #274).
Final source candidate: `1e9a688159707d70243a4aeb23e47678a5a6e6f2`. The retained full-cohort
capture is source `1dae876a`; the final source-binding/qualifying-design corrections have their own
explicit census, counterexamples and targeted 78-label capture below.

Owner: `clinical_applicability::assess_clinical_applicability`, `::qualifying_purpose_outcomes`,
`evidence_resolver::clinical_record_sources_eligible`, `::resolve_omega_evidence_standard`,
`scoring_input_contract::_named_in_title`; readiness and scoring consume those decisions.
Evidence: ownership matrix, GLOSSARY, source callers and fail-first production-seam regressions.
Will NOT create: a parallel purpose engine, scorer, registry, clinical approval, public status or magnitude.

## Implemented behavior

- No label claim is required. Eligible research earns the same points with an aligned claim or no claim.
  299v's exact IBS context earns 16/20 in either case; marketing alignment remains explanation metadata.
- An unrelated attributable claim cannot inherit an outcome. Formula-level positioning does not reject
  unrelated formula ingredients; named identity attribution reuses the existing role-owner alias matcher.
- Preparation and population stay source/context-specific. Special populations require explicit targeting.
- The existing qualifying-outcome predicate is required before scoped credit, including claim-free labels.
  A null/mixed primary, exploratory secondary or unresolved outcome is never affirmative support.
  Approved independent contexts remain usable while siblings are held.
- Ginger's general adult label uses its qualifying direct trial, not the pregnancy synthesis's study strength.
- Enrichment and score consumers exclude explicitly held/unapproved clinical contexts through the shared
  source-eligibility gate. Vitamin D keeps independent nutrition authority; Testofen cannot regain legacy
  positive credit from its ineligible contexts; lactoferrin's explicit hold stays in force.
- Omega clinical holds do not erase separately approved nutritional contribution. One shared resolver serves
  native/generic routes, retains existing numerical policy and population/preparation/identity controls, and
  cites EFSA dietary-reference authority rather than routine retail heart-event research. EPA/DHA quantities
  remain owned by the existing exposure resolver; carrier-oil mass is never substituted.

The omega ruling is `scripts/audits/held_source_closure_20261028/DR_PHAM_RULINGS_20261028.md:122`.
It preserves EPA/DHA nutrition and rejects routine retail heart-event credit. EFSA's primary source was
content-verified on October 28: https://www.efsa.europa.eu/en/efsajournal/pub/1461
(DOI 10.2903/j.efsa.2010.1461). Adult 250 mg/day is a total-intake AI, not an RDA, clinical efficacy threshold
or an EFSA-authored score. Existing editorial 10.4/11.1 magnitudes are unchanged.

## Fail-first and focused verification

Receipts in `~/pg_quality/condition_scope_20261028/`:

- `fail_first_takeover.log`: four failures establish abbreviated attribution and held-source credit leakage.
  The eight affected cases passed after correction.
- `fail_first_outcomes.log`: both null-primary/positive-secondary and unresolved contexts wrongly earned
  14 raw on a claim-free product. Qualifying-outcome and ginger slice: 18 passed after correction.
- `fail_first_enrichment_hold.log`: three held records remained positive-looking clinical matches during
  enrichment even when scoring excluded them. The corrected enrichment/owner slice passed 571 tests.
- `takeover_stable_owner_slice.log`: 718 owner/consumer tests passed. Subsequent enrichment-hold source
  correction was checked in `takeover_enrichment_hold_slice2.log` (571 passed).
- Native/generic omega public-seam cases cover fish/krill/algae, held-study exclusion, unchanged magnitudes,
  unknown exposure, child/SPM/DHA-only controls and unfinished companion assessments. Their separate owner
  retains the detailed focused verification receipts.
- 230149's named canary passes: approved native research restores applicability 3→6, Evidence 13→16 and
  total 65.5→68.5; undisclosed-amount Dose remains 8.55 raw. The old assertion encoded a claim bonus.

Source-specific fixture corrections retain production holds: synthetic role/lineage controls are marked
explicitly as test mechanics, never new clinical approval. Real held-source and independent-authority
assertions are maintained separately. No runtime guard was relaxed to retain an obsolete score.

## Frozen raw-label measurement

Same immutable manifests as the original lane: main 460 labels and gated 40 labels. Baseline captures
`takeover_base.jsonl` and `gated/takeover_base.jsonl` both attest e923cb233 and unchanged source fingerprints.
The main-cohort capture completed successfully on `1dae876a`: **66/460 numeric movers, 32 up and 34 down**.
All numerical changes are Evidence except **304641 Healthy Hormone Formula**: excluding held Testofen
also removes the existing branded-studied Formulation credit, 20.0→14.7. Evidence 15.6→10.4; total
76.0→65.5. This is a source-eligibility effect, not a purpose-only rejection. Remaining non-Evidence pillars,
input hashes, routes/subroutes/profiles/status, safety-gate and Dose-safety projections are identical.
Complete per-label listing: `takeover_movement.txt`. The earlier report's 48-mover count is superseded.

Final independent review found source-binding and trial-strength edge cases. `7b3e34f3` joins context
approval to that same eligible declared source (with the signed source mask), never a sibling's citation.
The live census finds no newly blocked scoring-capable context; the 11 rejected accepted-context rows
belong to records already reference-only (`context_source_join_census.json`). Real Magtein trial
39252819 remains eligible beside excluded correction 40567408; correction-only source scope cannot credit.

`1e9a6881` always derives direct-RCT strength from the qualifying families, even if a held synthesis was
filtered before scope evaluation. Aggregate enrollment is removed when the type changes or curated
contexts are excluded; a fully qualifying record at the same design retains its enrollment. This affects
12 recorded source-design relationships (`qualifying_design_census.json`). The same frozen input pool
supplies a targeted **78-label final-source capture**, covering those sources and controls. Its input paths
and raw hashes are verified row-for-row against the retained 460 capture; the original capture and metadata
are not rewritten or restamped. Existing `replay.compare_records` produces the incremental comparison.

Final-source targeted result: **14 numeric movers, all Evidence downward; 64 numerical controls unchanged**.
Thirteen move 15.6→12.2 public Evidence (strong record body→one approved RCT); Adrenal Energy Formula
328276 moves 5.0→4.0. Other pillar scores, routes/subroutes/profiles/status and safety-gate/Dose-safety
projections are unchanged in all 78. Receipts: `strength/candidate.jsonl[.meta.json]`,
`strength/comparison_receipt.json`, `strength/delta_from_1dae.json`. Source is exactly `1e9a6881`;
source_unchanged=true. This is a bounded incremental measurement, not a claim of another full 460 replay.
Gated final capture `gated/takeover_final.jsonl` attests 1dae876a, 40 products, source_unchanged=true.

The final 40-label candidate gives 21 Evidence-only movers (19 up, 2 down) and no other
pillar/status/route/safety-gate or Dose-safety projection change. Cranberry/inositol/selenium/riboflavin gain scoped claim-free credit;
ginger gains direct-trial credit; two quercetin-phytosome labels lose mixed-primary credit. The prior intermediate receipt is preserved separately; final qualification uses the clean committed capture.

## Raw canary review

Before final readiness-consumer reconciliation, the complete 33-label check found four expected-field
drifts with the remaining 29 unchanged. No safety, warning, identity, amount or unrelated pillar field drift.

- 182730: false partial from an EPA/DHA nutrition resolution not recognized by the readiness consumer;
  correct shared-authority consumer is being qualified, without calling omega an essential nutrient.
- 278454: 330 mg DHA-only disclosure does not pass the existing EPA+DHA authority rule. Its held clinical
  match cannot establish completion. Complete→partial is truthful, while its nutrient-panel points stay.
- 298070: native strains have completed limited/null review and no affirmative points. Partial→complete
  reflects the existing reviewed finding, not a new benefit or positive conclusion.
- 298102: held respiratory clinical credit is removed. Independent vitamin D authority remains 10 raw;
  public Evidence falls 15.6→11.1, total 92.7→88.2, Excellent→Very good; assessment completes on authority.

Final source-bound refresh: 278454, 298070, 298102 and 337853 were each updated individually from raw,
with exact causes in the existing manifest changelog. 337853 is **Boswellia Phytosome**, whose qualified
PMID39092235 is a direct RCT, not the record's pooled rating: Evidence 15.6→12.2, total81.2→77.8,
Very good→Good. All other frozen fields stay unchanged. 182730 remains complete through the shared
readiness consumer. Final check on `1e9a6881` (`final_qualified_raw_canary_green.log`): **33 checked, 0 failed**.

Final owner/consumer slice (`final_source_owner_slice.log`): **721 passed**. Independent fresh review by
`safety_check` of source-binding and qualified-strength corrections reproduced the held-ginger and valid
Magtein/correction controls, three named tests passed, and reported no remaining finding. Broader integration,
exact final-head CI and local qualification remain root-owned; a pending check is not a pass.

## Remaining boundaries

PR278 owns receipt-by-receipt legacy reconciliation and retirement of its remaining purpose fallback.
Pooled probiotic `not_reported` clinical credit remains a named, separately measured follow-up; native
`_qualifying_outcomes` still requires primary hierarchy. Existing scientific holds are preserved.

Whole-fast CI on the exact final candidate and applicable local verification remain required before merge. The bounded capture compares scored pillars, routes, source fingerprints and safety-gate/Dose-safety
projections; it does not establish whole exported-blob equality or a new-catalog app rendering check.
No corpus build, export, release, upload, app import or publication was performed.
