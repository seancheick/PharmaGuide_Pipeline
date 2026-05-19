"""P0.1b regression tests — cert overcredit integrity fix.

These tests directly exercise the B4a math by constructing minimal product
dicts with the new `verified_cert_programs` field. They do NOT depend on
the on-disk registry, the enricher, or the full pipeline — just the
scorer's `_compute_certifications_bonus()` and the new scope-aware
diminishing-returns rule.

Four contract tests, mapped 1:1 to Sean's P0.1b approval criteria:

  1. Thorne Mg: NSF Sport (sku) + NSF Certified (sku) → 12 B4a (8 + 4),
     NOT the v3 stacked 15.
  2. Thorne Basic Prenatal: NSF Sport (brand_only) only → 0 B4a, NOT
     the v3 manufacturer-injection-inflated 15.
  3. Stale registry: scoring_blocked_reason set → 0 B4a even on sku
     matches (recency gate).
  4. needs_review: 0 B4a until a reviewer confirms via the override file.
"""

from __future__ import annotations

import json
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
    """Construct a scorer with the default config so the v4 B4a code runs."""
    return SupplementScorer()


def _make_product(
    verified_cert_programs=None,
    third_party_programs=None,
    gmp_level=None,
    has_coa=False,
    has_batch_lookup=False,
    ingredients=None,
):
    """Minimal product dict the scorer expects."""
    return {
        "verified_cert_programs": verified_cert_programs or [],
        "certification_data": {
            "third_party_programs": {"programs": third_party_programs or []},
            "gmp": {},
            "batch_traceability": {
                "has_coa": has_coa,
                "has_batch_lookup": has_batch_lookup,
            },
        },
        "gmp_level": gmp_level,
        "has_coa": has_coa,
        "has_batch_lookup": has_batch_lookup,
        "ingredients": ingredients or [],
    }


# --- Test 1: Thorne Mg pattern ---------------------------------------------


def test_thorne_mg_two_sku_verified_certs_equals_12_not_15(scorer: SupplementScorer) -> None:
    """Thorne Mg Bisglycinate matches BOTH NSF Sport AND NSF/ANSI 173 in the
    live registry. Each scores 8 + 4 = 12 under v4 diminishing returns.

    Critical: this MUST be 12, not the v3 stacked 15 (which counted each
    cert at flat +5 with no diminishing returns)."""
    product = _make_product(
        verified_cert_programs=[
            {
                "program": "NSF Sport",
                "scope": "sku",
                "match_confidence": 1.0,
                "recency_status": "fresh",
            },
            {
                "program": "NSF Certified",
                "scope": "sku",
                "match_confidence": 1.0,
                "recency_status": "fresh",
            },
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 12.0, f"expected 12 (8 sku + 4 sku), got {result['B4a']}"
    assert result["_verified_scope_counts"] == {"sku": 2}


def test_third_sku_cert_adds_diminishing_2_for_total_14_clamped_to_12(scorer: SupplementScorer) -> None:
    """Three SKU-verified certs: 8 + 4 + 2 = 14 raw, but B4a hard cap is 12.
    Stacking shouldn't bypass the cap."""
    product = _make_product(
        verified_cert_programs=[
            {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"},
            {"program": "NSF Certified", "scope": "sku", "recency_status": "fresh"},
            {"program": "USP Verified", "scope": "sku", "recency_status": "fresh"},
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 12.0, f"hard cap should clamp 14 → 12, got {result['B4a']}"


# --- Test 2: Thorne Basic Prenatal pattern (manufacturer-injection bug) ----


def test_thorne_basic_prenatal_brand_only_resolves_to_zero(scorer: SupplementScorer) -> None:
    """Thorne Basic Prenatal claims NSF Sport on its label/manufacturer
    evidence, BUT the SKU is not in NSF's public registry. v3 awarded +15
    via manufacturer injection. v4 must score 0.

    Resolver returns scope=brand_only for these cases. SCOPE_POINTS["brand_only"]
    is [0,0,0] — points route to manufacturer trust (D), not B4a."""
    product = _make_product(
        verified_cert_programs=[
            {
                "program": "NSF Sport",
                "scope": "brand_only",
                "notes": "brand has cert but this product not in registry",
                "recency_status": "fresh",
            }
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0, f"brand_only must score 0 (was the v3 bug), got {result['B4a']}"


def test_claimed_only_resolves_to_zero(scorer: SupplementScorer) -> None:
    """Claimed cert on the label but no registry hit at all → claimed_only → 0."""
    product = _make_product(
        verified_cert_programs=[
            {"program": "NSF Certified", "scope": "claimed_only", "recency_status": "fresh"}
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


# --- Test 3: Recency gate --------------------------------------------------


def test_stale_registry_blocks_scoring_even_on_sku_match(scorer: SupplementScorer) -> None:
    """A SKU match against a stale (scoring_blocked) registry snapshot must
    NOT grant B4a points. The resolver writes scoring_blocked_reason; the
    scorer must honor it."""
    product = _make_product(
        verified_cert_programs=[
            {
                "program": "NSF Sport",
                "scope": "sku",
                "match_confidence": 1.0,
                "recency_status": "scoring_blocked",
                "scoring_blocked_reason": "snapshot is 1977d old (> 180d audit-only threshold)",
            }
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0, (
        "stale snapshot must block scoring — got "
        f"{result['B4a']}, scope_counts={result['_verified_scope_counts']}"
    )


def test_unknown_recency_blocks_scoring(scorer: SupplementScorer) -> None:
    """Unknown snapshot date → resolver writes scoring_blocked_reason →
    scorer refuses points (conservative)."""
    product = _make_product(
        verified_cert_programs=[
            {
                "program": "NSF Sport",
                "scope": "sku",
                "scoring_blocked_reason": "snapshot date unknown; refresh registry before granting points",
            }
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


# --- Test 4: needs_review zero-points contract -----------------------------


def test_needs_review_resolves_to_zero(scorer: SupplementScorer) -> None:
    """The resolver flags borderline matches as needs_review (e.g., 0.85
    confidence). The scorer awards 0 points until a reviewer confirms via
    the override file (which would flip scope to sku/product_line)."""
    product = _make_product(
        verified_cert_programs=[
            {
                "program": "NSF Sport",
                "scope": "needs_review",
                "match_confidence": 0.86,
                "recency_status": "fresh",
            }
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0, "needs_review must score 0 until reviewed"


def test_mixed_scopes_only_sku_and_product_line_score(scorer: SupplementScorer) -> None:
    """Mix of scopes: one sku (8) + one product_line (6) → 14 raw → clamped to 12.
    needs_review, brand_only, claimed_only contribute 0."""
    product = _make_product(
        verified_cert_programs=[
            {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"},
            {"program": "USP Verified", "scope": "product_line", "recency_status": "fresh"},
            {"program": "Informed Sport", "scope": "needs_review", "recency_status": "fresh"},
            {"program": "IFOS", "scope": "brand_only", "recency_status": "fresh"},
            {"program": "Clean Label Project", "scope": "claimed_only", "recency_status": "fresh"},
        ]
    )
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    # sku 8 + product_line 6 = 14, clamped to B4A_CAP=12
    assert result["B4a"] == 12.0
    assert result["_verified_scope_counts"] == {"sku": 1, "product_line": 1}


# --- Bonus: no certs at all -> 0 -------------------------------------------


def test_no_verified_certs_returns_zero(scorer: SupplementScorer) -> None:
    """A product with empty/missing verified_cert_programs must score 0 B4a."""
    product = _make_product(verified_cert_programs=[])
    result = scorer._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0


def test_missing_verified_field_returns_zero(scorer: SupplementScorer) -> None:
    """Old enrichment output without verified_cert_programs field must NOT
    fall back to the old behavior — must score 0 conservatively. This makes
    re-enrichment a hard dependency for P0.1b deployment."""
    product = {
        # No verified_cert_programs field at all
        "certification_data": {
            "third_party_programs": {
                "programs": [
                    {"name": "NSF Sport"},
                    {"name": "NSF Certified"},
                    {"name": "USP Verified"},
                ]
            },
            "gmp": {},
            "batch_traceability": {},
        },
        "named_cert_programs": ["NSF Sport", "NSF Certified", "USP Verified"],
        "ingredients": [],
    }
    result = SupplementScorer()._compute_certifications_bonus(product, supp_type="generic")
    assert result["B4a"] == 0.0, (
        "scorer must NOT fall back to claimed-only behavior when "
        f"verified_cert_programs is missing — got {result['B4a']}"
    )


def test_scoring_config_documents_scope_aware_b4a_contract() -> None:
    """The config must not silently drift back to the old v3 flat
    `5 points per named program` model. Code owns the current constants, but
    config is what future maintainers read first."""
    cfg = json.loads((SCRIPTS_ROOT / "config" / "scoring_config.json").read_text())
    b4 = cfg["section_B_safety_purity"]["B4_quality_certifications"]

    assert b4["B4a_verified_programs"]["scope_points"] == {
        "sku": [8, 4, 2],
        "product_line": [6, 3, 1],
        "label_asserted_product": [2, 1, 0],
        "brand_only": [0, 0, 0],
        "needs_review": [0, 0, 0],
        "claimed_only": [0, 0, 0],
    }
    assert b4["B4a_verified_programs"]["cap"] == 12
    label_cfg = b4["B4a_verified_programs"]["label_asserted_product"]
    assert label_cfg["evidence_source_required"] == "product_label"
    assert label_cfg["eligible_programs"] == [
        "USP Verified",
        "Informed Choice",
        "Informed Sport",
        "BSCG",
    ]
    assert label_cfg["omega_only_eligible_programs"] == ["IFOS"]
    assert b4["B4a_named_programs"]["points_per_program"] == 0
    assert b4["B4a_named_programs"]["cap"] == 0
