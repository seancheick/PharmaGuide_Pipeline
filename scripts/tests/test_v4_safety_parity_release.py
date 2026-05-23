"""v4 safety parity gate against released artifacts.

Clinical invariant: a product that v3 marks BLOCKED must not become scoreable
or SAFE/POOR in v4 shadow. This catches missing safety-signal propagation
between enrichment, scoring, final DB, and v4 module dispatch.
"""

from __future__ import annotations

import glob
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _load_release_ids() -> set[str]:
    db_path = ROOT / "scripts" / "dist" / "pharmaguide_core.db"
    if not db_path.exists():
        pytest.skip("release DB not present")
    conn = sqlite3.connect(db_path)
    try:
        return {str(row[0]) for row in conn.execute("select dsld_id from products_core")}
    finally:
        conn.close()


def _load_json_records(pattern: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in glob.glob(str(ROOT / pattern)):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for rec in data:
            if not isinstance(rec, dict):
                continue
            dsld_id = str(rec.get("dsld_id") or rec.get("id") or "")
            if dsld_id:
                rows[dsld_id] = rec
    return rows


def test_v3_blocked_release_products_remain_v4_blocked() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    release_ids = _load_release_ids()
    scored = _load_json_records("scripts/products/output_*_scored/scored/*.json")
    enriched = _load_json_records("scripts/products/output_*_enriched/enriched/*.json")

    blocked_ids = sorted(
        dsld_id
        for dsld_id in release_ids
        if (scored.get(dsld_id) or {}).get("verdict") == "BLOCKED"
    )
    assert blocked_ids, "release artifact should contain v3 BLOCKED canaries"

    failures = []
    for dsld_id in blocked_ids:
        product = enriched.get(dsld_id)
        if not product:
            failures.append((dsld_id, "missing enriched blob", None))
            continue
        out = score_product_v4_shadow(product)
        if out.get("shadow_score_v4_verdict") != "BLOCKED":
            failures.append((
                dsld_id,
                product.get("brandName") or product.get("brand_name"),
                product.get("productName") or product.get("product_name") or product.get("fullName"),
                out.get("shadow_score_v4_verdict"),
                out.get("shadow_score_v4_100"),
            ))

    assert failures == []
