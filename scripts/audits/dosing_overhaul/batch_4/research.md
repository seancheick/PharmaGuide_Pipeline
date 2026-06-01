# Batch 4 — remaining non-botanical bioactives migrated to rda_optimal_uls.json

15 entries migrated OUT of rda_therapeutic_dosing.json (inert there) INTO rda_optimal_uls.json
(generic dose path), each with content-verified PMIDs (re-verified via verify_all_citations_content.py
→ 35 match / 2 benign partial (mononym) / 0 mismatch on the full file). rda_ai anchor = effective-dose
lower bound; ul:null/not_determined (no toxicity ULs; prior "upper_limit" were tolerability soft-caps).

| Ingredient | unit | range | anchor | PMIDs | safety note |
|---|---|---|---|---|---|
| Glucosamine Sulfate | mg | 1500 | 1500 | 30566740 | shellfish allergen; glucose monitoring |
| MSM | mg | 1500-6000 | 1500 | 16309928, 18417375 | |
| Hyaluronic Acid (oral) | mg | 80-200 | 80 | 32047830, 37686801 | |
| GABA | mg | 100-200 | 100 | 16971751, 22203366 | WEAK evidence (small trials) |
| Melatonin | mg | 0.5-5 | 0.5 | 38888087, 23691095 | low dose optimal |
| NAC | mg | 600-2400 | 600 | 25957927, 33354859 | nitroglycerin/antiplatelet |
| Ubiquinol | mg | 100-200 | 100 | 32188111, 32326664 | warfarin |
| Magnesium L-Threonate | mg | 1500-2000 | 1500 | 26519439, 39252819 | counts toward 350mg elemental-Mg UL when stacked |
| NMN | mg | 250-900 | 250 | 35479740, 36482258 | FDA supplement-status flag (regulatory) |
| PQQ | mg | 20-40 | 20 | 34415830, 31860387 | |
| SAM-e | mg | 400-1600 | 400 | 38199136, 27727432 | AVOID bipolar; serotonin syndrome |
| Berberine | mg | 900-1500 | 900 | 34956436, 36999891 | CYP3A4/P-gp; pregnancy contraindicated |
| Quercetin | mg | 500-1000 | 500 | 27405810, 35948195 | CYP3A4 |
| DIM | mg | 100-200 | 100 | 32458980, 26501150 | moderate evidence |
| 5-HTP | mg | 150-300 | 150 | 31504850, 12169147 | serotonin syndrome; EMS purity flag |

Plant-isolate decision: Berberine/Quercetin/DIM/5-HTP migrated as compounds (predominantly sold isolated;
not in botanical_ingredients.json). Residual: a rare botanical-tagged source product (e.g. goldenseal→berberine)
would get disclosed_no_reference rather than a band — acceptable minor effect.
Lutein and Probiotics(CFU) retained in therapeutic (documented exceptions). Off-topic PMIDs discarded by
the agent's live efetch check (listed in session log).
