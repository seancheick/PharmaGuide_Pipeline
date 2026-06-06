"""P0.1d enrichment tests for provisional label_asserted_product cert scope."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cert_resolver import CertRegistry  # noqa: E402
from cert_resolver import normalize_brand, normalize_product  # noqa: E402
from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


def _enricher_with_registry(registry: CertRegistry) -> SupplementEnricherV3:
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    enricher._cert_registry_cache = registry
    return enricher


def _registry_with_override(override: dict) -> CertRegistry:
    registry = CertRegistry()
    from cert_resolver import normalize_brand, normalize_product

    key = (
        normalize_brand(override.get("brand", "")),
        normalize_product(override.get("product", "")),
    )
    registry.overrides_by_brand_product.setdefault(key, []).append(override)
    return registry


def _product() -> dict:
    return {
        "brandName": "Example Brand",
        "productName": "Example Magnesium",
        "fullName": "Example Brand Example Magnesium",
    }


def test_enricher_emits_label_asserted_for_unscraped_product_label_cert() -> None:
    enricher = _enricher_with_registry(CertRegistry())

    resolved = enricher._resolve_verified_cert_programs(
        product=_product(),
        third_party_programs={
            "programs": [{"name": "USP Verified", "source": "rules_db"}],
        },
        manufacturer_signals=[],
    )

    assert resolved == [
        {
            "program": "USP Verified",
            "scope": "label_asserted_product",
            "evidence_source": "product_label",
            "provisional": True,
            "provisional_reason": "product-level label claim; live scraper not loaded for this program",
            "claim_source": "rules_db",
        }
    ]


def test_enricher_does_not_label_assert_manufacturer_only_cert() -> None:
    enricher = _enricher_with_registry(CertRegistry())

    resolved = enricher._resolve_verified_cert_programs(
        product=_product(),
        third_party_programs={"programs": []},
        manufacturer_signals=[
            {
                "program": "USP Verified",
                "source": "top_manufacturers_data.json",
            }
        ],
    )

    assert resolved == [{"program": "USP Verified", "scope": "claimed_only"}]


def test_enricher_does_not_label_assert_when_live_registry_is_loaded() -> None:
    registry = CertRegistry(
        records_by_program={
            "USP Verified": [
                {
                    "record_id": "USP_OTHER_SKU",
                    "program": "USP Verified",
                    "brand": "Different Brand",
                    "product": "Different Product",
                }
            ]
        }
    )
    enricher = _enricher_with_registry(registry)

    resolved = enricher._resolve_verified_cert_programs(
        product=_product(),
        third_party_programs={
            "programs": [{"name": "USP Verified", "source": "rules_db"}],
        },
        manufacturer_signals=[],
    )

    assert resolved == [{"program": "USP Verified", "scope": "claimed_only"}]


def test_enricher_discovers_registry_sku_cert_without_label_claim() -> None:
    registry = CertRegistry()
    registry.records_by_program["USP Verified"] = [{
        "record_id": "USP_RITUAL_EFW",
        "program": "USP Verified",
        "brand": "Ritual",
        "product": "Ritual Essential for Women Multivitamin 18+",
        "brand_normalized": normalize_brand("Ritual"),
        "product_normalized": normalize_product("Ritual Essential for Women Multivitamin 18+"),
        "_recency_status": "fresh",
        "_snapshot_date": "2026-05-18",
        "_snapshot_age_days": 0,
    }]
    enricher = _enricher_with_registry(registry)

    resolved = enricher._resolve_verified_cert_programs(
        product={
            "brandName": "Ritual",
            "fullName": "Ritual Essential for Women 18+",
        },
        third_party_programs={"programs": []},
        manufacturer_signals=[],
    )

    assert len(resolved) == 1
    assert resolved[0]["program"] == "USP Verified"
    assert resolved[0]["scope"] == "sku"
    assert resolved[0]["record_id"] == "USP_RITUAL_EFW"
    assert "registry_discovered_product_match" in resolved[0]["notes"]


def test_enricher_discovery_ignores_brand_only_registry_presence() -> None:
    registry = CertRegistry()
    registry.records_by_program["USP Verified"] = [{
        "record_id": "USP_RITUAL_PROTEIN",
        "program": "USP Verified",
        "brand": "Ritual",
        "product": "Ritual Essential Protein Daily Shake",
        "brand_normalized": normalize_brand("Ritual"),
        "product_normalized": normalize_product("Ritual Essential Protein Daily Shake"),
        "_recency_status": "fresh",
        "_snapshot_date": "2026-05-18",
        "_snapshot_age_days": 0,
    }]
    enricher = _enricher_with_registry(registry)

    resolved = enricher._resolve_verified_cert_programs(
        product={
            "brandName": "Ritual",
            "fullName": "Ritual Synbiotic+",
        },
        third_party_programs={"programs": []},
        manufacturer_signals=[],
    )

    assert resolved == []


def test_enricher_emits_label_asserted_for_ifos_label_claim() -> None:
    """The scorer later applies the omega-only gate; enrichment preserves the
    product-label IFOS evidence so scorer can decide from ingredients."""
    enricher = _enricher_with_registry(CertRegistry())

    resolved = enricher._resolve_verified_cert_programs(
        product=_product(),
        third_party_programs={
            "programs": [{"name": "IFOS", "source": "label"}],
        },
        manufacturer_signals=[],
    )

    assert resolved[0]["program"] == "IFOS"
    assert resolved[0]["scope"] == "label_asserted_product"
    assert resolved[0]["evidence_source"] == "product_label"


def test_enricher_ifos_label_claim_wins_when_manufacturer_signal_also_exists() -> None:
    """Some omega brands have both product-label IFOS and brand-level IFOS
    evidence. That is not manufacturer-only; preserve the label assertion."""
    enricher = _enricher_with_registry(CertRegistry())

    resolved = enricher._resolve_verified_cert_programs(
        product=_product(),
        third_party_programs={
            "programs": [{"name": "IFOS", "source": "label"}],
        },
        manufacturer_signals=[
            {
                "program": "IFOS",
                "source": "top_manufacturers_data.json",
            }
        ],
    )

    assert resolved[0]["program"] == "IFOS"
    assert resolved[0]["scope"] == "label_asserted_product"
    assert resolved[0]["evidence_source"] == "product_label"


def test_enricher_dedupes_label_and_manufacturer_duplicate_program() -> None:
    """If the same unsupported program is present on the product label and in
    manufacturer evidence, the product-label assertion wins and only one
    resolution is emitted."""
    enricher = _enricher_with_registry(CertRegistry())

    resolved = enricher._resolve_verified_cert_programs(
        product=_product(),
        third_party_programs={
            "programs": [{"name": "USP Verified", "source": "rules_db"}],
        },
        manufacturer_signals=[
            {
                "program": "USP Verified",
                "source": "top_manufacturers_data.json",
            }
        ],
    )

    assert resolved == [
        {
            "program": "USP Verified",
            "scope": "label_asserted_product",
            "evidence_source": "product_label",
            "provisional": True,
            "provisional_reason": "product-level label claim; live scraper not loaded for this program",
            "claim_source": "rules_db",
        }
    ]


def test_enricher_keeps_marine_sustainability_claims_out_of_b4a_scope() -> None:
    enricher = _enricher_with_registry(CertRegistry())

    resolved = enricher._resolve_verified_cert_programs(
        product=_product(),
        third_party_programs={
            "programs": [{"name": "Friend of the Sea", "source": "rules_db"}],
        },
        manufacturer_signals=[],
    )

    assert resolved == [{"program": "Friend of the Sea", "scope": "claimed_only"}]


def test_enricher_passes_dsld_id_to_cert_resolver_for_member_specific_overrides() -> None:
    registry = _registry_with_override({
        "brand": "Nature Made",
        "product": "Vitamin D3 2000 IU",
        "program": "USP Verified",
        "status": "verified",
        "scope": "product_line",
        "record_id": "USP_D3_SOFTGEL",
        "dsld_id": "12154",
    })
    registry.records_by_program["USP Verified"] = [{
        "program": "USP Verified",
        "brand": "Nature Made",
        "product": "Some Other Live Registry Row",
    }]
    enricher = _enricher_with_registry(registry)

    resolved = enricher._resolve_verified_cert_programs(
        product={
            "id": "12154",
            "brandName": "Nature Made",
            "productName": "Vitamin D3 2000 IU",
        },
        third_party_programs={
            "programs": [{"name": "USP Verified", "source": "rules_db"}],
        },
        manufacturer_signals=[],
    )

    assert resolved[0]["scope"] == "product_line"
    assert resolved[0]["record_id"] == "USP_D3_SOFTGEL"

    wrong_product = enricher._resolve_verified_cert_programs(
        product={
            "id": "274365",
            "brandName": "Nature Made",
            "productName": "Vitamin D3 2000 IU",
        },
        third_party_programs={
            "programs": [{"name": "USP Verified", "source": "rules_db"}],
        },
        manufacturer_signals=[],
    )

    assert wrong_product[0]["program"] == "USP Verified"
    assert wrong_product[0]["scope"] == "brand_only"
