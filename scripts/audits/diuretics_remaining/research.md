# Section 1 — remaining diuretic records (zinc, calcium, thiamine, folate)

Reviewer: `lead_clinician_diuretics_remaining` · 2026-07-24

All PMIDs below independently content-verified against live PubMed esummary
(title/first-author/journal/year match). No hallucinated identifiers.

Taxonomy (app resolver supports both `type:class` via drug_class_map and
`type:drug` by rxcui — 18 existing drug-level entries):

| Record | New drug_ref | Why |
|--------|--------------|-----|
| calcium | `class:loop_diuretics` (NEW, 5 loops) | NKCC2 calciuria is a loop effect; thiazides RETAIN calcium (opposite) |
| thiamine | drug `4603` furosemide | best-documented culprit (mechanism is flow-dependent/class-shared, furosemide-led) |
| folate | drug `10763` triamterene | triamterene-specific DHFR inhibition; not a class effect |
| zinc | `class:thiazide_diuretics` | **thiazide** effect — loop is much weaker (Wester RCT); NOT all-diuretics |

## 1. Loop → calcium — VERDICT: SUPPORTED (verified). Severity → moderate.

Loops inhibit NKCC2 → hypercalciuria → modest long-term fracture risk. Do NOT
overstate: adjusted human fracture ORs are small; part is fall-mediated.
- **PMID 16336519** Rejnmark L, *J Intern Med* 2006 — loop use → fracture; any-fracture OR 1.04 (1.01–1.07), hip OR 1.16; furosemide > bumetanide.
- **PMID 26589307** Corrao G, *Drugs Aging* 2015 — current loop use → hip fracture OR ~1.49–1.67 (81,617 pts); partly fall-mediated.
- **PMID 7465281** Warshaw BL, *Pediatr Res* 1980 — chronic furosemide ~tripled urinary calcium, net-negative balance (mechanism; rodent).
NOT supported: large effect; thiazide extension; deficiency in young/healthy short-term users.

## 2. Furosemide → thiamine — VERDICT: SUPPORTED (verified). Severity: significant (kept).

Best-evidenced here. Mechanism = urine-flow-dependent (NOT protein displacement — correct the old mechanism text). Deficiency emerges with chronic higher-dose use + marginal intake (CHF, elderly).
- **PMID 1867241** Seligmann H, *Am J Med* 1991 — furosemide 80–240 mg/d 3–14 mo: 21/23 CHF pts thiamine-deficient vs 2/16.
- **PMID 14712323** Zenuk C, *Can J Clin Pharmacol* 2003 — dose-response; deficiency 98% at ≥80 mg vs 57% at 40 mg.
- **PMID 16412860** Hanninen SA, *J Am Coll Cardiol* 2006 — deficiency 33% CHF vs 12% controls; urinary loss the only predictor.
- **PMID 10482308** Rieck J, *J Lab Clin Med* 1999 — furosemide 1/3/10 mg IV doubled thiamine excretion, flow-dependent (mechanism, healthy volunteers).
NOT supported: furosemide chemically *unique*; every user becomes deficient; generalizing to other B-vitamins.

## 3. Triamterene → folate — VERDICT: SUPPORTED-BUT-NARROW → REFRAME (verified, severity → mild, type → functional_antagonism).

Real weak DHFR inhibition; routine depletion at normal doses is NOT well supported (cells up-regulate DHFR). Reframe to at-risk groups (pregnancy, low folate, cirrhosis, co-antifolate).
- **PMID 2490542** Sidhom MB, *J Pharm Biomed Anal* 1989 — triamterene competitive DHFR inhibitor (100% at 1 µM); HCTZ none.
- **PMID 7286039** Schalhorn A, *Eur J Clin Pharmacol* 1981 — inhibits human-leukocyte DHFR BUT cells compensate at attainable conc; risk flagged in alcoholic cirrhosis.
- **PMID 11096168** Hernández-Díaz S, *NEJM* 2000 — DHFR-antagonist class in pregnancy → cardiovascular defects RR 3.4, oral clefts RR 2.6 (**pooled** antifolate class, NOT triamterene-isolated).
NOT supported: routine depletion in average patients; NEJM RRs as triamterene-specific; renal folate-reabsorption mechanism (drop it).

## 4. Diuretics → zinc — VERDICT: SUPPORTED-BUT-NARROW, **THIAZIDE-scoped** → REFRAME (verified, severity → mild).

Thiazide effect; loop much weaker (Wester RCT). Increased urinary excretion is SOLID; serum zinc usually NORMAL; tissue depletion suggested but observational. Frame as "increased loss / possible tissue depletion," never "deficiency."
- **PMID 7001863** Wester PO, *Acta Med Scand* 1980 — RCT: thiazides ↑ urinary zinc ~60%; loop/triamterene much less. (loop-vs-thiazide scoping)
- **PMID 3595066** Golik A, *Clin Pharmacol Ther* 1987 — HCTZ(±amiloride) ↑ urinary zinc; serum stayed normal.
- **PMID 7446206** Wester PO, *Acta Med Scand* 1980 — autopsy: liver + muscle zinc lower with diuretics >6 mo (tissue signal; observational).
- **PMID 6152785** Mountokalakis T, *J Hypertens Suppl* 1984 — hair zinc lower after thiazides; serum normal.
NOT supported: zinc *deficiency*; loop-diuretic scope; "all diuretics."
Rejected candidates: Reyes 1983 (PMID 6316570, review); Golik 1998 (PMID 9477394, ACE-inhibitor study, off-scope); Sica 2007 (PMID 17673878, review).

## Outcome
4 verified · 0 rejected. calcium→loop class; thiamine→furosemide; folate→triamterene (reframed weak); zinc→thiazide class (reframed, no "deficiency"). Copy softened to match evidence strength.
