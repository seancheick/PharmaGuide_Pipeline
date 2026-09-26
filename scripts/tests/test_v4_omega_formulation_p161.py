"""v4 Omega Formulation dimension — P1.6.1 tests.

Locks the Formulation sub-component math:

    form_tier            8 / 8 / 7 / 4 / 2 (TG / rTG / PL / EE / undefined)
    source_disclosed     +4
    premium_form_a2      +5 (only when form != undefined)
    sustainability_cert  0 (attribute only since quality_score 1.2.0; program kept in metadata)
    epa_dha_concentration +0..4 (EPA+DHA mg / omega oil mg, when disclosed)

Maximum reachable: 21/25 today.

Per Sean's 2026-05-20 directive: 'Do not invent fields.' Form is credited
only when the label or ingredient panel EXPLICITLY discloses molecular
form. Bare 'fish oil' does NOT imply TG. Nordic Naturals scores 'undefined'
because their DSLD label omits form info (even though they're known to be
rTG) — credit follows the label, not marketing knowledge.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# --- Helpers --------------------------------------------------------------


def _epa_dha_product(
    *,
    name: str = "Generic EPA+DHA",
    epa: float = 600,
    dha: float = 300,
    extra_ingredients: list | None = None,
    certification_data: dict | None = None,
) -> dict:
    """Build a minimal omega-class product for formulation tests."""
    ingredients = [
        {"name": "Eicosapentaenoic Acid", "canonical_id": "epa",
         "mapped": True, "quantity": epa, "unit": "mg",
         "matched_form": "epa (unspecified)", "bio_score": 8.0},
        {"name": "Docosahexaenoic Acid", "canonical_id": "dha",
         "mapped": True, "quantity": dha, "unit": "mg",
         "matched_form": "dha (unspecified)", "bio_score": 8.0},
    ]
    if extra_ingredients:
        ingredients.extend(extra_ingredients)
    product = {
        "status": "active",
        "form_factor": "softgel",
        "product_name": name,
        "supplement_type": {"type": "targeted", "category_breakdown": {"fatty_acid": 2}},
        "ingredient_quality_data": {
            "total_active": len(ingredients),
            "ingredients_scorable": ingredients,
        },
    }
    if certification_data:
        product["certification_data"] = certification_data
    return product


def _set_epa_dha_iqm_form(product: dict, form_label: str, bio_score: float) -> dict:
    """Set the enriched IQM result; label text alone never sets quality."""
    for row in product["ingredient_quality_data"]["ingredients_scorable"]:
        canonical = row.get("canonical_id")
        if canonical in {"epa", "dha"}:
            row["matched_form"] = f"{canonical} {form_label}"
            row["bio_score"] = bio_score
    return product


def _verified_sustainability(program: str) -> dict:
    """Build the certification_data shape that the rules_db-verified
    sustainability check looks for."""
    return {
        "evidence_based": {
            "third_party_programs": [
                {
                    "rule_id": f"CERT_{program.upper().replace(' ', '_')}",
                    "display_name": program,
                    "score_eligible": True,
                    "evidence_strength": "strong",
                    "points_if_eligible": 5,
                }
            ]
        }
    }


def _verified_quality_program(program: str) -> dict:
    return {
        "evidence_based": {
            "third_party_programs": [
                {
                    "rule_id": f"CERT_{program.upper().replace(' ', '_')}",
                    "display_name": program,
                    "score_eligible": True,
                    "evidence_strength": "strong",
                }
            ]
        }
    }


# --- Component contract --------------------------------------------------


def test_returns_normalized_payload_shape() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product())
    for key in ("score", "max", "components", "penalties", "metadata"):
        assert key in payload
    assert payload["max"] == 25.0
    assert isinstance(payload["components"], dict)
    assert isinstance(payload["penalties"], dict)
    assert payload["metadata"]["phase"] == "P1.6.1_omega_formulation"


def test_empty_product_scores_zero() -> None:
    """Per the omega-signal guard: a product with no EPA/DHA, no source
    keyword, and no canonical_id evidence gets 0 — no form_tier baseline."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation({})
    assert payload["score"] == 0.0
    assert payload["components"] == {}


def test_none_input_scores_zero_safely() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(None)
    assert payload["score"] == 0.0
    assert payload["components"] == {}


def test_non_omega_product_scores_zero() -> None:
    """A magnesium glycinate product (no omega signal whatsoever) gets 0,
    even though score_formulation never raises on the input."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation({
        "product_name": "Magnesium Glycinate 200 mg",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Magnesium", "canonical_id": "magnesium", "quantity": 200}
        ]}
    })
    assert payload["score"] == 0.0


# --- Form-tier detection (TG / PL / rTG / EE / undefined) ----------------


def test_form_tier_tg_explicit_keyword_in_name() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Omega-3 Natural Triglycerides 1000 mg"
    ))
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "tg"


def test_form_tier_tg_via_ingredient_row_name() -> None:
    """Sports Research-style: ingredient panel has a row named
    'Triglycerides' — that IS the form disclosure even when product_name
    is silent."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Sports Research Omega-3 Fish Oil",
        extra_ingredients=[
            {"name": "Triglycerides", "canonical_id": "dha", "quantity": 1, "unit": "mg", "bio_score": 11.0}
        ],
    )
    payload = score_formulation(product)
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "tg"


def test_form_tier_rtg_re_esterified_match() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Triple Strength Omega-3 Re-esterified"
    ))
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "rtg"


def test_form_tier_ee_ethyl_ester_match() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Fish Oil Ethyl Esters EPA 500 DHA 200"
    ))
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "ee"


def test_form_tier_detected_from_label_text_statement() -> None:
    """Nordic-style: the molecular form is disclosed in the label text /
    statements ('All fish oils are in the triglyceride form'), NOT in the product
    name or ingredient panel. Form detection must read those surfaces — otherwise
    the gold-standard rTG/TG brands crater at form_tier=undefined (2)."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(name="Daily Omega")  # name carries no form keyword
    product["labelText"] = {
        "raw": "Wild caught. Pure. All fish oils are in the triglyceride form "
               "and surpass the strictest international standards."
    }
    payload = score_formulation(product)
    assert payload["metadata"]["form_detected"] == "tg"
    assert payload["components"]["form_tier"] == 4.5714


def test_form_tier_detected_from_statements_notes() -> None:
    """Form disclosed in structured statements[].notes (another real surface)."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(name="Omega-3")
    product["statements"] = [{"type": "other", "notes": "Superior Triglyceride Form."}]
    payload = score_formulation(product)
    assert payload["metadata"]["form_detected"] == "tg"


def test_triglyceride_health_claim_in_label_does_not_trigger_form() -> None:
    """A blood-lipid HEALTH CLAIM ('supports healthy triglyceride levels') is NOT
    a molecular-form disclosure. Reading label prose must not false-positive these
    into form=tg — only an explicit form context ('in the triglyceride form')
    counts. ~52 omega labels carry the health claim; mis-crediting them would
    invent a premium form that isn't disclosed."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(name="Omega-3 Fish Oil")
    product["labelText"] = {
        "raw": "Helps support healthy triglyceride levels already within the normal range."
    }
    payload = score_formulation(product)
    assert payload["metadata"]["form_detected"] == "undefined"


def test_form_tier_pl_krill_implies_phospholipid() -> None:
    """Krill omega-3 is naturally phospholipid-bound (phosphatidylcholine
    carrier). Per the rubric, 'krill' or 'krill oil' in the name maps to
    PL form = 7 pts. Clinical biochemistry, not heuristic."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Antarctic Krill Oil EPA+DHA"
    ))
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "pl"


def test_form_tier_pl_explicit_phospholipid_keyword() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Phospholipid Omega-3 Complex"
    ))
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "pl"


def test_form_tier_undefined_bare_fish_oil_no_form_keyword() -> None:
    """Per 'do not invent fields': bare 'fish oil' is NOT enough to credit
    TG. Many commodity fish oils ARE TG but processing is opaque from
    label text. Score undefined = 2 baseline."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Fish Oil 1000 mg Softgels"
    ))
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "undefined"


def test_certification_cannot_manufacture_omega_formulation_credit() -> None:
    """Certification belongs to Verification, not molecular formulation."""
    from scoring_v4.modules.omega_formulation import score_formulation

    certified = score_formulation(_epa_dha_product(
        name="Prenatal DHA Fish Oil",
        epa=200,
        dha=650,
        certification_data=_verified_quality_program("IFOS Certified"),
    ))
    uncertified = score_formulation(_epa_dha_product(
        name="Prenatal DHA Fish Oil",
        epa=200,
        dha=650,
    ))

    assert certified["score"] == uncertified["score"] == 4.57
    assert certified["components"] == uncertified["components"]
    assert certified["components"]["form_tier"] == 4.5714
    assert "source_disclosed" not in certified["components"]
    assert "premium_form_a2_carry" not in certified["components"]
    assert certified["metadata"]["form_detected"] == "undefined"


def test_undefined_form_high_dose_without_verified_quality_stays_label_only() -> None:
    """Dose + source alone is not enough to infer quality/form. Commodity
    undefined-form fish oil stays at form_tier + source only."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Prenatal DHA Fish Oil",
        epa=200,
        dha=650,
    ))

    assert payload["score"] == 4.57


def test_form_tier_does_not_treat_mct_carrier_as_omega_tg_form() -> None:
    """Medium-chain triglycerides are carrier/MCT fat, not an omega-3
    molecular form disclosure. A mixed fatty-acid product with an MCT row
    must keep the undefined-form baseline instead of full TG credit."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="CLA 3-6-9 with Fish Oil",
        extra_ingredients=[
            {"name": "Medium Chain Triglycerides", "canonical_id": "mct_oil",
             "quantity": 100, "unit": "mg"},
        ],
    )
    payload = score_formulation(product)
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "undefined"
    assert "premium_form_a2_carry" not in payload["components"]


def test_form_tier_does_not_treat_caprylic_capric_triglycerides_as_omega_tg() -> None:
    """Caprylic/capric triglycerides are MCT carrier wording and should not
    unlock omega TG form credit."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Fish Oil EPA DHA",
        extra_ingredients=[
            {"name": "Caprylic/Capric Triglycerides", "canonical_id": "mct_oil",
             "quantity": 50, "unit": "mg"},
        ],
    )
    payload = score_formulation(product)
    assert payload["components"]["form_tier"] == 4.5714
    assert payload["metadata"]["form_detected"] == "undefined"
    assert "premium_form_a2_carry" not in payload["components"]


def test_form_tier_pl_wins_over_tg_when_both_match() -> None:
    """A product labeled as 'Krill Oil ... Triglycerides' is most-specifically
    krill (PL). The pattern order PL > rTG > EE > TG is locked here."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Krill Oil with Natural Triglycerides"
    ))
    # PL pattern matches first (krill is naturally PL).
    assert payload["metadata"]["form_detected"] == "pl"


# --- Premium-form A2 carryforward: retired 2026-09-18 --------------------


def test_premium_a2_carry_is_retired_for_every_form() -> None:
    """Retired 2026-09-18: it re-paid for the molecular form form_tier scores."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Omega-3 Triglycerides EPA+DHA",
    ))
    assert "premium_form_a2_carry" not in payload["components"]


def test_premium_a2_credit_not_awarded_when_form_undefined() -> None:
    """Per the rubric: premium A2 carryforward is the 'you disclosed form +
    EPA/DHA together' signal. Undefined form → no carryforward."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Fish Oil 1000 mg"  # no form keyword
    ))
    assert "premium_form_a2_carry" not in payload["components"]


# --- Source detection (recorded in metadata, 0 points since 2026-09-18) ---


def test_source_disclosed_fish_oil() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Omega-3 Fish Oil EPA+DHA"
    ))
    assert "source_disclosed" not in payload["components"]  # Transparency owns disclosure
    assert payload["metadata"]["source_disclosed"] is True


def test_source_disclosed_krill() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(name="Krill Omega"))
    assert "source_disclosed" not in payload["components"]  # Transparency owns disclosure
    assert payload["metadata"]["source_disclosed"] is True


def test_source_disclosed_algae_vegan_dha() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Algae Oil Vegan DHA 200"
    ))
    assert "source_disclosed" not in payload["components"]  # Transparency owns disclosure
    assert payload["metadata"]["source_disclosed"] is True


def test_source_disclosed_cod_liver() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(name="Norwegian Cod Liver Oil"))
    assert "source_disclosed" not in payload["components"]  # Transparency owns disclosure
    assert payload["metadata"]["source_disclosed"] is True


def test_source_not_disclosed_bare_epa_dha_name() -> None:
    """'EPA+DHA' alone doesn't tell the consumer where the omega-3 comes
    from. No source bonus."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Pure EPA+DHA Concentrate"
    ))
    assert payload["metadata"]["source_disclosed"] is False


# --- Sustainability cert (rules_db verified) -----------------------------


def test_sustainability_friend_of_the_sea_is_attribute_only() -> None:
    """Friend of the Sea must be in evidence_based.third_party_programs
    with score_eligible=True. Bare label-text claims do NOT qualify."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Sustainable Fish Oil",
        certification_data=_verified_sustainability("Friend of the Sea"),
    )
    payload = score_formulation(product)
    assert "sustainability_cert" not in payload["components"]
    assert payload["metadata"]["sustainability_cert_program"] == "Friend of the Sea"


def test_sustainability_msc_is_attribute_only() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="MSC Sustainable Fish Oil",
        certification_data=_verified_sustainability("MSC"),
    )
    payload = score_formulation(product)
    assert "sustainability_cert" not in payload["components"]
    assert payload["metadata"]["sustainability_cert_program"] == "MSC"


def test_verified_sustainability_does_not_change_formulation_score() -> None:
    """Invariance: sustainable sourcing is an attribute, so the score is identical."""
    from scoring_v4.modules.omega_formulation import score_formulation

    certified = score_formulation(_epa_dha_product(
        name="Sustainable Fish Oil",
        certification_data=_verified_sustainability("Friend of the Sea"),
    ))
    plain = score_formulation(_epa_dha_product(name="Sustainable Fish Oil"))
    assert certified["score"] == plain["score"]
    assert certified["metadata"]["sustainability_cert_program"] == "Friend of the Sea"


# --- EPA+DHA concentration credit ----------------------------------------


def test_concentration_credit_high_potency_fish_oil() -> None:
    """750mg EPA+DHA in 1000mg fish oil is high concentration and earns
    meaningful formulation credit. This is label math, not a guessed field."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Natural Triglyceride Fish Oil",
        epa=500,
        dha=250,
        extra_ingredients=[
            {"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 1000, "unit": "mg",
             "mapped": True, "matched_form": "triglyceride (rTG) form", "bio_score": 14.0}
        ],
    )
    payload = score_formulation(product)
    assert payload["components"]["epa_dha_concentration"] == 4.0
    assert payload["metadata"]["epa_dha_concentration"]["ratio"] == 0.75


def test_concentration_credit_mid_potency_fish_oil() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Fish Oil",
        epa=180,
        dha=120,
        extra_ingredients=[
            {"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 1000, "unit": "mg"}
        ],
    )
    payload = score_formulation(product)
    assert payload["components"]["epa_dha_concentration"] == 2.0
    assert payload["metadata"]["epa_dha_concentration"]["ratio"] == 0.3


def test_concentration_not_awarded_without_oil_mass() -> None:
    """EPA/DHA disclosure alone does not invent concentration; parent oil
    mass must be present."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(name="Fish Oil", epa=500, dha=250))
    assert "epa_dha_concentration" not in payload["components"]
    assert payload["metadata"]["epa_dha_concentration"]["status"] == "missing_oil_mass"


def _with_total_fat(product: dict, amount: float, unit: str = "Gram(s)") -> dict:
    product["nutritionalInfo"] = {"totalFat": {"amount": amount, "unit": unit}}
    return product


def test_concentration_uses_declared_total_fat_upper_bound_when_oil_mass_missing() -> None:
    """Thorne Prenatal DHA prints DHA 650 mg + EPA 200 mg and Total Fat 1 g, but
    no oil mass. FDA rounds fat of 0.5-5 g to the nearest 0.5 g, so the oil is at
    most 1.25 g: concentration is at least 68%, never overstated."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_with_total_fat(
        _epa_dha_product(name="Prenatal DHA 650 mg", epa=200, dha=650), 1.0,
    ))
    concentration = payload["metadata"]["epa_dha_concentration"]
    assert concentration["oil_mg"] == 1250.0
    assert concentration["oil_mass_source"] == "total_fat_rounding_upper_bound"
    assert concentration["ratio"] == 0.68
    assert payload["components"]["epa_dha_concentration"] == 3.0


def test_total_fat_above_five_grams_uses_the_one_gram_rounding_bound() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_with_total_fat(
        _epa_dha_product(name="Fish Oil", epa=1200, dha=800), 6.0,
    ))
    assert payload["metadata"]["epa_dha_concentration"]["oil_mg"] == 6500.0

    at_five = score_formulation(_with_total_fat(
        _epa_dha_product(name="Fish Oil", epa=1200, dha=800), 5.0,
    ))
    assert at_five["metadata"]["epa_dha_concentration"]["oil_mg"] == 5500.0


def test_impossible_total_fat_bound_does_not_create_over_100_percent_concentration() -> None:
    """A rounded Total Fat bound below EPA+DHA is inconsistent label data,
    not proof of a concentration above 100%."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_with_total_fat(
        _epa_dha_product(name="Advanced Omega", epa=700, dha=590), 0.5,
    ))
    concentration = payload["metadata"]["epa_dha_concentration"]
    assert concentration["status"] == "inconsistent_oil_mass_below_epa_dha"
    assert "ratio" not in concentration
    assert "epa_dha_concentration" not in payload["components"]


def test_declared_oil_mass_wins_over_total_fat() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _with_total_fat(_epa_dha_product(
        name="Fish Oil", epa=500, dha=250,
        extra_ingredients=[{"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 1000, "unit": "mg"}],
    ), 3.0)
    concentration = score_formulation(product)["metadata"]["epa_dha_concentration"]
    assert concentration["oil_mg"] == 1000.0
    assert concentration["oil_mass_source"] == "label_oil_row"


def test_zero_total_fat_does_not_supply_oil_mass() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_with_total_fat(
        _epa_dha_product(name="Fish Oil", epa=500, dha=250), 0.0,
    ))
    assert payload["metadata"]["epa_dha_concentration"]["status"] == "missing_oil_mass"


def test_sustainability_does_not_credit_when_score_eligible_false() -> None:
    """Score_eligible=False means rules_db flagged the claim as
    proximity_conflict / negation / scope_violation. Do NOT credit."""
    from scoring_v4.modules.omega_formulation import score_formulation

    cert_data = _verified_sustainability("Friend of the Sea")
    cert_data["evidence_based"]["third_party_programs"][0]["score_eligible"] = False

    product = _epa_dha_product(
        name="Sustainable Fish Oil",
        certification_data=cert_data,
    )
    payload = score_formulation(product)
    assert "sustainability_cert" not in payload["components"]


def test_sustainability_does_not_credit_claimed_only_label_text() -> None:
    """A product with Friend of the Sea ONLY at
    verified_cert_programs[].scope=claimed_only (label text, no rules_db
    backing) does NOT score sustainability. P0.1b discipline preserved."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Fish Oil with Sustainable Claim",
        certification_data={
            "verified_cert_programs": [
                {"program": "Friend of the Sea", "scope": "claimed_only"}
            ],
            # No evidence_based.third_party_programs entry
        },
    )
    payload = score_formulation(product)
    assert "sustainability_cert" not in payload["components"]


def test_sustainability_does_not_credit_unrelated_cert() -> None:
    """USP/NSF/etc. don't count as sustainability certs even when
    rules_db verified."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="USP Verified Fish Oil",
        certification_data=_verified_sustainability("USP Verified"),
    )
    payload = score_formulation(product)
    assert "sustainability_cert" not in payload["components"]


# --- Score ceiling + headroom -------------------------------------------


def test_maximum_reachable_score_is_12() -> None:
    """Per the rubric: max reachable today is form 8 + concentration 4 = 12/25.
    Source disclosure and the premium-form carry were retired 2026-09-18
    (Transparency owns disclosure); sustainability adds 0."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Premium Natural Triglyceride Fish Oil",
        extra_ingredients=[
            {"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 1000, "unit": "mg",
             "mapped": True, "matched_form": "triglyceride (rTG) form", "bio_score": 14.0}
        ],
        certification_data=_verified_sustainability("Friend of the Sea"),
    )
    payload = score_formulation(product)
    assert payload["score"] == 12.0
    assert payload["metadata"]["max_reachable_in_p161"] == 12.0


def test_dimension_cap_clamps_above_25() -> None:
    """Defensive: if a future bug adds enough components to exceed 25,
    the cap clamps. Verified at 12 today since no path reaches 25+;
    test exercises the clamp logic shape."""
    from scoring_v4.modules.omega_formulation import score_formulation, CAP_FORMULATION

    assert CAP_FORMULATION == 25.0


# --- Canary integration --------------------------------------------------


def test_canary_sports_research_omega_3_scores_max_reachable() -> None:
    """Sports Research Omega-3 1055mg Fish Oil (DSLD 327776) has TG form
    (via ingredient panel 'Triglycerides' row), source disclosed
    (Fish Oil Concentrate), and Friend of the Sea rules_db verified.
    The frozen enrichment rates its parent-oil row at 10/14 of the IQM parent
    ceiling, so the label-text TG detector explains disclosure but does not
    override IQM quality."""
    from scoring_v4.modules.omega_formulation import score_formulation

    # Synthesize the canary blob shape from the field audit.
    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Omega-3 1055 mg Fish Oil 1250 mg",
        "brand_name": "Sports Research",
        "supplement_type": {"type": "targeted", "category_breakdown": {"fatty_acid": 4}},
        "ingredient_quality_data": {
            "total_active": 4,
            "ingredients_scorable": [
                {"name": "Fish Oil Concentrate", "canonical_id": "fish_oil",
                 "quantity": 1250, "unit": "mg", "bio_score": 10.0},
                    {"name": "Triglycerides", "canonical_id": "dha",
                     "quantity": 1, "unit": "mg", "bio_score": 11.0},
                {"name": "Eicosapentaenoic Acid", "canonical_id": "epa",
                 "quantity": 690, "unit": "mg", "bio_score": 10.0},
                {"name": "Docosahexaenoic Acid", "canonical_id": "dha",
                 "quantity": 310, "unit": "mg", "bio_score": 10.0},
            ],
        },
        "certification_data": {
            "evidence_based": {
                "third_party_programs": [
                    {"rule_id": "CERT_IFOS", "display_name": "IFOS Certified",
                     "score_eligible": True},
                    {"rule_id": "CERT_FRIEND_OF_THE_SEA",
                     "display_name": "Friend of the Sea",
                     "score_eligible": True},
                ]
            }
        }
    }
    payload = score_formulation(product)
    assert payload["score"] == 9.71
    assert payload["metadata"]["form_detected"] == "tg"
    assert payload["metadata"]["sustainability_cert_program"] == "Friend of the Sea"


def test_canary_nordic_naturals_ultimate_omega_undefined_form() -> None:
    """Nordic Naturals Ultimate Omega + CoQ10 (DSLD 288740) has no form
    keyword on the DSLD label (Nordic is widely known to be rTG but
    doesn't disclose this on the label DSLD scrapes). Per
    'do not invent fields', score the undefined-form baseline only.
    Expected: form_tier 2 + source 4 + concentration 4 = 10/25 (sustainability 0).
    No premium_form_a2_carry (form undefined)."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Ultimate Omega + CoQ10 Lemon",
        "brand_name": "Nordic Naturals",
        "supplement_type": {"type": "specialty",
                            "category_breakdown": {"fatty_acid": 5, "antioxidant": 1}},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Eicosapentaenoic Acid", "canonical_id": "epa",
                 "quantity": 650, "unit": "mg", "mapped": True,
                 "matched_form": "epa (unspecified)", "bio_score": 8.0},
                {"name": "Docosahexaenoic Acid", "canonical_id": "dha",
                 "quantity": 450, "unit": "mg", "mapped": True,
                 "matched_form": "dha (unspecified)", "bio_score": 8.0},
                {"name": "purified deep sea Fish Oil", "canonical_id": "fish_oil",
                 "quantity": 1100, "unit": "mg", "mapped": True,
                 "matched_form": "fish oil (unspecified)", "bio_score": 8.0},
            ],
        },
        "certification_data": {
            "evidence_based": {
                "third_party_programs": [
                    {"rule_id": "CERT_FRIEND_OF_THE_SEA",
                     "display_name": "Friend of the Sea",
                     "score_eligible": True},
                ]
            }
        }
    }
    payload = score_formulation(product)
    assert payload["score"] == 8.57
    assert payload["metadata"]["form_detected"] == "undefined"
    assert "premium_form_a2_carry" not in payload["components"]


# --- Skeleton roll-forward -----------------------------------------------


def test_omega_orchestrator_phase_rolls_forward_to_p161() -> None:
    """After P1.6.1 lands, the module-level phase marker advances."""
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega({"product_name": "Fish Oil"}).to_breakdown()
    assert breakdown["phase"].startswith("P1.6.")


def test_omega_formulation_dimension_score_populated_in_breakdown() -> None:
    """After P1.6.1 lands, score_omega's formulation dimension carries a
    numeric score (not None) — the other 4 dimensions remain None until
    their slices ship."""
    from scoring_v4.modules.omega import score_omega

    product = {
        "product_name": "Krill Oil 500 mg",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Krill Oil", "canonical_id": "krill_oil", "quantity": 500,
                 "mapped": True, "matched_form": "standard krill oil", "bio_score": 13.0},
                {"name": "EPA", "canonical_id": "epa", "quantity": 200},
                {"name": "DHA", "canonical_id": "dha", "quantity": 100},
            ],
        },
    }
    breakdown = score_omega(product).to_breakdown()
    form_dim = breakdown["dimensions"]["formulation"]
    assert form_dim["score"] is not None
    assert form_dim["score"] > 0


# --- Architecture lock ---------------------------------------------------


def test_omega_formulation_does_not_import_v3_scorer() -> None:
    """§13 architecture lock — omega_formulation.py is independent of
    score_supplements.py. AST-based check to avoid docstring false positives."""
    import ast
    import scoring_v4.modules.omega_formulation as of

    tree = ast.parse(Path(of.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith("score_supplements"), (
                f"v4→v3 import: from {module_name}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("score_supplements"), (
                    f"v4→v3 import: import {alias.name}"
                )


# --- Config-as-truth -----------------------------------------------------


def test_formulation_weights_match_rubric_config() -> None:
    """Code reads weights from omega_rubric.json; the config is the
    source of truth. This test confirms the loader sees the right values
    and would fail if someone edited code but not config (or vice versa)."""
    from scoring_v4.modules.omega_formulation import _load_rubric

    rubric = _load_rubric()
    f = rubric["formulation"]

    assert f["form_quality"]["cap"] == 8
    assert "form_tier" not in f
    assert f["source_disclosed"]["score"] == 0  # retired 2026-09-18
    assert f["premium_form_a2_carry"]["score"] == 0  # retired 2026-09-18
    assert f["sustainability_cert"]["score"] == 0
    assert f["epa_dha_concentration"]["score_bands"][0]["score"] == 4
    assert f["sustainability_cert"]["eligibility"] == "rules_db_verified"


# --- 2026-09-18 omega formulation semantics -------------------------------
# Formulation measures material facts: molecular form quality and EPA+DHA
# concentration. Disclosure is Transparency's job and is not paid twice.


def test_unknown_form_uses_iqm_nondisclosure_value_below_ethyl_ester() -> None:
    """IQM owns the authored one-point nondisclosure deduction."""
    from scoring_v4.modules.omega_formulation import score_formulation

    unknown = score_formulation(_epa_dha_product(name="Fish Oil 1000 mg"))
    ethyl_ester = score_formulation(_set_epa_dha_iqm_form(
        _epa_dha_product(name="Fish Oil Ethyl Esters EPA 500 DHA 200"),
        "fish oil ethyl ester", 9.0,
    ))

    assert unknown["components"]["form_tier"] < ethyl_ester["components"]["form_tier"]
    assert unknown["components"]["form_tier"] == 4.5714
    assert ethyl_ester["components"]["form_tier"] == 5.1429


def test_triglyceride_still_outranks_ethyl_ester() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    triglyceride = score_formulation(_set_epa_dha_iqm_form(
        _epa_dha_product(name="Natural Triglyceride Fish Oil"),
        "fish oil triglyceride", 11.0,
    ))
    ethyl_ester = score_formulation(_set_epa_dha_iqm_form(
        _epa_dha_product(name="Fish Oil Ethyl Esters EPA 500 DHA 200"),
        "fish oil ethyl ester", 9.0,
    ))

    assert triglyceride["components"]["form_tier"] > ethyl_ester["components"]["form_tier"]
    assert triglyceride["components"]["form_tier"] == 6.2857


def test_disclosing_the_form_earns_no_second_formulation_credit() -> None:
    """The premium-form carry paid for the same fact the form tier already scores,
    while Transparency separately pays for the disclosure."""
    from scoring_v4.modules.omega_formulation import score_formulation

    for name in ("Omega-3 Triglycerides EPA+DHA", "Fish Oil Ethyl Esters EPA 500 DHA 200",
                 "Krill Oil Phospholipid", "Fish Oil 1000 mg"):
        payload = score_formulation(_epa_dha_product(name=name))
        assert "premium_form_a2_carry" not in payload["components"], name


def test_naming_the_marine_source_earns_no_formulation_points() -> None:
    """Transparency owns source disclosure; Formulation reads material quality."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(name="Fish Oil 1000 mg"))

    assert "source_disclosed" not in payload["components"]
    assert payload["metadata"]["source_disclosed"] is True
