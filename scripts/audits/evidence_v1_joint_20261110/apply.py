"""ADR-0007 joint batch (2026-11-10): explicit per-entry patches, applied once.

Entries: backed_clinical_studies/INGR_HYALURONIC_ACID, backed_clinical_studies/INGR_MSM.
Receipts: research.md beside this file. Run from the repo root with $PG_PYTHON.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import data_batch  # noqa: E402
from clinical_evidence_schema import validate_ingredient_context  # noqa: E402

PATH = ROOT / "scripts/data/backed_clinical_studies.json"
TODAY = "2026-11-10"
REVIEW = {
    "reviewer": "Claude agent source review with independent agent check; Sean-approved ADR-0007 V1 policy",
    "reviewed_at": TODAY,
    "scope": "identity_dose_outcome_applicability",
    "basis": ("ADR-0007 one-pass review (Sean accepted 2026-11-10). Agent review, not clinician review; "
              "clinician_approved is the existing compatibility status. Full text read on PMC11778613."),
}

HA_JOINT_CONTEXT = {
    "context_schema_version": "1.1.0",
    "context_id": "ingr_hyaluronic_acid_v1_39886281_oral_joint_review",
    "source_pmids": ["39886281"],
    "components": ["INGR_HYALURONIC_ACID"],
    "identity_scope": "ingredient_general",
    "identity": {
        "preparation": ("Oral hyaluronic acid in 11 human studies at 30-300 mg/day; 2 of 11 gave HA alone, "
                        "9 combined it with other actives (glucosamine/chondroitin, Boswellia serrata, krill oil "
                        "and astaxanthin, chondroitin and keratin peptides, collagen matrix with MSM) or procedures."),
    },
    "exposure_basis": "supplement_dose",
    "route": "oral",
    "evidence_role": "systematic_review",
    "component_registration_status": "fully_registered",
    "condition": "knee_osteoarthritis",
    "purpose": "treatment",
    "review_status": "clinician_approved",
    "clinical_review": REVIEW,
    "scoring_eligible": False,
    "human_status": "confirmed",
    "source_integrity": "none",
    "trial_family": "source_39886281",
    "population": {
        "age_group": "adult",
        "description": ("597 adults aged about 40-80 in 11 studies: knee OA (9), knee and hip OA (1), low back "
                        "pain (1); follow-up 4 weeks to 12 months (Results; Table 1)."),
    },
    "study_design": ("Systematic review without meta-analysis or formal risk-of-bias grading; PubMed, EMBASE and "
                     "SciELO searched 1966 to May 2024 per full-text Methods (the abstract names PubMed only). "
                     "Included 6 randomized double-blind placebo-controlled trials, 4 randomized controlled trials "
                     "and 1 double-blind placebo-controlled trial."),
    "outcomes": [{
        # Review-level tally, not a pooled between-group effect: several included trials report
        # improvement in both arms, so no outcome_role is asserted.
        "name": ("9 of 11 studies reported improvement in pain, WOMAC, function, Lequesne, stiffness or SF-36, "
                 "within or between groups; 2 found no between-group difference; results were not pooled"),
        "hierarchy": "not_reported",
        "kind": "patient_important",
        "direction": "mixed",
    }],
    "limitations": [
        ("ADR-0007 one-pass conclusion: limited research for oral hyaluronic acid in general. This context "
         "records the ingredient-level conclusion and earns no points."),
        ("The review's authors concluded that oral HA seems safe and effective for OA; this record does not adopt "
         "that conclusion because only 2 of 11 studies gave HA alone and 9 used multi-ingredient products or "
         "procedures, so the reported improvements are not attributable to HA."),
        ("No meta-analysis, risk-of-bias assessment or certainty grading; small samples (20-100), short "
         "follow-up in most studies, and heterogeneous doses, comparators and preparations."),
        ("PMID 42914415 (2026 review) likewise finds that incomplete molecular characterization, heterogeneous "
         "doses and formulations, short trials and multi-ingredient products prevent HA-specific attribution."),
        ("No NIH ODS, NCCIH or MedlinePlus monograph covers oral HA, and EFSA (2012, doi:10.2903/j.efsa.2012.2806) "
         "found no cause-and-effect relationship for protection of the skin against dehydration."),
        "The signed A077 exact Hyabest (S) LF-P skin context remains separate and is not transferred.",
    ],
    "dose": {
        "measurement_type": "mass",
        "unit": "mg",
        "values": [30, 50, 80, 120, 150, 200, 300],
        "dose_status": "verified",
        "dose_basis": "not_applicable",
        "duration_basis": "participant_specific",
        "duration_days": None,
        "administration_frequency": "Mostly once daily (Table 1)",
        "dosage_forms": ["capsule", "oral liquid"],
        "co_therapies": [
            ("Co-actives in 9 of 11 studies; comparators included placebo, no treatment, intra-articular HA, "
             "arthrocentesis, kinesiotherapy and a glucosamine-chondroitin product (Table 1)"),
        ],
        "source_provenance": {
            "pmid": "39886281",
            "location": "Methods (search, PRISMA screening); Results; Table 1 (design, HA dosage/day, comparator, outcome)",
            "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11778613/",
        },
        "reported_regimen": "30-300 mg/day oral HA for 4 weeks to 12 months (Table 1)",
        "normalization": {"basis": "Per-study HA mass only; co-active amounts are not normalized."},
    },
    # Source references 6-16 (PMC11778613 reference list), membership only, never credit.
    "included_study_pmids": ["37686801", "33592868", "34622845", "33213125", "27681813", "26550817",
                             "24899570", "23226979", "18208600", "33568038", "38707049"],
}

HA_REFS = [
    {"type": "pubmed", "authority": "NCBI PubMed", "pmid": "39886281", "doi": "10.31138/mjr.240724.oha",
     "title": "Oral Hyaluronic Acid in Osteoarthritis and Low Back Pain: A Systematic Review.",
     "citation": "Mediterranean journal of rheumatology (2024-12-31)",
     "url": "https://pubmed.ncbi.nlm.nih.gov/39886281/", "published_date": "2024-12-31",
     "publication_types": ["Journal Article", "Review"], "mesh_terms": [], "supplementary_concepts": [],
     "evidence_grade": "systematic_review", "retracted": False, "supports_claims": [],
     "verification_source": "pubmed_eutils", "scoring_eligible": False,
     "notes": ("ADR-0007 ingredient-level conclusion source: limited research, no points. 2 of 11 studies "
               "gave HA alone; not pooled.")},
    {"type": "pubmed", "authority": "NCBI PubMed", "pmid": "42914415", "doi": "10.1016/j.foodres.2026.120695",
     "title": ("Hyaluronic acid in functional foods and oral supplements: linking molecular weight, "
               "bioavailability, and food matrix effects to clinical translation."),
     "citation": "Food research international (2026-12-01)",
     "url": "https://pubmed.ncbi.nlm.nih.gov/42914415/", "published_date": "2026-12-01",
     "publication_types": ["Journal Article", "Review"],
     "mesh_terms": ["Hyaluronic Acid", "Humans", "Biological Availability", "Molecular Weight",
                    "Dietary Supplements", "Functional Food", "Administration, Oral", "Animals"],
     "supplementary_concepts": [], "evidence_grade": "review", "retracted": False, "supports_claims": [],
     "verification_source": "pubmed_eutils", "scoring_eligible": False,
     "notes": "Narrative review cited only for the limitation that HA-specific attribution is not established."},
]

HA_NOTES = (
    "ADR-0007 one-pass review (agent review by Claude with an independent agent check, 2026-11-10): oral "
    "hyaluronic acid has limited human research. Skin: a 2025 meta-analysis of 7 small, heterogeneous RCTs "
    "(PMID 40911749) reported improved hydration, elasticity and wrinkle depth, with no significant change in "
    "firmness, wrinkle volume or transepidermal water loss. Joint: a 2024 systematic review (PMID 39886281) "
    "found 11 small studies (597 adults, mostly knee OA, 30-300 mg/day); 9 reported improvement and its "
    "authors concluded that oral HA seems safe and effective for OA, but only 2 studies gave HA alone, "
    "nothing was pooled or graded for bias, and 2 found no difference. A 2026 review "
    "(PMID 42914415) finds that undefined molecular weight, heterogeneous doses and multi-ingredient products "
    "prevent HA-specific attribution. EFSA (2012, doi:10.2903/j.efsa.2012.2806) found no cause-and-effect "
    "relationship for protecting skin against dehydration, and no NIH ODS, NCCIH or MedlinePlus monograph "
    "covers oral HA. Conclusion: limited research and no ingredient-level points; a label that does not name "
    "the studied preparation finishes here with no points. The signed A077 exact Hyabest (S) LF-P 120 mg/day "
    "capsule skin context (PMID 34203487) stays the only credit-bearing scope, and PMID 28761365 remains a "
    "separate preparation context. This does not claim that hyaluronic acid is ineffective."
)

MSM_SPELLINGS = ["methyl sulfonyl methane", "methylsulfonyl methane", "methyl sulphonyl methane",
                 "methylsulphonylmethane", "methysulfonylmethane", "dimethyl sulfone"]


def main():
    blob = data_batch.load(PATH)
    rows = {row["id"]: row for row in blob["backed_clinical_studies"]}

    ha = rows["INGR_HYALURONIC_ACID"]
    assert not any(c["context_id"] == HA_JOINT_CONTEXT["context_id"] for c in ha["study_contexts"])
    assert not {"39886281", "42914415"} & {r.get("pmid") for r in ha["references_structured"]}
    errors = validate_ingredient_context(HA_JOINT_CONTEXT, known_component_ids={ha["id"]},
                                         require_complete_review=True)
    assert not errors, errors
    ha["study_contexts"].append(HA_JOINT_CONTEXT)
    ha["references_structured"].extend(HA_REFS)
    ha["notes"] = HA_NOTES
    ha["applicability"]["preparation_uncertainty_reviewed"] = True
    ha["applicability"]["reviewed_at"] = TODAY
    ha["applicability"]["reason"] += (
        " ADR-0007 (2026-11-10): preparation uncertainty reviewed; a label that does not name the studied "
        "preparation finishes as limited research with no points, never as Hyabest credit.")
    ha["last_updated"] = TODAY

    msm = rows["INGR_MSM"]
    terms = msm["applicability"]["required_form_terms"]
    assert not set(MSM_SPELLINGS) & {t.lower() for t in terms}
    terms.extend(MSM_SPELLINGS)
    msm["applicability"]["reason"] += (
        " Same-chemistry label spellings of methylsulfonylmethane (dimethyl sulfone, PubChem CID 6213, "
        "CAS 67-71-0), already mapped by the identity owner, satisfy the form term; DMSO stays excluded.")
    msm["applicability"]["reviewed_at"] = TODAY
    msm["last_updated"] = TODAY

    print(data_batch.save(PATH, blob))


if __name__ == "__main__":
    main()
