# Omega Dose review before the next pipeline run

**October 17, 2026 — analysis and policy proposal only. No scoring/config/clinical data changes, corpus run or publication.**

## Conclusion

**Requiring 2,000 mg EPA+DHA for full Dose credit is not justified as an ordinary-adult general-nutrition requirement.** The calculation works as authored, but the authored scale combines different purposes. It awards ordinary adult products more points for reaching a triglyceride-related amount, even when that is not the product's assessed purpose.

This is a shared calibration problem, not a brand-specific error, an EPA/DHA unit error, or justification for changing individual product scores manually. The recent declared-serving correction makes the amount basis consistent; it does not validate the old dose curve.

Recommendation: settle this omega policy before Sean's next necessary pipeline run. A pipeline rerun cannot repair a policy that still tells the scorer to reward larger amounts.

## 1. What current code actually does

Source inspected: engine 4.6.0, config 1.27.0-declared-serving-dose, checkout HEAD b043fc513d3d90e7f0258cb48af232430b8fb873. This is a local source observation, not a fresh claim about remote branch state. Existing documentation edits are uncommitted; no runtime edits were made for this review.

Owner Check:

- Owner: `scripts/scoring_v4/modules/omega_dose.py::score_dose` and `_band_score` — amount credit and interpolation; read `scripts/data/omega_rubric.json` through the validated rubric loader.
- Owner: `scripts/scoring_v4/modules/generic_helpers.py::score_declared_serving_dose` — one declared serving for quality, with original daily safety retained separately.
- Owner: `scripts/scoring_v4/quality_score.py::_pillar_dose` — raw-to-public normalization, omega reference 20.
- Owner: `scripts/evidence_resolver.py::resolve_omega_evidence_standard` — assessed omega purpose and applicability for Evidence, already distinguishes ordinary adult, prenatal and triglyceride context.
- Evidence: matrix `quality_pillars_v4_contract`, glossary “Omega purpose evidence,” source/caller inspection, current rubric and tests, manifest-owned stored-input screen and representative full scored-artifact calls.
- Will NOT create: a second scorer/purpose resolver, supplement regimen advice, clinical threshold, safety status or new persisted/public field.

| EPA+DHA per declared serving | Current Dose points |
|---|---:|
| 100 mg | 2.5/20 |
| 200 mg | 4/20 |
| 250 mg | 5/20 |
| 500 mg | 10/20 |
| 750 mg | 13/20 |
| 1,000 mg | 16/20 |
| 2,000 mg | 20/20 |
| 4,000 mg | 20/20, with prescription-dose context flag |

Positive anchors interpolate. Below 100 mg receives zero. The ordinary adult path does not select a different Dose target based on nutritional versus triglyceride purpose. There is an existing prenatal DHA exception, which must not be swept into an adult combined-EPA/DHA change.

The rubric's own source note attributes the 2,000 mg full-credit anchor to the triglyceride claim. Git history identifies `dfa5aa540` (June 5, 2026, “give full omega dose credit at 2000mg”) as the change from 17.5 to 20 at that anchor. The contemporary test calls it a “high-clinical consumer dose.” Those are historical calibration decisions; neither establishes that 2 g is a general-health requirement.

**The mismatch:** Evidence distinguishes product purpose, but ordinary omega Dose uses one higher-is-better curve spanning nutritional intake and triglyceride amounts. Generic source names such as `general_health` or `aha_cvd` are band labels, not proof that the product was assigned to the matching indication.

## 2. What the primary sources support

### General nutrition reference

EFSA's adult adequate intake is **250 mg/day EPA+DHA combined**. Its 2022 nutrient-profiling opinion reiterates that reference. It describes dietary intake, not a universal prescription for a supplement, a measured optimum for every individual, or a guarantee of disease prevention.

Sources: [EFSA 2010 dietary reference opinion](https://www.efsa.europa.eu/en/efsajournal/pub/1461), [EFSA 2022 nutrient-profiling opinion](https://efsa.onlinelibrary.wiley.com/doi/abs/10.2903/j.efsa.2022.7259).

The United States does not have a specific EPA/DHA RDA or AI established by the IOM/NAM; the adult omega-3 AI refers to ALA. Using the EFSA reference would therefore be an explicit PharmaGuide policy choice grounded in a named authority, not “the universal RDA.” Food contributes to total intake. PharmaGuide cannot infer the user's nutritional shortfall from the bottle.

Source: [NIH ODS professional fact sheet, Recommended Intakes](https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/).

### Why 2 g appears in the rubric

The EU authorizes a **normal blood-triglyceride maintenance claim** with a daily intake condition of 2 g EPA+DHA. That is an endpoint-specific claim condition. It is different from an ordinary adult nutritional target and different again from proving treatment equivalence for an OTC supplement.

Source: [EU authorized health-claims regulation, consolidated August 2024](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=consolidation%3A2012R0432%2F20240819_0110010).

For clinical management of elevated triglycerides, the AHA advisory addresses **4 g/day prescription omega-3**, with reductions around 20–30% in the assessed population. It explicitly distinguishes prescription products from dietary supplements. A treatment dose or a change in triglycerides cannot be translated into greater general-health benefit for every purchaser.

Source: [AHA scientific advisory summary, August 19, 2019](https://professional.heart.org/en/science-news/omega-3-fatty-acids-for-the-management-of-hypertriglyceridemia/top-things-to-know).

### Outcome evidence does not establish a universal rising benefit curve

VITAL randomized 25,871 participants and tested a 1 g fish-oil capsule containing 840 mg EPA+DHA daily. It did not significantly reduce its primary major-cardiovascular-event or cancer outcomes; a myocardial-infarction secondary outcome was more favorable. This does not prove absence of every benefit. It does undermine treating each larger amount as established additional general-health benefit.

Source: [VITAL original trial](https://www.nejm.org/doi/full/10.1056/NEJMoa1811403).

ASCEND likewise found no significant reduction in its primary serious vascular-event outcome with daily 1 g omega-3 capsules in participants with diabetes but no known cardiovascular disease. This population is not interchangeable with all healthy adults.

Source: [ASCEND original trial](https://www.nejm.org/doi/full/10.1056/NEJMoa1804989).

STRENGTH tested a specific 4 g/day omega-3 carboxylic-acid formulation in high-risk, statin-treated patients: no significant reduction in the primary cardiovascular composite and more investigator-reported atrial fibrillation. Do not extrapolate that result into a new universal hazard threshold at 250, 500 or 2,000 mg, or into an automatic deduction for every fish oil. It does show why larger amount and greater benefit are separate propositions.

Source: [STRENGTH original trial](https://jamanetwork.com/journals/jama/fullarticle/2773120).

## 3. Real-input checks

Read-only probe: all 15,426 products from manifest-owned stored enriched files screened. Of those, 715 classify as omega; 431 select the ordinary-adult explicit-EPA+DHA Evidence context. Among those 431:

| EPA+DHA per serving | Stored input count |
|---|---:|
| <250 mg | 56 |
| 250–<500 mg | 40 |
| 500–<1,000 mg | 201 |
| 1,000–<2,000 mg | 117 |
| ≥2,000 mg | 17 |

**358 ordinary-adult inputs provide at least 250 mg but earn less than full raw Dose credit under the current curve.** This is input-screen coverage, not a claim that all 715 pass every final completeness/publication gate. “Ordinary adult” here means the current resolver's explicit-EPA+DHA context, not a clinician's finding that a particular user is healthy or needs the product.

Representative complete production scored-artifact calls confirm the pathway:

| DSLD ID | Label name | EPA+DHA/serving | Current public Dose | Current analytical total |
|---|---|---:|---:|---:|
| 11609 | Omega Complex | 300.1 mg | 6.0 | 50.5 |
| 252500 | Fish Oil Softgel 1000 mg | 563 mg | 10.8 | 66.4 |
| 203390 | Purified & Clear Omega 3 Fish Oil 1000 mg | 1,200 mg | 16.8 | 66.7 |
| 4283 | Oceans 3 Beyond Omega-3 Cod Liver Oil Orange Tangerine Flavor | 2,745 mg | 20.0 | 64.4 |

These are different formulas, so their total scores do not isolate dose or prove a brand ranking. The Dose column specifically reproduces the quantity advantage. All four receive 10.4 Evidence under the same ordinary-adult standard. The “1000 mg” product-title strings do not substitute for resolved EPA/DHA amounts.

Preserved controls include prenatal DHA (20 Dose /11.1 Evidence in example 82381), DHA-only held Evidence (example 12944), child-population hold, mixed-purpose hold and specialized preparation hold. Eleven representative full-artifact calls completed, including one duplicated ordinary-adult example serving two selection groups. No candidate policy was executed.

Reproducible local evidence: `reports/omega_dose_review_20261017/probe.py`, `probe.log`, `screen.json` (source hashes, all input rows, current context/amount/credit and representative artifacts). These stored inputs predate the required serving-policy pipeline regeneration. This is a current-source diagnostic, not a replacement corpus run, current deployed output or release approval.

## 4. Recommended correction for approval

**Separate “enough for the assessed purpose” from “contains more.”**

For ordinary-adult general-nutrition scoring, I recommend a reviewed **250 mg EPA+DHA reference contribution per declared serving**, with full amount-adequacy credit at that reference and no extra positive credit above it. This is an explicit reference-based product-comparison calibration. It does not claim that the supplement is necessary, that one serving meets every person's complete needs, or that the studies measured a 20-point clinical benefit.

A concrete candidate for measurement is:

```text
ordinary adult nutritional Dose, before applicable safety adjustments:
    20 × min(disclosed EPA+DHA per serving / 250 mg, 1)
```

This would give 100 mg →8, 200 mg →16, 250 mg →20, and 500/1,000/2,000 mg →20 before independent safety handling. The new low-dose ramp and removal of the old <100 mg zero cliff are part of this proposal, not implied approvals. If the team wants to retain a trace threshold, that also needs an explicit rationale rather than inheriting a threshold whose only justification was avoiding “inflation.” Neither the exact partial-credit slope nor 20 points is a number derived from a trial.

Do not apply that formula to every omega input unconditionally:

- Preserve an explicitly supported prenatal DHA standard, not combined EPA+DHA as a surrogate for DHA.
- Retain honest unassessed/held population, identity and preparation cases. A held Evidence state does not automatically mean Dose must be zero or that the product is poor.
- A label's triglyceride wording alone must not authorize general treatment equivalence or a scoring shortcut. Use the existing purpose owner; a therapeutic comparator requires an explicit supported purpose, preparation, population and benchmark. A separate treatment-suitability assessment is preferable to silently changing ordinary product ranking because of a marketing sentence.
- Preserve maximum labeled daily-use warnings and their source-grounded applicability. No invented high-dose penalty at 500 mg and no loss of safety warnings when an adequacy curve plateaus.
- Keep other pillars, certification policy, ingredient identity, form ratings and existing EPA/DHA mass ownership unchanged.

**Interpretation:** once the amount is adequate for the selected reference purpose, formulation, verification, transparency and evidence should distinguish products. More milligrams can remain a useful disclosed fact without automatically being a better quality score. Concentration already has its own bounded Formulation credit; do not award another arbitrary dose premium for the same marketing advantage.

## 5. Implementation and run boundary

No policy has been silently applied. This request was to analyze the rule. AGENTS.md reserves new scoring/clinical policy to Sean; the existing scoring-change skill also requires a decision before editing such a rule. This report makes the proposed change reviewable before that decision.

After approval, complete one bounded omega batch through the existing owners: fail-first public-seam regressions, purpose/amount boundary and held-context cases, existing dose warning controls, source/config version and fingerprint history, captured before/after scores for affected omega labels and non-omega controls, raw canaries and independent review. Inspect all six pillars, quality/assessment/safety states, warnings and tier changes separately. A shared-cause score rise is expected, but an unexplained safety/identity change is not.

Only then finalize the pipeline command and required start stage using the actual fingerprints. The already-integrated serving change previously required Clean → Enrich → Score; this analysis does not make those old artifacts current. Sean still runs the pipeline. This review did not trigger the expensive pre-check, full suite, corpus run, catalog publication or IPA build.


## October 18 independent re-audit — refine before approval

Audited current main `60d8ea0e2655a9c4ad3c34259428f47e1e4fa4c1`, including the merged architecture batch. This section refines the proposal above; no runtime/config/clinical data change or corpus run was made.

**Recommendation: retain the adult 250 mg reference-contribution plateau, but approve and validate the complete omega boundary rather than changing the band table alone.** The curve is a product-comparison convention grounded in an intake reference. It is not a clinical efficacy curve, universal supplement requirement or personal recommendation. EFSA's adult AI is daily total intake, including food; NIH confirms that NAM has not set a separate EPA/DHA intake recommendation. The 2 g EU condition concerns maintaining normal triglycerides; AHA's treatment advisory concerns prescription preparations at 4 g/day. These are distinct uses. Live sources rechecked October18: [EFSA](https://www.efsa.europa.eu/en/efsajournal/pub/1461), [NIH ODS](https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/), [EU claim conditions](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=consolidation%3A2012R0432%2F20240819_0110010), [AHA advisory](https://professional.heart.org/en/science-news/omega-3-fatty-acids-for-the-management-of-hypertriglyceridemia/top-things-to-know).

Current-source checks verified all58input-file hashes and repeated Dose/context resolution for all715omega inputs with zero differences from the October17probe.431are ordinary-adult explicit-EPA+DHA cases;358provide250–<2000mg and receive less than full Dose credit. These remain stored-input diagnostics, not rebuilt output.90named tests passed across omega Dose, prenatal Dose, purpose evidence, declared-serving and amount ownership. Receipts: `reports/omega_dose_review_20261017/reaudit_20261018.json`.

### Findings that the original proposal did not close

1. **Prenatal is not an already-validated exception to preserve blindly.** `omega_dose::score_dose` awards10/20for any positive DHA below100mg; a1mgDHA probe receives10. The general curve can also bypass DHA adequacy: prenatal EPA1999mg+DHA1mg receives20/20. Flattening that general curve to250mg without exclusive prenatal selection would expand this problem. Recommend a DHA-specific reference-contribution assessment, using the existing200mg additional-DHA anchor as an explicitly selected comparison reference, with proportional partial credit and no combined-EPA/DHA override. EFSA describes additional100–200mgDHA on top of adult intake; do not claim200mgDHA alone meets all pregnancy needs. NIH's ACOG entry recommends seafood intake, not the code comment's attributed200–300mg target. Correct that attribution with the policy. Do not infer individual preterm-birth benefit or a need for600–1000mg from a product label.

2. **A therapeutic marketing sentence currently upgrades Evidence.** Appending only `EPA and DHA help lower triglyceride levels.` to stored product11609 (300.1mg/serving) changes the selected record from ordinary-adult to triglyceride-strong and public Evidence10.4→20. `evidence_resolver::resolve_omega_evidence_standard` intentionally uses the claim as a purpose switch; an existing test explicitly pins this even at250mg. This is a policy/applicability concern, not a newly introduced code regression. A claimed purpose does not establish the preparation/population match needed for therapeutic product credit. Keep Evidence strength separate from amount adequacy, but do not let a label sentence alone grant the strongest product evidence or silently determine a favorable Dose target. No therapeutic-purpose case occurs in the715stored rows; this is a controlled adversarial probe.

3. **The same sentence falsely discloses molecular form.** `normalization::omega_molecular_form_disclosures` has a health-claim exclusion but misses lowering/reducing language. `_detect_form` then passes the false TG disclosure to Transparency:6.8→10.9. Together with Evidence, total score rises50.5→64.2; Dose and the other pillars remain unchanged. This is a source-owner parsing defect. Fix the shared normalization rule and its enrichment/presentation consumers, retaining actual TG/rTG declarations and MCT exclusion; a dashboard or scorer-only filter would leave enrichment inconsistent.

4. **The internal prescription-dose flag does not prove user-visible warning coverage.** The literal is emitted in omega Dose metadata and tested there; no direct exporter/Flutter reader was found. Preserve and verify the real daily-exposure/safety path, including user-visible warnings, separately from the capped nutritional score. Do not infer a new safety limit from250mg or invent a penalty above it. STRENGTH's4g/day high-risk population result is not a universal lower-dose hazard threshold ([original trial](https://jamanetwork.com/journals/jama/fullarticle/2773120)).

### Bounded policy and implementation recommendation

- Ordinary adult nutritional reference: `20 × min(max(disclosed EPA+DHA per declared serving, 0) / 250, 1)`, before applicable existing safety deductions.0→0,100→8,200→16,250and above→20. The linear ramp/20-point mapping is PharmaGuide calibration, not a measured treatment response. No inherited100mg cliff.
- Prenatal-DHA reference: explicit DHA assessment as described above; no adult-curve maximum fallback. Keep other populations, specialized preparations and identity holds distinct. An Evidence hold must not automatically mean zero Dose; combined-only and pure-component quantities need explicit eligibility cases at the shared amount/purpose owner, without inventing EPA/DHA breakdown or ratios.
- Therapeutic claims: record the claim, but require independently supported applicability for strong product evidence; do not transfer prescription findings to an OTC product merely because the sentence exists. No new treatment-ranking feature is needed for this batch.
- Fix the shared molecular-form false positive, align consumer explanations with the named reference and preserve the actual safety pipeline. Full nutritional Dose credit must never read as proven disease prevention, complete personal adequacy or a safety clearance.

After Sean selects this policy, implement one bounded owner-based batch with failing regressions for these cases; score frozen affected labels and unaffected controls through the full public seam; inspect all six pillars, identities, safety/assessment states, warnings, receipts and tiers; perform independent review plus required CI/local validation. Existing held populations must not acquire adult credit accidentally. Reinspect stage fingerprints, then perform the single necessary corpus pass. A configuration-only250mg edit is not ready for that pass.
