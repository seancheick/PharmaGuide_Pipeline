# Fish species and krill as allergen phrase terms — receipts (2026-10-19)

Follow-up to PR #182 (allergen variant matching), requested by the #182 audit.

## Defect

FDA requires labels to declare the fish or crustacean **species**, not the word "fish": allergen Q&A
Ed. 5 C.5 ("cannot broadly declare … 'fish'"), C.6 (species = an acceptable market or common name
from FDA's Seafood List) and D.4 ("gelatin (cod, haddock, pollock)"). allergens.json deliberately
keeps species out of `aliases`, because the cleaner's identity lookup reads aliases (allergen tier
before IQM) and "Cod Liver Oil" must stay `cod_liver_oil`. So on main these shipped no fish or
crustacean flag unless another text named "fish":

- rows: purified Arctic Cod Liver Oil (28705 and others), Gelatin with forms Cod/Cusk/Flounder/
  Haddock/Hake/Pollock/Sole (8719), Docosahexaenoic Acid with form Tuna (56163), Shark Cartilage,
  Krill Oil;
- statements: "Contains: Sardines, anchovies, soy", "CONTAINS: Crustaceans (Krill)." (statement
  parts matched only exact aliases; "crustaceans" is plural).

## Mechanism

`match_rules.phrase_match_terms` (new; GLOSSARY "Allergen phrase match terms") joins the enricher's
whole-word phrase pattern only. The cleaner never reads it (pinned by
`test_species_terms_are_not_identity_aliases_in_the_cleaner`). Statement parts fall back to the
same phrase match only when the clause opens with the declaration ("Contains…", "May contain…",
optionally after "Allergens:") or is a facility list; prose such as "krill oil contains astaxanthin,
which is not seen in standard fish oil" stays exact-only. Statement negation now also covers
"contains none of" and "doesn't/do not contain".

## Entries

| Entry | phrase_match_terms | Source | Verdict |
|---|---|---|---|
| ALLERGEN_FISH | cod, flounder, mackerel, salmon, shark, tilapia, trout, tuna, grouper | FDA Q&A B.10 examples of bony and cartilaginous fish | add |
| ALLERGEN_FISH | cusk, haddock, hake, pollock, sole, herring, dogfish, anchovy/anchovies, sardine/sardines | FDA Seafood List (read 2026-10-19), Type V: Cusk *Brosme brosme*; Haddock *Melanogrammus aeglefinus*; Hake *Urophycis* spp.; Pollock *Pollachius virens*, *Gadus chalcogrammus*; Sole *Austroglossus* spp.; Herring *Harengula*, *Ilisha* spp.; Dogfish Shark *Squalus* spp.; Anchovy *Engraulis* spp.; Sardine *Sardina pilchardus*, *Sardinops* spp. Each name occurs on corpus labels. | add |
| ALLERGEN_CRUSTACEANS | krill, crustaceans | FDA Seafood List: Krill, *Euphausia* spp., Type I(C) (crustacean); "crustaceans" is the plural on Contains statements | add |

Not added: bass, ray, skate (ambiguous English words); menhaden, pilchard (no corpus row needs
them; "menhaden" statements already name other species). "highly refined" (D.9) still vetoes fish:
"Highly Refined Marine Oil Concentrate" with anchovy/herring/mackerel/sardine forms (328645) and
"highly refined Shark Liver Oil" stay unflagged. Shark cartilage is flagged: sharks are fish (B.10).

## Corpus re-check (`_check_allergens` over 15,426 enriched products, main 941d273d3 vs e8f45ac4d)

- 101 products gain an allergen: fish 47 (42 ingredient rows: cod liver oil, shark cartilage,
  gelatin, DHA from tuna; plus statements "contains tilapia.", "Contains herring, mackerel, menhaden,
  sardines and soy.", "may contain … pelagic wild sardine", a facility "fish extracts"), crustaceans
  18 (krill oil rows; "Contains: Krill", "Crustaceans (Krill)"; facility lists naming shellfish),
  milk 23 (facility/may-contain statements), soy 8, eggs 5, wheat 2, oats 1, tree nuts 2 ("Contains:
  Tree nuts (coconut)"), peanuts 1, molluscs 1 (squid), sulfites 1. Every gained statement is a
  declaration that names the allergen.
- 6 hits removed, all false: wheat from "Contains none of the following: … wheat" (182545, 218073,
  218139) and soy from "Macros doesn't contains soy" (220125, 220132, 220137). On 218073 and 182545
  milk changes from that false "contains" to the label's real facility statement.
- 67 products change only the hit's evidence/presence text.

## Replay (measured) — `~/pg_quality/allergen_species_20261019/`

`replay.py freeze-raw` 506 labels: the 106 affected products with a raw label (manual submission
PG_SUB_C29FA… has none) plus 400 seeded controls from PR #176's route cohort; `snapshot --full
--blob` base origin/main 941d273d3 vs candidate e8f45ac4d.

- 138 records changed: the 106 affected; 31 whose existing fish hit only takes the corrected note;
  297629, whose soy hit moves from its facility statement to its own "may contain traces of soy"
  (higher precedence, same label).
  Allergen ids gained match the corpus re-check exactly (fish 46 without the submission,
  crustaceans 18, milk 23, soy 8, eggs 5, wheat 2, tree nuts 2, oats 1, peanuts 1, molluscs 1,
  sulfites 1); lost: the 6 false wheat/soy flags above. No product_status, product_status_detail,
  quality_assessment_status, v4_safety_gate or product_safety_status change.
- 14 products (all gummies) drop 2–3 points, one tier (304605 Very good → Good). Cause: a newly read
  milk or soy facility/may-contain statement meets the existing Transparency B2 rule that an
  allergen-free claim conflicts with any detected allergen or may-contain warning
  (`generic_transparency._score_b2_false_allergen_claim_penalty`). Expected development movement.
- The same 14 lose `gluten_free_validated`: `enrich_supplements_v3` sets
  `gluten_contradiction = has_may_contain or …`, so a milk facility warning voids a gluten-free
  claim. That coarse rule predates this batch; reported for a separate fix, not changed here.

