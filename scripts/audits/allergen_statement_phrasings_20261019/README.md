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
- `gluten_free_validated` is lost on 180 products: 35 whose new facility statement names wheat,
  and 145 whose new warnings name only other allergens. Those 145 are PR #187's defect
  (`gluten_contradiction = has_may_contain`) and do not occur once #187 merges.

Tests: `scripts/tests/test_allergen_statement_phrasings.py` (corpus strings, positives fail on main;
negated controls "facility free from", "not manufactured with", "does not process", "peanut-free
facility").
