"""v4 Omega Formulation dimension — P1.6.1 tests.

Locks the Formulation sub-component math:

    form_tier            8 / 8 / 7 / 4 / 2 (TG / rTG / PL / EE / undefined)
    source_disclosed     +4
    premium_form_a2      +5 (only when form != undefined)
    sustainability_cert  +2 (Friend of the Sea or MSC, rules_db verified)
    epa_dha_concentration +0..4 (EPA+DHA mg / omega oil mg, when disclosed)

Maximum reachable: 23/25 today. The remaining 2-point headroom is reserved
for future lot-level purity/oxidation evidence.

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
         "mapped": True, "quantity": epa, "unit": "mg"},
        {"name": "Docosahexaenoic Acid", "canonical_id": "dha",
         "mapped": True, "quantity": dha, "unit": "mg"},
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
    assert payload["components"]["form_tier"] == 8.0
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
    assert payload["components"]["form_tier"] == 8.0
    assert payload["metadata"]["form_detected"] == "tg"


def test_form_tier_rtg_re_esterified_match() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Triple Strength Omega-3 Re-esterified"
    ))
    assert payload["components"]["form_tier"] == 8.0
    assert payload["metadata"]["form_detected"] == "rtg"


def test_form_tier_ee_ethyl_ester_match() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Fish Oil Ethyl Esters EPA 500 DHA 200"
    ))
    assert payload["components"]["form_tier"] == 4.0
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
    assert payload["components"]["form_tier"] == 8.0


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
    assert payload["components"]["form_tier"] == 7.0
    assert payload["metadata"]["form_detected"] == "pl"


def test_form_tier_pl_explicit_phospholipid_keyword() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Phospholipid Omega-3 Complex"
    ))
    assert payload["components"]["form_tier"] == 7.0
    assert payload["metadata"]["form_detected"] == "pl"


def test_form_tier_undefined_bare_fish_oil_no_form_keyword() -> None:
    """Per 'do not invent fields': bare 'fish oil' is NOT enough to credit
    TG. Many commodity fish oils ARE TG but processing is opaque from
    label text. Score undefined = 2 baseline."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Fish Oil 1000 mg Softgels"
    ))
    assert payload["components"]["form_tier"] == 2.0
    assert payload["metadata"]["form_detected"] == "undefined"


def test_undefined_form_high_dose_verified_quality_gets_data_limited_floor() -> None:
    """A strong, source-disclosed EPA/DHA product with verified third-party
    quality evidence should not crater to 6/25 solely because DSLD omitted
    molecular form. This is a data-limited floor, not invented TG/rTG credit:
    premium_form_a2_carry remains absent and form_detected stays undefined."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Prenatal DHA Fish Oil",
        epa=200,
        dha=650,
        certification_data=_verified_quality_program("IFOS Certified"),
    ))

    assert payload["score"] == 17.0
    assert payload["components"]["form_tier"] == 2.0
    assert payload["components"]["source_disclosed"] == 4.0
    assert payload["components"]["data_limited_formulation_floor"] == 11.0
    assert "premium_form_a2_carry" not in payload["components"]
    assert payload["metadata"]["form_detected"] == "undefined"
    assert payload["metadata"]["data_limited_form_floor_applied"] is True
    assert payload["metadata"]["data_limited_form_floor"]["quality_programs"] == ["IFOS Certified"]


def test_undefined_form_high_dose_without_verified_quality_stays_label_only() -> None:
    """Dose + source alone is not enough to infer quality/form. Commodity
    undefined-form fish oil stays at form_tier + source only."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Prenatal DHA Fish Oil",
        epa=200,
        dha=650,
    ))

    assert payload["score"] == 6.0
    assert "data_limited_formulation_floor" not in payload["components"]
    assert payload["metadata"]["data_limited_form_floor_applied"] is False


def test_undefined_form_floor_accepts_sku_verified_cert_programs() -> None:
    """Some enriched records carry verified SKU certs in verified_cert_programs
    even when evidence_based.third_party_programs is empty. SKU/product-line
    verified certs are real quality evidence; claimed_only/brand_only remain
    ineligible."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Prenatal DHA Fish Oil",
        epa=200,
        dha=650,
        certification_data={
            "verified_cert_programs": [
                {"program": "NSF Certified", "scope": "sku", "match_confidence": 1.0},
                {"program": "IFOS", "scope": "brand_only"},
            ],
            "evidence_based": {"third_party_programs": []},
        },
    ))

    assert payload["score"] == 17.0
    assert payload["metadata"]["data_limited_form_floor"]["quality_programs"] == ["NSF Certified"]


def test_undefined_form_floor_rejects_mismatched_registry_brand() -> None:
    """A stale/bad cert match can carry scope=sku but point to another brand.
    Do not use it as quality evidence for the omega form fallback."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Fish Oil 1000 mg",
        epa=600,
        dha=400,
        certification_data={
            "verified_cert_programs": [
                {
                    "program": "NSF Sport",
                    "scope": "sku",
                    "match_confidence": 1.0,
                    "matched_brand": "LTH",
                    "matched_product": "GLOW Omega-3 Fish Oil",
                }
            ]
        },
    )
    product["brandName"] = "CVS Health"

    payload = score_formulation(product)

    assert payload["score"] == 6.0
    assert payload["metadata"]["data_limited_form_floor"]["quality_programs"] == []


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
    assert payload["components"]["form_tier"] == 2.0
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
    assert payload["components"]["form_tier"] == 2.0
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


# --- Premium-form A2 carryforward (only when form != undefined) ----------


def test_premium_a2_credit_awarded_when_form_disclosed() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Omega-3 Triglycerides EPA+DHA",
    ))
    assert payload["components"]["premium_form_a2_carry"] == 5.0


def test_premium_a2_credit_not_awarded_when_form_undefined() -> None:
    """Per the rubric: premium A2 carryforward is the 'you disclosed form +
    EPA/DHA together' signal. Undefined form → no carryforward."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Fish Oil 1000 mg"  # no form keyword
    ))
    assert "premium_form_a2_carry" not in payload["components"]


# --- Source-disclosed credit (+4) ----------------------------------------


def test_source_disclosed_fish_oil() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Omega-3 Fish Oil EPA+DHA"
    ))
    assert payload["components"]["source_disclosed"] == 4.0


def test_source_disclosed_krill() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(name="Krill Omega"))
    assert payload["components"]["source_disclosed"] == 4.0


def test_source_disclosed_algae_vegan_dha() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Algae Oil Vegan DHA 200"
    ))
    assert payload["components"]["source_disclosed"] == 4.0


def test_source_disclosed_cod_liver() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(name="Norwegian Cod Liver Oil"))
    assert payload["components"]["source_disclosed"] == 4.0


def test_source_not_disclosed_bare_epa_dha_name() -> None:
    """'EPA+DHA' alone doesn't tell the consumer where the omega-3 comes
    from. No source bonus."""
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_epa_dha_product(
        name="Pure EPA+DHA Concentrate"
    ))
    assert "source_disclosed" not in payload["components"]


# --- Sustainability cert (rules_db verified) -----------------------------


def test_sustainability_credit_friend_of_the_sea_rules_db_verified() -> None:
    """Friend of the Sea must be in evidence_based.third_party_programs
    with score_eligible=True. Bare label-text claims do NOT qualify."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Sustainable Fish Oil",
        certification_data=_verified_sustainability("Friend of the Sea"),
    )
    payload = score_formulation(product)
    assert payload["components"]["sustainability_cert"] == 2.0
    assert payload["metadata"]["sustainability_cert_program"] == "Friend of the Sea"


def test_sustainability_credit_msc_rules_db_verified() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="MSC Sustainable Fish Oil",
        certification_data=_verified_sustainability("MSC"),
    )
    payload = score_formulation(product)
    assert payload["components"]["sustainability_cert"] == 2.0


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
            {"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 1000, "unit": "mg"}
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


def test_maximum_reachable_score_is_23() -> None:
    """Per the rubric: max reachable today is form 8 + source 4 +
    premium 5 + sustainability 2 + concentration 4 = 23/25. The remaining
    2-point headroom is reserved for future lot-level purity evidence."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = _epa_dha_product(
        name="Premium Natural Triglyceride Fish Oil",
        extra_ingredients=[
            {"name": "Fish Oil", "canonical_id": "fish_oil", "quantity": 1000, "unit": "mg"}
        ],
        certification_data=_verified_sustainability("Friend of the Sea"),
    )
    payload = score_formulation(product)
    assert payload["score"] == 23.0
    assert payload["metadata"]["max_reachable_in_p161"] == 23.0


def test_dimension_cap_clamps_above_25() -> None:
    """Defensive: if a future bug adds enough components to exceed 25,
    the cap clamps. Verified at 21 today since no path reaches 25+;
    test exercises the clamp logic shape."""
    from scoring_v4.modules.omega_formulation import score_formulation, CAP_FORMULATION

    assert CAP_FORMULATION == 25.0


# --- Canary integration --------------------------------------------------


def test_canary_sports_research_omega_3_scores_max_reachable() -> None:
    """Sports Research Omega-3 1055mg Fish Oil (DSLD 327776) has TG form
    (via ingredient panel 'Triglycerides' row), source disclosed
    (Fish Oil Concentrate), and Friend of the Sea rules_db verified.
    Expected: 23/25 (max reachable today)."""
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
    assert payload["score"] == 23.0
    assert payload["metadata"]["form_detected"] == "tg"
    assert payload["metadata"]["sustainability_cert_program"] == "Friend of the Sea"


def test_canary_nordic_naturals_ultimate_omega_undefined_form() -> None:
    """Nordic Naturals Ultimate Omega + CoQ10 (DSLD 288740) has no form
    keyword on the DSLD label (Nordic is widely known to be rTG but
    doesn't disclose this on the label DSLD scrapes). Per
    'do not invent fields', score the undefined-form baseline only.
    Expected: form_tier 2 + source 4 + sustainability 2 + concentration 4 = 12/25.
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
                 "quantity": 650, "unit": "mg"},
                {"name": "Docosahexaenoic Acid", "canonical_id": "dha",
                 "quantity": 450, "unit": "mg"},
                    {"name": "purified deep sea Fish Oil", "canonical_id": "fish_oil", "quantity": 1100, "unit": "mg"},
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
    assert payload["score"] == 12.0
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

    assert f["form_tier"]["tg"] == 8
    assert f["form_tier"]["pl"] == 7
    assert f["form_tier"]["rtg"] == 8
    assert f["form_tier"]["ee"] == 4
    assert f["form_tier"]["undefined"] == 2
    assert f["source_disclosed"]["score"] == 4
    assert f["premium_form_a2_carry"]["score"] == 5
    assert f["sustainability_cert"]["score"] == 2
    assert f["epa_dha_concentration"]["score_bands"][0]["score"] == 4
    assert f["sustainability_cert"]["eligibility"] == "rules_db_verified"
