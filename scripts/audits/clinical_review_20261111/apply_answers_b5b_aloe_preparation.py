"""Batch 5b of Dr. Pham's signed answers (2026-11-12): aloe preparation identity for the digoxin warning.

Authority: DR_PHAM_ANSWERS_20261112.md Part A, section 2 ("Senna, cascara and aloe with digoxin"): keep "avoid
unsupervised use" with potassium-loss and preparation context. Oral latex / dried leaf juice preparations reach the
warning; verified inner-leaf gel and topical-only products do not inherit it indiscriminately; whole leaf of unknown
processing stays uncertain. Fix the preparation mapping, not by aliasing all Aloe vera to Aloe ferox.

- RULE_IQM_ALOE_FEROX was authored on the IQM species identity aloe_ferox. A label row of Aloe vera latex carries
  the RISK_ALOE_LATEX safety identity but no aloe_ferox identity, so it met no finding; "Aloe ferox gel", an IQM
  aloe_ferox alias, met all of them. The rule moves onto RISK_ALOE_LATEX, the preparation identity: its aliases
  name the latex of both species, and its negative terms (gel, inner leaf, acemannan, polysaccharide) keep gel out.
  Every non-gel aloe_ferox name already matches RISK_ALOE_LATEX (a test holds this), and the four corpus products
  that met the rule (267819, 273379, 337239, 333705) all carry the latex flag. The rule id is kept: it is a stable
  reference in tests and release receipts.
- RISK_ALOE_LATEX gains "aloe barbadensis latex": Aloe barbadensis is Aloe vera, whose latex ("aloe vera latex")
  is already an alias, and the monograph names Barbados aloes.
- The digoxin row gets the section-2 wording used for senna and cascara (batch 5a), with the aloe monograph's own
  4.4 and 4.5 text and the preparation scope.
- Topical-only products: none in the corpus carries an aloe latex row, the monograph's pharmaceutical form is oral, and
  the latex identity names oral laxative preparations. No `product_forms_any: ["topical_only"]` exclusion is added: it
  would change no product today and would make each hard row unexpressible by alerts (`rule_change_gate.py::
  _alert_can_express`), so review-class at the release gate.
- The pregnancy row's mechanism named Cape aloe latex only; it now names Cape or Barbados aloes, which it reaches.
- Side effect, held for Dr. Pham: a label row named "Aloe ferox gel" met this whole rule before and now meets no aloe
  rule. No raw label in the corpus (15,414 scanned) names a Cape aloe gel; the only Cape aloe rows are the four above.

Agent wording; the decision is Dr. Pham's. Sources: EU herbal monograph EMA/HMPC/625788/2015 (Aloe barbadensis and
Aloe ferox, folii succus siccatus), sections 2, 3, 4.4 and 4.5, read 2026-11-12; NCCIH "Aloe Vera" (gel from the inner
leaf, latex from the outer layer, whole crushed leaf has both; latex overuse and cardiac glycosides), read 2026-11-12;
LANOXIN (setid d91e3646) 5.3.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

DATA = REPO / "scripts/data"
RULES = DATA / "ingredient_interaction_rules.json"
BANNED = DATA / "banned_recalled_ingredients.json"
ANSWERS = "audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md"
TODAY = "2026-11-12"
LANOXIN = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d91e3646-4c63-4512-ab22-db39c085c4dc"
AGENT = " Wording and sources (mechanism, action and alert text) prepared by agent, not reviewed by Dr. Pham."
LATEX = {"db": "banned_recalled_ingredients", "canonical_id": "RISK_ALOE_LATEX"}

DIGOXIN = {
    "mechanism": (
        "Prolonged or excessive stimulant-laxative use can cause potassium loss, which can increase digoxin toxicity "
        "risk. NCCIH says overuse of aloe latex may increase the risk of adverse effects from cardiac glycosides such "
        "as digoxin. The EU herbal monograph for the dried leaf juice of Aloe barbadensis and Aloe ferox (Barbados and "
        "Cape aloes) says hypokalaemia resulting from long-term laxative abuse potentiates the action of cardiac "
        "glycosides (4.5), and that patients taking cardiac glycosides have to consult a doctor before taking aloes "
        "concomitantly (4.4). It sets no dose or duration that clears the combination and does not show that every "
        "brief use causes toxicity. NCCIH separates aloe latex, from the leaf's outer layer, from inner-leaf gel; "
        "this warning follows the latex."
    ),
    "action": (
        "If you take digoxin or another cardiac glycoside, do not use aloe latex products without your prescriber's "
        "advice. They may check your potassium."
    ),
    "alert_headline": "Avoid unsupervised use with digoxin",
    "alert_body": (
        "Prolonged or excessive use of aloe latex can lower potassium and raise the risk of digoxin side effects. If "
        "you take digoxin, do not use this product without your prescriber's advice."
    ),
    "informational_note": "Prolonged or heavy aloe latex use can lower potassium, which matters for people taking digoxin.",
    "clinical_review": {
        "reviewer": "Dr. Pham",
        "reviewed_at": TODAY,
        "file": ANSWERS,
        "notes": (
            "Section 2 (Dr. Pham): keep 'avoid unsupervised use,' with potassium-loss and preparation context. "
            "'Relevant oral latex/dried leaf juice preparations should reach the warning. Verified inner-leaf gel and "
            "topical-only products should not inherit it indiscriminately. \"Whole leaf\" with unknown processing "
            "should remain uncertain.' Agent implementation, not reviewed by Dr. Pham: the rule sits on the latex "
            "identity, so gel and whole leaf of unknown processing show no latex finding (no uncertain-preparation "
            "display exists), and no topical-only exclusion is added." + AGENT
        ),
    },
}
# The pregnancy row now also reaches Barbados aloe latex; its text named Cape aloe only.
PREGNANCY_MECHANISM = (
    "Aloe latex (Cape or Barbados aloes) contains anthranoid laxatives, including emodin and aloe-emodin, that showed "
    "genotoxic potential in experimental studies, so the EU herbal monograph contraindicates aloes in pregnancy."
)
OLD_PREGNANCY_MECHANISM = (
    "Cape aloe latex contains anthranoid laxatives, including emodin and aloe-emodin, that showed genotoxic potential "
    "in experimental studies, so the EU herbal monograph contraindicates aloes in pregnancy."
)
OWNER = (
    "Dr. Pham (signed answers 2026-11-12, section 2: keep 'avoid unsupervised use' on the cardiac-glycoside row, with "
    "preparation context); wording and the latex-identity subject by agent, not reviewed by Dr. Pham; other rows: "
    "original rule pharmaguide_clinical_team"
)


def check_copy(sub: dict) -> None:
    for key, lo, hi in (("alert_headline", 20, 60), ("alert_body", 60, 200), ("informational_note", 40, 120)):
        assert lo <= len(sub[key]) <= hi, (key, len(sub[key]), sub[key])


def rules(blob: dict) -> None:
    [rule] = [r for r in blob["interaction_rules"] if r["id"] == "RULE_IQM_ALOE_FEROX"]
    assert rule["subject_ref"] == {"db": "ingredient_quality_map", "canonical_id": "aloe_ferox"}
    assert rule["review_owner"] == "pharmaguide_clinical_team"
    rule["subject_ref"] = dict(LATEX)
    [digoxin] = [d for d in rule["drug_class_rules"] if d["drug_class_id"] == "cardiac_glycosides"]
    assert digoxin["severity"] == "avoid" and "clinical_review" not in digoxin
    digoxin.update(DIGOXIN)
    if LANOXIN not in digoxin["sources"]:
        digoxin["sources"].append(LANOXIN)
    check_copy(digoxin)
    [pregnancy] = [c for c in rule["condition_rules"] if c["condition_id"] == "pregnancy"]
    assert pregnancy["mechanism"] == OLD_PREGNANCY_MECHANISM
    pregnancy["mechanism"] = PREGNANCY_MECHANISM
    rule["review_owner"] = OWNER
    rule["last_reviewed"] = TODAY


def banned(blob: dict) -> None:
    [entry] = [e for e in blob["ingredients"] if e["id"] == "RISK_ALOE_LATEX"]
    assert "aloe barbadensis latex" not in entry["aliases"]
    entry["aliases"].insert(entry["aliases"].index("aloe vera latex") + 1, "aloe barbadensis latex")
    entry["review"]["change_log"].append({
        "date": TODAY,
        "change": (
            "Added alias 'aloe barbadensis latex' (Barbados aloes; A. barbadensis is A. vera, whose latex was already "
            "an alias). The aloe digoxin, antiarrhythmic, diuretic, pregnancy, kidney and liver interaction rule "
            "(RULE_IQM_ALOE_FEROX) now sits on this identity: agent implementation of Dr. Pham's section 2 direction "
            "(signed answers 2026-11-12: preparation context), so the negative terms that keep inner-leaf gel out of "
            "this entry also keep it out of that rule."
        ),
        "by": "claude_interaction_lane",
    })


if __name__ == "__main__":
    for path, edit in ((RULES, rules), (BANNED, banned)):
        blob = data_batch.load(path)
        edit(blob)
        data_batch.save(path, blob)
