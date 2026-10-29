"""Clinical-evidence and identity contracts for L-carnitine."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.modules.generic_evidence import score_evidence


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def clinical_entries() -> dict[str, dict]:
    payload = json.loads(
        (DATA_DIR / "backed_clinical_studies.json").read_text()
    )
    return {
        entry["id"]: entry
        for entry in payload["backed_clinical_studies"]
    }


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.fixture
def eligible_carnitine_sources(monkeypatch, enricher, clinical_entries):
    """Explicit synthetic source approval for recovery/dedup mechanics only."""
    import clinical_applicability
    import evidence_resolver
    from scoring_v4.modules import generic_evidence
    from test_evidence_resolver import _approved_test_source
    sources = {}
    for source_id in ("INGR_L_CARNITINE", "BRAND_CARNIPURE"):
        original = deepcopy(clinical_entries[source_id])
        source = _approved_test_source(original, name=original["standard_name"],
            pmid=original["references_structured"][0]["pmid"], outcome="Muscle soreness after exercise")
        context = source["study_contexts"][0]
        context["condition"] = "muscle_recovery"
        if source["study_type"] == "systematic_review_meta":
            native_review = next(review for review in original["study_contexts"]
                                 if review.get("evidence_role") in {"systematic_review", "meta_analysis"})
            context["evidence_role"] = native_review["evidence_role"]
            context["included_study_pmids"] = deepcopy(native_review["included_study_pmids"])
            context["study_design"] = "Synthetic synthesis mechanics fixture; no clinical claim"
        if source["effect_direction"] == "mixed":
            context["outcomes"].append({**context["outcomes"][0], "name": "Muscle recovery null endpoint", "direction": "null"})
        sources[source_id] = source
    current = clinical_applicability.reviewed_entries()
    monkeypatch.setattr(clinical_applicability, "reviewed_entries", lambda: {**current, **sources})
    for source_id in sources:
        review = clinical_applicability.assess_clinical_source_review({"id": source_id})
        assert review["is_complete"], review["errors"]
    verified = generic_evidence._verified_ingredient_human_evidence_entries()
    monkeypatch.setattr(generic_evidence, "_verified_ingredient_human_evidence_entries",
        lambda: tuple(row for row in verified if row["id"] not in sources) + tuple(
            row for row in sources.values() if generic_evidence._is_verified_ingredient_human_entry(row)))
    index = evidence_resolver._backed_studies_index()
    monkeypatch.setattr(evidence_resolver, "_backed_studies_index", lambda: {
        key: [sources.get(row["id"], row) for row in rows] for key, rows in index.items()})
    payload = enricher.databases["backed_clinical_studies"]
    monkeypatch.setitem(enricher.databases, "backed_clinical_studies", {**payload,
        "backed_clinical_studies": [sources.get(row["id"], row) for row in payload["backed_clinical_studies"]]})
    return sources



def test_synthetic_carnitine_fixture_has_complete_source_review(eligible_carnitine_sources):
    from clinical_applicability import assess_clinical_source_review
    for source_id, source in eligible_carnitine_sources.items():
        review = assess_clinical_source_review({"id": source_id})
        assert review["is_complete"] is True
        assert review["errors"] == []
        assert review["context_ids"] == [context["context_id"] for context in source["study_contexts"]]

def test_generic_l_carnitine_record_is_mixed_and_dose_scoped(
    clinical_entries: dict[str, dict],
) -> None:
    entry = clinical_entries["INGR_L_CARNITINE"]

    assert entry["evidence_level"] == "ingredient-human"
    assert entry["study_type"] == "systematic_review_meta"
    assert entry["effect_direction"] == "mixed"
    assert entry["min_clinical_dose"] == 1000
    assert entry["max_studied_clinical_dose"] == 4000
    assert entry["dose_unit"] == "mg"
    assert entry["exclude_alias_match_mode"] == "bounded_phrase"
    assert entry["evidence_group_id"] == "l_carnitine"
    assert entry["health_goals_supported"] == [
        "Muscle Growth & Recovery",
        "Weight Management",
    ]
    assert {
        ref["pmid"] for ref in entry["references_structured"]
    } == {"32958033", "32154768", "32359762"}
    assert all(
        ref["verification_source"] == "pubmed_eutils"
        for ref in entry["references_structured"]
    )
    assert all(
        ref["retracted"] is False
        for ref in entry["references_structured"]
    )


@pytest.mark.parametrize(
    "label_term",
    [
        "L-Carnitine",
        "Levocarnitine",
        "L-Carnitine Base",
        "L-Carnitine L-Tartrate",
        "L-Carnitine Tartrate",
        "Levocarnitine Tartrate",
        "LCLT",
    ],
)
def test_generic_l_carnitine_matches_reviewed_base_and_tartrate(
    enricher: SupplementEnricherV3,
    clinical_entries: dict[str, dict],
    label_term: str,
) -> None:
    entry = clinical_entries["INGR_L_CARNITINE"]
    assert enricher._clinical_study_match([label_term], entry) is not None


@pytest.mark.parametrize(
    "label_term",
    [
        "L-Carnitine Fumarate",
        "L-Carnitine HCl",
        "L-Carnitine Hydrochloride",
        "N-Acetyl L-Carnitine HCl",
        "Acetyl-L-Carnitine",
        "ArginoCarn Acetyl-L-Carnitine Arginate Dihydrochloride",
        "Acetyl-L-Carnitine HCl",
        "Propionyl-L-Carnitine",
        "GlycoCarn Glycine Propionyl L-Carnitine HCl",
        "Glycine Propionyl L-Carnitine Hydrochloride",
        "D-Carnitine",
        "DL-Carnitine",
    ],
)
def test_other_carnitines_do_not_borrow_generic_l_carnitine_evidence(
    enricher: SupplementEnricherV3,
    clinical_entries: dict[str, dict],
    label_term: str,
) -> None:
    entry = clinical_entries["INGR_L_CARNITINE"]
    assert enricher._clinical_study_match(
        [label_term, "L-Carnitine"],
        entry,
    ) is None


def test_carnipure_record_matches_its_two_small_recovery_trials(
    clinical_entries: dict[str, dict],
) -> None:
    entry = clinical_entries["BRAND_CARNIPURE"]

    assert entry["effect_direction"] == "positive_weak"
    assert entry["total_enrollment"] == 28
    assert "registry_completed_trials_count" not in entry
    assert entry["primary_outcome"] == "Muscle Growth & Recovery"
    assert entry["category"] == "sports_performance"
    assert entry["health_goals_supported"] == [
        "Muscle Growth & Recovery"
    ]
    assert entry["min_clinical_dose"] == 2000
    assert entry["max_studied_clinical_dose"] == 2000
    assert entry["external_ids"]["unii"] == "4D8F2Q45LQ"
    assert entry["evidence_group_id"] == "l_carnitine"

    combined = " ".join(
        str(entry.get(field) or "")
        for field in (
            "key_endpoints",
            "notes",
            "notable_studies",
            "effect_direction_rationale",
        )
    ).lower()
    assert "recovery" in combined
    assert "biomarker" in combined
    assert "heart health" not in combined
    assert "performance gains" not in combined


def test_from_prefixed_l_carnitine_tartrate_is_an_actual_form(
    enricher: SupplementEnricherV3,
) -> None:
    quality_map = enricher.databases["ingredient_quality_map"]
    result = enricher._match_quality_map(
        "L-Carnitine",
        "L-Carnitine",
        quality_map,
        cleaned_forms=[
            {
                "name": "L-Carnitine Tartrate",
                "prefix": "from",
                "percent": None,
                "ingredientGroup": "L-Carnitine",
            }
        ],
        cleaner_canonical_id="l_carnitine",
    )

    assert result is not None
    assert result["canonical_id"] == "l_carnitine"
    assert result["form_id"] == "l-carnitine tartrate (lclt)"
    assert result["bio_score"] == 10


def _single_l_carnitine_product(
    *,
    name: str,
    matched_form: str | None,
    product_name: str = "L-Carnitine",
) -> dict:
    ingredient = {
        "name": name,
        "raw_source_text": name,
        "standard_name": "L-Carnitine",
        "canonical_id": "l_carnitine",
        "mapped": True,
        "quantity": 2000,
        "unit": "mg",
        "raw_source_path": "ingredientRows[0]",
    }
    if matched_form is not None:
        ingredient["matched_form"] = matched_form
    return {
        "status": "active",
        "product_name": product_name,
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {
            "ingredients_scorable": [ingredient],
            "ingredients": [ingredient],
        },
        "evidence_data": {"clinical_matches": []},
    }


@pytest.mark.parametrize(
    ("name", "matched_form"),
    [
        ("L-Carnitine", None),
        ("L-Carnitine Tartrate", "L-Carnitine Tartrate"),
    ],
)
def test_scoring_recovery_accepts_reviewed_l_carnitine_forms(
    name: str,
    matched_form: str | None,
    eligible_carnitine_sources,
) -> None:
    payload = score_evidence(
        _single_l_carnitine_product(
            name=name,
            matched_form=matched_form,
        ),
        apply_primary_floor=True,
    )

    assert payload["metadata"]["recovered_matches"] == [
        "INGR_L_CARNITINE"
    ]
    assert payload["score"] > 0.0


def test_scoring_recovery_rejects_excluded_l_carnitine_form() -> None:
    payload = score_evidence(
        _single_l_carnitine_product(
            name="L-Carnitine Fumarate",
            matched_form="L-Carnitine Fumarate",
        ),
        apply_primary_floor=True,
    )

    assert payload["metadata"]["recovered_matches"] == []
    assert payload["score"] == 0.0


@pytest.mark.parametrize(
    "excluded_form",
    [
        "L-Carnitine Fumarate",
        "L-Carnitine HCl",
        "Acetyl-L-Carnitine Arginate",
    ],
)
def test_scoring_recovery_uses_product_identity_when_row_lost_form(
    excluded_form: str,
) -> None:
    payload = score_evidence(
        _single_l_carnitine_product(
            name="L-Carnitine",
            matched_form="L-Carnitine Base",
            product_name=f"{excluded_form} 1000 mg",
        ),
        apply_primary_floor=True,
    )

    assert payload["metadata"]["recovered_matches"] == []
    assert payload["score"] == 0.0


def test_enrichment_deduplicates_same_study_across_active_rows(
    enricher: SupplementEnricherV3,
    eligible_carnitine_sources,
) -> None:
    product = {
        "fullName": "L-Carnitine Blend",
        "activeIngredients": [
            {
                "name": "L-Carnitine",
                "standardName": "L-Carnitine",
                "quantity": 1000,
                "unit": "mg",
                "mapped": True,
            },
            {
                "name": "L-Carnitine Tartrate",
                "standardName": "L-Carnitine",
                "quantity": 1000,
                "unit": "mg",
                "mapped": True,
            },
        ],
    }

    evidence = enricher._collect_evidence_data(product)
    matches = [
        match
        for match in evidence["clinical_matches"]
        if match["id"] == "INGR_L_CARNITINE"
    ]

    assert len(matches) == 1


def test_enrichment_rejects_broad_parent_for_excluded_carnitine_rows(
    enricher: SupplementEnricherV3,
) -> None:
    product = {
        "fullName": "Carnitine Complex",
        "activeIngredients": [
            {
                "name": "L-Carnitine Fumarate",
                "standardName": "L-Carnitine",
                "quantity": 500,
                "unit": "mg",
                "mapped": True,
            },
            {
                "name": "GlycoCarn Glycine Propionyl L-Carnitine HCl",
                "raw_source_text": (
                    "GlycoCarn Glycine Propionyl L-Carnitine HCl"
                ),
                "standardName": "L-Carnitine",
                "branded_token_extracted": "GlycoCarn",
                "quantity": 250,
                "unit": "mg",
                "mapped": True,
            },
        ],
    }

    evidence = enricher._collect_evidence_data(product)

    assert all(
        match["id"] != "INGR_L_CARNITINE"
        for match in evidence["clinical_matches"]
    )


def test_brand_and_generic_carnitine_evidence_share_one_ingredient_group(
    clinical_entries: dict[str, dict],
    eligible_carnitine_sources,
) -> None:
    product = _single_l_carnitine_product(
        name="Carnipure",
        matched_form="L-Carnitine L-Tartrate",
        product_name="Carnipure L-Carnitine 2000 mg",
    )
    product["evidence_data"]["clinical_matches"] = [
        {**eligible_carnitine_sources[source_id], "ingredient": "Carnipure",
         "matched_source_row_refs": ["ingredientRows[0]"], "matched_canonical_ids": ["l_carnitine"]}
        for source_id in ("BRAND_CARNIPURE", "INGR_L_CARNITINE")
    ]

    payload = score_evidence(product, apply_primary_floor=True)

    assert list(payload["metadata"]["ingredient_points"]) == [
        "l carnitine"
    ]
    assert payload["metadata"]["top_n_applied"] == 1


def test_actual_carnitine_records_cannot_earn_preparation_only_credit():
    from clinical_applicability import assess_clinical_source_review, reviewed_entries
    for source_id in ("INGR_L_CARNITINE", "BRAND_CARNIPURE"):
        assert assess_clinical_source_review(reviewed_entries()[source_id])["is_complete"] is False
    product = _single_l_carnitine_product(name="L-Carnitine", matched_form="L-Carnitine Base")
    result = score_evidence(product, apply_primary_floor=True)
    assert result["score"] == 0
    assert result["metadata"]["recovered_matches"] == []
