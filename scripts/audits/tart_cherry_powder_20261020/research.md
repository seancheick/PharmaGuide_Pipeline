# Tart cherry powder aliases — receipts (2026-10-20)

Batch: `scripts/data/ingredient_quality_map.json` entry `tart_cherry`; four aliases move from form
'tart cherry extract' (bio 6) to 'tart cherry (unspecified)' (bio 5). No form, alias text, identifier or
bio_score is added. Decision (A) from the coordinating session, applying the whole-powder rule of
6d7d535d0.

Why the aliases matched nothing: `enrich_supplements_v3.py::_match_quality_map_impl.add_candidate` drops
any candidate whose form name contains "extract" when the label says powder/dried and not extract
(6d7d535d0, 2026-10-12, "Preserve whole powder identities without invented extract form credit").
A matcher bisect on main: every powder alias of the extract form returned no match; the extract and
concentrate aliases matched; "Prunus cerasus, Powder" (unspecified form) matched.

| Alias | Added | Verdict | Receipt |
|---|---|---|---|
| sour cherry, powder | 654e5034a (2026-09-27, "same substance") | move to unspecified | Sour cherry = Prunus cerasus = tart cherry (botanical_ingredients `tart_cherry_fruit`, UNII 1L29G6428X, GSRS "SOUR CHERRY"; IQM tart_cherry unspecified already lists "sour cherry"). A powder is not an extract. The same commit filed "Prunus cerasus, Powder" under the unspecified form. |
| tart cherry powder | 77cefe17a (2026-04-15) | move to unspecified | Whole-material powder of the same species; no preparation that would make it an extract. |
| tart cherry fruit powder | 77cefe17a | move to unspecified | As above (fruit powder). |
| cherrypure tart cherry fruit & skin powder | 77cefe17a | move to unspecified | CherryPURE (trademark of Shoreline Fruit, LLC) is described by distributor and supplier listings as a freeze-dried, carrier-free powder from Montmorency tart cherry skins, with no drying aids, 100+ lb fresh cherries per kg (web search 2026-10-20; knowde.com Anderson Advanced Ingredients "CherryPURE Organic Tart Cherry Powder", nxtingredients.com). One supplier sentence also calls it "the extract". It is not established as a solvent extract or as standardized, so the unspecified form is the reading that credits nothing unproven. |

Left unchanged: "cherrypure tart cherry" stays on the extract form (no powder word, so the guard does not block it; out of scope).

Siblings (same dead-alias class, queued, not changed): 30 more aliases with "powder"/"dried" and no "extract",
filed on 17 other parents' "...extract" forms: stinging_nettle, grape_seed_extract, turmeric, garlic, bilberry,
deer_antler_velvet, chamomile, olive_leaf, rose_hips, cinnamon, common_bean_extract, corn_silk, amla,
guggul, bile_extract, coffee_fruit, soybean. Each needs its own preparation judgment: for example,
"curcuminoid powder" under 'turmeric extract (95% curcuminoids)' may really name the extract.

Display follow-up for Sean (text unchanged): the unspecified consumer note says the listing does not say
"whether it is whole fruit, juice concentrate, powder, or a standardized extract". On a label that prints
"powder", that is imprecise. "Prunus cerasus, Powder" already shows it.
