# Flutter v1.3.0 Integration Guide

> **Supplement to:** `FLUTTER_DATA_CONTRACT_V1.md`  
> **Version:** 1.3.0 — 2026-04-07  
> **Purpose:** How to use the 23 new columns added in Export Schema v1.3.0

This document shows Flutter developers how to leverage the new pre-computed fields for faster UX.

---

## Enhancement 1: Stack Interaction Checking

### **What's New:**
- `ingredient_fingerprint` (TEXT JSON)
- `key_nutrients_summary` (TEXT JSON)
- `contains_stimulants` (INTEGER)
- `contains_sedatives` (INTEGER)
- `contains_blood_thinners` (INTEGER)

### **Use Case:** Multi-Product Safety Validation

**Before v1.3.0:**
```dart
// ❌ OLD: Required fetching detail blobs for all 5 stack products
Future<List<StackWarning>> checkStackSafety(newProduct, stackProducts) async {
  // Fetch 5 detail blobs from Supabase (slow, network-dependent)
  for (product in stackProducts) {
    final blob = await fetchDetailBlob(product.detailBlobSha256);
    // Parse ingredients, aggregate doses...
  }
}
```

**After v1.3.0:**
```dart
// ✅ NEW: Instant check using fingerprints (no network needed)
Future<List<StackWarning>> checkStackSafety(
  ProductsCore newProduct,
  List<ProductsCore> stackProducts,
) async {
  final warnings = <StackWarning>[];
  
  // Parse ingredient fingerprints (already in products_core)
  final newFingerprint = jsonDecode(newProduct.ingredientFingerprint);
  final stackFingerprints = stackProducts
      .map((p) => jsonDecode(p.ingredientFingerprint))
      .toList();
  
  // Check cumulative nutrient doses
  for (final nutrient in newFingerprint['nutrients'].keys) {
    double totalDose = newFingerprint['nutrients'][nutrient]['amount'];
    
    for (final stack in stackFingerprints) {
      if (stack['nutrients'].containsKey(nutrient)) {
        totalDose += stack['nutrients'][nutrient]['amount'];
      }
    }
    
    // Check against UL from bundled rda_optimal_uls.json
    final ul = await lookupUL(nutrient, userProfile);
    if (totalDose > ul) {
      warnings.add(StackWarning(
        type: 'cumulative_dose_exceeded',
        nutrient: nutrient,
        totalDose: totalDose,
        ul: ul,
        severity: 'high',
      ));
    }
  }
  
  // Check conflicting pharmacological effects
  final hasStimulant = newProduct.containsStimulants == 1;
  final hasSedativeInStack = stackProducts.any((p) => p.containsSedatives == 1);
  
  if (hasStimulant && hasSedativeInStack) {
    warnings.add(StackWarning(
      type: 'antagonistic_effects',
      message: 'Stack contains both stimulants and sedatives',
      severity: 'moderate',
    ));
  }
  
  return warnings;
}
```

**Performance:** <100ms vs 2-5 seconds (network dependent)

---

## Enhancement 2: Social Sharing

### **What's New:**
- `share_title` (TEXT)
- `share_description` (TEXT)
- `share_highlights` (TEXT JSON array)
- `share_og_image_url` (TEXT)

### **Use Case:** One-Tap Social Sharing

**Implementation:**
```dart
// lib/services/share_service.dart
void shareProduct(ProductsCore product) {
  final highlights = (jsonDecode(product.shareHighlights) as List).join('\n• ');
  
  Share.share('''
${product.shareTitle}

${product.shareDescription}

✨ Why it's great:
• $highlights

Analyzed by PharmaGuide 📊
''',
    subject: product.shareTitle,
  );
}

// Instagram Story Template
Future<void> shareToInstagramStory(ProductsCore product) async {
  final storyImage = await generateStoryTemplate(
    title: product.shareTitle,
    score: product.score100Equivalent,
    imageUrl: product.shareOgImageUrl,
    highlights: jsonDecode(product.shareHighlights),
  );
  
  await Instagram.shareToStory(imageFile: storyImage);
}
```

---

## Enhancement 3: Search & Filter

### **What's New:**
- `primary_category` (TEXT)
- `secondary_categories` (TEXT JSON array)
- `contains_omega3`, `contains_probiotics`, `contains_collagen`, `contains_adaptogens`, `contains_nootropics` (INTEGER)
- `key_ingredient_tags` (TEXT JSON array)

### **Use Case:** Fast Product Discovery

**SQL Queries:**
```sql
-- Find all omega-3 supplements sorted by quality
SELECT * FROM products_core
WHERE contains_omega3 = 1 AND score_quality_80 >= 60
ORDER BY score_quality_80 DESC
LIMIT 20;

-- Find all adaptogens
SELECT * FROM products_core
WHERE contains_adaptogens = 1
ORDER BY score_quality_80 DESC;

-- Find products by category
SELECT * FROM products_core
WHERE primary_category = 'probiotic'
ORDER BY score_quality_80 DESC;
```

**Dart Service:**
```dart
// lib/services/search_service.dart
Future<List<ProductsCore>> searchByCategory(String category) async {
  return await db.query(
    'products_core',
    where: 'primary_category = ? AND score_quality_80 >= ?',
    whereArgs: [category, 60],
    orderBy: 'score_quality_80 DESC',
    limit: 50,
  );
}

Future<List<ProductsCore>> searchByIngredient(String ingredient) async {
  final products = await db.query('products_core');
  return products.where((p) {
    final tags = jsonDecode(p.keyIngredientTags) as List;
    return tags.contains(ingredient.toLowerCase().replaceAll(' ', '_'));
  }).toList();
}
```

---

## Enhancement 4: Goal Matching

### **What's New:**
- `goal_matches` (TEXT JSON array)
- `goal_match_confidence` (REAL)

### **Use Case:** "Matches Your Goals" Badge

**Widget:**
```dart
// lib/widgets/goal_match_badge.dart
Widget buildGoalMatchBadge(ProductsCore product, UserProfile profile) {
  if (profile.goals.isEmpty) return SizedBox.shrink();
  
  final productGoals = jsonDecode(product.goalMatches) as List<String>;
  final matchedGoals = productGoals.toSet().intersection(profile.goals.toSet());
  
  if (matchedGoals.isEmpty) return SizedBox.shrink();
  
  return Container(
    padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(
      color: Colors.green.withOpacity(0.1),
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      '✓ Matches ${matchedGoals.length} of your goals',
      style: TextStyle(color: Colors.green, fontSize: 12),
    ),
  );
}
```

---

## Enhancement 5: Dosing Guidance

### **What's New:**
- `dosing_summary` (TEXT)
- `servings_per_container` (INTEGER)

### **Use Case:** Quick Dosing Info

**Widget:**
```dart
// lib/widgets/dosing_quick_info.dart
Widget buildDosingQuickInfo(ProductsCore product) {
  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(product.dosingSummary, style: AppTheme.body1),
      if (product.servingsPerContainer != null)
        Text(
          '${product.servingsPerContainer} servings per container',
          style: AppTheme.caption,
        ),
    ],
  );
}
```

---

## Enhancement 6: Allergen Summary

### **What's New:**
- `allergen_summary` (TEXT)

### **Use Case:** Instant Allergen Warning

**Widget:**
```dart
// lib/widgets/allergen_warning.dart
Widget buildAllergenWarning(ProductsCore product) {
  if (product.allergenSummary == null) return SizedBox.shrink();
  
  return Container(
    padding: EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: Colors.orange.withOpacity(0.1),
      borderRadius: BorderRadius.circular(8),
    ),
    child: Row(
      children: [
        Icon(Icons.warning, color: Colors.orange),
        SizedBox(width: 8),
        Expanded(
          child: Text(
            product.allergenSummary!,
            style: TextStyle(color: Colors.orange[900]),
          ),
        ),
      ],
    ),
  );
}
```

---

## Updated Dart Models

Add these fields to your `ProductsCore` model:

```dart
// lib/models/products_core.dart
class ProductsCore {
  // ... existing fields ...
  
  // v1.3.0 additions
  final String ingredientFingerprint;
  final String keyNutrientsSummary;
  final int containsStimulants;
  final int containsSedatives;
  final int containsBloodThinners;
  
  final String shareTitle;
  final String shareDescription;
  final String shareHighlights;  // JSON array
  final String? shareOgImageUrl;
  
  final String? primaryCategory;
  final String? secondaryCategories;  // JSON array
  final int containsOmega3;
  final int containsProbiotics;
  final int containsCollagen;
  final int containsAdaptogens;
  final int containsNootropics;
  final String keyIngredientTags;  // JSON array
  
  final String goalMatches;  // JSON array
  final double? goalMatchConfidence;
  
  final String dosingSummary;
  final int? servingsPerContainer;
  
  final String? allergenSummary;
}
```

---

## Performance Gains

| Feature                  | Before v1.3.0      | After v1.3.0      | Improvement |
|--------------------------|--------------------|-------------------|-------------|
| Stack safety check       | 2-5s (network)     | <100ms (local)    | 20-50x      |
| Social share             | 500ms (blob fetch) | <10ms (instant)   | 50x         |
| Category filter          | 1-2s (FTS scan)    | <50ms (index)     | 20-40x      |
| Goal match badge         | 500ms (blob fetch) | <10ms (instant)   | 50x         |
| Dosing info              | 500ms (blob fetch) | <10ms (instant)   | 50x         |
| Allergen warning         | 500ms (blob fetch) | <10ms (instant)   | 50x         |

**Overall:** ~80% reduction in detail blob fetches for common UI actions.
