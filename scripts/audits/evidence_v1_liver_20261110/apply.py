"""ADR-0007 liver/antioxidant batch (2026-11-10): explicit per-entry patches, applied once.

Entries: backed_clinical_studies/INGR_MILK_THISTLE, backed_clinical_studies/INGR_NAC.
No change: INGR_ALPHA_LIPOIC_ACID (signed A036), PRECLIN_RESVERATROL (reconciled 2026-10-23/28).
Receipts: research.md beside this file. Run from the repo root with $PG_PYTHON.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import data_batch  # noqa: E402

PATH = ROOT / "scripts/data/backed_clinical_studies.json"
TODAY = "2026-11-10"

MILK_THISTLE_NOTES = (
    "The reviewed research does not establish a qualifying benefit. Dr. Pham's signed A092 (2026-10-28) "
    "rejects the earlier 'liver protection and enzyme normalization' claim and keeps only a narrower NAFLD/NASH "
    "research reading, with no Evidence credit: a 2024 meta-analysis (PMID 38579127; 26 RCTs, 2,375 patients) "
    "reports favorable lipid, liver-enzyme and steatosis changes, but gives no silymarin dose and mostly tests "
    "silymarin added to other active therapy. A Cochrane review of alcoholic and hepatitis B/C liver disease "
    "(PMID 17943794; 18 RCTs, 1,088 patients, mostly low quality) found no significant effect on mortality, "
    "complications or liver histology. NCCIH (fact sheet updated February 2025) describes liver-disease trial results as "
    "conflicting or too limited for conclusions, and its two funded trials (hepatitis C, NASH) showed no "
    "benefit. Agent reconciliation of this text with A092, 2026-11-10; not clinician review."
)
MILK_THISTLE_NOTABLE = (
    "Li et al. (2024, PMID 38579127) pooled 26 NAFLD/NASH RCTs (2,375 patients, 8-48 weeks): silymarin "
    "added to lifestyle or drug therapy was associated with lower ALT, AST, total and LDL cholesterol and "
    "triglycerides, higher HDL cholesterol and better steatosis grade, with very high heterogeneity and no reported silymarin dose. Rambaldi et al. (2007 Cochrane, "
    "PMID 17943794) found no significant effect on mortality, complications or histology in alcoholic or "
    "viral liver disease and questioned the benefit."
)
MILK_THISTLE_RATIONALE = (
    "Reference-only under signed A092 (Dr. Pham, 2026-10-28). Descriptive direction mixed: NAFLD/NASH "
    "surrogate improvements without a reported dose, mostly as add-on therapy (PMID 38579127), and a null "
    "Cochrane review on hard outcomes in alcoholic/viral liver disease (PMID 17943794). Earlier "
    "positive_strong, 'liver protection' and healthy-aging tags were removed because A092 rejected them."
)

NCCIH_REF = {
    "type": "nccih", "authority": "NIH National Center for Complementary and Integrative Health",
    "title": "Milk Thistle", "citation": "NCCIH fact sheet (last updated February 2025)",
    "url": "https://www.nccih.nih.gov/health/milk-thistle", "published_date": "2025-02",
    "publication_types": [], "mesh_terms": [], "supplementary_concepts": [],
    "evidence_grade": "reference", "retracted": False, "supports_claims": [],
    "verification_source": "nccih", "scoring_eligible": False,
    "notes": ("Liver-disease trial results conflicting or too limited for conclusions; two NCCIH-funded "
              "trials (hepatitis C, NASH) showed no benefit. Read 2026-11-10."),
}

NAC_OLD = ("Human evidence supports NAC as a glutathione precursor that measurably lowers oxidative-stress markers, "
           "and a randomized trial supports attenuation of influenza-like illness in older adults.")
NAC_NEW = ("NAC is a glutathione precursor. A 2024 meta-analysis (PMID 39632267) reports lower TBARS and higher "
           "glutathione after exercise; a single 1997 randomized trial (PMID 9230243; 262 adults, 78% aged 65 or "
           "older, 600 mg twice daily for 6 months) reported fewer and milder influenza-like episodes without "
           "preventing infection.")


def main():
    blob = data_batch.load(PATH)
    rows = {row["id"]: row for row in blob["backed_clinical_studies"]}

    mt = rows["INGR_MILK_THISTLE"]
    assert mt["notes"] == "Clinical studies support liver protection and enzyme normalization."
    assert mt["study_type"] == "reference" and mt["effect_direction"] == "positive_strong"
    assert {c["review_status"] for c in mt["study_contexts"]} == {"rejected_source"}
    mt.update({
        "notes": MILK_THISTLE_NOTES,
        "notable_studies": MILK_THISTLE_NOTABLE,
        "effect_direction": "mixed",
        "effect_direction_confidence": "medium",
        "effect_direction_rationale": MILK_THISTLE_RATIONALE,
        "key_endpoints": [],
        "health_goals_supported": [],
        "primary_outcome": "",
        "endpoint_relevance_tags": [],
        "published_studies": ["38579127", "17943794"],
        "total_enrollment": None,
        "registry_completed_trials_count": None,
        "last_updated": TODAY,
    })
    assert not any(r.get("type") == "nccih" for r in mt["references_structured"])
    mt["references_structured"].append(NCCIH_REF)

    nac = rows["INGR_NAC"]
    assert nac["notes"].startswith(NAC_OLD)
    nac["notes"] = NAC_NEW + nac["notes"][len(NAC_OLD):]
    nac["last_updated"] = TODAY

    print(data_batch.save(PATH, blob))


if __name__ == "__main__":
    main()
