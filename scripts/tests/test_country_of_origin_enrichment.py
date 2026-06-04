"""country_of_origin enrichment: verified top-manufacturer jurisdiction fallback.

Most labels print no "made in" text and carry no manufacturer-country contact,
so ~78% of products had no country and silently lost the manufacturer-trust
high-standard-region (D4) point even for known USA/EU/CA brands. _extract_country
now falls back to the research-verified `country` of an exact top-manufacturer
match (top_manufacturers_data.json). Unverified manufacturer records carry no
country, so they correctly yield none.

NOTE: this takes effect on the next enrichment pipeline run (country_of_origin is
computed during enrichment from raw label/contact data that is stripped from the
enriched output).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


_NO_SIGNAL_PRODUCT = {"fullName": "Creatine", "labelText": "", "statements": [], "contacts": []}


def test_top_manufacturer_jurisdiction_fills_country_when_label_silent(enricher):
    top = {"found": True, "manufacturer_id": "MANUF_THORNE", "match_type": "exact"}
    out = enricher._extract_country(_NO_SIGNAL_PRODUCT, top)
    assert out["country"] == "USA"
    assert out["detected"] is True
    assert out["high_regulation_country"] is True
    assert out["source"] == "top_manufacturer_jurisdiction"


def test_non_usa_verified_manufacturer_jurisdiction(enricher):
    top = {"found": True, "manufacturer_id": "MANUF_BIOGAIA", "match_type": "exact"}
    out = enricher._extract_country(_NO_SIGNAL_PRODUCT, top)
    assert out["country"] == "Sweden"
    assert out["high_regulation_country"] is True


def test_unverified_top_manufacturer_yields_no_country(enricher):
    # Dolomite is an unverified record (no country) -> no fabricated jurisdiction.
    top = {"found": True, "manufacturer_id": "MANUF_DOLOMITE", "match_type": "exact"}
    out = enricher._extract_country(_NO_SIGNAL_PRODUCT, top)
    assert out["country"] == ""
    assert out["detected"] is False
    assert out["high_regulation_country"] is False


def test_no_manufacturer_match_yields_no_country(enricher):
    out = enricher._extract_country(_NO_SIGNAL_PRODUCT, {"found": False})
    assert out["country"] == ""
    assert out["detected"] is False
    out_none = enricher._extract_country(_NO_SIGNAL_PRODUCT, None)
    assert out_none["country"] == ""


def test_label_made_in_usa_takes_precedence_over_fallback(enricher):
    # An explicit label signal describes the actual product and must win over the
    # manufacturer-jurisdiction fallback.
    product = {"fullName": "X", "labelText": "Proudly Made in USA", "statements": [], "contacts": []}
    top = {"found": True, "manufacturer_id": "MANUF_BIOGAIA", "match_type": "exact"}
    out = enricher._extract_country(product, top)
    assert out["country"] == "USA"
    assert out["source"] == "label_or_contact"
