# Unmapped Ingredient Categorization Report

Generated: 2026-02-12
Total unmapped active: 1,592 unique (5,648 occurrences)

---

## Category E: Skip Terms (Nutrition Aggregates) - ADD TO EXCLUDED_NUTRITION_FACTS

These are label math/rollups that should NEVER be mapped as ingredients.

### Already Covered (in constants.py):
- Total Omega-6 Fatty Acids (99 occurrences) ✓
- Total Omega-9 Fatty Acids (95) ✓
- Total Fish Oil (40) ✓
- Total Phospholipids (37) ✓
- Total Tocotrienols (22) ✓
- Total EPA + DHA (19) ✓
- Other Omega-6 Fatty Acids (19) ✓
- Omega-5-6-7-8-9-11 (18) ✓
- Total Omega-5 & 7 Fatty Acids (18) ✓
- Total Fatty Acids (16) ✓
- Total D-Mixed Tocotrienols (13) ✓
- Total Omega 3-5-6-7-8-9-11 (13) ✓

### Need to Add to EXCLUDED_NUTRITION_FACTS:
```
# Additional omega variants
"omega-5 fatty acids", "omega-7 fatty acids", "omega-11 fatty acids",
"omega 3-6-9", "omega 3 fish oil",
"total omega 3", "total omega 6", "total omega 9",
"total omega long-chain fatty acids",
"total omega 3 polyunsaturates",

# Specific compound totals (aggregates, not discrete)
"total docosapentaenoic acid", "total turmerones",
"total eleutherosides", "total thiosulfinates",

# Generic aggregate phrases
"fish oils", "other fish oils", "fish body oils",
"omega fatty acids", "essential fatty acid",

# Calorie/energy variants
"kcals", "grasa total",

# Miscellaneous aggregates
"other isomers", "other sterols", "other soy phospholipids",
"other fatty acids, lignans",
"five other naturally found fatty acids",
"and five other naturally found fatty acids",
"stearidonic, eicosatrienoic, eicosatetraenoic, heneicosapentaenoic, and alpha-linolenic acids",
```

---

## Category F: Extraction Noise (handled by strip_extraction_noise)

These are prefix patterns that the new `strip_extraction_noise()` function should handle:

### Pattern: "from X mg of Y"
- "from 286 mg of LYC-O-MATO(R)" → "LYC-O-MATO"
- "from 862 mg. of L-carnitine fumarate" → "L-carnitine fumarate"
- "from 400 mg Fish Oil" → "Fish Oil"
- "from 44.7 mg Fish Oil" → "Fish Oil"
- "from 445 mg Fish Oil" → "Fish Oil"

### Pattern: "Contains X mg of Y"
- "Contains 12.5 mcg of Stabilized Allicin" → "Stabilized Allicin"
- "Contains 15 mg of Caffeine" → "Caffeine"
- "Contains 2 mg of Caffeine" → "Caffeine"

### Pattern: "min. X mg Y"
- "min. 0.08 mg Wogonin" → "Wogonin"
- "min. 1.6 mg TPA" → "TPA"
- "min. 30 mg Polyphenols" → "Polyphenols"
- "min. 2.4 mg Berberine" → "Berberine"
- "min. 6.4 mg Resveratrols" → "Resveratrols"

### Pattern: "providing X mg Y"
- "providing 10 mg Beta Sitosterol" → "Beta Sitosterol"
- "providing 100 mg Phosphatidylserine" → "Phosphatidylserine"
- "providing Tocotrienols" → "Tocotrienols"
- "providing 12 mg of Turmerones" → "Turmerones"

### Pattern: "standardized to contain X mg Y"
- "standardized to contain 7.5 mg Petasins" → "Petasins"
- "standardized to contain >4 mg of Miliacin" → "Miliacin"

### Pattern: "yielding X mg of Y"
- "yielding 37 mg of Trans Resveratrol" → "Trans Resveratrol"

### Pattern: "containing X mg Y"
- "containing 24 mg of Total Rice Tocotrienols" → "Total Rice Tocotrienols"
- "containing fatty acids" → "fatty acids"

### Other Label Noise (add to EXCLUDED_LABEL_PHRASES):
- "which typically provides:"
- "Providing:"
- "providing minimum 40 mg of beta-sitosterol"

---

## Category B: Branded Aliases - ADD TO ingredient_quality_map.json

These are branded ingredient names that should be aliases for existing parents:

### CoQ10 Branded Forms (alias to coenzyme_q10):
| Brand Name | Occurrences | Maps to Form |
|------------|-------------|--------------|
| Q-Sorb Coenzyme Q-10 | 58 | ubiquinone |
| Hydro Q-Sorb Coenzyme Q10 | 14 | ubiquinol |
| Megasorb Coenzyme Q-10 | 12 | ubiquinone |
| Kaneka Q10 | 12 | ubiquinone |
| Q-Gel Coenzyme Q10 | 10 | ubiquinone |
| CoQsol Coenzyme Q10 | 8 | ubiquinone |
| Kaneka Ubiquinol Coenzyme Q10 | 4 | ubiquinol |
| Nutri-Nano Coenzyme Q-10 | 4 | ubiquinone |
| KanekaQ10 Coenzyme Q10 | 4 | ubiquinone |
| Kaneka-QH Ubiquinol | 3 | ubiquinol |
| CoQH-CF Ubiquinol | 4 | ubiquinol |
| Quinogel Ubiquinol | 2 | ubiquinol |

### Curcumin/Turmeric Branded Forms:
| Brand Name | Occurrences | Maps to |
|------------|-------------|---------|
| HydroCurc | 24 | Curcumin (enhanced absorption) |
| Longvida Optimized Curcumin extract | 6 | Curcumin (lipidated) |
| Meriva Curcumin Phytosome | 2 | Curcumin phytosome |
| CurQLife | 2 | Curcumin |
| NovaSol Curcumin Liquid Extract | 1 | Curcumin (micellar) |
| Curcu-Gel | 1 | Curcumin |

### CLA Branded Forms:
| Brand Name | Occurrences | Maps to |
|------------|-------------|---------|
| Tonalin | 13 | CLA (conjugated linoleic acid) |
| Tonalin(R) CLA | 12 | CLA |
| Tonalin CLA | 11 | CLA |
| Myoleptin(TM) CLA | 12 | CLA |
| Myoleptin CLA | 8 | CLA |
| CLA95 | 2 | CLA |
| Lean CLA | 1 | CLA |

### Phosphatidylserine Branded Forms:
| Brand Name | Occurrences | Maps to |
|------------|-------------|---------|
| Neuro-PS | 18 | Phosphatidylserine |
| Neuro-PS(R) | 6 | Phosphatidylserine |
| Sharp-PS Green Phosphatidylserine | 3 | Phosphatidylserine (sunflower) |
| SerinAid | 1 | Phosphatidylserine |
| SerinAid Phosphatidylserine | 1 | Phosphatidylserine |

### Krill Oil Branded Forms:
| Brand Name | Occurrences | Maps to |
|------------|-------------|---------|
| Superba Boost Krill Oil | 10 | Krill Oil |
| 100% pure Superba2 Krill Oil | 6 | Krill Oil |
| SuperbaBoost Krill Oil | 5 | Krill Oil |
| NKO Krill Oil | 5 | Krill Oil |
| Ester-Omega Krill Oil | 5 | Krill Oil |
| K-REAL Krill Oil | 4 | Krill Oil |
| 100% Pure Superba Krill Oil | 3 | Krill Oil |
| Azantis Krill Oil | 2 | Krill Oil |

### Other Branded Ingredients:
| Brand Name | Occurrences | Maps to Parent |
|------------|-------------|----------------|
| Tocomin SupraBio | 36 | Tocotrienols |
| Sytrinol | 20 | Citrus polymethoxylated flavones |
| ImmunEnhancer | 19 | Beta-glucan |
| GlucoHelp | 16 | Banaba extract (corosolic acid) |
| PGX | 16 | Glucomannan fiber |
| Lyc-O-Mato | 10 | Lycopene |
| Celadrin | 10 | Cetylated fatty acids |
| ZMA | 10 | Zinc magnesium aspartate |
| BioResponse DIM | 7 | DIM (diindolylmethane) |
| Relora | 5 | Magnolia/Phellodendron extract |
| Setria L-Glutathione | 3 | L-Glutathione (reduced) |
| MenaQ7 | 3 | Vitamin K2 (MK-7) |
| Suntheanine L-Theanine | 8 | L-Theanine |
| ApresFlex/ApresFLEX | 12 | Boswellia serrata extract (AKBA) |
| EVNol SupraBio | 4 | Tocotrienols (full spectrum) |
| DeltaGOLD Tocotrienols | 9 | Delta-tocotrienol |
| Greenselect Phytosome | 6 | Green tea extract (phytosome) |
| UC-II | 6 | Undenatured type II collagen |

---

## Category A: Real Ingredients - ADD TO ingredient_quality_map.json

These are legitimate supplement ingredients that need proper database entries:

### Fatty Acids (need new parent entries or forms):
| Ingredient | Occurrences | Category | Notes |
|------------|-------------|----------|-------|
| Caprylic Acid | 94 | fatty_acids | C8:0, MCT component |
| Capric Acid | 85 | fatty_acids | C10:0, MCT component |
| Myristic Acid | 39 | fatty_acids | C14:0 saturated |
| Stearidonic Acid | 34 | fatty_acids | C18:4 omega-3 |
| Linolenic Acid | 23 | fatty_acids | Could be alpha or gamma |
| Gamma Linolenic Acid | 14 | fatty_acids | C18:3 omega-6 (GLA) |
| Alpha Linolenic Acid | 11 | fatty_acids | C18:3 omega-3 (ALA) |
| Arachidonic Acid | 5 | fatty_acids | C20:4 omega-6 |
| Punicic Acid | 3 | fatty_acids | C18:3, pomegranate |
| Petroselinic Acid | 2 | fatty_acids | C18:1, parsley seed |

### Phospholipids:
| Ingredient | Occurrences | Category |
|------------|-------------|----------|
| Phosphatidylinositol | 67 | phospholipids |
| Phosphatidyl Inositol | 20 | phospholipids |
| Phosphatidic Acid | 12 | phospholipids |
| Polar Lipids | 8 | phospholipids |

### Tocotrienols (specific forms):
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| D-Alpha-Tocotrienol | 45 | Alpha form |
| Alpha-Tocotrienol | 31 | Alpha form |
| D-Beta-Tocotrienol | 26 | Beta form |
| D-Beta Tocotrienol | 19 | Beta form |
| Beta-Tocotrienol | 9 | Beta form |
| Delta and Beta Tocotrienols | 12 | Combined |

### Carotenoids:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| Alpha-Carotene | 39 | Provitamin A |
| Alpha Carotene | 22 | Provitamin A |
| Gamma-Carotene | 4 | Carotenoid |

### Amino Acids:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| L-Alanine | 23 | Essential |
| L-Histidine | 16 | Essential |
| L-Glutamic Acid | 15 | Non-essential |
| L-Serine | 11 | Non-essential |
| L-Ornithine | 2 | Urea cycle |
| L-Cystine | 1 | Disulfide form |

### Enzymes:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| Nattokinase | 16 | Fibrinolytic enzyme |
| Lactoferrin | 4 | Iron-binding protein |
| Intrinsic Factor | 3 | B12 absorption |
| Lactase Enzyme | 4 | Lactose digestion |

### Phytosterols:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| Beta Sitosterol | 23 | Plant sterol |
| Plant Sterols | 16 | General |
| Plant Sterol Esters | 15 | Esterified |
| Stigmasterol | 5 | Plant sterol |
| Campesterol | 4 | Plant sterol |

### Terpenes/Terpenoids:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| D-Limonene | 34 | Citrus terpene |
| Squalene | 10 | Triterpene |
| Plant Squalene | 54 | Plant-derived |
| Beta-Caryophyllene | 11 | Sesquiterpene |

### Flavonoids/Polyphenols:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| C3G (Cyanidin-3-glucoside) | 24 | Anthocyanin |
| Chlorogenic Acid | 4 | Coffee polyphenol |
| Diosmin | 3 | Citrus flavonoid |
| Chrysin | 5 | Flavone |
| Myricetin | 4 | Flavonol |

### Other Real Ingredients:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| Oil of Oregano | 23 | Carvacrol source |
| Argan Oil | 16 | Moroccan oil |
| Pyrroloquinoline Quinone (PQQ) | 6 | Cofactor |
| Menaquinone | 6 | Vitamin K2 |
| 7-KETO | 11 | DHEA metabolite |
| Gamma Oryzanol | 11 | Rice bran |
| DMG (Dimethylglycine) | 8 | Methylation |
| GLA | 8 | Gamma-linolenic acid |
| Policosanols | 6 | Plant waxes |
| Carnosic Acid | 3 | Rosemary compound |
| Hexacosanol | 3 | Policosanol component |
| Triacontanol | 3 | Policosanol component |

---

## Category C: Delivery Systems - ADD TO enhanced_delivery.json

| Delivery System | Occurrences | Description |
|-----------------|-------------|-------------|
| Siliphos Phytosome | 8 | Milk thistle phytosome |
| Greenselect Phytosome | 6 | Green tea phytosome |
| Meriva Curcumin Phytosome | 2 | Curcumin phytosome |
| VESIsorb | 6+ | Self-emulsifying system |
| MaxSimil | 4+ | Pre-emulsified fish oil |
| Phytosome (generic) | - | Phospholipid complex |

---

## Category D: Source/Oil Variants - Evaluate individually

These may be real ingredients or branded variants:

### Fish/Marine Oils:
| Ingredient | Occurrences | Action |
|------------|-------------|--------|
| Fish Body Oil | 63 | Add as form under fish_oil |
| Fish Liver Oil | 42 | Add as form (has vitamin A/D) |
| Norwegian Fish Oil | 36 | Alias to fish_oil |
| Norwegian Fish Oil concentrate | 28 | Alias to fish_oil |
| Shark Liver Oil | 8 | Separate entry (alkylglycerols) |
| Cod Liver Oil variants | 15+ | Form under fish_oil |
| Salmon Oil variants | 20+ | Form under fish_oil |

### Botanical Extracts needing entries:
| Ingredient | Occurrences | Notes |
|------------|-------------|-------|
| Stinging Nettle root extract | 30 | Urtica dioica |
| Sesame Seed Lignan Extract | 29 | Sesamum indicum |
| Pygeum bark extract | 19 | Prunus africana |
| Uva-Ursi extract | 16 | Arctostaphylos uva-ursi |
| Petasins | 16 | Butterbur compound |

---

## Summary Statistics

| Category | Count | Action Required |
|----------|-------|-----------------|
| E: Skip Terms (Aggregates) | ~80 | Add to EXCLUDED_NUTRITION_FACTS |
| F: Extraction Noise | ~100 | Handled by strip_extraction_noise() |
| B: Branded Aliases | ~150 | Add as aliases in ingredient_quality_map |
| A: Real Ingredients | ~300 | Add new entries to ingredient_quality_map |
| C: Delivery Systems | ~15 | Add to enhanced_delivery.json |
| D: Source Variants | ~100 | Evaluate individually |
| Already mappable | ~850 | Should resolve after above changes |

---

## Priority Actions

1. **HIGH**: Add remaining nutrition aggregates to `EXCLUDED_NUTRITION_FACTS` in constants.py
2. **HIGH**: Add branded CoQ10, CLA, PS aliases to ingredient_quality_map.json
3. **MEDIUM**: Add real fatty acids (Caprylic, Capric, etc.) to ingredient_quality_map.json
4. **MEDIUM**: Add amino acids (L-Alanine, L-Histidine, etc.) to ingredient_quality_map.json
5. **LOW**: Add delivery systems to enhanced_delivery.json
6. **LOW**: Add source oil variants as forms
