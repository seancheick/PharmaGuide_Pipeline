# UNII Same-Tier Conflict Audit

Generated: 2026-05-25T21:09:22+00:00

## Scope

This is a read-only scanner for the runtime warning emitted by `EnhancedDSLDNormalizer._build_unii_to_payload_lookup`: same UNII, same lookup-priority tier, multiple records. Cross-tier collisions are intentionally excluded because runtime priority order resolves them.

Tier labels below are **effective runtime priorities** from the normalizer's fast exact lookup for active/safety sources. `other_ingredients.json` UNII records intentionally remain in the low-priority other-ingredient tier because inactive/excipient UNII recognition is handled by a separate context-aware enricher index.

No reference data was changed by this audit.

## Summary

- UNII-bearing records scanned: **1493**
- Same-tier UNII groups: **173**

| Severity | Groups |
|---|---:|
| high_review | 40 |
| review | 13 |
| info | 120 |

| Tier | Groups |
|---|---:|
| allergens | 3 |
| banned_recalled | 1 |
| botanical_ingredients | 3 |
| harmful_additives | 3 |
| ingredient_quality_map | 138 |
| other_ingredients | 18 |
| standardized_botanicals | 7 |

| Classification | Groups |
|---|---:|
| iqm_same_parent_parent_form | 120 |
| same_tier_different_names | 40 |
| same_tier_duplicate_name | 13 |

## High-Review Groups

### `3C3Y389JBU` — tier 2 `allergens` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `wheatgrass_powder` (botanical; Wheatgrass Powder)
- `ingredient_quality_map.json` → `wheatgrass` (iqm_parent; Wheatgrass, parent=`wheatgrass`)

### `86507VZR9K` — tier 2 `allergens` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `barley_grass` (botanical; Barley Grass)
- `botanical_ingredients.json` → `barley_grass_powder` (botanical; Barley Grass Powder)

### `11MSQ4JG7G` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `himematsutake` (botanical; Himematsutake)
- `standardized_botanicals.json` → `agaricus_blazei` (standardized_botanical; Agaricus Blazei)

### `1A64QN2D2F` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `shiitake_mushroom` (botanical; Shiitake Mushroom)
- `standardized_botanicals.json` → `shiitake` (standardized_botanical; Shiitake)

### `1L29G6428X` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `tart_cherry_fruit` (botanical; Tart Cherry Fruit)
- `standardized_botanicals.json` → `tart_cherry` (standardized_botanical; Tart Cherry)

### `31T0FF0472` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `standardized_botanicals.json` → `astaxanthin_haematococcus_pluvialis` (standardized_botanical; Astaxanthin (Haematococcus pluvialis))
- `standardized_botanicals.json` → `astazine` (standardized_botanical; AstaZine)

### `3S5ITS5ULN` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `rhodiola_rosea_root` (botanical; Rhodiola Rosea Root)
- `standardized_botanicals.json` → `rhodiola` (standardized_botanical; Rhodiola rosea)

### `46AM2VJ0AW` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `acai_berry` (botanical; Acai Berry)
- `standardized_botanicals.json` → `acai` (standardized_botanical; Acai)

### `654825W09Z` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `fenugreek_seed` (botanical; Fenugreek Seed)
- `standardized_botanicals.json` → `fenugreek` (standardized_botanical; Fenugreek)

### `714783Y9Z0` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `danshen` (botanical; Danshen)
- `standardized_botanicals.json` → `salvia_miltiorrhiza` (standardized_botanical; Salvia Miltiorrhiza)

### `HP7119212T` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `maca_root` (botanical; Maca Root)
- `standardized_botanicals.json` → `maca` (standardized_botanical; Maca)

### `J617U5X7NN` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `cordyceps_mushroom_powder` (botanical; Cordyceps Mushroom Powder)
- `standardized_botanicals.json` → `cordyceps_militaris` (standardized_botanical; Cordyceps militaris)

### `KM66971LVF` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `black_pepper` (botanical; Black Pepper)
- `standardized_botanicals.json` → `black_pepper_extract` (standardized_botanical; Black Pepper Extract)

### `QI7G114Y98` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `echinacea_purpurea_aerial` (botanical; Echinacea Purpurea Aerial)
- `standardized_botanicals.json` → `echinacea_purpurea` (standardized_botanical; Echinacea Purpurea)

### `SCJ765569P` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `holy_basil_leaf` (botanical; Holy Basil Leaf)
- `standardized_botanicals.json` → `holy_basil` (standardized_botanical; Holy Basil)

### `V038D626IF` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `ashwagandha_root` (botanical; Ashwagandha Root)
- `standardized_botanicals.json` → `ashwagandha` (standardized_botanical; Ashwagandha)
- `standardized_botanicals.json` → `ksm_66_ashwagandha` (standardized_botanical; KSM-66 Ashwagandha)

### `Y8P1YR4920` — tier 4 `ingredient_quality_map` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `shatavari_root` (botanical; Shatavari Root)
- `standardized_botanicals.json` → `shatavari` (standardized_botanical; Shatavari)

### `0MVO31Q3QS` — tier 5 `standardized_botanicals` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `standardized_botanicals.json` → `cran_max` (standardized_botanical; Cran-Max)
- `standardized_botanicals.json` → `flowens` (standardized_botanical; Flowens)
- `standardized_botanicals.json` → `pacran` (standardized_botanical; Pacran)

### `597E9BI3Z3` — tier 5 `standardized_botanicals` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `burdock_root_powder` (botanical; Burdock Root Powder)
- `standardized_botanicals.json` → `burdock_root` (standardized_botanical; Burdock Root)

### `KYV09BQ2YN` — tier 5 `standardized_botanicals` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `suma_root` (botanical; Suma Root)
- `standardized_botanicals.json` → `suma` (standardized_botanical; Suma)

### `MN25R0HH5A` — tier 5 `standardized_botanicals` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `white_mulberry` (botanical; White Mulberry)
- `standardized_botanicals.json` → `mulberry` (standardized_botanical; Mulberry)

### `7UI036LFRJ` — tier 6 `botanical_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `caralluma` (botanical; Caralluma)
- `botanical_ingredients.json` → `caralluma_fimbriata` (botanical; Caralluma Fimbriata)

### `BIA2SO6F5B` — tier 6 `botanical_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `galega_officinalis` (botanical; Galega Officinalis (French Lilac))
- `botanical_ingredients.json` → `goats_rue` (botanical; Goat's Rue)

### `JC71GJ1F3L` — tier 6 `botanical_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `botanical_ingredients.json` → `myrrh_resin` (botanical; Myrrh Resin)
- `botanical_ingredients.json` → `myrrh_resin_extract` (botanical; Myrrh Resin Extract)

### `0MVO31Q3QS` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_CRANBERRY_EXTRACT` (other_ingredient; Cranberry Concentrate)
- `other_ingredients.json` → `NHA_CRANBERRY_FIBER` (other_ingredient; Cranberry Fiber)

### `230OU9XXE4` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_MONO_DIGLYCERIDES` (other_ingredient; Mono and Diglycerides)
- `other_ingredients.json` → `PII_GLYCEROL_MONOSTEARATE` (other_ingredient; Glycerol Monostearate)

### `3OWL53L36A` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `PII_PARTECK` (other_ingredient; Parteck (Mannitol))
- `other_ingredients.json` → `PII_PEARLITOL` (other_ingredient; Pearlitol (Mannitol))

### `4J2TY8Y81V` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_STRAWBERRY_PUREE` (other_ingredient; Strawberry Puree)
- `other_ingredients.json` → `OI_NATURAL_STRAWBERRY_FLAVOR` (other_ingredient; Natural Strawberry Flavor)

### `5EVU04N5QU` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_ORANGE_CRYSTALS` (other_ingredient; Orange Crystals)
- `other_ingredients.json` → `NHA_ORANGE_FLAVOR` (other_ingredient; Orange Flavor)

### `5MG5Z946UO` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `OI_CAROB_CARAMEL` (other_ingredient; Carob and Caramel)
- `other_ingredients.json` → `PII_CAROB_STJOHNS_BREAD` (other_ingredient; Carob (St. John's Bread))

### `6PQP1V1B6O` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_ANNATTO_VARIANTS` (other_ingredient; Annatto (Variants))
- `other_ingredients.json` → `NHA_FRUIT_VEG_POWDERS` (other_ingredient; Fruit & Vegetable Powders)
- `other_ingredients.json` → `OI_ANNATTO_EXTRACT` (other_ingredient; Annatto Extract)

### `B423VGH5S9` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_APPLE_PUREE_CONCENTRATE` (other_ingredient; Apple Puree Concentrate)
- `other_ingredients.json` → `NHA_NATURAL_APPLE_FLAVOR` (other_ingredient; Natural Apple Flavor)
- `other_ingredients.json` → `PII_APPLE_FLAVOR` (other_ingredient; Apple Flavor)

### `C4YAD5F5G6` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `PII_GLYCEROL_MONOOLEATE` (other_ingredient; Glycerol Monooleate)
- `other_ingredients.json` → `PII_GLYCERYL_MONOOLEATE` (other_ingredient; Glyceryl Monooleate)

### `C5529G5JPQ` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_GINGER_EXTRACT` (other_ingredient; Ginger Extract)
- `other_ingredients.json` → `NHA_GINGER_FLAVOR` (other_ingredient; Ginger Flavor)

### `E89I1637KE` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_PARTIALLY_HYDROLYZED_GUAR_GUM` (other_ingredient; Partially Hydrolyzed Guar Gum)
- `other_ingredients.json` → `OI_GUAR_GUM` (other_ingredient; Guar Gum)

### `FZ989GH94E` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_PVP` (other_ingredient; Polyvinyl Pyrrolidone)
- `other_ingredients.json` → `PII_KOLLIDON` (other_ingredient; Kollidon (Polyvinylpyrrolidone))
- `other_ingredients.json` → `PII_POVIDONE` (other_ingredient; Povidone)

### `K679OBS311` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `OI_CELLULOSE_GUM` (other_ingredient; Cellulose Gum)
- `other_ingredients.json` → `PII_SODIUM_CARBOXYMETHYLCELLULOSE` (other_ingredient; Sodium Carboxymethylcellulose)

### `LSU3YX0KZO` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_BLACK_STRAP_MOLASSES` (other_ingredient; Blackstrap Molasses)
- `other_ingredients.json` → `NHA_MAPLE_MOLASSES` (other_ingredient; Maple Syrup & Molasses)

### `R60QEP13IC` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `NHA_RICE_BRAN_EXTRACT` (other_ingredient; Rice Bran Extract)
- `other_ingredients.json` → `NHA_RICE_EXTRACT` (other_ingredient; Rice Extract Blend)
- `other_ingredients.json` → `OI_RICE_FIBER` (other_ingredient; Rice Fiber)

### `Y9H1V576FH` — tier 9 `other_ingredients` (same_tier_different_names, high_review)

- Action: `verify_unii_assignment`
- Reason: Same-tier records have materially different names; first-write wins at runtime until reviewed.
- `other_ingredients.json` → `PII_HONEY` (other_ingredient; Honey)
- `other_ingredients.json` → `PII_HONEY_FLAVOR` (other_ingredient; Honey Flavor)


## Review Groups

### `8W94T9026R` — tier 1 `banned_recalled` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `banned_recalled_ingredients.json` → `RISK_GARCINIA_CAMBOGIA` (banned; Garcinia Cambogia)
- `ingredient_quality_map.json` → `garcinia_cambogia` (iqm_parent; Garcinia Cambogia (Hydroxycitric Acid), parent=`garcinia_cambogia`)

### `KQX236OK4U` — tier 2 `allergens` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `oat_bran` (botanical; Oat Bran)
- `ingredient_quality_map.json` → `oat_bran` (iqm_parent; Oat Bran, parent=`oat_bran`)

### `331KBJ17RK` — tier 3 `harmful_additives` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `ingredient_quality_map.json` → `canola_oil.forms[canola oil]` (iqm_form; canola oil, parent=`canola_oil`)
- `ingredient_quality_map.json` → `canola_oil` (iqm_parent; Canola Oil (Brassica napus), parent=`canola_oil`)

### `PHA4727WTP` — tier 3 `harmful_additives` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `d_mannose` (botanical; D-Mannose)
- `ingredient_quality_map.json` → `d_mannose.forms[d-mannose]` (iqm_form; d-mannose, parent=`d_mannose`)
- `ingredient_quality_map.json` → `d_mannose` (iqm_parent; D-Mannose, parent=`d_mannose`)

### `VCQ006KQ1E` — tier 3 `harmful_additives` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `ingredient_quality_map.json` → `xylitol.forms[xylitol]` (iqm_form; xylitol, parent=`xylitol`)
- `ingredient_quality_map.json` → `xylitol` (iqm_parent; Xylitol, parent=`xylitol`)

### `0P49L952WZ` — tier 4 `ingredient_quality_map` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `andrographis` (botanical; Andrographis)
- `standardized_botanicals.json` → `andrographis` (standardized_botanical; Andrographis)

### `4G174V5051` — tier 4 `ingredient_quality_map` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `beetroot` (botanical; Beetroot)
- `standardized_botanicals.json` → `beetroot` (standardized_botanical; Beetroot)

### `7M867G6T1U` — tier 4 `ingredient_quality_map` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `gotu_kola` (botanical; Gotu Kola)
- `standardized_botanicals.json` → `gotu_kola` (standardized_botanical; Gotu Kola)

### `F84709P2XV` — tier 5 `standardized_botanicals` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `wormwood_leaf` (botanical; Wormwood)
- `standardized_botanicals.json` → `wormwood` (standardized_botanical; Wormwood)

### `PQM9SA369U` — tier 5 `standardized_botanicals` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `kola_nut` (botanical; Kola Nut)
- `standardized_botanicals.json` → `kola_nut` (standardized_botanical; Kola Nut)

### `UOI4FT57BZ` — tier 5 `standardized_botanicals` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `botanical_ingredients.json` → `broccoli` (botanical; Broccoli)
- `standardized_botanicals.json` → `broccoli` (standardized_botanical; Broccoli)

### `H8AV0SQX4D` — tier 9 `other_ingredients` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `other_ingredients.json` → `NHA_SODIUM_STARCH_GLYCOLATE` (other_ingredient; Sodium Starch Glycolate)
- `other_ingredients.json` → `PII_SODIUM_STARCH_GLYCOLATE` (other_ingredient; Sodium Starch Glycolate)

### `M4I0D6VV5M` — tier 9 `other_ingredients` (same_tier_duplicate_name, review)

- Action: `review_duplicate_or_alias_model`
- Reason: Same-tier records have the same normalized name; may be duplicate modeling or alias drift.
- `other_ingredients.json` → `NHA_CALCIUM_CHLORIDE` (other_ingredient; Calcium Chloride)
- `other_ingredients.json` → `PII_CALCIUM_CHLORIDE_EXCIPIENT` (other_ingredient; Calcium Chloride (Excipient))


## Info / Suppression-Candidate Groups

### `0111871I23` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `huperzine_a` (botanical; Huperzine A)
- `ingredient_quality_map.json` → `huperzine_a` (iqm_parent; Huperzine A, parent=`huperzine_a`)

### `01G73H6H83` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `hops` (iqm_parent; Hops (Humulus lupulus), parent=`hops`)
- `standardized_botanicals.json` → `hops` (standardized_botanical; Hops)

### `065C5D077J` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `sage_leaf_extract` (botanical; Sage Leaf Extract)
- `ingredient_quality_map.json` → `sage` (iqm_parent; Sage, parent=`sage`)

### `0I8Y3P32UF` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `berberine_supplement` (iqm_parent; Berberine, parent=`berberine_supplement`)
- `standardized_botanicals.json` → `berberine` (standardized_botanical; Berberine)

### `0MVO31Q3QS` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `cranberry` (botanical; Cranberry)
- `botanical_ingredients.json` → `cranberry_fruit` (botanical; Cranberry Fruit)
- `ingredient_quality_map.json` → `cranberry` (iqm_parent; Cranberry, parent=`cranberry`)

### `0UE22Q87VC` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `apple_cider_vinegar` (botanical; Apple Cider Vinegar)
- `ingredient_quality_map.json` → `apple_cider_vinegar` (iqm_parent; Apple Cider Vinegar, parent=`apple_cider_vinegar`)

### `19F5HK2737` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `vitamin_b5_pantothenic.forms[pantothenic acid]` (iqm_form; pantothenic acid, parent=`vitamin_b5_pantothenic`)
- `ingredient_quality_map.json` → `vitamin_b5_pantothenic` (iqm_parent; Vitamin B5 (Pantothenic Acid), parent=`vitamin_b5_pantothenic`)

### `19FUJ2C58T` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `ginkgo_biloba_leaf` (botanical; Ginkgo Biloba Leaf)
- `ingredient_quality_map.json` → `ginkgo` (iqm_parent; Ginkgo, parent=`ginkgo`)

### `19MU22KQ26` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `picrorhiza_kurroa` (botanical; Picrorhiza kurroa)
- `ingredient_quality_map.json` → `picrorhiza` (iqm_parent; Picrorhiza Kurroa, parent=`picrorhiza`)

### `1LIB31N73G` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `mung_bean` (botanical; Mung Bean)
- `ingredient_quality_map.json` → `mung_bean` (iqm_parent; Mung Bean Extract, parent=`mung_bean`)

### `205MXS71H7` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `white_willow_bark` (botanical; White Willow Bark)
- `ingredient_quality_map.json` → `white_willow_bark` (iqm_parent; White Willow Bark, parent=`white_willow_bark`)
- `standardized_botanicals.json` → `white_willow_bark` (standardized_botanical; White Willow Bark)

### `209B6YPZ4I` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `palmitoleic_acid.forms[palmitoleic acid]` (iqm_form; palmitoleic acid, parent=`palmitoleic_acid`)
- `ingredient_quality_map.json` → `palmitoleic_acid` (iqm_parent; Palmitoleic Acid, parent=`palmitoleic_acid`)

### `253RUG1X1A` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `blueberry` (botanical; Blueberry)
- `ingredient_quality_map.json` → `blueberry` (iqm_parent; Blueberry, parent=`blueberry`)
- `standardized_botanicals.json` → `blueberry` (standardized_botanical; Blueberry)

### `268IL53Q7O` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `lactobacillus_brevis.forms[lactobacillus brevis (unspecified)]` (iqm_form; lactobacillus brevis (unspecified), parent=`lactobacillus_brevis`)
- `ingredient_quality_map.json` → `lactobacillus_brevis` (iqm_parent; Lactobacillus Brevis, parent=`lactobacillus_brevis`)

### `2968PHW8QP` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `citric_acid.forms[citric acid]` (iqm_form; citric acid, parent=`citric_acid`)
- `ingredient_quality_map.json` → `citric_acid` (iqm_parent; Citric Acid, parent=`citric_acid`)

### `2H1576D5WG` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `sarsaparilla` (botanical; Sarsaparilla)
- `ingredient_quality_map.json` → `sarsaparilla` (iqm_parent; Sarsaparilla, parent=`sarsaparilla`)

### `2JN37DC03A` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `mucuna_pruriens` (botanical; Mucuna Pruriens)
- `ingredient_quality_map.json` → `mucuna_pruriens` (iqm_parent; Mucuna Pruriens (Velvet Bean), parent=`mucuna_pruriens`)
- `standardized_botanicals.json` → `mucuna_pruriens` (standardized_botanical; Mucuna Pruriens)

### `2UMI9U37CP` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `oleic_acid.forms[oleic acid]` (iqm_form; oleic acid, parent=`oleic_acid`)
- `ingredient_quality_map.json` → `oleic_acid` (iqm_parent; Oleic Acid, parent=`oleic_acid`)

### `2V16EO95H1` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `palmitic_acid.forms[palmitic acid (unspecified)]` (iqm_form; palmitic acid (unspecified), parent=`palmitic_acid`)
- `ingredient_quality_map.json` → `palmitic_acid` (iqm_parent; Palmitic Acid, parent=`palmitic_acid`)

### `34969JX79R` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `guggul` (botanical; Guggul)
- `ingredient_quality_map.json` → `guggul` (iqm_parent; Guggul (Commiphora mukul), parent=`guggul`)

### `3729L8MA2C` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `bee_pollen` (botanical; Bee Pollen)
- `ingredient_quality_map.json` → `bee_pollen` (iqm_parent; Bee Pollen, parent=`bee_pollen`)

### `394XK0IH40` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `phosphatidylserine` (botanical; Phosphatidylserine)
- `ingredient_quality_map.json` → `phosphatidylserine` (iqm_parent; Phosphatidylserine, parent=`phosphatidylserine`)
- `standardized_botanicals.json` → `sharp_ps_green` (standardized_botanical; Sharp-PS Green)

### `39981FM375` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `dandelion` (botanical; Dandelion)
- `ingredient_quality_map.json` → `dandelion` (iqm_parent; Dandelion, parent=`dandelion`)
- `standardized_botanicals.json` → `dandelion` (standardized_botanical; Dandelion)

### `3C18L6RJAZ` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `horse_chestnut_seed` (botanical; Horse Chestnut Seed)
- `ingredient_quality_map.json` → `horse_chestnut_seed` (iqm_parent; Horse Chestnut Seed, parent=`horse_chestnut_seed`)

### `3W1JG795YI` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `sunflower_oil.forms[sunflower oil]` (iqm_form; sunflower oil, parent=`sunflower_oil`)
- `ingredient_quality_map.json` → `sunflower_oil` (iqm_parent; Sunflower Oil, parent=`sunflower_oil`)

### `4V59G5UW9X` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `argan_oil.forms[argan oil]` (iqm_form; argan oil, parent=`argan_oil`)
- `ingredient_quality_map.json` → `argan_oil` (iqm_parent; Argan Oil, parent=`argan_oil`)

### `4X4HLN92OT` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `tribulus_terrestris` (botanical; Tribulus terrestris)
- `ingredient_quality_map.json` → `tribulus` (iqm_parent; Tribulus Terrestris, parent=`tribulus`)
- `standardized_botanicals.json` → `tribulus` (standardized_botanical; Tribulus)

### `50JZ5Z98QY` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `pine_bark_extract` (botanical; Pine Bark Extract)
- `ingredient_quality_map.json` → `pine_bark_extract` (iqm_parent; Pine Bark Extract, parent=`pine_bark_extract`)
- `standardized_botanicals.json` → `pycnogenol` (standardized_botanical; Pycnogenol)

### `52U584F1CA` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `guarana` (iqm_parent; Guarana, parent=`guarana`)
- `standardized_botanicals.json` → `guarana` (standardized_botanical; Guarana)

### `56687D1Z4D` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `pomegranate` (botanical; Pomegranate)
- `ingredient_quality_map.json` → `pomegranate` (iqm_parent; Pomegranate, parent=`pomegranate`)
- `standardized_botanicals.json` → `pomegranate` (standardized_botanical; Pomegranate)

### `5M609NV974` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `magnolia_bark` (iqm_parent; Magnolia Bark, parent=`magnolia_bark`)
- `standardized_botanicals.json` → `magnolia_bark` (standardized_botanical; Magnolia Bark)

### `5S29HWU6QB` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `ceylon_cinnamon` (botanical; Ceylon Cinnamon)
- `botanical_ingredients.json` → `cinnamon` (botanical; Cinnamon)
- `ingredient_quality_map.json` → `cinnamon` (iqm_parent; Cinnamon, parent=`cinnamon`)

### `61H4T033E5` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `orotic_acid.forms[orotic acid]` (iqm_form; orotic acid, parent=`orotic_acid`)
- `ingredient_quality_map.json` → `orotic_acid` (iqm_parent; Orotic Acid, parent=`orotic_acid`)

### `61ZBX54883` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `licorice_root` (botanical; Licorice Root)
- `ingredient_quality_map.json` → `licorice` (iqm_parent; Licorice, parent=`licorice`)
- `standardized_botanicals.json` → `licorice` (standardized_botanical; Licorice)

### `63POE2M46Y` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `slippery_elm` (botanical; Slippery Elm)
- `ingredient_quality_map.json` → `slippery_elm` (iqm_parent; Slippery Elm, parent=`slippery_elm`)

### `6E5QR5USSP` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `pumpkin_seed_oil.forms[pumpkin seed oil]` (iqm_form; pumpkin seed oil, parent=`pumpkin_seed_oil`)
- `ingredient_quality_map.json` → `pumpkin_seed_oil` (iqm_parent; Pumpkin Seed Oil, parent=`pumpkin_seed_oil`)

### `6M47G7C4SY` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `cayenne_pepper` (botanical; Cayenne Pepper)
- `ingredient_quality_map.json` → `cayenne_pepper` (iqm_parent; Cayenne Pepper, parent=`cayenne_pepper`)

### `6R8T1UDM3V` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `palmitoylethanolamide` (iqm_parent; Palmitoylethanolamide, parent=`palmitoylethanolamide`)
- `standardized_botanicals.json` → `levagen` (standardized_botanical; Levagen)

### `6Y8XYV2NOF` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `propolis` (iqm_parent; Propolis, parent=`propolis`)
- `standardized_botanicals.json` → `propolis` (standardized_botanical; Propolis)

### `709HYI14M4` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `pygeum` (iqm_parent; Pygeum, parent=`pygeum`)
- `standardized_botanicals.json` → `pygeum` (standardized_botanical; Pygeum)

### `710FLW4U46` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `stinging_nettle` (iqm_parent; Stinging Nettle, parent=`stinging_nettle`)
- `standardized_botanicals.json` → `nettle` (standardized_botanical; Nettle (Urtica dioica))

### `731P2LE49E` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `kaempferol.forms[kaempferol]` (iqm_form; kaempferol, parent=`kaempferol`)
- `ingredient_quality_map.json` → `kaempferol` (iqm_parent; Kaempferol, parent=`kaempferol`)

### `73R90F7MQ8` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `pregnenolone.forms[pregnenolone]` (iqm_form; pregnenolone, parent=`pregnenolone`)
- `ingredient_quality_map.json` → `pregnenolone` (iqm_parent; Pregnenolone, parent=`pregnenolone`)

### `8021PR16QO` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `l_theanine` (botanical; L-Theanine)
- `ingredient_quality_map.json` → `l_theanine` (iqm_parent; L-Theanine, parent=`l_theanine`)

### `8369GFM6LY` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `butterbur` (iqm_parent; Butterbur (Petasites hybridus), parent=`butterbur`)
- `standardized_botanicals.json` → `butterbur` (standardized_botanical; Butterbur)

### `856YO1Z64F` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `turmeric` (botanical; Turmeric)
- `botanical_ingredients.json` → `turmeric_root_powder` (botanical; Turmeric Root Powder)
- `ingredient_quality_map.json` → `turmeric` (iqm_parent; Turmeric, parent=`turmeric`)
- `standardized_botanicals.json` → `turmeric` (standardized_botanical; Turmeric)

### `8GOM182CI3` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `tongkat_ali` (botanical; Tongkat Ali)
- `ingredient_quality_map.json` → `tongkat_ali` (iqm_parent; Tongkat Ali, parent=`tongkat_ali`)
- `standardized_botanicals.json` → `tongkat_ali` (standardized_botanical; Tongkat Ali)

### `8Q1GYP08KU` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `cordyceps` (iqm_parent; Cordyceps, parent=`cordyceps`)
- `standardized_botanicals.json` → `cordyceps` (standardized_botanical; Cordyceps sinensis)

### `8XPW32PR7I` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `astaxanthin` (botanical; Astaxanthin)
- `ingredient_quality_map.json` → `astaxanthin` (iqm_parent; Astaxanthin, parent=`astaxanthin`)

### `9060PRM18Q` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `cat_s_claw` (iqm_parent; Cat's Claw, parent=`cat_s_claw`)
- `standardized_botanicals.json` → `cat_s_claw` (standardized_botanical; Cat's Claw)

### `9294024N9Q` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `lychee_polyphenol.forms[lychee polyphenol (unspecified)]` (iqm_form; lychee polyphenol (unspecified), parent=`lychee_polyphenol`)
- `ingredient_quality_map.json` → `lychee_polyphenol` (iqm_parent; Lychee Polyphenol, parent=`lychee_polyphenol`)

### `930626MWDL` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `goji_berry` (botanical; Goji Berry)
- `ingredient_quality_map.json` → `goji_berry` (iqm_parent; Goji Berry, parent=`goji_berry`)

### `935E97BOY8` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `vitamin_b9_folate.forms[folic acid]` (iqm_form; folic acid, parent=`vitamin_b9_folate`)
- `ingredient_quality_map.json` → `vitamin_b9_folate` (iqm_parent; Vitamin B9 (Folate), parent=`vitamin_b9_folate`)

### `9603LN7R2Q` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `creatine_monohydrate.forms[creatine monohydrate]` (iqm_form; creatine monohydrate, parent=`creatine_monohydrate`)
- `ingredient_quality_map.json` → `creatine_monohydrate` (iqm_parent; Creatine Monohydrate, parent=`creatine_monohydrate`)

### `9755T40D11` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `black_currant` (iqm_parent; Black Currant, parent=`black_currant`)
- `standardized_botanicals.json` → `black_currant` (standardized_botanical; Black Currant)

### `98HPY76U4W` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `beef_tallow.forms[beef tallow]` (iqm_form; beef tallow, parent=`beef_tallow`)
- `ingredient_quality_map.json` → `beef_tallow` (iqm_parent; Beef Tallow, parent=`beef_tallow`)

### `9B45E1E94Z` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `amla` (iqm_parent; Amla (Phyllanthus emblica), parent=`amla`)
- `standardized_botanicals.json` → `amla` (standardized_botanical; Amla)

### `9IKM0I5T1E` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `quercetin` (iqm_parent; Quercetin, parent=`quercetin`)
- `standardized_botanicals.json` → `quercetin` (standardized_botanical; Quercetin)

### `9L3TIH1UUE` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `spirulina_powder` (botanical; Spirulina Powder)
- `ingredient_quality_map.json` → `spirulina` (iqm_parent; Spirulina, parent=`spirulina`)
- `standardized_botanicals.json` → `spirulina` (standardized_botanical; Spirulina)

### `9P2U39H18W` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `bilberry` (botanical; Bilberry)
- `botanical_ingredients.json` → `bilberry_fruit` (botanical; Bilberry Fruit)
- `ingredient_quality_map.json` → `bilberry` (iqm_parent; Bilberry, parent=`bilberry`)
- `standardized_botanicals.json` → `bilberry` (standardized_botanical; Bilberry (Vaccinium myrtillus))

### `A1ST9M22TO` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `black_ginger` (botanical; Black Ginger)
- `ingredient_quality_map.json` → `kaempferia_parviflora` (iqm_parent; Kaempferia Parviflora, parent=`kaempferia_parviflora`)

### `A1U5YJI0Z8` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `maitake` (botanical; Maitake)
- `ingredient_quality_map.json` → `maitake` (iqm_parent; Maitake, parent=`maitake`)
- `standardized_botanicals.json` → `maitake` (standardized_botanical; Maitake)

### `A77056YJ4K` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `black_cherry` (botanical; Black Cherry)
- `ingredient_quality_map.json` → `black_cherry` (iqm_parent; Black Cherry, parent=`black_cherry`)

### `AB6MNQ6J6L` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `succinic_acid.forms[succinic acid]` (iqm_form; succinic acid, parent=`succinic_acid`)
- `ingredient_quality_map.json` → `succinic_acid` (iqm_parent; Succinic Acid, parent=`succinic_acid`)

### `BD70459I50` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `lemon_bioflavonoids` (botanical; Lemon Bioflavonoids)
- `ingredient_quality_map.json` → `citrus_bioflavonoids` (iqm_parent; Citrus Bioflavonoids, parent=`citrus_bioflavonoids`)

### `BQY1UBX046` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `elderberries` (botanical; Elderberries)
- `ingredient_quality_map.json` → `elderberry` (iqm_parent; Elderberry, parent=`elderberry`)
- `standardized_botanicals.json` → `elderberry` (standardized_botanical; Elderberry)

### `C5529G5JPQ` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `ginger_extract` (botanical; Ginger Extract)
- `botanical_ingredients.json` → `ginger_root` (botanical; Ginger Root)
- `ingredient_quality_map.json` → `ginger` (iqm_parent; Ginger, parent=`ginger`)
- `standardized_botanicals.json` → `ginger_extract` (standardized_botanical; Ginger (Zingiber officinale))

### `CHC1JS541R` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `gynostemma` (botanical; Gynostemma)
- `ingredient_quality_map.json` → `gypenosides` (iqm_parent; Gypenosides, parent=`gypenosides`)
- `standardized_botanicals.json` → `gynostemma` (standardized_botanical; Gynostemma)

### `CLF5YFS11O` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `passionflower` (iqm_parent; Passionflower, parent=`passionflower`)
- `standardized_botanicals.json` → `passionflower` (standardized_botanical; Passionflower)

### `CS4U38E731` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `black_seed_oil` (iqm_parent; Black Seed Oil (Nigella Sativa), parent=`black_seed_oil`)
- `standardized_botanicals.json` → `black_seed_oil` (standardized_botanical; Black Seed Oil)

### `CUQ3A77YXI` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `ginseng` (iqm_parent; Ginseng, parent=`ginseng`)
- `standardized_botanicals.json` → `panax_ginseng` (standardized_botanical; Panax Ginseng)

### `CW657OBU4N` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `thyme` (botanical; Thyme)
- `ingredient_quality_map.json` → `thyme_extract` (iqm_parent; Thyme Extract, parent=`thyme_extract`)
- `standardized_botanicals.json` → `thyme` (standardized_botanical; Thyme)

### `D65QWF3541` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `pau_darco_bark` (botanical; Pau d'Arco Bark)
- `ingredient_quality_map.json` → `pau_darco` (iqm_parent; Pau D'Arco, parent=`pau_darco`)

### `D9108TZ9KG` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `cacao_powder` (botanical; Cacao Powder)
- `ingredient_quality_map.json` → `cocoa` (iqm_parent; Cocoa, parent=`cocoa`)

### `E750O06Y6O` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `hesperidin` (botanical; Hesperidin)
- `ingredient_quality_map.json` → `citrus_bioflavonoids.forms[hesperidin]` (iqm_form; hesperidin, parent=`citrus_bioflavonoids`)

### `E849G4X5YJ` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `saffron` (botanical; Saffron)
- `ingredient_quality_map.json` → `saffron` (iqm_parent; Saffron, parent=`saffron`)

### `F8XAG1755S` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `borage_seed_oil.forms[borage seed oil]` (iqm_form; borage seed oil, parent=`borage_seed_oil`)
- `ingredient_quality_map.json` → `borage_seed_oil` (iqm_parent; Borage Seed Oil, parent=`borage_seed_oil`)

### `FGL3685T2X` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `chamomile` (botanical; Chamomile)
- `ingredient_quality_map.json` → `chamomile` (iqm_parent; Chamomile, parent=`chamomile`)

### `HB6PN45W4J` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `idebenone.forms[idebenone]` (iqm_form; idebenone, parent=`idebenone`)
- `ingredient_quality_map.json` → `idebenone` (iqm_parent; Idebenone, parent=`idebenone`)

### `HN5425SBF2` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `naringenin.forms[naringenin]` (iqm_form; naringenin, parent=`naringenin`)
- `ingredient_quality_map.json` → `naringenin` (iqm_parent; Naringenin, parent=`naringenin`)

### `HOX6BEK27Q` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `coffee_fruit` (botanical; Coffee Fruit)
- `ingredient_quality_map.json` → `coffee_fruit` (iqm_parent; Coffee Fruit Extract, parent=`coffee_fruit`)
- `standardized_botanicals.json` → `coffeeberry` (standardized_botanical; CoffeeBerry (whole coffee fruit extract))

### `IJ67X351P9` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `rosemary` (iqm_parent; Rosemary, parent=`rosemary`)
- `standardized_botanicals.json` → `rosemary` (standardized_botanical; Rosemary)

### `IT942ZTH98` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `curcumin` (iqm_parent; Curcumin, parent=`curcumin`)
- `standardized_botanicals.json` → `curcumin` (standardized_botanical; Curcumin)

### `IWY3IWX2G8` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `wild_yam_root` (botanical; Wild Yam Root)
- `ingredient_quality_map.json` → `wild_yam` (iqm_parent; Wild Yam, parent=`wild_yam`)
- `standardized_botanicals.json` → `wild_yam` (standardized_botanical; Wild Yam)

### `J7WWH9M8QS` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `saw_palmetto_berry` (botanical; Saw Palmetto Berry)
- `ingredient_quality_map.json` → `saw_palmetto` (iqm_parent; Saw Palmetto, parent=`saw_palmetto`)
- `standardized_botanicals.json` → `saw_palmetto` (standardized_botanical; Saw Palmetto)

### `JL5DK93RCL` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `melatonin` (iqm_parent; Melatonin, parent=`melatonin`)
- `standardized_botanicals.json` → `microactive_melatonin` (standardized_botanical; MicroActive Melatonin)

### `JOS53KRJ01` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `inulin` (botanical; Inulin)
- `ingredient_quality_map.json` → `inulin` (iqm_parent; Inulin, parent=`inulin`)

### `JWF5YAW3QW` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `valerian_root` (botanical; Valerian Root)
- `ingredient_quality_map.json` → `valerian` (iqm_parent; Valerian, parent=`valerian`)
- `standardized_botanicals.json` → `valerian` (standardized_botanical; Valerian)

### `K5877MW0LE` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `watercress_herb` (botanical; Watercress Herb)
- `ingredient_quality_map.json` → `watercress` (iqm_parent; Watercress, parent=`watercress`)

### `K73E24S6X9` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `black_cohosh` (botanical; Black Cohosh)
- `ingredient_quality_map.json` → `black_cohosh` (iqm_parent; Black Cohosh, parent=`black_cohosh`)

### `KP2MW85SSQ` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `vitamin_e.forms[tocotrienols]` (iqm_form; tocotrienols, parent=`vitamin_e`)
- `ingredient_quality_map.json` → `vitamin_e` (iqm_parent; Vitamin E, parent=`vitamin_e`)

### `KU94FIY6JB` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `papaya_fruit_powder` (botanical; Papaya Fruit Powder)
- `ingredient_quality_map.json` → `papaya` (iqm_parent; Papaya, parent=`papaya`)

### `L497I37F0C` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `royal_jelly.forms[royal jelly]` (iqm_form; royal jelly, parent=`royal_jelly`)
- `ingredient_quality_map.json` → `royal_jelly` (iqm_parent; Royal Jelly, parent=`royal_jelly`)

### `L9153EKV2Y` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `red_clover` (botanical; Red Clover)
- `botanical_ingredients.json` → `red_clover_flower` (botanical; Red Clover Flower)
- `ingredient_quality_map.json` → `red_clover` (iqm_parent; Red Clover, parent=`red_clover`)
- `standardized_botanicals.json` → `red_clover` (standardized_botanical; Red Clover)

### `LYR4M0NH37` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `sodium.forms[sodium (unspecified)]` (iqm_form; sodium (unspecified), parent=`sodium`)
- `ingredient_quality_map.json` → `sodium` (iqm_parent; Sodium, parent=`sodium`)

### `NU0OLX06F8` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `chia_seed` (botanical; Chia Seed)
- `ingredient_quality_map.json` → `chia_seed.forms[chia seed]` (iqm_form; chia seed, parent=`chia_seed`)
- `ingredient_quality_map.json` → `chia_seed` (iqm_parent; Chia Seed, parent=`chia_seed`)

### `P6YC3EG204` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `vitamin_b12_cobalamin.forms[cyanocobalamin]` (iqm_form; cyanocobalamin, parent=`vitamin_b12_cobalamin`)
- `ingredient_quality_map.json` → `vitamin_b12_cobalamin` (iqm_parent; Vitamin B12, parent=`vitamin_b12_cobalamin`)

### `PQ6CK8PD0R` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `vitamin_c.forms[ascorbic acid]` (iqm_form; ascorbic acid, parent=`vitamin_c`)
- `ingredient_quality_map.json` → `vitamin_c` (iqm_parent; Vitamin C, parent=`vitamin_c`)

### `Q369O8926L` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `resveratrol` (iqm_parent; Resveratrol, parent=`resveratrol`)
- `standardized_botanicals.json` → `resveratrol` (standardized_botanical; Resveratrol)

### `Q46FF3N01L` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `grains_of_paradise` (iqm_parent; Grains of Paradise, parent=`grains_of_paradise`)
- `standardized_botanicals.json` → `grains_of_paradise` (standardized_botanical; Grains of Paradise)

### `RDS2V6DVY5` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `grape_seed_extract` (iqm_parent; Grape Seed Extract, parent=`grape_seed_extract`)
- `standardized_botanicals.json` → `grape_seed` (standardized_botanical; Grape Seed (Vitis vinifera seed))
- `standardized_botanicals.json` → `grape_seed_extract` (standardized_botanical; Grape Seed Extract)

### `RU0176QL8I` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `agmatine.forms[agmatine sulfate]` (iqm_form; agmatine sulfate, parent=`agmatine`)
- `ingredient_quality_map.json` → `agmatine` (iqm_parent; Agmatine Sulfate, parent=`agmatine`)

### `S347WMO6M4` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `phytosterols.forms[beta-sitosterol]` (iqm_form; beta-sitosterol, parent=`phytosterols`)
- `ingredient_quality_map.json` → `phytosterols` (iqm_parent; Phytosterols, parent=`phytosterols`)

### `SSZ9HQT61Z` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `diindolylmethane.forms[diindolylmethane (dim)]` (iqm_form; diindolylmethane (dim), parent=`diindolylmethane`)
- `ingredient_quality_map.json` → `diindolylmethane` (iqm_parent; Diindolylmethane (DIM), parent=`diindolylmethane`)

### `T538276W1L` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `woad` (botanical; Woad)
- `ingredient_quality_map.json` → `isatis` (iqm_parent; Isatis tinctoria, parent=`isatis`)

### `TJ6XA84OQF` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `cutch_tree` (botanical; Cutch Tree)
- `ingredient_quality_map.json` → `acacia_catechu` (iqm_parent; Acacia Catechu, parent=`acacia_catechu`)

### `TKD8LH0X2Z` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `reishi_mushroom` (botanical; Reishi Mushroom)
- `ingredient_quality_map.json` → `reishi` (iqm_parent; Reishi, parent=`reishi`)
- `standardized_botanicals.json` → `reishi` (standardized_botanical; Reishi)

### `TLM2976OFR` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `vitamin_b2_riboflavin.forms[riboflavin]` (iqm_form; riboflavin, parent=`vitamin_b2_riboflavin`)
- `ingredient_quality_map.json` → `vitamin_b2_riboflavin` (iqm_parent; Vitamin B2 (Riboflavin), parent=`vitamin_b2_riboflavin`)

### `U182GP2CF3` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `bromelain` (iqm_parent; Bromelain, parent=`bromelain`)
- `standardized_botanicals.json` → `bromelain` (standardized_botanical; Bromelain)

### `U946SH95EE` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `milk_thistle` (botanical; Milk Thistle)
- `botanical_ingredients.json` → `milk_thistle_seed` (botanical; Milk Thistle Seed)
- `ingredient_quality_map.json` → `milk_thistle` (iqm_parent; Milk Thistle, parent=`milk_thistle`)
- `standardized_botanicals.json` → `milk_thistle` (standardized_botanical; Milk Thistle)

### `UFH8805FKA` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `st_john_s_wort` (botanical; St. John's Wort)
- `ingredient_quality_map.json` → `st_johns_wort` (iqm_parent; St. John's Wort, parent=`st_johns_wort`)
- `standardized_botanicals.json` → `st_john_s_wort` (standardized_botanical; St. John's Wort)

### `V1V998DC17` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `black_garlic` (botanical; Black Garlic)
- `ingredient_quality_map.json` → `garlic` (iqm_parent; Garlic, parent=`garlic`)

### `V95R5KMY2B` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `peppermint` (botanical; Peppermint)
- `ingredient_quality_map.json` → `peppermint` (iqm_parent; Peppermint, parent=`peppermint`)
- `standardized_botanicals.json` → `peppermint` (standardized_botanical; Peppermint)

### `VB06AV5US8` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `echinacea_angustifolia` (botanical; Echinacea Angustifolia)
- `ingredient_quality_map.json` → `echinacea.forms[echinacea angustifolia]` (iqm_form; echinacea angustifolia, parent=`echinacea`)
- `standardized_botanicals.json` → `echinacea_angustifolia` (standardized_botanical; Echinacea Angustifolia)

### `WQ0UW3VFG5` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `oat_straw` (botanical; Oat Straw)
- `ingredient_quality_map.json` → `oat_straw` (iqm_parent; Oat Straw Extract, parent=`oat_straw`)

### `X72A60C9MT` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `lutein` (iqm_parent; Lutein, parent=`lutein`)
- `standardized_botanicals.json` → `floraglo` (standardized_botanical; FloraGLO)
- `standardized_botanicals.json` → `lutemax_2020` (standardized_botanical; Lutemax 2020)

### `XII14C5FXV` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `shilajit.forms[fulvic acid]` (iqm_form; fulvic acid, parent=`shilajit`)
- `ingredient_quality_map.json` → `shilajit` (iqm_parent; Shilajit, parent=`shilajit`)

### `Z64FK7P217` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `feverfew` (botanical; Feverfew)
- `ingredient_quality_map.json` → `feverfew` (iqm_parent; Feverfew, parent=`feverfew`)
- `standardized_botanicals.json` → `feverfew` (standardized_botanical; Feverfew)

### `ZS98O42YBB` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `ingredient_quality_map.json` → `lactobacillus_kefiranofaciens.forms[lactobacillus kefiranofaciens (unspecified)]` (iqm_form; lactobacillus kefiranofaciens (unspecified), parent=`lactobacillus_kefiranofaciens`)
- `ingredient_quality_map.json` → `lactobacillus_kefiranofaciens` (iqm_parent; Lactobacillus Kefiranofaciens, parent=`lactobacillus_kefiranofaciens`)

### `ZW3Z11D0JV` — tier 4 `ingredient_quality_map` (iqm_same_parent_parent_form, info)

- Action: `suppress_runtime_warning_candidate`
- Reason: IQM parent/form records share the same parent identity; runtime routes both to the same parent payload.
- `botanical_ingredients.json` → `goldenseal` (botanical; Goldenseal)
- `ingredient_quality_map.json` → `goldenseal` (iqm_parent; Goldenseal, parent=`goldenseal`)
- `standardized_botanicals.json` → `goldenseal` (standardized_botanical; Goldenseal)
