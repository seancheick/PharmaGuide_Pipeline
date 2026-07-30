# PharmaGuide Clinical Team delta — source verification

Date: 2026-07-30

This file records the primary-source checks used for the post-review clinical
copy and interaction changes. It is not a substitute for the machine-enforced
record fingerprints or the licensed-pharmacist sign-off ledger.

## Orlistat and vitamin A

- Canonical medication identity: RxCUI `37925`, orlistat.
- Primary source: DailyMed XENICAL label, SetID
  `6240792b-9224-2d10-e053-2a91aa0a2c3e`.
- Verified label claims:
  - XENICAL is contraindicated during pregnancy because weight loss provides no
    benefit during pregnancy and may result in fetal harm.
  - A daily multivitamin containing vitamins A, D, E, K, and beta-carotene is
    recommended.
  - The multivitamin should be taken at least two hours before or after XENICAL,
    such as at bedtime.
- Authoring decision: pregnancy is presented as a medication-safety issue, not
  as a vitamin-form or vitamin-dose adjustment. The reviewer-suggested
  “trying to conceive” clause is not copied into the label-derived statement
  because the cited XENICAL label does not state that clause.

## Cholestyramine, vitamin K, and warfarin

- Canonical identities verified live through RxNorm:
  - RxCUI `2447`: cholestyramine resin (ingredient).
  - RxCUI `11289`: warfarin (ingredient).
- Primary source: DailyMed CHOLESTYRAMINE label, SetID
  `09420793-7357-4194-8172-0b1cddb167fe`, updated 2026-03-05.
- Verified label claims:
  - Chronic cholestyramine use may cause vitamin-K-deficiency
    hypoprothrombinemia and increased bleeding tendency.
  - The adverse-reaction section reports prolonged prothrombin time.
  - Cholestyramine may delay or reduce warfarin absorption.
  - Other oral drugs should be taken at least one hour before or four to six
    hours after cholestyramine, or at as great an interval as possible.
- Authoring decision: the nutrient card uses specific PT/INR language, while a
  separate direct drug-drug rule carries the warfarin absorption/timing warning.
  This avoids hiding a drug-drug interaction inside a vitamin-K card.

## Levothyroxine with calcium or iron

- Canonical medication identity: RxCUI `10582`, levothyroxine.
- Primary label source: DailyMed LEVOTHYROXINE SODIUM label, SetID
  `a8db0f7d-8863-9309-e053-2995a90a284a`.
- Verified label claims:
  - Levothyroxine is administered on an empty stomach, one-half to one hour
    before breakfast.
  - Iron and calcium supplements should be separated from levothyroxine by at
    least four hours.
  - Periodic TSH and/or T4 monitoring is used to assess adequacy of therapy.
- Primary study: Campbell et al., PMID `1443969`.
  - PubMed identifies an uncontrolled 12-week study of 14 patients.
  - Participants simultaneously took a 300 mg ferrous sulfate tablet and their
    usual thyroxine dose.
- Authoring decision: standardize the consumer-facing TSH unit to `mIU/L` while
  preserving the study values.

## Acid suppression and iron

- Primary population study: Lam et al., PMID `27890768`.
- Verified abstract claims:
  - Both at least two years of PPI use and at least two years of H2-receptor
    antagonist use were associated with subsequent iron deficiency.
  - The reported association was stronger for PPIs than H2 blockers.
  - Higher-dose and post-discontinuation analyses were specifically reported
    among PPI users.
- Mechanistic study: Hutchinson et al., PMID `17344278`.
  - The population was hereditary haemochromatosis; it supports the absorption
    mechanism but is not general-population outcome evidence.
- Authoring decision: keep the mechanistic citation but label its role and
  population explicitly.

## Scope checks

- `DEP_ANTICOAGULANTS_VITAMINK` is authored as a direct drug reference to
  warfarin RxCUI `11289`; it does not match DOACs.
- `DEP_DIURETICS_THIAMINE` is authored as a direct drug reference to furosemide
  RxCUI `4603`; it does not match thiazides.
- The `DEP_` prefix is an internal stable identifier and is not consumer-facing
  in the app card or clinician PDF.
