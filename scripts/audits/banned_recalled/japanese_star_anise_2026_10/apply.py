#!/usr/bin/env python3
"""Add HIGH_RISK_JAPANESE_STAR_ANISE (receipts: research.md in this folder).

Run once from the repo root: $PG_PYTHON scripts/audits/banned_recalled/japanese_star_anise_2026_10/apply.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

PATH = REPO / "scripts" / "data" / "banned_recalled_ingredients.json"
FDA_ADVISORY = "https://web.archive.org/web/20050115085515/http://www.fda.gov/bbs/topics/NEWS/2003/NEW00941.html"

ENTRY = {
    "id": "HIGH_RISK_JAPANESE_STAR_ANISE",
    "standard_name": "Japanese Star Anise",
    "aliases": [
        "japanese star anise",
        "illicium anisatum",
        "illicium religiosum",
        "illicium japonicum",
    ],
    "reason": (
        "Japanese star anise (Illicium anisatum) contains anisatin, a neurotoxin that can cause "
        "seizures (epilepsy), hallucinations and nausea. FDA states it has long been recognized as "
        "toxic, should be used for decorative purposes only and is not generally recognized as safe "
        "(GRAS); dried, it cannot be told apart from edible Chinese star anise (Illicium verum) by eye. "
        "Case reports describe adult seizures after tea made from it. No current prohibition was "
        "found (EU Decision 2002/75/EC on star anise imports ended in 2003), so it is high_risk "
        "rather than banned."
    ),
    "status": "high_risk",
    "class_tags": ["toxic_botanical", "botanical"],
    "match_rules": {
        "exclusions": [],
        "case_sensitive": False,
        "priority": 1,
        "match_type": "normalized",
        "confidence": "high",
        "negative_match_terms": [],
    },
    "legal_status_enum": "under_review",
    "clinical_risk_enum": "high",
    "jurisdictions": [{
        "region": "US",
        "level": "federal",
        "status": "under_review",
        "effective_date": None,
        "source": {
            "type": "fda_advisory",
            "citation": (
                "FDA news release P03-67 (2003-09-10): Japanese star anise (Illicium anisatum) has long "
                "been recognized as toxic, should be used for decorative purposes only and is not GRAS; "
                "FDA would monitor star anise imports so Japanese star anise is not labeled for food use. "
                "An advisory, not a ban."
            ),
            "accessed_date": "2026-10-20",
            "url": FDA_ADVISORY,
        },
        "jurisdiction_type": "country",
        "jurisdiction_code": "US",
        "last_verified_date": "2026-10-20",
    }],
    "references_structured": [
        {
            "type": "fda_advisory",
            "title": "FDA Issues Advisory on Star Anise \"Teas\" (P03-67)",
            "evidence_grade": "R",
            "date": "2003-09-10",
            "url": FDA_ADVISORY,
            "supports_claims": ["regulatory_action", "clinical_outcomes"],
            "evidence_summary": (
                "Japanese star anise is toxic, not GRAS and for decorative use only; star anise teas were "
                "linked to about 40 illnesses including seizures; dried Japanese and Chinese star anise "
                "cannot be distinguished by eye."
            ),
        },
        {
            "type": "pmid",
            "id": "22484123",
            "title": ("Rapid control of Chinese star anise fruits and teas for neurotoxic anisatin by Direct "
                      "Analysis in Real Time high resolution mass spectrometry"),
            "url": "https://pubmed.ncbi.nlm.nih.gov/22484123/",
            "evidence_grade": "B",
            "supports_claims": ["mechanism_of_harm"],
            "evidence_summary": (
                "Anisatin in Japanese star anise can cause epilepsy, hallucinations and nausea; its "
                "signal is typically over 1000 times larger in Japanese than in Chinese star anise."
            ),
        },
        {
            "type": "pmid",
            "id": "12014240",
            "title": "[Epileptic seizure after a cup of tea: intoxication with Japanese star anise]",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12014240/",
            "evidence_grade": "C",
            "supports_claims": ["clinical_outcomes"],
            "evidence_summary": "Case report (Dutch): an epileptic seizure after tea made from Japanese star anise.",
        },
        {
            "type": "pmid",
            "id": "12617067",
            "title": ("[An inaugural generalized tonic-clonic convulsive crisis following ingestion of "
                      "Japanese star anise]"),
            "url": "https://pubmed.ncbi.nlm.nih.gov/12617067/",
            "evidence_grade": "C",
            "supports_claims": ["clinical_outcomes"],
            "evidence_summary": "Case report (French): a first generalized tonic-clonic seizure after Japanese star anise.",
        },
    ],
    "source_category": "toxic_botanical",
    "entity_type": "ingredient",
    "regulatory_date": "2003-09-10",
    "regulatory_date_label": "FDA consumer advisory",
    "match_mode": "active",
    "cui": "C0949938",
    "external_ids": {"unii": "96MVO223I9"},
    "gsrs": {
        "substance_name": "ILLICIUM ANISATUM WHOLE",
        "substance_class": "structurallyDiverse",
        "cfr_sections": [],
        "dsld_count": None,
        "dsld_info_raw": None,
        "active_moiety": None,
        "salt_parents": [],
        "metabolic_relationships": [],
        "metabolites": [],
    },
    "ban_context": "substance",
    "safety_warning": (
        "Contains anisatin, a neurotoxin that has caused seizures. FDA calls Japanese star anise toxic "
        "and for decorative use only. Do not use it."
    ),
    "safety_warning_one_liner": "Toxic plant linked to seizures. Do not use.",
    "inactive_policy": "penalize_anyway",
    "inactive_policy_reason": "Neurotoxic botanical — never an excipient",
    "review": {
        "status": "validated",
        "last_reviewed_at": "2026-10-20",
        "next_review_due": "2027-04-20",
        "reviewed_by": "manual_entry",
        "change_log": [{
            "date": "2026-10-20",
            "by": "claude-audit",
            "change": (
                "Created from live-verified identifiers (GSRS UNII 96MVO223I9 ILLICIUM ANISATUM WHOLE, "
                "UMLS C0949938) and content-read sources (FDA P03-67; PMIDs 22484123, 12014240, "
                "12617067). Agent source-content review, not clinician-reviewed."
            ),
        }],
    },
}


def main() -> None:
    blob = data_batch.load(PATH)
    rows = blob["ingredients"]
    assert not any(r["id"] == ENTRY["id"] for r in rows), "already applied"
    rows.append(ENTRY)
    print(data_batch.save(PATH, blob))


if __name__ == "__main__":
    main()
