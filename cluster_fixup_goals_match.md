We need to tighten the **goal-matching contract** so goal fit is computed reliably in pipeline and Flutter only consumes the result.

## Source files and contracts

### Pipeline source of truth

- File: `scripts/data/user_goals_to_clusters.json`
- Current top-level key: `user_goal_mappings`
- Current consumer in pipeline: `scripts/build_final_db.py` → `compute_goal_matches()`
- Current exported DB fields:
  - `goal_matches` (`TEXT`, JSON array of goal IDs)
  - `goal_match_confidence` (`REAL`, 0.0–1.0)

### Flutter consumer

- Bundled asset path: `assets/reference_data/user_goals_to_clusters.json`
- Flutter DB fields already exist in `products_core`:
  - `goal_matches`
  - `goal_match_confidence`

## Goal

Move goal matching to **pipeline-first** logic.

Flutter should not be deciding whether a product supports a user goal beyond a simple intersection:

```text
selected_user_goals ∩ product.goal_matches
```

## Required changes

### 1. Update `scripts/data/user_goals_to_clusters.json`

Keep the filename and top-level key `user_goal_mappings`, but simplify each goal entry to this ship-ready contract:

```json
{
  "_metadata": {
    "description": "User goal to product-cluster matching rules",
    "purpose": "goal_matching",
    "schema_version": "6.0.0",
    "last_updated": "2026-04-23",
    "total_entries": 18
  },
  "user_goal_mappings": [
    {
      "id": "GOAL_SLEEP_QUALITY",
      "user_facing_goal": "Sleep Quality",
      "cluster_weights": {
        "sleep_stack": 1.0,
        "magnesium_nervous_system": 0.8,
        "stress_resilience": 0.4
      },
      "required_clusters": ["sleep_stack"],
      "blocked_by_clusters": ["pre_workout_energy", "focus_attention_support"],
      "min_match_score": 0.45
    }
  ]
}
```

### 2. Keep only these per-goal fields

- `id`
- `user_facing_goal`
- `cluster_weights`
- `required_clusters`
- `blocked_by_clusters`
- `min_match_score`

### 3. Drop these fields from the matching contract

These are not needed for launch goal matching:

- `goal_category`
- `goal_priority`
- `core_clusters`
- `anti_clusters`
- `cluster_limits`
- `confidence_threshold`
- `conflicting_goals`
- `synergy_goals`

If we still want onboarding metadata later, put it in a separate file, not in the matching contract.

## Matching behavior in enrichment

### Product input

Goal matching should use the product’s enriched cluster list, i.e. the same cluster set already produced from synergy/ingredient enrichment:

```json
{
  "clusters_matched": ["sleep_stack", "magnesium_nervous_system"]
}
```

### Matching algorithm

For each goal in `user_goal_mappings`:

1. Read product cluster IDs
2. Deduplicate cluster IDs
3. If any `blocked_by_clusters` is present → no match
4. If `required_clusters` is non-empty and none are present → no match
5. Compute:

```text
matched_weight = sum(cluster_weights[c] for matched clusters)
max_weight = sum(all cluster_weights values)
score = matched_weight / max_weight
```

6. If `score >= min_match_score` → include goal in `goal_matches`
7. Track confidence score for matched goals

### Output rules

- `goal_matches`: JSON array of matched goal IDs
- `goal_match_confidence`: best or average matched score, rounded to 2 decimals

Recommended:

- `goal_matches`: all matched goal IDs
- `goal_match_confidence`: average score across matched goals

## Required final DB output

Keep these fields in `products_core`:

- `goal_matches TEXT` → JSON array of goal IDs, e.g.

```json
examples: correct ID down below
["GOAL_SLEEP_QUALITY", "GOAL_BLOOD_SUGAR_SUPPORT"]
```

- `goal_match_confidence REAL` → e.g. `0.78`

Optional but useful for debugging/explainer:

- retain product clusters in blob/detail output if already present as `product_clusters`, but this is not required for Flutter matching logic

## What Flutter will expect

### Primary expectation

Flutter will treat pipeline output as source of truth:

- read product `goal_matches`
- read user selected goals from profile
- compute intersection only

### Display behavior

If user selected:examples:

```json
["GOAL_SLEEP_QUALITY", "GOAL_BLOOD_SUGAR_SUPPORT"]
```

And product row has:

```json
["GOAL_SLEEP_QUALITY"]
```

Flutter should show:

- matched selected goal: `Sleep Quality`
- unmatched selected goal: not shown as matched

### Flutter should not need to recompute goal matching

Local fallback logic from `product_clusters` should be considered legacy/fallback only. The intended product contract is:

- pipeline computes matches
- Flutter consumes matches

## Important implementation note

Current `compute_goal_matches()` in `scripts/build_final_db.py` is too simplistic:

- it only uses `cluster_weights`
- it ignores required/blocked logic
- it uses a hardcoded threshold

Please update it to honor:

- `required_clusters`
- `blocked_by_clusters`
- `min_match_score`

## Validation updates needed

Please update pipeline integrity tests for the new schema:

- `scripts/tests/test_goal_mapping_integrity.py`
- `scripts/db_integrity_sanity_check.py`

New required fields per goal:

- `id`
- `user_facing_goal`
- `cluster_weights`
- `required_clusters`
- `blocked_by_clusters`
- `min_match_score`

Validation rules:

- `cluster_weights` must be non-empty
- cluster weight values must be numeric `0.0..1.0`
- all cluster keys must exist in `synergy_cluster.json`
- `required_clusters` and `blocked_by_clusters` must reference valid cluster IDs
- `min_match_score` must be numeric `> 0` and `<= 1`

## Example

### Goal rule

```json
{
  "id": "GOAL_SLEEP_QUALITY",
  "user_facing_goal": "Sleep Quality",
  "cluster_weights": {
    "sleep_stack": 1.0,
    "magnesium_nervous_system": 0.8,
    "stress_resilience": 0.4
  },
  "required_clusters": ["sleep_stack"],
  "blocked_by_clusters": ["pre_workout_energy"],
  "min_match_score": 0.45
}
```

### example Product clusters

```json
["sleep_stack", "GOAL_EYE_VISION_HEALTH"]
```

### Score

```text
matched_weight = 1.8
max_weight = 2.2
score = 0.82
```

### Exported result

```json
{
  "goal_matches": ["GOAL_SLEEP_QUALITY"],
  "goal_match_confidence": 0.82
}
```

## Final direction

Please make `user_goals_to_clusters.json` a **pipeline-owned matching contract**, not a Flutter-authored logic file.

Flutter will consume:

- bundled `assets/reference_data/user_goals_to_clusters.json` for labels/reference
- `goal_matches`
- `goal_match_confidence`

The final product contract should be:

- enrichment derives product clusters
- pipeline computes goal matches
- final DB stores goal matches
- Flutter only filters matched goals against the user’s selected goals

Use the Flutter app IDs as canonical:
So the pipeline goal file and final DB output should use exactly these 18 Flutter IDs:

GOAL_SLEEP_QUALITY
GOAL_REDUCE_STRESS_ANXIETY
GOAL_INCREASE_ENERGY
GOAL_DIGESTIVE_HEALTH
GOAL_WEIGHT_MANAGEMENT
GOAL_CARDIOVASCULAR_HEART_HEALTH
GOAL_HEALTHY_AGING_LONGEVITY
GOAL_BLOOD_SUGAR_SUPPORT
GOAL_IMMUNE_SUPPORT
GOAL_FOCUS_MENTAL_CLARITY
GOAL_MOOD_EMOTIONAL_WELLNESS
GOAL_MUSCLE_GROWTH_RECOVERY
GOAL_JOINT_BONE_MOBILITY
GOAL_SKIN_HAIR_NAILS
GOAL_LIVER_DETOX
GOAL_PRENATAL_PREGNANCY
GOAL_HORMONAL_BALANCE
GOAL_EYE_VISION_HEALTH

Recommendation
Before pipeline team updates enrichment:
align scripts/data/user_goals_to_clusters.json IDs to the Flutter IDs

then
turn this into a tighter engineering ticket format with:

- scope
- acceptance criteria
- sample payloads
- regression checklist.
- best practice
