# Fix Sprint 01 — needs_revision → publication-ready conversions

Converts 4 suppressed `needs_revision` entries after content re-verification.
Scope = single-file `medication_depletions.json` edits only (no drug-class
taxonomy change). All citations content-verified against PubMed (title +
abstract read, not existence-checked).

Reviewer: `lead_clinician_fix_sprint_01` · 2026-07-23

| Entry | Before | After | Driver |
|-------|--------|-------|--------|
| DEP_LEVOTHYROXINE_CALCIUM | needs_revision | **verified** | overstated "40%" corrected; tangent claims trimmed |
| DEP_LEVOTHYROXINE_IRON | needs_revision | **verified** | placeholder source → controlled trial; "30–45%" softened; tangents trimmed |
| DEP_OCP_VITAMINB6 | needs_revision | **verified** (downgraded) | evidence established→limited; **dose 25–50 mg cut** (> EFSA 12 mg UL); real source |
| DEP_OCP_FOLATE | needs_revision | **rejected** | depletion premise contradicted by the literature |

## DEP_LEVOTHYROXINE_CALCIUM → verified

Relationship (Ca binds levothyroxine in gut → ↓T4 absorption → ↑TSH) is a real,
well-documented `supplement_interaction`. Sources verified on-topic:
- **PMID 10838651** Singh, JAMA 2000 — 1200 mg elemental Ca w/ LT4 × 3 mo: mean
  free-T4 fell, TSH 1.6→2.7 mIU/L, 20% of patients above-range TSH.
- **PMID 11716045** Singh, Thyroid 2001 — acute: LT4 absorption 83.7%→57.9% with
  2 g Ca.

Defects fixed:
- clinical_impact said "reduces … by up to **40%**" — not what either study
  shows (~12% mean free-T4 drop; ~26 pts acute at a large 2 g dose). Corrected
  to the honest study figure.
- Removed the tangential "over-replacement depletes bone calcium" / "hyperthyroid
  states increase urinary calcium loss" claims — a different mechanism, not the
  cited Ca–LT4 interaction, and uncited.

## DEP_LEVOTHYROXINE_IRON → verified

Real `supplement_interaction` (iron chelates levothyroxine → ↓absorption).
Placeholder NIH-ODS Iron fact sheet replaced with the primary controlled trial:
- **PMID 1443969** Campbell, Ann Intern Med 1992 — 300 mg ferrous sulfate + LT4
  × 12 wk: TSH 1.6→5.4 mU/L (P<0.01), 9/14 symptomatic; in-vitro iron–T4 complex.

Defects fixed:
- "reduces absorption by up to **30–45%**" — an unsupported precise figure;
  softened to the trial's actual finding ("variable reduction, clinically
  significant in some patients").
- Removed tangents (hypothyroidism impairs iron absorption; IDA impairs
  thyroperoxidase) — true but out of scope for this interaction entry, uncited.

## DEP_OCP_VITAMINB6 → verified (downgraded, dose cut)

- **PMID 21967158** Wilson, Nutr Rev 2011 — "current low-dose OCs **may**
  negatively impact vitamin B6 status" (↓plasma PLP); the practical concern is
  **pre-pregnancy adequacy** in women who stop OCs and conceive soon. Evidence
  is population-level and cautious → evidence_level established→**limited**,
  severity significant→**moderate**.
- **Safety fix (UL gate):** old copy recommended **25–50 mg B6** — above the
  EFSA 12 mg/day UL; chronic high-dose B6 causes peripheral neuropathy. Rewritten
  to "a standard multivitamin / normal diet provides adequate B6; high-dose B6 is
  not recommended." No hard mg number → passes `test_med_nutrient_ul_safety`.
- Removed the speculative "OCP mood symptoms may reflect B6 depletion" (Wilson
  does not establish it).

## DEP_OCP_FOLATE → rejected

- **PMID 21967158** Wilson, Nutr Rev 2011 — "the presently available data **do
  not support** a conclusion that currently used OCs negatively impact folate
  status"; the older depletion evidence used higher-estrogen pills and lacked
  controls.
- The entry asserted an **established** folate depletion — directly contradicted
  by the literature for modern formulations → `rejected` (not published as a
  drug-nutrient depletion). Preconception folate adequacy remains standard
  prenatal guidance independent of OCP use, and belongs there, not here.

## Citations added/kept (all PubMed-verified this sprint)
- 10838651, 11716045 (levo-Ca, kept) · 1443969 (levo-Fe, added) · 21967158
  (OCP-B6 + OCP-folate, added)
