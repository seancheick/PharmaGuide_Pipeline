import hashlib
import json
import sqlite3
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from sync_to_supabase import write_share_index  # noqa: E402


def _catalog(path: Path) -> None:
    db = sqlite3.connect(path)
    db.execute(
        """
        CREATE TABLE products_core (
          dsld_id TEXT PRIMARY KEY,
          product_name TEXT NOT NULL,
          brand_name TEXT,
          product_safety_status TEXT,
          quality_assessment_status TEXT,
          quality_score_status TEXT,
          quality_score_v4_100 INTEGER,
          quality_tier TEXT,
          v4_confidence TEXT,
          has_third_party_testing INTEGER,
          is_trusted_manufacturer INTEGER,
          is_vegan INTEGER,
          is_gluten_free INTEGER,
          is_dairy_free INTEGER,
          is_soy_free INTEGER,
          is_organic INTEGER,
          is_non_gmo INTEGER
        )
        """
    )
    rows = [
        (
            "1001",
            "Verified Multi",
            "Example",
            "no_known_catalog_concern",
            "complete",
            "scored",
            91,
            "Excellent",
            "low",
            1,
            1,
            0,
            1,
            0,
            0,
            0,
            0,
        ),
        (
            "1002",
            "Unsafe Product",
            None,
            "blocked",
            "complete",
            "suppressed_safety",
            None,
            None,
            "high",
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
        ),
        (
            "1003",
            "Incomplete Label",
            "Example",
            "no_known_catalog_concern",
            "partial",
            "scored",
            88,
            "Strong",
            "moderate",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ),
    ]
    db.executemany(
        "INSERT INTO products_core VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    db.commit()
    db.close()


def test_share_index_is_canonical_and_preserves_blocked_disposition(tmp_path):
    db_path = tmp_path / "pharmaguide_core.db"
    out_dir = tmp_path / "share_index"
    _catalog(db_path)

    count = write_share_index(
        db_path=str(db_path),
        output_dir=str(out_dir),
        catalog_version="2026.08.13.204005",
    )

    assert count == 3

    def entry(dsld_id):
        shard = hashlib.sha256(dsld_id.encode()).hexdigest()[0]
        payload = json.loads((out_dir / f"{shard}.json").read_text())
        assert payload["schemaVersion"] == 1
        assert payload["catalogVersion"] == "2026.08.13.204005"
        return payload["products"][dsld_id]

    assert sorted(path.name for path in out_dir.glob("*.json")) == [
        f"{shard}.json" for shard in "0123456789abcdef"
    ]
    payload = json.loads(next(out_dir.glob("*.json")).read_text())
    assert payload["schemaVersion"] == 1
    assert payload["catalogVersion"] == "2026.08.13.204005"

    scored = entry("1001")
    assert scored == {
        "productName": "Verified Multi",
        "brandName": "Example",
        "catalogDisposition": "scored",
        "qualityScore": 91,
        "qualityTier": "excellent",
        "confidence": "Limited",
        "highlights": [
            "Third-Party Tested",
            "Trusted Manufacturer",
            "Gluten-Free",
        ],
    }

    blocked = entry("1002")
    assert blocked["catalogDisposition"] == "blocked"
    assert blocked["qualityScore"] is None
    assert blocked["qualityTier"] is None
    assert blocked["confidence"] is None
    assert blocked["highlights"] == []

    partial = entry("1003")
    assert partial["catalogDisposition"] == "not_scored"
    assert partial["qualityScore"] is None
    assert partial["qualityTier"] is None
