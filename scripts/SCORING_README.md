# DSLD Supplement Scoring System v3.0.0

## Overview

The scoring script (`score_supplements.py`) calculates product quality scores based on enriched data from the enrichment pipeline. It implements the Scoring v3.0 specification with 80 points total (Section E for User Profile is calculated on device).

## Quick Start

```bash
# Default: reads from output_Lozenges_enriched/enriched, outputs to output_Lozenges_scored
python3 score_supplements.py

# With custom paths
python3 score_supplements.py --input-dir path/to/enriched --output-dir path/to/scored

# Test mode (no files written)
python3 score_supplements.py --dry-run
```

## Scoring Breakdown (80 Points Total)

### Section A: Ingredient Bio-Score & Dosing (0-25 pts)
- **Single nutrient**: `bio_score × dosage_importance` (capped at 25)
- **Multivitamin**: Average of top 5 key vitamins/minerals
- **Multi-ingredient**: Weighted average based on dosage importance

### Section B: Delivery System & Absorption (0-15 pts)
- **Delivery tiers**:
  - Tier 1 (liposomal, nanoemulsion): +8
  - Tier 2 (softgel, lozenge): +5
  - Tier 3 (capsule): +3
  - Tier 4 (tablet): +1
- **Absorption enhancers**:
  - First qualifying enhancer: +3 (requires both enhancer AND enhanced nutrient present)
  - Additional enhancers: +1 each (cap +4 total)

### Section C: Formulation Quality (0-10 pts)
- Organic/wildcrafted certification: +2
- Standardized botanicals (meets threshold): +2
- Synergy cluster (2+ ingredients, adequate doses): +3
- Clinical probiotic strain: +1
- Prebiotic synergy: +2

### Section D: Safety & Compliance (0-30 pts base with penalties/bonuses)
**Start at 30, apply penalties and bonuses:**

**Penalties:**
- Banned substances: -25 (critical), -10 (high), -5 (moderate)
- Harmful additives: -3 (high), -2 (moderate), -1 (low)
- Allergens: -2 (high), -1.5 (moderate), -1 (low)
- Proprietary blends: -10 (critical 75%+), -5 (high 50-74%), -3 (moderate <50%)
- FDA violations: -3 per warning

**Bonuses:**
- Allergen-free claims: +1 each (cap +3)
- Third-party tested (NSF, USP, etc.): +2
- GMP certified: +1
- Batch traceability (COA/QR/lookup): +1
- Top manufacturer (>85% confidence): +2
- CFU documented (probiotics): +1

## Output Format

### Scored Product JSON
```json
{
  "dsld_id": "10042",
  "product_name": "Methyl B12 5,000 mcg Methylcobalamin",
  "brand_name": "Protocol For Life Balance",
  "score_80": 47.5,
  "score_100_equivalent": 59.4,
  "display": "47.5/80",
  "grade": "D",
  "section_scores": {
    "A_ingredient_bio_dosing": {
      "score": 18.0,
      "max": 25,
      "details": {...}
    },
    "B_delivery_absorption": {...},
    "C_formulation_quality": {...},
    "D_safety_compliance": {...}
  },
  "scoring_notes": [
    "Single nutrient: Vitamin B12",
    "Bio-score: 12, Dosage importance: 1.5",
    "Delivery system: lozenge (Tier 2) = +5",
    ...
  ],
  "scoring_metadata": {
    "scoring_version": "3.0.0",
    "scored_date": "2025-12-03T20:14:19.741552Z",
    "enrichment_version": "3.0.0",
    "supplement_type": "single_nutrient"
  }
}
```

### Summary Report
Located in `output_Lozenges_scored/reports/scoring_summary_TIMESTAMP.json`

```json
{
  "processing_info": {
    "scoring_version": "3.0.0",
    "files_processed": 2,
    "duration_seconds": 0.24,
    "timestamp": "2025-12-03T20:14:19.741552Z"
  },
  "stats": {
    "total_products": 978,
    "successful": 978,
    "average_score_80": 44.4,
    "average_score_100": 55.5,
    "score_distribution": {
      "A": 0,
      "B": 40,
      "C": 234,
      "D": 517,
      "F": 187
    }
  }
}
```

## Grade Scale

| Score (/100) | Grade |
|--------------|-------|
| 90-100       | A+    |
| 85-89        | A     |
| 80-84        | A-    |
| 77-79        | B+    |
| 73-76        | B     |
| 70-72        | B-    |
| 67-69        | C+    |
| 63-66        | C     |
| 60-62        | C-    |
| 50-59        | D     |
| <50          | F     |

## Configuration

The script uses the same config file as enrichment (`config/enrichment_config.json`). Key settings:

```json
{
  "paths": {
    "input_directory": "output_Lozenges_enriched/enriched",
    "output_directory": "output_Lozenges_scored"
  },
  "scoring_weights": {
    "absorption_enhancers": {
      "presence_bonus": 3,
      "per_enhancer_bonus": 1
    },
    "allergens": {
      "low_penalty": -1,
      "moderate_penalty": -1.5,
      "high_penalty": -2
    },
    ...
  }
}
```

## Output Structure

```
output_Lozenges_scored/
├── scored/
│   ├── scored_cleaned_batch_1.json  (scored products)
│   └── scored_cleaned_batch_2.json
└── reports/
    └── scoring_summary_20251203_201419.json  (summary stats)
```

## Error Handling

The script gracefully handles:
- Unmapped ingredients (defaults to bio_score = 5)
- Missing enrichment data (returns score of 0 with error details)
- Incompatible enrichment versions (logs warning but continues)

Failed products are included in output with:
```json
{
  "dsld_id": "...",
  "product_name": "...",
  "score_80": 0,
  "score_100_equivalent": 0,
  "display": "0/80",
  "grade": "F",
  "error": "error message here",
  "scoring_metadata": {
    "status": "failed"
  }
}
```

## Implementation Notes

### Key Design Decisions

1. **Unmapped Ingredient Handling**: Ingredients without bio_score data default to 5 (middle of scale) to avoid penalizing products with ingredients not yet in the quality map.

2. **Absorption Enhancer Bonus**: Only awards bonus if BOTH the enhancer AND the enhanced nutrient are present in the formula. This prevents bonus for citric acid in formulas without any minerals.

3. **Proprietary Blend Severity**: Calculated dynamically based on percentage of proprietary ingredients:
   - 75%+: Critical (-10)
   - 50-74%: High (-5)
   - <50%: Moderate (-3)

4. **Top Manufacturer Matching**: Requires >85% confidence for fuzzy matches to avoid false positives.

5. **Section D Floor**: Safety & Compliance score cannot go below 0 (prevents negative section scores).

## Dependencies

- Python 3.7+
- Standard library only (json, os, sys, logging, argparse, datetime, pathlib, typing)
- Optional: `tqdm` for progress bars (falls back gracefully if not installed)

## Testing

```bash
# Test with dry-run
python3 score_supplements.py --dry-run

# Test with small dataset
python3 score_supplements.py --input-dir test_enriched --output-dir test_scored
```

## Troubleshooting

**Issue**: Script fails with "unsupported operand type(s) for *: 'NoneType' and 'float'"
- **Solution**: Ensure enrichment data includes bio_score for all ingredients, or update to latest scorer version that handles None values

**Issue**: No output files generated
- **Solution**: Check input directory path is correct and contains enriched JSON files

**Issue**: Low scores across all products
- **Solution**: Review enrichment data quality - many penalties may indicate data quality issues

## Version Compatibility

- **Enrichment v3.0.0+**: Fully compatible
- **Enrichment v2.x**: May have missing fields, script will handle gracefully with defaults

## Future Enhancements

Section E (User Profile Scoring) will be implemented on the mobile device side to calculate personalized scores based on:
- Age/sex-specific RDA alignment
- User health goals
- Specific nutrient needs
