# Profile identity follow-through — 2026-09-04

This is correctness work exposed by the controlled clean replay, not weight
calibration. `cea87d01` and the candidate consumed identical labels.

## Whole seaweed versus its iodine/isolated constituents

Nature's Way 251618, 251620, 251621, 256128, 337206 and 79208 lost botanical
profile eligibility when a stale `Seaweed Extract` standard name was replaced
by the resolved preparation name. Kelp/Bladderwrack remained literal, quantified
source rows; DSLD's category was `other`. The scorer then assessed the dose
from iodine alone (public Dose 9.1 to 20), missing the whole seaweed intervention.

The correction extends the existing row-owned botanical source grammar with
word-bounded seaweed nouns. No new botanical resolver, registry relocation,
inferred dose or therapeutic range is introduced. Existing domain, materiality
and product-intent guards remain authoritative. A mineral may have a botanical
source without becoming a botanical intervention.

Primary sources checked:

- [NIH ODS iodine fact sheet](https://ods.od.nih.gov/factsheets/Iodine-HealthProfessional/):
  identifies seaweed, including kelp, as an iodine source. This does not make a
  declared whole-seaweed mass interchangeable with its iodine amount.
- [EMA Fucus identity](https://www.ema.europa.eu/en/medicines/herbal/fucus):
  identifies bladderwrack as the seaweed Fucus vesiculosus thallus. Used only
  for source identity, not US authorization, efficacy or a scoring floor.
- [NCI astaxanthin definition](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/astaxanthin):
  identifies the isolated carotenoid. A seaweed/algal source form cannot make
  it whole seaweed.
- [NCI fucoidan trial description](https://www.cancer.gov/research/participate/clinical-trials-search/v?id=NCI-2025-01334):
  identifies fucoidan as a sulfated polysaccharide from brown seaweed. Used only
  for the constituent-versus-whole-source distinction, not a treatment claim.

Tests first reproduced six missing whole-source profiles and a pre-existing
astaxanthin source/profile leak. A separate RED test proved a stale native
classifier stamp could hide the corrected profile. Classifier 1.3.1 invalidates
older native decisions without changing the 1.3.0 contract shape. The focused
357-case backstop and independent 208-case review passed. The full-corpus
report remains the acceptance gate for numerical effects.

## Fucoxanthin boundary exposed by the corpus diff

The expanded seaweed grammar also exposed FucoThin 241286/274270 and
XanthiTrim 294075. Their already-resolved primary is `fucoxanthin`, not a
whole-seaweed preparation. An owned brown-seaweed/Undaria source must not
override that constituent identity. The same existing isolated-constituent
set now includes `fucoxanthin`; no alternative classifier or score rule was
introduced. Its regression failed before the addition, then all 13 tests in
`test_seaweed_profile_identity.py` passed.

Identity verified on 2026-09-04, not inferred from a similar name:

- [NIH ODS weight-loss fact sheet](https://ods.od.nih.gov/factsheets/WeightLoss-HealthProfessional/)
  identifies fucoxanthin as a carotenoid found in brown seaweed and algae.
  This check does not adopt the page's trial inventory as a current systematic
  review or add an efficacy/dose claim.
- [PubChem CID 5281239](https://pubchem.ncbi.nlm.nih.gov/compound/5281239)
  and its live PUG REST property response identify molecular formula
  `C42H58O6` and InChIKey `SJWWTRQNNRNTPU-ABBNZJFMSA-N`.
  The identifier is research provenance only; no identifier was added to data.

The astaxanthin/fucoidan/fucoxanthin checks distinguish an isolated constituent
from its source organism. A corrected domain can change which existing
Formulation and Dose assessment applies; it is not a reason to tune the result
back toward its previous number. Full-product comparisons and independent
review must verify those differences before acceptance.

## Title-boundary ownership exposed by the isolated-identity correction

Fresh control/candidate probes of MacuGuard 182388 retained identical scoring
rows, source quantities, IQM ratings and RDA assessments. Its source-owned
Saffron extract is 20 mg at `ingredientRows[1]`; natural Astaxanthin is 6 mg at
`ingredientRows[2]`. The MacuGuard blend carries an opaque 173 mg total.

Correctly classifying astaxanthin as an isolated marker exposed an existing
title parser defect. In `MacuGuard Ocular Support with Saffron & Astaxanthin`,
the title boundary is position 24, saffron starts at 30 and astaxanthin at 40.
The old earliest-name fallback called saffron the title head even though both
names followed `with`. Saffron failed both materiality checks, but the existing
therapeutic-owner branch accepted its title-prominent role. This changed the
whole product from the generic adapter to saffron's botanical adapter.

The bounded correction requires the botanical name to precede the existing
title separator before it can win title-head precedence. Genuine head ties
retain their prior earliest-name rule. No separator vocabulary, materiality
threshold, reference lookup, domain mapping, or other owner policy changed.
In particular, the earlier standardized/material-owner branch still accepts
the positive control `Formula with Elderberry & Zinc`; being after `with`
does not itself mean an ingredient is immaterial.

TDD evidence: the new public classification/dose regression failed with
`eligible=True` (1 failed in 0.11 s), then passed after the guard (1 passed in
0.14 s). After word-order, separator, genuine-head and material standardized
controls, the five-file adjacent backstop passed 192 tests in 1.17 s. The
production change is confined to `_profile_botanical_is_title_head`.

Three bounded, in-memory fresh probes after the correction:

| Product | Result | Formulation | Dose | Ownership |
| --- | ---: | ---: | ---: | --- |
| 182388 MacuGuard | 59.1 | 5.9 | 20.0 | Generic; post-separator saffron does not own |
| 294487 Astaxanthin Softgels | 66.9 | 10.4 | 14.5 | Isolated marker; no botanical owner |
| 294075 XanthiTrim | 52.4 | 8.8 | 9.1 | Existing whole-seaweed blend anchor; blend-total dose only |

The latter two results are unchanged by the title guard. MacuGuard's restored
number is an observed consequence of corrected ownership, not a target used
to select weights or thresholds. These probes did not persist enriched/scored
outputs; the parent-owned complete controlled replay remains the final gate.

Read-only blast-radius inventory used all 58 manifest-owned enriched input
files in `corpus_preparation_control_cea87d01_source_owners.json`: 15,415 unique
products, of which 1,864 titles contained an existing explicit separator.
Those candidates received current classification without re-enrichment or
scoring; their identical row contracts were evaluated against the old and new
title helper through the unchanged owner classifier. This avoids relying on
stored classifier 1.3.0 decisions that predate the isolated-marker correction.

Exactly three products changed both title-helper and owner decisions:
182388, 232205 and 232206, all named `MacuGuard Ocular Support with Saffron &
Astaxanthin`. Each changed `therapeutic_botanical_owner` to
`nonbotanical_title_head_blocks_botanical`, with saffron 20 mg versus the
173 mg blend and both materiality checks false. No changed actual case was a
material or standardized botanical counterexample. All three are already in
the report's 7,791 full-re-enrichment selection: outside count 0, IDs `[]`.
The inventory completed in 248.55 s with zero errors; no additional replay
targets or scoring thresholds were introduced.
