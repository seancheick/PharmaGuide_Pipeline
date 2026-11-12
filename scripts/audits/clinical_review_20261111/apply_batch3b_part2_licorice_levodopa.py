"""Batch 3b, part 2: licorice (A14, F4) and levodopa + iron (F2) of Dr. Pham's 2026-11-11 review, plus the
alignment of curated supplement canonical ids with the ids verification ships.

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3b_part2_licorice_levodopa.py

A14  Licorice + antihypertensives: avoid for glycyrrhizin-containing licorice; verified DGL is excluded by
     identity (it routes to its own botanical, which has no licorice rule); a product that does not say it is
     DGL is not assumed to be. A licorice_root label meets both licorice rules (its IQM twin), so both
     antihypertensive sub-rules carry one text. EU herbal monograph EMA/HMPC/108399/2024 Rev. 1 (read
     2026-11-11), 4.5: liquorice root may counteract the action of antihypertensive medicines.
F4   Licorice + cardiac glycosides: avoid, DGL excluded, no glycyrrhizin floor. The same monograph, 4.5: not to
     be used concomitantly with cardiac glycosides; LANOXIN (setid d91e3646): hypokalemia may predispose to
     digoxin toxicity; PMID 28660884 (meta-analysis): plasma potassium fell with chronic glycyrrhizic acid.
     The sub-rule sits on the IQM licorice rule, which licorice_root and (now) chinese_licorice also meet.
     The monograph covers G. glabra, G. inflata and G. uralensis root, so the IQM licorice form names those
     species and chinese_licorice twins to it (scripts/identity/interaction.py). DGL's bare "Glycyrrhiza
     glabra" alias goes: a species name is not a DGL claim.
F2   Levodopa + iron: caution from SINEMET (setid 9b17b028): iron salts, including multivitamins with iron
     salts, should be taken with caution because they chelate levodopa and carbidopa and reduce their
     bioavailability. The label gives no interval and none is stated. Combination products reach the pair
     through their levodopa ingredient (RxCUI 6375).
IDs  verify_interactions.py derives a supplement side's canonical id from its CUI and ignores the stored one.
     Eight stored ids differed from what ships; the shipped ids are the ones products carry (traced through
     the 2026-11-02 catalog), so the stored ids are aligned and nothing that ships changes.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

DATA = REPO / "scripts/data"
RULES = DATA / "ingredient_interaction_rules.json"
CURATED = DATA / "curated_interactions/curated_interactions_v1.json"
BOTANICALS = DATA / "botanical_ingredients.json"
IQM = DATA / "ingredient_quality_map.json"

REVIEW_FILE = "audits/clinical_review_20261111/DR_PHAM_REVIEW_20261111.md"
EMA_LICORICE = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-"
    "glycyrrhiza-glabra-l-glycyrrhiza-inflata-bat-glycyrrhiza-uralensis-fisch-radix-revision-1_en.pdf"
)
LANOXIN = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d91e3646-4c63-4512-ab22-db39c085c4dc"
SINEMET = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=9b17b028-964a-473c-823d-81423535bd66"
META_ANALYSIS = "https://pubmed.ncbi.nlm.nih.gov/28660884/"
DGL_SCOPE = (
    "Verified deglycyrrhizinated (DGL) licorice is a different preparation; a licorice product that does not "
    "say it is DGL is treated as containing glycyrrhizin."
)


def _gate(drug_class: str) -> dict:
    return {
        "gate_type": "drug_class",
        "requires": {"conditions_any": [], "drug_classes_any": [drug_class], "profile_flags_any": []},
        "excludes": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
                     "product_forms_any": [], "nutrient_forms_any": []},
        "dose": None,
    }


def _review(notes: str) -> dict:
    return {"reviewer": "Dr. Pham", "reviewed_at": "2026-11-11", "file": REVIEW_FILE, "notes": notes}


ANTIHYPERTENSIVES = {
    "drug_class_id": "antihypertensives",
    "severity": "avoid",
    "evidence_level": "established",
    "mechanism": (
        "Glycyrrhizin in licorice can raise blood pressure and lower potassium, working against blood-pressure "
        "treatment. The EU herbal monograph for licorice root says it may counteract the action of "
        "antihypertensive medicines. A meta-analysis of glycyrrhizic-acid trials found higher blood pressure and "
        "lower plasma potassium; in healthy young adults, licorice supplying 100 mg/day glycyrrhizic acid, a "
        "level WHO has suggested is unlikely to harm most adults, raised home systolic blood pressure within 2 "
        "weeks, and people with hypertension respond more strongly. " + DGL_SCOPE
    ),
    "action": (
        "Avoid glycyrrhizin-containing licorice while taking blood-pressure medicine unless your prescriber has "
        "reviewed it. Verified DGL licorice is a different preparation; treat a licorice product that does not "
        "say it is DGL as containing glycyrrhizin."
    ),
    "sources": [
        EMA_LICORICE,
        "https://www.nccih.nih.gov/health/licorice-root",
        META_ANALYSIS,
        "https://pubmed.ncbi.nlm.nih.gov/38246526/",
        "https://pubmed.ncbi.nlm.nih.gov/12574791/",
    ],
    "alert_headline": "Can work against blood-pressure medicine",
    "alert_body": (
        "Licorice that contains glycyrrhizin can raise blood pressure and lower potassium, working against "
        "blood-pressure medicine. If you take blood-pressure medication, avoid it unless your prescriber has "
        "reviewed it. Verified DGL licorice is a different preparation; a product that does not say it is DGL "
        "may contain glycyrrhizin."
    ),
    "informational_note": (
        "Licorice with glycyrrhizin can raise blood pressure — relevant to people taking blood-pressure "
        "medication."
    ),
    "profile_gate": _gate("antihypertensives"),
    "direction": "harmful",
    "materiality": "presence",
    "clinical_review": _review(
        "A14: avoid for glycyrrhizin-containing licorice; verified DGL excluded; unknown preparation is not "
        "assumed to be DGL. Wording and sources prepared by agent from the EMA monograph and cited studies."
    ),
}

CG_MECHANISM = (
    "Glycyrrhizin in licorice can lower blood potassium, and low potassium makes digoxin toxicity more likely. "
    "The EU herbal monograph for licorice root says it is not to be used together with cardiac glycosides, and "
    "the digoxin (LANOXIN) label lists hypokalemia among conditions that may predispose to digoxin toxicity. A "
    "meta-analysis of glycyrrhizic-acid trials found lower plasma potassium. The sources set no amount of "
    "glycyrrhizin below which this concern does not apply. " + DGL_SCOPE
)
CARDIAC_GLYCOSIDES = {
    "drug_class_id": "cardiac_glycosides",
    "severity": "avoid",
    "evidence_level": "established",
    "mechanism": CG_MECHANISM,
    "action": (
        "Avoid glycyrrhizin-containing licorice with digoxin or another cardiac glycoside unless your prescriber "
        "advises it. Verified DGL licorice is a different preparation; treat a licorice product that does not "
        "say it is DGL as containing glycyrrhizin."
    ),
    "sources": [EMA_LICORICE, LANOXIN, META_ANALYSIS],
    "alert_headline": "Can raise digoxin toxicity risk",
    "alert_body": (
        "Licorice that contains glycyrrhizin can lower potassium, which makes digoxin toxicity more likely. If "
        "you take digoxin, avoid it unless your prescriber advises it. Verified DGL licorice is a different "
        "preparation; a product that does not say it is DGL may contain glycyrrhizin."
    ),
    "informational_note": (
        "Licorice with glycyrrhizin can lower potassium — relevant to people taking digoxin or other cardiac "
        "glycosides."
    ),
    "profile_gate": _gate("cardiac_glycosides"),
    "direction": "harmful",
    "materiality": "presence",
    "clinical_review": _review(
        "F4: avoid for glycyrrhizin-containing licorice with cardiac glycosides; verified DGL excluded; no "
        "glycyrrhizin floor. Wording and sources prepared by agent from the EMA monograph and LANOXIN label."
    ),
}

AGENT_VERIFICATION = {"status": "verified", "verified_at": "2026-11-11", "method": "agent_label_content_review_2026_11_11"}

PAIR_CARDIACGLYC_LICORICE = {
    "id": "DSI_CARDIACGLYC_LICORICE",
    "type": "Med-Sup",
    "agent1_name": "Cardiac glycosides (class)",
    "agent1_id": "class:cardiac_glycosides",
    "agent2_name": "Licorice root (glycyrrhizin)",
    "agent2_id": "C0086555",
    "severity": "Major",
    "interaction_effect_type": "Additive",
    "mechanism": CG_MECHANISM,
    "management": (
        "Avoid glycyrrhizin-containing licorice with digoxin or another cardiac glycoside unless the prescriber "
        "advises it. A product described as deglycyrrhizinated (DGL) is a different preparation, but the label "
        "must establish that identity; a licorice product that does not say it is DGL is treated as containing "
        "glycyrrhizin."
    ),
    "source_urls": [EMA_LICORICE, LANOXIN, META_ANALYSIS],
    "source_pmids": ["28660884"],
    "verification": {
        **AGENT_VERIFICATION,
        "verified_with": {"rxnorm": True, "umls": True, "pubmed": True},
        "notes": (
            "EMA/HMPC/108399/2024 Rev. 1 section 4.5, the LANOXIN warnings on hypokalemia and the PMID 28660884 "
            "abstract read 2026-11-11; C0086555 (UMLS, licorice) checked live; class:cardiac_glycosides members "
            "are RxNorm-verified in drug_classes.json. Severity and DGL scope decided by Dr. Pham (clinical "
            "review 2026-11-11, F4); passages read by agent."
        ),
    },
    "evidence_basis": "label_regulatory",
    "clinical_confidence": "medium",
    "applies_to": "whole_class",
    "evidence_notes": (
        "EU herbal monograph on liquorice root (EMA/HMPC/108399/2024, Final Rev. 1, 4 March 2026; covers "
        "Glycyrrhiza glabra, G. inflata and G. uralensis root), 4.5: not to be used concomitantly with diuretics, "
        "cardiac glycosides, corticosteroids, stimulant laxatives or other medicines that may aggravate "
        "electrolyte imbalance. LANOXIN (digoxin) label: hypokalemia may predispose to digoxin toxicity. PMID "
        "28660884 (meta-analysis of 18 studies of daily glycyrrhizic acid): plasma potassium fell. No study of "
        "the combination's outcome was read, and the sources set no glycyrrhizin amount below which the concern "
        "does not apply. Verified DGL routes to its own identity and does not meet this pair."
    ),
    "agent1_canonical_id": None,
    "agent2_canonical_id": "licorice",
    "direction": "harmful",
    "materiality": "presence",
}

PAIR_LEVODOPA_IRON = {
    "id": "DSI_LEVODOPA_IRON",
    "type": "Med-Sup",
    "agent1_name": "Levodopa",
    "agent1_id": "6375",
    "agent2_name": "Iron (supplement)",
    "agent2_id": "C0302583",
    "severity": "Moderate",
    "interaction_effect_type": "Inhibitor",
    "mechanism": (
        "Iron salts can form chelates with levodopa and carbidopa and so reduce how much of the medicine is "
        "available to the body. The carbidopa/levodopa (SINEMET) label says this applies to iron supplements and "
        "to multivitamins that contain iron salts."
    ),
    "management": (
        "If you take carbidopa/levodopa, talk to your prescriber or pharmacist before starting an iron supplement "
        "or a multivitamin with iron; the label says to take them together with caution. The label gives no "
        "spacing interval, so ask how to time them."
    ),
    "source_urls": [SINEMET],
    "source_pmids": [],
    "verification": {
        **AGENT_VERIFICATION,
        "verified_with": {"rxnorm": True, "umls": True, "pubmed": False},
        "notes": (
            "SINEMET (setid 9b17b028) drug-interaction and patient text read 2026-11-11; RxCUI 6375 (levodopa, "
            "ingredient, Active) and C0302583 (UMLS, iron) checked live. Severity and the no-interval scope "
            "decided by Dr. Pham (clinical review 2026-11-11, F2); label passages read by agent."
        ),
    },
    "evidence_basis": "label_regulatory",
    "clinical_confidence": "medium",
    "applies_to": "specific_drug",
    "evidence_notes": (
        "SINEMET (carbidopa and levodopa) label, read 2026-11-11: carbidopa/levodopa and iron salts, or "
        "multivitamins containing iron salts, should be taken together with caution, because iron salts can "
        "chelate levodopa and carbidopa and reduce their bioavailability. The label gives no spacing interval, so "
        "none is stated. Combination products (carbidopa/levodopa, carbidopa/levodopa/entacapone) reach this "
        "pair through their levodopa ingredient (RxCUI 6375)."
    ),
    "agent1_canonical_id": None,
    "agent2_canonical_id": "iron",
    "direction": "harmful",
    "materiality": "presence",
}

# Stored supplement canonical id -> the id verification derives from the CUI and ships (traced 2026-11-11).
SHIPPED_CANONICAL = {
    "DSI_STATINS_GRAPEFRUIT": ("grapefruit", None),  # Med-Food food note; no supplement identity
    "DSI_CCB_GRAPEFRUIT": ("grapefruit", None),
    "DSI_IMMUNO_GRAPEFRUIT": ("grapefruit", None),
    "DSI_LEVOTHYROXINE_COFFEE": ("coffee", None),
    "DSI_BETABLOCK_EPHEDRA": ("ephedra", "BANNED_EPHEDRA"),
    "DSI_MAOI_TYRAMINE": ("tyramine", "ADD_TYRAMINE_RICH_EXTRACT"),
    "DSI_ANTICOAG_VINPOCETINE": ("nootropic_vinpocetine", "vinpocetine"),
    "DSI_IMMUNOSUP_PROBIOTICS": ("probiotic_unspecified", "probiotics"),
}


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}
    for rule_id in ("RULE_IQM_LICORICE_HYPERTENSION", "RULE_BOTANICAL_LICORICE_ROOT"):
        rule = by_id[rule_id]
        subs = rule["drug_class_rules"]
        [i] = [n for n, s in enumerate(subs) if s["drug_class_id"] == "antihypertensives"]
        assert subs[i]["severity"] == "caution"
        subs[i] = copy.deepcopy(ANTIHYPERTENSIVES)
        rule["last_reviewed"] = "2026-11-11"
        rule["review_owner"] = (
            "Dr. Pham (clinical review 2026-11-11, licorice A14/F4 severity and DGL scope); monograph and label "
            "passages read by agent; pharmaguide_clinical_team"
        )
    iqm_rule = by_id["RULE_IQM_LICORICE_HYPERTENSION"]
    assert not [s for s in iqm_rule["drug_class_rules"] if s["drug_class_id"] == "cardiac_glycosides"]
    iqm_rule["drug_class_rules"].append(copy.deepcopy(CARDIAC_GLYCOSIDES))


def curated(blob: dict) -> None:
    rows = blob["interactions"]
    by_id = {r["id"]: r for r in rows}
    assert "DSI_CARDIACGLYC_LICORICE" not in by_id and "DSI_LEVODOPA_IRON" not in by_id
    for pair_id, (old, new) in SHIPPED_CANONICAL.items():
        assert by_id[pair_id]["agent2_canonical_id"] == old, pair_id
        by_id[pair_id]["agent2_canonical_id"] = new
    antihyp = by_id["DSI_ANTIHYP_LICORICE"]
    assert antihyp["severity"] == "Major" and EMA_LICORICE not in antihyp["source_urls"]
    antihyp["source_urls"] = [EMA_LICORICE, *antihyp["source_urls"]]
    rows.extend([copy.deepcopy(PAIR_CARDIACGLYC_LICORICE), copy.deepcopy(PAIR_LEVODOPA_IRON)])


def botanicals(blob: dict) -> None:
    dgl = next(b for b in blob["botanical_ingredients"] if b["id"] == "dgl_deglycyrrhizinated_licorice")
    assert "Glycyrrhiza glabra" in dgl["aliases"]
    dgl["aliases"] = [a for a in dgl["aliases"] if a != "Glycyrrhiza glabra"]


def iqm(blob: dict) -> None:
    form = blob["licorice"]["forms"]["licorice root extract"]
    old = "Glycyrrhiza glabra root extract. "
    assert form["notes"].startswith(old)
    form["notes"] = (
        "Licorice root extract: Glycyrrhiza glabra, Glycyrrhiza inflata or Glycyrrhiza uralensis root, the species "
        "the EU herbal monograph on liquorice root covers. " + form["notes"][len(old):]
    )


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    edit(RULES, rules)
    edit(CURATED, curated)
    edit(BOTANICALS, botanicals)
    edit(IQM, iqm)
