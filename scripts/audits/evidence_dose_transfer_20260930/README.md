# Evidence → Dose responsibility transfer

Status: implementation decision packet; no score arithmetic in this document.

Baseline: pipeline `880b17a7`; focused owner/role suite 103 passed, 7 skipped,
1 strict xfail. The frozen 1,261-label audit sample is
`~/pg_quality/closure_20261001/deadcode_6917_1261.jsonl`.

## Invariant and owners

An amount-based adequacy or exposure judgment may leave Evidence only when the
same judgment is already made by an existing Dose owner or is added to that
owner in the same change. Clinical trial amounts remain registry source facts.
Identity, preparation, intervention, population, purpose and outcome
applicability remain Evidence judgments.

Owner: `scripts/scoring_input_contract.py::get_evidence_subject_rows` for the
subject set; `scripts/scoring_v4/exposure.py::row_exposure`, enrichment
`rda_ul_data.adequacy_results`, and the existing route Dose modules for amount
assessment. Will NOT create a second subject provider or post-route Dose engine.

## Current amount judgments

| Route / decision | Current Evidence owner | Existing Dose coverage | Transfer classification |
|---|---|---|---|
| Generic record minimum (`min_clinical_dose`) and undisclosed amount | `clinical_applicability.py::assess_clinical_applicability`; `evidence_resolver.py::resolve_evidence_for_row`; `generic_evidence.py::score_evidence` | The registry has 16 dose-bearing records. Existing Dose covers KSM-66, white kidney bean, amla, MSM/OptiMSM, BCAA and official nutrient adequacy. It does not yet own equivalent benchmarks for nine named groups below. | Add a typed, audit-visible studied-dose assessment to the existing Dose result before deleting the Evidence veto. Numerical treatment of a missing benchmark remains D24 policy. Shared removal cannot land while any record lacks an owner. |
| Generic primary floor amount gate | `generic_evidence.py::_primary_mass_floor` | Route Dose owns amount adequacy; shared role classifier owns prominence | Replace its private mass-primary selection with `classify_ingredient_roles`; Evidence floor eligibility may use research/role facts but not label amount. Dose retains the exposure judgment. |
| Literature `studied_dose_exposure` gate | `evidence_resolver.py::resolve_evidence_for_row` | Partial; only routes/reference families with an existing benchmark | Same as generic record minimum. Do not discard the studied exposure from the source record. |
| Probiotic trial-dose applicability, up to 8 Evidence points | `probiotic_evidence.py::score_evidence` via native context `dose_applicability_credit` | `probiotic_dose.py::score_dose` owns disclosed CFU and adequacy, but most current adequacy tiers are industry-potency rather than trial-dose judgments | Remove dose from Evidence only with an explicit Evidence magnitude decision. Preserve trial-dose comparison in Dose metadata; do not silently convert the 12-point clinical subscale to 20. |
| Omega Evidence selected/graduated by daily EPA+DHA or DHA | `evidence_resolver.py::resolve_omega_evidence_standard` | `omega_dose.py::score_dose` already owns the same explicit EPA+DHA exposure and directed-serving interval | Remove amount thresholds from Evidence. A purpose-only record-selection rule and its magnitudes require approval; do not award 20 merely because exposure leaves Evidence. |

The uncovered generic groups are lactoferrin; Carnipure/L-carnitine; ALCAR;
the zinc-lozenge 80–207 mg intervention; L-arginine; D-mannose; D-aspartic
acid; Tesnor; and Sytrinol. Generic Dose's current no-reference disclosure
credit is not an adequacy judgment and does not satisfy the transfer invariant.

Amount comparisons in `clinical_applicability`, `evidence_resolver`, and
`generic_evidence` are shared gates. Do not introduce a record allowlist or a
route-specific exception: globally removing them before those nine groups have
an existing Dose benchmark would create an assessment gap.

## Observed baseline

In the frozen 1,261-label sample, the route distribution is small but exposes
the coupling:

- Omega: 5 products; Evidence/Dose pairs are 0/0, 0/4.3, 13.9/17.5,
  0/4.5 and 0/7.3.
- Probiotic: 8 products; reviewed clinical strength can coexist with low Dose
  (for example Evidence 5.4 with Dose 3.1), and one product receives Evidence
  9.0 with Dose 18.2.
- Generic: 1,003 products; the most common combinations include Evidence 0
  with Dose 9.5 (329), 14.5 (246), and 11.4 (113). This is not by itself proof
  of a dose-gate defect because completed negative/no-evidence reviews also
  score zero; candidate replay must classify drivers per product.

## Required implementation tests

All tests pass through `build_scored_artifact` or the route's production scorer.

1. The same reviewed evidence record produces the same Evidence score at a
   disclosed studied dose, a lower dose, and an undisclosed member dose.
2. The three labels retain distinct Dose assessments and reasons.
3. A blend total never becomes a member dose; an exact studied formula can use
   only its own declared total.
4. Preparation, intervention and population mismatches still deny Evidence.
5. Probiotic Evidence does not contain `dose_applicability`; Dose retains the
   reviewed trial comparison and ordinary CFU assessment.
6. Omega Evidence record selection is unchanged by EPA+DHA amount; omega Dose
   remains amount-sensitive and rejects carrier-oil mass.
7. Every removed config key and explanation has no production consumer.

Real seams for the generic transfer include 305203 KSM-66, 182940 MSM,
293877/307547 ALCAR, 309486 CogniPhos, 54775 Sytrinol, and 1179/2219 Ravage
blend ownership. Probiotic canaries include 250851, 299239, 307727, 326762 and
327965. Omega canaries include raw labels 224615, 206295, 35718 and 77225 plus
enriched labels 327776, 288740, 273630, 239592, 184654, 261863 and 267461.

## Decisions required before score-changing implementation

1. **Probiotic Evidence magnitude:** keep the reviewed clinical-strength
   subscale at its current maximum of 12/20, or approve a new non-dose mapping.
   Automatic 12→20 rescaling is excluded.
2. **Omega Evidence purpose mapping:** approve which existing reviewed record
   applies to an ordinary omega product, an explicit triglyceride-purpose
   product, and a prenatal DHA product, independent of amount. Existing point
   values may be compared, but their amount-triggered use is not approved as a
   purpose-only policy.
3. **Generic missing benchmark:** D24 must decide whether an otherwise complete
   product retains an ordinary numeric total. Until then, the transfer can
   preserve the assessment as `unassessable`; it cannot treat missing knowledge
   as zero dose.

No implementation agent may decide these magnitudes implicitly.

## Execution boundary from this packet

Immediately landable work is regression and replay scaffolding plus relocation
of a diagnostic only where the existing Dose result receives the same
comparison. The shared amount gates, probiotic 8-point component, omega scale,
and primary Evidence floor are not landable until their named ownership and
magnitude decisions close. A partial removal would violate the transfer
invariant even if its focused tests passed.
