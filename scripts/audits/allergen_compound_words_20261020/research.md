# One-word allergen compounds — receipts (2026-10-20)

Requested by the #189 audit: rows printed "Wheatgrass" as one word (293243, 294319, 294321, 294322)
shipped no ALLERGEN_WHEAT. allergens.json listed only "wheat grass", and the enricher matches whole
words, so the one-word spelling never matched unless the row carried a *Triticum aestivum* form.

## Entry

| Entry | Change | Source | Verdict |
|---|---|---|---|
| ALLERGEN_WHEAT | `match_rules.phrase_match_terms: ["wheatgrass"]` | FDA allergen Q&A Ed. 5 C.9: "wheat" means any species in the genus *Triticum* (fda.gov/media/117410, read 2026-10-20). Wheatgrass is young *Triticum aestivum*: `botanical_ingredients` `wheatgrass_powder` `latin_name`; 311846 prints the form "Triticum aestivum L.". 294319/294321/294322 themselves state "Allergen Information: Wheat". | add |

A phrase term, not an alias: the cleaner's identity lookup reads aliases (allergen tier before IQM)
and #189 just settled wheatgrass identity in `ingredient_quality_map`; phrase terms are enricher-only
(`test_species_terms_are_not_identity_aliases_in_the_cleaner`).

## Sibling scan (raw staging labels, 15,414 files, every string field)

Tokens joining an allergen stem to other letters, then a baseline snapshot of the 383 labels that
carry one (`~/pg_quality/lucidbanach_compound_allergens_20261020/base.jsonl`) to read each row's hits:

- **Missed on main:** only the four one-word "Wheatgrass" rows above.
- **Already flagged via a form, alias or statement:** NovaSoy / SoyLife / Soynatto Fermented
  Soyfood (soy forms), Eggshell Membrane (egg), Lipowheat ("Wheat (Triticum vulgare) oil extract"
  form), Goatein ("Contains: Milk"), redfish and catfish (inside "Contains: Fish (…)").
  Hyphenated compounds (wheat-grass, leucine-whey, shell-fish) already match: a hyphen is a word
  boundary.
- **Names, not ingredients:** Wheybolic, ioWHEY, WheyBasics, EstroSoy (product or trademark names;
  their whey/soy rows flag), Megmilk Snow Brand (company), buttermilk (lactase directions).
- **Must not match, and don't:** buckwheat (*Fagopyrum*; no wheat hit comes from a buckwheat row: 44 buckwheat products carry no wheat hit, the other 58 get it from other rows or statements), perennial
  ryegrass (*Lolium*, not rye *Secale*; 232473's "Rye" form is vetoed by `pollen`).
- **Not in the corpus:** barleygrass, wheatgerm (one word). Not added.

## Replay — `~/pg_quality/lucidbanach_compound_allergens_20261020/`

`freeze-raw` 533 labels (383 above + 150 seeded controls from the #187 cohort), `--full --blob`,
main 0826118d5 vs 52ed30ac7. 17 records change; 0 product_status or product_safety_status changes;
0 controls change.
- 4 gain a row-level ALLERGEN_WHEAT (`ingredient_list`, matched "Wheatgrass"/"Wheatgrass, Powder").
- 3 of them claim gluten-free ("Free from gluten…", "Free of: … gluten") and lose the gluten-free
  badge (compliance `gluten_free` → core `is_gluten_free`, blob `gluten_free_validated`): 293243,
  294321, 294322. 294321 and 294322 drop 54.4 → 51.4 (Transparency B2 −2, gluten-free claim with a
  wheat ingredient; tier stays Poor). This is the same result main already gives two-word
  "Wheat Grass" rows (311846 et al.). Whether a wheatgrass product may carry a gluten-free claim
  is the open 21 CFR 101.91 question for Sean (see PR #187's
  `GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE`).
- 3 ("Contains: Wheatgrass, sesame.") keep ALLERGEN_WHEAT; `matched_text` becomes "wheatgrass".
- 10 keep ALLERGEN_WHEAT; the evidence drops the form suffix ("Ingredient: Wheatgrass, Powder
  (from Triticum aestivum L., Powder)" → "Ingredient: Wheatgrass, Powder") because the row name now
  matches before the form.

Tests: `scripts/tests/test_allergen_species_phrases.py` — the four products fail first (no
row-level wheat hit), buckwheat 29105 and ryegrass 232473 controls; allergen slice 2,286 passed.
