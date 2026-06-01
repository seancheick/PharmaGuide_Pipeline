"""v4 canary coverage gate.

Locks the canary set in `scripts/data/canary_products.json` against the
shipped catalog so:

  1. Every canary DSLD ID still exists in production (catches catalog
     deletions before they silently shrink test coverage).
  2. Every `primary_class` declared in `_metadata.primary_classes` has at
     least one canary (catches accidental removal of a class).
  3. Every `expected_b5_class` declared in `_metadata.b5_class_routes`
     has at least one canary (catches B5 router class becoming dead).
  4. The canary file's schema is well-formed (every entry has the
     fields the score-delta report + v4 score policy depend on).

These are coverage tests, not behavior tests.  Behavior contracts live
in test_b4a_p01b_integrity, test_b4a_p01d_label_asserted,
test_cert_label_asserted_enrichment, and test_b5_p02_class_aware_opacity.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANARY_PATH = REPO_ROOT / "scripts" / "data" / "canary_products.json"
CORE_DB = REPO_ROOT / "scripts" / "final_db_output" / "pharmaguide_core.db"

REQUIRED_FIELDS = {
    "dsld_id",
    "brand_name",
    "product_name",
    "primary_class",
    "subclass",
    "expected_b5_class",
    "expected_dose_route_v4",
    "edge_cases",
    "v3_shipped_verdict",
    "notes",
}


@pytest.fixture(scope="module")
def canary_doc() -> dict:
    return json.loads(CANARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def shipped_dsld_ids() -> set[str]:
    """Return the set of dsld_ids in the shipped pharmaguide_core.db."""
    if not CORE_DB.exists():
        pytest.skip(f"shipped catalog missing at {CORE_DB}")
    con = sqlite3.connect(CORE_DB)
    try:
        rows = con.execute("SELECT dsld_id FROM products_core").fetchall()
    finally:
        con.close()
    return {str(r[0]) for r in rows if r[0] is not None}


# --- Schema -----------------------------------------------------------------


def test_canary_doc_has_metadata(canary_doc: dict) -> None:
    md = canary_doc.get("_metadata", {})
    assert md.get("schema_version"), "canary file requires _metadata.schema_version"
    assert isinstance(md.get("primary_classes"), list)
    assert isinstance(md.get("b5_class_routes"), list)


def test_canary_doc_has_canaries_list(canary_doc: dict) -> None:
    assert isinstance(canary_doc.get("canaries"), list)
    assert len(canary_doc["canaries"]) >= 20, "canary set should have ≥20 entries"


def test_every_canary_has_required_fields(canary_doc: dict) -> None:
    missing_report: list[tuple[str, set[str]]] = []
    for c in canary_doc["canaries"]:
        missing = REQUIRED_FIELDS - set(c.keys())
        if missing:
            missing_report.append((c.get("dsld_id", "?"), missing))
    assert not missing_report, f"canaries missing required fields: {missing_report}"


def test_no_duplicate_dsld_ids(canary_doc: dict) -> None:
    ids = [c["dsld_id"] for c in canary_doc["canaries"]]
    dups = {i for i in ids if ids.count(i) > 1}
    assert not dups, f"duplicate dsld_ids in canary set: {dups}"


# --- Catalog presence -------------------------------------------------------


def test_every_canary_exists_in_shipped_catalog(
    canary_doc: dict, shipped_dsld_ids: set[str]
) -> None:
    missing = [
        c["dsld_id"]
        for c in canary_doc["canaries"]
        if c["dsld_id"] not in shipped_dsld_ids
    ]
    assert not missing, (
        f"canaries reference DSLD IDs not in shipped catalog: {missing}. "
        f"Either the products were removed from the live catalog or the "
        f"canary entries have stale IDs — fix before merging."
    )


# --- Class coverage ---------------------------------------------------------


def test_every_primary_class_has_at_least_one_canary(canary_doc: dict) -> None:
    declared = set(canary_doc["_metadata"]["primary_classes"])
    represented = {c["primary_class"] for c in canary_doc["canaries"]}
    missing = declared - represented
    assert not missing, (
        f"primary_classes declared in metadata but no canary covers them: {missing}"
    )


def test_no_canary_uses_undeclared_primary_class(canary_doc: dict) -> None:
    declared = set(canary_doc["_metadata"]["primary_classes"])
    used = {c["primary_class"] for c in canary_doc["canaries"]}
    extras = used - declared
    assert not extras, (
        f"canaries use primary_class values not in _metadata.primary_classes: "
        f"{extras}. Add them to metadata or fix the canary."
    )


def test_every_b5_class_route_has_at_least_one_canary(canary_doc: dict) -> None:
    declared = set(canary_doc["_metadata"]["b5_class_routes"])
    represented = {c["expected_b5_class"] for c in canary_doc["canaries"]}
    missing = declared - represented
    assert not missing, (
        f"b5_class_routes declared but no canary exercises them: {missing}"
    )


# --- Edge-case coverage -----------------------------------------------------


def test_p01b_anchor_canary_present(canary_doc: dict) -> None:
    """Thorne Magnesium Bisglycinate is the P0.1b NSF-stacking anchor.
    Removing it breaks the cert overcredit regression story — guard it."""
    ids = {c["dsld_id"] for c in canary_doc["canaries"]}
    assert "298074" in ids, "P0.1b anchor (298074 Thorne Mg) missing from canary set"


def test_p01d_label_asserted_anchors_present(canary_doc: dict) -> None:
    """P0.1d label_asserted_product coverage requires at least one product
    per whitelisted program (USP, Informed Choice, Informed Sport, BSCG)
    plus the omega-only IFOS case."""
    edge_index: dict[str, list[str]] = {}
    for c in canary_doc["canaries"]:
        for e in c.get("edge_cases", []):
            edge_index.setdefault(e, []).append(c["dsld_id"])
    required_anchors = {
        "usp_label_not_in_registry_drops_to_zero_post_scraper",
        "informed_sport_label_p01d_anchor",
        "informed_choice_label_p01d_anchor",
        "bscg_label_asserted_p01d_anchor",
        "ifos_label_asserted_p01d_anchor",
    }
    missing = [a for a in required_anchors if a not in edge_index]
    assert not missing, (
        f"P0.1d label_asserted anchors missing edge_case tags: {missing}"
    )


def test_b5_class_router_disagreement_canaries_present(canary_doc: dict) -> None:
    """At least two canaries should expose the supp_type vs primary_category /
    product-name disagreement so the router fix is testable on real shipped
    products, not just synthetic fixtures."""
    disagreements = [
        c for c in canary_doc["canaries"]
        if any(e.startswith("router_disagreement_") for e in c.get("edge_cases", []))
    ]
    assert len(disagreements) >= 2, (
        f"expected ≥2 router_disagreement_* canaries, found {len(disagreements)}"
    )


def test_blocked_verdict_canaries_present(canary_doc: dict) -> None:
    """Need at least one BLOCKED-verdict canary so v4 work doesn't
    accidentally regress the safety short-circuit."""
    blocked = [
        c for c in canary_doc["canaries"]
        if c.get("v3_shipped_verdict") == "BLOCKED"
    ]
    assert len(blocked) >= 1, "no BLOCKED-verdict canary — safety gate untested on real data"


# --- Shape sanity ----------------------------------------------------------


def test_canary_expected_b5_class_matches_router(canary_doc: dict) -> None:
    """For every canary, the scorer's `_b5_class_for_product` output should
    match the `expected_b5_class` field. This locks the canary file against
    the live scorer router — if either drifts, the test names the dsld_id
    so we know whose expectation is wrong.

    Uses the shipped products_core row (supp_type + primary_category +
    product_name + brand_name) to construct a minimal product fixture.
    The router only inspects those fields, so this is sufficient."""
    import sys, sqlite3
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from score_supplements import SupplementScorer  # noqa: E402

    if not CORE_DB.exists():
        pytest.skip(f"shipped catalog missing at {CORE_DB}")

    scorer = SupplementScorer()
    con = sqlite3.connect(CORE_DB)
    con.row_factory = sqlite3.Row

    mismatches: list[str] = []
    for c in canary_doc["canaries"]:
        row = con.execute(
            "SELECT supplement_type, primary_category, brand_name, product_name, "
            "is_probiotic, contains_probiotics "
            "FROM products_core WHERE dsld_id = ?",
            (c["dsld_id"],),
        ).fetchone()
        if row is None:
            continue  # presence test already covers missing rows
        product = {
            "supplement_type": {"type": row["supplement_type"]} if row["supplement_type"] else {},
            "primary_category": row["primary_category"],
            "brand_name": row["brand_name"],
            "product_name": row["product_name"],
            "fullName": f"{row['brand_name']} {row['product_name']}",
            "is_probiotic": row["is_probiotic"],
            "contains_probiotics": row["contains_probiotics"],
        }
        actual = scorer._b5_class_for_product(product)
        if actual != c["expected_b5_class"]:
            mismatches.append(
                f"{c['dsld_id']} ({c['brand_name']} / {row['product_name'][:50]}): "
                f"expected={c['expected_b5_class']!r} actual={actual!r} "
                f"supp_type={row['supplement_type']!r} primary_category={row['primary_category']!r}"
            )
    con.close()

    assert not mismatches, (
        "canary expected_b5_class disagrees with scorer router on real "
        f"shipped products:\n  " + "\n  ".join(mismatches)
    )


def test_canary_distribution_is_balanced(canary_doc: dict) -> None:
    """Spot-check that no single class hogs the set (>50%) — keeps the
    canary representative rather than coq10-skewed."""
    from collections import Counter
    cls_counts = Counter(c["primary_class"] for c in canary_doc["canaries"])
    total = sum(cls_counts.values())
    biggest = max(cls_counts.values())
    assert biggest / total <= 0.5, (
        f"canary set is class-skewed: largest class has {biggest}/{total} "
        f"({biggest/total:.0%}). Distribution: {dict(cls_counts)}"
    )
