# Phase 2 Migration Run Report

_Run: 2026-05-11T07:49:13.443649+00:00_

## Summary

- **forms_deleted_from_iqm**: 4
- **aliases_removed_from_iqm_forms**: 68
- **aliases_added_to_botanical_ingredients**: 96
- **aliases_added_to_standardized_botanicals**: 12
- **aliases_skipped_as_duplicate**: 11
- **qualify_entries_unchanged_in_data**: 10
- **new_botanical_canonical_created**: broccoli_sprout

## Per-form actions

- REMOVE 3 alias(es) from `aescin.aescin (unspecified)`; relocate to `horse_chestnut_seed` (botanical_ingredients)
- REMOVE 8 alias(es) from `capsaicin.capsaicin (unspecified)`; relocate to `cayenne_pepper` (botanical_ingredients)
- REMOVE 6 alias(es) from `capsaicin.capsaicin extract`; relocate to `cayenne_pepper` (botanical_ingredients)
- REMOVE 12 alias(es) from `capsaicin.capsimax`; relocate to `cayenne_pepper` (botanical_ingredients)
- REMOVE 3 alias(es) from `curcumin.bcm-95 curcumin`; relocate to `turmeric` (botanical_ingredients)
- REMOVE 4 alias(es) from `curcumin.curcumin (unspecified)`; relocate to `turmeric` (botanical_ingredients)
- REMOVE 1 alias(es) from `curcumin.curcumin c3 complex with bioperine`; relocate to `turmeric` (botanical_ingredients)
- REMOVE 14 alias(es) from `curcumin.meriva curcumin`; relocate to `turmeric` (botanical_ingredients)
- DELETE form `curcumin.turmeric powder (unstandardized)` (bio_score=4); relocate 3 aliases to `turmeric` (botanical_ingredients)
- REMOVE 4 alias(es) from `lycopene.lycopene extract`; relocate to `tomato` (botanical_ingredients)
- REMOVE 1 alias(es) from `quercetin.quercetin dihydrate`; relocate to `sophora_japonica` (botanical_ingredients)
- REMOVE 2 alias(es) from `quercetin.quercetin phytosome`; relocate to `sophora_japonica` (botanical_ingredients)
- REMOVE 8 alias(es) from `resveratrol.trans-resveratrol`; relocate to `japanese_knotweed` (botanical_ingredients)
- DELETE form `sulforaphane.broccoli sprout extract` (bio_score=11); relocate 11 aliases to `broccoli_sprout` (MISSING_NEEDS_CREATION)
- REMOVE 1 alias(es) from `sulforaphane.glucoraphanin`; relocate to `broccoli_sprout` (MISSING_NEEDS_CREATION)
- REMOVE 1 alias(es) from `sulforaphane.sulforaphane (unspecified)`; relocate to `broccoli_sprout` (MISSING_NEEDS_CREATION)
- DELETE form `vitamin_c.acerola cherry extract` (bio_score=12); relocate 23 aliases to `acerola_cherry` (botanical_ingredients)
- DELETE form `vitamin_c.camu camu extract` (bio_score=12); relocate 14 aliases to `camu_camu` (standardized_botanicals)

## Archive

Pre-migration snapshots: `scripts/data/_archive/iqm_pre_identity_split/`