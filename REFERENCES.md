# References to Verify Online

Status: Partially verified on 2026-01-07 (UTC). Use only NIH ODS, FDA, NASEM/IOM, USP, or PubMed systematic reviews/meta-analyses.

## Unit Conversion Constants
Source of truth: `scripts/data/unit_conversions.json`

- Vitamin D (D2/D3) IU↔mcg
  - Values: `iu_to_mcg=0.025`, `mcg_to_iu=40`
  - File: `scripts/data/unit_conversions.json:21`-`scripts/data/unit_conversions.json:45`
  - Stated source: FDA Guidance 2020
  - Verified against: NIH ODS Vitamin D (Health Professional) states “1 mcg vitamin D is equal to 40 IU”
  - Source: https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/
  - Date accessed: 2026-01-07

- Vitamin E IU↔mg (natural vs synthetic)
  - Natural d-alpha: `iu_to_mg=0.67`, `mg_to_iu=1.49`
  - Synthetic dl-alpha: `iu_to_mg=0.45`, `mg_to_iu=2.22`
  - File: `scripts/data/unit_conversions.json:48`-`scripts/data/unit_conversions.json:87`
  - Stated source: NIH ODS
  - Verified against: NIH ODS Vitamin E conversion rules (mg↔IU)
  - Source: https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional?print=1
  - Date accessed: 2026-01-07

- Vitamin A IU↔mcg RAE (form-specific)
  - Retinol: `iu_to_mcg_rae=0.3`, `mcg_rae_to_iu=3.33`
  - Beta-carotene (supplement): `iu_to_mcg_rae=0.1`, `mcg_rae_to_iu=10`, `mcg_beta_carotene_to_mcg_rae=0.5`
  - Beta-carotene (food): `iu_to_mcg_rae=0.05`, `mcg_rae_to_iu=20`, `mcg_beta_carotene_to_mcg_rae=0.083`
  - File: `scripts/data/unit_conversions.json:89`-`scripts/data/unit_conversions.json:146`
  - Stated source: NIH ODS
  - Needs verification: NIH ODS Vitamin A and FDA labeling guidance do not clearly publish IU↔RAE in this format
  - Candidate sources:
    - NIH ODS Vitamin A (Health Professional): https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/
    - FDA Nutrition/Supplement Facts label guidance (vitamin A IU legacy): https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels
    - NIH DSID Conversions (blocked by Cloudflare on 2026-01-07): https://dsid.od.nih.gov/Conversions.php
  - Date accessed: 2026-01-07 (DSID access blocked)

- Folate DFE conversions
  - Folic acid: `mcg_to_mcg_dfe=1.7`, `mcg_dfe_to_mcg=0.588`
  - Methylfolate: `mcg_to_mcg_dfe=1.7`
  - Food folate: `mcg_to_mcg_dfe=1.0`
  - File: `scripts/data/unit_conversions.json:159`-`scripts/data/unit_conversions.json:203`
  - Stated source: NIH ODS
  - Verified against: NIH ODS Folate DFE definitions (1 mcg DFE = 1 mcg food folate; 0.6 mcg folic acid with food; 0.5 mcg folic acid empty stomach)
  - Source: https://ods.od.nih.gov/factsheets/Folate-HealthProfessional?print=1
  - Date accessed: 2026-01-07

- Niacin NE conversions
  - `mg_to_mg_ne=1.0`, `tryptophan_mg_to_mg_ne=0.0167` (60 mg tryptophan = 1 mg NE)
  - File: `scripts/data/unit_conversions.json:206`-`scripts/data/unit_conversions.json:219`
  - Stated source: NIH ODS
  - Verified against: NIH ODS Niacin definition of NE (1 mg niacin = 1 NE; 60 mg tryptophan = 1 NE)
  - Source: https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional?print=1
  - Date accessed: 2026-01-07

## RDA/AI/UL Tables
Source of truth: `scripts/data/rda_optimal_uls.json`

- Database metadata and stated sources
  - File: `scripts/data/rda_optimal_uls.json:2`-`scripts/data/rda_optimal_uls.json:23`
  - Stated sources: IOM DRI, NASEM 2019 sodium/potassium update, FDA, USDA, clinical research
  - Verify against: NASEM/IOM DRI reports; FDA Daily Value guidance; NIH ODS nutrient recommendations
  - Candidate sources:
    - NASEM DRI collection: https://nap.nationalacademies.org/collection/57/dietary-reference-intakes
    - FDA Daily Values: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels
    - NIH ODS fact sheets: https://ods.od.nih.gov/factsheets/list-all/

- Nutrient thresholds (RDA/AI/UL)
  - File: `scripts/data/rda_optimal_uls.json:24` (start of `nutrient_recommendations`)
  - Requirement: verify each nutrient’s RDA/AI/UL values and units against authoritative sources.

### RDA/AI/UL Verification Log (in progress)

Format: Nutrient | JSON unit | JSON values checked | Sources | Status | Date

- Vitamin D | mcg | Male/Female 19-70 RDA 15, UL 100; 71+ RDA 20, UL 100 | NASEM DRI (Calcium & Vitamin D, 2011): https://nap.nationalacademies.org/catalog/13050/dietary-reference-intakes-for-calcium-and-vitamin-d; NIH ODS Vitamin D: https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Vitamin C | mg | Male 19+ RDA 90, UL 2000; Female 19+ RDA 75, UL 2000 | NASEM DRI (Vitamin C/E/Selenium/Carotenoids, 2000): https://nap.nationalacademies.org/catalog/9810/dietary-reference-intakes-for-vitamin-c-vitamin-e-selenium-and-carotenoids; NIH ODS Vitamin C: https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Iron | mg | Male 19+ RDA 8, UL 45; Female 19-50 RDA 18, UL 45; Female 51+ RDA 8, UL 45 | NASEM DRI (Vitamin A/K/Trace Elements incl. Iron, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Iron: https://ods.od.nih.gov/factsheets/Iron-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07

- Calcium | mg | Male 19-50 RDA 1000, UL 2500; Male 51-70 RDA 1000, UL 2000; Female 51+ RDA 1200, UL 2000 | NASEM DRI (Calcium & Vitamin D, 2011): https://nap.nationalacademies.org/catalog/13050/dietary-reference-intakes-for-calcium-and-vitamin-d; NIH ODS Calcium: https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Zinc | mg | Male 19+ RDA 11, UL 40; Female 19+ RDA 8, UL 40 | NASEM DRI (Vitamin A/K/Trace Elements incl. Zinc, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Zinc: https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Folate | mcg DFE | Adult RDA 400, UL 1000 | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Folate: https://ods.od.nih.gov/factsheets/Folate-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Vitamin A | mcg RAE | Male 19+ RDA 900, UL 3000; Female 19+ RDA 700, UL 3000 | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Vitamin A: https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Vitamin E | mg alpha-tocopherol | Adult RDA 15, UL 1000 | NASEM DRI (Vitamin C/E/Selenium/Carotenoids, 2000): https://nap.nationalacademies.org/catalog/9810/dietary-reference-intakes-for-vitamin-c-vitamin-e-selenium-and-carotenoids; NIH ODS Vitamin E: https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Vitamin K | mcg | AI 120 (male), 90 (female); UL ND | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Vitamin K: https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Vitamin B6 | mg | Adult 19-50 RDA 1.3, UL 100; Male 51+ RDA 1.7; Female 51+ RDA 1.5 | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Vitamin B6: https://ods.od.nih.gov/factsheets/VitaminB6-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Vitamin B12 | mcg | Adult RDA 2.4, UL ND | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Vitamin B12: https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Niacin | mg NE | Adult RDA 16 (male), 14 (female), UL 35 | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Niacin: https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Thiamin | mg | Adult RDA 1.2 (male), 1.1 (female), UL ND | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Thiamin: https://ods.od.nih.gov/factsheets/Thiamin-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Riboflavin | mg | Adult RDA 1.3 (male), 1.1 (female), UL ND | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Riboflavin: https://ods.od.nih.gov/factsheets/Riboflavin-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Pantothenic Acid | mg | AI 5, UL ND | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Pantothenic Acid: https://ods.od.nih.gov/factsheets/PantothenicAcid-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Biotin | mcg | AI 30, UL ND | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Biotin: https://ods.od.nih.gov/factsheets/Biotin-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Choline | mg | AI 550 (male), 425 (female), UL 3500 | NASEM DRI (Thiamin/Riboflavin/Niacin/B6/Folate/B12/Pantothenic Acid/Biotin/Choline, 1998): https://nap.nationalacademies.org/catalog/6015/dietary-reference-intakes-for-thiamin-riboflavin-niacin-vitamin-b6-folate-vitamin-b12-pantothenic-acid-biotin-and-choline; NIH ODS Choline: https://ods.od.nih.gov/factsheets/Choline-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Magnesium | mg | Adult RDA 400/310 (19-30), 420/320 (51+); UL 350 (supplemental) | NASEM DRI (Calcium/Magnesium/Vitamin D/Fluoride, 1997): https://nap.nationalacademies.org/catalog/5776/dietary-reference-intakes-for-calcium-phosphorus-magnesium-vitamin-d-and-fluoride; NIH ODS Magnesium: https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Phosphorus | mg | Adult RDA 700, UL 4000 | NASEM DRI (Calcium/Phosphorus/Magnesium/Vitamin D/Fluoride, 1997): https://nap.nationalacademies.org/catalog/5776/dietary-reference-intakes-for-calcium-phosphorus-magnesium-vitamin-d-and-fluoride; NIH ODS Phosphorus: https://ods.od.nih.gov/factsheets/Phosphorus-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Potassium | mg | AI 3400 (male), 2600 (female), UL ND | NASEM DRI (Water/Potassium/Sodium/Chloride/Sulfate, 2005) and 2019 update: https://nap.nationalacademies.org/catalog/10925/dietary-reference-intakes-for-water-potassium-sodium-chloride-and-sulfate; NIH ODS Potassium: https://ods.od.nih.gov/factsheets/Potassium-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Sodium | mg | AI 1500 (19-50), 1200 (71+); CDRR 2300 (used as highest_ul) | NASEM DRI (Water/Potassium/Sodium/Chloride/Sulfate, 2005) and 2019 update: https://nap.nationalacademies.org/catalog/10925/dietary-reference-intakes-for-water-potassium-sodium-chloride-and-sulfate; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels; NIH ODS Sodium page not available (404 on 2026-01-07) | Not verified (ODS not available) | Pending
- Chloride | mg | AI 2300 (adult), 1800 (71+); UL 3600 | NASEM DRI (Water/Potassium/Sodium/Chloride/Sulfate, 2005): https://nap.nationalacademies.org/catalog/10925/dietary-reference-intakes-for-water-potassium-sodium-chloride-and-sulfate; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels; NIH ODS Chloride page not available (404 on 2026-01-07) | Not verified (ODS not available) | Pending
- Iodine | mcg | Adult RDA 150, UL 1100 | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Iodine: https://ods.od.nih.gov/factsheets/Iodine-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Selenium | mcg | Adult RDA 55, UL 400 | NASEM DRI (Vitamin C/E/Selenium/Carotenoids, 2000): https://nap.nationalacademies.org/catalog/9810/dietary-reference-intakes-for-vitamin-c-vitamin-e-selenium-and-carotenoids; NIH ODS Selenium: https://ods.od.nih.gov/factsheets/Selenium-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Copper | mcg | Adult RDA 900, UL 10000 | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Copper: https://ods.od.nih.gov/factsheets/Copper-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Manganese | mg | AI 2.3 (male), 1.8 (female), UL 11 | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Manganese: https://ods.od.nih.gov/factsheets/Manganese-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Molybdenum | mcg | Adult RDA 45, UL 2000 | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Molybdenum: https://ods.od.nih.gov/factsheets/Molybdenum-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Chromium | mcg | AI 35 (male), 25 (female), UL ND | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Chromium: https://ods.od.nih.gov/factsheets/Chromium-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Fluoride | mg | AI 4 (male), 3 (female), UL 10 | NASEM DRI (Calcium/Phosphorus/Magnesium/Vitamin D/Fluoride, 1997): https://nap.nationalacademies.org/catalog/5776/dietary-reference-intakes-for-calcium-phosphorus-magnesium-vitamin-d-and-fluoride; NIH ODS Fluoride: https://ods.od.nih.gov/factsheets/Fluoride-HealthProfessional?print=1; FDA DV: https://www.fda.gov/food/new-nutrition-facts-label/daily-value-new-nutrition-and-supplement-facts-labels | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Boron | mg | UL 20 (no RDA/AI) | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Boron: https://ods.od.nih.gov/factsheets/Boron-HealthProfessional?print=1 | Verified (ODS cross-check; DRI link recorded) | 2026-01-07
- Nickel | mg | ND (no RDA/AI/UL in JSON) | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Nickel page not available (404 on 2026-01-07) | Not verified (ODS not available) | Pending
- Silicon | mg | ND (no RDA/AI/UL in JSON) | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Silicon page not available (404 on 2026-01-07) | Not verified (ODS not available) | Pending
- Vanadium | mcg | UL 1800 (no RDA/AI in JSON) | NASEM DRI (Vitamin A/K/Trace Elements, 2001): https://nap.nationalacademies.org/catalog/10026/dietary-reference-intakes-for-vitamin-a-vitamin-k-arsenic-boron-chromium-copper-iodine-iron-manganese-molybdenum-nickel-silicon-vanadium-and-zinc; NIH ODS Vanadium page not available (404 on 2026-01-07) | Not verified (ODS not available) | Pending
- Sulfate | mg | ND (no RDA/AI/UL in JSON) | NASEM DRI (Water/Potassium/Sodium/Chloride/Sulfate, 2005): https://nap.nationalacademies.org/catalog/10925/dietary-reference-intakes-for-water-potassium-sodium-chloride-and-sulfate; NIH ODS Sulfate page not available (404 on 2026-01-07) | Not verified (ODS not available) | Pending

Note: Non-DRI compounds in `rda_optimal_uls.json` (e.g., alpha-lipoic acid, coenzyme Q10, lutein, lycopene) require separate evidence policies; not included in this DRI verification pass.

## Banned/Recall Safety Data
Source of truth: `scripts/data/banned_recalled_ingredients.json`

- Permanently banned substances (example entries: Ephedra, DMAA, Yellow Oleander)
  - File: `scripts/data/banned_recalled_ingredients.json:1`
  - Requirement: verify each entry's regulatory status, ban dates, and rationale against FDA enforcement actions/recalls and authoritative safety sources.
  - Candidate sources:
    - FDA Recalls, Market Withdrawals, and Safety Alerts: https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts
    - FDA Warning Letters (supplements): https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters

### FDA Source Fields (v3.1+)

Product recall entries (`entity_type: "product"`) should include in `references_structured`:

- `fda_recall_url`: Direct link to FDA recall notice or warning letter
- `fda_recall_number`: FDA recall case number (e.g., "R-1234-2026") when available
- `date`: Date of recall notice
- `type`: One of `fda_recall`, `fda_warning_letter`, `fda_advisory`

Example structure:
```json
"references_structured": [
  {
    "type": "fda_recall",
    "title": "FDA Recall Notice - Product Name",
    "fda_recall_url": "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/...",
    "fda_recall_number": "R-1234-2026",
    "date": "2026-01-15",
    "evidence_grade": "A",
    "supports_claims": ["regulatory_action"]
  }
]
```

### Product Matching Rules (v3.1+)

Product entries should follow these alias and matching rules:

1. **Brand-qualified aliases**: All aliases must include brand name or unique identifiers
   - Good: `"live it up super greens original"`
   - Bad: `"super greens original"` (too generic, could match other brands)

2. **Synchronized fields**: Keep `aliases`, `synonyms`, and `match_rules.label_tokens` in sync

3. **Negative match terms**: Populate `match_rules.negative_match_terms` with competitor brand names to prevent false positive matches

Example:
```json
"aliases": ["live it up super greens original", "superfoods inc super greens"],
"synonyms": ["live it up super greens original", "superfoods inc super greens"],
"match_rules": {
  "label_tokens": ["live it up super greens original", "superfoods inc super greens"],
  "negative_match_terms": ["amazing grass", "garden of life", "organifi"]
}
```

## Matching Strategy (v3.1+)

The enrichment system uses a tiered matching approach optimized for safety-critical applications.

### Matching Tiers (by priority)

| Tier | Method | Use Case | False Positive Risk |
|------|--------|----------|---------------------|
| 1 | Exact match | Direct name match | None |
| 2 | Alias match | Known synonyms | Low |
| 3 | Token-bounded | Word boundary matching | Low |
| 4 | Fuzzy (threshold 85%) | Typo tolerance | Medium |

### Standardized Identifiers

The system supports multiple identifier types for cross-database linking:

| Identifier | Source | Coverage | Notes |
|------------|--------|----------|-------|
| `CUI` | UMLS Metathesaurus | ~65% | Gold standard for medical terms |
| `rxcui` | RxNorm (NLM) | ~20% | FDA drug normalization |
| `pubchem_cid` | PubChem (NCBI) | ~6% | Chemical compounds |
| `cas_number` | CAS Registry | ~9% | Chemical identification |
| `unii` | FDA UNII | ~1% | FDA substance registration |

### Safety Policy: Banned Substance Detection

**Banned substance detection uses EXACT matching only** (Tiers 1-3). Fuzzy matching is explicitly disabled for safety-critical detection to prevent:
- False positives (flagging safe ingredients as banned)
- False negatives (missing actual banned substances due to partial matches)

```python
# From enrich_supplements_v3.py - banned detection uses token_bounded only
matched, matched_variant = self._token_bounded_match(
    ing_name, banned_name, all_aliases
)
# NO fuzzy fallback for safety-critical matching
```

### Fuzzy Matching Configuration

For ingredient quality matching (non-safety-critical), fuzzy matching is available as a fallback:

```python
# Default thresholds
threshold = 0.85       # Minimum score to accept match
review_threshold = 0.90  # Flag for human review if below this
```

Matches between `threshold` and `review_threshold` are flagged with `needs_review: true`.

### Files

| File | Purpose |
|------|---------|
| [fuzzy_matcher.py](scripts/fuzzy_matcher.py) | Standalone fuzzy matching module |
| [enrich_supplements_v3.py](scripts/enrich_supplements_v3.py) | Contains `_fuzzy_ingredient_match()` |
| [test_fuzzy_matching.py](scripts/tests/test_fuzzy_matching.py) | Fuzzy matching tests |

## Notes
- All references above are required for medical/legal defensibility.
- If any values change, update this file and the relevant JSON entries together.
