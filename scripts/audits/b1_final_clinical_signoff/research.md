# B1 final clinical-content review — research record

Review date: 2026-07-27
Scope: the 33 records that were consumer-visible at artifact hash
`sha256:98259507ef920a503084f748b11c9bbcc1d7ec7fabdadb9d3d7326610bef2753`.

This is an AI clinical-content audit. It does not claim pharmacist licensure.

## Verification method

- Every cited PMID was re-resolved through the live NCBI E-utilities API and
  its title/abstract was compared with the medication, nutrient, mechanism,
  impact, and recommendation.
- Current NIH ODS, DailyMed, MHRA, ADA 2026, and ACR guidance was used where
  the consumer recommendation depended on current monitoring or label advice.
- Direct release identities were re-resolved through the live RxNorm API:
  warfarin `11289` = IN; prednisone `8640` = IN.
- Runtime drug-class membership was reviewed from `drug_classes.json`, not
  inferred from class display names.
- The verified and unavailable app goldens were inspected; unavailable copy
  explicitly says the result is not an all-clear.

## Decisive findings

1. `DEP_ANTICOAGULANTS_VITAMINK` displayed “Warfarin” but referenced
   `class:anticoagulants`, which includes direct oral anticoagulants that do not
   antagonize vitamin K. The record is narrowed to warfarin RxCUI `11289`.
2. `DEP_OCP_VITAMINB6` cites evidence about estrogen-containing oral pills,
   while `class:oral_contraceptives` includes implants, injectable progestins,
   emergency contraception, and megestrol. It is suppressed pending a
   reliably normalized combined-oral scope and stronger evidence of clinical
   importance.
3. `DEP_ANTICONVULSANTS_VITAMINK` is pregnancy-specific, cites conflicting
   evidence, and cannot be context-gated by pregnancy in the runtime. It is
   removed from release.
4. The “systemic corticosteroid” class is ingredient-based and can resolve
   route-ambiguous products. Both B1 bone-health records are narrowed to
   long-term oral prednisone RxCUI `8640`.
5. The metformin recommendation incorrectly said ADA recommends monitoring
   every patient and prescribed sublingual methylcobalamin 1,000 mcg/day.
   ADA 2026 and MHRA guidance support risk-, symptom-, dose-, and
   duration-based assessment plus clinician-directed treatment.

## Authoritative current sources

- ADA Standards of Care in Diabetes—2026, recommendation 3.10: consider
  periodic B12 assessment with long-term metformin, especially anemia,
  neuropathy, higher dose, longer duration, or other risk factors.
- MHRA Drug Safety Update, 20 June 2022: test B12 when deficiency is suspected
  and consider periodic monitoring in people with risk factors.
- ACR 2022 glucocorticoid-induced osteoporosis guideline: fracture-risk
  assessment and optimized calcium/vitamin D for chronic systemic
  glucocorticoid exposure, not a universal self-selected supplement dose.
- DailyMed XENICAL: daily multivitamin containing A, D, E, and K at least two
  hours before or after orlistat.
- DailyMed cholestyramine: long-term therapy can impair A, D, E, and K
  absorption; clinician-directed water-miscible/parenteral forms may be
  considered.
- DailyMed levothyroxine: calcium and iron products should be separated from
  levothyroxine by at least four hours.
- DailyMed warfarin: maintain a normal, balanced diet with a reasonably
  consistent vitamin K intake; avoid drastic changes.
- DailyMed isoniazid: pyridoxine is recommended for malnutrition and other
  neuropathy-predisposing risks.
- DailyMed sulfasalazine: reduced folic-acid absorption and folate deficiency
  are recognized label effects.

## Evidence limitations preserved in copy

- Statins lower circulating CoQ10, but tissue deficiency and supplement
  benefit for muscle symptoms remain uncertain.
- PPI fracture associations are observational and do not prove body-calcium
  deficiency.
- Thiazides increase urinary zinc loss, but routine zinc supplementation is
  not established.
- Furosemide increases urinary thiamine loss; heart-failure studies are partly
  confounded by illness and intake.
- Phenytoin-associated B12 evidence is serum-level based; the mechanism is not
  established.
- Chronic valproate/carnitine evidence is strongest in children and
  higher-risk patients; routine supplementation is not universal.
- Colchicine-associated B12 malabsorption is recognized but does not establish
  universal periodic screening.
