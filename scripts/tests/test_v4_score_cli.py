"""Fail-closed batch-I/O tests for the v4 Stage-3 CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import score_products_v4  # noqa: E402


def _product(dsld_id: str) -> dict:
    return {
        "dsld_id": dsld_id,
        "product_name": "Empty fixture",
        "ingredient_quality_data": {"ingredients": [], "ingredients_scorable": []},
        "supplement_taxonomy": {
            "primary_type": "general_supplement",
            "percentile_category": "general_supplement",
        },
    }


def test_score_file_atomically_writes_v4_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "enriched_batch_1.json"
    source.write_text(json.dumps([_product("1")]), encoding="utf-8")

    stats = score_products_v4.score_file(source, tmp_path / "scored")

    output = Path(stats["output_file"])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert output.name == "scored_batch_1.json"
    assert payload[0]["quality_score_status"] == "not_scored"
    assert payload[0]["score_basis"] == "v4_six_pillar"
    assert list((tmp_path / "scored").glob("*.tmp")) == []


@pytest.mark.parametrize(
    "payload",
    ["{broken", json.dumps({"dsld_id": "1"}), json.dumps([1]), json.dumps([])],
)
def test_bad_batch_never_writes_partial_output(tmp_path: Path, payload: str) -> None:
    source = tmp_path / "enriched_batch_1.json"
    source.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError):
        score_products_v4.score_file(source, tmp_path / "scored")

    assert not (tmp_path / "scored" / "scored_batch_1.json").exists()


def test_duplicate_product_ids_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "enriched_batch_1.json"
    source.write_text(json.dumps([_product("1"), _product("1")]), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate dsld_id"):
        score_products_v4.score_file(source, tmp_path / "scored")

    assert not (tmp_path / "scored" / "scored_batch_1.json").exists()


def test_duplicate_ids_across_input_files_fail_before_any_output(tmp_path: Path) -> None:
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    (enriched / "enriched_batch_1.json").write_text(
        json.dumps([_product("same")]), encoding="utf-8"
    )
    (enriched / "enriched_batch_2.json").write_text(
        json.dumps([_product("same")]), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="duplicate dsld_id across enriched batches"):
        score_products_v4.score_all(enriched, tmp_path / "output")

    assert not (tmp_path / "output" / "scored").exists()
