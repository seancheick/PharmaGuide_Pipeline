"""Panax notoginseng identity batch (October 20, 2026). Run from the repo root with $PG_PYTHON."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

IQM = "scripts/data/ingredient_quality_map.json"
OTHER = "scripts/data/other_ingredients.json"
BOT = "scripts/data/botanical_ingredients.json"
RULES = "scripts/data/ingredient_interaction_rules.json"


def remove(aliases, gone):
    lowered = {a.lower() for a in gone}
    kept = [a for a in aliases if a.lower() not in lowered]
    assert len(aliases) - len(kept) == len(gone), gone
    aliases[:] = kept


def add(aliases, new):
    for alias in new:
        assert alias.lower() not in {a.lower() for a in aliases}, alias
        aliases.append(alias)


# 1. IQM ginseng: Senactiv and the notoginseng / chestnut-rose source names are not Panax ginseng.
iqm = data_batch.load(IQM)
form = iqm["ginseng"]["forms"]["ginseng (unspecified)"]
remove(form["aliases"], ["senactiv", "senactiv panax notoginseng", "Seneactiv", "Panax notoginseng, Rosa roxburghii"])
remove(form["source_form_aliases"], ["panax notoginseng", "rosa roxburghii"])
data_batch.save(IQM, iqm)

# 2. The branded complex keeps its existing owner.
other = data_batch.load(OTHER)
[senactiv] = [e for e in other["other_ingredients"] if e["id"] == "NHA_SENACTIV"]
add(senactiv["aliases"], ["seneactiv", "senactiv panax notoginseng", "panax notoginseng, rosa roxburghii"])
senactiv["last_updated"] = "2026-10-20"
data_batch.save(OTHER, other)

# 3. Panax notoginseng root: names from GSRS GQX1C1175U (PANAX NOTOGINSENG ROOT).
bot = data_batch.load(BOT)
assert not [e for e in bot["botanical_ingredients"] if e["id"] == "panax_notoginseng"]
bot["botanical_ingredients"].append({
    "id": "panax_notoginseng",
    "standard_name": "Panax Notoginseng",
    "latin_name": "Panax notoginseng",
    "aliases": [
        "panax notoginseng",
        "panax notoginseng root",
        "panax notoginseng root extract",
        "panax notoginseng extract",
        "panax pseudoginseng var. notoginseng root",
        "notoginseng",
        "notoginseng root",
        "notoginseng root extract",
        "pseudoginseng root",
        "san qi",
        "san qi root",
        "sanqi",
        "sanchi",
        "tian qi root",
        "tienchi ginseng root",
        "tienchi ginseng root extract",
    ],
    "category": "root",
    "notes": "Panax notoginseng (Araliaceae) root and rhizome; San Qi / Tienchi ginseng in TCM (GSRS "
             "GQX1C1175U, Chinese Pharmacopoeia Notoginseng Radix et Rhizoma). A different species "
             "from Panax ginseng; its saponin profile (notoginsenoside R1) differs. Identity-only "
             "mapping.",
    "last_updated": "2026-10-20",
    "external_ids": {"unii": "GQX1C1175U"},
    "cui": "C1011520",
    "rxcui": "1365707",
    "functional_roles": [],
    "attributes": {"source_origin": "plant"},
})
data_batch.save(BOT, bot)

# 4. One sourced advisory: antiplatelets only.
EMPTY = {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
         "product_forms_any": [], "nutrient_forms_any": []}
rules = data_batch.load(RULES)
assert not [r for r in rules["interaction_rules"] if r["id"] == "RULE_BOTAN_PANAX_NOTOGINSENG_ANTIPLATELET"]
body = ("In a small trial, notoginseng saponins added to aspirin increased platelet inhibition. "
        "A bleeding risk is not established; tell your clinician you use it.")
assert 60 <= len(body) <= 200, len(body)
rules["interaction_rules"].append({
    "id": "RULE_BOTAN_PANAX_NOTOGINSENG_ANTIPLATELET",
    "subject_ref": {"db": "botanical_ingredients", "canonical_id": "panax_notoginseng"},
    "condition_rules": [],
    "drug_class_rules": [{
        "drug_class_id": "antiplatelets",
        "severity": "monitor",
        "evidence_level": "limited",
        "mechanism": "In a randomized, assessor-blinded trial of 42 people with stable coronary heart "
                     "disease, Panax notoginseng saponins taken with aspirin for 2 months further "
                     "inhibited platelet aggregation and activation (COX-1/thromboxane pathway) "
                     "compared with aspirin alone. Bleeding was not an outcome; whether supplement "
                     "amounts of notoginseng root change bleeding risk with antiplatelet drugs is "
                     "not established. A review of herb-drug interaction studies lists antiplatelet "
                     "synergy among its pharmacodynamic interactions.",
        "action": "If you take an antiplatelet medicine such as aspirin or clopidogrel, tell your "
                  "clinician you use Panax notoginseng.",
        "sources": [
            "https://pubmed.ncbi.nlm.nih.gov/33370633/",
            "https://pubmed.ncbi.nlm.nih.gov/36754189/",
        ],
        "alert_headline": "Notoginseng — antiplatelet medicines",
        "alert_body": body,
        "informational_note": "Evidence is one small trial of notoginseng saponins with aspirin; "
                              "clinical bleeding significance is not established.",
        "profile_gate": {
            "gate_type": "drug_class",
            "requires": {"conditions_any": [], "drug_classes_any": ["antiplatelets"], "profile_flags_any": []},
            "excludes": dict(EMPTY),
            "dose": None,
        },
        "direction": "harmful",
        "materiality": "presence",
    }],
    "dose_thresholds": [],
    "pregnancy_lactation": {
        "pregnancy_category": "no_data",
        "lactation_category": "no_data",
        "evidence_level": "no_data",
        "notes": "Pregnancy and breastfeeding safety data for Panax notoginseng supplements are "
                 "limited; discuss use with your clinician.",
        "alert_headline": "Limited safety data",
        "alert_body": "There isn't enough specific safety data to give a confident recommendation "
                      "for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician "
                      "before using this supplement.",
        "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended.",
        "direction": "unknown",
        "materiality": "presence",
    },
    "last_reviewed": "2026-10-20",
    "review_owner": "Source-content review (agent); clinical bleeding significance unestablished",
})
data_batch.save(RULES, rules)
