"""Apply the source-checked G3 timing decisions; no new relation or scoring policy.

Owner: timing_rules.json / timing_rules_rejected.json. See batch7_timing_research.md.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

TIMING = REPO / "scripts/data/timing_rules.json"
REJECTED = REPO / "scripts/data/timing_rules_rejected.json"
MEDLINE = "https://medlineplus.gov/druginfo/meds/a601104.html"
SYNTHROID = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1e11ad30-1041-4520-10b0-8f9d30d30fcc"
DATE = "2026-11-12"


def main() -> None:
    doc = data_batch.load(TIMING)
    ledger = data_batch.load(REJECTED)
    rules = {r["id"]: r for r in doc["timing_rules"]}
    reasons = {
        "timing_calcium_vitamin_d_together": "Dr. Pham G3 (2026-11-11) rejects necessary simultaneous dosing: vitamin D adequacy supports calcium handling, but PMID 21118827 establishes intake requirements, not a same-time absorption window or timing score bonus.",
        "timing_quercetin_vitamin_c_together": "Dr. Pham G3 (2026-11-11) rejects this absorption/timing claim: the LPI flavonoid reference does not establish that simultaneous vitamin C improves quercetin absorption. No timing score bonus is justified.",
    }
    for rule_id, reason in reasons.items():
        old = rules.pop(rule_id, None)
        if old is None:
            continue
        ledger["rejected"].append({
            "id": rule_id,
            "prior_claim": old["advice"],
            "rejection_reason": reason,
            "source_reviewed": [s["url"] for s in old["sources"]],
            "reviewer": "Decision: Dr. Pham, DR_PHAM_REVIEW_20261111.md G3. Source recheck and implementation: Codex agent, not clinician review.",
            "reviewed_on": DATE,
            "superseding_rule": None,
            "clinical_fingerprint": {k: deepcopy(old.get(k)) for k in (
                "ingredient1", "ingredient2", "ingredient1_tags", "ingredient2_tags",
                "ingredient1_rxcuis", "ingredient2_rxcuis", "timing_relation", "mechanism",
            )},
        })

    magnesium = rules["timing_thyroid_med_magnesium_separate"]
    magnesium.update({
        "review_status": "verified",
        "mechanism": "In 15 healthy adults, simultaneous magnesium aspartate reduced thyroxine exposure by 12%; the 7% reduction with magnesium citrate was not statistically significant. The trial did not test separated dosing. Four hours is the adopted D27 precaution extrapolated from levothyroxine label guidance for antacids, not a trial-proven magnesium interval.",
        "review_note": "Sean D27 (2026-10-01) adopted at least 4 hours consistently; Dr. Pham (2026-11-11, sections C and G3) recommended publishing on that precautionary basis. Agent source recheck 2026-11-12: ThyroMag PMID 41221788, case series PMID 10193669, SYNTHROID sections 7.1 and 17. Wording prepared by agent, not reviewed by Dr. Pham. The trial tested dissolved magnesium citrate/aspartate coadministration, not four-hour separation or every formulation.",
        "reviewed_on": DATE,
        "review_blockers": [],
        "canaries": {"positive": ["1055"], "negative": ["17550"]},
    })
    magnesium["sources"][-1] = {
        "source_type": "fda", "label": "SYNTHROID label sections 7.1 and 17: magnesium-containing antacids; four-hour antacid instruction", "url": SYNTHROID,
    }

    base = rules["timing_psyllium_water_med_spacing"]
    for rule_id, name, rxcuis in (
        ("timing_psyllium_water_med_spacing", "digoxin", ["3407"]),
        ("timing_psyllium_salicylates_separate", "salicylates", ["1191", "36108", "215799", "52364", "9907"]),
        ("timing_psyllium_nitrofurantoin_separate", "nitrofurantoin", ["7454"]),
    ):
        rule = deepcopy(base)
        rule.pop("excluded_member_rxcuis", None)
        rule.update({
            "id": rule_id,
            "ingredient2": name,
            "ingredient2_rxcuis": rxcuis,
            "timing_relation": {"type": "separate_from", "minimum_hours": 3},
            "review_status": "verified",
            "advice": f"Keep {name} taken by mouth at least 3 hours apart from psyllium. Take psyllium with at least 8 oz of liquid; mix powder or granules with liquid just before use. Follow your product's directions for other medicines.",
            "mechanism": "MedlinePlus gives a three-hour precaution for psyllium with digoxin, salicylates or nitrofurantoin; it does not set this interval for every medicine. Psyllium absorbs liquid and swells; adequate liquid is a separate administration instruction.",
            "review_note": "Dr. Pham G3/F10 (2026-11-11) authorizes the named three-hour guidance, not a universal medication interval. MedlinePlus and RxNorm identities rechecked by agent 2026-11-12. Wording prepared by agent, not reviewed by Dr. Pham. Product-label spacing is not generalized across brands. Water guidance is retained as advice, with no separate timing bonus. The authored excluded_member_rxcuis list excludes the content-verified nonoral product identities current on 2026-11-12; unknown routes retain the oral-qualified instruction. It is not an exhaustive future/retired-concept guarantee.",
            "reviewed_on": DATE,
            "review_blockers": [],
            "canaries": {"positive": ["17778"], "negative": ["17550"]},
            "sources": [{"source_type": "reference", "label": "MedlinePlus — Psyllium: liquid instructions and named three-hour medication precaution", "url": MEDLINE}],
        })
        if name == "digoxin":
            rule["mechanism"] += " A small four-week study in older inpatients found no change in steady-state digoxin levels with ispaghula; this study did not establish reduced absorption or validate the interval."
            rule["sources"].append({"source_type": "pubmed", "label": "Nordstrom et al. — Ispaghula and digoxin in geriatric inpatients (1987); negative study", "url": "https://pubmed.ncbi.nlm.nih.gov/3038494/"})
        rules[rule_id] = rule

    # Sean explicitly approved this optional timing predicate on 2026-11-12.
    # These are current nonoral product identities, not ingredient exclusions.
    excluded_by_ingredient = {
        "10582": ["1115267", "1115269", "2166148", "2166193", "2166196", "2621123", "966219", "1868004", "1602750"],
        "3407": ["208135", "208137", "1743560", "1175613", "104208", "204504", "1743558", "1151519"],
        "1191": ["103863", "198461", "198463", "198464", "198473", "370609", "1154071"],
    }
    for rule in rules.values():
        ingredients = rule.get("ingredient1_rxcuis", []) + rule.get("ingredient2_rxcuis", [])
        excluded = sorted({identity for ingredient in ingredients for identity in excluded_by_ingredient.get(ingredient, [])})
        if excluded:
            rule["excluded_member_rxcuis"] = excluded
    doc["_metadata"]["schema_version"] = "6.1.0"
    doc["timing_rules"] = list(rules.values())
    doc["_metadata"]["status_counts"] = {
        "verified": sum(r["review_status"] == "verified" for r in rules.values()),
        "needs_revision": sum(r["review_status"] == "needs_revision" for r in rules.values()),
        "rejected": len(ledger["rejected"]),
    }
    data_batch.save(TIMING, doc)
    data_batch.save(REJECTED, ledger)


if __name__ == "__main__":
    main()
