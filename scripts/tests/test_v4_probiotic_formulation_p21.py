"""v4 Probiotic Formulation — P2.1 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _product(
    *,
    total_billion: float = 50.0,
    strain_count: int = 5,
    clinical_strain_count: int = 5,
    prebiotic_present: bool = True,
    survivability: bool = True,
    delivery_tier: int | None = None,
    blends: list[dict] | None = None,
) -> dict:
    default_blends = blends is None
    if default_blends:
        blends = [
            {
                "name": f"Strain {i}",
                "strain_count": 1,
                "strains": [f"Strain {i}"],
                "cfu_data": {"has_cfu": False, "billion_count": 0, "cfu_count": 0},
            }
            for i in range(1, strain_count + 1)
        ]
    ingredients_scorable = [
        {"name": "Lactobacillus rhamnosus", "canonical_id": "lacto", "mapped": True, "has_dose": True}
    ]
    if prebiotic_present:
        ingredients_scorable.append(
            {
                "name": "Inulin",
                "canonical_id": "inulin",
                "mapped": True,
                "has_dose": True,
                "quantity": 3.0,
                "unit": "g",
            }
        )
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": max(1, strain_count),
            "ingredients_scorable": ingredients_scorable,
        },
        "delivery_tier": delivery_tier,
        "physicalState": {"langualCodeDescription": "Delayed-release capsules"} if survivability else {},
        "delivery_data": {
            "matched": bool(survivability or delivery_tier),
            "highest_tier": delivery_tier or (2 if survivability else None),
            "systems": [{"canonical_name": {1: "liposomal", 2: "delayed-release", 3: "microencapsulation"}.get(delivery_tier, "delayed-release"),
                         "tier": delivery_tier or 2, "match_source": "physical_state",
                         "raw_source_text": {1: "liposomal", 2: "delayed-release", 3: "microencapsulation"}.get(delivery_tier, "delayed-release")}]
                       if survivability or delivery_tier else [],
        },
        "probiotic_data": {
            "is_probiotic": True,
            "is_probiotic_product": True,
            "probiotic_blends": blends,
            "has_cfu": total_billion > 0,
            "total_cfu": total_billion * 1_000_000_000,
            "total_billion_count": total_billion,
            "total_strain_count": strain_count,
            "clinical_strain_count": clinical_strain_count,
            "clinical_strains": [
                {"strain": name, "clinical_id": clinical_id}
                for name, clinical_id in [
                    ("Lactobacillus rhamnosus GG", "STRAIN_LGG"),
                    # Saturation arithmetic needs five reviewed identities;
                    # BB-12's held citation is tested separately, not bypassed.
                    ("Lactobacillus plantarum 299v", "STRAIN_PLANTARUM_299V"),
                    ("Lactobacillus reuteri DSM 17938", "STRAIN_REUTERI_DSM17938"),
                    ("Bifidobacterium longum BB536", "STRAIN_LONGUM_BB536"),
                    ("Lactobacillus rhamnosus HN001", "STRAIN_RHAMNOSUS_HN001"),
                ][:clinical_strain_count]
            ],
            "prebiotic_present": prebiotic_present,
            "prebiotic_name": "Inulin" if prebiotic_present else "",
            "has_survivability_coating": survivability,
        },
    }
    # Physical identity requires a label owner, not a detached registry ID.
    product["activeIngredients"] = []
    for index, row in enumerate(product["probiotic_data"]["clinical_strains"]):
        ref = f"ingredientRows[{index}]"
        row["source_row_ref"] = ref
        product["activeIngredients"].append({"name": row["strain"], "raw_source_path": ref})
        if default_blends and index < len(blends):
            blends[index].update(name=row["strain"], strains=[row["strain"]], raw_source_path=ref)
    if default_blends:
        # The unresolved labels are actual source members too; absence of a
        # clinical projection must not stand in for absence from the label.
        for index in range(len(product["activeIngredients"]), len(blends)):
            ref = f"ingredientRows[{index}]"
            product["activeIngredients"].append({"name": blends[index]["strains"][0], "raw_source_path": ref})
            blends[index]["raw_source_path"] = ref
    return product


def test_clean_exact_probiotic_reaches_full_formulation_without_optional_prebiotic() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(prebiotic_present=False))

    assert payload["score"] == 15.0
    assert payload["max"] == 15.0
    assert payload["components"] == {
        "total_cfu_disclosed": 4.0,
        "exact_identity_completeness": 8.0,
        "delivery_survivability": 3.0,
    }
    assert payload["metadata"]["phase"] == "P2.1_probiotic_formulation"


@pytest.mark.parametrize(
    "total_billion", [0.0, 0.5, 1.1, 10.0, 50.0],
)
def test_only_valid_cfu_disclosure_matters_to_formulation(total_billion: float) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(total_billion=total_billion))

    assert "cfu_amount" not in payload["components"]
    assert payload["components"]["total_cfu_disclosed"] == (4.0 if total_billion > 0 else 0.0)


@pytest.mark.parametrize(
    "strain_count", [1, 2, 3, 5],
)
def test_complete_identity_credit_is_independent_of_strain_count(strain_count: int) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(
        _product(strain_count=strain_count, clinical_strain_count=strain_count)
    )
    assert "named_species_diversity" not in payload["components"]
    assert payload["components"]["exact_identity_completeness"] == 8


@pytest.mark.parametrize(
    ("clinical_strain_count", "expected"),
    [
        (0, 0.0),
        (1, 1.6),
        (2, 3.2),
        (3, 4.8),
        (5, 8.0),
    ],
)
def test_identity_credit_is_proportional_to_resolved_fraction(
    clinical_strain_count: int,
    expected: float,
) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(clinical_strain_count=clinical_strain_count))

    assert payload["components"]["exact_identity_completeness"] == expected


@pytest.mark.parametrize(
    ("survivability", "delivery_tier", "expected"),
    [
        (True, None, 3.0),  # Supported source-owned delayed-release capsule.
        (False, 1, 0.0),  # A generic unsourced tier is not survivability evidence.
        (False, 2, 0.0),
        (False, 3, 0.0),
        (False, None, 0.0),
    ],
)
def test_delivery_survivability_does_not_infer_coating_from_unsourced_tier(
    survivability: bool,
    delivery_tier: int | None,
    expected: float,
) -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    payload = score_formulation(_product(survivability=survivability, delivery_tier=delivery_tier))

    assert payload["components"]["delivery_survivability"] == expected


def test_optional_prebiotic_does_not_change_probiotic_formulation_quality() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    with_prebiotic = score_formulation(_product(prebiotic_present=True))
    without_prebiotic = score_formulation(_product(prebiotic_present=False))

    assert with_prebiotic == without_prebiotic


def test_probiotic_formulation_accepts_final_blob_probiotic_detail_alias() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    product = _product()
    product["probiotic_detail"] = product.pop("probiotic_data")

    payload = score_formulation(product)

    assert payload["score"] == 15.0
    assert payload["metadata"]["total_billion_count"] == 50.0


def test_strain_count_falls_back_to_unique_blend_strains() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    blends = [
        {"strains": ["Lactobacillus acidophilus", "Bifidobacterium lactis"]},
        {"strains": ["Lactobacillus acidophilus", "Lactobacillus rhamnosus"]},
    ]
    payload = score_formulation(_product(strain_count=0, clinical_strain_count=0, blends=blends))

    assert payload["metadata"]["total_strain_count"] == 3
    assert payload["components"]["exact_identity_completeness"] == 0.0


def test_score_probiotic_wires_formulation_and_preserves_p21_payload_at_p23() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_product()).to_breakdown()
    formulation = breakdown["dimensions"]["formulation"]

    assert formulation["score"] == 15.0
    assert formulation["max"] == 15.0
    assert formulation["metadata"]["phase"] == "P2.1_probiotic_formulation"
    assert breakdown["dimensions"]["dose"]["score"] is not None
    # Module-level phase rolls forward as each P2.x slice lands.
    assert breakdown["phase"].startswith("P2.")
    # score_100 lands at P2.6 final assembly — the formulation dimension
    # contract is independent of when final assembly runs.


def test_probiotic_formulation_resilient_to_malformed_input() -> None:
    from scoring_v4.modules.probiotic_formulation import score_formulation

    for bad in (None, {}, {"probiotic_data": None}, 42, "oops"):
        payload = score_formulation(bad)  # type: ignore[arg-type]
        assert payload["score"] == 0.0
        assert payload["max"] == 15.0



@pytest.mark.parametrize('technology,tier,expected',[
    ('methylcobalamin',2,0.0),('fermented',3,0.0),('whole food',3,0.0),
    ('enteric-coated',2,2.5),('microencapsulation',3,1.5),
])
def test_probiotic_survivability_requires_relevant_delivery(technology,tier,expected):
    from scoring_v4.modules.probiotic_formulation import score_formulation
    product=_product(survivability=False,delivery_tier=tier)
    product['activeIngredients']=[{'name':'Lactobacillus rhamnosus '+technology,'raw_source_text':'Lactobacillus rhamnosus '+technology,'category':'probiotic','quantity':10,'unit':'billion CFU','raw_source_path':'ingredientRows[0]'}]
    product['delivery_data']={'highest_tier':tier,'systems':[{'canonical_name':technology,'name':technology,'tier':tier,'raw_source_text':technology,'match_source':'ingredientRows[0]'}]}
    assert score_formulation(product)['components']['delivery_survivability']==expected


def test_probiotic_cannot_borrow_other_rows_enteric_delivery():
    from scoring_v4.modules.probiotic_formulation import score_formulation
    product=_product(survivability=False,delivery_tier=2)
    product['activeIngredients']=[
        {'name':'Lactobacillus rhamnosus','category':'probiotic','quantity':10,'unit':'billion CFU','raw_source_path':'ingredientRows[0]','raw_source_text':'Lactobacillus rhamnosus'},
        {'name':'Enteric-coated Peppermint Oil','quantity':200,'unit':'mg','raw_source_path':'ingredientRows[1]','raw_source_text':'Enteric-coated Peppermint Oil'},
    ]
    product['delivery_data']={'highest_tier':2,'systems':[{'canonical_name':'enteric-coated','tier':2,'match_source':'ingredientRows[1]','raw_source_text':'Enteric-coated'}]}
    assert score_formulation(product)['components']['delivery_survivability']==0.0

@pytest.mark.parametrize('source,expected',[
    ('Enteric-coated Lactobacillus rhamnosus',2.5),
    ('Non-enteric-coated Lactobacillus rhamnosus',0.0),
    ('Lactobacillus rhamnosus, not enteric-coated',0.0),
    ('Lactobacillus rhamnosus without enteric-coated delivery',0.0),
])
def test_probiotic_stale_delivery_marker_requires_affirmative_source(source,expected):
    from scoring_v4.modules.probiotic_formulation import score_formulation
    product=_product(survivability=False,delivery_tier=2)
    product['activeIngredients']=[{'name':source,'raw_source_text':source,'category':'probiotic','quantity':10,'unit':'billion CFU','raw_source_path':'ingredientRows[0]'}]
    product['delivery_data']={'highest_tier':2,'systems':[{'canonical_name':'enteric-coated','tier':2,'match_source':'ingredientRows[0]','raw_source_text':'enteric-coated'}]}
    assert score_formulation(product)['components']['delivery_survivability']==expected


def test_probiotic_delivery_retains_owned_source_note_assertion():
    from scoring_v4.modules.probiotic_formulation import score_formulation
    product = _product(survivability=False, delivery_tier=3)
    note = 'ME refers to microencapsulation process that protects the probiotics'
    product['activeIngredients'] = [{
        'name': 'Lactobacillus helveticus Rosell-52',
        'raw_source_text': 'Lactobacillus helveticus Rosell-52',
        'raw_source_path': 'ingredientRows[0].nestedRows[0]',
        'category': 'probiotic', 'quantity': 3, 'unit': 'billion CFU',
        'notes': note,
    }]
    product['delivery_data'] = {'highest_tier': 3, 'systems': [{
        'canonical_name': 'microencapsulation', 'tier': 3,
        'raw_source_text': note, 'match_source': 'ingredientRows[0].nestedRows[0]',
    }]}
    assert score_formulation(product)['components']['delivery_survivability'] == 1.5
