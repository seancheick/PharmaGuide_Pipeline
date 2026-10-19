# Identity straight line — receipts (October 19, 2026)

Branch `claude/upbeat-montalcini-ef2f53`. Findings F1/F2/F4 of the line integrity audit
(`reports/line_integrity_audit_20261019/README.md` in the main checkout). Measurement script:
`measure_rewrites.py` (this folder). Data patch: `alias_batch.py` (this folder).

## Step 1 — what the enricher's rewrites are (951a05415 full capture, 15,414 labels)

A rewrite is an `ingredient_quality_data` row whose `canonical_id_before` differs from its final
`canonical_id`. `identity_decision_reason` on those rows mostly carries the row's skip reason
(`nested_under_non_therapeutic_parent`, `blend_header_total_weight_only`), not the identity
decision, so rewrites are classified here by the decision's own rationale and by evidence.

| Decision path (rationale) | Rows | Blend children | Scoreable | Row interaction rules change | Verdict |
|---|---:|---:|---:|---:|---|
| DSLD ingredientGroup replaced the supplied id; label is an exact curated alias of the supplied id, not of the group's | 2,311 | ~1,600 | 467 | 139 | **Defect** (wrong plant/species/part/preparation), except where the group says "Proprietary Blend" (row role) or the alias itself is wrong (see data batch) |
| same, label names the group's identity | 130 | — | 128 | 100 | Intended repair (e.g. "Vitamin E" first matched to sunflower oil; "Biotin" to brewer's yeast) |
| same, label resolves to neither | 508 | — | 155 | 25 | Mixed: group right ("Charcoal, Activated", "Strawberry powder") and wrong ("Tapioca"→corn starch, "Ginger rhizome extract"→ginger). Needs curated aliases, not a rule. Follow-up |
| Non-scorable row, no identity inferred (canonical dropped to none) | 2,039 | 1,457 | 0 | 225 | Intended honest unresolved, except 201 rows whose label is an exact curated alias of the supplied id (e.g. "Raw organic Svetol") → **defect**, retained now |
| Botanical source retained, marker secondary metadata | 345 | 52 | 0 | 14 | Intended part/registry refinement (cranberry→cranberry_fruit, "Star Anise extract"→star_anise) |
| Later re-stamp after a clean decision (relocation/botanical paths) | 236 | 54 | 0 | 82 | Mostly correct repairs ("Catuaba", "Cassia Seed Extract", "Shark Cartilage", DGL); reishi→generic mushroom record noted as follow-up |
| Other (registered parent/child, microbial preparation) | 51 | — | 12 | 24 | Intended |

Allergen and banned/harmful flags: not affected by IQD identity. `_collect_contaminant_data`
reads `product['activeIngredients']` / `inactiveIngredients` (cleaner rows, names), not the IQD
rewrite (`enrich_supplements_v3.py::_collect_contaminant_data`). Interaction subjects ARE the IQD
identity (`_derive_interaction_subject_ref`), so rewrites move warnings.

Product level (951 capture): 229 cases where the cleaner identity's rule is absent from the
shipped profile. Representative under-warnings caused by a wrong rewrite: "Green Tea (Camellia
sinensis) extract" → green_tea (GREEN_TEA_HYPERTENSION missing, 16 products); "Olive leaf extract"
→ olive_fruit_extract (OLIVE_LEAF_DIABETES missing, 13); "Reishi … Extract" → generic mushroom
record (REISHI autoimmune, 5). Correct removals: "King Trumpet" → lion's mane (anticoagulant rule
wrongly gained), "Cassia Seed Extract" is not cinnamon, DGL is not glycyrrhizin licorice.

## Fix (owner `scripts/identity_integrity.py::resolve_identity`)

1. A DSLD group cannot replace an identity whose exact curated alias is the printed name (resolver
   reads it as nothing else) unless the label also names the group's identity, the group's id is a
   registered child (refinement), or either side is the general blend owner (a row role).
2. A non-scorable row keeps a supplied identity its printed name is an exact curated alias of.

Prior policy reversed: commit 9f0daf180 (July 13, "rank declared taxonomy above aliases", no
rationale recorded). `test_structured_epa_label_repairs_conflicting_dha_taxonomy` still passes (it
has no curated registry); with the real registry a printed "Docosahexaenoic Acid Ethyl Ester" under
an EPA group now stays DHA — the printed name wins.

## Data batch — curated aliases that named another substance (`alias_batch.py`)

| Entry | Before → after | Evidence | Verdict |
|---|---|---|---|
| `lactococcus_cremoris` / `lactococcus_lactis` form aliases | 4 "diacetylactis" aliases moved to L. lactis | NCBI Taxonomy 44688 "Lactococcus lactis subsp. lactis bv. diacetylactis", lineage …Lactococcus lactis; L. lactis subsp. lactis (L. cremoris is taxid 1359), checked 2026-10-19 via E-utilities | fixed |
| `shilajit` form `fulvic acid` | "elevATP", "elevatp ancient peat", "ancient peat and apple extract" removed; the latter two added to `PII_ELEVATP_BRANDED_BLEND` (already owns "elevatp") | ElevATP = ancient peat + apple extract (FutureCeuticals): https://nutritionaloutlook.com/view/apple-extract-plus-ancient-peat-may-increase-athletic-performance, https://nxtingredients.com/specialty-ingredient/elevatp-by-futureceuticals/ | fixed |
| `olive_leaf` form / botanical `olive_leaf_powder` | "olive juice extract", "Olive Water extract" moved to `olive_fruit_extract` | DSLD rows record PlantPart "fruit" (Life Extension 64572, 62279, 60911); vegetation water is the liquid from pressing olive fruit (US 6,416,808, https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6416808) | fixed |
| `artemisinin` (compound, qinghaosu) | plant names "sweet wormwood", "artemisia annua", "… extract", "sweet annie extract", "qinghao" moved to botanical `sweet_wormwood_herb` | Artemisinin is a sesquiterpene lactone from Artemisia annua; qinghao is the plant, qinghaosu the compound | fixed |
| "Polyphen-Oil olive extract" on `olive_leaf` | unchanged | DSLD PlantPart "fruit and leaf" (Life Extension 63665, 232620): mixed, no single owner | confirmed, not changed |
| "red cabbage" on `NHA_NATURAL_COLORS` | unchanged | In inactive lists it is a colorant; inside veggie blends a food. Section-dependent role, not a wrong substance | queued (follow-up) |
| "hu zhang" aliases on `resveratrol` | unchanged | Hu Zhang is Polygonum cuspidatum (the plant). Moving it removes RESVERATROL_BLEEDING from knotweed rows; needs a sourced knotweed interaction decision first | queued (clinical) |
