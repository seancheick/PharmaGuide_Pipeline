#!/usr/bin/env python3
"""
Apply the previously-deferred items from clinician batch (2026-04-30):

  W10  Bromelain × anticoagulants (severity: monitor)
       - Add IQM bromelain parent (verified UNII U182GP2CF3, CUI C0006217,
         CAS 9001-00-7 from standardized_botanicals).
       - Cross-reference standardized_botanicals.bromelain with the new
         IQM parent (replaces no_iqm_parent_reason).
       - Add the W10 drug_class_rule.

  M2   Tyramine-rich extracts × MAOIs (severity: contraindicated)
       - Add harmful_additives entry ADD_TYRAMINE_RICH_EXTRACT.
       - Add the M2 drug_class_rule with full clinical payload.
       - Section 6 open call locked Position A: contraindicated.

  2E (partial) Goldenseal × cyp2d6_substrates (severity: avoid)
       - Existing C5 mechanism already documents "Also affects CYP2D6".
       - Add the cyp2d6_substrates drug_class_rule on the goldenseal subject.
       - Bupleurum and St. John's Wort × CYP2D6 still need clinician sign-off
         per Section 2E "next batch" deferral; not authored here.

Idempotent.
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
IQM_PATH = DATA_DIR / "ingredient_quality_map.json"
HARMFUL_PATH = DATA_DIR / "harmful_additives.json"
SB_PATH = DATA_DIR / "standardized_botanicals.json"
RULES_PATH = DATA_DIR / "ingredient_interaction_rules.json"


# ---------------------------------------------------------------------------
# 1. IQM bromelain entry
# ---------------------------------------------------------------------------

BROMELAIN_IQM = {
    "standard_name": "Bromelain",
    "category": "enzymes",
    "category_enum": "enzymes",
    "cui": "C0006217",
    "external_ids": {
        "unii": "U182GP2CF3",
        "cas": "9001-00-7",
    },
    "forms": {
        "bromelain": {
            "bio_score": 10,
            "natural": True,
            "score": 12,
            "absorption": "Local-action enzyme; systemic absorption is partial via Peyer's patches. Activity-based dosing (GDU/g or MCU/mg), not mass-based.",
            "notes": "Pineapple-stem proteolytic enzyme. Standardized by activity (2400 GDU/g standard). Clinical use in osteoarthritis, sinusitis, and post-surgical inflammation (NCCIH monograph). Has mild fibrinolytic / antiplatelet activity at supplement doses ≥500 mg/day — see ingredient_interaction_rules for anticoagulant interaction.",
            "aliases": [
                "bromelain enzyme",
                "pineapple enzyme",
                "pineapple bromelain",
                "stem bromelain",
                "fruit bromelain",
            ],
            "dosage_importance": 1.0,
        },
    },
    "aliases": ["bromelain"],
    "match_rules": {
        "priority": 0,
        "match_mode": "alias_and_fuzzy",
        "exclusions": [],
        "parent_id": None,
        "confidence": "high",
    },
}


# ---------------------------------------------------------------------------
# 2. Harmful_additives tyramine-rich extracts entry
# ---------------------------------------------------------------------------

TYRAMINE_HARMFUL = {
    "id": "ADD_TYRAMINE_RICH_EXTRACT",
    "standard_name": "Tyramine-Rich Extracts",
    "aliases": [
        "tyramine",
        "tyramine extract",
        "aged yeast extract",
        "fermented bovine",
        "fermented bovine extract",
        "biogenic amine extract",
        "tyramine-containing extract",
        "fermented protein hydrolysate",
    ],
    "category": "biogenic_amine",
    "mechanism_of_harm": "Tyramine is a sympathomimetic biogenic amine. Combined with MAO-inhibitor medication, dietary or supplemental tyramine produces hypertensive crisis ('cheese reaction') — severe blood-pressure spike with documented fatalities. Concentrated in aged, fermented, and bacterially-processed extracts (aged-yeast, fermented bovine, certain protein hydrolysates).",
    "regulatory_status": {
        "US": "Not specifically regulated in supplements; FDA Drug Safety Communications warn of MAOI-tyramine interaction.",
        "EU": "EFSA risk assessment for histamine and tyramine in fermented foods (EFSA Journal 2011;9:2393).",
        "WHO": "Recognized contraindication with MAO-A inhibitors.",
    },
    "population_warnings": [
        "Anyone taking MAO inhibitors (phenelzine, tranylcypromine, isocarboxazid, selegiline) — contraindicated; severe hypertensive reaction risk",
        "Anyone with hypertension — concentrated tyramine sources elevate sympathetic tone",
    ],
    "notes": "Tyramine itself is not toxic at dietary levels in most people; the safety issue is exclusively the MAOI interaction. Fermented and aged supplement extracts can contain markedly higher tyramine than fresh ingredients. See ingredient_interaction_rules for the MAOI rule.",
    "severity_level": "high",
    "confidence": "high",
    "evidence_basis": "Established pharmacological interaction (Gillman 2018 Br J Clin Pharmacol; Shulman 2013 Drug Saf).",
    "sources": [
        "https://pubmed.ncbi.nlm.nih.gov/29380410/",
        "https://www.efsa.europa.eu/en/efsajournal/pub/2393",
    ],
}


# ---------------------------------------------------------------------------
# 3. New interaction rules
# ---------------------------------------------------------------------------

W10_BROMELAIN_RULE = {
    "drug_class_id": "anticoagulants",
    "severity": "monitor",
    "evidence_level": "limited",
    "mechanism": "Mild fibrinolytic / antiplatelet activity at high dose (≥500 mg/day). Bromelain enhances plasmin generation and modestly inhibits platelet aggregation. Clinical bleeding events with warfarin are rare but documented in case reports.",
    "action": "If you take warfarin or an antiplatelet, mention bromelain supplements ≥500 mg/day to your prescriber. Watch for unusual bruising or bleeding.",
    "sources": [
        "https://pubmed.ncbi.nlm.nih.gov/11577981/",
    ],
    "alert_headline": "Mild bleeding risk at high dose",
    "alert_body": "High-dose bromelain (500 mg/day or more) has mild blood-thinning activity. Combined with warfarin or antiplatelet drugs, this can slightly raise bleeding risk.",
    "informational_note": "Bromelain has fibrinolytic activity at clinical doses — relevant to anyone on blood thinners.",
}

M2_TYRAMINE_RULE = {
    "drug_class_id": "maois",
    "severity": "contraindicated",
    "evidence_level": "established",
    "mechanism": "Tyramine is a sympathomimetic biogenic amine and MAO substrate. With MAO-inhibitor medication, ingested tyramine cannot be metabolized normally, producing massive norepinephrine release and severe hypertensive crisis ('cheese reaction'). Documented fatalities in the clinical literature.",
    "action": "Do not combine tyramine-rich extracts with MAOIs. Read supplement labels for aged-yeast, fermented bovine, or tyramine-containing protein hydrolysates if you take an MAOI.",
    "sources": [
        "https://pubmed.ncbi.nlm.nih.gov/29380410/",
    ],
    "alert_headline": "Do not combine with MAOIs",
    "alert_body": "Tyramine-rich supplement extracts combined with MAO-inhibitor antidepressants can cause a life-threatening blood pressure spike. This is the same 'cheese reaction' that requires dietary restrictions on MAOIs.",
    "informational_note": "Tyramine is the classic MAOI dietary contraindication — relevant to anyone on phenelzine, tranylcypromine, isocarboxazid, or selegiline.",
}

GOLDENSEAL_CYP2D6_RULE = {
    "drug_class_id": "cyp2d6_substrates",
    "severity": "avoid",
    "evidence_level": "established",
    "mechanism": "Berberine and hydrastine inhibit CYP2D6 in addition to CYP3A4. CYP2D6 metabolizes a large class of psychiatric drugs (many SSRIs, tricyclics), opioids (codeine, tramadol — for activation), and tamoxifen.",
    "action": "If you take a CYP2D6-substrate prescription drug, avoid goldenseal unless your prescriber clears it. Especially relevant for codeine, tramadol, tamoxifen, paroxetine, and fluoxetine.",
    "sources": [
        "https://pubmed.ncbi.nlm.nih.gov/18180278/",
    ],
    "alert_headline": "Affects how many drugs are processed",
    "alert_body": "Goldenseal blocks the CYP2D6 enzyme that activates codeine and tramadol and metabolizes many antidepressants. This can change the effectiveness or side-effect profile of those drugs.",
    "informational_note": "Goldenseal inhibits CYP2D6 in addition to CYP3A4 — relevant to anyone on antidepressants, opioids for pain, or tamoxifen.",
}


# Helpers --------------------------------------------------------------------

def find_rule(rules, db, canonical_id):
    for r in rules:
        sref = r.get("subject_ref", {})
        if sref.get("db") == db and sref.get("canonical_id") == canonical_id:
            return r
    return None


def upsert_drug_class_rule(rule_obj, payload):
    """Idempotent upsert keyed by drug_class_id. Returns (changed, action)."""
    dcrs = rule_obj.setdefault("drug_class_rules", [])
    target_id = payload["drug_class_id"]
    for i, dcr in enumerate(dcrs):
        if dcr.get("drug_class_id") == target_id:
            if dcr == payload:
                return False, "noop"
            dcrs[i] = payload
            return True, "updated"
    dcrs.append(payload)
    return True, "added"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    summary = {
        "iqm_bromelain": "noop",
        "harmful_tyramine": "noop",
        "sb_bromelain_xref": "noop",
        "rule_W10": "noop",
        "rule_M2": "noop",
        "rule_goldenseal_cyp2d6": "noop",
    }

    # 1. IQM bromelain
    iqm = json.load(open(IQM_PATH))
    if "bromelain" not in iqm:
        iqm["bromelain"] = BROMELAIN_IQM
        summary["iqm_bromelain"] = "added"
    elif iqm["bromelain"] != BROMELAIN_IQM:
        iqm["bromelain"] = BROMELAIN_IQM
        summary["iqm_bromelain"] = "updated"

    # 2. Harmful_additives tyramine
    harmful = json.load(open(HARMFUL_PATH))
    arr = harmful.get("harmful_additives", [])
    existing_idx = next((i for i, e in enumerate(arr)
                         if isinstance(e, dict) and e.get("id") == TYRAMINE_HARMFUL["id"]), None)
    if existing_idx is None:
        arr.append(TYRAMINE_HARMFUL)
        summary["harmful_tyramine"] = "added"
    elif arr[existing_idx] != TYRAMINE_HARMFUL:
        arr[existing_idx] = TYRAMINE_HARMFUL
        summary["harmful_tyramine"] = "updated"

    # 3. Standardized_botanicals bromelain cross-ref (replace no_iqm_parent_reason)
    sb = json.load(open(SB_PATH))
    sb_arr = sb.get("standardized_botanicals", [])
    for e in sb_arr:
        if e.get("id") == "bromelain":
            attrs = e.get("attributes") or {}
            changed = False
            if attrs.get("iqm_parent_id") != "bromelain":
                attrs["iqm_parent_id"] = "bromelain"
                changed = True
            if "no_iqm_parent_reason" in attrs:
                attrs.pop("no_iqm_parent_reason")
                changed = True
            if changed:
                e["attributes"] = attrs
                summary["sb_bromelain_xref"] = "updated"
            break

    # 4. Interaction rules
    rules_data = json.load(open(RULES_PATH))
    rules = rules_data["interaction_rules"]

    # W10 — bromelain × anticoagulants. Create rule entry first.
    bromelain_rule = find_rule(rules, "ingredient_quality_map", "bromelain")
    if bromelain_rule is None:
        bromelain_rule = {
            "id": "RULE_IQM_BROMELAIN",
            "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "bromelain"},
            "condition_rules": [],
            "drug_class_rules": [],
            "dose_thresholds": [],
            "pregnancy_lactation": {
                "pregnancy_category": "no_data",
                "lactation_category": "no_data",
                "evidence_level": "no_data",
                "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
                "alert_headline": "Limited safety data",
                "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
                "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended.",
                "sources": [],
            },
            "last_reviewed": "2026-04-30",
            "review_owner": "pharmaguide_clinical_team",
        }
        rules.append(bromelain_rule)
    changed, action = upsert_drug_class_rule(bromelain_rule, W10_BROMELAIN_RULE)
    if changed:
        summary["rule_W10"] = action

    # M2 — tyramine × MAOIs. New rule entry under harmful_additives.
    tyramine_rule = find_rule(rules, "harmful_additives", "ADD_TYRAMINE_RICH_EXTRACT")
    if tyramine_rule is None:
        tyramine_rule = {
            "id": "RULE_HARM_TYRAMINE_RICH_EXTRACT",
            "subject_ref": {"db": "harmful_additives", "canonical_id": "ADD_TYRAMINE_RICH_EXTRACT"},
            "condition_rules": [],
            "drug_class_rules": [],
            "dose_thresholds": [],
            "pregnancy_lactation": {
                "pregnancy_category": "caution",
                "lactation_category": "caution",
                "evidence_level": "limited",
                "notes": "Concentrated tyramine extracts may elevate sympathetic tone — talk to your clinician before use during pregnancy or breastfeeding.",
                "alert_headline": "Talk to your clinician",
                "alert_body": "Concentrated tyramine sources can elevate blood pressure and sympathetic tone. Discuss with your obstetrician or pediatrician before use during pregnancy or breastfeeding.",
                "informational_note": "Tyramine elevates sympathetic tone — pregnancy/lactation guidance recommended.",
                "sources": [],
            },
            "last_reviewed": "2026-04-30",
            "review_owner": "pharmaguide_clinical_team",
        }
        rules.append(tyramine_rule)
    changed, action = upsert_drug_class_rule(tyramine_rule, M2_TYRAMINE_RULE)
    if changed:
        summary["rule_M2"] = action

    # 2E — goldenseal × cyp2d6_substrates (extends existing C5 rule)
    goldenseal_rule = find_rule(rules, "ingredient_quality_map", "goldenseal")
    if goldenseal_rule is not None:
        changed, action = upsert_drug_class_rule(goldenseal_rule, GOLDENSEAL_CYP2D6_RULE)
        if changed:
            summary["rule_goldenseal_cyp2d6"] = action

    # Bump metadata
    rules_data["_metadata"]["last_updated"] = "2026-04-30"
    rules_data["_metadata"]["total_rules"] = len(rules)
    rules_data["_metadata"]["total_entries"] = len(rules)

    print("Deferred-items application:")
    for k, v in summary.items():
        print(f"  {k:30s} {v}")

    if args.dry_run:
        print("\n[dry-run] would write changes")
        return 0

    json.dump(iqm, open(IQM_PATH, "w"), indent=2, ensure_ascii=False)
    open(IQM_PATH, "a").write("\n")
    json.dump(harmful, open(HARMFUL_PATH, "w"), indent=2, ensure_ascii=False)
    open(HARMFUL_PATH, "a").write("\n")
    json.dump(sb, open(SB_PATH, "w"), indent=2, ensure_ascii=False)
    open(SB_PATH, "a").write("\n")
    json.dump(rules_data, open(RULES_PATH, "w"), indent=2, ensure_ascii=False)
    open(RULES_PATH, "a").write("\n")
    print("\nWrote 4 data files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
