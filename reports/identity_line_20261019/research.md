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

A DSLD group cannot replace an identity whose exact curated alias is the printed name (the
resolver reads it as nothing else) unless: the label also names the group's identity (alias, or
every word of its standard name); the group's id is a registered child; the supplied id is a role
or catch-all record (other_ingredients, proprietary_blends) or either side is BLEND_GENERAL; or
keeping the label identity would drop an interaction rule the group's identity answers to (the
enricher passes `_interaction_rule_ids_of`).

Narrowed after CI run 39333525445 (6 failures) and the independent review: the first version also
let generic/role records beat a correct specific group (NHA_NATURAL_COLORS over cabbage,
digestive_enzymes over protease, isoflavones over soy isoflavones), undid the pinned IQM ginger
projection, and dropped rules the group carried (knotweed → resveratrol bleeding, cod liver oil
→ fish oil). A second rule (non-scorable rows keep a label-named identity) was dropped: it
retained blend-registry ids on headers and moved unrelated clinical matches (204521 lost
INGR_WHEY_PROTEIN, INGR_CHLORELLA through the blend-evidence path). Follow-up, not in this batch.

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
| "ancient peat & apple extract" on `shilajit` fulvic acid | moved to `PII_ELEVATP_BRANDED_BLEND` (review finding; same product as "ancient peat and apple extract") | ElevATP receipt above | fixed (`review_fix_batch.py`) |
| `green_bell_pepper` evidence record (new) | `identity_classification_no_literature_claim`, not_efficacy_relevant | bounded PubMed screen 2026-10-19, 13 records: only bell-pepper human study is juice added to yoga therapy (PMID 28917374); others capsaicin/capsinoid/paprika-oleoresin Capsicum extracts, child vegetable-acceptance trials, agronomy | added (`review_fix_batch.py`); needed because 282638 now carries the printed bell pepper identity |
| "hu zhang" aliases on `resveratrol` | unchanged | Hu Zhang is Polygonum cuspidatum (the plant). Moving it removes RESVERATROL_BLEEDING from knotweed rows; needs a sourced knotweed interaction decision first | queued (clinical) |

## Measurement — cohort replay (October 19, 2026)

`scripts/audits/quality_redesign/replay.py`, cohort of 3,596 labels: 2,396 affected (every product
with an identity rewrite on the 951a05415 capture, plus every label naming a batch alias) and 1,200
seeded-random controls. Frozen raw: `~/pg_quality/identity_line_20261019/frozen_raw` (from
full_artifact_baseline_20261018). `--full --blob --workers 4`, `compare --all-paths`. Every capture
`source_unchanged: true`, 3,596/3,596. Classification: `measure_outcomes.py`; final result
`outcomes_aeae4534b.json` (this folder).

| Record | Baseline | Candidate | Changed products |
|---|---|---|---|
| 0 | fd51b5828 | c9eb38b41/9a56520ee | 1,038 (found BioVin, cabbage palm) |
| 1 | fd51b5828 | 249278ec2 (batch 3) | 1,038 (268 = clock field across UTC midnight) |
| **final** | **main 2b676f415** | **aeae4534b (merged)** | **796** (786 affected, 10 controls) |

Final record, by outcome:

- Safety status moves: **0**. Allergen / banned / harmful hits moved: **0**.
- Raw-to-final line gate on every candidate product: **0 findings**.
- Interaction rules lost: **19, all RULE_IQM_OLIVE_LEAF_DIABETES** on Life Extension
  "Olive juice extract" rows. DSLD records PlantPart fruit; the row moves from olive_leaf_powder to
  olive_fruit_extract, and the rule's subject is olive leaf (oleuropein-rich leaf extract). This is a
  correct removal from the alias batch.
- Interaction rules gained: 16 — RULE_IQM_OLIVE_LEAF_DIABETES ×13 (printed "Olive leaf extract"
  restored), RULE_BOTAN_SCHISANDRA_BERRY_CYP3A4 ×2, RULE_INGREDIENT_FISH_OIL ×1 (kids' "EPA/DHA").
- Per-id carrier counts (blob ingredients / active display_ingredients / IQD), interaction-rule
  subjects only:
  - **The display ledger, which the app reads,** loses only olive_leaf ×19, resveratrol ×7 and
    saw_palmetto ×2. All three are wrong-substance removals: olive fruit; BioVin is a grape extract;
    "Cabbage Palm" in a berry blend is açaí.
  - **Blob ingredients** loses probiotics ×8, vitamin_a ×2, and cinnamon, cranberry,
    creatine_monohydrate and echinacea ×1 each. These are F2 rows the enricher leaves unresolved;
    the display ledger still carries them, so neither the app's id set nor any rule loses them.
  - Totals: IQD −785/+788, blob ingredients −382/+301, display ledger −82/+82.
- Score moves: 108 products (100 with totals both sides; mean +0.41, range −6.0 to +23.4; 51 up,
  49 down). By cause:
  - Correct identity restored and scored at its IQM form quality: Levagen → PEA ×22 (−0.9 to −2.7),
    Capsicum/cayenne ×6+ (−0.1 to −6.0), soy protein isolate → protein, silica, olive juice →
    fruit extract ×19 (+0.1 to +0.2).
  - Correct identity restored, score rises: NeuroFactor ×15 (+1.7), "Coconut water powder" was
    mct_oil (+2.6), "Brown Seaweed Fucoxanthin Concentrate" → fucoxanthin (+23.4), kids' "EPA/DHA"
    from a purified-fish-oil carrier record to fish_oil (+14.3), IQM lion's mane (+5.5), KeraGLO
    (+6.6), Bonolive (+2.7), tart cherry, wheatgrass, kelp.
  - **scored → not_scored, 8 products:** single-ingredient "Barley Grass" ×7 (was the
    other-ingredients role record NHA_YOUNG_BARLEY) and 204040 "Soy Isoflavones extract". The
    restored identity's DSLD form ("Hordeum vulgare", "Soybean" — the species) is unmapped, so
    readiness withholds the score (`disclosed_form_unmapped`), an honest unknown. Follow-up: a
    form policy for species-binomial forms.
- Remaining changed products without a score or rule move: F2 export (blob ingredients / row_ledger
  / analysis `canonical_id`, `is_mapped`), printed display names, `identity_integrity_state`
  repaired → clean, and list-index shifts when a row moves bucket. None unexplained.
