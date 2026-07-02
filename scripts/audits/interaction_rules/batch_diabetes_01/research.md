# Batch diabetes-01 — direction / materiality / floors (verified)

**Date:** 2026-07-02
**Scope:** 5 diabetes-cluster ingredients (complaint-drivers + every edge of the model).
**Verification:** opus medical-verification pass against NIH ODS (Health Professional fact sheets),
NCCIH, MSKCC About Herbs, and PubMed (content-checked). No hallucinated identifiers.

## Honesty flags (govern authoring)
1. **Only niacin has a guideline-stated glucose floor.** NIH ODS: nicotinic acid ≥1.5 g/day is
   where hyperglycemia becomes likely. Chromium / berberine floors are *inferences* from published
   dose ranges (documented as such in the `rationale`), NOT guideline no-effect cutoffs. ALA has no
   defensible numeric floor from the sources retrieved.
2. **Niacin form-gating required.** The glucose effect is specific to **nicotinic acid**; NIH ODS
   does not attribute it to **nicotinamide/niacinamide**. The floor+direction must exclude
   niacinamide forms or it will over-warn on the common multivitamin form.

## Per-ingredient decisions

| Ingredient | direction | materiality | floor (per_day) | confidence | source |
|---|---|---|---|---|---|
| Niacin (nicotinic acid) | harmful (raises glucose) | dose_dependent | **1500 mg** (guideline cutoff) | high | NIH ODS Niacin |
| Chromium (picolinate) | harmful (weak/additive) | dose_dependent | **200 mcg** (inferred: top of supplemental range, below trial doses) | medium | NIH ODS Chromium |
| Alpha-lipoic acid | harmful (lowers, additive) | dose_dependent | **none — floor unverified → fail-open (fires)** | medium (dir) | MSKCC; PMID 41077538 |
| Magnesium | **beneficial** | presence | no floor | high | NIH ODS Magnesium |
| Berberine | harmful (lowers, additive, potent) | dose_dependent | **900 mg** (inferred: below lowest effective RCT range ~900–1500 mg) | medium-high | PMID 34956436; 23118793 |

### Niacin — RULE_IQM_NIACIN_DIABETES
- direction=harmful, materiality=dose_dependent, floor=1500 mg/day (nicotinic acid).
- NIH ODS: "nicotinic acid doses of 1.5 g/day or more are most likely to increase blood glucose
  levels"; supplemental UL 35 mg/day; monitoring advised on antidiabetes meds at high-dose nicotinic acid.
- **Form-gate:** exclude nicotinamide/niacinamide (no glucose effect).
- Existing rule already states "Low-dose niacin in multivitamins is not a concern" — floor makes that structural.
- Existing dose_threshold escalation is at 1000 mg (>1000 → avoid); suppression floor is the verified 1500 mg.

### Chromium — RULE_IQM_CHROMIUM_GLUCOSE
- direction=harmful (additive with insulin/metformin per NIH ODS), materiality=dose_dependent, floor=200 mcg/day.
- NIH ODS: AI 25–35 mcg/day; supplements 200–1000 mcg; effect concentrated at high doses; clinical
  significance "unclear". 200 mcg = top of typical multivitamin range, below the trial doses.
- **Rationale is an inference, not a stated cutoff** (confidence medium). Directly fixes the ~120 mcg
  multivitamin complaint (120 < 200 → suppressed).

### Alpha-lipoic acid — RULE_IQM_ALPHA_LIPOIC_ACID_DIABETES
- direction=harmful (lowers glucose, synergistic with hypoglycemics — MSKCC), materiality=dose_dependent.
- **No numeric floor authored** — sources give effective range (300–600 mg) but no validated
  below-which-immaterial cutoff. Fail-open (fires) until a floor is verified in a later batch.
- Existing dose_threshold escalation stays at 600 mg (severity only, does not suppress).

### Magnesium — (diabetes condition_rule)
- direction=beneficial, materiality=presence, no floor. Routes to the support surface, not review.
- NIH ODS: 100 mg/day higher intake → 15% lower diabetes risk (associational). **Copy must stay
  hedged** — ADA says insufficient evidence for routine glycemic use; benefit is strongest for
  dietary mg and prospective data. No mg–antidiabetes-drug hypoglycemia interaction documented.

### Berberine — RULE_IQM_BERBERINE_DIABETES
- direction=harmful (potent glucose-lowering, additive — meta-analyses), materiality=dose_dependent, floor=900 mg/day.
- PMID 34956436 (HbA1c −0.73%, FPG −0.86 mmol/L; "adjunctive"), PMID 23118793 (berberine + oral
  hypoglycemic > drug alone). Effective ~900–1500 mg/day → 900 mg is a conservative effective-range
  floor (**inference, not a no-effect cutoff**; confidence medium-high).
- Separate PK interaction (berberine/goldenseal lowers metformin ~25%, NCCIH) is out of scope for
  this additive-glucose batch — capture later.

## Sources (content-verified)
- NIH ODS Niacin — https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional/
- NIH ODS Chromium — https://ods.od.nih.gov/factsheets/Chromium-HealthProfessional/
- NIH ODS Magnesium — https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/
- NCCIH Goldenseal — https://www.nccih.nih.gov/health/goldenseal
- MSKCC About Herbs, Alpha-Lipoic Acid — https://www.mskcc.org/cancer-care/integrative-medicine/herbs/alpha-lipoic-acid
- PMID 34956436 — Berberine meta-analysis, Oxid Med Cell Longev 2021 (doi:10.1155/2021/2074610)
- PMID 23118793 — Berberine meta-analysis, Evid Based Complement Alternat Med 2012 (doi:10.1155/2012/591654)
- PMID 41077538 — ALA dose-response meta-analysis, Nutr Metab Cardiovasc Dis 2025 (doi:10.1016/j.numecd.2025.104370)

## Authoring status
- [ ] Emission + suppression infra (enrich/build) — walking skeleton with niacin first
- [ ] Niacin authored + form-gated + tested
- [ ] Chromium / berberine floors + magnesium beneficial + ALA (no-floor) authored + tested
- [ ] Atomic commit `batch diabetes-01`
