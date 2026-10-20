"""RULE_IQM_RESVERATROL_BLEEDING copy (Sean, 2026-10-19): a qualified advisory whose clinical
significance at low declared amounts is uncertain; no proven-risk wording, no mg cutoff, no
medication adjustment. Severity, materiality, sources and profile gates unchanged.
Run from the repo root with $PG_PYTHON."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

PATH = "scripts/data/ingredient_interaction_rules.json"
BLEED_BODY = ("Lab studies show resveratrol can slow platelet clumping; whether supplement amounts affect "
              "bleeding in people is uncertain. Mention it to your clinician if you have a bleeding disorder.")
ANTI_BODY = ("Lab and mouse studies suggest resveratrol may add to blood-thinner effects; whether supplement "
             "amounts matter in people is uncertain. Tell your blood-thinner prescriber you use it.")
PLATE_BODY = ("Lab studies show resveratrol can slow platelet clumping; whether supplement amounts add to "
              "antiplatelet medicines in people is uncertain. Tell your prescriber you use it.")
for body in (BLEED_BODY, ANTI_BODY, PLATE_BODY):
    assert 60 <= len(body) <= 200, (len(body), body)
blob = data_batch.load(PATH)
[rule] = [r for r in blob["interaction_rules"] if r["id"] == "RULE_IQM_RESVERATROL_BLEEDING"]
subs = {s.get("condition_id") or s.get("drug_class_id"): s for s in rule["condition_rules"] + rule["drug_class_rules"]}

bleed = subs["bleeding_disorders"]
bleed["mechanism"] = ("In laboratory (in vitro) studies resveratrol inhibits platelet aggregation; its clinical relevance is not "
                      "established (MSKCC). No human study cited here sets a bleeding risk or an amount.")
bleed["action"] = "If you have a bleeding disorder, tell your clinician you use resveratrol, especially before a procedure."
bleed["alert_body"] = BLEED_BODY

anti = subs["anticoagulants"]
anti["mechanism"] = ("In a mouse study, 0.5% dietary trans-resveratrol enhanced warfarin’s effect while 0.05% did "
                     "not (PMID 26947597). This model does not establish a human interaction, an amount, or an effect "
                     "on other anticoagulants; resveratrol's platelet effect is an in vitro finding (MSKCC).")
anti["action"] = "Tell the prescriber who manages your blood thinner that you use resveratrol."
anti["alert_body"] = ANTI_BODY

plate = subs["antiplatelets"]
plate["mechanism"] = ("Resveratrol inhibits platelet aggregation in vitro, so an additive effect with antiplatelet "
                      "medicines is possible; its clinical relevance is not established (MSKCC).")
plate["action"] = "Tell the prescriber of your antiplatelet medicine that you use resveratrol."
plate["alert_body"] = PLATE_BODY
data_batch.save(PATH, blob)
