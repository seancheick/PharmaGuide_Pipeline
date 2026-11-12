"""Batch 2 of Dr. Pham's signed answers (2026-11-12): anticoagulants.

Authority: DR_PHAM_ANSWERS_20261112.md Part A (Q3, Q7, section 2 "St. John's wort with anticoagulants") and Part B 3D
(heparin-group membership, the INR copy pass), as recorded in DISPOSITIONS_20261111.md.

- Injected anticoagulants (Q7, Part B 3D). New class `class:injectable_anticoagulants`: argatroban, bivalirudin,
  desirudin, lepirudin (ATC B01AE, not oral), heparin, enoxaparin, dalteparin, tinzaparin (B01AB) and fondaparinux
  (B01AX). Heparins and fondaparinux also join `class:anticoagulants`. The gate id joins the taxonomy; the six
  warfarin-addressed fallback sub-rules exclude it, so these medicines keep the general blood-thinner findings and
  never receive warfarin or oral-DOAC instructions.
- St. John's wort + VKAs (Q7, section 2): exact Major pairs for acenocoumarol (UK Sinthrome SmPC) and phenprocoumon
  (German Marcumar Fachinformation), each with its own label; the VKA sub-rule cites both and states that other
  VKAs are a precautionary class inference.
- St. John's wort + DOACs (section 2): DSI_DOAC_SJW records each label's own wording; edoxaban gets its own record
  (DSI_EDOXABAN_SJW, Major) saying avoid is PharmaGuide precautionary policy, since the UK Lixiana SmPC says caution.
- Glucosamine (Q3, Q7): caution kept; Q3's do-not-start-without-agreement action on the warfarin pair and both
  sub-rules; exact Moderate pairs for acenocoumarol and phenprocoumon from their labels.
- CoQ10, cranberry, ginger (both records) (Q7): warfarin-specific evidence; the VKA extension is stated as inference.
- INR copy pass (section 2, Part B 3D): no INR instruction reaches a DOAC or injected-anticoagulant user unless it is
  addressed to warfarin. Every anticoagulant sub-rule's "ask about INR or bleeding checks" becomes "ask about
  bleeding checks"; INR instructions in actions are addressed to warfarin users.

Agent review (label passages read 2026-11-12); attributed to Dr. Pham only where Dr. Pham's signed answer decides.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

DATA = REPO / "scripts/data"
CURATED = DATA / "curated_interactions/curated_interactions_v1.json"
CRITICAL = DATA / "curated_interactions/batch_critical_2026_05.json"
RULES = DATA / "ingredient_interaction_rules.json"
CLASSES = DATA / "drug_classes.json"
TAXONOMY = DATA / "clinical_risk_taxonomy.json"

ANSWERS = "audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md"
TODAY = "2026-11-12"
DM = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid="
SINTHROME = "https://www.medicines.org.uk/emc/product/2058/smpc"
MARCUMAR = "https://www.fachinfo.de/pdf/003056"
LIXIANA = "https://www.medicines.org.uk/emc/product/6905/smpc"
SAVAYSA = DM + "e77d3400-56ad-11e3-949a-0800200c9a66"

INJECTED = {  # RxNorm ingredient (IN) RxCUIs, active, read on RxNav 2026-11-12, with their RxClass ATC class
    "argatroban": ("15202", "B01AE"), "bivalirudin": ("60819", "B01AE"), "dalteparin": ("67109", "B01AB"),
    "desirudin": ("114934", "B01AE"), "enoxaparin": ("67108", "B01AB"), "fondaparinux": ("321208", "B01AX"),
    "heparin": ("5224", "B01AB"), "lepirudin": ("237057", "B01AE"), "tinzaparin": ("69646", "B01AB"),
}
NEW_ANTICOAGULANTS = ("dalteparin", "enoxaparin", "fondaparinux", "heparin", "tinzaparin")
FALLBACK_RULES = ("RULE_INGREDIENT_ST_JOHNS_WORT", "RULE_INGREDIENT_GLUCOSAMINE", "RULE_INGREDIENT_CRANBERRY",
                  "RULE_IQM_COQ10_HEART_DISEASE_STATINS", "RULE_IQM_GINGER_BLEEDING",
                  "RULE_OTHER_GINGER_EXTRACT_BLEEDING")

GLUCOSAMINE_Q3 = (
    "Do not start glucosamine while taking warfarin unless your anticoagulation clinician has specifically agreed and "
    "arranged appropriate INR monitoring. Tell them before stopping or changing glucosamine. Some warfarin labels "
    "advise against this combination."
)


def verification(note: str) -> dict:
    return {
        "status": "verified",
        "verified_at": TODAY,
        "verified_with": {"rxnorm": True, "umls": True, "pubmed": False},
        "method": "agent_label_content_review_2026_11_12",
        "notes": note,
    }


def review(notes: str) -> dict:
    return {"reviewer": "Dr. Pham", "reviewed_at": TODAY, "file": ANSWERS, "notes": notes}


def check_copy(sub: dict) -> None:
    """The safety-copy validator's length windows, checked before writing."""
    for key, lo, hi in (("alert_headline", 20, 60), ("alert_body", 60, 200), ("informational_note", 40, 120)):
        if sub.get(key):
            assert lo <= len(sub[key]) <= hi, (key, len(sub[key]), sub[key])


# --- drug classes and taxonomy -------------------------------------------------------------------------------------

def classes(blob: dict) -> None:
    cls = blob["classes"]
    anticoag = cls["class:anticoagulants"]
    members = dict(zip(anticoag["member_names"], anticoag["member_rxcuis"]))
    assert not set(NEW_ANTICOAGULANTS) & members.keys()
    members.update({name: INJECTED[name][0] for name in NEW_ANTICOAGULANTS})
    ordered = sorted(members.items())
    anticoag.update({
        "member_names": [n for n, _ in ordered],
        "member_rxcuis": [r for _, r in ordered],
        "description": (
            "Vitamin K antagonists, direct oral anticoagulants, injected heparins and fondaparinux, and injected direct "
            "thrombin inhibitors"
        ),
        "atc_codes": sorted({*anticoag["atc_codes"], "B01AB", "B01AX05"}),
        "notes": anticoag["notes"].rstrip().rstrip(".") + "." + (
            " Heparin, enoxaparin, dalteparin, tinzaparin (ATC B01AB) and fondaparinux (B01AX05) added 2026-11-12 "
            "(RxNav ingredient RxCUIs); with the injected direct thrombin inhibitors they are also in "
            "class:injectable_anticoagulants, which keeps them out of warfarin-addressed fallbacks (Dr. Pham Q7; "
            "Part B 3D)."
        ),
    })
    assert "class:injectable_anticoagulants" not in cls
    injected = sorted((name, rxcui) for name, (rxcui, _) in INJECTED.items())
    cls["class:injectable_anticoagulants"] = {
        "display_name": "Injected anticoagulants",
        "description": "Heparins, fondaparinux and injected direct thrombin inhibitors (not vitamin K antagonists or "
                       "oral DOACs)",
        "member_names": [n for n, _ in injected],
        "member_rxcuis": [r for _, r in injected],
        "rxclass_id": "B01AB/B01AE/B01AX",
        "atc_codes": ["B01AB", "B01AE", "B01AX05"],
        "notes": (
            "Identified subgroup for Dr. Pham's Q7 (signed 2026-11-12): these medicines stay anticoagulants and keep "
            "general bleeding findings, but are excluded from the unidentified-warfarin fallback sub-rules and never "
            "receive warfarin INR or oral-inducer instructions. From ATC B01AE only argatroban, bivalirudin, desirudin "
            "and lepirudin are members; dabigatran (B01AE) is oral and a DOAC. Heparin's ingredient RxCUI also covers "
            "topical and eye products (ATC C05BA, S01XA); membership is by ingredient, so those users are treated as "
            "injected-anticoagulant users. RxCUIs read on RxNav 2026-11-12."
        ),
    }


def taxonomy(blob: dict) -> None:
    ids = [c["id"] for c in blob["drug_classes"]]
    assert "injectable_anticoagulants" not in ids
    blob["drug_classes"].append({
        "id": "injectable_anticoagulants", "label": "Injected Anticoagulants", "category": "hematology",
        "display_priority": max(c.get("display_priority", 0) for c in blob["drug_classes"]) + 1,
    })
    meta = blob["_metadata"]
    assert meta["schema_version"] == "5.6.0"
    meta["schema_version"] = "5.7.0"
    meta["drug_classes_count"] = len(blob["drug_classes"])
    assert meta["total_entries"] == 87
    meta["total_entries"] = sum(len(v) for v in blob.values() if isinstance(v, list))
    meta["migration"]["completed_migrations"].insert(0, {
        "from": "5.6.0", "to": "5.7.0", "date": TODAY,
        "summary": (
            "Additive: drug class injectable_anticoagulants (heparins, fondaparinux, injected direct thrombin "
            "inhibitors), so warfarin-addressed fallback findings can exclude them (Dr. Pham Q7). Gate vocabulary "
            "only; the profile picker (drug_class_vocab.json) is unchanged."
        ),
    })


# --- curated pairs ----------------------------------------------------------------------------------------------

def pair(pair_id: str, agent1: tuple[str, str], agent2: tuple[str, str, str], **fields) -> dict:
    return {
        "id": pair_id, "type": "Med-Sup",
        "agent1_name": agent1[1], "agent1_id": agent1[0],
        "agent2_name": agent2[1], "agent2_id": agent2[0],
        **fields,
        "applies_to": "specific_drug",
        "agent1_canonical_id": None, "agent2_canonical_id": agent2[2],
        "direction": "harmful", "materiality": "presence",
    }


SJW = ("C0813171", "St. John's Wort", "st_johns_wort")
GLUCOSAMINE = ("C0017718", "Glucosamine", "glucosamine")


def sjw_vka_pair(pair_id, rxcui, drug, label, mechanism, notes) -> dict:
    return pair(
        pair_id, (rxcui, drug.capitalize()), SJW,
        severity="Major", interaction_effect_type="Inhibitor", mechanism=mechanism,
        management=(
            f"Avoid St. John's wort while you take {drug}. If you already take both, do not stop either one on your "
            f"own: tell your anticoagulation team first, because starting or stopping St. John's wort can change how "
            f"well {drug} works and your INR."
        ),
        source_urls=[label], source_pmids=[],
        verification=verification(f"{notes} Severity: Dr. Pham, {ANSWERS} (Q7, section 2)."),
        evidence_basis="label_regulatory", clinical_confidence="medium",
        evidence_notes=notes + " Strong avoidance for warfarin, acenocoumarol and phenprocoumon is Dr. Pham's Q7 "
                               "decision (2026-11-12).",
    )


def glucosamine_vka_pair(pair_id, rxcui, drug, label, mechanism, notes) -> dict:
    return pair(
        pair_id, (rxcui, drug.capitalize()), GLUCOSAMINE,
        severity="Moderate", interaction_effect_type="Enhancer", mechanism=mechanism,
        management=(
            f"Do not start glucosamine while taking {drug} unless your anticoagulation clinician has specifically "
            f"agreed and arranged appropriate INR monitoring. Tell them before stopping or changing glucosamine. "
            f"Report unusual bruising or bleeding."
        ),
        source_urls=[label], source_pmids=[],
        verification=verification(f"{notes} Severity and action follow warfarin + glucosamine: Dr. Pham, {ANSWERS} "
                                  f"(Q3, Q7)."),
        evidence_basis="label_regulatory", clinical_confidence="medium",
        evidence_notes=notes + " Caution with a clinician-agreement action, as for warfarin (Dr. Pham Q3 and Q7, "
                               "2026-11-12); not a contraindication.",
    )


SINTHROME_SJW = (
    "UK Sinthrome (acenocoumarol) SmPC, section 4.5 (text revised June 2025): St. John's Wort/Hypericum perforatum is "
    "listed among medicines that may diminish acenocoumarol's anticoagulant effect."
)
MARCUMAR_SJW = (
    "German Marcumar (phenprocoumon) Fachinformation, section 4.5 (Stand June 2026): St. John's wort preparations can "
    "weaken phenprocoumon's effect, probably through cytochrome P450 induction; closer coagulation checks, especially "
    "at the start and, because of the overdose risk, after St. John's wort is stopped, and dose adjustment are "
    "recommended."
)
SINTHROME_GLUCOSAMINE = (
    "UK Sinthrome (acenocoumarol) SmPC, section 4.5 (text revised June 2025): increased INR has been reported in "
    "patients taking glucosamine and oral vitamin K antagonists; they should be closely monitored when glucosamine is "
    "started or stopped."
)
MARCUMAR_GLUCOSAMINE = (
    "German Marcumar (phenprocoumon) Fachinformation, section 4.5 (Stand June 2026): glucosamine can strengthen the "
    "effect of oral vitamin K antagonists; patients should be closely observed, especially when glucosamine is started "
    "or stopped."
)
DOAC_NOTES = (
    "Each label read 2026-11-12. ELIQUIS (apixaban, section 7.2) and rivaroxaban (section 7) name St. John's wort among "
    "combined P-gp and strong CYP3A inducers to avoid. PRADAXA (dabigatran, section 5.5) says P-gp inducers such as "
    "rifampin reduce exposure and should generally be avoided; it does not name St. John's wort. SAVAYSA (edoxaban, "
    "US, section 7.2) says to avoid rifampin and does not name St. John's wort; the UK Lixiana SmPC (section 4.5, "
    "revised 24 July 2025) lists St. John's wort among P-gp inducers to use with caution, so avoid for edoxaban is "
    "PharmaGuide precautionary policy (exact record DSI_EDOXABAN_SJW). Betrixaban (BEVYXXA) is no longer on DailyMed "
    "and was not re-read; it is avoid by Dr. Pham's section 2 decision."
)
EDOXABAN_NOTES = (
    "UK Lixiana SmPC, section 4.5 (revised 24 July 2025): other P-gp inducers such as St. John's wort may lower "
    "edoxaban concentrations, and edoxaban should be used with caution with P-gp inducers. The US SAVAYSA label "
    "(section 7.2) says to avoid rifampin and does not name St. John's wort. The label says caution; avoid is retained "
    "as PharmaGuide precautionary policy (Dr. Pham, 2026-11-12, section 2)."
)


def curated(blob: dict) -> None:
    rows = blob["interactions"]
    by_id = {r["id"]: r for r in rows}
    war_glucosamine = by_id["DSI_WAR_GLUCOSAMINE"]
    assert war_glucosamine["management"].startswith("Tell your anticoagulation team before you start")
    war_glucosamine["management"] = (
        GLUCOSAMINE_Q3 + " This includes glucosamine-chondroitin products. Report unusual bruising or bleeding."
    )
    war_glucosamine["verification"]["notes"] += f" Management: Dr. Pham Q3, {ANSWERS} (2026-11-12)."
    for pair_id, (old, new) in PAIR_REWRITES.items():
        assert by_id[pair_id]["management"] == old, pair_id
        by_id[pair_id]["management"] = new

    new_after = {
        "DSI_WAR_SJW": [
            sjw_vka_pair("DSI_ACENOCOUMAROL_SJW", "154", "acenocoumarol", SINTHROME,
                         "St. John's wort can induce drug-metabolizing enzymes and weaken acenocoumarol's anticoagulant "
                         "effect. Starting or stopping it can therefore change anticoagulation.", SINTHROME_SJW),
            sjw_vka_pair("DSI_PHENPROCOUMON_SJW", "8150", "phenprocoumon", MARCUMAR,
                         "St. John's wort can weaken phenprocoumon's anticoagulant effect, probably by inducing "
                         "cytochrome P450 enzymes. Stopping it while phenprocoumon continues can raise its effect.",
                         MARCUMAR_SJW),
            pair(
                "DSI_EDOXABAN_SJW", ("1599538", "Edoxaban"), SJW,
                severity="Major", interaction_effect_type="Inhibitor",
                mechanism=(
                    "St. John's wort induces P-gp. Edoxaban's UK label says P-gp inducers such as St. John's wort may "
                    "lower edoxaban levels, which can reduce protection against stroke or clots."
                ),
                management=(
                    "Avoid St. John's wort while you take edoxaban unless your prescriber explicitly manages the "
                    "combination. Do not start or stop St. John's wort without telling the prescriber."
                ),
                source_urls=[LIXIANA, SAVAYSA], source_pmids=[],
                verification=verification(f"{EDOXABAN_NOTES} Policy: Dr. Pham, {ANSWERS} (section 2)."),
                evidence_basis="label_regulatory", clinical_confidence="medium",
                evidence_notes=EDOXABAN_NOTES,
            ),
        ],
        "DSI_WAR_GLUCOSAMINE": [
            glucosamine_vka_pair("DSI_ACENOCOUMAROL_GLUCOSAMINE", "154", "acenocoumarol", SINTHROME,
                                 "Increased INR has been reported with glucosamine and oral vitamin K antagonists, "
                                 "including acenocoumarol. The mechanism is unknown.", SINTHROME_GLUCOSAMINE),
            glucosamine_vka_pair("DSI_PHENPROCOUMON_GLUCOSAMINE", "8150", "phenprocoumon", MARCUMAR,
                                 "Glucosamine can strengthen the effect of oral vitamin K antagonists, including "
                                 "phenprocoumon. The mechanism is unknown.", MARCUMAR_GLUCOSAMINE),
        ],
    }
    for anchor, new_rows in new_after.items():
        for row in new_rows:
            assert row["id"] not in by_id, row["id"]
        index = next(i for i, r in enumerate(rows) if r["id"] == anchor)
        rows[index + 1:index + 1] = new_rows


def critical(blob: dict) -> None:
    [doac] = [r for r in blob["interactions"] if r["id"] == "DSI_DOAC_SJW"]
    assert doac["severity"] == "Major" and LIXIANA not in doac["source_urls"]
    doac.update({
        "source_urls": [*doac["source_urls"], LIXIANA],
        "evidence_notes": DOAC_NOTES,
        "verification": verification(f"{DOAC_NOTES} Dr. Pham, {ANSWERS} (section 2)."),
    })


# --- profile rules ---------------------------------------------------------------------------------------------

def shared_vka_text(rule: dict, update: dict, review_note: str) -> None:
    """Q7: the identified-VKA sub-rule and the unidentified fallback carry one decision and one text."""
    for cls in ("vitamin_k_antagonists", "anticoagulants"):
        [sub] = [s for s in rule["drug_class_rules"] if s["drug_class_id"] == cls]
        resolved = {k: (v(sub) if callable(v) else v) for k, v in update.items()}
        sub.update(resolved)
        sub["clinical_review"] = review(review_note)
        check_copy(sub)


INFERENCE = " The studies concern warfarin; applying them to other vitamin K antagonists is an inference."


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}

    # Injected anticoagulants leave every warfarin-addressed fallback (Q7).
    for rule_id in FALLBACK_RULES:
        [sub] = [s for s in by_id[rule_id]["drug_class_rules"] if s["drug_class_id"] == "anticoagulants"]
        excludes = sub["profile_gate"]["excludes"]["drug_classes_any"]
        assert excludes == ["doacs", "vitamin_k_antagonists"], (rule_id, excludes)
        excludes.append("injectable_anticoagulants")

    sjw = by_id["RULE_INGREDIENT_ST_JOHNS_WORT"]
    shared_vka_text(sjw, {
        "alert_headline": "Avoid St. John's wort with warfarin-type blood thinners",
        "alert_body": (
            "If you take warfarin or another warfarin-type blood thinner, avoid St. John's wort: it can weaken the medicine's "
            "effect. Tell your prescriber about any use or change so INR checks can be planned."
        ),
        "action": (
            "If you take warfarin or another warfarin-type blood thinner (a vitamin K antagonist), avoid St. John's wort. If you "
            "already take both, tell your anticoagulation team before stopping either, because starting or stopping "
            "it can change your INR."
        ),
        "mechanism": (
            "St John’s wort can induce drug metabolism and reduce warfarin anticoagulation; the acenocoumarol "
            "(Sinthrome, UK) and phenprocoumon (Marcumar, Germany) labels describe the same weakened effect. For other "
            "vitamin K antagonists this is a precautionary class inference. S-warfarin is predominantly metabolized "
            "by CYP2C9, while other pathways contribute to R-warfarin; primary work found increased clearance of both "
            "enantiomers."
        ),
        "sources": lambda s: [*s["sources"], SINTHROME, MARCUMAR],
    }, "Q7 and section 2: avoid for warfarin, acenocoumarol and phenprocoumon, each with its own label (exact pairs "
       "DSI_WAR_SJW, DSI_ACENOCOUMAROL_SJW, DSI_PHENPROCOUMON_SJW); other vitamin K antagonists by stated "
       "precautionary class inference. Injected anticoagulants are excluded from the unidentified fallback.")
    [doac] = [s for s in sjw["drug_class_rules"] if s["drug_class_id"] == "doacs"]
    doac.update({
        "mechanism": (
            "St. John's wort induces P-gp and CYP3A pathways that can lower direct oral anticoagulant exposure, "
            "reducing protection against stroke or clot formation. The apixaban and rivaroxaban labels name St. "
            "John's wort among inducers to avoid, and the dabigatran label says P-gp inducers should generally be "
            "avoided. Edoxaban's UK label says to use caution with P-gp inducers including St. John's wort; for "
            "edoxaban, avoid is PharmaGuide precautionary policy."
        ),
        "sources": [*doac["sources"], SAVAYSA, LIXIANA],
        "clinical_review": review(
            "Section 2: avoid for apixaban, rivaroxaban, dabigatran and betrixaban; for edoxaban avoid is retained as "
            "precautionary policy (UK label: caution; exact pair DSI_EDOXABAN_SJW). No INR instruction for DOAC users."
        ),
    })

    shared_vka_text(by_id["RULE_INGREDIENT_GLUCOSAMINE"], {
        "alert_headline": "Can raise INR with warfarin-type blood thinners",
        "alert_body": (
            "If you take warfarin or another warfarin-type blood thinner, do not start glucosamine unless your anticoagulation "
            "clinician agrees and plans INR checks."
        ),
        "action": (
            "Do not start glucosamine while taking warfarin or another warfarin-type blood thinner unless your anticoagulation "
            "clinician has specifically agreed and arranged appropriate INR monitoring. Tell them before stopping or "
            "changing glucosamine. Some warfarin labels advise against this combination."
        ),
        "informational_note": "Glucosamine can raise INR in people taking warfarin-type blood thinners.",
        "mechanism": lambda s: s["mechanism"] + (
            " The UK acenocoumarol (Sinthrome) label reports a raised INR with glucosamine and oral vitamin K "
            "antagonists, and the German phenprocoumon (Marcumar) label says glucosamine can strengthen their effect; "
            "both advise close monitoring when glucosamine is started or stopped. For other vitamin K antagonists "
            "this is an inference."
        ),
        "sources": lambda s: [*s["sources"], SINTHROME, MARCUMAR],
    }, "Q3: caution kept, with the do-not-start-without-agreement action; no recheck interval; not a "
       "contraindication. Q7: warfarin, acenocoumarol and phenprocoumon labels support it (exact pairs); other vitamin "
       "K antagonists by inference.")

    shared_vka_text(by_id["RULE_INGREDIENT_CRANBERRY"], {
        "action": (
            "If you take warfarin or another warfarin-type blood thinner, contact your anticoagulation team before starting, "
            "stopping or materially changing cranberry supplements or concentrates. The studies used warfarin; for "
            "other warfarin-type blood thinners the concern is inferred."
        ),
        "mechanism": lambda s: s["mechanism"] + INFERENCE,
    }, "Q7: the direct evidence is warfarin-specific; the extension to other vitamin K antagonists is stated as an "
       "inference.")

    shared_vka_text(by_id["RULE_IQM_COQ10_HEART_DISEASE_STATINS"], {
        "alert_body": (
            "Evidence for a CoQ10–warfarin interaction is mixed. If you take warfarin or another warfarin-type blood thinner, ask "
            "whether INR checks are needed when your CoQ10 use changes."
        ),
        "action": (
            "If you take warfarin or another warfarin-type blood thinner, tell your anticoagulation team before you start, stop "
            "or substantially change CoQ10, so they can decide whether your INR needs extra checks. The label evidence "
            "is for warfarin; for other warfarin-type blood thinners it is inferred."
        ),
        "mechanism": lambda s: s["mechanism"] + INFERENCE,
    }, "Q7: the direct evidence is warfarin-specific; the extension to other vitamin K antagonists is stated as an "
       "inference.")

    for rule_id in ("RULE_IQM_GINGER_BLEEDING", "RULE_OTHER_GINGER_EXTRACT_BLEEDING"):
        shared_vka_text(by_id[rule_id], {
            "action": (
                "If you take warfarin or another warfarin-type medicine, talk to your prescriber before using ginger "
                "supplements or concentrates, and report unusual bruising or bleeding. The evidence is from warfarin; "
                "for other warfarin-type medicines it is inferred."
            ),
            "mechanism": lambda s: s["mechanism"] + INFERENCE,
        }, "Q7: the direct evidence is warfarin-specific; the extension to other vitamin K antagonists is stated as "
           "an inference, in both ginger records.")

    inr_copy_pass(by_id)
    # last_reviewed marks a clinical review: only the rules carrying Dr. Pham's signed decisions. The INR copy pass
    # (Part B 3D) is agent wording and leaves last_reviewed alone.
    for rule_id in FALLBACK_RULES:
        by_id[rule_id]["last_reviewed"] = TODAY


TEMPLATE_OLD = " and ask about INR or bleeding checks."
TEMPLATE_NEW = " and ask about bleeding checks."
TEMPLATE_RULES: list[str] = []

# Section 2: no INR instruction for DOAC users; Q7: none for injected anticoagulants. Each INR instruction a
# whole-class sub-rule shows is addressed to warfarin (old text asserted, so a drifted entry fails loudly).
ACTION_REWRITES = {
    "RULE_INGREDIENT_GINSENG": {
        "alert_body": (
            "Panax ginseng has mixed evidence for changing how warfarin works. INR monitoring is recommended if you "
            "start a ginseng supplement.",
            "Panax ginseng has mixed evidence for changing how warfarin works. If you take warfarin, ask about INR "
            "checks when you start a ginseng supplement.",
        ),
        "action": (
            "If you take warfarin, talk to your prescriber before using ginseng. INR may need re-checking after "
            "starting.",
            "If you take warfarin, talk to your prescriber before using ginseng, as your INR may need re-checking "
            "after you start it.",
        ),
        "mechanism": (
            "Mixed evidence — some studies show reduced INR (efficacy reduction); others null.",
            "Mixed evidence in warfarin users — some studies show reduced INR (efficacy reduction); others null.",
        ),
    },
    "RULE_INGREDIENT_OMEGA_3": {"action": (
        "Inform your warfarin prescriber about omega-3 supplements. Ask about INR monitoring when starting, stopping "
        "or changing them.",
        "If you take warfarin, tell your prescriber about omega-3 supplements and ask about INR monitoring when "
        "starting, stopping or changing them.",
    )},
    "RULE_INGREDIENT_FISH_OIL": {"action": (
        "Tell your warfarin prescriber about omega-3 (EPA/DHA) supplements and ask about INR monitoring when starting, "
        "stopping or changing them.",
        "If you take warfarin, tell your prescriber about omega-3 (EPA/DHA) supplements and ask about INR monitoring "
        "when starting, stopping or changing them.",
    )},
    "RULE_INGREDIENT_CHAMOMILE": {"action": (
        "Avoid large amounts of chamomile tea (>4 cups/day) or concentrated chamomile extracts while on warfarin. "
        "Inform your prescriber. Monitor INR if chamomile consumption is substantial or newly started.",
        "If you take warfarin, avoid large amounts of chamomile tea (>4 cups/day) or concentrated chamomile extracts, "
        "tell your prescriber, and ask about INR checks if your use is substantial or new.",
    )},
    "RULE_INGREDIENT_CAT_S_CLAW": {"action": (
        "Inform your prescriber if taking cat's claw while on anticoagulant therapy. Monitor for signs of excessive "
        "anticoagulation (unusual bruising, prolonged bleeding). Avoid in patients requiring tight INR control.",
        "Tell your prescriber if you take cat's claw with a blood thinner, and watch for unusual bruising or "
        "prolonged bleeding. If you take warfarin and need tight INR control, avoid it.",
    )},
    "RULE_INGREDIENT_DEVILS_CLAW": {"action": (
        "Inform your prescriber if taking devil's claw while on warfarin or other anticoagulants. Monitor INR if "
        "starting or stopping devil's claw supplementation.",
        "Tell your prescriber if you take devil's claw with a blood thinner. If you take warfarin, ask about INR "
        "checks when starting or stopping it.",
    )},
    "RULE_IQM_CHONDROITIN": {"action": (
        "Monitor INR in warfarin-treated patients who initiate chondroitin supplements. Alert prescriber to supplement "
        "use. Consider avoiding chondroitin if INR is already at the upper therapeutic range.",
        "Tell your prescriber about chondroitin. If you take warfarin, ask about INR checks when you start it, and ask "
        "whether to avoid it if your INR is already at the top of your range.",
    )},
    "RULE_IQM_BLACK_SEED_OIL_DIABETES": {"action": (
        "Monitor INR if combining black seed oil with warfarin or other anticoagulants. Alert prescriber to use.",
        "Tell your prescriber about black seed oil. If you take warfarin, ask whether INR checks are needed when your "
        "use changes.",
    )},
    "RULE_IQM_DHA_BLEEDING": {"action": (
        "Tell your warfarin prescriber about DHA supplements and ask about INR monitoring when starting, stopping or "
        "changing them.",
        "If you take warfarin, tell your prescriber about DHA supplements and ask about INR monitoring when starting, "
        "stopping or changing them.",
    )},
    "RULE_IQM_ALCAR_THYROID": {"action": (
        "Monitor INR when starting or stopping ALCAR in patients on anticoagulants. Alert prescriber to use.",
        "Tell your prescriber about acetyl-L-carnitine. If you take warfarin, ask whether INR checks are needed when "
        "you start or stop it.",
    )},
    "RULE_IQM_QUERCETIN_THYROID": {"action": (
        "Monitor INR frequently when starting or stopping quercetin supplementation in patients on warfarin. Alert "
        "prescriber to dose and any INR changes.",
        "If you take warfarin, ask about INR checks when starting or stopping quercetin, and tell your prescriber the "
        "dose.",
    )},
    "RULE_BANNED_CBD_INTERACTIONS": {"action": (
        "Monitor INR more frequently when starting or stopping CBD. Inform prescriber.",
        "Tell your prescriber about CBD. If you take warfarin, ask about closer INR checks when starting or stopping "
        "it.",
    )},
    # Part B 3D: "Adding them must not widen warfarin-specific instructions" (not only INR sentences).
    "RULE_INGREDIENT_VITAMIN_D": {"action": (
        "Tell your warfarin prescriber about changes in vitamin D supplementation.",
        "If you take warfarin, tell your prescriber about changes in vitamin D supplementation.",
    )},
    "RULE_INGREDIENT_FLAXSEED": {"action": (
        "Tell your warfarin prescriber about flaxseed or flaxseed oil supplements",
        "If you take warfarin, tell your prescriber about flaxseed or flaxseed oil supplements",
    )},
}

# Whole-class anticoagulant pairs reach DOAC and injected-anticoagulant users too: their warfarin sentences are
# addressed to warfarin users (old text asserted).
PAIR_REWRITES = {
    "DSI_ANTICOAG_GINSENG": (
        "Monitor INR closely if taking ginseng with warfarin. INR may need to be checked more frequently and warfarin "
        "dose adjusted.",
        "If you take warfarin, tell your prescriber before taking ginseng: your INR may need checking more often, and "
        "your prescriber may adjust the warfarin dose.",
    ),
    "DSI_ANTICOAG_CBD": (
        "Monitor INR closely if CBD is started or stopped with warfarin. Dose adjustment of warfarin may be required. "
        "Inform prescriber of all CBD use including oils and capsules.",
        "Tell your prescriber about all CBD use, including oils and capsules. If you take warfarin, ask about closer "
        "INR checks when CBD is started or stopped; your prescriber may need to adjust the warfarin dose.",
    ),
}


def inr_copy_pass(by_id: dict) -> None:
    for rule in by_id.values():
        for sub in rule.get("drug_class_rules", []):
            if sub["drug_class_id"] == "anticoagulants" and TEMPLATE_OLD in (sub.get("alert_body") or ""):
                sub["alert_body"] = sub["alert_body"].replace(TEMPLATE_OLD, TEMPLATE_NEW)
                check_copy(sub)
                TEMPLATE_RULES.append(rule["id"])
    assert len(TEMPLATE_RULES) == 19, sorted(TEMPLATE_RULES)
    for rule_id, fields in ACTION_REWRITES.items():
        [sub] = [s for s in by_id[rule_id]["drug_class_rules"] if s["drug_class_id"] == "anticoagulants"]
        for key, (old, new) in fields.items():
            assert old in sub[key], (rule_id, key)
            sub[key] = sub[key].replace(old, new)
        check_copy(sub)


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    edit(CLASSES, classes)
    edit(TAXONOMY, taxonomy)
    edit(CURATED, curated)
    edit(CRITICAL, critical)
    edit(RULES, rules)
