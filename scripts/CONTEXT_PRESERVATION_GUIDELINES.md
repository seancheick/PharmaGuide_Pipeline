# Context Preservation Guidelines for Healthcare Ingredient Processing

## The Core Problem

**Issue**: Cleaning process strips critical source context when extracting ingredient components, losing regulatory distinctions essential for healthcare safety.

**Example Case - IGF-1**:
- **Raw**: "New Zealand Deer Antler Velvet" (natural, legal)
- **Extracted**: "IGF-1" (lost context, flagged as unmapped)
- **Result**: Unable to distinguish natural vs synthetic forms

## Healthcare Safety Requirements

### 1. Source Distinction is Critical
```
✅ PRESERVE: "Deer Antler Velvet extract containing IGF-1"
❌ STRIP: "IGF-1" (lost natural source context)

✅ PRESERVE: "Synthetic IGF-1 complex"
❌ STRIP: "IGF-1" (lost synthetic warning)
```

### 2. Regulatory Context Must Survive Processing
- Natural sources often have different legal status than synthetic
- Dosage context affects classification (trace vs therapeutic amounts)
- Manufacturing method impacts safety profile
- Source geography can affect quality/regulation

## Best Practice Framework

### Level 1: Primary Ingredient (ALWAYS Preserve)
Keep complete original names with source context:
- "New Zealand Deer Antler Velvet"
- "Standardized Echinacea extract (4% Echinacoside)"
- "Proprietary Blend containing Beta-Alanine"

### Level 2: Component Mapping (Secondary)
Only extract components when:
1. **Source is preserved** in parent relationship
2. **Natural vs synthetic** distinction maintained
3. **Dosage context** retained
4. **Regulatory status** can be determined

### Level 3: Context Linking
```json
{
  "primary_ingredient": "New Zealand Deer Antler Velvet",
  "source_type": "natural",
  "components": [
    {
      "name": "IGF-1",
      "source_context": "naturally occurring from deer antler velvet",
      "regulatory_status": "legal_natural_source",
      "synthetic_equivalent_banned": true
    }
  ]
}
```

## Implementation Strategy

### For Your Cleaning Process:

#### 1. Conservative Extraction
```python
# CURRENT (problematic)
extract_components("Deer Antler Velvet") → ["IGF-1"] ❌

# IMPROVED (context-preserving)
preserve_source_hierarchy("Deer Antler Velvet") → {
    "primary": "Deer Antler Velvet",
    "source_type": "natural_animal",
    "active_components": ["IGF-1"],
    "regulatory_context": "natural_source_legal"
} ✅
```

#### 2. Tiered Processing
1. **Tier 1**: Map complete ingredient names first
2. **Tier 2**: Extract components only if source preserved
3. **Tier 3**: Flag for manual review if context ambiguous

#### 3. Source Context Flags
```python
CONTEXT_FLAGS = {
    "natural_source": ["extract", "whole", "natural", "organic"],
    "synthetic_source": ["synthetic", "artificial", "complex", "compound"],
    "proprietary": ["blend", "proprietary", "complex", "formula"],
    "standardized": ["standardized", "concentrated", "%", "ratio"]
}
```

## Specific Recommendations for Your Pipeline

### 1. Modify Extraction Logic
- **Before**: Extract individual components aggressively
- **After**: Preserve source hierarchy, extract selectively

### 2. Enhanced Database Structure
```json
{
  "ingredient_hierarchy": {
    "source_ingredient": "Deer Antler Velvet",
    "source_type": "natural",
    "components": [
      {
        "component": "IGF-1",
        "context": "naturally_occurring",
        "legal_status": "permitted",
        "synthetic_equivalent": "banned"
      }
    ]
  }
}
```

### 3. Context Preservation Rules

#### ALWAYS Preserve:
- Source material names (deer antler, whole foods, plants)
- Manufacturing methods (extract, concentrate, synthetic)
- Standardization details (percentages, ratios)
- Proprietary blend relationships
- Geographic origins (if regulatory relevant)

#### NEVER Strip:
- Natural vs synthetic indicators
- Standardization percentages
- Source plant/animal names
- Proprietary blend containers
- Dosage qualifiers

### 4. Quality Control Checks

Before flagging as unmapped:
1. **Source Check**: Is this a component of a known ingredient?
2. **Context Check**: Will classification differ based on source?
3. **Regulatory Check**: Does natural vs synthetic matter legally?
4. **Safety Check**: Could misclassification cause healthcare risk?

If ANY check is "Yes" → Preserve context, don't extract component

## Testing Your Improvements

### Test Cases:
1. **IGF-1 from deer antler** → Should map to natural source database
2. **Synthetic IGF-1** → Should flag as banned
3. **Vitamin E from wheat germ** → Natural source (different bioavailability)
4. **Synthetic Vitamin E** → Synthetic source (different absorption)

### Success Metrics:
- Zero healthcare-critical context loss
- Proper natural vs synthetic classification
- Maintained source-component relationships
- Reduced false unmapped flags for known sources

## Emergency Protocol

When encountering uncertain extractions:
1. **STOP** aggressive component extraction
2. **PRESERVE** complete original ingredient name
3. **FLAG** for manual review with full context
4. **RESEARCH** before any classification decisions

**Healthcare Safety Rule**: When in doubt, preserve more context rather than less. Patient safety depends on accurate ingredient classification.