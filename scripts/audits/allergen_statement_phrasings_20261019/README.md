# Allergen statement phrasings (2026-10-19)

**Defect.** `enrich_supplements_v3._parse_allergen_statement` read "Contains…", "May contain…" and
three fixed facility sentences. Corpus census (statements of 15,426 enriched products): about 200
products state "Allergen information: Fish, Soy" / "Allergy information: soy" / "Allergens:
milk.", and about 250 use other facility or shared-equipment wording ("Processed in a facility with
products that contain egg, fish, shellfish, soy and tree nuts.", "Manufactured on equipment which
processes dairy."), all with no allergen flag. Within one statement, lines were not separate
clauses, so "No added sugar" swallowed "This product contains whey protein isolate" on the next line
(328850); a declaration after a negator in the same clause ("Contains no artificial colors,
contains soy") was dropped. Only 3 corpus statements have that same-clause shape. Sentence-separated
cases ("Free of gluten and wheat. Contains milk.") already parsed correctly on main.

**Fix.**
- "Allergen(s)/allergy information:" and "Allergens:" list what the product contains.
- Any facility, equipment or production-line clause not matched by the fixed patterns names
  cross-contact sources after the cue word (`facility_warning`, phrase match with the
  allergens.json vetoes and the negation guard).
- Lines and tabs split clauses.
- A declaration after a negator is parsed on its own.
- "This/the product contains" is declaration-shaped.
- "not manufactured/made/processed/produced with" and "does not process/handle/use" are negators.

**Corpus re-check** (`_check_allergens`, main 625e90425 vs a7d812080): 297 products gain 1,181
hits (soy 232, crustaceans 208, eggs 203, fish 200, tree nuts 137, peanuts 75, wheat 69, milk 49,
sesame 8); 0 hits lost. All 55 distinct gained facility statements and 7 "Allergen information"
lines were read: each is a cross-contact or allergen declaration on the label.

**Replay** (`~/pg_quality/allergen_phrasings_20261019/`): `freeze-raw` 596 labels (296 affected,
300 seeded controls), `--full --blob`, main vs a7d812080.
- 300 records change; 1,172 hits gained, 0 lost; 0 status changes.
- 4 controls keep their allergen, whose source moves from an ingredient row to the label's own
  "Allergen information:" line.
- 174 products drop 1.2–3.1 points, all through the existing Transparency B2 rule: a free-from or
  allergen-free claim conflicts with a may-contain or facility warning
  (`generic_transparency._score_b2_false_allergen_claim_penalty`). 36 change tier (Very good → Good
  25, Good → Needs improvement 9, Exceptional → Excellent 1, Excellent → Very good 1).
- `gluten_free_validated` is lost on 180 products. 37 are real: 35 whose new facility statement
  names wheat, plus 294321 and 294322, whose new "Allergen Information: Wheat" line declares wheat.
  The other 143 have new warnings that name only other allergens: PR #187's defect
  (`gluten_contradiction = has_may_contain`), which does not occur once #187 merges.

Tests: `scripts/tests/test_allergen_statement_phrasings.py` (corpus strings, positives fail on main;
negated controls "facility free from", "not manufactured with", "does not process", "peanut-free
facility").

## Audit follow-up (7f413ce9a)

- F1: a statement line starts a new clause only when it opens with a new cue (contains, may
  contain, allergen information, a facility verb, "this product", a negator); any other line
  continues the list above it ("Contains:\nMilk, Soy", "Contains milk\tsoy", 287762
  "Contains:\r\nMilk.").
- F2: "which/that contain(s)" after a negator stays in the negated phrase ("Free of dairy, which
  contains lactose").
- F3: an "Allergen information:" line led by no/none/free is negated; one with a facility or
  equipment cue is read as a facility warning, not "contains".
- F4: per-allergen precedence is contains > ingredient_list > may_contain > facility_warning, so a
  real ingredient is never relabelled as cross-contact (76850 peanuts, 316791 soybean oil, 27807
  wheat grass).
- F5: `build_final_db.export_allergen_presence` maps enrichment presence to the app vocabulary
  (`ingredient_list` → `contains`, `facility_warning` → `manufactured_in_facility`), documented in
  FINAL_EXPORT_SCHEMA_V1.md; `allergen_summary`, blob `allergens[]` and the B2 card use it, so a
  facility hit is never "Contains:". No app change is needed: the app already knows these three
  values.
- F6: export allergen-row matching is whole-word (70066 "organic Buckwheat", 78327 "Pea").
- Probe: a facility clause must name something processed ("Our facility tests every lot for
  gluten" names no source).

## Replay after #187 merged (main 53e186ced vs 36687dd00)

`~/pg_quality/lucidbanach_pr188_20261020/`: the same 596 frozen labels (296 affected, 300 controls),
`--full --blob`. With #187's per-group rule on main, a new warning contradicts only a claim of its
own group.
- 333 records change; 1,172 allergen ids gained (soy 231, crustaceans 207, eggs 202, fish 199,
  tree nuts 136, peanuts 74, wheat 68, milk 48, sesame 7), 0 lost; 0 status changes. Presence:
  1,122 new `facility_warning`, 50 new `contains`, 9 `ingredient_list` → `contains` (the label's own
  allergen line).
- 37 controls change: 33 only through the F5 export vocabulary (blob `allergens[]` and
  `score_penalties` read `contains` for an ingredient hit), 4 whose hit source moves to the label's
  allergen line. No control score moves.
- **59 products drop 1.2–3.1 points** (−2.0 ×34, −3.0 ×17, −3.1 ×4, −2.7 ×2, −1.4, −1.2), down from
  174 before #187; 5 change tier (Very good → Good 4, Good → Needs improvement 1). Every one is B2
  with a matched own-group contradiction. Matched groups: gluten 21, soy 11, gluten + soy 10,
  dairy 6, dairy + soy 2, dairy + gluten 1, dairy + gluten + soy 1, egg + soy 1, egg + soy +
  tree nut 3, tree nut 3 (= 59). Per product with claimed and matched groups:
  `per_product_deltas.csv`.
- **3 of the 59 are false:** 75073 (−3.0), 206267 and 69313 (−2.7) say "No dairy, no peanuts,
  gluten free" and match `tree_nut` against a tree-nut facility statement. The `nut` claim pattern
  (`constants.py`) has no word boundary, so "peanuts" also claims tree-nut-free. That is the
  queued claim-regex fix, which restores them.
- Gluten-Free badge (compliance `gluten_free` → core `is_gluten_free`) cleared on 37, all real: 35
  whose new facility statement names wheat, plus 294321 and 294322 ("Allergen Information: Wheat").
  The 143 non-gluten losses measured before #187 no longer occur.
