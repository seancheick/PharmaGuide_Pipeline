"""Section 2 apply — 4 remaining acid-reduction records, re-scoped by evidence.

iron → PPI+H2 (new class:acid_suppressants); calcium → PPI-only; vitamin C and
zinc REJECTED as depletion warnings (evidence supports only acute fasting
supplement-salt absorption / unclear-significance plasma dips — documented, not a
data gap). All PMIDs content-verified against live PubMed (see research.md).
`_delete` drops unsupported adequacy_threshold_* comparison amounts.

Run: python3 scripts/audits/acid_reduction/apply.py
"""

import json
import os

SRC = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "data", "medication_depletions.json"
)
REVIEWED_AT = "2026-07-24"
REVIEWER = "lead_clinician_acid_reduction"


def pm(label, pmid):
    return {"source_type": "pubmed", "label": label,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"}


PATCHES = {
    "DEP_ANTACIDS_IRON": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mg"],
        "severity": "moderate",
        "drug_ref": {"type": "class", "id": "class:acid_suppressants",
                     "display_name": "Acid reducers (PPIs and H2 blockers)"},
        "mechanism": (
            "Gastric acid reduces dietary non-heme iron (Fe3+) to the absorbable "
            "ferrous form (Fe2+) and frees iron from food. Both PPIs and H2 "
            "blockers suppress acid, so long-term use can lower non-heme iron "
            "absorption; the effect is dose-related and reverses after stopping."
        ),
        "clinical_impact": (
            "Over months to years this can contribute to iron deficiency and, if "
            "unaddressed, iron-deficiency anemia — most relevant for menstruating "
            "women, frequent blood donors, and people with low dietary iron. Heme "
            "iron from meat is less affected."
        ),
        "recommendation": (
            "If you take a PPI or H2 blocker long-term and are at risk (menstruating, "
            "low iron, plant-based diet), ask your doctor to check ferritin. Take any "
            "iron supplement a couple of hours apart from your acid reducer, and with "
            "vitamin C to aid absorption."
        ),
        "sources": [
            pm("Lam JR et al. Proton pump inhibitor and histamine-2 receptor antagonist use and iron deficiency. Gastroenterology. 2017", 27890768),
            pm("Hutchinson C et al. Proton pump inhibitors suppress absorption of dietary non-haem iron in hereditary haemochromatosis. Gut. 2007", 17344278),
        ],
    },
    "DEP_ANTACIDS_CALCIUM": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mg"],
        "severity": "moderate",
        "drug_ref": {"type": "class", "id": "class:proton_pump_inhibitors",
                     "display_name": "Proton pump inhibitors (PPIs)"},
        "alert_body": (
            "Long-term PPI use can gradually reduce how well calcium carbonate is "
            "absorbed, which over years may influence bone strength. H2 blockers "
            "and occasional antacids are not a concern here."
        ),
        "mechanism": (
            "Stomach acid converts insoluble calcium carbonate into absorbable "
            "ionized calcium. PPIs strongly suppress acid, so calcium carbonate "
            "taken on an empty stomach is absorbed less well. Calcium citrate does "
            "not need acid, and taking carbonate with food restores absorption."
        ),
        "clinical_impact": (
            "Long-term PPI use is linked in observational studies to a modestly "
            "higher fracture risk (hip, wrist, spine), behind a 2010 FDA safety "
            "communication. The association is modest and partly confounded, and is "
            "not seen with H2 blockers."
        ),
        "recommendation": (
            "If you take a PPI long-term, prefer calcium citrate (it does not need "
            "stomach acid to absorb) or take calcium carbonate with a meal. Aim for "
            "adequate calcium and vitamin D, and ask your doctor about bone health."
        ),
        "sources": [
            pm("Recker RR. Calcium absorption and achlorhydria. N Engl J Med. 1985", 4000241),
            pm("O'Connell MB et al. Effects of proton pump inhibitors on calcium carbonate absorption in women: a randomized crossover trial. Am J Med. 2005", 15989913),
            pm("Yang YX et al. Long-term proton pump inhibitor therapy and risk of hip fracture. JAMA. 2006", 17190895),
            pm("Poly TN et al. Proton pump inhibitors and risk of hip fracture: a meta-analysis of observational studies. Osteoporos Int. 2019", 30539272),
            pm("Serfaty-Lacrosniere C et al. Hypochlorhydria from short-term omeprazole treatment does not inhibit intestinal absorption of calcium, phosphorus, magnesium or zinc from food in humans. J Am Coll Nutr. 1995", 8568113),
        ],
    },
    "DEP_ANTACIDS_VITAMINC": {
        "_status": "rejected",
        "_delete": ["adequacy_threshold_mg"],
        "citation_review_note": (
            "Rejected as a consumer depletion warning (evidence-based, not a data "
            "gap). Only one small systemic study (Henry 2005: omeprazole 40 mg x 4 wk "
            "→ plasma vitamin C -12.3%, authors state 'clinical significance is "
            "unclear', concentrated in H. pylori+/low-baseline). The remaining "
            "literature is intragastric gastric-juice ascorbate (an N-nitrosation/"
            "cancer mechanism, not body vitamin C status). No clinically meaningful "
            "depletion; no H2/antacid data. Retired the Pelton handbook citation."
        ),
        "sources": [
            pm("Henry EB et al. Proton pump inhibitors reduce the bioavailability of dietary vitamin C. Aliment Pharmacol Ther. 2005", 16167970),
            pm("Mowat C et al. Omeprazole and dietary nitrate independently affect levels of vitamin C and nitrite in gastric juice. Gastroenterology. 1999", 10092303),
        ],
    },
    "DEP_ANTACIDS_ZINC": {
        "_status": "rejected",
        "_delete": ["adequacy_threshold_mg"],
        "citation_review_note": (
            "Rejected as a consumer depletion warning (evidence-based, not a data "
            "gap). Support exists only for reduced acute absorption of a fasting "
            "soluble zinc-salt load (H2: Sturniolo 1991; PPI: Ozutemiz 2002) — a "
            "supplement-timing pharmacokinetic effect. A food-based study "
            "(Serfaty-Lacrosniere 1995) found NO change in zinc absorption from a "
            "meal, and no study shows actual zinc deficiency from acid suppression. "
            "Retired the Pelton handbook citation."
        ),
        "sources": [
            pm("Sturniolo GC et al. Inhibition of gastric acid secretion reduces zinc absorption in man. J Am Coll Nutr. 1991", 1894892),
            pm("Ozutemiz AO et al. Effect of omeprazole on plasma zinc levels after oral zinc administration. Indian J Gastroenterol. 2002 (PMID 12546170)", 12546170),
            pm("Serfaty-Lacrosniere C et al. Hypochlorhydria from short-term omeprazole treatment does not inhibit intestinal absorption of calcium, phosphorus, magnesium or zinc from food in humans. J Am Coll Nutr. 1995", 8568113),
        ],
    },
}

_ALLOWED_PRE = {None, "unverified", "needs_revision"}


def main():
    with open(SRC, encoding="utf-8") as f:
        doc = json.load(f)
    by = {e["id"]: e for e in doc["depletions"]}

    changed = 0
    for eid, patch in PATCHES.items():
        e = by[eid]
        target = patch["_status"]
        if e.get("citation_review_status") == target and e.get("reviewer") == REVIEWER:
            print(f"  = {eid} already at {target} (skip)")
            continue
        cur = e.get("citation_review_status")
        assert cur in _ALLOWED_PRE, (
            f"{eid}: expected one of {_ALLOWED_PRE}, found {cur!r} — reconcile before applying"
        )
        for key in patch.get("_delete", []):
            e.pop(key, None)
        for k, v in patch.items():
            if k in ("_status", "_delete"):
                continue
            e[k] = v
        e["citation_review_status"] = target
        e["reviewed_at"] = REVIEWED_AT
        e["reviewer"] = REVIEWER
        changed += 1
        print(f"  ✓ {eid} -> {target}")

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"applied {changed} change(s)")


if __name__ == "__main__":
    main()
