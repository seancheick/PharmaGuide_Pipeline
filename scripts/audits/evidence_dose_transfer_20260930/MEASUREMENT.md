# Phase 1 Evidence -> Dose measured transfer packet

## Baseline and provenance

- Repository/worktree: `codex/transfer-policy-measurement` at exact `origin/main`
  `880b17a7be94d515ca9b526b6d9b1300bcdd26ed`.
- Largest available frozen raw route cohort: every currently manifested scored
  omega/probiotic label, **1,259 products** (**717 omega, 542 probiotic**) from
  58 manifest-owned score files covering 15,421 stored scored products.
- Raw source: 1,256 labels from 33 brand directories under
  `/Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands`; three retained
  manual submissions from `manual_labels/product_submissions` (DS-01 Daily
  Synbiotic, Women's Dual Action, Omega-3 Fatty Acids).
- Every raw file was copied and SHA-256 frozen. Manifest SHA-256:
  `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`.
- Fresh replay ran raw Clean -> Enrich -> Score on all 1,259 with no capture errors
  and stable routing. Baseline SHA-256:
  `7f7b4425c21ccbe2cb46c4e6173a5372fd29a36fc02a2d4e81ec5146142a79b6`.
- Baseline statuses: omega 713 scored / 2 not_scored / 2 suppressed_safety;
  probiotic 535 scored / 2 not_scored / 5 suppressed_safety. Comparisons use
  1,248 products with scores on both sides.

## Owner check

- Owner: `scripts/scoring_input_contract.py::classify_ingredient_roles` -- current
  shared prominence result and function-claim source.
- Owner: `scripts/clinical_applicability.py::assess_clinical_applicability` and
  `scripts/scoring_v4/modules/generic_evidence.py::score_evidence` -- two current
  generic Evidence amount gates.
- Owner: `scripts/scoring_v4/modules/probiotic_evidence.py::score_evidence` --
  probiotic clinical and dose-applicability components.
- Owner: `scripts/evidence_resolver.py::resolve_omega_evidence_standard` ->
  `scripts/scoring_v4/modules/omega_evidence.py::score_evidence` -- omega Evidence.
- Owners: existing route Dose modules, especially
  `generic_dose.py::score_dose`, `probiotic_dose.py::score_dose`, and
  `omega_dose.py::score_dose`.
- Will NOT create: a second role/purpose parser, benchmark registry, Evidence
  subject list, scorer, or post-route Dose engine.

## Probiotic options

### P1: remove `dose_applicability`, retain clinical-strength maximum 12

- 4/542 probiotic labels moved; all four moved by at least one point.
- Deltas: -6.8 to -6.7; mean -6.725 among movers, -0.0216 across all 1,248
  comparable scores.
- Movers: DS-01 Daily Synbiotic 83.6 -> 76.8; two Women's 3-in-1 Probiotic
  Gummy labels 81.4 -> 74.7; Probiotic 2 Billion With LactoSpore 77.1 -> 70.4.
- Tier: three Very good -> Good. Verdict/status/Safety/Dose/other pillar changes: 0.

**Transfer-invariant result: not landable alone.** Probiotic Dose already owns
reviewed whole-formula dose adequacy and general CFU potency, but its ordinary
per-strain metadata explicitly uses an `industry_potency_not_trial_efficacy`
reference. Evidence's removed component uniquely records exact studied-dose
applicability for individual strains. The small movement does not prove the
judgment survived. The existing probiotic Dose owner must consume that reviewed
trial-range result in the same integration change before P1 can land.

### P2: illustrative 12 -> 20 clinical-strength rescale

This is a sensitivity, **not a recommendation**. It removes `dose_applicability`
then multiplies the clinical component by 20/12.

- 392/542 probiotic labels moved; 375 moved by at least one point.
- Deltas: -2.2 to +4.8; mean +2.9704 among movers, +0.9330 across all 1,248.
- Tier: 41 Poor -> Needs improvement, 22 Needs improvement -> Good, 3 Good ->
  Very good; 2 Very good -> Good. Verdict: 41 POOR -> SAFE. No status, Safety,
  Dose, or other-pillar movement.
- Exact-dose products can fall because baseline 12 + 8 = 20 exceeds the
  rescaled clinical-only result. DS-01 falls 2.2; the two Women's gummies and
  LactoSpore fall 1.6. The largest rises are +4.8.

P2 is a broad numerical policy change and requires calibration approval. Data do
not determine that clinical strength should fill all 20 Evidence points.

## Omega options

### Required identity correction

The first O1/O2 replay intentionally tested amount independence and exposed a
separate identity boundary: it awarded Evidence to **58 carrier-only fish-oil
labels** with zero explicit EPA/DHA amount and no EPA/DHA canonical subject.
Those 58 were restored to baseline in the identity-gated projection below.
Carrier oil mass supplies neither EPA/DHA identity nor dose. The projection is a
deterministic row substitution from the two replay captures, documented by
`o1i_identity_exclusions.json` / `o2i_identity_exclusions.json`; it is not a
second scorer.

The explicit triglyceride-purpose probe found another integration defect:
`classify_ingredient_roles` returns the L1 omega route-driver reason before it
can retain the L3 purpose fact. The temporary probe read the same accepted
statement classes only to measure the option. That parser cannot ship. The
existing shared role result must retain a separate efficacy-purpose fact beside
prominence. Triglyceride outcome purpose must never be inferred from triglyceride
molecular-form wording.

### O1: ordinary reviewed 10.4; explicit triglyceride purpose 20; prenatal authority 11.1

Identity-gated projection:

- 301/717 omega labels moved; 285 moved by at least one point.
- Deltas: -9.6 to +10.4; mean +3.0967 among movers, +0.7469 across all 1,248.
- Standards: 141 None -> ordinary reviewed; 9 ordinary -> explicit triglyceride;
  196 amount-derived triglyceride -> ordinary.
- Tier up: 52 Poor -> Needs improvement, 8 Needs improvement -> Good, 3 Good ->
  Very good. Tier down: 21 Good -> Needs improvement, 31 Very good -> Good,
  9 Excellent -> Very good.
- Verdict: 52 POOR -> SAFE; no SAFE -> POOR. Status/Safety/Dose/other pillars: 0.
- Representative high-dose/no-purpose labels (Clearly EPA/DHA and Super Omega-3
  families) fall 9.6 because amount no longer manufactures a strong purpose.

### O2: conservative illustrative mapping

O2 is **not a recommendation**. Values reuse existing generic anchors: ordinary
9.35 = moderate 11 x weak 0.85; explicit triglyceride purpose 14 = generic strong
floor; prenatal authority 10 = nutrition-authority floor.

Identity-gated projection:

- 655/717 omega labels moved (all by at least one point).
- Deltas: -10.7 to +9.3; mean +0.2333 among movers, +0.1224 across all 1,248.
- Tier up: 40 Poor -> Needs improvement, 1 Needs improvement -> Good. Tier down:
  4 Needs improvement -> Poor, 42 Good -> Needs improvement, 32 Very good ->
  Good, 1 Excellent -> Very good, 8 Excellent -> Good.
- Verdict: 40 POOR -> SAFE; 4 SAFE -> POOR. Status/Safety/Dose/other pillars: 0.

The data establish direction and affected labels, not the correct mapping.

## Generic all-route inventory

The exact registry union is **16 records**:

- 11 top-level studied-dose records: BRAND_KSM66, INGR_LACTOFERRIN,
  BRAND_CARNIPURE, INGR_L_CARNITINE, BRAND_OPTIMSM, INGR_MSM,
  INGR_ACETYL_L_CARNITINE, INGR_BRANCHED_CHAIN_AMINO_ACIDS, INGR_L_ARGININE,
  BRAND_TESNOR, BRAND_SYTRINOL.
- 5 applicability-policy dose records: INGR_ZINC_PICOLINATE 80-207 mg,
  INGR_WHITE_KIDNEY_BEAN 1000 mg, INGR_AMLA 500 mg, INGR_D_MANNOSE 2000 mg,
  INGR_D_ASPARTIC_ACID 3000 mg.

Existing Dose behavior covers KSM-66, white kidney bean, amla, MSM/OptiMSM and
BCAA through existing botanical, joint-support, and sports owners. The nine
uncovered groups are lactoferrin; Carnipure/L-carnitine; ALCAR; zinc lozenge;
L-arginine; D-mannose; D-aspartic acid; Tesnor; Sytrinol.

The targeted frozen set contains 11 real labels covering all nine uncovered
groups, a below/at-range D-mannose pair, and standalone/probiotic-route
lactoferrin. Manifest SHA-256:
`2a0c5bde685cca527968a861684c100639d8ee03611d3840dd8f9875d3177b29`.

### G1: amount-independent Evidence, current Dose unchanged

G1 is deliberately **non-landable** because it demonstrates the gap.

| Label | Route | Total | Evidence | Dose |
|---|---|---:|---:|---:|
| Zinc Lozenges 18.75 mg min/day | generic | 56.2 -> 60.7 | 11.1 -> 15.6 | 0 -> 0 |
| L-Arginine 500 mg | generic | 59.8 -> 67.1 | 0 -> 7.3 | 14.5 -> 14.5 |
| ALCAR 600 mg | generic | 71.0 -> 78.3 | 0 -> 7.3 | 20 -> 20 |
| Sytrinol 150 mg | generic | 49.5 -> 56.8 | 0 -> 7.3 | 9.5 -> 9.5 |
| Probiotic Pearls + lactoferrin | probiotic | 58.2 -> 58.7 | 5.4 -> 5.9 | 3.1 -> 3.1 |

Other canaries did not move in Evidence because they were already accepted, held,
or reviewed-null. Sytrinol crosses Poor -> Needs improvement and POOR -> SAFE.
There are no status, Safety, Dose, or other-pillar changes. Current Dose scores
can remain high even when the specific studied range is missed; therefore G1
removes an amount assessment without preserving it.

### G2: illustrative same-change Dose extension

G2 reuses the existing generic Dose clinical-anchor shape: 0-22 raw points,
linear to the reviewed minimum and full at/above the minimum; undisclosed amount
is zero; no benchmark remains unassessable. This point mapping is **editorial and
unapproved**. It was simulated inside `generic_dose.score_dose`, not as a second
production engine, and all code was reverted afterward.

| Label | Studied benchmark | Public Dose baseline -> G2 | Total baseline -> G2 |
|---|---:|---:|---:|
| D-Mannose 1000 mg | 2000 mg | 14.5 -> 10.0 | 65.5 -> 61.0 |
| Zinc lozenge 18.75 mg min/day | 80 mg | 0 -> 2.9 | 56.2 -> 63.6 |
| L-Arginine 500 mg | 1500 mg | 14.5 -> 6.7 | 59.8 -> 59.3 |
| ALCAR 600 mg | 1000 mg | 20 -> 12.0 | 71.0 -> 70.3 |
| D-Aspartic acid 2000 mg | 3000 mg | 14.5 -> 13.3 | 67.5 -> 66.3 |
| D-Mannose 2000 mg | 2000 mg | 14.5 -> 20 | 67.5 -> 73.0 |
| Tesnor 400 mg | 200 mg | 9.5 -> 20 | 53.3 -> 63.8 |
| Lactoferrin 250 mg | 200 mg | 14.5 -> 20 | 71.1 -> 76.6 |
| Sytrinol 150 mg | 300 mg | 9.5 -> 10.5 | 49.5 -> 57.8 |
| L-Carnitine 1000 mg | 1000 mg | 20 -> 20 | 78.3 -> 78.3 |

Tier/verdict changes versus baseline: D-Mannose 2 g Needs improvement -> Good;
Tesnor and Sytrinol Poor -> Needs improvement and POOR -> SAFE. Status and Safety
changes: 0.

The probiotic-route lactoferrin control stays at Dose 3.1 because a generic-route
Dose extension cannot reach it. An all-route integration needs one existing
exposure/adequacy result carrying the reviewed benchmark facts, consumed by the
current route Dose modules. It must not add a post-route engine.

Two policy questions cannot be answered by data:

1. D-mannose and D-aspartic-acid records are reviewed-null. Their trial amounts
   are applicability facts, but treating those amounts as positive Dose adequacy
   benchmarks is a new judgment. G2 quantifies it; it does not approve it.
2. A label can match generic and branded sibling records. The existing owner must
   define specificity and assess one benchmark group once. The simulation preferred
   a named branded record, then one generic group; that precedence is unapproved.

## Required integration symbols and regressions

Implementation seams:

- Generic Evidence: `clinical_applicability.py::assess_clinical_applicability`,
  `generic_evidence.py::score_evidence`, `_primary_mass_floor`.
- Generic Dose: `generic_dose.py::score_dose`, `_band_credit`, and existing
  `rda_ul_data.adequacy_results`/clinical-anchor reference routing.
- Probiotic: `probiotic_evidence.py::score_evidence`,
  `probiotic_dose.py::score_dose`, `studied_formulas.py` reviewed contexts.
- Omega: `resolve_omega_evidence_standard`, `omega_evidence.py::score_evidence`,
  `omega_dose.py::score_dose`, and the shared role/purpose result.

Focused tests to update/add before integration:

- `test_v4_generic_evidence_p133.py`, `test_clinical_applicability.py`,
  `test_below_clinical_dose_flag.py`, `test_v4_generic_dose_p132a.py`,
  `test_dose_window_component_selection.py`.
- `test_probiotic_context_approval_bridge.py`,
  `test_probiotic_review_policy.py`, `test_v4_probiotic_evidence_p23.py`,
  `test_v4_probiotic_dose_p22.py`.
- `test_candidate_d_omega_standard.py`, `test_v4_omega_evidence_p163.py`,
  `test_v4_evidence_magnitudes_config.py`, plus shared-role tests proving an omega
  route driver can simultaneously retain an explicit triglyceride-purpose fact.
- Cross-route canaries: same studied record on generic and probiotic/sports routes;
  disclosed below/at/above range; undisclosed amount zero; no benchmark remains
  unassessable; brand/generic siblings and BCAA/EAA groups assess once; Dose exact
  equality for unaffected controls; status/Safety unchanged.

## Commands

```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/audits/quality_redesign/replay.py snapshot \
  --checkout /Users/seancheick/.codex/worktrees/transfer-policy-measurement/dsld_clean \
  --products-root .claude/state/transfer_policy_measurement/frozen \
  --manifest .claude/state/transfer_policy_measurement/frozen/manifest.json \
  --out .claude/state/transfer_policy_measurement/baseline.jsonl --workers 4

# Same command and frozen manifest produced p1.jsonl, p2.jsonl, o1.jsonl, o2.jsonl
# after each temporary measurement patch.

"$PG_PYTHON" scripts/audits/quality_redesign/replay.py snapshot \
  --checkout /Users/seancheick/.codex/worktrees/transfer-policy-measurement/dsld_clean \
  --products-root .claude/state/transfer_policy_measurement/generic_frozen \
  --manifest .claude/state/transfer_policy_measurement/generic_frozen/manifest.json \
  --out .claude/state/transfer_policy_measurement/generic_baseline.jsonl --workers 2

# The same targeted command produced g1.jsonl and g2.jsonl.
python3 .claude/state/transfer_policy_measurement/analyze_arms.py p1 p2 o1 o2
git restore -- scripts/evidence_resolver.py scripts/scoring_v4/config/quality_score.json \
  scripts/clinical_applicability.py scripts/scoring_v4/modules/generic_evidence.py \
  scripts/scoring_v4/modules/generic_dose.py
git diff --exit-code
```

All experimental production edits were restored. The branch is clean and has no
commits. No focused pytest rung was run because no production change remains;
the evidence is fresh replay output. The integrator's independent full-fast run
at the same baseline completed 17,834 passed, 168 skipped, one existing Ravage
xfail, zero failures.
