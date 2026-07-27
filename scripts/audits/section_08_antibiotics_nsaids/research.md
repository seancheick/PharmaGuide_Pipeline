# Section 8 — antibiotics and NSAIDs review

Reviewed: 2026-07-26

| Record | Decision | Basis |
| --- | --- | --- |
| `DEP_NSAIDS_FOLATE` | Rejected | A handbook-only, broad NSAID claim and high-concentration mechanism do not support a consumer folate-depletion alert. |
| `DEP_NSAIDS_IRON` | Needs revision; suppressed | NSAID-associated GI bleeding can cause iron-deficiency anaemia, but the current all-NSAID nutrient-supplement alert lacks a dose, duration, and bleeding-risk scope. This must be authored as a clinical bleeding-risk rule, not as blanket iron supplementation. |
| `DEP_NSAIDS_VITAMINC` | Rejected | No claim-matched clinical citation supports routine aspirin/NSAID vitamin-C depletion or supplementation. |
| `DEP_ANTIBIOTICS_BVITAMINS` | Rejected | Antibiotics alter microbiota, but no evidence supports a short-course broad-antibiotic B12 depletion alert. The synthetic non-RxCUI subject cannot reach the runtime. |
| `DEP_ANTIBIOTICS_VITAMINK` | Needs revision; suppressed | Vitamin-K coagulopathy is a narrow, high-risk scenario (for example malnutrition/malabsorption or selected cephalosporin side chains), not a universal post-antibiotic K2 recommendation. The synthetic subject cannot reach the runtime. PMID 37763117 is a case report/narrative review, not broad consumer-claim evidence. |

## Live source checks

- PMID 37763117: case report and narrative review; reports possible broad-spectrum-antibiotic microbiota effects but emphasises underlying malnutrition/malabsorption and selected cephalosporin chemistry.
- PMID 35417701: healthy-adult study establishes antibiotic microbiome disruption, not B12 deficiency or B-complex supplementation.
- PMID 28242110: peptic-ulcer review is relevant to NSAID GI injury, but it is not an all-NSAID iron-depletion/supplement-dosing trial.

No taxonomy release is appropriate: no broad antibiotic class is promoted until its RxNorm members and clinical scope are separately verified.
