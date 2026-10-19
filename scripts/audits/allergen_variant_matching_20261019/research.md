# Allergen ingredient-variant matching — receipts (2026-10-19)

## Defect

`enrich_supplements_v3.py::_check_allergens` (the owner of shipped `allergen_hits`, blob
`allergens` and `allergen_summary`) flagged an ingredient row only when its whole name or
`standardName` equalled an allergens.json alias. Rows that name the source with any other wording
("Whey Protein Isolate", "Purified Deep Sea Fish Oil", "Soy Protein Isolate", "Omega-3 Fatty
Acids" with form "Fish Oil", "Glucosamine Sulfate" with form "Shellfish") shipped no allergen flag
unless the label also carried a "Contains" statement. The cleaner's allergen check is also exact,
but it decides lookup identity, not the shipped flag, and is unchanged.

The ALLERGEN_FISH note said fish oil, cod liver oil, salmon oil and marine collagen "are flagged via
the enricher's allergen cross-reference". No such cross-reference exists (no IQM allergen field; `rg`
finds no code). The note is corrected.

## Measurement (completed 2026-10-19 corpus run artifacts, 15,426 enriched products)

- Rows whose name or standardName contains an alias as words with no hit for that allergen:
  877 rows / 706 products (`impact.py`).
- Proposed rule (name + forms, whole-word, vetoes; standardName excluded): 640 new hits in 593
  products — fish 287, sesame 127, soy 81, barley 54, wheat 29, milk 23, oats 20, molluscs 6, rye 5
  (before the pollen veto), crustaceans 4, celery 2, mustard 1, tree nuts 1. Every distinct new
  (allergen, row name) pair was read; all name the allergen source in the row name or a form.
  Those that are not a real source (rye pollen, wheat polyols, coconut cream) were then vetoed.
- `standardName` is not evidence: the cleaner gives algal omega-3 rows the `fish_oil` identity
  (293409 NutraVege Plant-Based Omega-3, 305211 Vegan Omega-3 Algae Oil form "Algal Oil
  Concentrate", 278454/323711 Essential for Women/Men). Matching it would have put a false fish flag
  on vegan products.
- 42683 / 43191 Nordic Naturals "Algae Omega" are flagged fish because the raw DSLD row itself
  says "Total Omega-3s (Form: from Norwegian Fish Oil)" with form "Fish Oil" while the statements
  say "Certified by the American Vegetarian Association". That is a source transcription error:
  label-correction candidates, not a matcher exception.

## Source

FDA, *Questions and Answers Regarding Food Allergens, Including the Food Allergen Labeling
Requirements of the FD&C Act (Edition 5): Guidance for Industry*, https://www.fda.gov/media/117410/download
(read 2026-10-19):
- B.6–B.8: labeling applies to an ingredient that is or contains protein from a major allergen;
  derived ingredients with residual protein are covered (lactose, ghee).
- D.9: highly refined oils ("refined, bleached, deodorized") derived from major allergens are exempt
  from section 403(w); an oil that is not highly refined must declare its source.
- B.9: molluscan shellfish are not FDA major allergens (the DB keeps them as EU Annex II).
- B.10: "fish" includes cartilaginous fish such as shark.

Existing curated policy already flags allergen-derived oils and extracts (aliases soybean oil,
almond/walnut/hazelnut/macadamia oil, peanut oil, sesame oil, wheat germ oil, mustard seed oil,
"marine fish oil", soybean extract, soy lecithin). The batch applies that policy to row wording; it
adds no new clinical rule.

## Entries (allergens.json `match_rules.negative_match_terms`)

| Entry | Terms | Evidence | Verdict |
|---|---|---|---|
| ALLERGEN_MILK | milk thistle, coconut milk, coconut cream, dairy digestive, biocore dairy | Silybum marianum (botanical; silymarin/silybin rows carry form "Milk Thistle"); coconut milk/cream are plant products (10 corpus "Coconut Cream" rows, alias "cream"); "Dairy Digestive Enzymes"/"BioCore Dairy" are enzyme blends for digesting dairy | veto |
| ALLERGEN_TREE_NUTS | horse chestnut, tropical almond, almond mushroom, highly refined | Aesculus hippocastanum; Terminalia (chebula/catappa); Agaricus blazei; D.9 | veto |
| ALLERGEN_WHEAT | gluten enzyme, mannitol, xylitol, highly refined | "Gluten Enzyme Blend" digests gluten; mannitol/xylitol "from wheat" are protein-free polyols (B.8; 4 products); D.9 (wheat germ oil) | veto |
| ALLERGEN_RYE | rye flower, pollen | Rye flower/Graminex pollen extracts (Secale cereale pollen), not the grain | veto |
| ALLERGEN_MUSTARD | mustard greens | Brassica juncea leaf vegetable, not seed | veto |
| ALLERGEN_FISH, SOY, PEANUTS, SESAME | highly refined | D.9 | veto |

Not vetoed (flagged, existing policy): molluscs and mustard/celery are EU Annex II, where D.9 does
not apply; "refined soybean oil" (3 rows) is not labelled highly refined; dextrin labelled "from wheat"
follows the wheat dextrin alias.

Rows vetoed by the batch in the corpus: milk 214 (milk thistle family, coconut milk, enzyme
blends), tree nuts 28, rye 2 + 5 Graminex pollen rows, mustard 2, wheat 1 + 4 polyol rows, fish 2 ("highly refined fish
oil"). The simulation ran before the rye pollen veto; the replay below is the measured result.

## Replay (measured) — `~/pg_quality/allergen_variants_20261019/`

`replay.py freeze-raw` 1,292 labels: the 592 simulated-affected products with a raw label (manual
submission PG_SUB_F580FBD60E574699B47D0982663F17DD has none) plus 700 seeded controls from PR #176's
route cohort. `snapshot --full --blob` base origin/main fd51b5828 vs candidate 75ed731d8; then an
8-product replay for the later vetoes (base vs 90dfc3931, and 75ed731d8 vs 90dfc3931). None of the 10
coconut-cream products is in the cohort.

- At 75ed731d8: 639 records changed; 0 allergen hits lost; 587 products gain an allergen. At the
  final 90dfc3931 the 4 polyol products are unchanged, so 635 records / 583 products: fish 286,
  sesame 127, soy 81, barley 54, wheat 25, milk 23, oats 20, molluscs 6, crustaceans 4, celery 2, tree nuts 1,
  mustard 1. Rye 0 (pollen vetoed).
- 52 further records change only the fish hit's `notes` (corrected note text).
- Blob: new `allergens[]` rows and B2 "Declared allergen source" penalty labels; 107 records keep
  an extra allergen-bearing ingredient row in `blob.ingredients` (export keeps any row matching an
  allergen hit: `build_final_db._active_row_allowed_for_primary_export`). 19 of those swap the kept
  wheat evidence row from "organic Kamut Grass" to the earlier "organic Wheat Grass" (one hit per
  allergen id); the wheat flag itself is unchanged.
- No change to product_status, product_status_detail, quality_assessment_status, v4_safety_gate or
  product_safety_status; no route change; no tier change at 90dfc3931.
- Scores: 12 products move -2 to -3 (Transparency B2 false allergen-free claim, existing scorer
  policy: a gluten-free claim conflicts with a detected wheat/barley source): 8 wheatgrass powders
  (alias "wheat grass"), wheat dextrin 12077, malt syrup 243030, barley powder 216759, malt diastase
  82943. The 4 polyol products (267603, 268386, 268506, 273839), which also lost a tier at
  75ed731d8, are byte-identical to base at 90dfc3931.

Open for Sean (not changed here): 21 CFR 101.91 lets a food carry "gluten-free" with an ingredient
derived from a gluten-containing grain processed to remove gluten, or under 20 ppm (wheatgrass is
FDA's own example). The B2 conflict treats any wheat/barley source as falsifying the claim.
