"""#200 delta audit (October 20, 2026): the surgery mechanism's plural rests on one case
(PMID 17192169) and OPERA (PMID 30571332) was not "standard doses" (8-10 g before surgery,
then 2 g/day); the factor VII sentence's only source (PMID 14742793) is one case report.
Run from the repo root with $PG_PYTHON, then `scripts/data_batch.py check
scripts/data/ingredient_interaction_rules.json --since <ref> --expect
interaction_rules/RULE_INGREDIENT_FISH_OIL`."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

RULES = "scripts/data/ingredient_interaction_rules.json"
blob = data_batch.load(RULES)
[rule] = [r for r in blob["interaction_rules"] if r["id"] == "RULE_INGREDIENT_FISH_OIL"]
subs = {s.get("condition_id") or s.get("drug_class_id"): s for s in rule["condition_rules"] + rule["drug_class_rules"]}

surgery = subs["surgery_scheduled"]
old = ("A large RCT (OPERA, n=1516) found no significant increase in surgical bleeding at standard doses; "
       "however, high-dose use (6 g/day) combined with anticoagulants has produced serious hemorrhagic events.")
assert old in surgery["mechanism"], surgery["mechanism"]
surgery["mechanism"] = surgery["mechanism"].replace(
    old,
    "In a large fish-oil trial (OPERA, n=1516; 8-10 g before surgery, then 2 g/day), perioperative "
    "bleeding was not increased. In one reported case, 6 g/day of omega-3 taken with warfarin and "
    "aspirin was followed by a subdural hematoma after a fall.",
)

bleeding = subs["bleeding_disorders"]
old = ("In fish-oil studies, lower factor VII levels (a vitamin K-dependent coagulation factor) have also "
       "been reported; algal DHA at 1.62 g/day did not alter the thrombogenic factors measured (PMID 9001371).")
assert old in bleeding["mechanism"], bleeding["mechanism"]
bleeding["mechanism"] = bleeding["mechanism"].replace(
    old,
    "A fish-oil case report notes that omega-3 fatty acids may decrease factor VII levels (a vitamin "
    "K-dependent coagulation factor); algal DHA at 1.62 g/day did not alter the thrombogenic factors "
    "measured (PMID 9001371).",
)
data_batch.save(RULES, blob)
