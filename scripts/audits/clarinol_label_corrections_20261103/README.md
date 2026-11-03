# Clarinol label corrections (2026-11-03)

Branch `claude/clarinol-label-corrections-20261103`, off main 0c897b8ec. Owner: `scripts/data/curated_overrides/product_label_corrections.json`, applied by `enhanced_normalizer.py::_apply_label_corrections`. Scope confirmed by Sean Cheick as a data correction, one label at a time. This is not clinical approval and not publication.

The Clarinol form, its grade and its evidence are unchanged (bio 13, no `source_form_aliases`). No code reads DSLD alternate names.

## Per-label before and after

Replay on the real labels: main 0c897b8ec against this branch, `replay.py` with `--full --blob --workers 1`.

| DSLD ID | Printed on the label | Identity | Form (bio) | Score and tier | Assessment | Catalog safety | Warnings |
|---|---|---|---|---|---|---|---|
| 228934 | CLA (Conjugated Linoleic Acid)(from Safflower Oil)(Clarinol®) 500 mg | cla → cla | unspecified (10) → clarinol (13) | 52.3 Poor → 56.9 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 7 → 7 |
| 183546 | CLA panel in the 4-in-1 pack, Clarinol® from safflower oil, 4000 mg | cla → cla | unspecified (10) → clarinol (13) | 59.8 Needs improvement → 64.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |
| 213306 | CLA (Conjugated Linoleic Acid Isomers as Clarinol®)(from Safflower Oil) 3.4 g | cla → cla | unspecified (10) → clarinol (13) | 54.3 Poor → 58.9 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 6 → 6 |
| 1059 | Conjugated Linoleic Acid (CLA) (Clarinol®) 1300 mg | cla → cla | unspecified (10) → clarinol (13) | 48.7 Poor → 49.8 Poor | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 23 → 23 |
| 227855 | Clarinol® CLA Complex 1.3 g, providing 78% conjugated linoleic acid (1,014 mg) | cla → cla | unspecified (10) → clarinol (13) | 61.8 Needs improvement → 66.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |
| 176175 | (from Safflower Oil)(Clarinol®) 4000 mg | cla → cla | unspecified (10) → clarinol (13) | 59.8 Needs improvement → 64.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |
| 4259 | (Clarinol®) 1000 mg, left edge partly cropped | cla → cla | unspecified (10) → clarinol (13) | 59.8 Needs improvement → 64.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |
| 220140 | side callout: CLA (Conjugated Linoleic Acid as Clarinol®) 1 g; Other Ingredients also name it | cla → cla | unspecified (10) → clarinol (13) | 66.4 Needs improvement → 66.4 Needs improvement | partial → partial | caution → caution | 42 → 42 |
| 220238 | side callout, Other Ingredients also name it | cla → cla | unspecified (10) → clarinol (13) | 64.4 Needs improvement → 64.4 Needs improvement | partial → partial | caution → caution | 43 → 43 |
| 220239 | side callout only | cla → cla | unspecified (10) → clarinol (13) | 64.6 Needs improvement → 64.6 Needs improvement | partial → partial | caution → caution | 42 → 42 |
| 26318 | (CLA)(Clarinol®) 1000 mg | cla → cla | unspecified (10) → clarinol (13) | 59.8 Needs improvement → 64.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |
| 65945 | (CLA)(Clarinol®) 1000 mg | cla → cla | unspecified (10) → clarinol (13) | 59.8 Needs improvement → 64.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |
| 66895 | (CLA)(Clarinol®) 1000 mg | cla → cla | unspecified (10) → clarinol (13) | 59.8 Needs improvement → 64.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |
| 70326 | (CLA)(Clarinol®) 4000 mg | cla → cla | unspecified (10) → clarinol (13) | 59.8 Needs improvement → 64.4 Needs improvement | complete → complete | no_known_catalog_concern → no_known_catalog_concern | 0 → 0 |

Driver: Formulation A1 bioavailability (228934: A1 11.54 → 15, pillar 15.4 → 20). No Evidence-pillar path changes. 220140, 220238 and 220239 do not move because Formulation is already capped at 20.

Controls, unchanged at every stage: 244301, 244298, 74772, 47590, 33327, 178574, 182799, 184586, 219039, 221095, 45103, 5812, 74397.

## Exceptions to read

- 227855 uses a name correction, not a form correction. A second form turns the row into a blend header and drops it from scoring (61.8 → 47.9 in the first attempt). The name becomes "Clarinol CLA", which loses "Complex" on display. The printed 78% form stays.
- 220140, 220238 and 220239 print Clarinol in a side callout, not on the panel row.

Side effects, all explained: `raw_actives_count` +1 on 13 labels (the legacy tally counts forms; `active_source_row_count` is unchanged, as with existing form corrections); `label_record.formula_fingerprint` follows the displayed ingredients; `display_ingredients.children` gains Clarinol; `folded_label_components` becomes null on safflower labels while `children` keeps Safflower Oil. Of 188 non-volatile changed paths, none is a safety or warning path.

## Not done

- 184 rows where DSLD's alternate name alone hints at a preparation are in `alt_name_backlog.json` as a candidate backlog: `[id, brand, canonical, row, alternate name, form]`. It blocks nothing, and none of them is corrected here.
- 59 other `unspecified` CLA rows were not reviewed (for example 45103, 5812, 74397, 182799).
