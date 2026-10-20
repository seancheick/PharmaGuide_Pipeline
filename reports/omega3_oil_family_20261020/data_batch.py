"""EPA/DHA oil family (October 20, 2026). Run from the repo root with $PG_PYTHON.

Entries:
  ingredient_quality_map algae_oil  + relationships contains dha (algal oils are bioequivalent DHA
                                      sources, PMID 17713804)
  ingredient_quality_map algae_oil  + alias "life'sOmega" (the printed spelling of the curated DSM brand
                                      alias "life's omega" on the same form)
  ingredient_quality_map krill_oil  + relationships contains epa, dha (krill oil delivers EPA and DHA,
                                      PMID 26328782)
  ingredient_interaction_rules RULE_INGREDIENT_FISH_OIL consumer copy names "omega-3 (EPA/DHA)",
                                      not fish oil; verbs, dose qualifiers, severities, sources unchanged.
"""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

IQM = "scripts/data/ingredient_quality_map.json"
iqm = data_batch.load(IQM)
iqm["algae_oil"].setdefault("relationships", []).append(
    {"type": "contains", "target_id": "dha",
     "notes": "Algal oil is a DHA source; algal DHA oils are bioequivalent DHA sources (PMID 17713804)."})
form = iqm["algae_oil"]["forms"]["algae oil (dha)"]
assert "life's omega" in form["aliases"] and "life'sOmega" not in form["aliases"]
form["aliases"].append("life'sOmega")
iqm["krill_oil"].setdefault("relationships", []).extend([
    {"type": "contains", "target_id": "epa",
     "notes": "Krill oil delivers EPA and DHA at plasma levels comparable to fish oil (PMID 26328782)."},
    {"type": "contains", "target_id": "dha",
     "notes": "Krill oil delivers EPA and DHA at plasma levels comparable to fish oil (PMID 26328782)."},
])
data_batch.save(IQM, iqm)

RULES = "scripts/data/ingredient_interaction_rules.json"
blob = data_batch.load(RULES)
[rule] = [r for r in blob["interaction_rules"] if r["id"] == "RULE_INGREDIENT_FISH_OIL"]
subs = {s.get("condition_id") or s.get("drug_class_id"): s for s in rule["condition_rules"] + rule["drug_class_rules"]}
subs["bleeding_disorders"]["action"] = ("If you have a bleeding disorder, discuss omega-3 (EPA/DHA) supplements with your "
                                        "clinician. Clinically significant bleeding is not consistently demonstrated in "
                                        "trials; your other medicines and condition matter.")
subs["bleeding_disorders"]["informational_note"] = "Omega-3 (EPA/DHA) can affect platelet function — relevant to people with a bleeding disorder."
subs["surgery_scheduled"]["action"] = ("Inform your surgical team about omega-3 (EPA/DHA) supplements and any blood thinners, "
                                       "and follow their product-specific instructions.")
subs["surgery_scheduled"]["informational_note"] = "Omega-3 (EPA/DHA) can affect perioperative bleeding — relevant to anyone preparing for surgery."
subs["anticoagulants"]["alert_body"] = ("EPA/DHA at 3 g/day or higher can thin the blood. Combined with warfarin or antiplatelet "
                                        "medication, this raises bleeding risk.")
subs["anticoagulants"]["action"] = ("Tell your warfarin prescriber about omega-3 (EPA/DHA) supplements and ask about INR "
                                    "monitoring when starting, stopping or changing them.")
subs["antiplatelets"]["alert_body"] = ("Omega-3 (EPA/DHA) has mild antiplatelet activity. If you take an antiplatelet medication "
                                       "like aspirin or clopidogrel, talk to your prescriber before adding it.")
subs["antiplatelets"]["action"] = "Discuss omega-3 (EPA/DHA) supplements with your antiplatelet prescriber and report unusual bruising or bleeding."
subs["antiplatelets"]["informational_note"] = "Omega-3 (EPA/DHA) can affect platelet function — relevant to people on antiplatelets."
subs["nsaids"]["alert_body"] = ("A clinically important omega-3 (EPA/DHA) interaction with NSAIDs is uncertain. Discuss use "
                                "with your prescriber, especially if you also take blood thinners or have bleeding risks.")
subs["nsaids"]["action"] = "Monitor for GI symptoms when combining omega-3 (EPA/DHA) with NSAIDs. Take NSAIDs with food."
subs["nsaids"]["informational_note"] = "Omega-3 (EPA/DHA) can affect platelet function — relevant to people on NSAIDs."
rule["pregnancy_lactation"]["alert_body"] = ("Discuss omega-3 (EPA/DHA) use and the specific dose with your prenatal or "
                                             "breastfeeding clinician. General adult supplement guidance does not establish an "
                                             "individual pregnancy or breastfeeding dose.")
for s in list(subs.values()) + [rule["pregnancy_lactation"]]:
    body = s.get("alert_body") or ""
    assert 60 <= len(body) <= 200, (len(body), body)
data_batch.save(RULES, blob)
