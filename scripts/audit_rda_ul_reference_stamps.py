#!/usr/bin/env python3
"""Release gate: every emitted product RDA/UL block uses the canonical stamp."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

from reference_data_contract import (
    ReferenceDataContractError,
    assert_emitted_reference_stamp,
    validate_declared_reference_stamp,
)
from stage_manifest import select_stage_files


DEFAULT_REFERENCE = Path(__file__).parent / "data" / "rda_optimal_uls.json"


def _enriched_files(products_dir: Path) -> Iterator[Path]:
    stage_dirs = products_dir.glob("output_*_enriched/enriched")
    yield from select_stage_files(stage_dirs, "enrich")


def audit_emitted_stamps(*, products_dir: Path, reference_path: Path) -> tuple[int, list[str]]:
    """Audit reference stamps and block unsafe unresolved UL conversions."""
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    expected = validate_declared_reference_stamp(reference)
    checked = 0
    failures: list[str] = []

    for path in _enriched_files(products_dir):
        products = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(products, list):
            raise ReferenceDataContractError(f"enriched batch is not a list: {path}")
        for product in products:
            if not isinstance(product, dict):
                raise ReferenceDataContractError(f"enriched batch contains non-object row: {path}")
            rda_ul_data = product.get("rda_ul_data")
            if not isinstance(rda_ul_data, dict):
                continue
            checked += 1
            product_id = product.get("dsld_id") or product.get("id") or "unknown"
            try:
                assert_emitted_reference_stamp(rda_ul_data, expected)
            except ReferenceDataContractError as error:
                if len(failures) < 20:
                    failures.append(f"{path.name}:{product_id}: {error}")

            rows = (
                rda_ul_data.get("analyzed_ingredients")
                or rda_ul_data.get("ingredients_with_rda")
                or []
            )
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if row.get("skip_ul_reason") != "conversion_failed":
                    continue
                ul_values = (
                    row.get("ul_for_default_profile"),
                    row.get("highest_ul"),
                )
                has_ul = False
                for value in ul_values:
                    try:
                        has_ul = float(value) > 0
                    except (TypeError, ValueError):
                        has_ul = False
                    if has_ul:
                        break
                if has_ul and len(failures) < 20:
                    ingredient = row.get("ingredient") or row.get("standard_name") or "unknown"
                    failures.append(
                        f"{path.name}:{product_id}: {ingredient}: "
                        "conversion_failed for nutrient with established UL"
                    )

    return checked, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-dir", default="scripts/products")
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    args = parser.parse_args()

    checked, failures = audit_emitted_stamps(
        products_dir=Path(args.products_dir),
        reference_path=Path(args.reference),
    )
    if failures:
        print("RDA/UL emitted-reference stamp gate failed:")
        print("\n".join(failures))
        return 1
    print(
        "RDA/UL emitted-reference and conversion-safety gate passed "
        f"for {checked} product blocks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
