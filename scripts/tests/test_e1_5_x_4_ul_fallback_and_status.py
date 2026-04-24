"""Sprint E1.5.X-4 tests.

Two behaviors locked down:

1. `rda_ul_data.ingredients_with_rda[*].highest_ul` is ALWAYS populated
   from `rda_optimal_uls.json` when the nutrient exists in the RDA table,
   regardless of whether the pipeline's own UL check was skipped.
   Flutter's anonymous-user UL fallback relies on this contract.

2. `product_status` is a dedicated top-level blob dict field
   ({type, date, display}) — status is no longer emitted into `warnings[]`.
   Flutter renders this as a small neutral concern chip in the "Consider"
   soft-signal layer — not a safety warning and not a SAFE chip.
   Schema uses `type` (not `status`) so the field can grow beyond
   discontinuation (reformulated, limited_availability, seasonal).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_final_db import build_detail_blob  # noqa: E402


# ── Catalog-wide invariant: highest_ul always emitted for known nutrients ──


def _iter_blobs(limit: int = 500):
    """Yield a sample of blobs from scripts/dist/detail_blobs/."""
    blob_dir = ROOT / "scripts" / "dist" / "detail_blobs"
    if not blob_dir.exists():
        pytest.skip("dist/detail_blobs not present — run rebuild first")
    count = 0
    for path in sorted(blob_dir.glob("*.json")):
        try:
            with path.open() as f:
                yield json.load(f)
        except Exception:
            continue
        count += 1
        if count >= limit:
            break


def test_highest_ul_populated_for_ul_defined_nutrients() -> None:
    """Every rda_ul_data entry for a nutrient that HAS a UL defined in
    `rda_optimal_uls.json` must carry that numeric `highest_ul` value.

    Some nutrients legitimately have `highest_ul: null` in the RDA file
    (B12, Biotin, Thiamin, Riboflavin, Vitamin K, Chromium) because the
    IOM/NASEM has set no tolerable upper limit — those are not toxic at
    supplemental doses. The test must NOT penalize those.

    Contract: for nutrients where the RDA source has a numeric UL, the
    blob must carry the same number. Nullifying `highest_ul` post-hoc
    because the pipeline's own UL check was skipped (pre-E1.5.X-4 bug)
    was what broke Flutter's fallback.
    """
    # Nutrients with numeric highest_ul in the RDA source file
    # (scripts/data/rda_optimal_uls.json). Values copied exactly from the
    # source — DO NOT adjust from memory, verify against the file when
    # changing. Names match the blob's `standard_name` field (which the
    # calculator normalizes — some differ from the RDA file's bare form,
    # e.g. "Folate" in file vs "Vitamin B9 (Folate)" in blob).
    UL_DEFINED = {
        "Vitamin A": 3000,                  # mcg RAE
        "Vitamin D": 100,                   # mcg
        "Vitamin E": 1000,                  # mg
        "Vitamin C": 2000,                  # mg
        "Calcium": 3000,                    # mg (max across groups — ages 9-18)
        "Magnesium": 350,                   # mg (supplemental only)
        "Zinc": 40,                         # mg
        "Vitamin B6 (Pyridoxine)": 100,     # mg
        "Vitamin B9 (Folate)": 1667,        # mcg DFE (1,000 mcg DFE ÷ 0.6 bioequivalence)
        "Vitamin B3 (Niacin)": 35,          # mg (supplemental)
    }

    expected_values_seen = {name: 0 for name in UL_DEFINED}
    expected_values_mismatch: list[tuple[str, str, float]] = []
    for blob in _iter_blobs(limit=500):
        for entry in (blob.get("rda_ul_data") or {}).get(
            "ingredients_with_rda", []
        ):
            std_name = entry.get("standard_name")
            if std_name in UL_DEFINED:
                expected = UL_DEFINED[std_name]
                actual = entry.get("highest_ul")
                if actual != expected:
                    expected_values_mismatch.append(
                        (blob.get("dsld_id"), std_name, actual)
                    )
                else:
                    expected_values_seen[std_name] += 1

    # Every UL-defined nutrient we sampled must have no mismatches.
    assert not expected_values_mismatch, (
        f"highest_ul mismatch on {len(expected_values_mismatch)} entries "
        f"where the RDA file has a numeric UL: "
        f"{expected_values_mismatch[:5]}. Flutter fallback broken."
    )

    # Sanity: we should have hit at least a few of these common nutrients
    # across a 500-blob sample. If none, the sample itself is wrong.
    total_hits = sum(expected_values_seen.values())
    assert total_hits > 100, (
        f"only {total_hits} sightings of well-known UL-defined nutrients "
        f"in 500 blobs — test sample or classifier broken: "
        f"{expected_values_seen}"
    )


def test_blob_ul_for_default_profile_is_separate_field() -> None:
    """`ul_for_default_profile` exists as a distinct field from `highest_ul`
    so consumers can tell profile-specific UL from conservative absolute UL."""
    found = False
    for blob in _iter_blobs(limit=200):
        for entry in (blob.get("rda_ul_data") or {}).get(
            "ingredients_with_rda", []
        ):
            if "ul_for_default_profile" in entry:
                found = True
                # Can be None (when skip_ul_check) but field must exist
                break
        if found:
            break
    assert found, (
        "no blob entry carried ul_for_default_profile field — E1.5.X-4 "
        "split didn't emit"
    )


# ── product_status_detail top-level + not in warnings[] ──


def _minimal_enriched(status: str | None = None, disc_date: str | None = None):
    return {
        "dsld_id": "TEST-99999",
        "product_name": "Test Product",
        "status": status,
        "discontinuedDate": disc_date,
        "ingredients": [],
        "raw_actives_count": 0,
        "raw_inactives_count": 0,
        "display_ingredients": [],
    }


def _minimal_scored():
    return {
        "dsld_id": "TEST-99999",
        "section_scores": {},
        "score_80": 0,
        "score_100_equivalent": 0,
    }


def test_discontinued_produces_top_level_product_status_not_warning() -> None:
    """Discontinued products emit top-level `product_status` dict, not a
    warning. Schema: {type, date, display} — `type` (not `status`) for
    forward compatibility with additional non-safety statuses."""
    enriched = _minimal_enriched(status="discontinued", disc_date="2022-12-13")
    blob = build_detail_blob(enriched, _minimal_scored())

    ps = blob.get("product_status")
    assert ps is not None, (
        "discontinued product must emit top-level product_status dict"
    )
    assert ps["type"] == "discontinued"
    assert ps["date"] == "2022-12-13"
    assert "Discontinued" in ps["display"]

    # And critically: NO warning of type='status' in the warnings list.
    for bucket in ("warnings", "warnings_profile_gated"):
        for w in blob.get(bucket, []) or []:
            assert w.get("type") != "status", (
                f"type='status' leaked into {bucket} — must use "
                f"top-level product_status dict instead"
            )


def test_off_market_produces_top_level_product_status_not_warning() -> None:
    enriched = _minimal_enriched(status="off_market")
    blob = build_detail_blob(enriched, _minimal_scored())

    ps = blob.get("product_status")
    assert ps is not None
    assert ps["type"] == "off_market"
    assert "Off-market" in ps["display"]

    for bucket in ("warnings", "warnings_profile_gated"):
        for w in blob.get(bucket, []) or []:
            assert w.get("type") != "status"


def test_active_product_emits_null_product_status() -> None:
    """Active products have product_status = None — Flutter hides the
    chip entirely for these."""
    enriched = _minimal_enriched(status=None)
    blob = build_detail_blob(enriched, _minimal_scored())
    assert blob.get("product_status") is None
