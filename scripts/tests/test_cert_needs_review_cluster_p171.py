"""P1.7.1 — cert needs_review cluster report tests.

Generates a clustered triage report from `verified_cert_programs`
entries with `scope=needs_review` across the enriched catalog.
Clusters by `(program, record_id, matched_brand, matched_product)` —
the registry row that products are matching against — so the triage
operator can see all products claiming the same row and decide as a
group:

  - REJECT (e.g. dose/form mismatches like Nature Made Vit E 200 IU
    claiming the USP Vit E 1000 IU registry row)
  - VERIFY product_line (e.g. GNC AMP Wheybolic flavor variants all
    matching the genuine Informed Choice AMP Wheybolic row)
  - LEAVE pending (legitimately ambiguous; revisit after data clean)

The report is read-only. No scoring math changes; only writes JSON +
markdown artifacts under `scripts/api_audit/reports/`.
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


def _enriched_product(
    *,
    dsld_id: str,
    brand: str = "TestBrand",
    name: str = "Test Product",
    cert_entries: list | None = None,
) -> dict:
    """Minimal enriched product shape used for cert-resolver testing."""
    return {
        "dsld_id": dsld_id,
        "brand_name": brand,
        "product_name": name,
        "verified_cert_programs": cert_entries or [],
    }


# --- Cluster building ----------------------------------------------------


def test_cluster_groups_products_by_registry_row():
    """Two products matching the same (program, record_id) belong in the
    same cluster."""
    from api_audit.cert_needs_review_cluster import build_clusters

    products = [
        _enriched_product(
            dsld_id="A1", brand="GNC", name="AMP Wheybolic Vanilla",
            cert_entries=[{
                "program": "Informed Choice", "scope": "needs_review",
                "record_id": "IC_AMP_WHEYBOLIC_001",
                "matched_brand": "GNC", "matched_product": "AMP Wheybolic",
            }],
        ),
        _enriched_product(
            dsld_id="A2", brand="GNC", name="AMP Wheybolic Chocolate",
            cert_entries=[{
                "program": "Informed Choice", "scope": "needs_review",
                "record_id": "IC_AMP_WHEYBOLIC_001",
                "matched_brand": "GNC", "matched_product": "AMP Wheybolic",
            }],
        ),
    ]
    clusters = build_clusters(products)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["program"] == "Informed Choice"
    assert cluster["record_id"] == "IC_AMP_WHEYBOLIC_001"
    assert len(cluster["members"]) == 2
    assert {m["dsld_id"] for m in cluster["members"]} == {"A1", "A2"}


def test_cluster_separates_distinct_registry_rows():
    """Two products matching different (program, record_id) are in
    different clusters."""
    from api_audit.cert_needs_review_cluster import build_clusters

    products = [
        _enriched_product(
            dsld_id="B1", brand="X", name="Product 1",
            cert_entries=[{
                "program": "USP Verified", "scope": "needs_review",
                "record_id": "USP_A",
                "matched_product": "Different Thing",
            }],
        ),
        _enriched_product(
            dsld_id="B2", brand="X", name="Product 2",
            cert_entries=[{
                "program": "USP Verified", "scope": "needs_review",
                "record_id": "USP_B",
                "matched_product": "Another Thing",
            }],
        ),
    ]
    clusters = build_clusters(products)
    assert len(clusters) == 2


def test_cluster_ignores_scoring_scopes():
    """Only needs_review entries cluster. sku / product_line / brand_only
    are not part of the triage queue."""
    from api_audit.cert_needs_review_cluster import build_clusters

    products = [
        _enriched_product(
            dsld_id="C1",
            cert_entries=[{
                "program": "NSF Sport", "scope": "sku",
                "record_id": "NSF_001",
            }],
        ),
        _enriched_product(
            dsld_id="C2",
            cert_entries=[{
                "program": "NSF Sport", "scope": "brand_only",
                "record_id": "NSF_001",
            }],
        ),
        _enriched_product(
            dsld_id="C3",
            cert_entries=[{
                "program": "NSF Sport", "scope": "needs_review",
                "record_id": "NSF_002",
            }],
        ),
    ]
    clusters = build_clusters(products)
    assert len(clusters) == 1
    assert clusters[0]["record_id"] == "NSF_002"


def test_cluster_skips_stale_needs_review_after_current_override():
    """A curated reject in the current resolver removes stale embedded
    needs_review rows from the triage report."""
    from api_audit.cert_needs_review_cluster import build_clusters
    from cert_resolver import CertRegistry

    registry = CertRegistry(
        overrides_by_brand_product={
            ("nature s bounty", "d3 125 mcg 5000 iu"): [
                {
                    "program": "USP Verified",
                    "status": "rejected",
                    "scope": "claimed_only",
                    "reason": "dose_mismatch",
                    "dsld_id": "240732",
                }
            ]
        }
    )

    products = [
        _enriched_product(
            dsld_id="240732",
            brand="Nature's Bounty",
            name="D3 125 mcg (5000 IU)",
            cert_entries=[{
                "program": "USP Verified", "scope": "needs_review",
                "record_id": "USP_VERIFIED_0604E8F6CA5F",
                "matched_brand": "Nature's Bounty",
                "matched_product": "Nature's Bounty Vitamin D3 125 mcg Softgels",
            }],
        )
    ]

    assert build_clusters(products, registry=registry) == []


def test_cluster_handles_products_with_no_certs():
    """A product with empty verified_cert_programs contributes nothing."""
    from api_audit.cert_needs_review_cluster import build_clusters

    products = [
        _enriched_product(dsld_id="D1", cert_entries=[]),
        _enriched_product(dsld_id="D2"),  # also empty
    ]
    clusters = build_clusters(products)
    assert clusters == []


def test_cluster_groups_by_record_id_even_with_minor_name_drift():
    """Two products with slightly different matched_product strings but
    the same record_id still cluster together — record_id is the strong
    identifier."""
    from api_audit.cert_needs_review_cluster import build_clusters

    products = [
        _enriched_product(
            dsld_id="E1",
            cert_entries=[{
                "program": "USP", "scope": "needs_review",
                "record_id": "USP_VITE_1000",
                "matched_product": "Vitamin E 1000 IU",
            }],
        ),
        _enriched_product(
            dsld_id="E2",
            cert_entries=[{
                "program": "USP", "scope": "needs_review",
                "record_id": "USP_VITE_1000",
                "matched_product": "Vitamin E 1000IU softgel",  # minor drift
            }],
        ),
    ]
    clusters = build_clusters(products)
    assert len(clusters) == 1
    assert len(clusters[0]["members"]) == 2


# --- camelCase / snake_case shape compatibility ------------------------


def test_cluster_reads_camelcase_brand_and_product_fields():
    """Enriched product blobs use `brandName` and `fullName` at the top
    level. Scored blobs use `brand_name` / `product_name`. The cluster
    builder must read both so distinct_brands and per-member display
    fields are populated regardless of which artifact stage we read."""
    from api_audit.cert_needs_review_cluster import build_clusters, summarize

    products = [
        {
            "dsld_id": "CC1",
            "brandName": "GNC",
            "fullName": "AMP Wheybolic Vanilla",
            "verified_cert_programs": [{
                "program": "Informed Choice", "scope": "needs_review",
                "record_id": "IC_001",
                "matched_brand": "GNC", "matched_product": "AMP Wheybolic",
            }],
        },
    ]
    clusters = build_clusters(products)
    assert len(clusters) == 1
    member = clusters[0]["members"][0]
    assert member["brand_name"] == "GNC"
    assert member["product_name"] == "AMP Wheybolic Vanilla"

    summary = summarize(clusters)
    assert summary["distinct_brands"] == 1


# --- Triage hint ---------------------------------------------------------


def test_triage_hint_flags_dose_mismatch_false_positive():
    """A product named 'Vitamin E 200 IU' claiming a registry row for
    'Vitamin E 1000 IU' is a likely false positive — flag for REJECT."""
    from api_audit.cert_needs_review_cluster import classify_member

    member = {
        "dsld_id": "X1",
        "brand_name": "Nature Made",
        "product_name": "Vitamin E 200 IU",
        "matched_brand": "Nature Made",
        "matched_product": "Vitamin E 1000 IU",
    }
    hint = classify_member(member)
    assert hint["likely_action"] == "reject"
    assert "dose_mismatch" in hint["reasons"]


def test_triage_hint_reads_thousands_separators_like_the_resolver():
    """"5,000 mcg" and "5000 Mcg" are one strength. The duplicate dose parser
    read the comma label as 0 mcg and auto-rejected Nature Made Biotin against
    its own USP listing (P1.7.2, 2026-05-20)."""
    from api_audit.cert_needs_review_cluster import classify_member

    hint = classify_member({
        "dsld_id": "179953",
        "brand_name": "Nature Made",
        "product_name": "Maximum Strength Biotin 5,000 mcg",
        "matched_brand": "Nature Made",
        "matched_product": "Nature Made Maximum Strength Biotin 5000 Mcg Softgels",
    })
    assert "dose_mismatch" not in hint["reasons"]


def test_triage_uses_resolver_identity_helpers_not_copies():
    import api_audit.cert_needs_review_cluster as cluster
    import cert_resolver

    for duplicate in ("_DOSE_TOKEN_RE", "_extract_dose_tokens", "_brand_tokens"):
        assert not hasattr(cluster, duplicate), duplicate
    assert cluster._brands_likely_same is cert_resolver._brands_likely_same
    assert cluster._sku_dose_tokens is cert_resolver._sku_dose_tokens


def test_triage_hint_verifies_flavor_variant_match():
    """A product whose name is the registry product + a flavor suffix is
    a likely product_line variant — flag for VERIFY."""
    from api_audit.cert_needs_review_cluster import classify_member

    member = {
        "dsld_id": "X2",
        "brand_name": "GNC",
        "product_name": "AMP Wheybolic Vanilla Cream",
        "matched_brand": "GNC",
        "matched_product": "AMP Wheybolic",
    }
    hint = classify_member(member)
    assert hint["likely_action"] == "verify_product_line"
    assert "flavor_variant" in hint["reasons"]


def test_triage_hint_rejects_brand_name_collision():
    """Brand name fuzz too far from the matched_brand → REJECT."""
    from api_audit.cert_needs_review_cluster import classify_member

    member = {
        "dsld_id": "X3",
        "brand_name": "Nordic Naturals",
        "product_name": "Ultimate Omega",
        "matched_brand": "Naturalis Inc",
        "matched_product": "Some other product",
    }
    hint = classify_member(member)
    assert hint["likely_action"] == "reject"
    assert "brand_mismatch" in hint["reasons"]


def test_triage_hint_neutral_when_no_strong_signal():
    """Genuinely ambiguous cases (brand matches, product is close but
    not obviously dose-mismatch or flavor variant) get no strong hint."""
    from api_audit.cert_needs_review_cluster import classify_member

    member = {
        "dsld_id": "X4",
        "brand_name": "Thorne Research",
        "product_name": "Methylguard Plus",
        "matched_brand": "Thorne Research",
        "matched_product": "Methylguard",
    }
    hint = classify_member(member)
    # Could be either flavor_variant or pending_review — make sure we
    # don't auto-reject ambiguous cases.
    assert hint["likely_action"] != "reject"


# --- Report rendering ----------------------------------------------------


def test_report_writes_json_and_markdown(tmp_path: Path):
    from api_audit.cert_needs_review_cluster import build_clusters, write_reports

    products = [
        _enriched_product(
            dsld_id="R1", brand="GNC", name="AMP Wheybolic Vanilla",
            cert_entries=[{
                "program": "Informed Choice", "scope": "needs_review",
                "record_id": "IC_AMP_001",
                "matched_brand": "GNC", "matched_product": "AMP Wheybolic",
            }],
        ),
    ]
    clusters = build_clusters(products)
    json_path, md_path = write_reports(clusters, tmp_path)

    assert json_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text())
    assert payload["summary"]["cluster_count"] == 1
    assert payload["summary"]["member_count"] == 1
    assert payload["clusters"][0]["program"] == "Informed Choice"


def test_report_summary_counts_match_input():
    from api_audit.cert_needs_review_cluster import build_clusters, summarize

    products = [
        _enriched_product(
            dsld_id=f"P{i}", brand="X",
            cert_entries=[{
                "program": "USP", "scope": "needs_review",
                "record_id": f"USP_{i // 3}",  # 3 distinct record_ids for 9 products
                "matched_brand": "X", "matched_product": f"P{i // 3}",
            }],
        )
        for i in range(9)
    ]
    clusters = build_clusters(products)
    summary = summarize(clusters)
    assert summary["cluster_count"] == 3
    assert summary["member_count"] == 9
    assert summary["distinct_programs"] == 1
    assert summary["distinct_brands"] >= 1


# --- Integration with real catalog data ---------------------------------


def test_cluster_handles_real_catalog_shape_smoke():
    """Smoke: the cluster builder doesn't crash on real enriched blobs
    if any are present on disk."""
    from api_audit.cert_needs_review_cluster import build_clusters, load_enriched_products

    enriched_root = SCRIPTS_ROOT / "products"
    if not enriched_root.exists():
        pytest.skip("no enriched products dir present in this checkout")

    products = list(load_enriched_products(enriched_root, limit=100))
    # Should not crash; clusters may be empty or non-empty.
    clusters = build_clusters(products)
    assert isinstance(clusters, list)
    # Each cluster should have a non-empty members list
    for c in clusters:
        assert len(c["members"]) > 0


# --- Re-evaluation of P1.7.2 auto-rejects (2026-09-16) ------------------
# Read-only: classifies each automatic rejection with the current resolver.
# Nothing is applied; stale rows are reviewed one at a time.


def _auto_reject_registry():
    from cert_resolver import CertRegistry, normalize_brand, normalize_product

    registry = CertRegistry()
    records = [
        ("USP_BIOTIN_5000", "Nature Made Maximum Strength Biotin 5000 Mcg Softgels"),
        ("USP_COQ10_100", "Nature Made CoQ10 100 Mg Softgels"),
        ("USP_COQ10_400", "Nature Made CoQ10 400 Mg Softgels"),
        ("USP_VITE_1000", "Nature Made Vitamin E 1000 IU (450 Mg) Dl-Alpha Softgels"),
    ]
    for record_id, product in records:
        registry.records_by_program.setdefault("USP Verified", []).append({
            "program": "USP Verified", "brand": "Nature Made", "product": product,
            "brand_normalized": normalize_brand("Nature Made"),
            "product_normalized": normalize_product(product), "record_id": record_id,
            "source_url": "https://registry.example/usp-verified",
            "_snapshot_date": "2026-09-16", "_snapshot_age_days": 0, "_recency_status": "fresh",
        })
    overrides = [
        ("179953", "Maximum Strength Biotin 5,000 mcg", "USP_BIOTIN_5000"),
        ("179710", "CoQ10 400 mg", "USP_COQ10_100"),
        ("8750", "Vitamin E 200 IU Supplement", "USP_VITE_1000"),
    ]
    rows = []
    for dsld_id, product, record_id in overrides:
        row = {"brand": "Nature Made", "product": product, "program": "USP Verified",
               "status": "rejected", "scope": "claimed_only", "dsld_id": dsld_id,
               "record_id": record_id, "review_source": "P1.7.2_auto_reject_2026-05-20",
               "triage_reasons": ["dose_mismatch"]}
        rows.append(row)
        key = (normalize_brand("Nature Made"), normalize_product(product))
        registry.overrides_by_brand_product.setdefault(key, []).append(row)
    rows.append({"brand": "Nature Made", "product": "Iron", "program": "USP Verified",
                 "status": "rejected", "record_id": "X", "review_source": "human_review_2026-06-01"})
    products = {
        dsld_id: {"dsld_id": dsld_id, "brandName": "Nature Made", "product_name": product,
                  "netContents": [{"quantity": 60, "unit": "Softgel(s)"}]}
        for dsld_id, product, _ in overrides
    }
    return registry, rows, products


def test_auto_reject_reevaluation_classifies_each_row_without_applying():
    from api_audit.cert_needs_review_cluster import reevaluate_auto_rejects

    registry, overrides, products = _auto_reject_registry()
    before = json.dumps(overrides, sort_keys=True)

    packet = {row["dsld_id"]: row for row in reevaluate_auto_rejects(overrides, products, registry)}

    assert set(packet) == {"179953", "179710", "8750"}  # human review rows are not auto-rejects
    assert packet["179953"]["classification"] == "premise_stale"
    assert packet["179710"]["classification"] == "other_record_now_matches"
    assert packet["179710"]["current_record_id"] == "USP_COQ10_400"
    assert packet["8750"]["classification"] == "still_valid"
    assert json.dumps(overrides, sort_keys=True) == before
