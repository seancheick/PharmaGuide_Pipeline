"""Fix Sprint 01 apply — 4 entries, one at a time, self-verifying + idempotent.

Each edit asserts the entry's pre-state (needs_revision) or skips if already at
target (re-run safe), then sets the audited end-state directly. Run:
    python3 scripts/audits/fix_sprint_01/apply.py
See scripts/audits/fix_sprint_01/research.md for the clinical rationale and the
PubMed-verified citations behind every change.
"""

import json
import os

SRC = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "data", "medication_depletions.json"
)
REVIEWED_AT = "2026-07-23"
REVIEWER = "lead_clinician_fix_sprint_01"

# id -> full field patch (audited end-state). status/reviewed_at/reviewer added
# uniformly below.
PATCHES = {
    "DEP_LEVOTHYROXINE_CALCIUM": {
        "_status": "verified",
        "mechanism": (
            "Calcium supplements and calcium-rich foods bind levothyroxine in "
            "the gastrointestinal tract through a direct physicochemical "
            "interaction, reducing drug absorption rather than depleting body "
            "calcium stores. Levothyroxine adsorbs to calcium carbonate in an "
            "acidic environment, lowering its bioavailability."
        ),
        "clinical_impact": (
            "Taking calcium together with levothyroxine reduces thyroid hormone "
            "absorption and can raise TSH into the underactive range — in a "
            "pharmacokinetic study, levothyroxine uptake fell from about 84% to "
            "58% when taken with a large (2 g) calcium dose. The result can be "
            "inadequate thyroid control and hypothyroid symptoms."
        ),
        "recommendation": (
            "Take levothyroxine at least 4 hours apart from calcium supplements "
            "or calcium-rich meals. If you start, stop, or change calcium "
            "timing, ask your clinician about checking your thyroid levels."
        ),
        "citation_review_note": (
            "Ca–levothyroxine absorption interaction is well-documented (Singh "
            "2000 JAMA, 2001 Thyroid); overstated 40% figure corrected to the "
            "study values and out-of-scope bone-calcium claims removed."
        ),
    },
    "DEP_LEVOTHYROXINE_IRON": {
        "_status": "verified",
        "mechanism": (
            "Iron supplements form an insoluble complex with levothyroxine in "
            "the gut, reducing levothyroxine absorption. This is a drug-nutrient "
            "interaction affecting drug bioavailability rather than a direct "
            "iron depletion; in a controlled trial, taking ferrous sulfate with "
            "levothyroxine raised TSH from 1.6 to 5.4 mU/L over 12 weeks."
        ),
        "clinical_impact": (
            "Co-administration can lead to inadequate thyroid hormone levels and "
            "a return of hypothyroid symptoms; the effect is variable but "
            "clinically significant in some patients."
        ),
        "recommendation": (
            "Take iron supplements at least 4 hours before or after "
            "levothyroxine. If you start or stop iron, ask your clinician about "
            "rechecking your thyroid levels."
        ),
        "sources": [
            {
                "source_type": "pubmed",
                "label": (
                    "Campbell NR et al. Ferrous sulfate reduces thyroxine "
                    "efficacy in patients with hypothyroidism. Ann Intern Med. "
                    "1992;117(12):1010-3"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/1443969/",
            }
        ],
        "citation_review_note": (
            "Placeholder NIH-ODS Iron sheet replaced with the primary "
            "controlled trial (Campbell 1992); unsupported 30–45% figure and "
            "out-of-scope claims (gastric acid, thyroperoxidase) removed."
        ),
    },
    "DEP_OCP_VITAMINB6": {
        "_status": "verified",
        "severity": "moderate",
        "evidence_level": "possible",
        "mechanism": (
            "Estrogen-containing oral contraceptives are associated with lower "
            "plasma pyridoxal-5'-phosphate (the active form of vitamin B6) in "
            "population studies. The effect is modest with today's low-dose "
            "formulations and was larger with the higher-estrogen pills of "
            "earlier decades."
        ),
        "clinical_impact": (
            "The change in B6 status is usually subclinical. The main practical "
            "concern is entering pregnancy with reduced B6 reserves in someone "
            "who stops the pill and conceives soon after."
        ),
        "recommendation": (
            "A normal diet (poultry, fish, potatoes, chickpeas, bananas) or a "
            "standard multivitamin typically provides enough B6 — high-dose B6 "
            "supplements are not recommended, because chronic intake well above "
            "the daily requirement can cause nerve symptoms. If you are planning "
            "pregnancy, discuss B6 and folate with your clinician."
        ),
        "alert_body": (
            "Combined hormonal birth control is linked to modestly lower vitamin "
            "B6 (PLP) levels in some people over months of use. Levels usually "
            "stay in a range that isn't clinically obvious."
        ),
        "monitoring_tip_short": (
            "If you are planning pregnancy, consider discussing B6 and folate "
            "adequacy with your clinician."
        ),
        "adequacy_threshold_mg": 2,
        "sources": [
            {
                "source_type": "pubmed",
                "label": (
                    "Wilson SMC et al. Oral contraceptive use: impact on folate, "
                    "vitamin B6, and vitamin B12 status. Nutr Rev. "
                    "2011;69(10):572-83"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/21967158/",
            },
            {
                "source_type": "reference",
                "label": "NIH ODS — Vitamin B6 Fact Sheet for Health Professionals",
                "url": "https://ods.od.nih.gov/factsheets/VitaminB6-HealthProfessional/",
            },
        ],
        "citation_review_note": (
            "Downgraded to possible evidence (Wilson 2011); 25–50 mg B6 "
            "recommendation cut — chronic high-dose B6 exceeds the EFSA 12 mg UL "
            "(neuropathy risk); reframed around pre-pregnancy adequacy."
        ),
    },
    "DEP_OCP_FOLATE": {
        "_status": "rejected",
        "evidence_level": "possible",
        "sources": [
            {
                "source_type": "pubmed",
                "label": (
                    "Wilson SMC et al. Oral contraceptive use: impact on folate, "
                    "vitamin B6, and vitamin B12 status. Nutr Rev. "
                    "2011;69(10):572-83 — finds current OCs do not negatively "
                    "impact folate status"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/21967158/",
            }
        ],
        "citation_review_note": (
            "Rejected: modern low-dose oral contraceptives do not meaningfully "
            "deplete folate (Wilson 2011, Nutr Rev — older depletion evidence "
            "was confounded and used higher-estrogen pills). Preconception "
            "folate adequacy is standard prenatal guidance independent of OCP "
            "use."
        ),
    },
}


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
        assert e.get("citation_review_status") == "needs_revision", (
            f"{eid}: expected needs_revision, found "
            f"{e.get('citation_review_status')!r} — reconcile before applying"
        )
        for k, v in patch.items():
            if k == "_status":
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
