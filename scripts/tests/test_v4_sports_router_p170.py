"""Wave 6 sports v4 router tests.

The sports module must route explicit sports-nutrition products away from
generic RDA/UL dose math without turning every amino-acid or protein-like
product into a sports product.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_input_contract import SCORING_CLASSIFICATION_SCHEMA_VERSION
from scoring_v4.router import class_for_product


def _row(canonical_id: str, quantity: float = 1.0, unit: str = "g") -> dict:
    return {
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "score_eligible": True,
        "score_eligible_by_cleaner": True,
        "score_exclusion_reason": None,
        "score_exclusion_reason_code": None,
    }


def _product_evidence(
    *,
    canonical_id: str,
    evidence_type: str,
    quantity: float = 1.0,
    unit: str = "g",
) -> dict:
    return {
        "canonical_id": canonical_id,
        "clean_identity_id": canonical_id,
        "scoring_parent_id": canonical_id,
        "evidence_canonical_id": canonical_id,
        "canonical_source_db": "test_fixture",
        "evidence_origin": "native_enrichment",
        "evidence_type": evidence_type,
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "dose_value": quantity,
        "dose_unit": unit,
        "source": "test",
        "raw_source_path": f"product_scoring_evidence.{evidence_type}",
        "evidence_scope": "blend_level" if evidence_type == "blend_anchor_mass" else "row_level",
        "linked_rows": [f"product_scoring_evidence.{evidence_type}"],
        "confidence": "medium",
        "reason": "test_fixture",
        "name": canonical_id.replace("_", " ").title(),
    }


def _product(
    *,
    primary_type: str,
    name: str,
    rows: list[dict] | None = None,
    product_scoring_evidence: list[dict] | None = None,
) -> dict:
    return {
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "fullName": name,
        "product_name": name,
        "ingredient_quality_data": {"ingredients_scorable": rows or []},
        "product_scoring_evidence": product_scoring_evidence or [],
    }


def test_pre_workout_taxonomy_routes_to_sports() -> None:
    product = _product(
        primary_type="pre_workout",
        name="RapidDrive Pre-Workout Amino Complex",
        rows=[_row("beta-alanine", 3200, "mg")],
    )

    assert class_for_product(product) == "sports"


def test_pre_workout_name_overrides_b_complex_taxonomy() -> None:
    product = _product(
        primary_type="b_complex",
        name="PRE Pre-Workout Complex Blue Raspberry",
        rows=[_row("l_citrulline", 6000, "mg"), _row("beta-alanine", 3000, "mg")],
    )

    assert class_for_product(product) == "sports"


def test_creatine_variants_route_to_sports() -> None:
    for canonical in ("creatine", "creatine_hcl", "creatine_nitrate", "magnesium_creatine_chelate"):
        product = _product(
            primary_type="general_supplement",
            name="Creatine Performance",
            rows=[_row(canonical, 5, "g")],
        )

        assert class_for_product(product) == "sports", canonical


def test_pre_workout_taxonomy_with_alpha_gpc_atp_routes_to_sports() -> None:
    """A confident pre_workout taxonomy routes to sports by IDENTITY even when the
    actives are non-classic (alpha-GPC / ATP / stimulant botanicals) with no
    creatine/protein/BCAA/EAA/HMB anchor. The completeness gate now fails OPEN for
    these (soft debt, not NOT_SCORED) and the dose rubric credits the disclosed
    alpha-GPC/ATP, so routing them sports is net-positive (Thorne Pre-Workout Elite
    323126: generic 50.5 -> sports 58.5).
    """
    product = _product(
        primary_type="pre_workout",
        name="Pre-Workout Elite Citrus Berry Flavored",
        rows=[
            _row("alpha_gpc", 600, "mg"),
            _row("adenosine_triphosphate", 450, "mg"),
            _row("guayusa_leaf", 350, "mg"),
            _row("mango_leaf_extract", 140, "mg"),
        ],
    )

    assert class_for_product(product) == "sports"


def test_stale_native_sports_classification_without_identity_is_ignored() -> None:
    """Native classification cannot pin an obsolete sports route.

    A product with no sports identity or name (here a plain vitamin C) must route
    generic even when a persisted native enrichment blob still claims sports;
    otherwise stale blobs would mis-score until a full re-enrich. (The Thorne
    pre-workout shape now legitimately routes sports via the derived contract, so
    this guard uses a non-sports product to isolate the native-override behavior.)
    """
    product = _product(
        primary_type="single_nutrient",
        name="Vitamin C 500 mg Ascorbic Acid",
        rows=[_row("vitamin_c", 500, "mg")],
    )
    product["product_scoring_classification"] = {
        "classification_schema_version": SCORING_CLASSIFICATION_SCHEMA_VERSION,
        "classification_origin": "native_enrichment",
        "classification_failed": False,
        "route_module": "sports",
        "route_reason": "profile_content:sports",
        "route_confidence": "high",
        "route_evidence": ["sports_identity_or_dose", "scoring_rows_present"],
        "ingredients": [],
        "profile_eligibility": {},
    }

    assert class_for_product(product) == "generic"


def test_creatine_name_with_undisclosed_blend_routes_to_sports() -> None:
    """GNC Amplified Creatine XXX (18538): the name says creatine but the actives sit
    in a proprietary "Micronized Creatine Matrix Blend" with no disclosed creatine
    canonical (only arginine/glutamine blend anchors). The unambiguous creatine name
    routes it sports by identity; the opaque blend then correctly craters the dose
    dimension (transparency penalty), not the route.
    """
    product = _product(
        primary_type="general_supplement",
        name="Amplified Creatine XXX Blue Raspberry",
        rows=[_row("l_arginine", 10, "g"), _row("l_glutamine", 7, "g")],
    )

    assert class_for_product(product) == "sports"


def test_bcaa_plus_name_with_aggregate_routes_to_sports() -> None:
    """Nutricost BCAA+ (306183/307773): an unambiguous BCAA product whose BCAAs are
    disclosed as a single branched_chain_amino_acids aggregate (7 g) rather than the
    leu/iso/val trio. The BCAA name + aggregate identity route it sports.
    """
    product = _product(
        primary_type="amino_acid",
        name="BCAA+ Peach Mango",
        rows=[_row("branched_chain_amino_acids", 7000, "mg"), _row("potassium", 92, "mg")],
    )

    assert class_for_product(product) == "sports"


def test_carnitine_with_bcaa_routes_to_sports_and_is_dose_proxied() -> None:
    """GNC Carnitine 1000 + BCAA (67304): a fitness product with a 'BCAA' name token
    routes sports. Its L-carnitine primary has no sports dose band, but the sports
    dose dimension falls back to the generic dose-adequacy proxy (see
    test_offlist_dominant_active_uses_generic_dose_proxy) rather than discarding it,
    so routing sports is net-neutral. No carnitine routing guard is needed.
    """
    product = _product(
        primary_type="amino_acid",
        name="Carnitine 1000 + BCAA Orange Cream",
        rows=[_row("l_carnitine", 1, "Gram(s)")],
    )

    assert class_for_product(product) == "sports"


def test_whey_protein_powder_routes_to_sports() -> None:
    product = _product(
        primary_type="protein_powder",
        name="Whey Protein Isolate Dutch Chocolate",
        rows=[_row("whey_protein", 25, "Gram(s)")],
    )

    assert class_for_product(product) == "sports"


def test_casein_protein_powder_routes_to_sports() -> None:
    product = _product(
        primary_type="protein_powder",
        name="Micellar Casein Protein",
        rows=[_row("casein", 5, "Gram(s)")],
    )

    assert class_for_product(product) == "sports"


def test_keratin_protein_powder_stays_generic() -> None:
    product = _product(
        primary_type="protein_powder",
        name="Keratin 500 mg",
        rows=[_row("keratin", 500, "mg")],
    )

    assert class_for_product(product) == "generic"


def test_mixed_multivitamin_with_whey_row_stays_multi_not_sports() -> None:
    product = _product(
        primary_type="multivitamin",
        name="Daily Energy Shake",
        rows=[
            _row("vitamin_a", 900, "mcg"),
            _row("vitamin_c", 90, "mg"),
            _row("vitamin_d", 25, "mcg"),
            _row("vitamin_b12_cobalamin", 100, "mcg"),
            _row("whey_protein", 8, "Gram(s)"),
        ],
    )

    assert class_for_product(product) == "multi_or_prenatal"


def test_herbal_recovery_formula_with_pea_protein_stays_generic() -> None:
    product = _product(
        primary_type="herbal_botanical",
        name="Recover Powder",
        rows=[
            _row("magnesium", 84, "mg"),
            _row("pea_protein", 1.97, "Gram(s)"),
            _row("curcumin", 600, "mg"),
            _row("tart_cherry", 480, "mg"),
            _row("ashwagandha", 300, "mg"),
        ],
    )

    assert class_for_product(product) == "generic"


def test_explicit_whey_label_with_whey_row_routes_to_sports() -> None:
    product = _product(
        primary_type="general_supplement",
        name="Whey Protein Blend",
        rows=[_row("whey_protein", 20, "Gram(s)")],
    )

    assert class_for_product(product) == "sports"


def test_creatine_amino_acid_routes_to_sports_by_canonical() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Creatine Monohydrate 3 g",
        rows=[_row("creatine_monohydrate", 3, "Gram(s)")],
    )

    assert class_for_product(product) == "sports"


def test_bcaa_trio_routes_to_sports() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Precision BCAA Gummy Worm",
        rows=[
            _row("l_leucine", 5, "Gram(s)"),
            _row("l_isoleucine", 2.5, "Gram(s)"),
            _row("l_valine", 2.5, "Gram(s)"),
        ],
    )

    assert class_for_product(product) == "sports"


def test_incidental_bcaa_trio_in_mixed_formula_stays_generic() -> None:
    product = _product(
        primary_type="omega_3",
        name="SynaQuell",
        rows=[
            _row("l_leucine", 1250, "mg"),
            _row("l_isoleucine", 625, "mg"),
            _row("l_valine", 625, "mg"),
            _row("dha", 125, "mg"),
            _row("curcumin", 125, "mg"),
        ],
    )

    assert class_for_product(product) == "generic"


def test_standalone_citrulline_routes_to_sports_by_name_and_canonical() -> None:
    product = _product(
        primary_type="amino_acid",
        name="L-Citrulline Powder",
        rows=[_row("l_citrulline", 1200, "mg")],
    )

    assert class_for_product(product) == "sports"


def test_nac_amino_acid_stays_generic() -> None:
    product = _product(
        primary_type="amino_acid",
        name="NAC 600 mg",
        rows=[_row("nac", 600, "mg")],
    )

    assert class_for_product(product) == "generic"


def test_theanine_sleep_support_stays_generic() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Calm Sleep L-Theanine",
        rows=[_row("l_theanine", 200, "mg")],
    )

    assert class_for_product(product) == "generic"


def test_digestive_enzyme_amino_cofactor_routes_fiber_digestive_not_sports() -> None:
    product = _product(
        primary_type="amino_acid",
        name="Digestive Enzymes Ultra with Betaine HCl",
        rows=[_row("tmg_betaine", 650, "mg")],
    )

    assert class_for_product(product) == "fiber_digestive"


def test_conservative_blend_anchor_protein_does_not_route_multivitamin_to_sports() -> None:
    product = _product(
        primary_type="multivitamin",
        name="Daily Multi Shake",
        rows=[
            _row("vitamin_a", 900, "mcg"),
            _row("vitamin_c", 90, "mg"),
            _row("vitamin_d", 25, "mcg"),
            _row("vitamin_b12_cobalamin", 100, "mcg"),
        ],
        product_scoring_evidence=[
            _product_evidence(
                canonical_id="whey_protein",
                evidence_type="blend_anchor_mass",
                quantity=20,
                unit="Gram(s)",
            )
        ],
    )

    assert class_for_product(product) == "multi_or_prenatal"


def test_stale_taxonomy_whey_with_product_level_protein_mass_routes_sports() -> None:
    product = _product(
        primary_type="single_mineral",
        name="100% Whey Protein Powdered Drink Mix Chocolate",
        rows=[_row("potassium", 240, "mg")],
        product_scoring_evidence=[
            _product_evidence(
                canonical_id="protein",
                evidence_type="blend_anchor_mass",
                quantity=20,
                unit="Gram(s)",
            )
        ],
    )

    assert class_for_product(product) == "sports"


def test_stale_taxonomy_creatine_blend_anchor_routes_sports() -> None:
    product = _product(
        primary_type="general_supplement",
        name="Creatine Advance XR Unflavored",
        product_scoring_evidence=[
            _product_evidence(
                canonical_id="creatine_monohydrate",
                evidence_type="blend_anchor_mass",
                quantity=5,
                unit="Gram(s)",
            )
        ],
    )

    assert class_for_product(product) == "sports"


def test_collagen_protein_macro_does_not_route_sports() -> None:
    product = _product(
        primary_type="protein_powder",
        name="Collagen Hyaluronic Acid 20 g Unflavored",
        rows=[
            _row("collagen", 20, "Gram(s)"),
            _row("hyaluronic_acid", 120, "mg"),
        ],
        product_scoring_evidence=[
            _product_evidence(
                canonical_id="protein",
                evidence_type="sports_primary_dose",
                quantity=18,
                unit="Gram(s)",
            )
        ],
    )

    assert class_for_product(product) == "generic"


def test_native_sports_primary_dose_evidence_can_route_to_sports() -> None:
    product = _product(
        primary_type="general_supplement",
        name="Recovery Protein Drink",
        product_scoring_evidence=[
            _product_evidence(
                canonical_id="protein",
                evidence_type="sports_primary_dose",
                quantity=20,
                unit="Gram(s)",
            )
        ],
    )

    assert class_for_product(product) == "sports"
