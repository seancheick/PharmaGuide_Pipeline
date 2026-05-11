# Phase 0 — IQM Alias Audit Report

_Generated: 2026-05-11T07:39:41.968236+00:00_
_Source IQM schema: 5.0.0_

## Summary

- **Total offending entries detected:** 108
- **Categorized MOVE:** 98
- **Categorized QUALIFY:** 10
- **Categorized DELETE:** 0

### Per-marker breakdown

| Marker Canonical | # Form Entries | # Aliases | Total Hits |
| --- | --- | --- | --- |
| `vitamin_c` | 2 | 20 | 22 |
| `curcumin` | 1 | 28 | 29 |
| `sulforaphane` | 1 | 8 | 9 |
| `capsaicin` | 0 | 26 | 26 |
| `lycopene` | 0 | 4 | 4 |
| `quercetin` | 0 | 3 | 3 |
| `aescin` | 0 | 5 | 5 |
| `resveratrol` | 0 | 10 | 10 |

### Botanical canonical home check

| Botanical Canonical | Exists? | Source DB |
| --- | --- | --- |
| `acerola_cherry` | ✅ | botanical_ingredients |
| `broccoli_sprout` | ❌ | **MUST CREATE** |
| `camu_camu` | ✅ | standardized_botanicals |
| `cayenne_pepper` | ✅ | botanical_ingredients |
| `horse_chestnut_seed` | ✅ | botanical_ingredients |
| `japanese_knotweed` | ✅ | botanical_ingredients |
| `sophora_japonica` | ✅ | botanical_ingredients |
| `tomato` | ✅ | botanical_ingredients |
| `turmeric` | ✅ | botanical_ingredients |

## Detailed Findings (by marker)

### `vitamin_c` (22 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `camu camu extract` | form_name | `camu camu extract` | `camu_camu` | — | **MOVE** | 45 |
| `camu camu extract` | alias | `camu camu` | `camu_camu` | — | **MOVE** | 49 |
| `camu camu extract` | alias | `camu camu supplement` | `camu_camu` | — | **MOVE** | 0 |
| `camu camu extract` | alias | `camu camu extract supplement` | `camu_camu` | — | **MOVE** | 0 |
| `camu camu extract` | alias | `camu camu fruit extract` | `camu_camu` | — | **MOVE** | 3 |
| `camu camu extract` | alias | `Camu Camu Berry Extract` | `camu_camu` | — | **MOVE** | 0 |
| `acerola cherry extract` | form_name | `acerola cherry extract` | `acerola_cherry` | — | **MOVE** | 159 |
| `acerola cherry extract` | alias | `acerola cherry` | `acerola_cherry` | — | **MOVE** | 187 |
| `acerola cherry extract` | alias | `acerola extract` | `acerola_cherry` | — | **MOVE** | 48 |
| `acerola cherry extract` | alias | `natural c acerola` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `acerola fruit c` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `acerola cherry supplement` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `acerola extract supplement` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `natural c acerola supplement` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `acerola fruit c supplement` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `Acerola juice powder` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `acerola berry juice powder` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `acerola` | `acerola_cherry` | — | **MOVE** | 212 |
| `acerola cherry extract` | alias | `acerola cherry extract supplement` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `Acerola Fruit Juice` | `acerola_cherry` | — | **MOVE** | 15 |
| `acerola cherry extract` | alias | `acerola juice` | `acerola_cherry` | — | **MOVE** | 0 |
| `acerola cherry extract` | alias | `acerola fruit juice powder` | `acerola_cherry` | — | **MOVE** | 6 |

### `curcumin` (29 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `meriva curcumin` | alias | `Curcumin Phytosome (Curcuma longa extract (root) / Phosphatidylcholine complex)` | `turmeric` | — | **MOVE** | 1 |
| `meriva curcumin` | alias | `Curcuma longa extract, Phospholipid Complex` | `turmeric` | — | **MOVE** | 0 |
| `meriva curcumin` | alias | `Curcuma longa extract, Phosphatidylcholine Complex` | `turmeric` | — | **MOVE** | 0 |
| `meriva curcumin` | alias | `Meriva (Curcuma longa) Phytosome` | `turmeric` | — | **MOVE** | 0 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome` | `turmeric` | — | **MOVE** | 24 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Complex` | `turmeric` | — | **MOVE** | 10 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Complex Curcuminoids` | `turmeric` | Y | **QUALIFY** | 0 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Complex Sunflower Phospholipid` | `turmeric` | — | **MOVE** | 0 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Sunflower Phospholipid Complex` | `turmeric` | — | **MOVE** | 0 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Curcuminoids` | `turmeric` | Y | **QUALIFY** | 0 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Phospholipid Complex` | `turmeric` | — | **MOVE** | 0 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Complex Curcuma longa extract` | `turmeric` | — | **MOVE** | 2 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Complex Soy Phospholipid` | `turmeric` | — | **MOVE** | 0 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Curcuma longa extract` | `turmeric` | — | **MOVE** | 2 |
| `meriva curcumin` | alias | `Meriva Turmeric Phytosome Curcuma longa Root Extract` | `turmeric` | — | **MOVE** | 2 |
| `meriva curcumin` | alias | `Curcuma longa Root Extract, Phospholipid Complex` | `turmeric` | — | **MOVE** | 0 |
| `bcm-95 curcumin` | alias | `turmeric curcumin complex` | `turmeric` | — | **MOVE** | 0 |
| `bcm-95 curcumin` | alias | `BCM-95 Bio-Curcumin (Curcuma longa) 25:1 extract` | `turmeric` | — | **MOVE** | 0 |
| `bcm-95 curcumin` | alias | `Curcuminoid Complex, Turmeric essential Oil` | `turmeric` | Y | **QUALIFY** | 0 |
| `bcm-95 curcumin` | alias | `Curcuma longa rhizome extract, Curcuminoid Complex, Turmeric essential Oil` | `turmeric` | Y | **QUALIFY** | 0 |
| `bcm-95 curcumin` | alias | `curcuminoid complex turmeric oil` | `turmeric` | Y | **QUALIFY** | 0 |
| `bcm-95 curcumin` | alias | `BCM-95 Bio-Curcumin Turmeric 25:1 extract` | `turmeric` | — | **MOVE** | 0 |
| `bcm-95 curcumin` | alias | `BCM-95 Bio-Curcumin Turmeric 25:1 extract Total Curcuminoids Complex` | `turmeric` | Y | **QUALIFY** | 0 |
| `curcumin c3 complex with bioperine` | alias | `turmeric with bioperine` | `turmeric` | — | **MOVE** | 0 |
| `turmeric powder (unstandardized)` | form_name | `turmeric powder (unstandardized)` | `turmeric` | — | **MOVE** | 4 |
| `curcumin (unspecified)` | alias | `curcuma longa extract` | `turmeric` | — | **MOVE** | 36 |
| `curcumin (unspecified)` | alias | `curcumin curcuma longa rhizome extract` | `turmeric` | — | **MOVE** | 0 |
| `curcumin (unspecified)` | alias | `curcuma longa rhizome extract` | `turmeric` | — | **MOVE** | 9 |
| `curcumin (unspecified)` | alias | `Curcumin (Curcuma longa) rhizome extract` | `turmeric` | — | **MOVE** | 0 |

### `sulforaphane` (9 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `broccoli sprout extract` | form_name | `broccoli sprout extract` | `broccoli_sprout` | — | **MOVE** | 19 |
| `broccoli sprout extract` | alias | `broccoli sprouts` | `broccoli_sprout` | — | **MOVE** | 9 |
| `broccoli sprout extract` | alias | `broccoli sprouts powder` | `broccoli_sprout` | — | **MOVE** | 9 |
| `broccoli sprout extract` | alias | `Broccoli seed raffinate` | `broccoli_sprout` | — | **MOVE** | 0 |
| `broccoli sprout extract` | alias | `broccoli sprout, whole plant concentrate` | `broccoli_sprout` | — | **MOVE** | 2 |
| `broccoli sprout extract` | alias | `broccoli sprout whole plant concentrate` | `broccoli_sprout` | — | **MOVE** | 0 |
| `broccoli sprout extract` | alias | `broccoli sprout concentrate` | `broccoli_sprout` | — | **MOVE** | 2 |
| `glucoraphanin` | alias | `broccoli seed extract` | `broccoli_sprout` | — | **MOVE** | 5 |
| `sulforaphane (unspecified)` | alias | `broccoli sprout/seed extract` | `broccoli_sprout` | — | **MOVE** | 0 |

### `capsaicin` (26 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `capsimax` | alias | `capsimax capsicum extract` | `cayenne_pepper` | — | **MOVE** | 8 |
| `capsimax` | alias | `capsimax cayenne extract` | `cayenne_pepper` | — | **MOVE** | 1 |
| `capsimax` | alias | `omnibead capsicum` | `cayenne_pepper` | — | **MOVE** | 0 |
| `capsimax` | alias | `Capsimax Capsicum annuum fruit extract` | `cayenne_pepper` | — | **MOVE** | 3 |
| `capsimax` | alias | `capsimax capsicum fruit extract` | `cayenne_pepper` | — | **MOVE** | 49 |
| `capsimax` | alias | `capsimax(tm) capsicum fruit extract` | `cayenne_pepper` | — | **MOVE** | 9 |
| `capsimax` | alias | `capsimax capsicum seed extract` | `cayenne_pepper` | — | **MOVE** | 37 |
| `capsimax` | alias | `capsicum seed extract` | `cayenne_pepper` | — | **MOVE** | 42 |
| `capsimax` | alias | `capsimax red pepper extract` | `cayenne_pepper` | — | **MOVE** | 8 |
| `capsimax` | alias | `capsimax cayenne pepper fruit extract` | `cayenne_pepper` | — | **MOVE** | 3 |
| `capsimax` | alias | `capsimax(tm) capsicum extract` | `cayenne_pepper` | — | **MOVE** | 2 |
| `capsimax` | alias | `capsimax capsicum (capsicum annuum) fruit extract` | `cayenne_pepper` | — | **MOVE** | 1 |
| `capsaicin extract` | alias | `capsicum extract` | `cayenne_pepper` | — | **MOVE** | 12 |
| `capsaicin extract` | alias | `cayenne pepper extract` | `cayenne_pepper` | — | **MOVE** | 0 |
| `capsaicin extract` | alias | `cayenne extract` | `cayenne_pepper` | — | **MOVE** | 1 |
| `capsaicin extract` | alias | `capsicum annuum extract` | `cayenne_pepper` | — | **MOVE** | 0 |
| `capsaicin extract` | alias | `capsicum fruit extract` | `cayenne_pepper` | — | **MOVE** | 64 |
| `capsaicin extract` | alias | `cayenne pepper fruit powder` | `cayenne_pepper` | — | **MOVE** | 9 |
| `capsaicin (unspecified)` | alias | `cayenne` | `cayenne_pepper` | — | **MOVE** | 50 |
| `capsaicin (unspecified)` | alias | `cayenne pepper` | `cayenne_pepper` | — | **MOVE** | 31 |
| `capsaicin (unspecified)` | alias | `cayenne pepper powder` | `cayenne_pepper` | — | **MOVE** | 0 |
| `capsaicin (unspecified)` | alias | `cayenne powder` | `cayenne_pepper` | — | **MOVE** | 0 |
| `capsaicin (unspecified)` | alias | `cayenne fruit extract` | `cayenne_pepper` | — | **MOVE** | 8 |
| `capsaicin (unspecified)` | alias | `cayenne, powder` | `cayenne_pepper` | — | **MOVE** | 0 |
| `capsaicin (unspecified)` | alias | `organic cayenne` | `cayenne_pepper` | — | **MOVE** | 4 |
| `capsaicin (unspecified)` | alias | `wild crafted cayenne` | `cayenne_pepper` | — | **MOVE** | 2 |

### `lycopene` (4 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `lycopene extract` | alias | `tomato lycopene` | `tomato` | — | **MOVE** | 367 |
| `lycopene extract` | alias | `tomato lycopene supplement` | `tomato` | — | **MOVE** | 0 |
| `lycopene extract` | alias | `Lycopene LYC-O-MATO(R) tomato extract` | `tomato` | — | **MOVE** | 0 |
| `lycopene extract` | alias | `Tomato` | `tomato` | — | **MOVE** | 502 |

### `quercetin` (3 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `quercetin phytosome` | alias | `Phospholipid Complex, Sophora japonica Flower Extract` | `sophora_japonica` | — | **MOVE** | 0 |
| `quercetin phytosome` | alias | `Sophora japonica Flower Extract, Sunflower Phospholipids` | `sophora_japonica` | — | **MOVE** | 0 |
| `quercetin dihydrate` | alias | `Sophora japonica` | `sophora_japonica` | — | **MOVE** | 40 |

### `aescin` (5 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `aescin (unspecified)` | alias | `horse chestnut saponin` | `horse_chestnut_seed` | — | **MOVE** | 0 |
| `aescin (unspecified)` | alias | `aesculus hippocastanum extract` | `horse_chestnut_seed` | — | **MOVE** | 0 |
| `aescin (unspecified)` | alias | `horse chestnut seed extract` | `horse_chestnut_seed` | — | **MOVE** | 9 |
| `aescin (unspecified)` | alias | `horse chestnut 20% extract` | `horse_chestnut_seed` | Y | **QUALIFY** | 0 |
| `aescin (unspecified)` | alias | `horse chestnut extract 20%` | `horse_chestnut_seed` | Y | **QUALIFY** | 0 |

### `resveratrol` (10 entries)

| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |
| --- | --- | --- | --- | --- | --- | --- |
| `trans-resveratrol` | alias | `polygonum cuspidatum 50% extract` | `japanese_knotweed` | Y | **QUALIFY** | 0 |
| `trans-resveratrol` | alias | `standardized extract of polygonum cuspidatum` | `japanese_knotweed` | Y | **QUALIFY** | 0 |
| `trans-resveratrol` | alias | `japanese knotweed extract` | `japanese_knotweed` | — | **MOVE** | 3 |
| `trans-resveratrol` | alias | `polygonum cuspidatum extract` | `japanese_knotweed` | — | **MOVE** | 1 |
| `trans-resveratrol` | alias | `polygonum cuspidatum root extract` | `japanese_knotweed` | — | **MOVE** | 0 |
| `trans-resveratrol` | alias | `Japanese Knotweed (root) and whole Red Grape extracts` | `japanese_knotweed` | — | **MOVE** | 0 |
| `trans-resveratrol` | alias | `Whole grape extract (Vitis vinifera) and Polygonum cuspidatum (root) extract` | `japanese_knotweed` | — | **MOVE** | 0 |
| `trans-resveratrol` | alias | `Polygonum cuspidatum` | `japanese_knotweed` | — | **MOVE** | 5 |
| `trans-resveratrol` | alias | `Fallopia japonica` | `japanese_knotweed` | — | **MOVE** | 1 |
| `trans-resveratrol` | alias | `Japanese Knotweed Root Extract` | `japanese_knotweed` | — | **MOVE** | 4 |

## Categorization Rules

- **MOVE** — Source botanical name with no standardization predicate. Relocate alias to source botanical's own `aliases[]` in `botanical_ingredients.json` or `standardized_botanicals.json`. Remove from marker IQM forms.
- **QUALIFY** — Source botanical name with standardization keyword/percentage. Keep under marker IQM but cleaner must require standardization predicate in nearby label text to resolve to marker.
- **DELETE** — Wrong altogether (e.g., a vague generic term that should not alias anywhere). Reserved for manual review entries.
- **KEEP_UNCHANGED** — Not a source botanical at all. No action needed.

## Next Steps

1. Phase 1 — populate `scripts/data/botanical_marker_contributions.json` with USDA FDC / PubMed cited default contributions for detected botanicals.
2. Phase 2 — execute `proposed_alias_migration.json`:
   - MOVE entries: relocate aliases out of IQM into botanical canonicals.
   - QUALIFY entries: rewrite cleaner to require standardization predicate.
   - Pre-create any botanical canonical marked `needs_new_botanical_entry: true`.
3. Bump IQM `_metadata.schema_version` to 5.4.0; archive 5.3.0 snapshot.
