"""GTIN width contract for the shipped catalog (defect B, 2026-08-24).

Intake (`product_submission_import._is_valid_gtin`) accepts {8,12,13,14}-digit
GTINs; the exporter's `normalize_upc` kept only {12,13}, so an approved EAN-8
or GTIN-14 submission landed with ``upc_sku=""`` — permanently unscannable,
breaking the loop's core promise (rescan the same barcode, find the product).

The amended contract: preserve every valid width VERBATIM (no leading-zero
canonicalization, which silently merges distinct valid GTIN representations),
and surface zero-padding equivalence through the pad-to-14 collision report
instead of destructive normalization.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_final_db import dedup_by_upc, normalize_upc  # noqa: E402
from product_submission_import import _is_valid_gtin  # noqa: E402


def test_every_valid_gtin_width_is_preserved_verbatim():
    cases = {
        "96385074": "96385074",  # EAN-8 (valid check digit)
        "016000275447": "016000275447",  # UPC-A
        "0016000275447": "0016000275447",  # EAN-13 zero-padded form
        "00016000275447": "00016000275447",  # GTIN-14
    }
    for raw, expected in cases.items():
        assert _is_valid_gtin(raw), f"fixture {raw} must be a valid GTIN"
        assert normalize_upc(raw) == expected
        # Formatting characters strip; digits stay verbatim.
        spaced = " ".join([raw[:4], raw[4:]])
        assert normalize_upc(spaced) == expected


def test_no_leading_zero_canonicalization():
    # 13-digit zero-padded and 12-digit forms are DISTINCT stored values;
    # equivalence belongs to the reader's candidate set, not the writer.
    assert normalize_upc("0016000275447") == "0016000275447"
    assert normalize_upc("016000275447") == "016000275447"
    assert normalize_upc("0016000275447") != normalize_upc("016000275447")


def test_invalid_widths_and_garbage_still_blank():
    for bad in ("", None, "1234567", "123456789", "12345678901",
                "123456789012345", "no digits here"):
        assert normalize_upc(bad) == ""


def test_previously_accepted_widths_are_unchanged():
    # Full-corpus safety: for every input the OLD rule accepted (12/13
    # digits), the widened rule returns byte-identical output, so no
    # existing product's stored upc_sku can change on rebuild.
    for raw in ("016000275447", "0016000275447", "12 3456-78901.2"):
        digits = "".join(ch for ch in str(raw) if ch.isdigit())
        if len(digits) in (12, 13):
            assert normalize_upc(raw) == digits


def test_padding_equivalence_collisions_are_reported_not_merged():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "create table products_core (dsld_id text primary key, upc_sku text)"
    )
    rows = [
        ("100", "016000275447"),  # UPC-A
        ("200", "0016000275447"),  # same barcode, EAN-13 form
        ("300", "96385074"),  # EAN-8, no twin
        ("400", "016000275447"),  # exact duplicate of 100 (same width)
    ]
    conn.executemany("insert into products_core values (?, ?)", rows)

    report = dedup_by_upc(conn, detail_index={})

    # Same-width duplicates stay in the existing ambiguous report...
    assert report["ambiguous_upc_groups"] == 1
    # ...while cross-width padding equivalence gets its own report, and
    # nothing is deleted or rewritten.
    assert report["padding_equivalent_upc_groups"] == 1
    group = report["padding_equivalent_groups_sample"][0]
    assert group["upc_pad14"] == "00016000275447"
    assert group["dsld_ids"] == ["100", "200", "400"]
    kept = {
        row[0]: row[1]
        for row in conn.execute(
            "select dsld_id, upc_sku from products_core"
        )
    }
    assert kept == dict(rows)
