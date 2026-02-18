# Softgels Cleaning Unmapped Triage
Generated: 2026-02-18 12:10:31
Source files:
- /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/output_Softgels/unmapped/unmapped_active_ingredients.json
- /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/output_Softgels/unmapped/unmapped_inactive_ingredients.json
- Context sampled from /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/output_Softgels/cleaned/cleaned_batch_*.json

## Active (count >= 4)
| Ingredient | Count | Recommendation | Target | Confidence | Inline verification sample |
|---|---:|---|---|---|---|
| ZMA | 10 | skip_header | constants:BLEND_HEADER_EXACT_NAMES | high | 245873 / NOW Sports / Men's Active Sports Multi |
| Phosphatides | 9 | map_non_scorable | other_ingredients:phospholipid_descriptor(new) | high | 25911 / Puritan's Pride Premium / Soy Lecithin 1200 mg |
| Phospholipid | 8 | map_non_scorable | other_ingredients:phospholipid_descriptor(new) | high | 230755 / Esmond Natural / Krill Oil 720 mg |
| Polar Lipids | 8 | map_non_scorable | other_ingredients:polar_lipids(new) | high | 222961 / Nested Naturals / Vegan Omega-3 |
| Essential Oil | 7 | skip_component | skip if generic and parentBlend/form exists | medium | 38548 / New Chapter / Supercritical Prostate 5LX |
| Chinese Goldthread (Coptis chinensis) (root) aqueous extract | 7 | alias_add | botanical_ingredients:coptis_rhizome | high | 253186 / New Chapter / Zyflamend Mini Softgels |
| organic Oregano (Origanum vulgare) (leaf) supercritical extract | 7 | alias_add | ingredient_quality_map:oregano | high | 253186 / New Chapter / Zyflamend Mini Softgels |
| French Grape (Vitis vinifera) seed extract | 6 | alias_add | ingredient_quality_map:grape_seed_extract | high | 218055 / EuroMedica / Clinical OPC 400 mg |
| Probiotic Fermented Culture | 6 | skip_header | constants:BLEND_HEADER_EXACT_NAMES | high | 219283 / Premier Research Labs / Premier Probiotic Caps |
| Antioxidant Boost | 6 | skip_header | constants:BLEND_HEADER_EXACT_NAMES | high | 239597 / Applied Nutrition / Green Tea Fat Burner |
| Vitality Boost | 6 | skip_header | constants:BLEND_HEADER_EXACT_NAMES | high | 239597 / Applied Nutrition / Green Tea Fat Burner |
| Phytocannabinoids | 6 | new_entry_or_alias | ingredient_quality_map:new hemp phytocannabinoids entry | medium | 241275 / CompleteSpectrum Clinical Cannabis / Whole Hemp Extract |
| Sea Buckthorn (Hippophae rhamnoides) berry pulp and seed Oil | 5 | alias_add | ingredient_quality_map:sea_buckthorn | high | 261769 / EuroMedica / ProHydra-7 |
| Ahiflower (Buglossoides arvensis) seed oil | 5 | new_entry | ingredient_quality_map(new) | medium | 229085 / Chief Originals / Ahiflower Oil Softgels |
| concentrated European Hemp (Cannabis sativa) stalk and seed Oil | 5 | alias_add | ingredient_quality_map:hemp_seed_oil | medium | 218180 / EuroMedica / Premium European Hemp Oil |
| Polygodial | 5 | new_entry | ingredient_quality_map(new) | medium | 283343 / Xtendlife / Advanced Candida Support |
| Icosanoic Acid | 5 | map_non_scorable | other_ingredients:fatty_acid_profile_component(new) | medium | 232590 / Douglas Laboratories / Ultra G.L.A. |
| Docosanoic Acid | 5 | map_non_scorable | other_ingredients:fatty_acid_profile_component(new) | medium | 232590 / Douglas Laboratories / Ultra G.L.A. |
| Common Bean (White Kidney Bean) extract | 5 | new_entry_or_alias | ingredient_quality_map or botanical_ingredients | medium | 256605 / Irwin Naturals / Neutralize-Carbs Keto Support |
| Betatene | 5 | alias_add | ingredient_quality_map:vitamin_a | high | 262663 / Karuna / CoQ-10 100 mg |
| Phytofluene | 4 | new_entry_or_alias | ingredient_quality_map:carotenoid family(new) | medium | 12497 / Nature's Plus / Octa-Carotene With Lutein & Lycopene |
| Phytoene | 4 | new_entry_or_alias | ingredient_quality_map:carotenoid family(new) | medium | 12497 / Nature's Plus / Octa-Carotene With Lutein & Lycopene |
| pro-Vitamin A | 4 | alias_add | ingredient_quality_map:vitamin_a | high | 23801 / Protocol For Life Balance / Ortho Multi |
| Zinc Aspartate | 4 | alias_or_form_add | ingredient_quality_map:zinc form | high | 23443 / Ab Cuts Sleek & Lean / Dreamweaver PM |
| Castor Oil | 4 | new_entry | ingredient_quality_map(new) | medium | 15052 / NOW / Castor Oil 650 mg |
| 33 mg LycoMato(R) | 4 | alias_add | ingredient_quality_map:lycopene | high | 17043 / Xtendlife / Omega 3/DHA Fish Oil Premium |
| Millet (Panicum miliaceum) seed Oil CO2 extract | 4 | alias_add | botanical_ingredients:millet | high | 176880 / Terry Naturally / Hair Renew Formula |
| Isoflavone Glycosides | 4 | alias_add | ingredient_quality_map:isoflavones | high | 25260 / Bronson Laboratories / Bladder Relief |
| L-Hydroxylysine | 4 | new_entry_or_alias | ingredient_quality_map:collagen_amino_acid(new) | low |  |
| Myricetin | 4 | new_entry | ingredient_quality_map(new) | medium | 232708 / Life Extension Geroprotect / Ageless Cell |
| Bitter Melon/Marah | 4 | alias_add | botanical_ingredients:bitter_melon_fruit | high | 240755 / Perque / Glucose Regulation Guard Forte |
| French Lilac | 4 | new_entry_or_alias | botanical_ingredients:galega_officinalis(new) | medium | 240755 / Perque / Glucose Regulation Guard Forte |
| PC 35 | 4 | map_non_scorable | other_ingredients:phosphatidylcholine_complex(new) | medium | 240865 / Perque / Liva Guard Forte |
| Phytoene and Phytofluene | 4 | alias_add | ingredient_quality_map:new combined carotenoid alias | medium | 228604 / Douglas Laboratories / Skin Protect |
| Cow Milk | 4 | map_non_scorable | other_ingredients:milk_vehicle | medium | 15627 / Herbal Hills / Calmhills |
| Go-Ghruta | 4 | map_non_scorable | other_ingredients:ghee_vehicle(new) | medium | 202519 / Herbal Hills / Arthrohills |
| VESIsorb Hemp (Cannibis sativa) oil extract | 4 | alias_add | ingredient_quality_map:hemp_seed_oil | medium | 219646 / Pure Encapsulations / Hemp Extract VESIsorb |
| Gamma-Carotene | 4 | alias_add | ingredient_quality_map:vitamin_a | medium | 220793 / Natural Factors / BetaCareAll |
| Gondoic  Acid | 4 | map_non_scorable | other_ingredients:fatty_acid_profile_component(new) | medium | 221219 / SuperSmart / Arctic Plankton Oil 500 mg |
| Pure+ Wild Fish Oil and Antarctic Krill (Euphausia superba) Oil Concentrates | 4 | skip_header | constants:BLEND_HEADER_EXACT_NAMES | medium |  |
| Orange Pekoe (Black) Tea extract | 4 | new_entry_or_alias | botanical_ingredients:camellia_sinensis_black_tea(new) | medium | 240104 / Irwin Naturals / Triple-Tea Fat Burner |
| Cornsilk powder | 4 | new_entry_or_alias | botanical_ingredients:corn_silk(new) | medium | 256309 / Irwin Naturals / Bloat-Away |
| Lactase Enzyme | 4 | alias_add | ingredient_quality_map:digestive_enzymes | medium | 262897 / Wonder Laboratories / Zymelac |
| Ahiflower Seed Oil | 4 | new_entry | ingredient_quality_map(new) | medium | 297746 / Energetix / Phyto EFA |
| min. 0.08 mg Wogonin | 4 | skip_spec_string | skip pattern: ^min\.\s*\d | high | 38659 / New Chapter / Zyflamend Whole Body |
| min. 1.6 mg TPA | 4 | skip_spec_string | skip pattern: ^min\.\s*\d | high | 38659 / New Chapter / Zyflamend Whole Body |
| min. 30 mg Polyphenols | 4 | skip_spec_string | skip pattern: ^min\.\s*\d | high | 38807 / New Chapter / Supercritical Prostate 5LX |
| min. 2.4 mg Berberine | 4 | skip_spec_string | skip pattern: ^min\.\s*\d | high | 39472 / New Chapter / Zyflamend Whole Body |
| min. 6.4 mg Resveratrols | 4 | skip_spec_string | skip pattern: ^min\.\s*\d | high | 39472 / New Chapter / Zyflamend Whole Body |
| delta9,12-cis-Alpha-Linolenic Acid | 4 | alias_add | ingredient_quality_map:alpha-linolenic acid entry | medium | 47393 / OL Olympian Labs / Evening Primrose Oil Extra Strength 1.3 Grams (1,300 mg) |
| Uridine-5'-Monophosphate | 4 | new_entry | ingredient_quality_map(new) | medium | 59730 / Life Extension / Cognitex With Brain Shield |
| Brain Shield | 4 | alias_add | ingredient_quality_map:gastrodin/new gastrodia entry | medium | 59730 / Life Extension / Cognitex With Brain Shield |
| Cordiart Flavonoid Glycoside | 4 | new_entry_or_alias | ingredient_quality_map(new) / citrus flavonoid complex | low | 62500 / Life Extension / Endothelial Defense |

## Inactive (count >= 10)
| Ingredient | Count | Recommendation | Target | Confidence | Inline verification sample |
|---|---:|---|---|---|---|
| Caramel | 138 | alias_add | harmful_additives:ADD_CARAMEL_COLOR + color_indicators aliases | high | 1136 / Jarrow Formulas / CarotenAll Mixed Carotenoids Complex |
| Medium-Chain Triglycerides | 56 | alias_add | other_ingredients:PII_MEDIUM_CHAIN_TRIGLYCERIDES | high | 13452 / Qunol / Ultra CoQ10 100 mg |
| Ammonium Hydroxide | 48 | new_entry | other_ingredients(new) or harmful_additives review | medium | 10369 / Douglas Laboratories / Opti-EPA |
| pure Olive Oil | 41 | alias_add | other_ingredients:PII_EXTRA_VIRGIN_OLIVE_OIL | high | 10426 / Good 'N Natural / Ubiquinol 200 mg |
| Vegetarian Softgel | 38 | alias_add | other_ingredients:vegetarian capsule shell | high | 228640 / CHK Nutrition / Astaxanthin 4 mg |
| St. John's Bread | 36 | new_entry_or_alias | other_ingredients:carob(new alias) | medium | 239454 / Irwin Naturals / Triple Shredder Body-Shaper |
| Gamma-Tocopherol | 33 | alias_add | other_ingredients:tocopherol preservative | medium | 1127 / Jarrow Formulas / Q-absorb 100 mg |
| Caramel powder | 26 | alias_add | harmful_additives:ADD_CARAMEL_COLOR + color_indicators aliases | high | 11630 / Sonoran Bloom / Wellavoh Daily Multi-Nutrient Complex For Women PM Formula |
| non-GMO Sunflower Lecithin | 26 | alias_add | other_ingredients:NHA_LECITHIN_SUNFLOWER | high | 220801 / Natural Factors / PQQ-10 |
| non-GMO Soy Lecithin | 25 | alias_add | other_ingredients:PII_LECITHIN_SOY | high | 232641 / Nootropics Depot / Sytrinol Citrus Fruit & Malaysian Red Palm Oil Extract Softgels |
| Food Starch, Modified | 24 | alias_add | other_ingredients:NHA_MODIFIED_FOOD_STARCH | high | 269670 / Doctor's Best / Beauty Ceramides |
| non-GMO Soybean Oil | 23 | alias_add | other_ingredients:soybean_oil alias | high | 13528 / NOW / Lecithin |
| Caramel Liquid | 23 | alias_add | harmful_additives:ADD_CARAMEL_COLOR + color_indicators aliases | high | 232122 / Nootropics Depot / CoQH-CF Softgels 100 mg |
| Methacrylic Acid Copolymer | 22 | new_entry | other_ingredients(new polymer coating excipient) | high | 10014 / Sunmark / Enteric Coated Fish Oil 1000 mg |
| Food Starch | 21 | alias_add | other_ingredients:starch aliases | high | 261644 / Quality of Life / AHCC Rx |
| Cottonseed Oil | 18 | new_entry | other_ingredients(new oil excipient) | medium | 10416 / Good 'N Natural / Aloe Vera Gel 5000 mg |
| mixed Vitamin E Tocopherols | 18 | alias_add | other_ingredients:tocopherol preservative | medium | 247353 / Renew Life Norwegian Gold / Kids DHA Fruit Punch Flavor |
| D-Delta-Tocopherol | 18 | alias_add | other_ingredients:tocopherol preservative | medium | 217971 / Village Vitality / Vitamin E 1,000 IU |
| D-Gamma-Tocopherol | 18 | alias_add | other_ingredients:tocopherol preservative | medium | 217971 / Village Vitality / Vitamin E 1,000 IU |
| D-Beta Tocopherol | 18 | alias_add | other_ingredients:tocopherol preservative | medium | 217971 / Village Vitality / Vitamin E 1,000 IU |
| Gamma Cyclodextrin | 17 | alias_add | other_ingredients:PII_CYCLODEXTRIN | high | 230044 / Health Thru Nutrition Naturally / Freedom Softgels |
| kosher Gelatin | 17 | alias_add | other_ingredients:PII_GELATIN_CAPSULE | high | 231414 / Micro Ingredients / COQ-10 |
| Decaglycerol Monolaurate | 17 | new_entry | other_ingredients(new emulsifier) | medium | 24774 / Doctor's Best / Best Tocotrienols 50 mg |
| hydroxylated Soy Lecithin | 17 | alias_add | other_ingredients:lecithin hydroxy variants | medium | 221094 / Country Life / Maxi-Sorb Mega CoQ10 100 mg |
| USP purified Water | 16 | alias_add | other_ingredients:PII_PURIFIED_WATER | high | 11672 / Nature's Answer / EPA Fish Oil 1000 mg |
| Mica | 16 | new_entry | other_ingredients(new coating colorant) | medium | 232708 / Life Extension Geroprotect / Ageless Cell |
| Veg. Glycerin | 16 | alias_add | other_ingredients:NHA_VEGETABLE_GLYCERIN | high | 244198 / DC / Breath Freshener |
| Tapioca Starch, Modified | 16 | alias_add | other_ingredients:NHA_MODIFIED_FOOD_STARCH / tapioca starch | high | 267732 / doTERRA / Zendocrine Softgels |
| hydroxylated Lecithin | 15 | alias_add | other_ingredients:lecithin hydroxy variants | medium | 13452 / Qunol / Ultra CoQ10 100 mg |
| FD&C Red #3 | 14 | new_entry_or_alias | harmful_additives(new synthetic dye entry) | high | 12559 / Cellucor / CLK Raspberry Flavored Softgels |
| Sorbitan Monooleate | 14 | new_entry | other_ingredients(new emulsifier) | medium | 13168 / Country Life / CoQ10 30 mg |
| Bee's Wax | 14 | alias_add | other_ingredients:PII_BEESWAX | high | 12982 / dotFIT / Superior Antioxidant |
| Polyglycerol Fatty Acid Esters | 14 | new_entry | other_ingredients(new emulsifier) | medium | 232201 / Douglas Laboratories / Ubiquinol-QH |
| natural Lemon Oil flavor | 14 | alias_add | other_ingredients:natural flavor entries | high | 23093 / Vitamer Laboratories / Omega-3 Once Daily Natural Lemon Flavor |
| Caramel extract | 13 | alias_add | harmful_additives:ADD_CARAMEL_COLOR + color_indicators aliases | high | 1128 / Jarrow Formulas / QH-absorb 100 mg |
| Sorethytan Monooleate | 13 | data_cleanup | normalize typo -> Sorbitan Monooleate | high | 303258 / NeoLife Nutritionals / Vitamin A |
| non-GMO Safflower Oil | 13 | alias_add | other_ingredients:safflower oil aliases | medium | 240080 / Jarrow Formulas / Astaxanthin 4 mg |
| Sorbitol Sorbitan solution | 13 | new_entry | other_ingredients(new emulsifier/solvent) | medium | 221690 / Nutricost / Astaxanthin 12 mg |
| Disodium Phosphate | 13 | new_entry | other_ingredients(new buffering salt) | medium | 241665 / HUM / Arctic Repair |
| non-GMO PlantGel softgel | 13 | alias_add | other_ingredients:vegetarian capsule shell | high | 222758 / Garden of Life Dr. Formulated / CBD 10 mg Softgels |
| Calcium Chloride | 12 | new_entry | other_ingredients(new mineral salt excipient) | medium | 13190 / Finest Natural / Fish Oil Triple Strength 1400 mg |
| extra-virgin Olive Oil | 12 | alias_add | other_ingredients:PII_EXTRA_VIRGIN_OLIVE_OIL | high | 253186 / New Chapter / Zyflamend Mini Softgels |
| Polyoxyl Castor Oil | 12 | new_entry | other_ingredients(new surfactant) | medium | 243237 / Jarrow Formulas / Famil-E |
| Vitamin E, Natural | 12 | alias_add | other_ingredients:tocopherol preservative | medium | 277489 / TRUNATURE / Evening Primrose Oil 1000 mg |
| refined Soybean Oil | 11 | alias_add | other_ingredients:soybean_oil alias | high | 11039 / 21st Century / Beta Carotene 25,000 IU |
| Natural Lemon/Lime flavor | 11 | alias_add | other_ingredients:natural flavor entries | high | 243767 / Purity Products / Omega-3 Super Boost |
| high PC Lecithin | 11 | alias_add | other_ingredients:lecithin aliases | medium | 243421 / Tishcon Corp. / Q-Gel Ultra Coenzyme Q10 60 mg |
| Sea Vegetable extract | 11 | alias_add | other_ingredients:seaweed/capsule additive aliases | medium | 279800 / Bluebonnet / Lycopene 20 mg |
| Palm Olein | 11 | new_entry_or_alias | other_ingredients:palm oil fraction alias | medium | 243145 / Jarrow Formulas / CarotenAll |
| non-GMO modified Corn Starch | 11 | alias_add | other_ingredients:NHA_MODIFIED_FOOD_STARCH | high | 274410 / Lake Avenue Nutrition / Lutein 20 mg |
| Glyceryl Stearate | 11 | new_entry | other_ingredients(new emulsifier) | medium | 54530 / Carlson / Super 2 Daily |
| Safflower seed Oil | 11 | alias_add | other_ingredients:safflower oil aliases | medium | 217352 / tnvitamins / Ultra Thin CLA 1000 mg |
| Kosher Beef Gelatin | 11 | alias_add | other_ingredients:PII_GELATIN_CAPSULE | high | 229763 / Health Thru Nutrition Naturally / CoQ10 100 mg |
| Medium-Chain Triglycerides Oil | 10 | alias_add | other_ingredients:PII_MEDIUM_CHAIN_TRIGLYCERIDES | high | 174718 / Swanson Premium Brand / Lycopene 10 mg |
| Non-GMO Sunflower Lecithin | 10 | alias_add | other_ingredients:NHA_LECITHIN_SUNFLOWER | high | 34260 / Protocol For Life Balance / Boswellia Extract 500 mg |
| pure Water | 10 | alias_add | other_ingredients:PII_PURIFIED_WATER | high | 247074 / Moss Nutrition / EPO Organic 1000 mg |
| Full Spectrum Curcumin | 10 | skip_descriptor | other_ingredients:brand descriptor | medium | 219376 / Solgar / Full Spectrum Curcumin |
| highly refined and concentrated Omega-3 Fish Oil | 10 | skip_descriptor | other_ingredients:descriptor alias | medium | 223248 / Vital Nutrients / Ultra Pure Fish Oil 1000 Lemon Flavor |

## Coverage
- Active high-impact rows covered by explicit recommendation: 258 / 258 occurrences
- Inactive high-impact rows covered by explicit recommendation: 1162 / 1162 occurrences
- Remaining active occurrences in high-impact set needing manual review: 0
- Remaining inactive occurrences in high-impact set needing manual review: 0
