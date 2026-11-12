"""Batch 5a of Dr. Pham's signed answers (2026-11-12): vitamin E wording (Q2) and senna/cascara with digoxin.

Authority: DR_PHAM_ANSWERS_20261112.md Part A, Q2 and section 2 ("Senna, cascara and aloe with digoxin"), as recorded
in DISPOSITIONS_20261111.md.

- Vitamin E (Q2): remove wording that presents 400 IU/day as a proven onset threshold or calls the effect "mild". The
  NIH fact sheet says the amount needed for clinically significant interactions is unknown but probably exceeds
  400 IU/day; that is not a boundary below which the interaction disappears. The Schurks 2010 abstract gives no
  400 IU/day anchor, so the "anchored to ~400 IU/day" sentence goes too. Numerical suppression stays held: dose
  thresholds, materiality and dose gates are unchanged. The surgery row's alert text and action are not changed here.
- Senna and cascara with digoxin (section 2): keep "avoid unsupervised use" with potassium-loss context. The headline
  no longer says the laxative itself increases digoxin toxicity, the body no longer narrows the advice to prolonged
  use, and the actions no longer hand the consumer clinician tasks (choose an osmotic agent, monitor serum levels).
  "They may check your potassium" follows the LANOXIN label (assess serum electrolytes periodically). Aloe goes with
  the preparation mapping in batch 5b.

Agent wording; the decisions are Dr. Pham's. Sources: NIH ODS vitamin E fact sheet (read 2026-11-12, "Anticoagulant and
antiplatelet medications"); PMID 21051774 abstract (read 2026-11-12); EU herbal monographs for senna leaf and pod and
cascara bark, sections 4.4 and 4.5, verbatim in audits/interaction_rules/laxative_resourcing_2026_09/research.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

RULES = REPO / "scripts/data/ingredient_interaction_rules.json"
ANSWERS = "audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md"
TODAY = "2026-11-12"
AGENT = " Wording and sources (mechanism, action and alert text) prepared by agent, not reviewed by Dr. Pham."


def review(notes: str) -> dict:
    return {"reviewer": "Dr. Pham", "reviewed_at": TODAY, "file": ANSWERS, "notes": notes + AGENT}


def check_copy(sub: dict) -> None:
    """The safety-copy validator's length windows, checked before writing."""
    for key, lo, hi in (("alert_headline", 20, 60), ("alert_body", 60, 200), ("informational_note", 40, 120)):
        if sub.get(key):
            assert lo <= len(sub[key]) <= hi, (key, len(sub[key]), sub[key])


ODS_SENTENCE = (
    "The NIH Office of Dietary Supplements says large doses taken with anticoagulant or antiplatelet medicines such as "
    "warfarin can increase bleeding risk, especially with low vitamin K intake, and that the supplemental amount needed "
    "for clinically significant effects is unknown but probably exceeds 400 IU/day. That figure is not an established "
    "threshold below which the interaction disappears."
)
Q2_NOTE = "Q2: 400 IU/day is not a boundary below which the interaction disappears; the effect is not necessarily mild."

VITAMIN_E_ANTICOAGULANTS = {
    "mechanism": (
        "Vitamin E can inhibit platelet aggregation and antagonize vitamin K-dependent clotting factors. " + ODS_SENTENCE
    ),
    "action": (
        "If you take a blood thinner, talk to your prescriber before using vitamin E supplements, and tell them how "
        "much you take."
    ),
    "alert_body": (
        "Large doses of vitamin E can affect clotting and add to bleeding risk with blood thinners. The amount that "
        "matters is not known. Talk to your prescriber before taking vitamin E."
    ),
    "informational_note": "Vitamin E at high doses can have an antiplatelet effect — relevant to anyone on blood thinners.",
    "clinical_review": review(Q2_NOTE),
}
VITAMIN_E_BLEEDING = {
    "mechanism": (
        "Vitamin E inhibits platelet aggregation and antagonizes vitamin K-dependent clotting factors. A meta-analysis "
        "of randomized trials found a 22% increased risk of hemorrhagic stroke (Schurks 2010, pooled RR 1.22). The "
        "NIH fact sheet says the supplemental amount needed for clinically significant medication interactions is unknown but probably exceeds "
        "400 IU/day, which is not an established threshold. The risk adds to anticoagulant or antiplatelet use."
    ),
    "alert_body": (
        "High-dose vitamin E can raise bleeding risk; the amount that matters is not established. If you have a "
        "bleeding disorder or take blood thinners, review vitamin E use with your clinician."
    ),
    "last_reviewed": TODAY,
    "clinical_review": review(Q2_NOTE),
}
VITAMIN_E_SURGERY = {
    "mechanism": (
        "Vitamin E inhibits platelet aggregation and antagonizes vitamin K-dependent clotting factors, which can raise "
        "perioperative bleeding risk at high supplemental doses; the amount that matters is not established."
    ),
    "last_reviewed": TODAY,
    "clinical_review": review(
        Q2_NOTE + " Only the mechanism changed in this row; its alert text and action predate this review and were "
        "not reviewed by Dr. Pham."
    ),
}


def laxative(name: str, monograph: str, plural: bool) -> dict:
    says, sets, shows = ("say", "They set", "do not show") if plural else ("says", "It sets", "does not show")
    return {
        "mechanism": (
            "Prolonged or excessive stimulant-laxative use can cause potassium loss, which can increase digoxin "
            f"toxicity risk. The EU herbal {monograph} {says} hypokalaemia resulting from long-term laxative abuse "
            "potentiates the action of cardiac glycosides (4.5), and that patients taking cardiac glycosides have to "
            f"consult a doctor (4.4). {sets} no dose or duration that clears the combination and {shows} that "
            "every brief use causes toxicity."
        ),
        "action": (
            f"If you take digoxin or another cardiac glycoside, do not use {name} without your prescriber's advice. "
            "They may check your potassium."
        ),
        "alert_headline": "Avoid unsupervised use with digoxin",
        "alert_body": (
            "Prolonged or excessive laxative use can lower potassium and raise the risk of digoxin side effects. If "
            "you take digoxin, do not use this laxative without your prescriber's advice."
        ),
        "informational_note": f"Prolonged or heavy {name} use can lower potassium, which matters for people taking digoxin.",
        "clinical_review": review(
            "Section 2: keep 'avoid unsupervised use,' with potassium-loss and preparation context; the monographs "
            "require medical consultation and set no dose or duration cutoff. Her preparation guidance names aloe, "
            "which batch 5b handles."
        ),
    }


LAXATIVES = {
    "RULE_IQM_SENNA_PREGNANCY": laxative("senna", "monographs for senna leaf and pod", plural=True),
    "RULE_IQM_CASCARA_SAGRADA_PREGNANCY": laxative("cascara", "monograph for cascara bark", plural=False),
}
LAXATIVE_OWNER = (
    "Dr. Pham (signed answers 2026-11-12, section 2: keep 'avoid unsupervised use' on the cardiac-glycoside row "
    "only); wording by agent, not reviewed by Dr. Pham; other rows: original rule pharmaguide_clinical_team, agent "
    "re-sourcing 2026-04-26"
)


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}

    vitamin_e = by_id["RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS"]
    [anticoagulants] = vitamin_e["drug_class_rules"]
    assert anticoagulants["drug_class_id"] == "anticoagulants" and anticoagulants.get("clinical_review") is None
    conditions = {c["condition_id"]: c for c in vitamin_e["condition_rules"]}
    for sub, update in ((anticoagulants, VITAMIN_E_ANTICOAGULANTS), (conditions["bleeding_disorders"], VITAMIN_E_BLEEDING),
                        (conditions["surgery_scheduled"], VITAMIN_E_SURGERY)):
        assert sub.get("clinical_review") is None
        sub.update(update)
        check_copy(sub)
    vitamin_e["review_owner"] += "; Q2 wording 2026-11-12 (Dr. Pham signed the policy; wording by agent)"
    vitamin_e["last_reviewed"] = TODAY

    for rule_id, update in LAXATIVES.items():
        rule = by_id[rule_id]
        [digoxin] = [d for d in rule["drug_class_rules"] if d["drug_class_id"] == "cardiac_glycosides"]
        assert digoxin["severity"] == "avoid" and digoxin.get("clinical_review") is None
        digoxin.update(update)
        check_copy(digoxin)
        assert rule["review_owner"] == "pharmaguide_clinical_team", rule_id
        rule["review_owner"] = LAXATIVE_OWNER
        rule["last_reviewed"] = TODAY


if __name__ == "__main__":
    blob = data_batch.load(RULES)
    rules(blob)
    data_batch.save(RULES, blob)
