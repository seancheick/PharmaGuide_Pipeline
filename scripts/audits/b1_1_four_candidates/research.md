# B1.1 four-candidate evidence review

Date: 2026-07-27
Scope: PPI → vitamin B12, PPI → magnesium, loop/thiazide diuretics →
potassium, and loop/thiazide diuretics → magnesium.

## Release rule

This is an evidence-revision delta, not a clinical promotion. All four records
remain `needs_revision` and consumer-hidden until a licensed pharmacist reviews
the exact proposed copy and records one disposition per candidate. The signed
31-record B1 beta corpus is unchanged.

## Live identity verification

`verify_drug_class_rxcuis.py` resolved every member of
`class:proton_pump_inhibitors` (6/6) and
`class:loop_and_thiazide_diuretics` (21/21) against RxNorm on 2026-07-27.
All 27 identifiers resolved to their authored ingredient names.

The loop/thiazide class excludes potassium-sparing diuretics, vaptans,
theobromine, and obsolete mersalyl. This is essential for the potassium record:
an overbroad “all diuretics” warning could encourage potassium use where
hyperkalemia is the actual risk.

## PPI → magnesium

- PMID 22762246 is Hess et al., a systematic review of PPI-associated
  hypomagnesemia case reports. It supports a PPI class effect through
  dechallenge/rechallenge, with a median reported onset of 5.5 years and a
  broad range from 14 days to 13 years. It says reduced intestinal absorption
  is suspected; it does not establish a precise TRPM6/TRPM7 mechanism.
- The current DailyMed PRILOSEC label (set ID
  `b6761f84-53ac-4745-a8c8-1e5427d7e179`) states that symptomatic and
  asymptomatic hypomagnesemia has been reported rarely after at least three
  months, most often after a year. It advises considering baseline and periodic
  magnesium monitoring for prolonged therapy or concomitant digoxin/medicines
  that can lower magnesium.
- The prior FDA safety-communication URL now returns HTTP 404 and is removed.
- The prior 200–400 mg/day magnesium recommendation is removed. The label
  supports clinician-directed monitoring and management, not routine
  self-supplementation for every PPI user.

Proposed disposition: evidence-ready, pending pharmacist review. Evidence tier
`established`; severity `significant`; exact molecular mechanism explicitly
uncertain.

## PPI → vitamin B12

- PMID 24327038 is a large case-control study. At least two years of PPI supply
  was associated with B12 deficiency (OR 1.65, 95% CI 1.58–1.73); this is an
  association, not proof that every long-term user becomes deficient.
- PMID 37060552 is a 2023 systematic review/meta-analysis. The pooled odds ratio
  was 1.42, but heterogeneity was significant and the authors state the pooled
  effect was too small to clearly imply an association. This directly requires
  uncertainty-preserving copy.
- The current PRILOSEC label says daily long-term acid suppression (for example,
  longer than three years) may cause B12 malabsorption or deficiency and advises
  considering the diagnosis when compatible symptoms occur.
- The prior blanket 1,000 mcg/day recommendation and “food may not be enough /
  supplement is more reliable” copy are removed. The proposal uses
  symptom/risk-based assessment and treatment of confirmed deficiency.

Proposed disposition: evidence-ready, pending pharmacist review. Evidence tier
`probable`; severity `moderate`; PPI-only scope.

## Loop/thiazide diuretics → potassium

- Current DailyMed furosemide tablet labeling (set ID
  `f3173c0d-2b62-7c7b-e053-2995a90ada05`) warns about hypokalemia and calls for
  frequent early and periodic serum electrolyte monitoring.
- Current DailyMed hydrochlorothiazide tablet labeling (set ID
  `8a1de4e2-3aca-a4d3-e053-2995a90a1a41`) says hypokalemia can develop,
  particularly with brisk diuresis, inadequate intake, severe cirrhosis, or
  prolonged therapy, and calls for periodic electrolyte monitoring.
- Because onset depends on drug, dose, clinical state, and other medicines, the
  proposal uses `variable`, not a fabricated universal “weeks” timeline.
- The prior “many patients require 20–40 mEq/day” advice is removed. Potassium
  changes require lab-, kidney-, and medication-aware clinician direction.

Proposed disposition: evidence-ready, pending pharmacist review. Evidence tier
`established`; severity `significant`; loop/thiazide-only scope.

## Loop/thiazide diuretics → magnesium

- The same current furosemide labeling lists hypomagnesemia among electrolyte
  abnormalities.
- The same current hydrochlorothiazide labeling states thiazides increase
  urinary magnesium excretion and may cause hypomagnesemia.
- PMID 10997911 supports marked urinary magnesium excretion with loop diuretics
  and distinguishes acute from chronic thiazide effects.
- PMID 9083264 is a mouse distal-tubule cell study whose acute result is
  magnesium conservation, followed by a hypothesis about chronic potassium
  depletion. It is removed from the consumer claim.
- The prior blanket 200–400 mg/day magnesium recommendation is removed.

Proposed disposition: evidence-ready, pending pharmacist review. Evidence tier
`established`; severity `moderate`; subclass differences preserved.

## API/content verification record

- PubMed E-utilities title/abstract content verified on 2026-07-27:
  22762246, 24327038, 37060552, and 10997911.
- RxNorm REST ingredient identity verified on 2026-07-27 for all 27 class
  members.
- DailyMed pages returned HTTP 200 and the exact label sections described above
  were inspected on 2026-07-27.
