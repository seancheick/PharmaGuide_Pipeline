# Probiotic label-dose correction — bounded implementation complete

Baseline: candidate `8359facc`, not the released phone catalog. No operational
rebuild, publication, global-weight change or clinical sign-off is authorized here.
Implementation commit: `e8fc7ef08b8523c83ae450cd01a986c05f5c1779`.

## Bounded tasks

- [x] Reproduce citation-to-Dose/Formulation coupling and invented blend shares.
- [x] Separate label-owned identity/measurements from clinical-source approval.
- [x] Remove equal-split CFU inference; retain the existing limited total-disclosure
      floors and exact whole-formula assessment, without assigning strain doses.
- [x] Reject invalid numeric disclosure and duplicate measurement credit; verify
      source ownership and the reported winning dose basis.
- [x] Run targeted real-label replay, then complete read-only corpus impact diff.
- [x] Review regressions, run fast tests, record evidence, commit and push candidate.

The remaining potency-size/diversity rubric and its calibration are not being
declared clinically validated. Existing caps, weights and physical potency bands
stay fixed; invalid source joins and invented allocations do not get grandfathered.

## Root-cause corrections

- The current clinical registry still proves identity; clinical-source approval
  no longer decides whether the label states that identity or measured potency.
  Evidence keeps its independent review and scope gates.
- No equal split of a blend total, no evidence-strength multiplier inside Dose.
  An aggregate amount retains only the existing limited disclosure floor; it
  cannot establish an individual strain's dose. Seed's reviewed native-AFU
  whole-formula path remains separate and unchanged.
- CFU and billion-CFU use one numeric contract across Formulation, Dose,
  Transparency, routing, completeness/readiness, legacy input adapters and the
  exported total, serving-header override and goal-dose gate. Contradictory
  twins, booleans, nonfinite values and a bare `has_cfu` flag cannot manufacture
  a measured amount.
- An individual potency measurement requires the same label owner, strain and
  row-level amount. Identical source projections collapse; conflicting amounts
  fail closed. A daily serving range uses its minimum for physical potency and
  keeps its maximum in metadata; it is not one discrete clinically studied dose.
- One native projection consolidation supplies scoring and export. Duplicate
  reviews cannot win by row order; conflicting review fields remain pending.
  Rejected/inactivated diagnostic flags and explanations survive consolidation.
- Formulation's component is now `identified_strain_codes`, not
  `clinical_strain_codes`. The trade-off export reads the new key with an old-key
  compatibility fallback, never summing both. No Flutter code references this
  internal component key; the public six-pillar contract is unchanged.

Config is `1.1.1-probiotic-label-dose` (fingerprint `18b7ff59dc1c4baa`), within
the unreleased scoring-4.4 candidate. The removed equal-split cap and evidence
multiplier constants are retired; no global weights or remaining numeric bands
are recalibrated. No clinical registry data or clinician sign-off changed here.

## Interpretation and remaining work

Removing fictitious blend allocations can lower a score. Restoring a verified
physical identity despite a citation hold can raise a different component. Those
changes do not establish new clinical benefit, harm or a ranking target.

The larger-CFU/species-count rubric, disclosure overlap, clinical-context
applicability contract, source replacement review and blinded benchmark still
need the decisions documented in the preceding
[rubric review](../probiotic_coverage_2026_09_03/rubric_decisions.md). This batch
closes that review's identity/source-approval coupling item, not its entire
calibration backlog. The label-photo AI draft pilot is a separate Phase 3.

Do not rerun the full operational pipeline to ship this intermediate model.
Release approval remains false until the intended rubric scope is settled and
a fresh export/app candidate passes the actual release gates.

## Verification chronology

- All confirmed defects received failing behavioral assertions first. The new
  regression file covers review independence, ownership, duplicate projections,
  finite numeric validation, daily ranges, aggregate disclosure, export totals,
  completeness/readiness/routing, and the whole-formula native-AFU control.
- Broad fast profile: **12,950 passed, 167 skipped, zero failures** (216.12s),
  before the final two export-only substitutions. Existing skips include missing
  generated-artifact canaries in this isolated worktree, not verified behaviors.
- After those substitutions: final export/probiotic regression profile
  **428 passed, 5 skipped, zero failures** (8.35s), including all 71 new cases
  and the existing builder, ownership, native review and trade-off tests.
- Independent review caught duplicate-review ordering, duplicate export counts
  and lingering raw-total consumers. Each was reproduced before correction;
  final read-only re-review found no remaining actionable blocker in this scope.
- No full/release profile, Flutter build, operational pipeline, upload or
  promotion was run in this dose-correction batch. The previous missing-artifact
  release diagnostic is not rebranded as a passed gate.

Intermediate reports named `*_before_gate_unification.json` preserve the earlier
implementation for comparison; they are not the final candidate proof.

## Final full-corpus impact

`verified_impact.json` records every numeric delta, comparator and final report
hash. The final replay processed **15,415 products** in 328.6s with zero errors;
217 were fully re-enriched, while changed producer lanes and scoring were
recomputed for the rest. Input, implementation and baseline-chain hashes stayed
unchanged throughout. This is not a rebuilt release artifact.

- **215 numeric changes**, all probiotic-only: 130 increases and 85 decreases.
- Formulation changed on 36 products; Dose on 209. Evidence, Transparency,
  Verification and Safety/Hygiene have zero numeric changes.
- Zero route, score-status or score-confidence changes. The source corpus keeps
  15,284 scored, 54 safety-suppressed and 77 not-scored records; the latter are
  not a live app catalog.
- Nineteen tier changes and ten legacy POOR→SAFE verdict changes. The verdicts
  cross the unchanged score/raw-module-score floor; they are not new clinical
  safety findings. This inherited quality-versus-safety vocabulary still needs
  care when reviewing rankings.
- All 42 targeted candidate summaries exactly match the complete replay.
  Adding the final gate/export adapters creates no extra score, route, status,
  confidence or verdict deltas on this corpus; malformed-input regressions prove
  their fail-closed behavior.

Release approval remains **false**. The correctness batch is complete; pending
rubric/clinical decisions and a future operational rebuild/export/app validation
are not being marked complete by these engineering checks.

## Final targeted labels

The final targeted report fully re-enriched 42 labels in 35.1s with zero errors:
41 remained scored and one remained safety-suppressed. All six principal
comparators below were recomputed from their owned cleaned inputs, not blobs.
Scores compare with candidate `8359facc`'s authenticated replay, not the phone's
currently released catalog.

| Exact label | Prior candidate | Dose-corrected candidate |
|---|---:|---:|
| Seed DS-01 Daily Synbiotic (`PG_SUB_35E0BD3374BF494B80FEABE87FC559E7`) | 81.2 | 81.2 |
| Culturelle Digestive Daily (`250851`) | 72.7 | 72.7 |
| Garden of Life Probiotics 100 Billion (`326762`) | 63.8 | 57.4 |
| Nature's Way Fortify Ultra Potency Optima 100 Billion (`327965`) | 69.0 | 63.6 |
| Jarrow S. boulardii + MOS 5 Billion (`307727`) | 62.4 | 62.4 |
| Ritual Synbiotic+ (`299239`) | 56.0 | 55.9 |

Ritual's Formulation restores 12.5→14.3 for physical identities; its Dose changes
5.5→3.6 when unsupported equal shares are removed. Evidence remains 8.0 and the
BB-12 source hold remains intact. Seed's exact whole-formula AFU path is unchanged.

The larger positive-control change, Solgar Advanced Multi-Billion Dophilus
(`79324`), is 66.5→75.8. Its four label-owned 1.25B-CFU rows and 1–2 daily-serving
range previously lost potency credit because the clinical applicability adapter
required one discrete daily dose. Dose now uses the actual minimum, retains the
maximum, and does not claim that the range proves a studied indication. Its
Evidence remains 8.0. This is an engineering correction, not a claim that more
strains or higher CFU inherently improve outcomes.

## External basis checked 2026-09-04

[NIH ODS](https://ods.od.nih.gov/factsheets/Probiotics-HealthProfessional/)
distinguishes viable counts from mass and cautions that higher counts do not
necessarily mean greater benefit. [WGO 2023, section 2.2](https://www.worldgastroenterology.org/UserFiles/file/guidelines/probiotics-and-prebiotics-english-2023.pdf)
states that appropriate doses depend on strain/product and human evidence, not a
universal probiotic dose. These support avoiding invented allocations; neither
source validates PharmaGuide's numeric point values.
