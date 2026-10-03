# Q53 / D26 / D24 / omega calibration closure

Status: **implemented, measured and independently reviewed; fresh full-corpus
Clean and release validation remain pending.** Production source was measured at
`aca666213960dd0a42f49fcd49f65b9ee7a96a17` against the accepted baseline
`e250cd679a30241b5a08f9bad4c396649303dc39`. The input manifest contains 344
frozen raw DSLD labels and has SHA-256
`6c7c6c7e4080487830f5b0acd474204f75119b6b6c9bfe77e898c73009e6b764`.

This receipt does not claim a rebuilt catalog, release-rung pass or runtime
publication. Sean runs the final Clean corpus after this source candidate is
accepted.

## Owner check

- Owner: `dose_assessment::positive_clinical_benchmark` and existing route Dose
  modules assess amount adequacy; evidence:
  `rg 'positive_clinical_benchmark|score_.*purpose_dose' scripts`.
- Owner: `evidence_resolver::resolve_omega_evidence_standard` and existing route
  Evidence modules assess applicable evidence strength; evidence:
  `rg 'resolve_omega_evidence_standard|score_evidence' scripts/scoring_v4`.
- Owner: `scoring_input_contract::classify_ingredient_roles` supplies declared
  purpose participation; no mass-derived denominator was added.
- Owner: `enhanced_normalizer::EnhancedDSLDNormalizer._merge_alternate_serving_rows`
  reconciles alternate serving columns; Flutter consumes canonical
  `display_ingredients` and does not merge or rescore them.
- Owner: `quality_score::assemble_quality_score` retains pillar maxima
  **20 / 20 / 20 / 15 / 15 / 10** and independent quality/safety outputs.
- Will NOT create: another Dose or Evidence engine, benchmark registry, purpose
  classifier, serving selector, public status, export field or app calculation.

## Final policy behavior

1. A clinical amount becomes a Dose benchmark only for an exact, positive and
   applicable ingredient/preparation/population/purpose record. Null, mixed or
   inapplicable trials do not establish adequacy.
2. Every declared-purpose ingredient contributes one equal Dose vote. Existing
   collagen, botanical, sleep, joint and immune preparation/category Dose owners
   supply their per-purpose vote. Incidental/supporting ingredients are excluded
   unless the shared role owner gives them their own purpose.
3. A disclosed amount without an applicable benchmark receives the existing
   limited-assessability credit. A label whose required panel amounts are absent
   remains `not_scored`.
4. The four D26 amount/prominence safeguards were removed from Evidence only
   after the same rows became assessable through Dose. Evidence retains identity,
   source, preparation, population and purpose applicability.
5. Omega Evidence is amount-independent: ordinary applicable adult EPA+DHA is
   10.4, explicit applicable adult triglyceride-lowering purpose is 20, and
   prenatal intake authority is 11.1. Excluded populations/preparations remain
   held. Dose alone assesses the EPA+DHA amount.
6. Dose appropriateness and Safety risk remain separate. A specialized useful
   range can lower Dose without a safety finding; a regulator/reference safety
   threshold can affect Safety independently. The same numerical judgment is
   not copied between them.
7. Fiber detox/cleanse and stimulant-laxative facts now make one Formulation
   judgment each. Their former fixed duplicate penalties are removed.

## Purpose denominator demonstrations

These probes call the production Dose owner. The 16-point vote is the existing
disclosed-but-unbenchmarked fallback.

| Case | Equal votes | Denominator | Raw Dose |
|---|---|---:|---:|
| One declared purpose | 22 | 1 | 22.0 |
| Two declared purposes, one unbenchmarked | 22, 16 | 2 | 19.0 |
| Three declared purposes, one unbenchmarked | 22, 22, 16 | 3 | 20.0 |
| Four declared purposes, one unbenchmarked | 22, 22, 22, 16 | 4 | 20.5 |
| Vitamin C purpose plus incidental 1 mg lactoferrin | 22; lactoferrin excluded | 1 | 22.0 |
| BCAA formula plus another unbenchmarked declared purpose | 22, 16 | 2 | 19.0 |
| Required micronutrient panel amounts hidden | no assessable Dose | — | `not_scored` |

The exact payloads are in `purpose_demonstrations.json`. Separate regressions
also prove 100 mg versus 5,000 mg collagen, 0.5 mg versus 20 mg melatonin,
joint-active ranges and immune-active ranges retain their existing specialized
assessments inside the equal-purpose average.

## Omega eight-class movement table

| Class | Evidence before | Evidence candidate | Dose before/candidate | Candidate result |
|---|---:|---:|---:|---|
| Ordinary adult explicit EPA+DHA | 10.4 | 10.4 | 16 / 16 | reviewed weak, applicable |
| Explicit adult triglyceride-lowering purpose | 10.4 | 20.0 | 16 / 16 | strong, applicable |
| Prenatal intake authority | 11.1 | 11.1 | 20 / 20 | intake authority, applicable |
| DHA-only non-prenatal | 10.4 | 0 | 10 / 10 | held incomplete EPA+DHA identity |
| Child/baby | 10.4 | 0 | 10 / 10 | held population |
| Mixed purpose | 10.4 | 0 | 10 / 10 | held ownership |
| Specialized preparation/delivery | 10.4 | 0 | 10 / 10 | held preparation |
| Unresolved identity | 0 | 0 | 0 / 0 | held identity |

The candidate also rejects negated claims including “doesn't lower
triglycerides” and trailing qualifications such as “is not supported by
evidence”; neither manufactures the 20-point purpose standard. Full payloads
are in `omega_movement_table.json`.

## Frozen-raw movement report

Of 344 frozen labels, 71 totals move: 67 increase and 4 decrease. Mean movement
among movers is +5.3803; the range is -5.5 to +12.8.

| Public movement | Count | Direction |
|---|---:|---|
| Evidence | 61 | 61 up |
| Dose | 17 | 7 up, 10 down |
| Formulation | 2 | 2 up |
| Transparency | 2 | 2 up |
| Verification | 0 | — |
| Safety/Hygiene | 0 | — |
| Scoring status | 0 | — |
| Typed safety status | 0 | — |
| Route / subroute / subtype / purpose | 0 | — |

Quality-tier transitions are 30 Needs improvement→Good, 6 Poor→Needs
improvement, 6 Good→Very good and 2 Good→Needs improvement. The two downward
crossings are Dose corrections; neither is a safety movement.

The four products with a non-Dose/Evidence pillar movement are explained:

- `227922` and `79233`: Formulation increases because the duplicate fixed
  fiber detox/laxative penalties were removed; the underlying single
  Formulation judgment remains.
- `69507` and `74605`: Transparency increases because the canonical
  alternate-serving repair stops counting the same printed disclosure twice.
- `79233` also has its intended Evidence ownership movement.

Every moving product and pillar delta is listed in `movers.json`; aggregate
counts and the four cross-pillar explanations are in `movement_summary.json`.

## Duplicate-deduction and numerical-ownership disposition

| Fact | Disposition |
|---|---|
| Evidence trial amount versus Dose adequacy | Dose is the sole numerical amount owner; Evidence observes applicability and study strength |
| Omega EPA+DHA amount | Dose only |
| Fiber detox/laxative | Duplicate fixed penalties removed; one Formulation judgment retained per fact |
| UL/excess exposure | Dose useful-range appropriateness and Safety threshold risk retained as distinct judgments with separate bases |
| Harmful additive / sugar | Formulation quality and capped Safety/Hygiene consequence retained as distinct declared judgments; neither copies the other's magnitude |
| Restricted clean-label material / B1 | Restricted-material hygiene preference and formula-quality severity retained as distinct judgments; typed safety verdict remains independent |
| Proprietary blend | Transparency owns nondisclosure; Dose records unassessability without a second disclosure penalty |
| Certification | Verification owns quality/testing credit; omega sustainability remains zero-point metadata |
| Purpose/prominence | Shared role owner only; no Evidence or Dose mass-derived purpose selector remains |

The historical Q3 receipt was recovered and all 35 legacy `POOR → SAFE`
aliases were inspected individually. Every case is actually Poor→Needs
improvement quality movement; Safety/Hygiene and B1 remain unchanged in all 35.
The phrase does not represent a safer product or typed safety transition.
`q3_legacy_crossings.json` preserves the per-product receipt.

## Serving and app contract

The read-only raw census covers all 15,414 staged DSLD labels and 323
multi-column labels. Repeated top-level normalized ingredient names fall from
108 to 0; repeated names anywhere in the tree fall from 141 to 18. The retained
18 are distinct authored branches with overlapping serving contexts. Product
`250086` now has one Vitamin E row with 15 mg/2-gummy and 30 mg/4-gummy variants,
linked by the same form UNII; D-alpha and DL-alpha remain distinct.

Independent cross-repo review confirms `display_ingredients` is the canonical
app input. The app partitions it into Nutrition Facts, active ingredients and
other ingredients while preserving order, hierarchy, amount, unit and Daily
Value. No Flutter source change is required. Real rebuilt-artifact rendering
remains a post-Clean validation gate.

## Verification

- The corrected owner/consumer slice passes 471 checks with 26 expected
  absent-corpus canary skips. Earlier correction slices passed 244 and 635
  checks respectively. A new BCAA regression proves an aggregate formula is
  one equal purpose vote alongside another declared purpose.
- 28 alternate-serving checks passed; raw census is 108→0 top-level and
  141→18 all-tree.
- Independent policy review at `374fb4b6` found no remaining policy findings;
  independent serving/app review found no remaining findings after the unit
  correction.
- Frozen raw replay completed 344/344 with matching input manifest and no
  route, purpose, scoring-status or safety-status movement. The exact
  `aca66621` replay is numerically and semantically identical to the corrected
  candidate: zero score, pillar, route, status, Evidence-state or explanation
  changes; output SHA-256 is
  `6b4a14de0d5f55e600b52591fd593482ed92f04d08616587252f9f65f66473b2`.
  The prior CI correction changed only the intended limited-assessability
  explanation on 49 products, with zero numeric movement.

The final local rung ran after documentation integration: **398 passed and 129
skipped**, then correctly exited nonzero because this worktree does not contain
the rebuilt corpus, canaries or distribution artifacts. It is not an accepted
local gate; those skips are exactly what Sean's fresh Clean run supplies. The
dead-code/source-of-truth slice then found one obsolete private serving helper;
it was deleted and its failing node plus all 28 serving checks passed. The first
exact post-rebase CI run (`28837e08`, run 37089000275) exposed the remaining
stale expectations and two real Dose-owner gaps; all four shards were classified
before correction. The next run (`a9eee377`, run 37090968501) found two remaining
tests importing the retired Evidence mass helper; their structural assertions
remain and the amount assertions were deleted. Exact corrected-source CI at
`aca66621` passed all four shards and skip guards: **18,717 passed / 183 declared skips**
([run 37091524920](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37091524920)).
The fresh full Clean corpus is intentionally not run here.
