"""ADR-0007 close-out batch (2026-11-10): explicit per-entry patches, applied once.

literature_evidence_records: turmeric, ginkgo, collagen -> documented_review_scope attests
    preparation_uncertainty_reviewed (unnamed preparation finishes at the record's no-credit
    conclusion); applicability_decision clause updated to match.
backed_clinical_studies:
    age_group on the six scoring-eligible contexts that lacked it;
    PRECLIN_CURCUMIN_GENERIC and INGR_TURMERIC text reconciled with signed A130 / A115.
Receipts: research.md beside this file. Run from the repo root with $PG_PYTHON.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import data_batch  # noqa: E402

LIT = ROOT / "scripts/data/literature_evidence_records.json"
BACKED = ROOT / "scripts/data/backed_clinical_studies.json"
TODAY = "2026-11-10"

# (old clause, new clause) per literature record; each old clause must appear exactly once.
LIT_CLAUSES = {
    "turmeric": ("and a row stating no preparation stays open.",
                 "and a row naming no preparation finishes at the same no-credit conclusion "
                 "(ADR-0007; NCCIH: not enough evidence to conclude benefit)."),
    "ginkgo": ("and an extract or plant name alone stays open.",
               "and an extract or plant name alone finishes at the same no-credit conclusion (ADR-0007)."),
    "collagen": ("finishes as outside these studies, and collagen or gelatin alone stays open.",
                 "finishes as outside this review's studies, and collagen or gelatin alone finishes at "
                 "the same no-credit conclusion (ADR-0007)."),
}

# context_id -> age_group, each verified against the source (research.md).
AGE_GROUPS = {
    ("INGR_HYALURONIC_ACID", "ingr_hyaluronic_acid_34203487"): "adult",
    ("INGR_NAC", "nac_oral_exercise_soreness_subset_39632267"): "adult",
    ("INGR_PASSIONFLOWER", "passionflower_short_term_anxiety_review_33352740"): "adult",
    ("INGR_HONEY", "honey_child_nocturnal_cough_22869830"): "child",
    ("INGR_CREATINE_MONOHYDRATE", "creatine_monohydrate_resistance_training_body_composition_39074168"): "adult",
    ("INGR_ALPHA_GPC", "alpha_gpc_alzheimer_monotherapy_subset_36683513"): "adult",
}

CURCUMIN_NOTES = (
    "Signed A130 (Dr. Pham, 2026-10-28) rejects broad superiority and generic benefit language for curcumin, "
    "so the multi-outcome syntheses (PMIDs 39478418, 38945354, 38576215) carry no credit for a generic "
    "healthy-aging claim. The retained context is a meta-analysis of 21 RCTs in 1,705 knee-osteoarthritis "
    "patients (PMID 40615851) reporting lower CRP and TNF-alpha, with no significant effect on ESR, IL-1 beta, "
    "IL-6 or PGE2. Effects depend on preparation and outcome. Agent reconciliation of this text with A130, "
    "2026-11-10; not clinician review."
)
CURCUMIN_RATIONALE = (
    "Reference-only under signed A130 (Dr. Pham, 2026-10-28). Descriptive direction mixed: the retained "
    "knee-osteoarthritis biomarker meta-analysis (PMID 40615851) reports lower CRP and TNF-alpha but no "
    "significant effect on ESR, IL-1 beta, IL-6 or PGE2. The earlier positive_strong, healthy-aging and "
    "stress/mood tags and unverified registry/enrollment aggregates were removed because A130 rejected them."
)
TURMERIC_RATIONALE = (
    "Reference-only under signed A115 (Dr. Pham), which rejects broad preparation-wide approval. Descriptive "
    "direction mixed: the retained knee-osteoarthritis biomarker meta-analysis (PMID 40615851) reports lower "
    "CRP and TNF-alpha but no significant effect on ESR, IL-1 beta, IL-6 or PGE2. The earlier positive_strong "
    "and unverified registry/enrollment aggregates were removed; preparation applicability remains unestablished."
)


def patch_literature():
    blob = data_batch.load(LIT)
    rows = {row["canonical_id"]: row for row in blob["literature_evidence_records"]}
    for cid, (old, new) in LIT_CLAUSES.items():
        row = rows[cid]
        scope = row["documented_review_scope"]
        assert "preparation_uncertainty_reviewed" not in scope
        assert row["applicability_decision"].count(old) == 1, cid
        assert "earns no Evidence credit" in row["applicability_decision"], cid
        scope["preparation_uncertainty_reviewed"] = True
        scope["reviewed_at"] = TODAY
        row["applicability_decision"] = row["applicability_decision"].replace(old, new)
    assert "preparation_uncertainty_reviewed" not in rows["broccoli"]["documented_review_scope"]
    print(data_batch.save(LIT, blob))


def patch_backed():
    blob = data_batch.load(BACKED)
    rows = {row["id"]: row for row in blob["backed_clinical_studies"]}
    for (rid, ctx_id), age in AGE_GROUPS.items():
        [ctx] = [c for c in rows[rid]["study_contexts"] if c.get("context_id") == ctx_id]
        assert ctx.get("scoring_eligible") is True and not ctx["population"].get("age_group"), ctx_id
        ctx["population"]["age_group"] = age
        rows[rid]["last_updated"] = TODAY

    cur = rows["PRECLIN_CURCUMIN_GENERIC"]
    assert cur["effect_direction"] == "positive_strong" and cur["study_type"] == "reference"
    cur.update({
        "notes": CURCUMIN_NOTES,
        "effect_direction": "mixed",
        "effect_direction_confidence": "medium",
        "effect_direction_rationale": CURCUMIN_RATIONALE,
        "key_endpoints": [],
        "health_goals_supported": [],
        "endpoint_relevance_tags": [],
        "total_enrollment": None,
        "registry_completed_trials_count": None,
        "last_updated": TODAY,
    })
    # No primary_outcome: A130 leaves no benefit category (the vocab contract allows an absent key).
    cur.pop("primary_outcome")

    tur = rows["INGR_TURMERIC"]
    assert tur["effect_direction"] == "positive_strong" and tur["study_type"] == "reference"
    tur.update({
        "effect_direction": "mixed",
        "effect_direction_confidence": "medium",
        "effect_direction_rationale": TURMERIC_RATIONALE,
        "total_enrollment": None,
        "registry_completed_trials_count": None,
        "last_updated": TODAY,
    })
    print(data_batch.save(BACKED, blob))


CURCUMIN_NOTABLE = (
    "Under signed A130 these syntheses are noncredit context, not support for a generic curcumin "
    "benefit: PMID 39478418 (103-trial multi-outcome meta-analysis), PMID 38945354 (inflammatory, "
    "oxidative-stress and endothelial biomarker review) and PMID 38576215 (osteoarthritis umbrella "
    "review). PMID 40615851 (21 RCTs in knee osteoarthritis) reports lower CRP and TNF-alpha, with no "
    "significant effect on ESR, IL-1 beta, IL-6 or PGE2."
)


def patch_review_followup():
    """PR 439 review: curcumin notable_studies still carried A130-rejected benefit language, and the
    reference-only rice-protein record still listed a goal its rejected contexts do not support."""
    blob = data_batch.load(BACKED)
    rows = {row["id"]: row for row in blob["backed_clinical_studies"]}
    cur = rows["PRECLIN_CURCUMIN_GENERIC"]
    assert "high-credibility" in cur["notable_studies"]
    cur["notable_studies"] = CURCUMIN_NOTABLE
    rice = rows["INGR_RICE_PROTEIN"]
    assert rice["study_type"] == "reference" and not any(
        c.get("scoring_eligible") for c in rice["study_contexts"])
    rice["health_goals_supported"] = []
    rice["last_updated"] = TODAY
    print(data_batch.save(BACKED, blob))


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["review-followup"]:
        patch_review_followup()
    else:
        patch_literature()
        patch_backed()
