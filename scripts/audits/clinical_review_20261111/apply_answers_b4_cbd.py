"""Batch 4 of Dr. Pham's signed answers (2026-11-12): the CBD named-medicine split.

Authority: DR_PHAM_ANSWERS_20261112.md Part A, Q5, as recorded in DISPOSITIONS_20261111.md (F7).

- One finding per named medicine, each with the claim its source supports (EPIDIOLEX label, read 2026-11-12, effective
  2026-05-29; PMID 39601108 for tacrolimus):
  clobazam (raised active metabolite, sleepiness), valproate (more liver-enzyme rises, not raised valproate levels),
  stiripentol (raised levels), everolimus (raised levels; the specialist manages levels and dosing), tacrolimus
  (raised levels in a controlled study), sirolimus (label precaution plus measured trough rises in an observational
  series, PMID 31924480), and oral digoxin (a potential P-gp interaction not measured with that medicine).
- Other seizure medicines keep a qualified review message; the whole-class "may affect seizure medication" claim ends.
- The immunosuppressant sub-rule is narrowed away: only the named medicines get a CBD finding. Mycophenolate (label:
  mycophenolic-acid AUC +35%) goes on the review list, not into a finding. A profile with only the "Immunosuppressants"
  picker class loses the CBD finding; that consequence is held for Dr. Pham (DISPOSITIONS batch 4, H1).
- The "Digoxin / Heart rhythm medication" picker class also reaches the digoxin finding, whose copy is conditional on
  digoxin taken by mouth (Q4: an unknown medicine keeps a conditional message rather than none).
- The seizure-disorder condition keeps its guidance with an accurate claim; no instruction to change a prescription dose.
- Rule-only vocabulary entries reuse their parent class's approved strings verbatim. Dr. Pham's Q5 sentences for
  clobazam and valproate need adapting to the vocabulary contract ("Commonly used ...", one sentence, no "treat"), and
  the vocabulary's sign-off rule makes any new string wait for her confirmation, so the adaptations are held.

Agent implementation, wording, membership, severity and evidence grading; the findings and scope are Dr. Pham's (Q5).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

DATA = REPO / "scripts/data"
RULES = DATA / "ingredient_interaction_rules.json"
CLASSES = DATA / "drug_classes.json"
TAXONOMY = DATA / "clinical_risk_taxonomy.json"
VOCAB = DATA / "drug_class_vocab.json"

ANSWERS = "audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md"
TODAY = "2026-11-12"
EPIDIOLEX = "https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=8bf27097-4870-43fb-94f0-f3d0871d1eec&type=display"
TACROLIMUS_PK = "https://pubmed.ncbi.nlm.nih.gov/39601108/"
SIROLIMUS_OBSERVATIONAL = "https://pubmed.ncbi.nlm.nih.gov/31924480/"
FDA_CBD = ("https://www.fda.gov/news-events/public-health-focus/"
           "fda-regulation-cannabis-and-cannabis-derived-products-including-cannabidiol-cbd")
RULE_ID = "RULE_BANNED_CBD_INTERACTIONS"

# Single-medicine rule classes: RxNorm ingredient (IN) RxCUIs, active, and RxClass ATC classes, read 2026-11-12.
# (rxcui, display name, ATC classes, primary ATC class for the medicine's systemic use, parent rule class whose
# approved vocabulary strings the entry reuses)
NEW_CLASSES = {
    "stiripentol": ("2054968", "Stiripentol", ["N03AX"], "N03AX", "anticonvulsants"),
    "everolimus": ("141704", "Everolimus", ["L01EG", "L04AH"], "L04AH", "immunosuppressants"),
    "tacrolimus": ("42316", "Tacrolimus", ["D11AH", "L04AD"], "L04AD", "immunosuppressants"),
    "sirolimus": ("35302", "Sirolimus", ["L01EG", "L04AH", "S01XA"], "L04AH", "immunosuppressants"),
    "digoxin": ("3407", "Digoxin", ["C01AA"], "C01AA", "cardiac_glycosides"),
}
# Rule-only vocabulary entries for the two medicines that already had gate classes: (name, examples, parent class
# whose approved strings they reuse). Dr. Pham's Q5 sentences are held for her confirmation of the adaptation.
NAMED_VOCAB = {
    "clobazam": ("Clobazam", ["clobazam (Onfi, Sympazan)"], "anticonvulsants"),
    "valproate": ("Valproate medicines", ["valproic acid", "sodium valproate", "divalproex (Depakote)"],
                  "anticonvulsants"),
}


def review(notes: str) -> dict:
    """Dr. Pham signed the findings and scope; everything else is agent work, not reviewed by Dr. Pham."""
    return {"reviewer": "Dr. Pham", "reviewed_at": TODAY, "file": ANSWERS,
            "notes": notes + " Consumer wording, membership, severity and evidence grading: agent work, not reviewed "
                             "by Dr. Pham."}


REVIEW_OWNER = (
    "Dr. Pham (signed answers 2026-11-12, Q5: the seizure-medicine, immunosuppressant and digoxin findings and the "
    "seizure-condition note; findings and scope only); wording, membership, severity, evidence grading and labels read "
    "by agent; the anticoagulant, sedative and pregnancy sub-rules are unchanged from the original rule "
    "(drug_label_mining)"
)


def check_copy(sub: dict) -> None:
    for key, lo, hi in (("alert_headline", 20, 60), ("alert_body", 60, 200), ("informational_note", 40, 120)):
        if sub.get(key):
            assert lo <= len(sub[key]) <= hi, (key, len(sub[key]), sub[key])


def gate(requires: list[str], excludes: list[str] | None = None) -> dict:
    return {
        "gate_type": "drug_class",
        "requires": {"conditions_any": [], "drug_classes_any": requires, "profile_flags_any": []},
        "excludes": {"conditions_any": [], "drug_classes_any": excludes or [], "profile_flags_any": [],
                     "product_forms_any": [], "nutrient_forms_any": []},
        "dose": None,
    }


PRESCRIPTION_SCOPE = (
    " These findings concern the studied prescription oral cannabidiol; the size of the effect for over-the-counter or "
    "topical CBD products is not established."
)


def finding(class_id, severity, evidence, mechanism, action, headline, body, note, sources, decision,
            requires=None) -> dict:
    sub = {
        "drug_class_id": class_id, "severity": severity, "evidence_level": evidence, "mechanism": mechanism,
        "action": action, "sources": sources, "alert_headline": headline, "alert_body": body,
        "informational_note": note, "profile_gate": gate(requires or [class_id]), "direction": "harmful",
        "materiality": "presence", "clinical_review": review(decision),
    }
    check_copy(sub)
    return sub


NAMED = [
    finding(
        "clobazam", "caution", "established",
        "The EPIDIOLEX label reports that prescription cannabidiol raised N-desmethylclobazam, clobazam's active "
        "metabolite, about 3-fold in healthy subjects, with no effect on clobazam itself, which may increase "
        "clobazam-related adverse reactions such as sleepiness and sedation." + PRESCRIPTION_SCOPE,
        "If you take clobazam, talk to your neurologist before using CBD and tell them about new sleepiness or other "
        "side effects. Do not change your clobazam dose yourself.",
        "May increase clobazam side effects such as sleepiness",
        "Prescription CBD raised levels of clobazam's active form, which can add to sleepiness. If you take clobazam, "
        "talk to your neurologist before using CBD.",
        "Prescription CBD raised levels of clobazam's active form in label studies.",
        [EPIDIOLEX],
        "Q5: increased exposure to clobazam's active metabolite; greater sedation risk.",
    ),
    finding(
        "valproate", "caution", "established",
        "The EPIDIOLEX label reports that liver-enzyme (transaminase) elevations were more common when prescription "
        "cannabidiol was taken with valproate: most ALT elevations in the controlled studies occurred in patients "
        "taking valproate. Cannabidiol did not raise valproate exposure (no effect in healthy subjects; small, not "
        "clinically relevant decreases in patients)." + PRESCRIPTION_SCOPE,
        "If you take a valproate medicine, talk to your prescriber before using CBD; liver blood tests may be needed. "
        "Do not change your valproate dose yourself.",
        "Liver enzymes rose more often with valproate",
        "With valproate, prescription CBD raised liver enzymes more often in label studies. If you take valproate, "
        "talk to your prescriber before using CBD; liver tests may be needed.",
        "Prescription CBD with valproate raised liver enzymes more often in label studies.",
        [EPIDIOLEX],
        "Q5: greater liver-enzyme elevation risk; not described as increased valproate exposure.",
    ),
    finding(
        "stiripentol", "caution", "established",
        "The EPIDIOLEX label reports that prescription cannabidiol raised stiripentol exposure (AUC up 55% in healthy "
        "subjects and 30% in patients with epilepsy) and advises monitoring for stiripentol-related adverse "
        "reactions." + PRESCRIPTION_SCOPE,
        "If you take stiripentol, talk to your neurologist before using CBD and tell them about new side effects. Do "
        "not change your stiripentol dose yourself.",
        "May raise stiripentol levels",
        "Prescription CBD raised stiripentol levels in label studies, which can add to its side effects. If you take "
        "stiripentol, talk to your neurologist before using CBD.",
        "Prescription CBD raised stiripentol levels in label studies.",
        [EPIDIOLEX],
        "Q5: add stiripentol; increased exposure; monitor for adverse effects.",
    ),
    finding(
        "everolimus", "caution", "established",
        "The EPIDIOLEX label reports that prescription cannabidiol (12.5 mg/kg twice daily) raised everolimus peak "
        "levels and total exposure about 2.5-fold in healthy subjects; it advises monitoring everolimus levels, with "
        "dosing managed by the prescriber." + PRESCRIPTION_SCOPE,
        "If you take everolimus, talk to the specialist who prescribes it before using CBD; they may check your "
        "everolimus levels. Do not change your everolimus dose yourself.",
        "May raise everolimus levels",
        "Prescription CBD raised everolimus levels about 2.5-fold in a label study. If you take everolimus, talk to the "
        "specialist who prescribes it before using CBD.",
        "Prescription CBD raised everolimus levels in a label study.",
        [EPIDIOLEX],
        "Q5: increased exposure; specialist management of levels and dosing.",
    ),
    finding(
        "tacrolimus", "caution", "established",
        "In an open-label, fixed-sequence crossover study in 12 healthy adults (interim analysis), cannabidiol titrated "
        "to 5 mg/kg twice daily for 14 days raised tacrolimus peak levels 4.2-fold and total exposure 3.1-fold after a "
        "single 5 mg oral dose. The EPIDIOLEX label also says exposure to oral P-glycoprotein substrates such as "
        "tacrolimus may increase. The study used prescription-level doses; the effect of lower-dose over-the-counter "
        "or topical CBD is not established.",
        "If you take tacrolimus by mouth, talk to your transplant or specialist team before using CBD; they may check "
        "your tacrolimus levels. Do not change your tacrolimus dose yourself.",
        "May raise levels of tacrolimus taken by mouth",
        "In a study using prescription-level CBD doses, tacrolimus levels rose about 3-fold. If you take tacrolimus by "
        "mouth, talk to your transplant or specialist team before using CBD.",
        "Prescription-level CBD doses raised oral tacrolimus levels in a study in healthy adults.",
        [TACROLIMUS_PK, EPIDIOLEX],
        "Q5: tacrolimus gets its own record; a controlled human PK study found increased exposure. Graded established "
        "like everolimus: a measured human PK effect, with the label naming tacrolimus.",
    ),
    finding(
        "sirolimus", "caution", "probable",
        "The EPIDIOLEX label says exposure to other orally administered P-glycoprotein substrates, naming sirolimus, "
        "may increase with prescription cannabidiol, and suggests considering drug-level monitoring. A retrospective "
        "tuberous sclerosis complex series included seven sirolimus patients and reported a median trough-level "
        "increase of 5.1 ng/mL after cannabidiol. This was an observational series, not a controlled "
        "sirolimus interaction trial. The label concerns prescription oral cannabidiol; the size of the effect "
        "for over-the-counter or topical CBD products is not established.",
        "If you take sirolimus by mouth, talk to your transplant or specialist team before using CBD; they may check "
        "your sirolimus levels. Do not change your sirolimus dose yourself.",
        "Possible rise in levels of sirolimus taken by mouth",
        "The prescription CBD label flags rising sirolimus levels; an observational study also found this. If you take "
        "sirolimus by mouth, talk to your transplant or specialist team before using CBD.",
        "Higher sirolimus levels were measured in a small observational cannabidiol study.",
        [EPIDIOLEX, SIROLIMUS_OBSERVATIONAL],
        "Q5: oral P-gp precaution. Agent source correction 2026-11-12: PMID 31924480 reports measured sirolimus "
        "trough increases in an observational series. Probable follows the existing taxonomy's partial human "
        "support category; caution, action and matching remain unchanged. This source correction was not reviewed "
        "by Dr. Pham.",
    ),
    finding(
        "digoxin", "caution", "theoretical",
        "The EPIDIOLEX label says exposure to other orally administered P-glycoprotein substrates, naming digoxin, may "
        "increase with prescription cannabidiol, and suggests considering drug-level monitoring. This is a potential "
        "interaction described for the transporter, not one measured with digoxin." + PRESCRIPTION_SCOPE,
        "If you take digoxin by mouth, talk to your prescriber before using CBD; they may check your digoxin level. Do "
        "not change your digoxin dose yourself.",
        "Possible rise in levels of digoxin taken by mouth",
        "The prescription CBD label says digoxin levels may rise; this was not measured directly. If you take digoxin "
        "by mouth, talk to your prescriber before using CBD.",
        "Prescription CBD may raise levels of digoxin taken by mouth; not measured directly.",
        [EPIDIOLEX],
        "Q5: add a qualified CBD-digoxin finding, distinguished from a measured interaction. The 'Digoxin / Heart "
        "rhythm medication' picker class also reaches it, so every copy field is conditional on digoxin taken by "
        "mouth (Q4: an unknown medicine keeps a conditional message).",
        requires=["digoxin", "cardiac_glycosides"],
    ),
]

OTHER_SEIZURE_MEDICINES = {
    "evidence_level": "theoretical",
    "mechanism": (
        "Among seizure medicines, the EPIDIOLEX label reports dedicated interaction studies only with clobazam, "
        "valproate and stiripentol, which have their own findings. It reports no specific effect on other seizure "
        "medicines, so none is claimed here."
    ),
    "action": (
        "If you take a seizure medicine, talk to the doctor who prescribes it before using CBD. Do not change your "
        "seizure medicine yourself."
    ),
    "alert_headline": "Ask before using CBD with seizure medicines",
    "alert_body": (
        "The prescription CBD label reports studies with only a few seizure medicines. If you take a seizure medicine, "
        "talk to the doctor who prescribes it before using CBD."
    ),
    "informational_note": "The prescription CBD label reports interaction studies with only a few seizure medicines.",
    "clinical_review": review(
        "Q5: end the implication that every anticonvulsant shares the demonstrated interaction; keep a qualified "
        "review message for other seizure medicines until their evidence is assessed."
    ),
}

SEIZURE_CONDITION = {
    "mechanism": (
        "Prescription cannabidiol (EPIDIOLEX) is FDA-approved for seizures in Lennox-Gastaut syndrome, Dravet "
        "syndrome and tuberous sclerosis complex. Over-the-counter CBD products are not FDA-approved and can vary in "
        "dose and purity. With some seizure medicines, prescription cannabidiol raised drug levels (clobazam's active "
        "form, stiripentol) or made liver-enzyme rises more common (valproate); those findings appear separately."
    ),
    "action": (
        "If you have a seizure disorder, talk to your neurologist before using CBD, and do not use an over-the-counter "
        "CBD product in place of prescribed seizure treatment."
    ),
    "alert_body": (
        "Prescription cannabidiol is approved for specific seizure disorders, but OTC CBD products vary in dose and "
        "purity. If you have seizures, talk to your neurologist before using CBD."
    ),
    "informational_note": "OTC CBD products vary in dose and purity; prescription cannabidiol is a separate product.",
    "clinical_review": review(
        "Q5: keep seizure-condition guidance with an accurate claim; a condition note does not replace the "
        "drug-specific findings."
    ),
}


# --- classes, taxonomy, vocabulary ---------------------------------------------------------------------------------

def classes(blob: dict) -> None:
    cls = blob["classes"]
    for class_id, (rxcui, display, atc, primary_atc, parent) in NEW_CLASSES.items():
        key = f"class:{class_id}"
        assert key not in cls and primary_atc in atc
        parent_key = f"class:{parent}"
        assert rxcui in cls[parent_key]["member_rxcuis"], (class_id, parent_key)
        cls[key] = {
            "display_name": display,
            "description": f"{display} only, for findings its own source names",
            "member_names": [class_id],
            "member_rxcuis": [rxcui],
            "rxclass_id": primary_atc,
            "atc_codes": atc,
            "notes": (
                f"Single-medicine rule class for Dr. Pham's Q5 (signed 2026-11-12): the cannabidiol finding names "
                f"{class_id} with the claim its source supports. Also a member of {parent_key}. RxNorm ingredient "
                f"RxCUI and RxClass ATC read 2026-11-12. Membership is by ingredient, so every route matches."
            ),
        }


def taxonomy(blob: dict) -> None:
    ids = {c["id"] for c in blob["drug_classes"]}
    assert {"clobazam", "valproate"} <= ids and not ids & set(NEW_CLASSES)
    priority = max(c.get("display_priority", 0) for c in blob["drug_classes"])
    # anticonvulsants has no category; its siblings clobazam and valproate use "neurologic".
    category = {"anticonvulsants": "neurologic", "immunosuppressants": "immunology",
                "cardiac_glycosides": "cardiology"}
    for offset, (class_id, (_, display, _, _, parent)) in enumerate(NEW_CLASSES.items(), 1):
        blob["drug_classes"].append({"id": class_id, "label": display, "category": category[parent],
                                     "display_priority": priority + offset})
    meta = blob["_metadata"]
    major, minor, _ = meta["schema_version"].split(".")
    new_version = f"{major}.{int(minor) + 1}.0"
    meta["migration"]["completed_migrations"].insert(0, {
        "from": meta["schema_version"], "to": new_version, "date": TODAY,
        "summary": (
            "Additive: drug classes stiripentol, everolimus, tacrolimus, sirolimus and digoxin, so the cannabidiol "
            "findings can name each medicine with its own claim (Dr. Pham Q5). Gate vocabulary only; the profile "
            "picker is unchanged."
        ),
    })
    meta["schema_version"] = new_version
    meta["drug_classes_count"] = len(blob["drug_classes"])
    meta["total_entries"] = sum(len(v) for v in blob.values() if isinstance(v, list))


def vocab(blob: dict) -> None:
    entries = blob["drug_classes"]
    by_id = {e["id"]: e for e in entries}
    assert not set(by_id) & {*NEW_CLASSES, *NAMED_VOCAB}
    new = {class_id: (name, examples, parent) for class_id, (name, examples, parent) in NAMED_VOCAB.items()}
    new |= {class_id: (display, [class_id], parent) for class_id, (_, display, _, _, parent) in NEW_CLASSES.items()}
    for class_id, (name, examples, parent) in new.items():
        source = by_id[parent]
        entries.append({
            "id": class_id, "name": name,
            # The parent class's approved strings, verbatim: no new consumer copy (2026-08-08 sign-off).
            "group_label": source["group_label"], "commonly_used_for": source["commonly_used_for"],
            "notes": "Named in the prescription cannabidiol label; used for precise supplement interaction gates.",
            "examples": examples, "rx_status": "rx_only", "user_selectable": False,
        })
    meta = blob["_metadata"]
    total = len(entries)
    rule_only = sum(1 for e in entries if not e["user_selectable"])
    selectable = total - rule_only
    import re
    meta["description"] = re.sub(
        r"for the \d+ drug-class identifiers", f"for the {total} drug-class identifiers", meta["description"])
    meta["description"] = re.sub(r"\d+ RULE-ONLY classes", f"{rule_only} RULE-ONLY classes", meta["description"])
    assert f"{selectable} USER-SELECTABLE" in meta["description"]
    meta["last_updated"] = TODAY
    meta["consumer_copy_review"]["note"] += (
        " 2026-11-12: rule-only clobazam, valproate, stiripentol, everolimus, tacrolimus, sirolimus and digoxin reuse "
        "their parent class's approved strings verbatim, so no new string was added. Dr. Pham's Q5 sentences for "
        "clobazam and valproate, adapted to this contract, wait for her confirmation before they replace them."
    )


def rules(blob: dict) -> None:
    rule = next(r for r in blob["interaction_rules"] if r["id"] == RULE_ID)
    subs = rule["drug_class_rules"]
    by_class = {s["drug_class_id"]: s for s in subs}
    assert by_class["anticonvulsants"]["profile_gate"]["requires"]["drug_classes_any"] == [
        "anticonvulsants", "clobazam", "valproate"]
    # Q5: narrow the immunosuppressant finding to the named, supported medicines.
    subs.remove(by_class["immunosuppressants"])
    general = by_class["anticonvulsants"]
    general.update(OTHER_SEIZURE_MEDICINES)
    general["profile_gate"] = gate(["anticonvulsants"], ["stiripentol"])
    check_copy(general)
    at = subs.index(general)
    subs[at:at] = NAMED
    [seizure] = [c for c in rule["condition_rules"] if c["condition_id"] == "seizure_disorder"]
    seizure.update(SEIZURE_CONDITION)
    seizure["sources"] = [FDA_CBD, EPIDIOLEX]
    check_copy(seizure)
    assert rule["review_owner"] == "drug_label_mining"
    rule["review_owner"] = REVIEW_OWNER
    rule["last_reviewed"] = TODAY


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    for sub in NAMED:
        check_copy(sub)
    edit(CLASSES, classes)
    edit(TAXONOMY, taxonomy)
    edit(VOCAB, vocab)
    edit(RULES, rules)
