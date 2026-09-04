# Jarrow yeast-extract identity review — 2026-09-04

## Bounded decision

Register only the literal **Saccharomyces cerevisiae extract** preparation in
`other_ingredients.json`, as an active-only, recognized non-scorable identity.
Do not create an IQM quality form, a probiotic strain, a branded identity, or a
beta-glucan parent assignment. No clinical benefit, efficacy threshold, score,
or approval is established by this identity review.

## Primary-source evidence

- [Jarrow Beta Glucan product page](https://jarrow.com/products/beta-glucan-60-capsules),
  checked directly on 2026-09-04: the Supplement Facts assigns 250 mg to the
  S. cerevisiae extract, with at least 75% / 188 mg glucan content. The product
  description identifies a proprietary baker's-yeast cell-wall extract. This
  supports a preparation identity, not a whole live yeast or purified
  constituent identity. It does not disclose an independently matchable strain
  or ingredient trademark.
- [NIH DSLD 264610 label](https://api.ods.od.nih.gov/dsld/s3/pdf/264610.pdf): the
  identity researcher inspected the original label on 2026-09-04. It declares
  the extract at 250 mg, with a providing-at-least-75%
  glucan form; it does **not** print a separate 188 mg amount. The implementing
  agent's web PDF fetch failed, so this is explicitly the delegated primary
  label verification rather than a claimed second successful fetch.
- [NIH DSLD 307558 label](https://api.ods.od.nih.gov/dsld/s3/pdf/307558.pdf): the
  identity researcher inspected the original label on 2026-09-04. The 250 mg
  extract and separate 188 mg glucan declaration must stay
  distinct. The implementing agent reached the PDF but its screenshot request
  failed; the label-specific interpretation is the delegated verification.
  The main agent independently checked the local cleaned rows and current
  manufacturer page, not a successfully rendered original PDF.
- [FDA UNII 978D8U419H](https://precision.fda.gov/uniisearch/srs/unii/978d8u419h),
  checked directly on 2026-09-04: the preferred entity is S. cerevisiae. Its
  mappings span whole yeast, S. boulardii, and extract names. The broad entity
  does not uniquely establish the composition of this extract preparation.
- [FDA UNII 44FQ49X6UN](https://precision.fda.gov/uniisearch/srs/unii/44FQ49X6UN),
  checked directly on 2026-09-04: the entity is yeast beta-D-glucan, with
  beta-1,3-1,6-D-glucan among the mappings. This is the glucan constituent, not
  the entire source extract.

No exact-preparation CID, CAS, or UNII was verified. Keep `external_ids` empty;
neither of the above UNIIs is an exact-preparation identifier for the new
registry record. Preserve label-supplied taxonomy as raw provenance, not as
identity authority.

## Real cleaned boundary inspected directly

Source: `scripts/products/output_Jarrow_Formulas/cleaned/cleaned_batch_1.json`
in the main checkout, inspected on 2026-09-04. The regression fixture preserves
the relevant source fields instead of reading a generated catalog during tests.

| DSLD ID | Printed parent | Parent source path / amount | Separate constituent |
|---|---|---|---|
| 264610 | Saccharomyces cerevisiae extract | `ingredientRows[0]`, 250 mg | No child amount; form records at least 75% long, branched Beta 1,3/Beta 1,6 Glucans |
| 307558 | Saccharomyces cerevisiae Extract | `ingredientRows[0]`, 250 mg | Beta-1,3-1,6-Glucan at `ingredientRows[0].nestedRows[0]`, 188 mg; parent mass remains 250 mg |

Both cleaned parents incorrectly carry `brewers_yeast` / `Brewer's Yeast`.
264610 additionally carries S. boulardii taxonomy; 307558 carries the broad
S. cerevisiae UNII. The existing exact-literal preparation rescue in
`identity_integrity.py` can select a registered preparation without trusting
those organism assignments. The non-scorable recognition registry is already
loaded from `other_ingredients.json`; no new runtime surface is proposed.

## Alias and dose boundaries

Only the two observed case variants are registered. Do not add bare yeast
extract, whole baker's/brewer's yeast, S. boulardii, a proprietary strain name,
or glucan constituent aliases. The exact canonical key is
`NHA_SACCHAROMYCES_CEREVISIAE_EXTRACT`.

The 250 mg source amount is not a 250 mg beta-glucan amount. Do not derive a
new 187.5/188 mg child for 264610, sum the 307558 parent and child as separate
exposures, or convert either amount to CFU. Existing live S. boulardii rows
must remain live probiotic identities. Complete identity coverage alone does
not establish dose-rubric readiness, clinical evidence, or release readiness.

## Verification

Command: `scripts/test.sh fast scripts/tests/test_jarrow_yeast_extract_identity.py --tb=short`

- RED, before the registry addition: **2 failed**; both parent rows had
  `canonical_id=None` instead of the exact preparation identity.
- GREEN, after adding one record: **2 passed**.
- Final expanded boundary and negative controls: **9 passed in 1.03 seconds**.
  Both products have strict mapped coverage 1.0 and zero unmapped rows. The
  parent-only 264610 retains one 250 mg source projection, and 307558 retains
  that projection plus the separately linked 188 mg glucan child. Neither
  fixture produces probiotic data, CFU, or clinical matches. Bare yeast extract
  remains unresolved; a live S. boulardii control retains its owned CFU.
- `git diff --check` passed. At this isolated task's checkpoint, metadata and
  actual registry size both equalled 728 (before the separate Immuno-LP20 entry).

The data-only change exposes existing runtime provenance leftovers: the
enriched source row still has its old `brewers_yeast` canonical, the recognized
IQD row retains the old standard name and legacy `score` scalar despite
`bio_score=None` / `scoreable_identity=False`, and the correct NHA scoring
projection carries the wrong `canonical_source_db=ingredient_quality_map`.
These were reported for a separate shared-contract correction. This change
does not pin those leftovers as desired behavior or modify runtime code.

No score or release-readiness conclusion follows from this identity-only
test run. No broad pipeline, release, upload, scoring-policy change, or commit
was performed.
