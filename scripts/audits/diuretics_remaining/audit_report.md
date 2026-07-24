# Section 1 — remaining diuretic records — audit report

- **reviewer:** `lead_clinician_diuretics_remaining` · **2026-07-24**
- **scope:** the 4 diuretic records left on the coarse `class:diuretics` after
  Sprint 3 (zinc, calcium, thiamine, folate). All 14 PMIDs independently
  content-verified against live PubMed esummary.
- **outcome:** 4 verified · 0 rejected. Every record now drug- or subclass-specific.

## Dispositions

| Record | New scope | Verdict | Key change |
|--------|-----------|---------|------------|
| calcium | `class:loop_diuretics` (NEW) | **verified** (sev→moderate) | loop-only (NKCC2 calciuria; thiazides retain Ca); fracture effect softened to "modest" |
| thiamine | drug `4603` furosemide | **verified** (sev significant) | drug-level furosemide; mechanism corrected to flow-dependent (dropped "protein displacement") |
| folate | drug `10763` triamterene | **verified** (sev→mild, type→functional_antagonism) | reframed: weak DHFR inhibition, routine depletion uncommon, narrowed to pregnancy / low-folate / cirrhosis / co-antifolate |
| zinc | `class:thiazide_diuretics` | **verified** (sev→moderate→mild) | **rescoped loop→thiazide** (Wester RCT: loop much weaker); reframed "increased loss / possible tissue depletion", NOT "deficiency" (serum usually normal) |

## New taxonomy

`class:loop_diuretics` (5 loops: bumetanide, ethacrynic acid, furosemide,
piretanide, torsemide — all RxNorm-verified; C03C). Distinct from
`class:loop_and_thiazide_diuretics` because loop and thiazide handle calcium in
OPPOSITE directions — calcium depletion is loop-only.

## Citation defects fixed

Every original citation was a placeholder or misattribution:
- calcium cited **Quamme 1986 — a *magnesium* paper (PMID 3537199)** for a calcium claim → **misattributed_citation**; replaced with loop→calcium fracture + mechanism PMIDs.
- thiamine, folate, zinc each cited the **Pelton *Drug-Induced Nutrient Depletion Handbook*** (nlmcatalog, not primary) → **placeholder_source**; thiamine also had a generic NIH-ODS fact sheet → placeholder.

Replacements (all PubMed-verified): calcium 16336519 / 26589307 / 7465281 ·
thiamine 1867241 / 14712323 / 16412860 / 10482308 · folate 2490542 / 7286039 /
11096168 · zinc 7001863 / 3595066 / 7446206 / 6152785.

Candidates rejected as not-primary / off-scope (documented in research.md):
Reyes 1983 (review), Golik 1998 (ACE-inhibitor study), Sica 2007 (review).

## Overstatement removed

- Unsupported `adequacy_threshold_*` comparison amounts deleted on all 4 (they
  encoded an efficacy assumption the evidence does not support — Sprint-2 precedent).
- calcium fracture effect softened (adjusted human ORs 1.04–1.67, partly fall-mediated).
- folate: no routine depletion at normal doses (cells up-regulate DHFR).
- zinc: no "deficiency" claim — serum zinc typically normal.

## Propagation

Adds `class:loop_diuretics` to `drug_class_map`, so the section requires an app
propagation PR: rebuild interaction_db.sqlite → new Release asset + hydration pin,
regenerate the med-nutrient artifact, update both parity pins. thiamine/folate are
drug-level (resolve by rxcui, no drug_class_map dependency).
