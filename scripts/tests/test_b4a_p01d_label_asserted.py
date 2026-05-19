"""P0.1d regression tests — provisional `label_asserted_product` tier.

Bridges the undercredit gap created by P0.1b: live registries cover only
NSF Sport + NSF/ANSI 173 today, so strong product-LABEL claims for USP /
Informed Choice / Informed Sport / BSCG would otherwise score zero until
their scrapers land.

Contract:
  - scope = "label_asserted_product"
  - evidence_source MUST be "product_label" (never "manufacturer")
  - program must be in the label-asserted whitelist:
      USP Verified, Informed Choice, Informed Sport, BSCG
    (IFOS is in an omega-only whitelist — gated by ingredient context.)
  - Friend of the Sea / MSC / GOED / generic claims → 0 B4a (route to
    other dimensions later — marine source quality, claim compliance).
  - Diminishing returns: 2 / 1 / 0, hard cap 3.
  - Stacks WITH sku/product_line rungs but the overall B4a hard cap (12)
    still wins.

These tests exercise `_compute_certifications_bonus` directly so they
don't depend on the enricher path that emits these scope strings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from score_supplements import SupplementScorer  # noqa: E402


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


def _make_product(verified_cert_programs=None, ingredients=None):
    # _get_active_ingredients reads from ingredient_quality_data.ingredients_scorable.
    # We mirror it into ingredients_scorable so the omega-gate detection works.
    ings = ingredients or []
    return {
        "verified_cert_programs": verified_cert_programs or [],
        "certification_data": {
            "third_party_programs": {"programs": []},
            "gmp": {},
            "batch_traceability": {"has_coa": False, "has_batch_lookup": False},
        },
        "gmp_level": None,
        "has_coa": False,
        "has_batch_lookup": False,
        "ingredients": ings,
        "ingredient_quality_data": {"ingredients_scorable": ings},
    }


def _label(program: str, source: str = "product_label"):
    """Build a label_asserted_product entry the enricher would emit."""
    return {
        "program": program,
        "scope": "label_asserted_product",
        "evidence_source": source,
        "recency_status": "fresh",
    }


# --- Whitelist-positive tests ---------------------------------------------


def test_usp_label_claim_without_scraper_scores_2(scorer: SupplementScorer) -> None:
    """USP Verified is whitelist #1 — strongest provisional candidate.
    Product-label evidence (no live scraper yet) → +2 B4a."""
    product = _make_product(verified_cert_programs=[_label("USP Verified")])
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 2.0
    assert result["_verified_scope_counts"] == {"label_asserted_product": 1}


def test_informed_choice_label_claim_scores_2(scorer: SupplementScorer) -> None:
    product = _make_product(verified_cert_programs=[_label("Informed Choice")])
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 2.0


def test_informed_sport_label_claim_scores_2(scorer: SupplementScorer) -> None:
    product = _make_product(verified_cert_programs=[_label("Informed Sport")])
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 2.0


def test_bscg_label_claim_scores_2(scorer: SupplementScorer) -> None:
    product = _make_product(verified_cert_programs=[_label("BSCG")])
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 2.0


# --- Manufacturer-evidence guard (defense in depth) -----------------------


def test_usp_manufacturer_only_resolves_to_zero(scorer: SupplementScorer) -> None:
    """USP claimed via brand injection only (not product label) → 0 B4a.
    The enricher should emit scope='claimed_only' for these, but even if a
    bug routes them to label_asserted_product, the scorer's evidence_source
    check refuses to credit."""
    product = _make_product(
        verified_cert_programs=[
            {
                "program": "USP Verified",
                "scope": "label_asserted_product",
                "evidence_source": "manufacturer",
                "recency_status": "fresh",
            }
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0, "manufacturer-evidence must not score label_asserted"


def test_usp_with_claimed_only_scope_zero(scorer: SupplementScorer) -> None:
    """Even with USP in the program whitelist, scope=claimed_only → 0."""
    product = _make_product(
        verified_cert_programs=[
            {"program": "USP Verified", "scope": "claimed_only", "recency_status": "fresh"}
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


# --- IFOS omega-gating ----------------------------------------------------


def test_ifos_label_on_omega_product_scores_2(scorer: SupplementScorer) -> None:
    """IFOS is in the omega-only whitelist — credits only when the product
    actually contains omega-3/fish-oil ingredients."""
    product = _make_product(
        verified_cert_programs=[_label("IFOS")],
        ingredients=[{"name": "Fish Oil", "standard_name": "fish oil"}],
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 2.0


def test_ifos_label_on_non_omega_product_zero(scorer: SupplementScorer) -> None:
    """IFOS label on a non-omega product (e.g., magnesium) → 0.
    Marine cert gate prevents off-topic credit."""
    product = _make_product(
        verified_cert_programs=[_label("IFOS")],
        ingredients=[{"name": "Magnesium Bisglycinate"}],
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


def test_ifos_manufacturer_only_zero_even_on_omega(scorer: SupplementScorer) -> None:
    """Manufacturer-injection of IFOS even on an omega product → 0.
    Combines IFOS-omega gate + manufacturer-evidence gate."""
    product = _make_product(
        verified_cert_programs=[
            {
                "program": "IFOS",
                "scope": "label_asserted_product",
                "evidence_source": "manufacturer",
                "recency_status": "fresh",
            }
        ],
        ingredients=[{"name": "Fish Oil"}],
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


# --- Out-of-whitelist programs (Codex: route to other dimensions, not B4a)


def test_friend_of_the_sea_label_zero_b4a(scorer: SupplementScorer) -> None:
    """Friend of the Sea is a marine/sustainability cert — not a purity cert.
    Even with label evidence on an omega product, must NOT score B4a.
    (Will land elsewhere in v4: marine source quality dimension.)"""
    product = _make_product(
        verified_cert_programs=[_label("Friend of the Sea")],
        ingredients=[{"name": "Fish Oil"}],
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


def test_msc_certified_label_zero_b4a(scorer: SupplementScorer) -> None:
    """MSC Certified is a sustainability cert — routes to marine source
    quality, not B4a testing/purity."""
    product = _make_product(
        verified_cert_programs=[_label("MSC Certified")],
        ingredients=[{"name": "Fish Oil"}],
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


def test_goed_certified_label_zero_b4a(scorer: SupplementScorer) -> None:
    """GOED is an industry oxidation-spec cert — not a third-party purity
    audit. Routes to omega source quality, not B4a."""
    product = _make_product(
        verified_cert_programs=[_label("GOED Certified")],
        ingredients=[{"name": "Fish Oil"}],
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


def test_generic_third_party_tested_label_zero(scorer: SupplementScorer) -> None:
    """A free-text 'Third-Party Tested' claim is too vague to credit.
    Only specific whitelisted programs get provisional B4a."""
    product = _make_product(
        verified_cert_programs=[_label("Third-Party Tested")]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


def test_labdoor_label_zero_b4a(scorer: SupplementScorer) -> None:
    """Labdoor is third-party-review media, not a cert audit.
    Routes to manual review, not B4a."""
    product = _make_product(verified_cert_programs=[_label("Labdoor Tested")])
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


def test_health_canada_npn_label_zero_b4a(scorer: SupplementScorer) -> None:
    """Health Canada NPN is a regulatory filing, not a purity cert."""
    product = _make_product(verified_cert_programs=[_label("Health Canada NPN")])
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


# --- Diminishing returns + cap on the label_asserted tier -----------------


def test_two_whitelisted_label_certs_diminish_to_3(scorer: SupplementScorer) -> None:
    """USP + Informed Choice both on the label → 2 + 1 = 3 (hits cap)."""
    product = _make_product(
        verified_cert_programs=[
            _label("USP Verified"),
            _label("Informed Choice"),
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 3.0


def test_three_whitelisted_label_certs_clamp_at_3(scorer: SupplementScorer) -> None:
    """Three label-asserted: 2 + 1 + 0 = 3. Third rung is intentionally 0
    so stacking can't push provisional credit past the cap."""
    product = _make_product(
        verified_cert_programs=[
            _label("USP Verified"),
            _label("Informed Choice"),
            _label("Informed Sport"),
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 3.0


# --- Stacking with sku/product_line (overall cap still wins) --------------


def test_sku_plus_label_asserted_stacks_with_overall_cap(scorer: SupplementScorer) -> None:
    """1 SKU verified (NSF Sport, 8) + 1 label_asserted (USP, 2) = 10 B4a.
    Mixing tiers is allowed; overall cap stays 12."""
    product = _make_product(
        verified_cert_programs=[
            {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"},
            _label("USP Verified"),
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 10.0
    assert result["_verified_scope_counts"] == {"sku": 1, "label_asserted_product": 1}


def test_two_sku_plus_label_asserted_clamps_to_12(scorer: SupplementScorer) -> None:
    """2 SKU verified (8 + 4 = 12) + 1 label_asserted (2) = 14 raw → clamp 12.
    The provisional tier can't break the overall B4a cap."""
    product = _make_product(
        verified_cert_programs=[
            {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"},
            {"program": "NSF Certified", "scope": "sku", "recency_status": "fresh"},
            _label("USP Verified"),
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 12.0


def test_duplicate_label_asserted_same_program_counts_once(scorer: SupplementScorer) -> None:
    """Duplicate evidence for the same product-label program must not climb
    the provisional rung ladder. USP from label_certifications + rules_db is
    still one USP claim: +2, not +3."""
    product = _make_product(
        verified_cert_programs=[
            _label("USP Verified"),
            _label("USP Verified"),
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 2.0
    assert result["_verified_scope_counts"] == {"label_asserted_product": 1}


def test_duplicate_program_keeps_strongest_scope(scorer: SupplementScorer) -> None:
    """If a program appears as both SKU-verified and label-asserted, the SKU
    verification wins and the duplicate label assertion contributes nothing."""
    product = _make_product(
        verified_cert_programs=[
            {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"},
            {
                "program": "NSF Sport",
                "scope": "label_asserted_product",
                "evidence_source": "product_label",
                "recency_status": "fresh",
            },
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 8.0
    assert result["_verified_scope_counts"] == {"sku": 1}
