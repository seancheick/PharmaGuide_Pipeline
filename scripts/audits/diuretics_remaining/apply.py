"""Section 1 apply — 4 remaining diuretic records, drug/subclass-specific.

One entry at a time, self-verifying + idempotent. All PMIDs content-verified
against live PubMed (see research.md). `_delete` removes unsupported
`adequacy_threshold_*` comparison amounts (they encode an efficacy assumption the
evidence does not support — better absent, per the Sprint-2 precedent).

Run: python3 scripts/audits/diuretics_remaining/apply.py
"""

import json
import os

SRC = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "data", "medication_depletions.json"
)
REVIEWED_AT = "2026-07-24"
REVIEWER = "lead_clinician_diuretics_remaining"


def pm(label, pmid):
    return {"source_type": "pubmed", "label": label,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"}


PATCHES = {
    "DEP_DIURETICS_CALCIUM": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mg"],
        "severity": "moderate",
        "drug_ref": {"type": "class", "id": "class:loop_diuretics",
                     "display_name": "Loop diuretics (water pills like furosemide)"},
        "mechanism": (
            "Loop diuretics (furosemide, bumetanide, torsemide) inhibit the NKCC2 "
            "transporter in the thick ascending limb, which is also needed for "
            "calcium reabsorption, so more calcium is lost in the urine. Thiazide "
            "diuretics do the opposite and retain calcium."
        ),
        "clinical_impact": (
            "Long-term loop-diuretic use is linked to a modestly higher fracture "
            "risk, mainly in older adults, and part of that may reflect falls "
            "rather than bone loss alone. It is a modest effect and does not by "
            "itself mean a calcium shortfall."
        ),
        "recommendation": (
            "If you take a loop diuretic long-term, aim for adequate dietary "
            "calcium and vitamin D and ask your doctor about bone health. Most "
            "people do not need high-dose calcium supplements."
        ),
        "sources": [
            pm("Rejnmark L et al. Fracture risk in patients treated with loop diuretics. J Intern Med. 2006", 16336519),
            pm("Corrao G et al. Antihypertensive medications, loop diuretics, and risk of hip fracture in the elderly. Drugs Aging. 2015", 26589307),
            pm("Warshaw BL et al. The effect of chronic furosemide administration on urinary calcium excretion and calcium balance in growing rats. Pediatr Res. 1980", 7465281),
        ],
    },
    "DEP_DIURETICS_THIAMINE": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mg"],
        "severity": "significant",
        "drug_ref": {"type": "drug", "id": "4603", "display_name": "Furosemide (Lasix)"},
        "mechanism": (
            "Furosemide increases urine flow, and thiamine is carried out with it, "
            "so urinary thiamine loss rises. The effect tracks with the degree of "
            "diuresis and is greatest with higher doses and long-term use."
        ),
        "clinical_impact": (
            "In people on chronic, higher-dose furosemide — especially for heart "
            "failure — this can lead to thiamine deficiency, which may worsen "
            "heart function and, when severe, affect the nervous system. "
            "Everyday low-dose users with good intake are at much lower risk."
        ),
        "recommendation": (
            "If you take furosemide long-term, especially for heart failure, ask "
            "your doctor about checking thiamine or taking a thiamine-containing "
            "supplement. Do not change your diuretic on your own."
        ),
        "sources": [
            pm("Seligmann H et al. Thiamine deficiency in patients with congestive heart failure receiving long-term furosemide therapy: a pilot study. Am J Med. 1991", 1867241),
            pm("Zenuk C et al. Thiamine deficiency in congestive heart failure patients receiving long term furosemide therapy. Can J Clin Pharmacol. 2003", 14712323),
            pm("Hanninen SA et al. The prevalence of thiamin deficiency in hospitalized patients with congestive heart failure. J Am Coll Cardiol. 2006", 16412860),
            pm("Rieck J et al. Urinary loss of thiamine is increased by low doses of furosemide in healthy volunteers. J Lab Clin Med. 1999", 10482308),
        ],
    },
    "DEP_DIURETICS_FOLATE": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mcg"],
        "severity": "mild",
        "depletion_type": "functional_antagonism",
        "drug_ref": {"type": "drug", "id": "10763",
                     "display_name": "Triamterene (in Dyazide, Maxzide)"},
        "mechanism": (
            "Triamterene is a structural analog of folate and a weak inhibitor of "
            "dihydrofolate reductase, the enzyme that activates folate. At usual "
            "doses cells largely compensate, so the effect on folate status is "
            "modest."
        ),
        "clinical_impact": (
            "For most folate-replete people at normal doses, meaningful folate "
            "depletion is uncommon. The concern is greater in pregnancy (a class "
            "of folate-blocking drugs is linked to higher birth-defect rates), in "
            "people already low in folate, in heavy alcohol use, or when combined "
            "with another folate antagonist such as methotrexate."
        ),
        "recommendation": (
            "Most people on triamterene do not need a folate supplement. If you "
            "are pregnant, planning pregnancy, have low folate, or take "
            "methotrexate, discuss folate with your doctor."
        ),
        "alert_body": (
            "Over long-term use triamterene can mildly interfere with folate, but "
            "at usual doses the effect is small for most people. It matters more "
            "in pregnancy or if folate is already low."
        ),
        "acknowledgement_note": (
            "Good — folate is a sensible thing to cover, especially in pregnancy "
            "or if your folate tends to run low."
        ),
        "monitoring_tip_short": (
            "Consider discussing folate with your doctor if you are pregnant, "
            "planning pregnancy, or also take methotrexate."
        ),
        "sources": [
            pm("Sidhom MB et al. Monitoring the effect of triamterene and hydrochlorothiazide on dihydrofolate reductase activity. J Pharm Biomed Anal. 1989", 2490542),
            pm("Schalhorn A et al. Antifolate effect of triamterene on human leucocytes and on a human lymphoma cell line. Eur J Clin Pharmacol. 1981", 7286039),
            pm("Hernandez-Diaz S et al. Folic acid antagonists during pregnancy and the risk of birth defects. N Engl J Med. 2000", 11096168),
        ],
    },
    "DEP_DIURETICS_ZINC": {
        "_status": "verified",
        "_delete": ["adequacy_threshold_mg"],
        "severity": "mild",
        "drug_ref": {"type": "class", "id": "class:thiazide_diuretics",
                     "display_name": "Thiazide diuretics (e.g., hydrochlorothiazide)"},
        "alert_headline": "Thiazides may lower zinc over time",
        "mechanism": (
            "Thiazide diuretics increase urinary zinc excretion; loop diuretics "
            "have a much smaller effect. Over long-term use this can modestly "
            "lower tissue zinc, although blood zinc usually remains in the normal "
            "range."
        ),
        "clinical_impact": (
            "A clear zinc deficiency from thiazides has not been established — "
            "blood zinc typically stays normal — so this is a mild, long-term "
            "consideration. It is most relevant for people whose dietary zinc is "
            "already low."
        ),
        "recommendation": (
            "A true shortfall is unlikely. If you take a thiazide long-term and "
            "eat little zinc-rich food, a modest zinc intake (10-15 mg/day) or a "
            "multivitamin is reasonable. Zinc from meat, shellfish, and legumes "
            "covers most needs."
        ),
        "alert_body": (
            "Thiazide diuretics can gradually increase urinary zinc loss with "
            "long-term use. Blood zinc usually stays normal, though tissue stores "
            "may drift a little lower over time."
        ),
        "acknowledgement_note": (
            "Good - your zinc intake supports levels while on long-term thiazide "
            "therapy."
        ),
        "sources": [
            pm("Wester PO. Urinary zinc excretion during treatment with different diuretics. Acta Med Scand. 1980", 7001863),
            pm("Golik A et al. Hydrochlorothiazide-amiloride causes excessive urinary zinc excretion. Clin Pharmacol Ther. 1987", 3595066),
            pm("Wester PO. Tissue zinc at autopsy - relation to medication with diuretics. Acta Med Scand. 1980", 7446206),
            pm("Mountokalakis T et al. Zinc deficiency in mild hypertensive patients treated with diuretics. J Hypertens Suppl. 1984", 6152785),
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
