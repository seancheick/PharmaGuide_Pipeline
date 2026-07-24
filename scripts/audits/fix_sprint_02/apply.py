"""Fix Sprint 02 apply — 3 entries, one at a time, self-verifying + idempotent.

Supports `_delete` for removing unsupported comparison amounts outright (an
`adequacy_threshold_*` that encodes an efficacy assumption is worse than none).
Run: python3 scripts/audits/fix_sprint_02/apply.py
Rationale + field-level audit results: scripts/audits/fix_sprint_02/research.md
"""

import json
import os

SRC = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "data", "medication_depletions.json"
)
REVIEWED_AT = "2026-07-23"
REVIEWER = "lead_clinician_fix_sprint_02"

_SYSTEMIC_CORTICOSTEROID_REF = {
    "type": "class",
    "id": "class:corticosteroids",
    "display_name": "Systemic corticosteroids (prednisone, prednisolone, dexamethasone)",
}
_ACR_2022 = {
    "source_type": "pubmed",
    "label": (
        "Humphrey MB et al. 2022 American College of Rheumatology Guideline for "
        "the Prevention and Treatment of Glucocorticoid-Induced Osteoporosis. "
        "Arthritis Rheumatol. 2023;75(12):2088-2102"
    ),
    "url": "https://pubmed.ncbi.nlm.nih.gov/37845798/",
}

PATCHES = {
    "DEP_STATINS_COQ10": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mg"],
        "severity": "mild",
        "mechanism": (
            "Statins inhibit HMG-CoA reductase, the same early step of the "
            "mevalonate pathway the body uses to make ubiquinone (CoQ10). "
            "Placebo-controlled trials, pooled in a meta-analysis, show statin "
            "therapy lowers CoQ10 concentrations measured in blood."
        ),
        "clinical_impact": (
            "Whether that lower blood level causes the muscle symptoms some "
            "people report on statins is not established, and it does not by "
            "itself indicate a tissue deficiency. Trials of CoQ10 supplements "
            "for statin-related muscle symptoms disagree: some pooled analyses "
            "report improvement, others find no benefit over placebo."
        ),
        "recommendation": (
            "Statins can lower circulating CoQ10 levels. It is uncertain "
            "whether this contributes to muscle symptoms or whether CoQ10 "
            "supplements consistently help. Discuss persistent muscle symptoms "
            "with your prescriber, and do not stop a statin on your own."
        ),
        "monitoring_note": (
            "Routine blood CoQ10 testing is not part of standard care; "
            "persistent muscle symptoms are assessed clinically."
        ),
        "alert_headline": "May lower circulating CoQ10 levels",
        "alert_body": (
            "Statins can lower the amount of CoQ10 measured in the blood. "
            "Whether that causes symptoms is not established."
        ),
        "acknowledgement_note": (
            "You're taking CoQ10. Evidence that it improves statin-related "
            "muscle symptoms is mixed."
        ),
        "monitoring_tip_short": (
            "Consider mentioning any persistent muscle symptoms at your next visit."
        ),
        "food_sources_short": (
            "Dietary CoQ10 is minimal — organ meats and fatty fish contain small "
            "amounts — and the body also makes its own."
        ),
        "sources": [
            {
                "source_type": "pubmed",
                "label": (
                    "Banach M et al. Statin therapy and plasma coenzyme Q10 "
                    "concentrations — a systematic review and meta-analysis of "
                    "placebo-controlled trials. Pharmacol Res. 2015;99:329-36"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/26192349/",
            },
            {
                "source_type": "pubmed",
                "label": (
                    "Ghirlanda G et al. Evidence of plasma CoQ10-lowering effect "
                    "by HMG-CoA reductase inhibitors: a double-blind, "
                    "placebo-controlled study. J Clin Pharmacol. 1993;33(3):226-9"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/8463436/",
            },
            {
                "source_type": "pubmed",
                "label": (
                    "Qu H et al. Effects of coenzyme Q10 on statin-induced "
                    "myopathy: an updated meta-analysis of randomized controlled "
                    "trials. J Am Heart Assoc. 2018;7(19):e009835 — reports "
                    "symptom improvement"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/30371340/",
            },
            {
                "source_type": "pubmed",
                "label": (
                    "Kennedy C et al. Effect of coenzyme Q10 on statin-associated "
                    "myalgia and adherence to statin therapy: a systematic review "
                    "and meta-analysis. Atherosclerosis. 2020;299:1-8 — finds no "
                    "benefit"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/32179207/",
            },
        ],
        "citation_review_note": (
            "Circulating-CoQ10 reduction kept (Banach 2015 meta-analysis, "
            "Ghirlanda 1993). Removed causal myopathy claim, unsupported cardiac "
            "tissue language, routine 100-200 mg recommendation, non-standard "
            "plasma CoQ10 testing, and the 100 mg comparison amount. "
            "Supplementation evidence conflicts (Qu 2018 vs Kennedy 2020) — both "
            "cited; severity lowered to mild."
        ),
    },
    "DEP_CORTICOSTEROIDS_CALCIUM": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mg"],
        "drug_ref": _SYSTEMIC_CORTICOSTEROID_REF,
        "mechanism": (
            "Systemic glucocorticoids reduce intestinal calcium absorption and "
            "increase urinary calcium loss, while also lowering bone formation "
            "and increasing bone resorption. The net effect is negative calcium "
            "balance and bone loss, so the concern is bone strength rather than "
            "a measurable drop in blood calcium."
        ),
        "clinical_impact": (
            "Prolonged systemic glucocorticoid use — more than 3 months at about "
            "2.5 mg/day prednisone-equivalent or more — raises the risk of "
            "osteoporosis and fracture. This applies to tablets and injections "
            "taken over months, not to short courses, inhalers, creams, or a "
            "single joint injection."
        ),
        "recommendation": (
            "With prolonged systemic corticosteroid use, clinicians may assess "
            "calcium and vitamin D intake, fracture risk, and whether "
            "bone-protective treatment is needed. Guideline care is directed by "
            "your individual fracture risk rather than an automatic supplement "
            "dose."
        ),
        "monitoring_note": (
            "American College of Rheumatology guidance recommends assessing "
            "fracture risk soon after starting long-term glucocorticoids — "
            "clinical fracture assessment, bone mineral density with vertebral "
            "fracture assessment, and FRAX scoring for adults 40 and older."
        ),
        "alert_headline": "Can affect calcium balance with long-term systemic use",
        "alert_body": (
            "Taken systemically over months, corticosteroids can reduce calcium "
            "absorption and increase calcium loss, which affects bone strength "
            "over time."
        ),
        "acknowledgement_note": (
            "You're taking calcium. Whether you need it, and how much, depends "
            "on your diet and fracture risk — worth confirming with your "
            "clinician."
        ),
        "monitoring_tip_short": (
            "Consider discussing bone health and fracture-risk screening if "
            "systemic use continues."
        ),
        "sources": [
            _ACR_2022,
            {
                "source_type": "pubmed",
                "label": (
                    "Ferrari P. Cortisol and the renal handling of electrolytes: "
                    "role in glucocorticoid-induced hypertension and bone "
                    "disease. Best Pract Res Clin Endocrinol Metab. "
                    "2003;17(4):575-89"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/14687590/",
            },
        ],
        "citation_review_note": (
            "Scope narrowed to prolonged systemic use (ACR 2022: >3 months at "
            "≥2.5 mg/day); removed the universal 'all patients should take "
            "1,000-1,500 mg calcium' recommendation and the 500 mg comparison "
            "amount (guideline targets TOTAL intake including diet, which the "
            "app cannot observe). Mechanism cited to Ferrari 2003."
        ),
    },
    "DEP_CORTICOSTEROIDS_VITAMIND": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mcg"],
        "depletion_type": "monitoring_stability",
        "severity": "moderate",
        "evidence_level": "probable",
        "drug_ref": _SYSTEMIC_CORTICOSTEROID_REF,
        "mechanism": (
            "Long-term systemic glucocorticoid therapy increases bone loss and "
            "fracture risk, and vitamin D status is assessed as part of that "
            "bone-health management. There is no reliable evidence that "
            "corticosteroids themselves directly lower vitamin D levels — "
            "studies reporting low vitamin D in steroid-treated patients are "
            "confounded by the underlying illness and reduced sun exposure."
        ),
        "clinical_impact": (
            "Vitamin D matters here because of bone health during prolonged "
            "steroid therapy, not because the medication drains it."
        ),
        "recommendation": (
            "With prolonged systemic corticosteroid use, clinicians commonly "
            "assess vitamin D status and intake as part of bone-health "
            "management. Ask your clinician whether testing or supplementation "
            "is appropriate for you — there is no universal dose."
        ),
        "monitoring_note": (
            "American College of Rheumatology guidance recommends assessing "
            "fracture risk soon after starting long-term glucocorticoids; "
            "vitamin D status is commonly reviewed alongside it."
        ),
        "alert_headline": "Vitamin D is monitored during long-term steroid use",
        "alert_body": (
            "Long-term systemic corticosteroid use raises bone-loss risk, so "
            "clinicians often review vitamin D as part of bone care. This is a "
            "monitoring consideration, not a sign the medication drains "
            "vitamin D."
        ),
        "acknowledgement_note": (
            "You're taking vitamin D. Whether you need it, and how much, is "
            "worth confirming with your clinician."
        ),
        "monitoring_tip_short": (
            "Consider asking whether a vitamin D check fits your bone-health plan."
        ),
        "sources": [_ACR_2022],
        "citation_review_note": (
            "Retyped depletion → monitoring_stability: no reliable human "
            "evidence of a direct corticosteroid-driven vitamin D depletion "
            "(Peracchi 2014 found no association with medication intake; other "
            "reports are confounded cross-sectional or veterinary). The "
            "'hepatic CYP24A1 induction' mechanism was removed as unsupported "
            "(CYP24A1 is the renal/target-tissue 24-hydroxylase). Vitamin D "
            "assessment during prolonged systemic GC therapy is guideline-backed "
            "(ACR 2022)."
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
