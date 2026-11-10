# Joint batch receipts — ADR-0007 one-pass review (2026-11-10)

Agent review by Claude; independent agent check recorded below. Not clinician review.
Scope: glucosamine, chondroitin, collagen, MSM, hyaluronic acid. Census used for the cohort:
`~/pg_quality/catalog-release-20261105/CENSUS_ALL.json.gz` (stale: predates the 2026-11-09 MSM
review). Live current-code snapshot: `~/pg_quality/evidence-v1-joint-20261110/base.jsonl`
(239 real labels, replay.py freeze-raw + snapshot at 532c7a300).

## Per-entry results

| Ingredient | Record | Before (current code) | Decision | Data change |
|---|---|---|---|---|
| Glucosamine | INGR_GLUCOSAMINE_SULFATE | 107 rows finished, limited, 0 points (`reference_only_clinical_record`) | Already a finished judgment: Dr. Pham's 2026-10-28 shared OA standard (ACR 2026 strongly against; VA/DoD 2026 insufficient). No reopen trigger. | none |
| Chondroitin | INGR_CHONDROITIN_SULFATE | 73 rows finished, limited, 0 points | Same signed 2026-10-28 standard; Cochrane 2015 (PMID 25629804) retained. | none |
| Collagen | INGR_COLLAGEN_PEPTIDES + literature record `collagen` | 31 finished limited; 6 UC-II supported; 8 BioCell excluded; 5 plain "collagen"/"gelatin" held | Already finished by the signed A059/A148 restriction and the 2026-11-07 literature review. Plain collagen/gelatin stays open by that review's own decision; not changed here. | none |
| MSM | INGR_MSM | 126 supported; 5 held only because the label spells it "Methyl Sulfonyl Methane", "Methylsulfonyl Methane", "Methylsulfonyl-Methane" or "Methysulfonylmethane" | Matching defect. Identity by chemistry: PubChem CID 6213 (C2H6O2S, InChIKey HHVIBTZHLRERCL-UHFFFAOYSA-N), IUPAC methylsulfonylmethane; synonyms MSM, dimethyl sulfone, methyl sulfonyl methane, methylsulfonyl methane, CAS 67-71-0; DMSO is not a synonym. "sulphonyl" forms are British spellings of the same name; "methysulfonylmethane" is a label misspelling already mapped by the IQM. | `applicability.required_form_terms` += 6 same-chemistry spellings |
| Hyaluronic acid | INGR_HYALURONIC_ACID | 46 tablet rows finished (capsule-only Hyabest scope); 22 plain "Hyaluronic Acid" rows held (`clinical_source_label_unresolved`) | One-pass conclusion: limited research, no ingredient-level points. Hyabest (S) LF-P exact credit kept. | ingredient_general context (PMID 39886281, scoring_eligible false), 2 references, attestation, notes |

## Hyaluronic acid sources (read 2026-11-10)

1. NIH ODS / NCCIH / MedlinePlus: no oral hyaluronic acid monograph (MedlinePlus search returns
   only injection and skincare pages).
2. PMID 40911749 (2025 meta-analysis, already on the record): 7 RCTs; hydration, elasticity and
   wrinkle depth improved; firmness, wrinkle volume and TEWL not significant; authors cite small
   samples and heterogeneity.
3. PMID 39886281 (2024 systematic review, full text PMC11778613): 11 studies, 597 adults, 9 knee OA,
   1 knee/hip OA, 1 low back pain; 30-300 mg/day; only 2 of 11 gave HA alone; no pooling or
   risk-of-bias grading; 9/11 reported improvement, 2 no difference. Included studies
   (references 6-16): 37686801, 33592868, 34622845, 33213125, 27681813, 26550817, 24899570,
   23226979, 18208600, 33568038, 38707049.
4. PMID 42914415 (2026 review): incomplete molecular characterization, heterogeneous doses and
   formulations, short trials and multi-ingredient products prevent HA-specific attribution.
5. EFSA NDA 2012, doi:10.2903/j.efsa.2012.2806 (read on efsa.onlinelibrary.wiley.com): no
   cause-and-effect relationship between HA consumption and protecting the skin against dehydration.
6. PMID 26818459 (2016 review) noted, not cited in data: authored by the manufacturer (Kewpie).

Identifier verification: `verify_backed_studies_citations.py` live run, 2220 PMIDs, TITLE-MISMATCH 0,
TITLE-DRIFT 0; none of the 8 pre-existing ghost suspects is in this batch.

## Code

`evidence_resolver.py` V1 finish condition: an attested record finishes an unknown-preparation row
when it carries a reviewed `ingredient_general` context, credit-bearing or not; exact and branded
contexts may coexist and never transfer. Only INGR_ASHWAGANDHA and INGR_HYALURONIC_ACID carry the
attestation.

## Independent check (2026-11-10)

A fresh-context agent reviewer received the requirement, the owners and the diff (not the
builder's reasoning) and re-read PMID 39886281's full text. Verdict: no blockers. Three should-fix
items, all applied before the PR:

1. The HA joint outcome asserted `outcome_role: direct_between_group_effect`, but several included
   trials report improvement in both arms. The role was removed (it is optional) and the outcome name
   now says "within or between groups".
2. The V1 finish gate checked a raw `review_status` only. It now requires
   `evidence_resolver::_reviewed_general_conclusion`: finished, attributable review provenance
   (`clinical_review_provenance_valid`) and a schema-valid context
   (`validate_ingredient_context(..., require_complete_review=True)`). Fail-first test cases
   `unattributed` and `invalid` failed before the change and pass after.
3. The notes claimed an independent check that was not yet recorded; this section records it.

Also from the review: the notes and limitations now say that the review's authors concluded that oral
HA "seems to be a safe and effective therapy" for OA (abstract, PubMed efetch 2026-11-10), and why
this record does not adopt that conclusion. Labels naming Hyal-Joint (no record of its own) now finish
under the same label-unresolved reason with no points, which the reviewer accepted for V1. The
reviewer could not independently confirm the MedlinePlus search result; it is retained as our own
observation.
