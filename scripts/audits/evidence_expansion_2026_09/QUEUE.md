# Evidence curation queue — non-probiotic lane

Built 2026-09-17 from `inventory.json`. Discovery volume = PubMed human RCT/SR/MA count for the name: **workload only, never evidence strength**.

```
Two rankings, because the lanes differ from the probiotic queue this adapts
(scripts/audits/probiotic_curation_queue_2026_09_13), where every product sat at
Evidence <= 8. Here the slots x (0.25 + share <= 8) base term lets well-evidenced
multivitamin nutrients outrank identities whose products are actually at zero.
  gap priority      = products at Evidence <= 8 x uncertainty          (new-evidence waves)
  exposure priority = slots x (0.25 + share <= 8) x uncertainty        (legacy-record backfill)
  uncertainty: not reviewed 2.0, legacy record without review state 1.5, reviewed 1.0
```

## Gap queue (new-evidence waves)

| rank | identity | name | category | slots | products | brands | mean Ev | Ev=0 | Ev≤8 | review state | legacy records | dosed share | form-unmapped share | discovery vol | gap prio | exposure prio |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `fish_oil` | Fish Oil | fatty_acids | 548 | 482 | 42 | 11.48 | 2 | 116 | legacy_review_state_not_established | INGR_OMEGA3 | 1.0 | 0.0 | 1648 | 174.0 | 403.3 |
| 2 | `l_leucine` | L-Leucine | amino_acids | 393 | 375 | 26 | 13.51 | 30 | 77 | not_reviewed | — | 1.0 | 0.0 | 61 | 154.0 | 357.9 |
| 3 | `potassium` | Potassium | minerals | 1497 | 1491 | 70 | 16.11 | 0 | 101 | legacy_review_state_not_established | INGR_PHOSPHORUS, INGR_POTASSIUM | 0.999 | 0.0 | 4842 | 151.5 | 713.5 |
| 4 | `l_glutamine` | L-Glutamine | amino_acids | 189 | 182 | 27 | 10.38 | 64 | 71 | not_reviewed | — | 1.0 | 0.0 | 134 | 142.0 | 242.0 |
| 5 | `cla` | CLA | fatty_acids | 104 | 87 | 17 | 4.34 | 58 | 66 | not_reviewed | — | 1.0 | 0.0 | 267 | 132.0 | 209.8 |
| 6 | `l_isoleucine` | L-Isoleucine | amino_acids | 240 | 227 | 20 | 12.5 | 16 | 61 | not_reviewed | — | 1.0 | 0.0 | 21 | 122.0 | 249.0 |
| 7 | `l_valine` | L-Valine | amino_acids | 238 | 225 | 20 | 12.61 | 14 | 59 | not_reviewed | — | 1.0 | 0.0 | 19 | 118.0 | 243.8 |
| 8 | `l_lysine` | L-Lysine | amino_acids | 98 | 98 | 23 | 6.78 | 56 | 59 | not_reviewed | — | 1.0 | 0.0 | 66 | 118.0 | 167.0 |
| 9 | `ginkgo` | Ginkgo | herbs | 140 | 124 | 29 | 9.49 | 49 | 57 | not_reviewed | — | 1.0 | 0.0 | 526 | 114.0 | 198.7 |
| 10 | `maca` | Maca | herbs | 87 | 81 | 18 | 5.32 | 46 | 55 | not_reviewed | — | 1.0 | 0.057 | 19 | 110.0 | 161.6 |
| 11 | `iron` | Iron | minerals | 851 | 849 | 57 | 15.81 | 17 | 70 | legacy_review_state_not_established | INGR_IRON_BISGLYCINATE | 1.0 | 0.0 | 5561 | 105.0 | 424.4 |
| 12 | `l_carnosine` | L-Carnosine | amino_acids | 70 | 70 | 6 | 4.28 | 51 | 51 | not_reviewed | — | 1.0 | 0.0 | 45 | 102.0 | 137.0 |
| 13 | `l_tyrosine` | L-Tyrosine | amino_acids | 157 | 155 | 23 | 11.39 | 45 | 50 | not_reviewed | — | 1.0 | 0.0 | 46 | 100.0 | 179.8 |
| 14 | `garcinia_cambogia` | Garcinia Cambogia (Hydroxycitric Acid) | herbs | 85 | 80 | 20 | 6.19 | 41 | 49 | not_reviewed | — | 1.0 | 0.0 | 32 | 98.0 | 146.6 |
| 15 | `mct_oil` | MCT Oil | fatty_acids | 75 | 75 | 15 | 5.92 | 45 | 49 | not_reviewed | — | 1.0 | 0.0 | 37 | 98.0 | 135.5 |
| 16 | `dha` | DHA (Docosahexaenoic Acid) | fatty_acids | 733 | 715 | 60 | 12.5 | 0 | 64 | legacy_review_state_not_established | INGR_OMEGA3 | 1.0 | 0.0 | 2452 | 96.0 | 373.3 |
| 17 | `vitamin_e` | Vitamin E | vitamins | 2111 | 1926 | 82 | 16.8 | 0 | 62 | legacy_review_state_not_established | INGR_VITAMIN_E | 1.0 | 0.0 | 2358 | 93.0 | 893.6 |
| 18 | `l_carnitine` | L-Carnitine | amino_acids | 335 | 294 | 30 | 11.38 | 23 | 62 | legacy_review_state_not_established | INGR_ACETYL_L_CARNITINE, INGR_L_CARNITINE | 1.0 | 0.0 | 622 | 93.0 | 231.6 |
| 19 | `saw_palmetto` | Saw Palmetto | herbs | 129 | 128 | 21 | 10.0 | 0 | 62 | legacy_review_state_not_established | INGR_SAW_PALMETTO | 1.0 | 0.008 | 56 | 93.0 | 142.1 |
| 20 | `pomegranate` | Pomegranate | herbs | 114 | 104 | 16 | 10.16 | 41 | 46 | not_reviewed | — | 1.0 | 0.0 | 214 | 92.0 | 157.8 |
| 21 | `gamma_linolenic_acid` | Gamma-Linolenic Acid | fatty_acids | 97 | 97 | 29 | 7.33 | 33 | 45 | not_reviewed | — | 1.0 | 0.0 | 180 | 90.0 | 138.5 |
| 22 | `calcium` | Calcium | minerals | 2457 | 2445 | 84 | 16.63 | 0 | 59 | legacy_review_state_not_established | INGR_CALCIUM, INGR_PHOSPHORUS | 1.0 | 0.0 | 13458 | 88.5 | 1010.3 |
| 23 | `epa` | EPA (Eicosapentaenoic Acid) | fatty_acids | 645 | 643 | 53 | 12.35 | 0 | 57 | legacy_review_state_not_established | INGR_OMEGA3 | 1.0 | 0.0 | 2232 | 85.5 | 327.6 |
| 24 | `citrus_bioflavonoids` | Citrus Bioflavonoids | antioxidants | 250 | 185 | 21 | 13.73 | 27 | 40 | not_reviewed | — | 1.0 | 0.0 | 2 | 80.0 | 233.1 |
| 25 | `methionine` | L-Methionine | amino_acids | 131 | 125 | 16 | 11.75 | 39 | 40 | not_reviewed | — | 1.0 | 0.0 | 99 | 80.0 | 149.3 |
| 26 | `linoleic_acid` | Linoleic Acid | fatty_acids | 73 | 73 | 19 | 7.23 | 24 | 40 | not_reviewed | — | 1.0 | 0.0 | 731 | 80.0 | 116.5 |
| 27 | `vitamin_c` | Vitamin C | vitamins | 2713 | 2704 | 96 | 16.54 | 0 | 52 | legacy_review_state_not_established | BRAND_ESTERC, INGR_VITAMIN_C | 1.0 | 0.0 | 2130 | 78.0 | 1095.6 |
| 28 | `apple_cider_vinegar` | Apple Cider Vinegar | functional_foods | 52 | 52 | 19 | 4.69 | 23 | 39 | not_reviewed | — | 1.0 | 0.0 | 10 | 78.0 | 104.0 |
| 29 | `lecithin` | Lecithin | fatty_acids | 47 | 47 | 14 | 4.26 | 29 | 37 | not_reviewed | — | 1.0 | 0.0 | 246 | 74.0 | 97.5 |
| 30 | `l_phenylalanine` | L-Phenylalanine | amino_acids | 63 | 63 | 12 | 6.84 | 35 | 36 | not_reviewed | — | 1.0 | 0.0 | 54 | 72.0 | 103.5 |
| 31 | `acai_berry` | Acai Berry | antioxidants | 39 | 39 | 12 | 1.53 | 34 | 35 | not_reviewed | — | 1.0 | 0.256 | 2 | 70.0 | 89.5 |
| 32 | `nattokinase` | Nattokinase | enzymes | 38 | 38 | 7 | 1.17 | 35 | 35 | not_reviewed | — | 1.0 | 0.0 | 8 | 70.0 | 89.0 |
| 33 | `isoflavones` | Isoflavones | antioxidants | 60 | 57 | 11 | 6.81 | 31 | 34 | not_reviewed | — | 1.0 | 0.0 | 688 | 68.0 | 101.6 |
| 34 | `flaxseed` | Flaxseed | functional_foods | 86 | 85 | 23 | 10.08 | 14 | 33 | not_reviewed | — | 1.0 | 0.0 | 271 | 66.0 | 109.8 |
| 35 | `tribulus` | Tribulus Terrestris | herbs | 56 | 50 | 14 | 6.23 | 28 | 33 | not_reviewed | — | 1.0 | 0.0 | 46 | 66.0 | 101.9 |
| 36 | `pumpkin` | Pumpkin | unknown | 67 | 67 | 10 | 9.06 | 29 | 32 | not_reviewed | — | 1.0 | 0.06 | 23 | 64.0 | 97.5 |
| 37 | `l_tryptophan` | L-Tryptophan | amino_acids | 56 | 56 | 13 | 7.09 | 26 | 32 | not_reviewed | — | 1.0 | 0.0 | 135 | 64.0 | 92.0 |
| 38 | `vitamin_b12_cobalamin` | Vitamin B12 | vitamins | 2159 | 2154 | 83 | 17.14 | 0 | 42 | legacy_review_state_not_established | INGR_VITAMIN_B12 | 1.0 | 0.0 | 926 | 63.0 | 872.8 |
| 39 | `gotu_kola` | Gotu Kola | herbs | 44 | 43 | 9 | 4.7 | 25 | 30 | not_reviewed | — | 1.0 | 0.023 | 5 | 60.0 | 83.4 |
| 40 | `OI_BEETROOT_POWDER` | Beetroot Powder | unknown | 46 | 46 | 10 | 6.87 | 20 | 30 | not_reviewed | — | 1.0 | 0.0 | 5 | 60.0 | 83.0 |
| 41 | `l_arginine` | L-Arginine | amino_acids | 311 | 294 | 27 | 13.9 | 16 | 39 | legacy_review_state_not_established | BRAND_NITROSIGINE, INGR_L_ARGININE | 1.0 | 0.0 | 859 | 58.5 | 178.5 |
| 42 | `evening_primrose_oil` | Evening Primrose Oil | fatty_acids | 38 | 38 | 14 | 3.17 | 29 | 29 | not_reviewed | — | 1.0 | 0.0 | 95 | 58.0 | 77.0 |
| 43 | `fruits` | Fruits | unknown | 30 | 30 | 3 | 0.44 | 29 | 29 | not_reviewed | — | 1.0 | 0.0 | 1839 | 58.0 | 73.0 |
| 44 | `lycopene` | Lycopene | antioxidants | 461 | 461 | 42 | 17.21 | 22 | 28 | not_reviewed | — | 1.0 | 0.0 | 435 | 56.0 | 286.5 |
| 45 | `horny_goat_weed` | Horny Goat Weed | unknown | 55 | 51 | 9 | 4.86 | 28 | 28 | not_reviewed | — | 1.0 | 0.345 | 3 | 56.0 | 87.9 |
| 46 | `dandelion` | Dandelion | herbs | 58 | 57 | 15 | 8.6 | 21 | 27 | not_reviewed | — | 1.0 | 0.0 | 6 | 54.0 | 83.9 |
| 47 | `d_ribose` | D-Ribose | other | 33 | 33 | 9 | 3.35 | 25 | 27 | not_reviewed | — | 1.0 | 0.0 | 18 | 54.0 | 70.5 |
| 48 | `blueberry` | Blueberry | functional_foods | 92 | 86 | 10 | 11.84 | 22 | 26 | not_reviewed | — | 1.0 | 0.0 | 128 | 52.0 | 101.6 |
| 49 | `butterbur` | Butterbur (Petasites hybridus) | herbs | 33 | 29 | 6 | 1.5 | 25 | 26 | not_reviewed | — | 1.0 | 0.0 | 24 | 52.0 | 75.7 |
| 50 | `vitamin_d` | Vitamin D | vitamins | 2361 | 2356 | 97 | 17.31 | 0 | 34 | legacy_review_state_not_established | INGR_VITAMIN_D3 | 1.0 | 0.0 | 7503 | 51.0 | 936.5 |
| 51 | `olive_leaf` | Olive Leaf | herbs | 36 | 34 | 14 | 4.27 | 24 | 25 | not_reviewed | — | 1.0 | 0.0 | 34 | 50.0 | 70.9 |
| 52 | `dhea` | DHEA (Dehydroepiandrosterone) | other | 33 | 33 | 12 | 3.45 | 25 | 25 | not_reviewed | — | 1.0 | 0.0 | 937 | 50.0 | 66.5 |
| 53 | `glutathione` | Glutathione | antioxidants | 87 | 87 | 18 | 10.67 | 33 | 33 | legacy_review_state_not_established | BRAND_SETRIA | 1.0 | 0.0 | 2419 | 49.5 | 82.1 |
| 54 | `broccoli` | Broccoli | unknown | 66 | 64 | 6 | 11.21 | 20 | 24 | not_reviewed | — | 1.0 | 0.167 | 131 | 48.0 | 82.5 |
| 55 | `l_histidine` | L-Histidine | amino_acids | 41 | 41 | 9 | 6.44 | 23 | 24 | not_reviewed | — | 1.0 | 0.0 | 27 | 48.0 | 68.5 |
| 56 | `krill_oil` | Krill Oil | fatty_acids | 47 | 47 | 19 | 8.17 | 0 | 32 | legacy_review_state_not_established | INGR_OMEGA3 | 1.0 | 0.0 | 63 | 48.0 | 65.6 |
| 57 | `goldenseal` | Goldenseal | herbs | 52 | 51 | 13 | 8.89 | 23 | 23 | not_reviewed | — | 1.0 | 0.0 | 6 | 46.0 | 72.9 |
| 58 | `goji_berry` | Goji Berry | herbs | 25 | 24 | 6 | 1.53 | 20 | 23 | not_reviewed | — | 1.0 | 0.0 | 7 | 46.0 | 60.4 |
| 59 | `zinc` | Zinc | minerals | 2153 | 2144 | 86 | 16.96 | 6 | 30 | legacy_review_state_not_established | INGR_ZINC_PICOLINATE, PRECLIN_ZINC_CARNOSINE | 1.0 | 0.0 | 3449 | 45.0 | 852.6 |
| 60 | `silica` | Silica | minerals | 258 | 258 | 29 | 16.69 | 20 | 22 | not_reviewed | — | 1.0 | 0.0 | 370 | 44.0 | 173.0 |
| 61 | `cayenne_pepper` | Cayenne Pepper | unknown | 109 | 105 | 17 | 13.67 | 16 | 22 | not_reviewed | — | 1.0 | 0.0 | — | 44.0 | 100.2 |
| 62 | `green_coffee_bean` | Green Coffee Bean | unknown | 80 | 76 | 18 | 11.53 | 21 | 22 | not_reviewed | — | 1.0 | 0.212 | — | 44.0 | 86.3 |
| 63 | `d_aspartic_acid` | D-Aspartic Acid | amino_acids | 28 | 28 | 8 | 3.15 | 21 | 22 | not_reviewed | — | 1.0 | 0.0 | — | 44.0 | 58.0 |
| 64 | `l_ornithine` | L-Ornithine | amino_acids | 27 | 27 | 6 | 2.35 | 21 | 22 | not_reviewed | — | 1.0 | 0.0 | — | 44.0 | 57.5 |
| 65 | `dimethyl_glycine` | Dimethyl Glycine | amino_acids | 23 | 23 | 2 | 0.53 | 22 | 22 | not_reviewed | — | 1.0 | 0.0 | — | 44.0 | 55.5 |
| 66 | `digestive_enzymes` | Digestive Enzymes | enzymes | 245 | 81 | 23 | 11.71 | 9 | 29 | legacy_review_state_not_established | INGR_DIGESTIVE_ENZYMES | 1.0 | 0.0 | — | 43.5 | 223.4 |
| 67 | `diindolylmethane` | Diindolylmethane (DIM) | antioxidants | 67 | 46 | 14 | 8.42 | 0 | 28 | legacy_review_state_not_established | PRECLIN_DIM | 1.0 | 0.0 | — | 42.0 | 86.3 |
| 68 | `yohimbe` | Yohimbe | herbs | 59 | 56 | 11 | 8.36 | 20 | 21 | not_reviewed | — | 1.0 | 0.0 | — | 42.0 | 73.8 |
| 69 | `stinging_nettle` | Stinging Nettle | herbs | 43 | 42 | 11 | 7.5 | 12 | 21 | not_reviewed | — | 1.0 | 0.0 | — | 42.0 | 64.5 |
| 70 | `rosemary` | Rosemary | herbs | 38 | 38 | 5 | 7.39 | 14 | 21 | not_reviewed | — | 1.0 | 0.0 | — | 42.0 | 61.0 |
| 71 | `common_bean_extract` | Common Bean Extract | herbs | 22 | 22 | 7 | 0.48 | 21 | 21 | not_reviewed | — | 1.0 | 0.0 | — | 42.0 | 53.0 |
| 72 | `astaxanthin` | Astaxanthin | antioxidants | 279 | 274 | 33 | 16.16 | 0 | 27 | legacy_review_state_not_established | BRAND_ASTAREAL, PRECLIN_ASTAXANTHIN_GENERIC | 1.0 | 0.0 | — | 40.5 | 145.9 |
| 73 | `horsetail` | Horsetail | herbs | 57 | 57 | 15 | 11.58 | 18 | 20 | not_reviewed | — | 1.0 | 0.0 | — | 40.0 | 68.5 |
| 74 | `amla` | Amla (Phyllanthus emblica) | herbs | 52 | 52 | 16 | 9.55 | 19 | 20 | not_reviewed | — | 1.0 | 0.0 | — | 40.0 | 66.0 |
| 75 | `aloe_vera` | Aloe Vera | herbs | 34 | 32 | 10 | 6.14 | 15 | 20 | not_reviewed | — | 1.0 | 0.059 | — | 40.0 | 59.5 |
| 76 | `fennel` | Fennel | unknown | 37 | 37 | 12 | 7.66 | 17 | 20 | not_reviewed | — | 1.0 | 0.0 | — | 40.0 | 58.5 |
| 77 | `feverfew` | Feverfew | herbs | 23 | 21 | 6 | 0.48 | 20 | 20 | not_reviewed | — | 1.0 | 0.0 | — | 40.0 | 55.3 |
| 78 | `d_mannose` | D-Mannose | fibers | 25 | 25 | 5 | 3.86 | 16 | 20 | not_reviewed | — | 1.0 | 0.0 | — | 40.0 | 52.5 |
| 79 | `pregnenolone` | Pregnenolone | functional_foods | 22 | 22 | 4 | 1.15 | 20 | 20 | not_reviewed | — | 1.0 | 0.0 | — | 40.0 | 51.0 |
| 80 | `schisandra_berry` | Schisandra Berry | unknown | 48 | 48 | 13 | 9.81 | 19 | 19 | not_reviewed | — | 1.0 | 0.062 | — | 38.0 | 62.0 |

## Exposure queue (legacy-record backfill)

| rank | identity | name | category | slots | products | brands | mean Ev | Ev=0 | Ev≤8 | review state | legacy records | dosed share | form-unmapped share | discovery vol | gap prio | exposure prio |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `vitamin_b9_folate` | Vitamin B9 (Folate) | vitamins | 2903 | 1911 | 79 | 17.79 | 0 | 16 | legacy_review_state_not_established | BRAND_QUATREFOLIC, INGR_FOLATE_MTHF | 1.0 | 0.0 | — | 24.0 | 1125.1 |
| 2 | `vitamin_c` | Vitamin C | vitamins | 2713 | 2704 | 96 | 16.54 | 0 | 52 | legacy_review_state_not_established | BRAND_ESTERC, INGR_VITAMIN_C | 1.0 | 0.0 | 2130 | 78.0 | 1095.6 |
| 3 | `calcium` | Calcium | minerals | 2457 | 2445 | 84 | 16.63 | 0 | 59 | legacy_review_state_not_established | INGR_CALCIUM, INGR_PHOSPHORUS | 1.0 | 0.0 | 13458 | 88.5 | 1010.3 |
| 4 | `vitamin_d` | Vitamin D | vitamins | 2361 | 2356 | 97 | 17.31 | 0 | 34 | legacy_review_state_not_established | INGR_VITAMIN_D3 | 1.0 | 0.0 | 7503 | 51.0 | 936.5 |
| 5 | `vitamin_e` | Vitamin E | vitamins | 2111 | 1926 | 82 | 16.8 | 0 | 62 | legacy_review_state_not_established | INGR_VITAMIN_E | 1.0 | 0.0 | 2358 | 93.0 | 893.6 |
| 6 | `vitamin_b12_cobalamin` | Vitamin B12 | vitamins | 2159 | 2154 | 83 | 17.14 | 0 | 42 | legacy_review_state_not_established | INGR_VITAMIN_B12 | 1.0 | 0.0 | 926 | 63.0 | 872.8 |
| 7 | `zinc` | Zinc | minerals | 2153 | 2144 | 86 | 16.96 | 6 | 30 | legacy_review_state_not_established | INGR_ZINC_PICOLINATE, PRECLIN_ZINC_CARNOSINE | 1.0 | 0.0 | 3449 | 45.0 | 852.6 |
| 8 | `vitamin_b6_pyridoxine` | Vitamin B6 (Pyridoxine) | vitamins | 2131 | 2066 | 83 | 17.75 | 0 | 13 | legacy_review_state_not_established | INGR_VITAMIN_B6 | 1.0 | 0.0 | — | 19.5 | 819.2 |
| 9 | `vitamin_b3_niacin` | Vitamin B3 (Niacin) | vitamins | 1885 | 1856 | 77 | 17.83 | 0 | 17 | legacy_review_state_not_established | INGR_VITAMIN_B3_NIACIN | 1.0 | 0.0 | — | 25.5 | 732.8 |
| 10 | `potassium` | Potassium | minerals | 1497 | 1491 | 70 | 16.11 | 0 | 101 | legacy_review_state_not_established | INGR_PHOSPHORUS, INGR_POTASSIUM | 0.999 | 0.0 | 4842 | 151.5 | 713.5 |
| 11 | `magnesium` | Magnesium | minerals | 1824 | 1778 | 80 | 17.55 | 0 | 16 | legacy_review_state_not_established | BRAND_MAGTEIN, INGR_MAGNESIUM_GENERIC, INGR_MAG_GLYCINATE | 1.0 | 0.0 | — | 24.0 | 708.6 |
| 12 | `vitamin_b7_biotin` | Vitamin B7 (Biotin) | vitamins | 1797 | 1797 | 78 | 17.5 | 0 | 10 | legacy_review_state_not_established | INGR_BIOTIN | 1.0 | 0.0 | — | 15.0 | 688.9 |
| 13 | `vitamin_a` | Vitamin A | vitamins | 1774 | 1716 | 79 | 17.27 | 8 | 15 | legacy_review_state_not_established | INGR_VITAMIN_A_BETA_CAROTENE | 1.0 | 0.0 | — | 22.5 | 688.5 |
| 14 | `vitamin_b5_pantothenic` | Vitamin B5 (Pantothenic Acid) | vitamins | 1797 | 1755 | 74 | 18.04 | 0 | 2 | legacy_review_state_not_established | INGR_PANTETHINE, INGR_PANTOTHENIC_ACID_B5 | 1.0 | 0.0 | — | 3.0 | 676.9 |
| 15 | `vitamin_b1_thiamine` | Vitamin B1 (Thiamine) | vitamins | 1589 | 1561 | 69 | 18.26 | 0 | 0 | legacy_review_state_not_established | INGR_BENFOTIAMINE, INGR_THIAMINE_B1 | 1.0 | 0.0 | — | 0.0 | 595.9 |
| 16 | `vitamin_b2_riboflavin` | Vitamin B2 (Riboflavin) | vitamins | 1572 | 1549 | 68 | 18.43 | 0 | 0 | legacy_review_state_not_established | INGR_RIBOFLAVIN_B2 | 1.0 | 0.0 | — | 0.0 | 589.5 |
| 17 | `chromium` | Chromium | minerals | 1325 | 1321 | 65 | 17.79 | 0 | 9 | legacy_review_state_not_established | PRECLIN_CHROMIUM_PICOLINATE | 1.0 | 0.0 | — | 13.5 | 510.4 |
| 18 | `manganese` | Manganese | minerals | 1295 | 1293 | 62 | 18.02 | 0 | 3 | legacy_review_state_not_established | INGR_MANGANESE | 1.0 | 0.0 | — | 4.5 | 490.1 |
| 19 | `iodine` | Iodine | minerals | 1224 | 1222 | 65 | 17.8 | 0 | 12 | legacy_review_state_not_established | INGR_IODINE | 1.0 | 0.0 | — | 18.0 | 477.0 |
| 20 | `selenium` | Selenium | minerals | 1251 | 1250 | 67 | 18.05 | 0 | 5 | legacy_review_state_not_established | INGR_SELENIUM | 1.0 | 0.0 | — | 7.5 | 476.6 |
| 21 | `iron` | Iron | minerals | 851 | 849 | 57 | 15.81 | 17 | 70 | legacy_review_state_not_established | INGR_IRON_BISGLYCINATE | 1.0 | 0.0 | 5561 | 105.0 | 424.4 |
| 22 | `fish_oil` | Fish Oil | fatty_acids | 548 | 482 | 42 | 11.48 | 2 | 116 | legacy_review_state_not_established | INGR_OMEGA3 | 1.0 | 0.0 | 1648 | 174.0 | 403.3 |
| 23 | `dha` | DHA (Docosahexaenoic Acid) | fatty_acids | 733 | 715 | 60 | 12.5 | 0 | 64 | legacy_review_state_not_established | INGR_OMEGA3 | 1.0 | 0.0 | 2452 | 96.0 | 373.3 |
| 24 | `copper` | Copper | minerals | 928 | 926 | 57 | 17.89 | 11 | 14 | legacy_review_state_not_established | INGR_COPPER | 1.0 | 0.0 | — | 21.0 | 369.0 |
| 25 | `l_leucine` | L-Leucine | amino_acids | 393 | 375 | 26 | 13.51 | 30 | 77 | not_reviewed | — | 1.0 | 0.0 | 61 | 154.0 | 357.9 |
| 26 | `brewers_yeast` | Brewer's Yeast | functional_foods | 531 | 48 | 7 | 16.36 | 1 | 4 | not_reviewed | — | 1.0 | 0.0 | — | 8.0 | 354.0 |
| 27 | `epa` | EPA (Eicosapentaenoic Acid) | fatty_acids | 645 | 643 | 53 | 12.35 | 0 | 57 | legacy_review_state_not_established | INGR_OMEGA3 | 1.0 | 0.0 | 2232 | 85.5 | 327.6 |
| 28 | `molybdenum` | Molybdenum | minerals | 823 | 822 | 51 | 18.39 | 0 | 0 | legacy_review_state_not_established | INGR_MOLYBDENUM | 1.0 | 0.0 | — | 0.0 | 308.6 |
| 29 | `choline` | Choline | vitamins | 733 | 721 | 55 | 17.46 | 0 | 10 | legacy_review_state_not_established | BRAND_COGNIZIN, INGR_ALPHA_GPC, INGR_CITICOLINE_GENERIC | 1.0 | 0.0 | — | 15.0 | 290.1 |
| 30 | `lycopene` | Lycopene | antioxidants | 461 | 461 | 42 | 17.21 | 22 | 28 | not_reviewed | — | 1.0 | 0.0 | 435 | 56.0 | 286.5 |
| 31 | `vitamin_k1` | Vitamin K1 | vitamins | 552 | 552 | 36 | 17.88 | 0 | 5 | not_reviewed | — | 1.0 | 0.0 | — | 10.0 | 286.0 |
| 32 | `boron` | Boron | minerals | 679 | 679 | 49 | 17.68 | 0 | 14 | legacy_review_state_not_established | INGR_BORON | 1.0 | 0.0 | — | 21.0 | 275.6 |
| 33 | `zeaxanthin` | Zeaxanthin | antioxidants | 451 | 440 | 41 | 17.41 | 11 | 13 | not_reviewed | — | 1.0 | 0.0 | — | 26.0 | 252.2 |
| 34 | `l_isoleucine` | L-Isoleucine | amino_acids | 240 | 227 | 20 | 12.5 | 16 | 61 | not_reviewed | — | 1.0 | 0.0 | 21 | 122.0 | 249.0 |
| 35 | `lutein` | Lutein | antioxidants | 647 | 645 | 48 | 17.73 | 0 | 4 | legacy_review_state_not_established | BRAND_LUTEMAX_2020, INGR_LUTEIN | 1.0 | 0.0 | — | 6.0 | 248.6 |
| 36 | `l_valine` | L-Valine | amino_acids | 238 | 225 | 20 | 12.61 | 14 | 59 | not_reviewed | — | 1.0 | 0.0 | 19 | 118.0 | 243.8 |
| 37 | `l_glutamine` | L-Glutamine | amino_acids | 189 | 182 | 27 | 10.38 | 64 | 71 | not_reviewed | — | 1.0 | 0.0 | 134 | 142.0 | 242.0 |
| 38 | `citrus_bioflavonoids` | Citrus Bioflavonoids | antioxidants | 250 | 185 | 21 | 13.73 | 27 | 40 | not_reviewed | — | 1.0 | 0.0 | 2 | 80.0 | 233.1 |
| 39 | `inositol` | Inositol | vitamins | 611 | 609 | 46 | 17.69 | 0 | 2 | legacy_review_state_not_established | INGR_INOSITOL | 1.0 | 0.0 | — | 3.0 | 232.1 |
| 40 | `l_carnitine` | L-Carnitine | amino_acids | 335 | 294 | 30 | 11.38 | 23 | 62 | legacy_review_state_not_established | INGR_ACETYL_L_CARNITINE, INGR_L_CARNITINE | 1.0 | 0.0 | 622 | 93.0 | 231.6 |
