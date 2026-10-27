# Magtein source contexts and exact CogniMag verification — October 26, 2026

Owner: `scripts/data/backed_clinical_studies.json::BRAND_MAGTEIN`, existing `clinical_applicability.py`/ingredient-context owners; exact label repair through `scripts/data/curated_overrides/product_label_corrections.json::299037` and `enhanced_normalizer.py::_apply_label_corrections`. Will NOT create a new scorer, registry, preparation-equivalence rule, dose curve or approval authority.

## Signed source decisions applied

Sean attests Dr. Pham signed the explicit A011 source decisions and supplies October 26, 2026 as their review date. The exact date is preserved without invented clock time. This approves only the bounded recorded relationships; retail correspondence and other A/B decisions do not inherit blanket acceptance.

Three contexts cover every retained reference, with the correction kept beside its original trial:

- **39252819 +40567408:** Magtein capsules, 1,000 mg compound/day (approximately75mg elemental magnesium), together before bedtime for21days;80 adults aged35–55 with sleep problems,76 analyzed. Mixed selected sleep/daytime-function findings; important ISI/LSEQ/restorative-sleep nulls preserved. Correction records retrospective registration, AIDP commissioning/funding/patents and paid-author relationships; it is not another cohort.
- **41601871:** Magtein1g morning and1g evening,145mg elemental magnesium/day,42days;100 adults aged18–45 with dissatisfied sleep. Preliminary NIH cognitive-composite and subjective sleep-impairment findings; Raven/objective-sleep/other nulls retained. The [October15 publisher correction](https://www.frontiersin.org/journals/nutrition/articles/10.3389/fnut.2026.2010644/full) was checked live: tests were two-tailed and results unchanged. The stale PMC one-tailed sentence must not be used to alter p-values. No biological age reversal, dementia prevention or longevity inference is accepted.
- **36558392:** separate MagteinPS whole-formula context, nominal2g formula/day for30days,109 randomized healthy Chinese adults/102 completed. Four capsules provide1,600mg Magtein,200mg phosphatidylserine,48mg vitaminC,320IU vitaminD3 and16mg vitaminB6. Both the context and reference are explicitly ineligible to support **isolated Magtein** efficacy. Composition, whole-formula result and source history remain present.

The existing `tier_1` grade is retained provisionally; descriptive direction is corrected from `positive_strong` to `mixed` under the explicit mixed source decisions. The existing multiplier can change Evidence points; integrated real-product replay measures that effect. Source-level acceptance does not independently establish a broad positive grade or retail-product applicability. Key endpoint text now states preliminary cognition/mixed sleep/whole-formula distinctions rather than implying age reversal. The unsupported Healthy Aging/Longevity benefit qualification is removed under the signed no-age-reversal/no-longevity interpretation; Focus & Mental Clarity and Sleep Quality remain, with their stated limits. BCM-95 control goals remain unchanged.

## Source receipts

Re-read original full-text XML hashes against retained receipts:

| Source | SHA256 |
|---|---|
| Returned batch2 | b965b62d6602b3c061fa209be2a78582e98f801b5df0cd1d2459ef63ed616665 |
| PMC11381753 /39252819 | e2dfcdc2e61fcb0eba5bbb79086423de16e434e1825daa78c08a4801e0713d9f |
| PMC12832366 /41601871 | 4f2c0b8319bca064e69e8239c0fd5c616204ecc4315a8f673a4cc7b2f221ca25 |
| PMC9786204 /36558392 | 783c1aaa538e1cb5a638871d03481d153406ad4413ec91121732ae0e7d44d91e |

Correction40567408 body and original API verification are retained in the earlier signed/batch2 verification receipts; the context carries their amended disclosures. Publisher correction2010644 explicitly supersedes the stale indexed statistics sentence. No extra trial is counted.

## Exact-label discrepancy299037: existing repair independently confirmed

The [live NIH API](https://api.ods.od.nih.gov/dsld/v9/label/299037) crosses the Magnesium/Magtein names relative to their quantities. The [original CGM21V3 PDF](https://api.ods.od.nih.gov/dsld/s3/pdf/299037.pdf), retrieved and visually inspected October26, prints **72mg elemental magnesium from1000mg Magtein per two capsules**, taken twice daily.

The existing curated correction already swaps the two row names and removes the unsupported elemental UNII from the1000mg source-material row. Real current normalization produces1000mg Magtein at ingredientRows[0] and72mg Magnesium at its child, with two capsules twice daily. The resulting144mg elemental/day and2000mg complex/day are already correct. Source paths are provenance, not a reason to reinterpret the corrected semantic row.

An attempted quantity-swap replacement was rejected by the existing hierarchy regression. It was withdrawn, the exact299037 entry was restored to HEAD, and its new unnecessary fixture/test were removed. There is no runtime correction to299037 in this batch. The existing targeted hierarchy regression plus the four source-context tests pass (5 tests). This records an investigation correction, not a newly fixed production defect.

PDF SHA256: `a0f8b96565dfa94bcb97c93b16e068440054e7b50a70482810950ef9c67db256`. Original current API/PDF/PNG retained in `.claude/state/clinical_context_migration_20261026/`.

## Exact correspondence limits

Source API inspection confirms the eleven editions exist and exposes specific questions rather than requesting another generic review:

-182334/232311 are powders, whereas the accepted isolated trials used capsules; no automatic delivery equivalence is invented.
-269596 discloses2085mg complex/day, distinct from a2g nominal tested regimen.
-315679 includes nominal2g/day, first-week1g at night and warnings permitting an absolute4g/day maximum; retain those distinct directions, not an invented continuous efficacy range.
-299037 already receives the source-bound crossed-hierarchy repair; do not request a duplicate correction or treat raw API values as current normalized quantities.
-Other named Magtein declarations, co-actives and schedules remain available in the retained exact API responses; a brand-name match alone does not establish population, purpose or outcome correspondence.

No twelve-/eleven-product clearance follows from source extraction. Direct source owner now validates both isolated Magtein contexts, but product applicability still reports `not_curated/no_reviewed_scope_constraints` until the existing owner receives supported exact scope. No corpus rerun, export, app update or publication is performed by this subtask.

Final source-context/schema/applicability slice:225passed in13.30seconds before the final unsupported-goal removal. The new unsupported-goal assertion failed first, then all four focused returned-context tests passed after removal. Data-batch entry census reports exactly BCM95 and MAGTEIN at this checkpoint; no299037 runtime diff remains. Integration owns final combined tests, real-product replay and CI.

Final rationale/register reconciliation: historical no-approval wording is qualified as the earlier source-screen state; current text recognizes the scoped October26 signed decisions while explicitly retaining the broad grade as provisional and unvalidated. Only the Magtein row of the existing clinical register records its source-context pass, actual signed date and residual product/grade scope. Five focused returned-context tests pass after the fail-first stale-rationale regression. The146-subject denominator and all other register rows remain the integrator's current reconciliation, not wholesale closure.

The stale Magtein owner regression now checks both approved isolated trial families, correction pairing and whole-formula exclusion; it no longer expects a missing-context hold after migration. Direction regression failed first at positive_strong versus mixed. All six focused context/source-role checks pass after the source-direction correction. No scoring weight or numerical grade was invented.
