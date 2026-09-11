# Vinpocetine audit — 2026-09-11

Scope: one chemical identity, its IQM entry, and DSI_ANTICOAG_VINPOCETINE.
Sources below were read live before making the audit corrections. No efficacy
bonus or clinical dose threshold is inferred from pharmacokinetic studies.

## Identity

Project verify_pubchem.py --cid 443955 returned vinpocetine, C22H26N2O2,
CAS 42971-09-5, and Cavinton / apovincaminic acid ethyl ester synonyms.
Project verify_unii.py --search vinpocetine returned VINPOCETINE, UNII
543512OBTC, the same CAS/CID, and RxCUI 24506. Project verify_cui.py --cui
C0059752 returned vinpocetine (Organic Chemical, Pharmacologic Substance).

- https://pubchem.ncbi.nlm.nih.gov/compound/443955
- https://gsrs.ncats.nih.gov/
- https://uts-ws.nlm.nih.gov/rest/content/current/CUI/C0059752

## Absorption: observations versus calibration

- PMID 2624613 (1989), *Vinpocetine pharmacokinetics in elderly subjects*:
  20 elderly volunteers, oral 20 mg versus IV 10 mg; absolute bioavailability
  6.7%. The abstract gives no 5–13% interval.
  https://pubmed.ncbi.nlm.nih.gov/2624613/
- PMID 1418055 (1992), *Bioavailability of vinpocetine and interference of the
  time of application with food intake*: eight volunteers, 10 mg tablets;
  relative exposure was 60–100% higher with food. This is not an absolute
  bioavailability interval and must not be pooled with the 1989 estimate.
  https://pubmed.ncbi.nlm.nih.gov/1418055/
- PMID 582791 (1979), *Pharmacokinetics of vinpocetine in humans*:
  oral/IV AUC ratio 56.6 +/- 8.9%. This older conflicting result remains
  disclosed; the newer point estimate is not a universal absorption constant.
  https://pubmed.ncbi.nlm.nih.gov/582791/
- PMID 3691609 (1987): elderly-subject elimination half-life 2.12 +/- 0.51 h.
  https://pubmed.ncbi.nlm.nih.gov/3691609/
- PMID 2384112 (1990): five men, seven days at 3x5 / 3x10 mg per day;
  linear kinetics, no accumulation or autoinduction at the studied regimens.
  https://pubmed.ncbi.nlm.nih.gov/2384112/

The existing proposed bio_score 6/15 is an ordinal form-quality calibration,
not a measured percentage or efficacy finding. Retained, with the unsupported
structured range removed. Clinical scoring calibration remains reviewable.

## Anticoagulants: what the sources actually show

- PMID 28930203, DOI 10.3390/medicines2020093 (2015): in-vitro P-gp inhibition
  suggests interaction potential. Authors judge clinically relevant CYP
  inhibition unlikely at expected human plasma exposure. Their introductory
  warfarin claim cites PMID 2272713; that original study was checked directly.
  https://pubmed.ncbi.nlm.nih.gov/28930203/
  Full text: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5533163/fullTextXML
- PMID 2272713 (1990), *Influence of vinpocetine on warfarin-induced inhibition
  of coagulation*: 18 men, single warfarin doses before/after vinpocetine.
  Prothrombin-time comparisons met the study's equivalence criterion;
  authors considered the small influence likely without clinical implication.
  It does not establish meaningful warfarin potentiation or a class-wide effect.
  https://pubmed.ncbi.nlm.nih.gov/2272713/
- FDA's vinpocetine page concerns tentative dietary-ingredient status and
  reproductive risk. It is not an anticoagulant-interaction regulatory warning.
  https://www.fda.gov/food/information-select-dietary-supplement-ingredients-and-other-substances/vinpocetine-dietary-supplements

Correction: describe the interaction as precautionary/inferred from preclinical
work, cite the human study and its limitation, retain Moderate warning severity
and precautionary management under the confirmed prior approval, and stop grading this interaction as
regulator-established. Product-level reproductive-risk CAUTION is unchanged.

## Verification boundary

Claude's corpus run was active in the main checkout during this review. Audit
corrections were prepared in codex/vinpocetine-audit-fixes for integration. A run against the
previous reference fingerprint does not validate these final files for release.

RxNorm REST /REST/rxcui/24506/properties.json independently returned vinpocetine, TTY IN, suppress N on 2026-09-11.

## Final wording review and approval provenance

On 2026-09-11 the project owner confirmed prior approval and requested no
additional clinician review. Source-based editorial review retained the Moderate
precautionary warning while distinguishing in-vitro findings from established
clinical harm. The management text asks the prescriber about appropriate additional
monitoring, without suggesting one test applies to every anticoagulant. No new
clinical approval or stronger evidence is inferred from this authorization.
