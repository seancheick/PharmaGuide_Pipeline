#!/usr/bin/env python3
"""
Blob ↔ core parity gate.

build_core_row() and build_detail_blob() read the same enriched/scored
inputs but populate different outputs (a positional SQLite row vs. a
nested JSON document). Where the two outputs carry the same logical
field, they must agree — otherwise the app sees one truth from the
SQLite core cache and a different truth from the detail blob fetched
from Supabase.

Fields actually duplicated between blob and core:
  - dsld_id
  - product_name
  - brand_name
  - verdict (blob nests it under audit.gate_audit.verdict)

Cross-source consistency (different shapes, same underlying truth):
  - core.has_banned_substance == 1  ⇔  blob.warnings contains a
    type='banned_substance' entry

Fields the blob does NOT duplicate (queryable scalars; core-only):
  score_quality_80, score_display_100_equivalent, image_url,
  has_recalled_ingredient. Nothing to drift, nothing to assert.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import (  # noqa: E402
    build_core_row,
    build_detail_blob,
)

from test_build_final_db import (  # noqa: E402
    PRODUCTS_CORE_COLUMNS,
    make_enriched,
    make_scored,
    row_as_dict,
)


EXPORTED_AT = "2026-05-14T12:00:00Z"

# Verdicts the gate accepts and ships to the app. NOT_SCORED is excluded
# upstream by the data-integrity gate — testing its parity here would
# duplicate test_final_db_integrity_gate.
SHIPPABLE_VERDICTS = ["SAFE", "CAUTION", "POOR", "BLOCKED", "UNSAFE"]


@pytest.mark.parametrize("verdict", SHIPPABLE_VERDICTS)
def test_blob_and_core_agree_on_identity_fields(verdict):
    """dsld_id, product_name, brand_name must match between blob and core."""
    enriched = make_enriched()
    scored = make_scored(verdict)

    core = row_as_dict(build_core_row(enriched, scored, EXPORTED_AT))
    blob = build_detail_blob(enriched, scored)

    assert blob["dsld_id"] == core["dsld_id"], (
        f"dsld_id drift: blob={blob['dsld_id']!r} core={core['dsld_id']!r}"
    )
    assert blob["product_name"] == core["product_name"], (
        f"product_name drift: blob={blob['product_name']!r} "
        f"core={core['product_name']!r}"
    )
    assert blob["brand_name"] == core["brand_name"], (
        f"brand_name drift: blob={blob['brand_name']!r} "
        f"core={core['brand_name']!r}"
    )


@pytest.mark.parametrize("verdict", SHIPPABLE_VERDICTS)
def test_blob_and_core_agree_on_verdict(verdict):
    """Verdict must match between core.verdict and blob.audit.gate_audit.verdict.

    These are two independent reads of scored["verdict"] — if the
    extraction path diverges (case normalization, default value,
    different lookup), the app's BLOCKED/UNSAFE gating could disagree
    with the detail screen.
    """
    enriched = make_enriched()
    scored = make_scored(verdict)

    core = row_as_dict(build_core_row(enriched, scored, EXPORTED_AT))
    blob = build_detail_blob(enriched, scored)

    blob_verdict = blob.get("audit", {}).get("gate_audit", {}).get("verdict", "")
    # Core normalizes to upper; blob keeps the raw string from scored.
    # Compare case-insensitively — both must resolve to the same verdict.
    assert blob_verdict.upper() == core["verdict"].upper(), (
        f"verdict drift for {verdict}: "
        f"blob.audit.gate_audit.verdict={blob_verdict!r} "
        f"core.verdict={core['verdict']!r}"
    )


def test_banned_warning_in_blob_implies_has_banned_substance_in_core():
    """If blob.warnings carries a banned_substance entry, core flag must be 1.

    Inverse direction (core flag set → blob must have warning) is also
    asserted. Catches the class of bug where the per-ingredient resolver
    flags a banned substance but build_top_warnings() / has_banned_substance()
    disagree on whether to set the core flag.
    """
    enriched = make_enriched()
    # Inject a banned-substance hit on the enriched side. Mirrors the
    # contaminant_data shape build_top_warnings() reads.
    enriched["contaminant_data"] = {
        "banned_substances": {
            "substances": [
                {
                    "name": "Ephedra",
                    "status": "banned",
                    "matched_rule_id": "TEST_BANNED_001",
                }
            ]
        }
    }

    scored = make_scored("BLOCKED")
    core = row_as_dict(build_core_row(enriched, scored, EXPORTED_AT))
    blob = build_detail_blob(enriched, scored)

    blob_has_banned_warning = any(
        isinstance(w, dict) and w.get("type") == "banned_substance"
        for w in blob.get("warnings", [])
    )

    if blob_has_banned_warning:
        assert core["has_banned_substance"] == 1, (
            "blob.warnings has type='banned_substance' but "
            "core.has_banned_substance != 1 — gate skew between "
            "build_top_warnings() and has_banned_substance()"
        )
    if core["has_banned_substance"] == 1:
        assert blob_has_banned_warning, (
            "core.has_banned_substance == 1 but blob.warnings has no "
            "type='banned_substance' entry — user sees the safety flag "
            "but no explanation in the detail screen"
        )


def test_no_banned_signal_keeps_core_flag_zero():
    """Negative control: clean product has neither flag nor warning."""
    enriched = make_enriched()  # contaminant_data.banned_substances = []
    scored = make_scored("SAFE")

    core = row_as_dict(build_core_row(enriched, scored, EXPORTED_AT))
    blob = build_detail_blob(enriched, scored)

    blob_has_banned_warning = any(
        isinstance(w, dict) and w.get("type") == "banned_substance"
        for w in blob.get("warnings", [])
    )
    assert core["has_banned_substance"] == 0
    assert not blob_has_banned_warning


def test_parity_columns_exist_in_products_core_schema():
    """Guard: the parity fields tested above must still exist on the row.

    If a schema change drops one of these columns, the parity assertions
    above would silently key into a non-existent column via row_as_dict
    and pass for the wrong reason. This sentinel makes the dependency
    explicit.
    """
    for col in ("dsld_id", "product_name", "brand_name", "verdict",
                "has_banned_substance"):
        assert col in PRODUCTS_CORE_COLUMNS, (
            f"Parity test relies on core column {col!r} which is no "
            f"longer in PRODUCTS_CORE_COLUMNS — update this test."
        )
