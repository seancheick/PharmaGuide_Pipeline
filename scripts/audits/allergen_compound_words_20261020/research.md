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

## Replay — `~/pg_quality/lucidbanach_compound_allergens_20261020/r2/`

`freeze-raw` 533 labels (383 above + 150 seeded controls from the #187 cohort), `--full --blob`,
main 3d7fe8adf (after #187 and #188) vs 6b3720ab7. 5 records change; 0 score, tier, status,
Gluten-Free badge or control changes.
- 293243 gains a row-level ALLERGEN_WHEAT (`ingredient_list`, "Wheatgrass"). Its badge is already
  off on main (barley grass ingredient, D30 switch).
- 327405, 327407, 330686 ("Contains: Wheatgrass, sesame."): ALLERGEN_WHEAT now comes from the label's
  own Contains statement (precedence contains > ingredient_list, #188) instead of the "Wheat Grass
  Juice" row.
- 275997: evidence text only ("(from Triticum aestivum)" dropped; the row name now matches first).
- 294319, 294321, 294322 do not change: since #188 their "Allergen Information: Wheat" line already
  flags wheat and wins the per-allergen precedence. The tests run them with that line removed, so the
  row itself must name wheat.

An earlier run against main 0826118d5 (before #188) showed 17 changes, including the badge turning
off on 293243, 294321 and 294322 and B2 −2 on 294321/294322; #187 and #188 now produce those on main.

Tests: `scripts/tests/test_allergen_species_phrases.py` — the four products fail first (no
row-level wheat hit), buckwheat 29105 and ryegrass 232473 controls; allergen slice 2,286 passed.
