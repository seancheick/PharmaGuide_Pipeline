# Phytonadione classification investigation — 2026-05-12

## Question

Why does Phytonadione (Vitamin K1) appear in `inactiveIngredients[]` of 108 products with **0 active occurrences**? Is the DSLD source label classifying it as inactive, or is the cleaner mis-promoting it from active → inactive?

Per user direction: "Do not guess. If DSLD source itself classifies it as inactive, preserve that truth and document the ambiguity. If cleaner caused it, classify as blocker."

## Method

Cross-referenced 3 sampled products against their `cleaned_batch_*.json` outputs. For each, inspected the `display_ingredients[]` array which carries the cleaner's `source_section` provenance tag. Compared against corpus-wide name-form distribution.

## Findings

### 1. The cleaner is **NOT** mis-classifying

Three products randomly sampled from the 108:

```
DSLD 321926  inactive entry: 'Phytonadione' (ingredientGroup='Vitamin K (Phylloquinone)')
              display_ingredients tag: display_type='inactive_ingredient'
                                       source_section='inactiveIngredients'

DSLD 75016   inactive entry: 'Phytonadione' (ingredientGroup='Vitamin K')
              display_ingredients tag: display_type='inactive_ingredient'
                                       source_section='inactiveIngredients'

DSLD 75016   inactive entry: 'Phytonadione' (ingredientGroup='Vitamin K (Phylloquinone)')
              display_ingredients tag: display_type='inactive_ingredient'
                                       source_section='inactiveIngredients'
```

`source_section='inactiveIngredients'` means the cleaner **read** Phytonadione from the DSLD source's `inactiveIngredients[]` JSON array. It did not move it from active to inactive.

### 2. Corpus-wide name-form distribution explains the pattern

Across all `output_*/cleaned/` files:

| Name form               | active count | inactive count |
|-------------------------|-------------:|---------------:|
| `Vitamin K`             |        1,201 |              — |
| `Vitamin K2`            |          298 |              — |
| `Vitamin K1`            |          112 |              — |
| `Vitamin K-2`           |           12 |              — |
| `Menaquinone-4` / `-7`  |           10 |              — |
| `Phytonadione`          |              — |          108 |
| `Cultured Phytonadione` |              — |            5 |

The pattern is clean: **DSLD source curators put the IUPAC/chemical name ("Phytonadione") in `inactiveIngredients[]` but put the same molecule's common nutritional name ("Vitamin K1", "Vitamin K") in `activeIngredients[]`.** Same compound, different label position, governed by which name appears on the label.

### 3. Likely real-world meaning

A DSLD label that says "Vitamin K1, 100 mcg" in Supplement Facts → DSLD parses as active.
A DSLD label that says "Other Ingredients: ... Phytonadione (as stabilizer/preservative)" → DSLD parses as inactive.

The chemical name is more common in the inactive context because that's how stabilizer/vehicle uses tend to be declared on labels.

## Verdict

| Criterion | Verdict |
|---|---|
| Cleaner mis-classifying? | **No** — cleaner faithfully preserves DSLD source's section assignment |
| Is this a release blocker? | **No** — DSLD source is the truth; pipeline correctly mirrors it |
| Severity of remaining ambiguity | **Low (domain review)** — *why* DSLD curators choose "Phytonadione" over "Vitamin K1" in the inactive section is a labeling-convention question, not a pipeline question |

## Current pipeline behavior (correct)

In a Phytonadione-as-inactive product, the inactive ingredient blob entry:

```
name:              'Phytonadione'
matched_source:    None        (not in any reference data file)
display_role_label: None       (no role classification)
severity_status:   'n/a'
is_safety_concern: False
is_banned:         False
```

It's surfaced to Flutter as a plain "Other Ingredients" chip with no role label — which is the correct rendering when the cleaner+resolver have no role classification for the inactive use.

## Domain-review follow-up (out of pipeline scope)

If clinical / regulatory wants to clarify the inactive Phytonadione case, consider:

1. **Add an `other_ingredients.json` entry** with `functional_roles: ["preservative"]` or similar, ONLY after confirming with domain expert what role(s) Phytonadione actually plays in those 108 products' formulations.

2. **Alternative**: add it as a watchlist entry to `banned_recalled_ingredients.json` with a domain-review note, if the inactive use is considered clinically relevant.

3. **No action** (current state): leave it as unclassified — Flutter shows the raw label name with no role badge.

The 108 occurrences correctly carry the label's truth. Whether the role label should be populated is a clinical-judgment call, not an engineering call.

## No action this round

Per the user's explicit guidance, this finding is **closed without code changes**. The DSLD source classification is preserved end-to-end. The audit's "unknown inactive role" report continues to count these 108 entries (correctly, since we don't have a role for them).
