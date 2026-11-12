"""Batch 3 of Dr. Pham's signed answers (2026-11-12): anticholinergic scope.

Authority: DR_PHAM_ANSWERS_20261112.md Part A, Q4 (low-dose doxepin, topical anticholinergics) and Q6 (huperzine A and
alpha-GPC), as recorded in DISPOSITIONS_20261111.md.

- New rule class `class:antimuscarinics`: the members of class:anticholinergics that are taken for their antimuscarinic
  effect (bladder antimuscarinics, anticholinergic antiparkinson agents, scopolamine, antimuscarinic antispasmodics).
  The tricyclics and diphenhydramine stay in class:anticholinergics only; the identity class is unchanged (Q4, Q6).
- Huperzine A: avoid without prescriber approval for the antimuscarinic subset; caution with an evidence limitation
  for the rest of the class (tricyclics, diphenhydramine, including low-dose and topical doxepin, which keep qualified
  wording rather than an exemption or a strength cutoff) (Q6, Q4).
- Alpha-GPC: caution with limited evidence and no treatment-failure claim for the subset; an informational note for
  the rest of the class that asserts no loss of benefit (Q6).
- A profile that names only the picker class (medicine unknown) gets the broader sub-rule, whose visible headline and
  body carry both branches: the avoid instruction for a medicine taken for its anticholinergic effect, and ask first
  otherwise (Q4, unknown strength or route: preserve the uncertainty and ask). Whether that profile should get the
  subset's severity is held for Dr. Pham.
- Huperzine A subset evidence is graded theoretical: Q6 calls the donepezil-label extension a pharmacological
  inference with no direct huperzine interaction trial.

Agent implementation and wording; the severities and scope are Dr. Pham's (Q4, Q6). Labels read 2026-11-12: donepezil
76bf638e (7.1), ARICEPT 98e451e1 (7.1), SILENOR 1bec1223 (4.3, 10.1), ZONALON 5f302247 (contraindications, precautions).
PMIDs content-checked on PubMed 2026-11-12: 25191267, 2071257, 36950691.
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
DM = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid="
ARICEPT = DM + "98e451e1-e4d7-4439-a675-c5457ba20975"
DONEPEZIL = DM + "76bf638e-dbde-418e-8977-1caf009990bc"
SILENOR = DM + "1bec1223-5239-4eb6-a9e8-62444106d2c0"
ZONALON = DM + "5f302247-525e-4acc-852b-00eb1d79af4b"
PUBMED = "https://pubmed.ncbi.nlm.nih.gov/{}/"

# class:anticholinergics members whose anticholinergic effect is incidental (labels read 2026-11-11, D2).
INCIDENTAL = {
    "amitriptyline": "704", "amoxapine": "722", "clomipramine": "2597", "desipramine": "3247", "diphenhydramine": "3498",
    "doxepin": "3638", "imipramine": "5691", "nortriptyline": "7531", "protriptyline": "8886", "trimipramine": "10834",
}
# The rest, each with its RxClass ATC class (read on RxNav 2026-11-12): taken for the antimuscarinic effect.
ANTIMUSCARINIC = {
    "benztropine": ("1424", "N04AC"), "biperiden": ("1589", "N04AA"), "bornaprine": ("19610", "N04AA"),
    "darifenacin": ("136198", "G04BD"), "dexetimide": ("3267", "N04AA"), "dicyclomine": ("3361", "A03AA"),
    "emepronium": ("3816", "G04BD"), "fesoterodine": ("797195", "G04BD"), "glycopyrronium": ("1546438", "A03AB"),
    "hyoscyamine": ("153970", "A03BA"), "methixene": ("29682", "N04AA"), "oxybutynin": ("32675", "G04BD"),
    "procyclidine": ("8718", "N04AA"), "profenamine": ("4134", "N04AA"), "propiverine": ("55175", "G04BD"),
    "scopolamine": ("9601", "A04AD"), "solifenacin": ("322167", "G04BD"), "terodiline": ("37815", "G04BD"),
    "tolterodine": ("119565", "G04BD"), "trihexyphenidyl": ("10811", "N04AA"), "tropatepine": ("38876", "N04AA"),
    "trospium": ("236778", "G04BD"),
}


def review(notes: str) -> dict:
    """Dr. Pham signed the severity and scope; the consumer wording is agent wording, not reviewed by Dr. Pham."""
    return {"reviewer": "Dr. Pham", "reviewed_at": TODAY, "file": ANSWERS,
            "notes": notes + " Consumer wording, membership and evidence grading: agent work, not reviewed by Dr. Pham."}


REVIEW_OWNER = (
    "Dr. Pham (signed answers 2026-11-12, Q4 and Q6: severity and scope); wording, membership and labels read by "
    "agent; original rule pharmaguide_clinical_team"
)


def check_copy(sub: dict) -> None:
    """The safety-copy validator's length windows, checked before writing."""
    for key, lo, hi in (("alert_headline", 20, 60), ("alert_body", 60, 200), ("informational_note", 40, 120)):
        if sub.get(key):
            assert lo <= len(sub[key]) <= hi, (key, len(sub[key]), sub[key])


def gate(requires: str, excludes: list[str]) -> dict:
    return {
        "gate_type": "drug_class",
        "requires": {"conditions_any": [], "drug_classes_any": [requires], "profile_flags_any": []},
        "excludes": {"conditions_any": [], "drug_classes_any": excludes, "profile_flags_any": [],
                     "product_forms_any": [], "nutrient_forms_any": []},
        "dose": None,
    }


# --- drug classes, taxonomy, vocabulary ----------------------------------------------------------------------------

def classes(blob: dict) -> None:
    cls = blob["classes"]
    broad = cls["class:anticholinergics"]
    members = dict(zip(broad["member_names"], broad["member_rxcuis"]))
    assert members == {**INCIDENTAL, **{n: r for n, (r, _) in ANTIMUSCARINIC.items()}}, "membership drifted"
    stale = "low-dose doxepin (SILENOR, 3-6 mg) lists anticholinergic effects only above 6 mg (ask 4)."
    assert stale in broad["notes"]
    broad["notes"] = broad["notes"].replace(stale, (
        "low-dose doxepin (SILENOR, 3-6 mg) lists anticholinergic effects among those seen above 6 mg (10.1) but "
        "still contraindicates it in untreated narrow-angle glaucoma or severe urinary retention (4.3); Dr. Pham's Q4 "
        "(2026-11-12) says the 6 mg figure is not an interaction cutoff, and the ZONALON cream label (5f302247) reports systemic "
        "absorption, so topical doxepin is not exempt. Q4 keeps every member here; Q6 moves the strongest rules to "
        "class:antimuscarinics, the members taken for their antimuscarinic effect."
    ))
    assert "class:antimuscarinics" not in cls
    ordered = sorted(ANTIMUSCARINIC.items())
    cls["class:antimuscarinics"] = {
        "display_name": "Antimuscarinic medicines",
        "description": (
            "Medicines taken for their antimuscarinic effect: bladder antimuscarinics, anticholinergic antiparkinson "
            "agents, scopolamine and antimuscarinic antispasmodics (not tricyclic antidepressants or diphenhydramine)."
        ),
        "member_names": [n for n, _ in ordered],
        "member_rxcuis": [r for _, (r, _) in ordered],
        "rxclass_id": "G04BD",
        # The parent's codes for these members: groups where the whole group is in, exact codes for single members.
        "atc_codes": sorted(c for c in broad["atc_codes"] if c[:5] in {atc for _, atc in ANTIMUSCARINIC.values()}),
        "notes": (
            "Rule subset of class:anticholinergics for Dr. Pham's Q6 (signed 2026-11-12): huperzine A avoid without "
            "prescriber approval and alpha-GPC caution apply here; the tricyclics and diphenhydramine, whose "
            "anticholinergic effect is incidental, stay in class:anticholinergics only. Every member is also a member "
            "of class:anticholinergics. Membership is by ingredient, so transdermal, inhaled and topical products "
            "(scopolamine patches, oxybutynin gel and patch, inhaled or topical glycopyrronium) are included; each is "
            "still used for its antimuscarinic effect. ATC classes read on RxNav 2026-11-12."
        ),
    }


def taxonomy(blob: dict) -> None:
    ids = [c["id"] for c in blob["drug_classes"]]
    assert "antimuscarinics" not in ids and "anticholinergics" in ids
    blob["drug_classes"].append({
        "id": "antimuscarinics", "label": "Antimuscarinic Medications", "category": "neurology",
        "display_priority": max(c.get("display_priority", 0) for c in blob["drug_classes"]) + 1,
    })
    meta = blob["_metadata"]
    major, minor, _ = meta["schema_version"].split(".")
    new_version = f"{major}.{int(minor) + 1}.0"
    meta["migration"]["completed_migrations"].insert(0, {
        "from": meta["schema_version"], "to": new_version, "date": TODAY,
        "summary": (
            "Additive: drug class antimuscarinics (members of anticholinergics taken for their antimuscarinic "
            "effect), so huperzine A and alpha-GPC findings can follow Dr. Pham's Q6. Gate vocabulary only; the "
            "profile picker is unchanged."
        ),
    })
    meta["schema_version"] = new_version
    meta["drug_classes_count"] = len(blob["drug_classes"])
    meta["total_entries"] = sum(len(v) for v in blob.values() if isinstance(v, list))


def vocab(blob: dict) -> None:
    entries = blob["drug_classes"]
    broad = next(e for e in entries if e["id"] == "anticholinergics")
    assert not any(e["id"] == "antimuscarinics" for e in entries)
    entries.append({
        "id": "antimuscarinics",
        "name": "Antimuscarinic medication",
        # The approved anticholinergics strings, verbatim: no new consumer copy (2026-08-08 sign-off).
        "group_label": broad["group_label"],
        "commonly_used_for": broad["commonly_used_for"],
        "notes": (
            "Medicines taken for their anticholinergic (antimuscarinic) effect, such as oxybutynin for bladder control "
            "or benztropine for Parkinson's; used for precise supplement interaction gates."
        ),
        "examples": ["oxybutynin", "tolterodine", "benztropine", "scopolamine"],
        "rx_status": "mixed",
        "user_selectable": False,
    })
    meta = blob["_metadata"]
    old = ("Controlled vocabulary for the 30 drug-class identifiers referenced by interaction_rules.drug_class_rules. "
           "Splits into two tiers: 16 USER-SELECTABLE classes shown in onboarding/profile and 14 RULE-ONLY classes")
    assert meta["description"].startswith(old)
    meta["description"] = meta["description"].replace(old, (
        "Controlled vocabulary for the 31 drug-class identifiers referenced by interaction_rules.drug_class_rules. "
        "Splits into two tiers: 16 USER-SELECTABLE classes shown in onboarding/profile and 15 RULE-ONLY classes"
    ))
    meta["last_updated"] = TODAY
    meta["consumer_copy_review"]["note"] += (
        " 2026-11-12: rule-only `antimuscarinics` added with the approved anticholinergics group_label and "
        "commonly_used_for verbatim, so no new consumer copy; a subset-specific sentence is held for Dr. Pham."
    )


# --- rules ------------------------------------------------------------------------------------------------------

MUSCARINIC_EXAMPLES = "such as oxybutynin, tolterodine, trospium, scopolamine, benztropine and trihexyphenidyl"

HUPERZINE_SUBSET = {
    "drug_class_id": "antimuscarinics",
    "severity": "avoid",
    "evidence_level": "theoretical",
    "mechanism": (
        "Huperzine A is a natural acetylcholinesterase inhibitor, licensed as an Alzheimer's drug in China and sold as a "
        "supplement in the US. The prescribing information for donepezil, another cholinesterase inhibitor, states "
        "that because of their mechanism of action, cholinesterase inhibitors have the potential to interfere with the "
        f"activity of anticholinergic medications. Medicines in this group, {MUSCARINIC_EXAMPLES}, are taken for that "
        "antimuscarinic action, so interference would work against the reason they are prescribed. Applying the label "
        "statement to huperzine A is a pharmacological inference; no huperzine-specific interaction study was found."
    ),
    "action": (
        "If you take a medicine for its anticholinergic effect, such as oxybutynin for bladder control or benztropine, "
        "do not combine it with huperzine A unless your prescriber approves. Tell your prescriber about huperzine A use."
    ),
    "sources": [PUBMED.format("25191267"), ARICEPT, DONEPEZIL],
    "alert_headline": "Avoid with medicines like oxybutynin unless approved",
    "alert_body": (
        "Huperzine A may work against medicines taken for their anticholinergic effect, such as oxybutynin or "
        "benztropine. If you take one, do not combine them unless your prescriber approves."
    ),
    "informational_note": "Huperzine A raises acetylcholine, which medicines such as oxybutynin are taken to block.",
    "profile_gate": gate("antimuscarinics", []),
    "direction": "harmful",
    "materiality": "presence",
    "clinical_review": review(
        "Q6: avoid unsupervised combination with a medicine used for its antimuscarinic effect; obtain prescriber "
        "approval. The donepezil-label extension to huperzine A is a pharmacological inference."
    ),
}

HUPERZINE_BROAD = {
    "severity": "caution",
    "evidence_level": "theoretical",
    "mechanism": (
        "Huperzine A is a natural acetylcholinesterase inhibitor. The prescribing information for donepezil, another "
        "cholinesterase inhibitor, states that cholinesterase inhibitors have the potential to interfere with the "
        "activity of anticholinergic medications. Tricyclic antidepressants and diphenhydramine have anticholinergic "
        "effects that are usually not the reason they are taken, and no study was found that measured them with "
        "huperzine A, so the "
        "practical effect is not established. The low-dose doxepin label for sleep (SILENOR, 3-6 mg) lists "
        "anticholinergic effects among those seen above 6 mg but still contraindicates it in untreated narrow-angle "
        "glaucoma or severe urinary retention, so 6 mg is not an interaction cutoff; the doxepin cream label (ZONALON) "
        "reports measurable blood levels and systemic anticholinergic effects after skin application."
    ),
    "action": (
        "If you take a tricyclic antidepressant or diphenhydramine, ask your prescriber or pharmacist before using "
        "huperzine A, and tell them the medicine, the dose and whether you take it by mouth or on the skin. If your "
        "medicine is taken for its anticholinergic effect, such as oxybutynin, do not combine them unless your "
        "prescriber approves."
    ),
    "sources": [PUBMED.format("25191267"), ARICEPT, DONEPEZIL, SILENOR, ZONALON],
    "alert_headline": "Check first if you take an anticholinergic medicine",
    "alert_body": (
        "Huperzine A may interfere with anticholinergic medicines. If yours is taken for that effect, such as "
        "oxybutynin, do not combine unless your prescriber approves; otherwise ask first."
    ),
    "informational_note": "Huperzine A raises acetylcholine; some antidepressants and sleep aids have anticholinergic effects.",
    "clinical_review": review(
        "Q6: caution / professional review with an explicit evidence limitation for tricyclic antidepressants and "
        "systemic diphenhydramine. Q4: doxepin keeps its class membership with qualified wording; topical doxepin is "
        "not exempt; no SILENOR strength cutoff; an unknown medicine keeps its uncertainty."
    ),
}

ALPHA_GPC_SUBSET = {
    "drug_class_id": "antimuscarinics",
    "severity": "caution",
    "evidence_level": "limited",
    "mechanism": (
        "Alpha-GPC (L-alpha glycerylphosphorylcholine) is a choline donor that can increase acetylcholine synthesis. "
        f"Medicines in this group, {MUSCARINIC_EXAMPLES}, are taken for their antimuscarinic action. In 32 healthy "
        "volunteers, 10 days of alpha-GPC before a scopolamine injection reduced scopolamine-induced attention and "
        "memory impairment. That small study does not show that alpha-GPC makes these medicines ineffective in "
        "clinical use; the effect of the combination on treatment is not established."
    ),
    "action": (
        "If your medicine is taken for its anticholinergic action, such as oxybutynin for bladder control, tell your "
        "prescriber about alpha-GPC use, and report it if the medicine seems to work less well."
    ),
    "sources": [PUBMED.format("2071257"), PUBMED.format("36950691")],
    "alert_headline": "May affect medicines like oxybutynin",
    "alert_body": (
        "Alpha-GPC supplies choline, which is used to make acetylcholine. Evidence is limited, but it could "
        "lessen the effect of medicines taken for their anticholinergic action. Tell your prescriber about it."
    ),
    "informational_note": "Alpha-GPC supplies choline; evidence on medicines like oxybutynin is limited.",
    "profile_gate": gate("antimuscarinics", []),
    "direction": "harmful",
    "materiality": "presence",
    "clinical_review": review(
        "Q6: caution, with limited evidence and no categorical treatment-failure claim, for a medicine used for its "
        "antimuscarinic effect."
    ),
}

ALPHA_GPC_BROAD = {
    "severity": "informational",
    "evidence_level": "theoretical",
    "direction": "neutral",
    "mechanism": (
        "Alpha-GPC (L-alpha glycerylphosphorylcholine) is a choline donor. Tricyclic antidepressants and "
        "diphenhydramine usually have anticholinergic effects as side effects, not as the reason they are taken. No "
        "study was found showing that alpha-GPC changes how well these medicines work, and class membership alone "
        "does not establish a "
        "loss of benefit."
    ),
    "action": (
        "If your medicine is taken for its anticholinergic action, such as oxybutynin for bladder control, tell your "
        "prescriber about alpha-GPC use. For tricyclic antidepressants and diphenhydramine, no change in their effect "
        "has been shown."
    ),
    "sources": [PUBMED.format("2071257"), PUBMED.format("36950691")],
    "alert_headline": "Alpha-GPC with an anticholinergic medicine",
    "alert_body": (
        "No study was found showing alpha-GPC changes how tricyclics or diphenhydramine work. If you take a medicine "
        "like oxybutynin for its anticholinergic effect, tell your prescriber about alpha-GPC."
    ),
    "informational_note": "Alpha-GPC supplies choline; no effect on tricyclics or diphenhydramine has been shown.",
    "clinical_review": review(
        "Q6: for a medicine with incidental anticholinergic effects, do not assert loss of the medicine's intended "
        "benefit from class membership alone; a qualified informational note."
    ),
}


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}
    for rule_id, subset, broad_update in (
        ("RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS", HUPERZINE_SUBSET, HUPERZINE_BROAD),
        ("RULE_IQM_ALPHA_GPC_ANTICHOLINERGICS", ALPHA_GPC_SUBSET, ALPHA_GPC_BROAD),
    ):
        rule = by_id[rule_id]
        subs = rule["drug_class_rules"]
        assert [s["drug_class_id"] for s in subs] == ["anticholinergics"], rule_id
        [broad] = subs
        broad.update(broad_update)
        broad["profile_gate"]["excludes"]["drug_classes_any"] = ["antimuscarinics"]
        for sub in (broad, subset):
            check_copy(sub)
        subs.insert(0, dict(subset))
        assert rule["review_owner"] == "pharmaguide_clinical_team", rule_id
        rule["review_owner"] = REVIEW_OWNER
        rule["last_reviewed"] = TODAY


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    edit(CLASSES, classes)
    edit(TAXONOMY, taxonomy)
    edit(VOCAB, vocab)
    edit(RULES, rules)
