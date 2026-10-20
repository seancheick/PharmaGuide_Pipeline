"""#202 audit batch (October 20, 2026): bleeding-disorder and surgery lines on the
notoginseng advisory; the same advisory on the Senactiv complex. Run from the repo root."""
import copy
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

RULES = "scripts/data/ingredient_interaction_rules.json"
EMPTY = {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
         "product_forms_any": [], "nutrient_forms_any": []}
SOURCES = [
    "https://pubmed.ncbi.nlm.nih.gov/33370633/",
    "https://pubmed.ncbi.nlm.nih.gov/31471773/",
    "https://pubmed.ncbi.nlm.nih.gov/39364700/",
    "https://pubmed.ncbi.nlm.nih.gov/34307625/",
]
MECHANISM = (
    "Panax notoginseng saponins added to aspirin further inhibited platelet aggregation in a "
    "randomized trial of 42 people with coronary heart disease (bleeding was not measured), and "
    "a review of clopidogrel-herb interactions reports increased antiplatelet activity with "
    "notoginseng. Two case reports describe esophageal submucosal hematoma after notoginseng "
    "capsules; one involved a homemade mixture with hirudin, a known anticoagulant, so it cannot "
    "be attributed to notoginseng alone. The clinical significance for bleeding is not established."
)


def condition_line(condition_id, gate_type, gate_key, headline, body, action, note):
    assert 60 <= len(body) <= 200, (condition_id, len(body))
    requires = {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": []}
    requires[gate_key] = [condition_id]
    return {
        "condition_id": condition_id, "severity": "monitor", "evidence_level": "limited",
        "mechanism": MECHANISM, "action": action, "sources": list(SOURCES),
        "alert_headline": headline, "alert_body": body, "informational_note": note,
        "profile_gate": {"gate_type": gate_type, "requires": requires, "excludes": dict(EMPTY), "dose": None},
        "direction": "harmful", "materiality": "presence",
    }


rules = data_batch.load(RULES)
by_id = {r["id"]: r for r in rules["interaction_rules"]}
noto = by_id["RULE_BOTAN_PANAX_NOTOGINSENG_ANTIPLATELET"]
assert noto["condition_rules"] == []
noto["condition_rules"] = [
    condition_line(
        "bleeding_disorders", "condition", "conditions_any",
        "Notoginseng — bleeding disorders",
        "Notoginseng may affect platelet function. A bleeding risk is not established; if you "
        "have a bleeding disorder, talk to your clinician before using it.",
        "If you have a bleeding disorder, talk to your clinician before using Panax notoginseng.",
        "Platelet effects come from small studies and case reports; clinical bleeding significance is not established.",
    ),
    condition_line(
        "surgery_scheduled", "profile_flag", "profile_flags_any",
        "Notoginseng — before surgery",
        "Notoginseng may affect platelet function. A bleeding risk is not established; tell "
        "your surgeon you use it before a scheduled procedure.",
        "Tell your surgeon you use Panax notoginseng before a scheduled procedure.",
        "Platelet effects come from small studies and case reports; clinical bleeding significance is not established.",
    ),
]
for sub in noto["drug_class_rules"]:
    sub["sources"] = list(SOURCES)
    sub["mechanism"] = MECHANISM
noto["last_reviewed"] = "2026-10-20"

assert "RULE_OTHER_SENACTIV_ANTIPLATELET" not in by_id
senactiv = copy.deepcopy(noto)
senactiv["id"] = "RULE_OTHER_SENACTIV_ANTIPLATELET"
senactiv["subject_ref"] = {"db": "other_ingredients", "canonical_id": "NHA_SENACTIV"}
for sub in senactiv["condition_rules"] + senactiv["drug_class_rules"]:
    for key in ("alert_headline", "alert_body", "action"):
        sub[key] = sub[key].replace("Panax notoginseng", "Senactiv (Panax notoginseng)").replace(
            "Notoginseng", "Senactiv (notoginseng)")
        if key == "alert_body":
            assert 60 <= len(sub[key]) <= 200, (sub.get("condition_id") or sub.get("drug_class_id"), len(sub[key]))
senactiv["pregnancy_lactation"]["notes"] = (
    "Pregnancy and breastfeeding safety data for Senactiv (Panax notoginseng and Rosa roxburghii) "
    "are limited; discuss use with your clinician."
)
senactiv["review_owner"] = "Source-content review (agent); Senactiv is Panax notoginseng + Rosa roxburghii fractions (NHA_SENACTIV)"
rules["interaction_rules"].append(senactiv)
data_batch.save(RULES, rules)

# Reviewed ghost-suspects: the Senactiv rule cites notoginseng studies; "Senactiv" is the
# branded complex of the same material and never appears in their titles or abstracts.
import json  # noqa: E402

GHOST = "scripts/data/interaction_rules_ghost_review.json"
ghost = json.load(open(GHOST))
TITLES = {
    "33370633": "Combination of Panax notoginseng saponins and aspirin potentiates platelet inhibition with alleviated gastric injury via modulating arachidonic acid metabolism.",
    "31471773": "Interactions between clopidogrel and traditional Chinese medicine.",
    "39364700": "Spontaneous esophageal submucosal hematoma.",
    "34307625": "Submucosal hematoma with a wide range of lesions, severe condition and atypical clinical symptoms: A case report.",
}
existing = {(e["pmid"], e["rule_id"], e["sub_rule"]) for e in ghost["reviewed"]}
for sub_rule in ("condition:bleeding_disorders", "condition:surgery_scheduled", "drug:antiplatelets"):
    for pmid, title in TITLES.items():
        key = (pmid, "RULE_OTHER_SENACTIV_ANTIPLATELET", sub_rule)
        assert key not in existing, key
        ghost["reviewed"].append({
            "pmid": pmid, "rule_id": key[1], "sub_rule": sub_rule, "live_title": title,
            "rationale": "Branded-material citation: Senactiv (NHA_SENACTIV) is Panax notoginseng "
                         "and Rosa roxburghii fractions; the record concerns Panax notoginseng "
                         "(saponins or capsules), the material the sub-rule names. The same PMID is "
                         "cited on RULE_BOTAN_PANAX_NOTOGINSENG_ANTIPLATELET, where the strict gate "
                         "finds the subject.",
            "reviewed_by": "agent source-content review (not clinician-reviewed)",
            "reviewed_at": "2026-10-20",
        })
ghost["_metadata"]["total_entries"] = len(ghost["reviewed"])
with open(GHOST, "w") as handle:
    json.dump(ghost, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
