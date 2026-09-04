# Source-owned botanical evidence joins — 2026-09-04

## Defect and scope

The 8,078-label fresh replay exposed actual missing joins, not reviewed clinical
rejections: Boswellia 311175 and its nine peers, plus cranberry 259627/333698,
retain their original dose-bearing source rows but lose existing research after
the preferred botanical name is corrected. Their rejected-evidence lists are
empty. A missing exact alias is not a scientific finding of inapplicability.

Repair only the existing records and source-declared preparation aliases. Keep
the one exact matcher and existing source-owned applicability evaluator; do not
restore stale IQM names, add substring matching or change global weights.
Whole resin/powder or essential oil cannot borrow resin-extract research;
cranberry seed/leaf preparations cannot borrow fruit research. Family-level
research does not establish generic-to-branded preparation or dose equivalence.

## Cranberry: verified existing sources

[PMID 37068952](https://pubmed.ncbi.nlm.nih.gov/37068952/) is the April 2023
Cochrane review: 50 trials / 8,857 participants. Benefits concern prevention of
recurrent symptomatic UTIs in selected populations, not general immune,
cardiovascular or glycemic improvement. Fruit juice, tablets and powders are
included; dose/preparation comparisons do not establish one universal PAC or
extract-mass threshold. The review does not support extrapolation to treatment
of an existing infection or all populations. Its November update is distinct;
do not silently attach that update's citation to the April identifier.

[PMID 34473789](https://pubmed.ncbi.nlm.nih.gov/34473789/),
[primary PLOS article](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0256992),
is a 2021 prevention review in susceptible populations. It supports the same
bounded ingredient family, not a specific commercial chew or a universal dose.
Its participants are not summed with the overlapping Cochrane review.

Live FDA GSRS, queried with the existing `GSRSClient.get_full_substance`, confirms
the retained `0MVO31Q3QS` is CRANBERRY, including Vaccinium macrocarpon fruit,
fruit powder and fruit-extract aliases. The added concentrate spelling is a
fruit-preparation join, not permission to infer PAC content from its total mass.

## Boswellia: verified existing sources

[PMID 32680575](https://pubmed.ncbi.nlm.nih.gov/32680575/),
[primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC7368679/),
reports seven trials / 545 osteoarthritis patients. The assessed outcomes are
pain, stiffness and physical function, not stress, longevity or immune support.
The pooled extract family does not establish interchangeability among the
different standardized products. Use the review's enrollment alone.

[PMID 39092235](https://pubmed.ncbi.nlm.nih.gov/39092235/),
[primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11291344/),
studies standardized Boswellin Super gum-resin extract in knee OA, at 150 or
300 mg per tablet, twice daily (300 or 600 mg/day), for 90 days. The primary
methods distinguish tablet strength from daily dose. Its standardized composition and rapid-onset result
must not be transferred to a generic 1,000 mg resin-extract label.

[PMID 35512759](https://pubmed.ncbi.nlm.nih.gov/35512759/) was re-fetched directly
through NCBI EFetch. Its abstract describes 70 randomized, 67 completed, Aflapin
standardized to 20% AKBA, 100 mg/day for 30 days. An earlier similarly titled
2011 paper is not this trial; its dosing frequency or enrollment cannot fill
missing details. These participants are not summed into the 2020 review count.

Live GSRS identifies the old `X7B7P649WQ` as BOSWELLIA SERRATA WHOLE. Remove this
misleading whole-plant identifier from an extract-focused evidence record;
do not invent an extract UNII. Primary ingredient identity remains owned by the
existing botanical registry, not this evidence record.

## Interpretation limits

The exact-match aliases, preparation exclusions and clinical endpoint text are
engineering/data corrections. Existing evidence-strength multipliers are not
re-ratified or tuned here. No new clinician approval or product-specific dose
claim is introduced. Correcting an enrollment count is source correction, not
independent replication or summed meta-analysis participants. Generic evidence
floor/score semantics remain subject to the separate unratified rubric work.

Other drops (Astragalus, Ceylon cinnamon, black garlic and others) are not restored
by name similarity. Their exact intervention/form/outcome coverage requires
individual source review. Absence from a registry is not evidence of inefficacy.

## Verification ledger

- RED: nine assertions reproduce three lost joins, four stale-preparation
  bypasses and two unsupported claim records.
- Additional RED checks bind the two source-reviewed enrollments, removal
  of the whole-plant UNII, and exclusion of isolated AKBA/boswellic-acid names
  from the whole-extract matcher: **14 failed** before the data correction.
  Final GREEN and corpus results are recorded by the
  continuation acceptance report, not inferred from these tests.
