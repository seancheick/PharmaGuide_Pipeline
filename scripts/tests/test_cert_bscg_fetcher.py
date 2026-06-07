"""BSCG Certified Drug Free registry fetcher (parser) tests.

Tests the pure ``parse_bscg_products_payload`` against a fixture payload shaped
like the live POST /selected_program response — no network. Locks: program-code
filtering (keep '1' Certified Drug Free, drop CBD/animal), lot aggregation to one
SKU record, most-recent report date, slug-derived source URL, and schema parity
with the other registry programs.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.verify_certifications import parse_bscg_products_payload  # noqa: E402

SNAPSHOT = "2026-06-07"

# Two lots of the same product (program '1'), one multi-program ('1,2') product,
# and two non-Certified-Drug-Free rows (CBD '4', animal '5') that must be dropped.
BSCG_SAMPLE_PAYLOAD = [
    {
        "product_id": "10", "company": "Acme Labs", "company_slug": "acme-labs",
        "product": "Pre-Workout Fuel", "product_slug": "pre-workout-fuel",
        "product_lot": "LOT-A1", "program": "1", "category": "Pre-Workout",
        "countries_sold": "United States", "report_date": "30 July 2022",
    },
    {
        "product_id": "10", "company": "Acme Labs", "company_slug": "acme-labs",
        "product": "Pre-Workout Fuel", "product_slug": "pre-workout-fuel",
        "product_lot": "LOT-A2", "program": "1", "category": "Pre-Workout",
        "countries_sold": "Canada", "report_date": "15 March 2024",
    },
    {
        "product_id": "22", "company": "Beta Nutrition", "company_slug": "beta-nutrition",
        "product": "Omega Boost", "product_slug": "omega-boost",
        "product_lot": "B-900", "program": "1,2", "category": "Omega-3",
        "countries_sold": "United States", "report_date": "01 January 2025",
    },
    {
        "product_id": "33", "company": "Hemp Co", "company_slug": "hemp-co",
        "product": "CBD Tincture", "product_slug": "cbd-tincture",
        "product_lot": "C-1", "program": "4", "report_date": "01 June 2025",
    },
    {
        "product_id": "44", "company": "Paws Inc", "company_slug": "paws-inc",
        "product": "Dog Joint Chews", "product_slug": "dog-joint-chews",
        "product_lot": "D-1", "program": "5", "report_date": "01 June 2025",
    },
]


def test_parse_bscg_keeps_only_certified_drug_free() -> None:
    records = parse_bscg_products_payload(BSCG_SAMPLE_PAYLOAD, SNAPSHOT)
    products = {r["product"] for r in records}
    assert products == {"Pre-Workout Fuel", "Omega Boost"}  # CBD + animal dropped
    assert all(r["program"] == "BSCG" for r in records)
    assert all(r["scope"] == "sku" for r in records)
    assert all(r["verified_at"] == SNAPSHOT for r in records)
    assert all(r["evidence_band"] == "strong" for r in records)


def test_parse_bscg_aggregates_lots_and_latest_report_date() -> None:
    records = parse_bscg_products_payload(BSCG_SAMPLE_PAYLOAD, SNAPSHOT)
    acme = next(r for r in records if r["product"] == "Pre-Workout Fuel")
    # Two lots collapse into one SKU record carrying both lots.
    assert sorted(acme["lot_numbers_tested"]) == ["LOT-A1", "LOT-A2"]
    # Most-recent report date wins.
    assert acme["report_date"] == "15 March 2024"
    # Countries from both rows are unioned.
    assert acme["countries_sold"] == "Canada; United States"


def test_parse_bscg_source_url_built_from_slugs() -> None:
    records = parse_bscg_products_payload(BSCG_SAMPLE_PAYLOAD, SNAPSHOT)
    acme = next(r for r in records if r["product"] == "Pre-Workout Fuel")
    assert acme["source_url"] == (
        "https://www.bscg.org/certified-drug-free-database/acme-labs/pre-workout-fuel"
    )


def test_parse_bscg_multiprogram_row_counts_as_drug_free() -> None:
    records = parse_bscg_products_payload(BSCG_SAMPLE_PAYLOAD, SNAPSHOT)
    # 'program': '1,2' includes Certified Drug Free, so it is kept.
    assert any(r["product"] == "Omega Boost" for r in records)


def test_parse_bscg_record_has_required_registry_fields() -> None:
    records = parse_bscg_products_payload(BSCG_SAMPLE_PAYLOAD, SNAPSHOT)
    required = {
        "record_id", "program", "brand", "product", "brand_normalized",
        "product_normalized", "scope", "lot_numbers_tested", "verified_at",
        "source_url", "evidence_band",
    }
    for r in records:
        assert required <= set(r), f"missing fields: {required - set(r)}"
        assert r["record_id"].startswith("BSCG_")
