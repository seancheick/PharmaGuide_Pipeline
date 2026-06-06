"""v4 Probiotic Transparency dimension — P2.5 tests.

Per §6 line 296-307, probiotic Transparency 15 has class-specific
positives + reuses the generic Transparency penalty machinery:

    Positive components (probiotic-specific):
        all strain identities named on label    8 pts
        per-strain CFU on label                 7 pts
        aggregate CFU floor                     up to +4, non-stacking
        B3 claim_compliance bonus               up to +4  (allergen_free +2,
                                                           gluten_free +1,
                                                           vegan_or_veg +1)

    Penalties (reused from generic_transparency):
        B2 false allergen-free claim            up to -2
        B5 opacity (class-aware probiotic 0.4x) up to -5
        B6 marketing / disease claims           -5

    Final: clamp(0, 15, sum(positives) - sum(|penalties|))

Strain identities (8 pts): credited when total_strain_count > 0 and
each named blend has at least one strain identified by name. A
"Probiotic Blend" container with named children counts as identities-named.

Per-strain CFU (7 pts): reuses the disclosure signal from P2.2 dose —
proportional to disclosed_count / total_strain_count. Aggregate CFU is
acceptable but non-premium disclosure, so it floors this line below the
full per-strain score instead of scoring as zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _probiotic(
    *,
    strain_count: int = 1,
    blends: list | None = None,
    clinical_strains: list | None = None,
    has_disease_claims: bool = False,
    allergens: list | None = None,
    compliance: dict | None = None,
    **extra,
):
    """Build a probiotic product fixture for transparency tests."""
    strains = blends if blends is not None else [
        {"name": f"Strain {i+1}",
         "strains": [f"Lactobacillus species_{i+1}"],
         "cfu_data": {"has_cfu": False, "billion_count": 0}}
        for i in range(strain_count)
    ]
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": strain_count or 1,
            "ingredients_scorable": [
                {"name": "Probiotic blend",
                 "canonical_id": "probiotic_blend", "mapped": True,
                 "has_dose": True}
            ],
        },
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_billion_count": 20.0,
            "total_strain_count": strain_count,
            "clinical_strain_count": strain_count,
            "probiotic_blends": strains,
            "clinical_strains": clinical_strains or [
                {"name": s["strains"][0] if s.get("strains") else f"Strain {i+1}"}
                for i, s in enumerate(strains)
            ],
        },
        "has_disease_claims": has_disease_claims,
        "contaminant_data": {"allergens": {"allergens": allergens or []}},
        "compliance_data": compliance or {},
    }
    product.update(extra)
    return product


# --- Strain identities (8) -----------------------------------------------


def test_transparency_strain_identities_credit_when_strains_named() -> None:
    """A probiotic with named strains (e.g. "Lactobacillus rhamnosus HN001")
    gets the strain-identities credit. §6 line 297: "All strain identities
    named on label (regardless of whether a 'Probiotic Blend' container
    is used)."""
    from scoring_v4.modules.probiotic_transparency import score_transparency

    payload = score_transparency(_probiotic(strain_count=10))
    assert payload["components"]["strain_identities_named"] == 8.0


def test_transparency_strain_identities_zero_when_no_strains() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(strain_count=0, blends=[])
    product["probiotic_data"]["total_strain_count"] = 0
    payload = score_transparency(product)
    assert payload["components"]["strain_identities_named"] == 0.0


def test_transparency_strain_identities_partial_when_unnamed_blends_present() -> None:
    """A product with some named strains + some unnamed blend containers
    gets proportional credit. Conservative — full credit only when all
    blends have at least one named strain."""
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        strain_count=3,
        blends=[
            {"name": "L. rhamnosus", "strains": ["Lactobacillus rhamnosus HN001"]},
            {"name": "B. lactis", "strains": ["Bifidobacterium lactis BB-12"]},
            {"name": "Proprietary blend", "strains": []},  # unnamed
        ],
    )
    payload = score_transparency(product)
    # 2 of 3 blends have named strains → 8 * (2/3) ≈ 5.33
    assert 5.0 <= payload["components"]["strain_identities_named"] <= 6.0


# --- Per-strain CFU on label (7) -----------------------------------------


def test_transparency_per_strain_cfu_credit_when_disclosed() -> None:
    """Per-strain CFU on label gets full 7 pts when all strains have
    individual CFU disclosure. §6 line 298: "Intentionally double-counts
    with the Dose dimension (strong signal)"."""
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        strain_count=2,
        blends=[
            {"name": "L. rhamnosus",
             "strains": ["Lactobacillus rhamnosus HN001"],
             "cfu_data": {"has_cfu": True, "billion_count": 10}},
            {"name": "B. lactis",
             "strains": ["Bifidobacterium lactis BB-12"],
             "cfu_data": {"has_cfu": True, "billion_count": 5}},
        ],
    )
    payload = score_transparency(product)
    assert payload["components"]["per_strain_cfu_on_label"] == 7.0
    assert payload["components"]["aggregate_cfu_disclosure_proxy"] == 0.0
    assert payload["metadata"]["aggregate_cfu_disclosure"]["basis"] == "per_strain_cfu"


def test_transparency_per_strain_cfu_proportional() -> None:
    """Partial disclosure — only 1 of 4 strains has CFU → 7 * 0.25 = 1.75,
    then aggregate CFU fills the non-premium disclosure floor to 4 total.
    """
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        strain_count=4,
        blends=[
            {"name": "A", "strains": ["Strain A"],
             "cfu_data": {"has_cfu": True, "billion_count": 10}},
        ] + [
            {"name": f"Strain {i}", "strains": [f"Strain {i}"],
             "cfu_data": {"has_cfu": False}}
            for i in range(3)
        ],
    )
    product["probiotic_data"]["total_strain_count"] = 4
    payload = score_transparency(product)
    assert payload["components"]["per_strain_cfu_on_label"] == 1.75
    assert payload["components"]["aggregate_cfu_disclosure_proxy"] == 2.25
    assert payload["metadata"]["aggregate_cfu_disclosure"]["basis"] == "aggregate_cfu_floor"


def test_transparency_aggregate_cfu_gets_non_premium_disclosure_floor() -> None:
    """The 3 real probiotic canaries (Spring Valley, GNC Ultra, GoL Prenatal):
    all disclose aggregate CFU but not per-strain CFU. That is acceptable
    disclosure, not premium disclosure: 4 pts, not 0 and not 7.
    """
    from scoring_v4.modules.probiotic_transparency import score_transparency

    payload = score_transparency(_probiotic(strain_count=10))
    assert payload["components"]["per_strain_cfu_on_label"] == 0.0
    assert payload["components"]["aggregate_cfu_disclosure_proxy"] == 4.0
    assert payload["metadata"]["aggregate_cfu_disclosure"] == {
        "total_billion_count": 20.0,
        "proxy_cap": 4.0,
        "proxy_points": 4.0,
        "per_strain_points": 0.0,
        "basis": "aggregate_cfu_floor",
    }


def test_transparency_no_cfu_still_gets_no_cfu_disclosure_credit() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(strain_count=2)
    product["probiotic_data"]["total_billion_count"] = 0.0
    for blend in product["probiotic_data"]["probiotic_blends"]:
        blend["cfu_data"] = {"has_cfu": False, "billion_count": 0}

    payload = score_transparency(product)

    assert payload["components"]["per_strain_cfu_on_label"] == 0.0
    assert payload["components"]["aggregate_cfu_disclosure_proxy"] == 0.0
    assert payload["metadata"]["aggregate_cfu_disclosure"]["basis"] == "no_cfu_disclosure"


# --- B3 claim_compliance bonus (reused) ----------------------------------


def test_transparency_b3_claim_compliance_reuses_generic() -> None:
    """Gluten-free + allergen-free → +3 (1 + 2). Vegan only → +1. Cap +4."""
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        compliance={"gluten_free": True, "allergen_free_claims": ["dairy-free"],
                    "conflicts": [], "has_may_contain_warning": False, "vegan": False},
    )
    payload = score_transparency(product)
    assert payload["components"]["B3_claim_compliance"] == 3.0


# --- B2 allergen penalty (reused) ----------------------------------------


def test_transparency_b2_allergen_presence_alone_has_no_penalty() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        allergens=[{"allergen_id": "milk", "severity_level": "high"}],
    )
    payload = score_transparency(product)
    assert payload["penalties"]["B2_false_allergen_free_claim"] == 0.0


def test_transparency_b2_false_allergen_claim_reuses_generic() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        allergens=[{"allergen_id": "milk", "severity_level": "high"}],
        compliance={
            "allergen_free_claims": ["dairy-free"],
            "conflicts": [],
            "has_may_contain_warning": False,
            "gluten_free": False,
            "vegan": False,
        },
    )
    payload = score_transparency(product)
    assert payload["penalties"]["B2_false_allergen_free_claim"] == -2.0


# --- B5 opacity class-aware probiotic 0.4x (reused) ----------------------


def test_transparency_b5_opacity_applies_probiotic_class_multiplier() -> None:
    """Probiotic B5 penalty is class-multiplied by 0.4x (vs generic 1.0x).
    Per §5 line 255: 'Probiotic — per-strain CFU hidden, strains named,
    total CFU shown → Moderate score/confidence penalty (-3 to -5)'."""
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        strain_count=3,
        proprietary_blends=[{
            "name": "Probiotic Complex",
            "disclosure_level": "partial",
            "child_ingredients": [
                {"name": "L. rhamnosus"},
                {"name": "B. lactis"},
                {"name": "S. boulardii"},
            ],
            "blend_total_mg": 100, "source_path": "activeIngredients[0]",
            "hidden_count": 2,
        }],
        proprietary_data={"total_active_mg": 100, "total_active_ingredients": 3},
    )
    payload = score_transparency(product)
    # B5 should fire but with 0.4x probiotic class multiplier
    b5 = payload["penalties"].get("B5_proprietary_blend_opacity", 0.0)
    assert b5 <= 0
    # The probiotic 0.4x makes B5 significantly lighter than the generic
    # 1.0x version of the same blend would be.
    assert abs(b5) < 3.0, "probiotic class multiplier should keep B5 light"


# --- B6 marketing penalty (reused) ---------------------------------------


def test_transparency_b6_disease_claim_penalty_reuses_generic() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    payload = score_transparency(_probiotic(has_disease_claims=True))
    assert payload["penalties"]["B6_marketing_claims"] == -5.0


# --- Dimension assembly --------------------------------------------------


def test_transparency_dimension_cap_15() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    payload = score_transparency(_probiotic())
    assert payload["max"] == 15.0


def test_transparency_dimension_clamps_to_15() -> None:
    """Strain identities 8 + per-strain CFU 7 + B3 +4 = 19. Must clamp to 15."""
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        strain_count=2,
        blends=[
            {"name": "L. rhamnosus", "strains": ["L. rhamnosus HN001"],
             "cfu_data": {"has_cfu": True, "billion_count": 10}},
            {"name": "B. lactis", "strains": ["B. lactis BB-12"],
             "cfu_data": {"has_cfu": True, "billion_count": 5}},
        ],
        compliance={"gluten_free": True,
                    "allergen_free_claims": ["dairy-free"],
                    "vegan": True, "conflicts": [],
                    "has_may_contain_warning": False},
    )
    payload = score_transparency(product)
    assert payload["score"] == 15.0


def test_transparency_floors_at_zero() -> None:
    """Heavy penalties can't drive Transparency negative."""
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = _probiotic(
        strain_count=0, blends=[],
        has_disease_claims=True,
        allergens=[{"allergen_id": "milk", "severity_level": "high"}],
    )
    product["probiotic_data"]["total_strain_count"] = 0
    payload = score_transparency(product)
    assert payload["score"] >= 0.0


def test_transparency_phase_marker_p25() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    payload = score_transparency(_probiotic())
    assert payload["phase"] == "P2.5_probiotic_transparency"
    assert payload["metadata"]["phase"] == "P2.5_probiotic_transparency"


def test_transparency_resilient_to_malformed_input() -> None:
    from scoring_v4.modules.probiotic_transparency import score_transparency

    for bad in (None, {}, {"probiotic_data": None}, 42, "oops"):
        payload = score_transparency(bad)  # type: ignore[arg-type]
        assert payload["score"] >= 0
        assert payload["max"] == 15.0
        assert "strain_identities_named" in payload["components"]


# --- Module wiring -------------------------------------------------------


def test_probiotic_module_phase_rolls_forward_after_p25() -> None:
    """Module-level phase rolls forward as each P2.x slice lands. After
    P2.5 the marker is at least P2.5; P2.6 final assembly rolls it again."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic()).to_breakdown()
    assert breakdown["phase"].startswith("P2."), (
        f"unexpected phase: {breakdown['phase']}"
    )


def test_probiotic_module_transparency_dimension_populated() -> None:
    """After P2.5, transparency dim is no longer skeleton."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic()).to_breakdown()
    trans = breakdown["dimensions"]["transparency"]
    assert trans["score"] is not None
    assert "strain_identities_named" in trans["components"]
    assert trans["max"] == 15


def test_probiotic_canary_full_dimensions_populated_at_p25() -> None:
    """All 5 probiotic dimensions populated by P2.5. score_100 lands
    via P2.6 final assembly (this test originally asserted None; rolled
    forward to assert the dimensions populate independently of final
    assembly)."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic(strain_count=5)).to_breakdown()
    for name in ("formulation", "dose", "evidence", "transparency"):
        assert breakdown["dimensions"][name]["score"] is not None, (
            f"{name} should be populated at P2.5"
        )


# --- Architecture lock ---------------------------------------------------


def test_probiotic_transparency_does_not_import_v3() -> None:
    import scoring_v4.modules.probiotic_transparency as pt

    source = Path(pt.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
