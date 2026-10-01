# Probiotic Evidence certainty parity — October 1, 2026

Status: Policy APPROVED / Measurement COMPLETE / Production validated for local integration / Release NOT AUTHORIZED. These results supersede the historical September30 counts below. No push or release.

## Owner Check

- Owner: `scripts/scoring_v4/modules/probiotic_evidence.py::score_evidence` — certainty/applicability/confirmation; traced callers, focused regressions and frozen replay.
- Owner: `scripts/studied_formulas.py::_assess` — formula identity/preparation/source ownership and existing dose comparison.
- Owner: `scripts/scoring_v4/modules/probiotic_dose.py::score_dose` — amount and reviewed trial comparison destination.
- Owner: `scripts/scoring_v4/config/quality_score.json` — production magnitudes.
- Will NOT create: another scorer, clinical registry, formula matcher, Dose engine or app calculation.

## Corrections

Equivalent recorded study designs and effects now share one certainty calculation across generic/formula and native paths. Identity specificity belongs exclusively to applicability. Missing design never becomes an RCT; missing native effect strength is not invented or derived from replication counts. Mixed primary outcomes cap that family's certainty using the existing mixed-effect weight.

An assessed exact formula cannot borrow species/member research. Applicability follows the same family earning certainty. Candidate ownership metadata and explanations no longer claim companion credit or matching dose. An unknown formula strain fails closed instead of crashing. Native eligibility preserves preparation and identity safeguards: inactivated organisms cannot inherit live-strain Evidence. That last correction is latent in this cohort but protected by a failing-before/passing-after regression.

## Current frozen result

| Check | Corrected candidate |
|---|---:|
| Labels |1259:542 probiotics+717 controls|
| Comparable scored probiotics |535|
| Seed Evidence / total |14.5/20 /84.5/100|
| Seed certainty / applicability / confirmation |8.5+6+0|
| Seed Transparency / Verification |12/15 /8/15|
| Four infant BB12 anchors |Evidence18=10+6+2|
| Changed totals versus prior graded draft |191, entirely Evidence|
| Quality-tier crossings versus baseline |106, previously103|
| Added / removed crossings versus prior draft |12 /9|
| Needs improvement→Poor |31, previously36|
| Other pillars, Safety drivers, route/status changes |0|
| Changed nonprobiotic controls |0/717, complete payloads identical|
| Unexplained measured deltas |0|

The JSON re-reports all103 previously classified crossing IDs, all106 current crossings and all191 changes versus the prior graded draft with component causes. Raw components and displayed pillar deltas are distinguished to account for public rounding. None of the31 downward-to-Poor labels has certainty≥8, replication credit or an assessed formula. Quality tiers and Safety are different judgments; none of these changes alters a Safety driver.

Observed certainty among535 scored probiotics:0:225;4:4;5.6667:2;6.6667:56;8.5:1;10:247. Clinical-strain summaries without a reported design retain the conservative4/6 design weight; this is not randomized research.

Seed's8.5 certainty belongs to its exact formula's recorded positive-weak RCT. The previous6 was not solely that formula's score: generic B.longum research on other strains could win the earlier candidate. The corrected owner prevents that substitution. No competitor score target or Seed exception is used. Keep the verified stored label because the current webpage has conflicting blend allocations. Transparency12 and Verification8 remain; Seed is a Phase5 Verification calibration canary.

## Verification and next integration gate

- Clean replay head145ff18c:1259/1259. The preparation-corrected replay is byte-identical to f82ba9cd:SHA25645ad0e58d79ae746c0994409acbe0d156d355e5925e7ca722854eb5291a708d2.
- Frozen manifest:cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286.
- Current focused measurement suite:50 passed. Prior full-fast checkpoint at a5ab7029:17885 passed,168 skipped,1 existing Ravage cinnamon xfail. Current full-fast checkpoint at145ff18c:17886 passed,168 skipped,1 existing Ravage cinnamon xfail (536.28 seconds).
- Fresh reviewer reproduced Seed, all four BB12 anchors, every crossing, all controls and preparation rejection. No measurement blocker remains.
- Production single owner migrated: retired12/8 and experiment path removed; formula identity delegates to `_assess`; CFU/studied-amount assessment stays with existing Dose. Identity, preparation, population, purpose, primary outcomes, review and trial-family independence remain guarded.
- Clean reconciled production head `b06be9802f8c6d91126ab6033880c25bd9c1c249`, including concurrent main `d021061b`. Production replay SHA256 `a20cea182bc18ecb6eeff4dc7dc54232c6452a2631c22a53b5b11e2560c5ea72`:1259/1259 captured, source unchanged. All Evidence components, dimension math, public pillars, totals, tiers, routes, status, Safety and confidence match the accepted measurement. All717 controls retain complete semantic payloads; only the four exact quality-config version/fingerprint provenance paths are excluded.
- Config revision `1.22.0-probiotic-family-evidence` has fingerprint `b23444ae2b18e041`; prior version/fingerprint history is preserved. Synthetic expectations were migrated without changing their labels or other fixture values: unspecified study design6.6667 certainty+3 applicability=9.6667 Evidence; species research10 certainty+0 applicability=10 Evidence. Neither receives invented strain efficacy or replication.
-119 Evidence-state clarifications were independently checked:24 applicable primary null states and95 zero-credit native assessments without applicable primary null findings. All are recorded per product in the JSON receipt; no numerical or safety change.
- Focused checkpoint4002 passed21 skipped; additional owner checks64 passed1 skipped; population regression checkpoint746 passed. Final full `scripts/test.sh fast`: **17898 passed,167 skipped,1 existing Ravage cinnamon xfail**,627.94 seconds. Log `.claude/state/probiotic_production_reconciled_fast.log`. The preliminary run interrupted to reconcile main is not an acceptance receipt.
- Fresh-context reviewer approved source, clinical guards, semantic test migration, complete replay equality and main reconciliation. The existing Ravage xfail is unrelated and remains a mandatory Phase2 closure before release.
- Next: local integration, then Phase2 identity/roles/prominence (Ravage, shared primary selection, trace protein and alternate servings). Generic/omega amount transfers and broader Dose policies remain open. No push or release.

## Historical September30 report — superseded measurements

# Probiotic Evidence final calibration

Status: measurement and crossing classification complete; production policy is not integrated.

## Owner Check

- Owner: `scripts/scoring_v4/modules/probiotic_evidence.py::score_evidence` — the public v4 scorer's probiotic Evidence result.
- Owner: `scripts/studied_formulas.py` — exact-formula identity and accepted native-context validation.
- Owner: `scripts/scoring_v4/modules/probiotic_dose.py::score_dose` — the existing destination for trial-range and label-amount assessment.
- Will NOT create: another Evidence scorer, clinical registry, identity resolver, Dose engine, or app calculation.

## Recommendation

Keep Candidate B's 10/6/4 architecture, with the 4-point component graded:

| Component | Range | Meaning |
|---|---:|---|
| Evidence-family certainty | 0–10 | Strength of the strongest single applicable probiotic-owned evidence family. Enrollment, top-N, depth and repeated-study bonuses do not stack here. |
| Product applicability | 0–6 | Whether that positive evidence directly applies to the identified strain/formula, product purpose and population. |
| Independent replication/consistency | 0, 2 or 4 | 0 for one family; 2 for two independent, applicable, directionally consistent RCT families for one condition; 4 for at least three. Pooled records add no family until their underlying independence is curated. |

An applicable null, negative or mixed family suppresses consistency credit only when an applicable positive family exists for the same condition. It does not erase the strongest positive-family certainty or product-applicability facts. No new negative penalty is proposed.

This removes the old artificial 12/20 category ceiling. It also prevents two trials from mechanically producing 20/20. In the measured corpus, four infant labels score 18/20 rather than 20/20; no product reaches 20 today because none has three independent qualifying families for one applicable condition.

## Binary versus graded result

Both arms replayed the same 1,259-label manifest: all 542 probiotic labels plus 717 exact non-probiotic controls.

| Result | Binary 10/6/4 | Graded 10/6/(0,2,4) |
|---|---:|---:|
| Comparable scored probiotics | 535 | 535 |
| Mean Evidence | 6.475 | 6.460 |
| Median Evidence | 6.0 | 6.0 |
| Maximum observed Evidence | 20 | 18 |
| Products at 20 Evidence | 4 | 0 |
| Maximum observed total | 83 | 83 |
| Products whose total moved from baseline | 412 | 412 |
| Quality-tier crossings | 103 | 103 |
| Binary-to-graded tier differences | — | 0 |
| Non-probiotic controls changed | 0 / 717 | 0 / 717 |
| Route, status, Safety pillar or Safety verdict changes | 0 | 0 |

Only products 217182, 246008, 246011 and 246012 differ between the two models. Each has two independent accepted BB-12 infant-colic families, so graded consistency contributes 2/4. Each loses two Evidence points and none changes quality tier.

## The 10-point certainty continuum

The single-family core has two source paths, both bounded at 10:

1. A reviewed native exact-strain context maps study design once: positive RCT, crossover RCT, cluster RCT, meta-analysis or systematic review = 10; guideline = 8; observational = 5; open-label = 4. The context must have an accepted exact-strain identity and a primary, patient-important outcome applicable to the product purpose and population.
2. An existing probiotic-owned generic/formula record uses `10 × study-design base / 6 × evidence-level multiplier × effect-direction multiplier`. `rct_multiple` is treated as one `rct_single` family so replication is not counted twice.

The observed certainty values among the 535 scored probiotics are:

| Certainty | Products | Typical derivation |
|---:|---:|---|
| 0 | 225 | No applicable positive qualifying family. |
| 2.6 | 4 | One clinical-strain family with mixed effect. |
| 3.6833 | 2 | One clinical-strain family with positive-weak effect. |
| 4.3333 | 56 | One clinical-strain family with positive-strong effect. |
| 6 | 127 | A single accepted formula/generic family at the existing design, identity and effect weights. |
| 9 | 2 | A high-level branded family at 0.9 identity weight. |
| 10 | 119 | A positive top-design exact-strain context or maximum single generic family. |

These are explicit computations rather than hidden research-depth bonuses. The production explanation should expose the winning family and inputs when this policy is integrated.

## Conflict census

Among the 535 scored probiotic labels, 416 have zero applicable positive RCT families for one condition, 115 have one, four have two and none has three. No label has both an applicable positive RCT family and an applicable null, negative or mixed family for the same condition.

The first diagnostic incorrectly called any applicable null family a material conflict, including a null result with no positive family or for another condition. That diagnostic defect was fixed in the experimental owner and covered by regressions. The score was already calculated per condition, so the correction changes no replayed score.

The conflict rule is therefore tested but future-facing in this corpus. A future same-condition conflict earns 0 consistency points; it does not create a separate penalty without another approved policy decision.

## All 103 quality-tier crossings

The complete per-label rows and causal tags are in `PROBIOTIC_FINAL_CALIBRATION.json`. Primary causes are mutually assigned for review:

| Primary cause | Crossings |
|---|---:|
| Single-family certainty gain | 43 |
| Product-applicability gain | 7 |
| True independent replication gain | 4 |
| Companion evidence removed | 11 |
| Applicable primary outcomes were null/nonpositive | 9 |
| No qualifying positive family for this purpose/population | 24 |
| Old aggregate/depth credit removed | 5 |
| **Total** | **103** |

The movement remains a quality-score tier movement. Safety is a separate axis and did not change.

### The 36 Needs improvement to Poor crossings

Every one was inspected through its embedded assessment and owner metadata:

- 9 lose companion-ingredient evidence that accounted for the removed points;
- 7 have applicable exact-strain primary patient-important outcomes, but those outcomes are null or otherwise nonpositive;
- 16 have no qualifying positive family applicable to the product's purpose/population, commonly because the evidence is combination-only, non-primary, a different indication or a different population. Seven of these also had a smaller amount of companion leakage, but that leakage did not explain most of the drop;
- 4 retain one family at six points but lose the old aggregate/depth credit and have no applicable purpose credit.

None of the 36 has certainty of 8 or more, replication credit, or an assessed exact formula. The downward crossings therefore do not show strong exact-strain or exact-formula evidence being forced into Poor. Sixty-three crossings have an absolute total movement of at least eight points; their rows remain individually enumerated in the JSON.

Eight other products have strong Evidence but an overall Poor total. They were already Poor because other pillars are weak; Candidate B gives them 9–16 Evidence points. Evidence does not guarantee a high total when Dose, Verification, Transparency or Formulation are weak.

## Seed canary

Seed DS-01 remains Very good at 82:

| Pillar | Points |
|---|---:|
| Formulation | 20 / 20 |
| Dose | 20 / 20 |
| Evidence | 12 / 20 |
| Transparency | 12 / 15 |
| Verification | 8 / 15 |
| Safety/Hygiene | 10 / 10 |

Its 12 Evidence points are six for the strongest exact-formula evidence family plus six for direct applicability. It receives no consistency points because the registry does not establish independent symptom replication. The other ten lost points are three in Transparency and seven in Verification, not a probiotic ceiling. Competitor scores remain canaries rather than calibration targets.

## Seed source audit follow-up — October 1, 2026

The current Seed website audit adds unresolved checks before policy ratification; it does not change the frozen replay or award points.

- **Certainty consistency:** the native exact-strain path assigns 10 to accepted positive top-design contexts, whereas the formula/generic path preserves design, evidence-level and effect weights. Seed receives 6 through the latter. Compare matched study-design/quality scenarios across both paths and justify differences by clinical facts rather than record representation. The existing recorded trial has limitations; a higher score is not presumed.
- **Label version:** the official reference library currently lists new blend allocations near its top but old allocations in its lower Supplement Facts section. The verified September submission matches the older label. Establish commercial version and trial-formula equivalence before altering label facts or the exact-formula contract. Source: https://seed.com/reference/syn-wk?tab=studies .
- **Transparency:** the reviewed pages disclose blend totals and strain names, but not individual-strain allocation. No new basis for the remaining three disclosure points was found.
- **Verification:** current company pages describe accredited third-party testing; the current pillar still treats this as a company assertion without independent product certification. Mamavation reports a separately purchased contaminant test dated February 24, 2026 (https://mamavation.com/supplements-mamavation/seed-testing-results.html). Obtain and verify underlying laboratory/sample provenance before treating that narrative as verified test results. Its scope cannot establish strain identity, probiotic potency, every batch, or product certification.

Next action: measure representation consistency through the existing probiotic Evidence owner, then present any required numerical policy revision with affected labels and controls. Keep source completeness, clinical certainty and independent product verification as distinct judgments.

## Decision and integration boundary

Recommended policy: approve Candidate B with graded 10/6/(0,2,4) and same-condition conflict suppression. This is more conservative and more explainable than the binary version, does not depress any quality tier relative to binary Candidate B, and reserves 20/20 for exceptional replicated evidence.

After Sean approves this policy, production integration must happen through the existing probiotic Evidence owner. The same change must put reviewed trial-range/amount assessment in the existing probiotic Dose owner, remove the measurement switch, update explanations, and replay frozen affected labels plus controls. This packet does not integrate a production score or authorize publication.

## Verification

- Graded-model replay head: `6aa38537701d9c7fc753a5bf16fd65ca0aae8954`; final audit/reporting head: `42908527ab52b43cbc208a267321dce33551b411`.
- Focused measurement and report-integrity regressions: 19 passed.
- Final current-model replay: 1,259/1,259 products; byte-identical to the prior graded replay; SHA-256 `71b97cfce0d2cd25370524cd1b47ee2de788fd61950882321d0e2e3d672edcc8`.
- Frozen manifest SHA-256: `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`.
- Full fast checkpoint after the graded scoring model: 17,854 passed, 168 skipped, 1 existing Ravage cinnamon expected failure. The final audit-only JSON correction is covered by the focused rung and changes no score output.
