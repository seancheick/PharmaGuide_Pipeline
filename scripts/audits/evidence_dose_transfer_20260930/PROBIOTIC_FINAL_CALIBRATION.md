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

## Decision and integration boundary

Recommended policy: approve Candidate B with graded 10/6/(0,2,4) and same-condition conflict suppression. This is more conservative and more explainable than the binary version, does not depress any quality tier relative to binary Candidate B, and reserves 20/20 for exceptional replicated evidence.

After Sean approves this policy, production integration must happen through the existing probiotic Evidence owner. The same change must put reviewed trial-range/amount assessment in the existing probiotic Dose owner, remove the measurement switch, update explanations, and replay frozen affected labels plus controls. This packet does not integrate a production score or authorize publication.

## Verification

- Graded-model replay head: `6aa38537701d9c7fc753a5bf16fd65ca0aae8954`; final audit/reporting head: `42908527ab52b43cbc208a267321dce33551b411`.
- Focused measurement and report-integrity regressions: 19 passed.
- Final current-model replay: 1,259/1,259 products; byte-identical to the prior graded replay; SHA-256 `71b97cfce0d2cd25370524cd1b47ee2de788fd61950882321d0e2e3d672edcc8`.
- Frozen manifest SHA-256: `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`.
- Full fast checkpoint after the graded scoring model: 17,854 passed, 168 skipped, 1 existing Ravage cinnamon expected failure. The final audit-only JSON correction is covered by the focused rung and changes no score output.
