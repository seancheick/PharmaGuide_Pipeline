# Green tea extract contains EGCG — receipt (2026-10-20)

Batch: `scripts/data/ingredient_quality_map.json` entry `green_tea_extract`; add
`relationships: [{type: contains, target_id: egcg}]`. No form, alias, identifier or score is added. Design decision
("contains", not a standardized_botanicals marker) from the coordinating session: standardized_botanicals has one
`min_threshold` per entry, and green_tea's (50) is for polyphenols; its notes say polyphenol % is not EGCG %, so
scoring % EGCG against it would mix markers.

| Item | Verified by content (2026-10-20) |
|---|---|
| IQM `egcg` target (UNII BQM438CTEL) | GSRS "EPIGALLOCATECHIN GALLATE", chemical; PubChem CID 65064, C22H18O11. |
| Green tea extract contains EGCG | Already recorded by `botanical_marker_contributions.json::green_tea_extract` (delivers egcg; PMID 23950663, "Treatment of symptomatic uterine fibroids with green tea extract: a pilot randomized controlled clinical study", Int J Womens Health 2013, extract standardized to 45% EGCG). GSRS GREEN TEA LEAF lists EGCG metabolites. |

Precedent: IQM turmeric contains curcumin, grape_seed_extract contains opc, ginseng contains ginsenosides,
fenugreek contains 4_hydroxyisoleucine, fish_oil contains epa/dha.

Readers of IQM `relationships` checked: `enrich_supplements_v3._form_token_context` (contains → component; the
intended effect), `_identity_parent_predicate` (category_for only), `inactive_ingredient_resolver` (relationship
targets become parent identity terms; replay shows no change on the 22 labels with EGCG/green tea inactives),
`api_audit/verify_backed_studies_citations` (topic vocabulary; INGR_EPICATECHIN gains the word "epigallo" on 2
claims). No interaction, warning or interaction-subject code reads IQM relationships.
