"""#200 audit F1 (October 20, 2026): RULE_INGREDIENT_FISH_OIL mechanisms ship as warnings[].detail;
findings from fish-oil studies are scoped as such. Run from the repo root with $PG_PYTHON, then
`scripts/data_batch.py check scripts/data/ingredient_interaction_rules.json --since <ref>
--expect interaction_rules/RULE_INGREDIENT_FISH_OIL`."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

RULES = "scripts/data/ingredient_interaction_rules.json"
blob = data_batch.load(RULES)
[rule] = [r for r in blob["interaction_rules"] if r["id"] == "RULE_INGREDIENT_FISH_OIL"]
subs = {s.get("condition_id") or s.get("drug_class_id"): s for s in rule["condition_rules"] + rule["drug_class_rules"]}

bleeding = subs["bleeding_disorders"]
old = "Fish oil may also reduce factor VII levels, a vitamin K-dependent coagulation factor."
assert old in bleeding["mechanism"]
bleeding["mechanism"] = bleeding["mechanism"].replace(
    old,
    "In fish-oil studies, lower factor VII levels (a vitamin K-dependent coagulation factor) have also "
    "been reported; algal DHA at 1.62 g/day did not alter the thrombogenic factors measured (PMID 9001371).",
)
bleeding["sources"].append("https://pubmed.ncbi.nlm.nih.gov/9001371/")

antiplatelets = subs["antiplatelets"]
old = ("Combined use of high-dose fish oil with aspirin and warfarin has been associated with subdural "
       "hematoma after minor trauma.")
assert old in antiplatelets["mechanism"]
antiplatelets["mechanism"] = antiplatelets["mechanism"].replace(
    old, "In one reported case, high-dose fish oil taken with aspirin and warfarin was followed by a "
         "subdural hematoma after minor trauma.")

nsaids = subs["nsaids"]
old = "universal combined gastrointestinal-bleeding risk from fish oil."
assert old in nsaids["mechanism"]
nsaids["mechanism"] = nsaids["mechanism"].replace(
    old, "universal combined gastrointestinal-bleeding risk from omega-3 (EPA/DHA) supplements.")

data_batch.save(RULES, blob)
