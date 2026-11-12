"""Apply F1/F3 source scope and a deliberately unpublished SINEMET B6 record."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

DATA = REPO / "scripts/data"
DAILYMED = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid="
ISOTRETINOIN = DAILYMED + "4e8516dc-a3c6-4d8f-aa14-2c37c6c8f6e6"
ABSORICA = DAILYMED + "3ef0cff8-19c1-4441-b780-fca6c7ee1615"
FOSAMAX = DAILYMED + "14e931fd-2c5f-4d90-b7db-5980706f4a56"
IBANDRONATE = DAILYMED + "6ca94cce-a2bb-421f-bd8f-6b14bc2bd985"
ACTONEL = DAILYMED + "24ed00e0-25e2-49a8-97fc-66c1b417dc0b"
ATELVIA = DAILYMED + "c89430be-15f1-4b8b-ab7e-738de716ee7d"
SINEMET = DAILYMED + "9b17b028-964a-473c-823d-81423535bd66"
ODS = "https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/"


def _vitamin_pair(beta: bool) -> dict:
    return {
        "id": "DSI_ISOTRETINOIN_BETA_CAROTENE" if beta else "DSI_ISOTRETINOIN_VITAMIN_A",
        "type": "Med-Sup",
        "agent1_name": "Isotretinoin",
        "agent1_id": "6064",
        "agent1_canonical_id": None,
        "agent2_name": "Beta-carotene (supplement)" if beta else "Vitamin A (supplement)",
        "agent2_id": "ref:beta_carotene" if beta else "C0042839",
        "agent2_canonical_id": "beta_carotene" if beta else "vitamin_a",
        "severity": "Major",
        "interaction_effect_type": "Additive",
        "mechanism": (
            "Beta-carotene is a provitamin A carotenoid that the body can convert to vitamin A; it is not "
            "preformed retinol. The oral isotretinoin label advises avoiding supplements containing vitamin A. "
            "Applying that precaution to beta-carotene supplements does not mean their toxicity is the same as "
            "preformed retinol, and the label does not separately quantify this combination's risk."
            if beta else
            "Oral isotretinoin is closely related to vitamin A. Taking vitamin A supplements with it may add "
            "to isotretinoin-associated adverse reactions; the oral isotretinoin and ABSORICA labels advise "
            "avoiding concomitant vitamin A supplements."
        ),
        "management": (
            "Avoid beta-carotene supplements while taking oral isotretinoin unless your prescriber has reviewed "
            "the combination. This is a precaution for a vitamin A precursor, not a claim of the same toxicity "
            "as retinol. Do not stop or change your prescribed isotretinoin to use a supplement."
            if beta else
            "Avoid supplements containing vitamin A while taking oral isotretinoin. Ask your prescriber about "
            "your supplements, including multivitamins. Do not stop or change your prescribed isotretinoin to "
            "use a supplement."
        ),
        "source_urls": [ISOTRETINOIN, ABSORICA] + ([ODS] if beta else []),
        "source_pmids": [],
        "verification": {
            "status": "verified", "verified_at": "2026-11-12",
            "method": "agent_label_content_review_2026_11_12",
            "verified_with": {"rxnorm": True, "umls": not beta, "pubmed": False},
            "notes": "DailyMed section 7.1 and RxNorm 6064 content checked by agent; beta-carotene identity "
            "and provitamin distinction checked against NIH ODS. Not clinician review of authored wording.",
        },
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "medium" if beta else "high",
        "applies_to": "specific_drug",
        "evidence_notes": (
            "F1, Dr. Pham review 2026-11-11: oral isotretinoin plus vitamin A is avoid; beta-carotene must not "
            "be automatically exempted. The follow-up signed by Dr. Pham and relayed by Sean retains a separate "
            "Major precaution with the provitamin A qualification. "
            if beta else
            "F1, Dr. Pham review 2026-11-11: avoid oral isotretinoin plus supplemental vitamin A. "
        ) + "Wording prepared by agent, not reviewed by Dr. Pham. Scope is supplements and oral isotretinoin, "
        "not foods, unrelated carotenoids or topical retinoids. RxNorm 6064 is isotretinoin, not tretinoin.",
        "direction": "harmful", "materiality": "presence",
    }


def _mineral_management(mineral: str) -> str:
    return (
        f"For oral bisphosphonates, ask your pharmacist to schedule {mineral} using the exact medicine and "
        "formulation. Alendronate (Fosamax): wait at least 30 minutes after the medicine before taking "
        f"{mineral}. Ibandronate tablets (Boniva): wait at least 60 minutes after the tablet. "
        "Immediate-release risedronate (Actonel): take the medicine at least 30 minutes before the first "
        f"food, drink other than plain water, or other oral medicine; take {mineral} at a different time of day. "
        f"Delayed-release risedronate (Atelvia): take it immediately after breakfast and take {mineral} at a "
        "different time of day. These oral-absorption instructions do not apply to intravenous bisphosphonates."
    )


def apply() -> None:
    path = DATA / "curated_interactions/curated_interactions_v1.json"
    data = data_batch.load(path)
    rows = {r["id"]: r for r in data["interactions"]}
    for beta in (False, True):
        row = _vitamin_pair(beta)
        if row["id"] in rows:
            rows[row["id"]].clear()
            rows[row["id"]].update(row)
        else:
            data["interactions"].append(row)
    magnesium = rows["DSI_MAGNESIUM_BISPHOSPHONATE"]
    calcium = copy.deepcopy(magnesium)
    calcium.update({
        "id": "DSI_CALCIUM_BISPHOSPHONATE", "agent2_name": "Calcium", "agent2_id": "C0006675",
        "agent2_canonical_id": "calcium",
    })
    for row, mineral in ((magnesium, "magnesium"), (calcium, "calcium")):
        row.update({
            "agent1_name": "Oral bisphosphonates (class)",
            "severity": "Moderate",
            "mechanism": f"{mineral.capitalize()}-containing products can interfere with absorption of oral "
            "bisphosphonates. This gastrointestinal interaction does not establish a warning for intravenous "
            "bisphosphonates; dosing instructions differ by oral medicine and formulation.",
            "management": _mineral_management(mineral),
            "source_urls": [FOSAMAX, IBANDRONATE, ACTONEL, ATELVIA],
            "source_pmids": [],
            "verification": {
                "status": "verified", "verified_at": "2026-11-12",
                "method": "agent_label_content_review_2026_11_12",
                "verified_with": {"rxnorm": True, "umls": True, "pubmed": False},
                "notes": "FOSAMAX 2.6/7.1, ibandronate tablets 2.2/7.1, ACTONEL 2.6/2.7/7.1, "
                "and delayed-release risedronate 2.2/2.3/7.1 content checked by agent. "
                "Wording prepared by agent, not reviewed by Dr. Pham.",
            },
            "evidence_notes": "F3, Dr. Pham review 2026-11-11: manageable oral-absorption interactions; "
            "calcium is caution with formulation-specific timing. The signed follow-up supports magnesium caution "
            "with oral bisphosphonates and medicine-specific timing. Zoledronic acid is excluded. "
            "Release limitation: the ingredient-level class does not by itself distinguish oral from "
            "intravenous ibandronate; route qualification must be verified in the consumer before release. "
            "No source establishes one universal interval. Wording prepared by agent, not reviewed by Dr. Pham.",
        })
    if calcium["id"] in rows:
        rows[calcium["id"]].clear()
        rows[calcium["id"]].update(calcium)
    else:
        data["interactions"].append(calcium)
    data_batch.save(path, data)

    path = DATA / "drug_classes.json"
    data = data_batch.load(path)
    row = data["classes"]["class:bisphosphonates"]
    members = [(r, n) for r, n in zip(row["member_rxcuis"], row["member_names"]) if r != "77655"]
    row["member_rxcuis"] = [r for r, _ in members]
    row["member_names"] = [n for _, n in members]
    row["excluded_member_rxcuis"] = sorted(
        set(row.get("excluded_member_rxcuis", [])) | {"77655", "904952", "904954", "904955"}
    )
    row["description"] = "Bisphosphonate medicines with oral formulations; mineral-interaction rules concern oral absorption."
    row["notes"] = (
        "F3 (Dr. Pham, 2026-11-11): zoledronic acid 77655 is intravenous-only and excluded from "
        "oral-absorption rules. Alendronate, ibandronate and risedronate identities checked live in RxNorm "
        "2026-11-12. Intravenous ibandronate shares ingredient 115264 with tablets: exact nonoral concepts "
        "904952 (prefilled syringe), 904954 (Boniva prefilled syringe), and 904955 (injection) are excluded, "
        "verified against RxNorm related SCD/SBD concepts on 2026-11-12. Consumer qualification must prove "
        "that selected-product exclusions take precedence over its ingredient membership; do not apply oral "
        "timing to an injection. Unknown route retains qualified oral wording."
    )
    data["_metadata"]["total_members"] = sum(len(c["member_rxcuis"]) for c in data["classes"].values())
    data_batch.save(path, data)

    path = DATA / "medication_depletions.json"
    data = data_batch.load(path)
    row = {
        "id": "DEP_CARBIDOPA_LEVODOPA_B6",
        "drug_ref": {"type": "drug", "id": "103990", "display_name": "Carbidopa / levodopa (SINEMET)"},
        "depleted_nutrient": {"standard_name": "Vitamin B6", "canonical_id": "vitamin_b6_pyridoxine"},
        "depletion_type": "depletion", "severity": "moderate",
        "mechanism": "The SINEMET label reports that treatment may contribute to reduced vitamin B6 levels; "
        "higher carbidopa/levodopa doses may increase the risk of deficiency.",
        "clinical_impact": "Postmarketing seizures associated with vitamin B6 deficiency have been reported. "
        "The label does not quantify incidence or establish an onset interval.",
        "recommendation": "SINEMET treatment may be initiated and continued while supplementing vitamin B6. "
        "The prescriber evaluates levels and supplements if needed; this record is not a warning to avoid B6.",
        "onset_timeline": "not established", "evidence_level": "possible",
        "monitoring_note": "The label directs evaluation of vitamin B6 prior to initiation, periodically "
        "during treatment and as clinically indicated, with supplementation to sufficient levels when low.",
        "sources": [{"source_type": "fda", "label": "SINEMET prescribing information: Vitamin B6 Deficiency "
                     "and Seizures; Management of Vitamin B6 Levels; pharmacokinetics", "url": SINEMET}],
        "alert_headline": "Vitamin B6 review record held",
        "alert_body": "Vitamin B6 deficiency may develop during SINEMET treatment. This source record remains withheld pending review.",
        "acknowledgement_note": "No supplementation adequacy determination has been approved for this record.",
        "monitoring_tip_short": "Discuss vitamin B6 monitoring with the prescriber.",
        "food_sources_short": "No food-source recommendation is published from this held record.",
        "citation_review_status": "needs_revision", "reviewed_at": "2026-11-12",
        "reviewer": "openai_codex_agent_source_review",
        "citation_review_note": "Agent read the SINEMET label effective 2026-08-01 and verified RxNorm MIN "
        "103990 (carbidopa / levodopa). Source content is verified, but consumer wording, severity, evidence "
        "grading and combination-product matching remain held; no Dr. Pham or B1 approval is claimed. "
        "The app compares selected, generic and ingredient RxCUIs; do not substitute levodopa 6375, which "
        "would extend this combination-label finding to levodopa alone. Publication remains blocked by "
        "citation_review_status until the exact combination identity is qualified.",
    }
    existing = next((r for r in data["depletions"] if r["id"] == row["id"]), None)
    if existing is None:
        data["depletions"].append(row)
    else:
        existing.clear()
        existing.update(row)
    data_batch.save(path, data)


if __name__ == "__main__":
    apply()
