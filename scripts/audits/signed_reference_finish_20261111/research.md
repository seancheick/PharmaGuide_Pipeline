# Signed "does not score" records finish as reference-only (2026-11-11)

**Request.** On 2026-11-11 Sean asked to fix the signed-ineligible holds listed in
`evidence_v1_closeout_20261110/research.md` §6. Those were six records whose signed contexts are all
`scoring_eligible: false`. Each held its products as `clinical_sources_ineligible`.

**Mechanism.** No new field was added. Each record became reference-only (`study_type` and
`evidence_level` both set to `reference`), the existing route by which a finished review counts at
no credit. Main's rule in `evidence_resolver._resolve_evidence_for_row` finishes a reference record
when its source review is complete. ADR-0007 allows a finished review to end at zero, and amendment 3
still applies: no unfinished source review is closed by a zero. Every declared PMID in these five
records already has a signed context; `test_every_declared_source_has_its_own_context` checks this,
because the reference path does not check coverage.

This supersedes the elderberry hold kept in 13179d11b.

**Review.** The conclusions are agent research. An independent agent checked all 13 PMIDs (with
FINISH-AS-REFERENCE for all five), and the main model checked key abstracts against PubMed
E-utilities on 2026-11-11. This is not clinician review.

## Per entry (before → after)

| Record | Before | After | Key sources (content-checked) |
|---|---|---|---|
| INGR_ELDERBERRY | mixed / medium; "promising"; arrow endpoints; goal Immune Support; enrollment 204, registry 13 | reference; mixed / low; goals and tags []; aggregates null | 33827515: GRADE, low to very low certainty, no clear effect on incidence. 30670267: 180-participant pooled analysis. NCCIH: preliminary. |
| INGR_L_CARNITINE | ingredient-human SR/MA; mixed / high; goals Muscle Growth, Weight Management; context limitation said 32359762 "remains pending" | reference; mixed / medium; goals and tags []; limitation now says finished bounded noncredit transfer (consistent with notes) | 32154768: soreness and short-lived markers. 32359762: about 1.2 kg, mainly overweight or obese. 32958033: conditional performance, raised TMAO. Dose fields unchanged (Dose pillar). |
| INGR_VITAMIN_D3 | positive_strong / high (automated); "supports reduced ARI"; arrow endpoints; goals Immune Support, Healthy Aging; `applicability` scoped to immune_support; enrollment 576, registry 2067 | reference; mixed / low; goals and tags []; `applicability` removed; aggregates null; OWNERSHIP paragraph kept | 28202713 (2017 benefit) vs 39993397 (2025 update: 40 trials, 61,589 participants, OR 0.94, 0.88 to 1.00, p=0.057). 38787821: older adults, RR 0.99, moderate certainty. 30293909: no bone benefit. |
| BRAND_ASTAREAL | positive_strong / medium; unsourced exercise and eye-strain wording; goal Skin; registry 12 | reference; no direction / low; goals and tags []; aggregates null | 22428137: sole affiliation Fuji Chemical Industry; 36 men placebo-controlled, 30 women uncontrolled. |
| BRAND_TESTOFEN | positive_strong / medium; "randomized evidence for libido..."; enrollment 150 | reference; mixed / low; goals and tags []; aggregates null | 26791805: sponsor trial, positive. 21312304: with minerals, libido. 31828857: standardised extract at 600 mg/day in BPH men, hormones unchanged (did not measure AMS or libido). 42688439: total T SMD 0.25 at very low certainty; evidence does not support testosterone-boosting claims. |
| INGR_OMEGA3 | held | **unchanged, still held** | Omega products resolve through the nutrition path when EPA/DHA amounts are disclosed. Closing this record would turn undisclosed EPA/DHA amounts into a finished zero, which amendment 3 forbids. |

`clinical_review_holds.csv` (2026-10-28 snapshot) rows for the five records are superseded by this
batch; the snapshot is history and was not rewritten.

## Effects found while testing

- Real label rows finish at no credit: Elderberry, L-Carnitine base, L-Carnitine fumarate and
  acetyl-L-carnitine (tests `test_label_rows_finish_at_no_credit` and
  `test_real_elderberry_labels_finish_their_elderberry_row`).
- **Generic astaxanthin stays held.** PRECLIN_ASTAXANTHIN_GENERIC is a separate unfinished record:
  declared sources 32755613, 35091276 and 38243785 have no context. Bare "Astaxanthin" and
  "AstaREAL Astaxanthin" rows match it, so they remain `not_yet_evaluated`. That source review is
  outstanding work, not closed here.
- **Unprinted carnitine salts stay open.** A canonical query, or a row whose salt is not printed,
  stays `clinical_source_row_unresolved`, because BRAND_CARNIPURE (tartrate, scoring-eligible)
  needs a printed tartrate. Carnipure tartrate credit is unchanged
  (`test_actual_reviewed_carnipure_source_requires_printed_tartrate`).
- **Reason precision.** For a reference record with no `applicability` block, the existing seam
  (`clinical_applicability._assess_scoped_reference`) returns `reference_only_clinical_record`
  before the legacy `exclude_aliases` check. INGR_L_CARNITINE's per-record reason for fumarate and
  ALCAR rows is therefore "reference only" instead of "preparation mismatch". Both finish at zero.
  The seam was left unchanged; changing it would move the reasons on every other reference record
  that has exclusions.

## Tests

- New: `scripts/tests/test_signed_reference_finish_20261111.py`. Fail-first: 10 failed before the
  apply; the controls (omega-3 held, fish oil held, vitamin D authority) passed before and after.
- Updated pins, each reviewed against the change:
  - a9 elderberry params moved out of the "unread ingredient holds" lists; fish oil, reishi, maca
    and keratin still cover that mechanism.
  - Carnitine and resolver mechanics tests keep their synthetic eligible vehicle explicitly.
  - Vitamin D ownership tests assert the benefit-scope applicability is gone and the refuting
    citation is kept.
  - batch1 holds and finishes updated.

Apply: `$PG_PYTHON scripts/audits/signed_reference_finish_20261111/apply.py` (from the repo root).

## Replay (2026-11-11)

Cohort: 1,134 labels. It covers every elderberry (326), L-carnitine (350), astaxanthin (287) and
fenugreek (122) product in the integrated-run census, 120 sampled vitamin D products, 30 fish-oil
controls and 60 random controls; one submission without a DSLD raw label was dropped. Method:
`replay.py freeze-raw` then `snapshot`. Base: main a01269d6b. Candidate: this branch. Files are in
`~/pg_quality/signed-reference-20261111/`.

- Score, pillar and quality-status moves: **0** (the scores of held products were already retained).
- Evidence finished for 171 products (display `not_yet_reviewed` → finished); none went the other way.
  - 70 now `evaluated_applicable`, with credit from other reviewed actives or a printed carnitine
    tartrate (e.g. 20008 prints "as L-Carnitine L-Tartrate": existing BRAND_CARNIPURE route,
    unchanged).
  - 65 now `evaluated_authority`, from vitamin C and zinc in elderberry formulas.
  - 35 now `applicability_unestablished` at Evidence 0: elderberry-only products such as Sambucus
    syrups.
  - 1 now `no_qualifying_human_evidence`.
- V030 (Vitacost) re-aging: no Vitacost label was in this cohort, so it is not measured here; it
  changes only that manufacturer's penalty (`--check` passes).
