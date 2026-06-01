# Batch 6 — 18 new BOTANICAL entries added to rda_therapeutic_dosing.json

All confirmed present in botanical_ingredients.json (so they route through the v4 botanical
adapter and are actually scored) and present in the live _dosing_index(). Every PMID
content-verified via verify_all_citations_content.py (full file: 67 match / 4 mononym partial /
0 mismatch / 0 not_found). Standardization basis encoded in upper_limit_notes (load-bearing).

Tier 1 (meta-analysis / pivotal RCT): Boswellia serrata (18667054, 35512759), Soy Isoflavones
(22433977, 25316502), Vitex agnus-castus (28237870, 31780016), Elderberry (30670267), Grape Seed
Extract (27537554, 34798267), Andrographis paniculata (28783743, 14748896).

Tier 2 (solid RCT-level): Pycnogenol (31585179, 31763928), Cinnamon/Cassia (24019277, 37818728;
coumarin ceiling flagged), Fenugreek (26791805, 36837450), Gymnema (34467577), Saffron (30036891,
20579522; toxicity ceiling), Tongkat Ali (36013514, 23705671), Bergamot (24239156, 30501605),
Olive Leaf (26951205, 40990594), Lemon Balm (15272110), Passionflower (21294203), Sage (18350281,
12895685), Holy Basil/Tulsi (19253862, 26571987).

Excluded on evidence/safety (not added): Tribulus (no testosterone effect), Policosanol (replication
failure), Kava (hepatotox), Black Cohosh (hepatotox + mixed), Turkey Tail/PSK (purified-fraction only),
Echinacea (Cochrane inconclusive). Off-topic candidate PMIDs discarded live by the research agent.
