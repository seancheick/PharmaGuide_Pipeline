#!/usr/bin/env python3
"""Read-only raw DSLD census for alternate-serving duplicate rows."""

from __future__ import annotations

import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _contexts(rows: list[dict]) -> set[tuple]:
    return {
        (
            quantity.get("servingSizeOrder"),
            quantity.get("servingSizeQuantity"),
            _normalized(quantity.get("servingSizeUnit")),
        )
        for row in rows
        if isinstance(row, dict)
        for quantity in row.get("quantity") or []
        if isinstance(quantity, dict)
    }


def _flatten(rows: list[dict]):
    for row in rows:
        if not isinstance(row, dict):
            continue
        yield row
        yield from _flatten(row.get("nestedRows") or [])


def _duplicates(rows: list[dict], *, recursive: bool) -> list[str]:
    selected = _flatten(rows) if recursive else iter(rows)
    counts = Counter(
        _normalized(row.get("name"))
        for row in selected
        if isinstance(row, dict) and _normalized(row.get("name"))
    )
    return sorted(name for name, count in counts.items() if count > 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: census.py /path/to/staging/brands")
    root = Path(sys.argv[1]).expanduser().resolve()
    paths = list(root.rglob("*.json"))
    report = {
        "files_total": len(paths),
        "multi_column": 0,
        "top_duplicate_before": [],
        "top_duplicate_after": [],
        "all_tree_duplicate_before": [],
        "all_tree_duplicate_after": [],
    }
    for path in paths:
        raw = json.loads(path.read_text())
        rows = raw.get("ingredientRows") or []
        by_order: dict[object, set[tuple]] = {}
        for order, size, unit in _contexts(rows):
            by_order.setdefault(order, set()).add((size, unit))
        if not (
            any(len(values) > 1 for values in by_order.values())
            or len(by_order) > 1
        ):
            continue
        report["multi_column"] += 1
        merged = EnhancedDSLDNormalizer._merge_alternate_serving_rows(
            copy.deepcopy(rows), raw.get("servingSizes")
        )
        product_id = str(raw.get("id") or path.stem)
        for key, found in (
            ("top_duplicate_before", _duplicates(rows, recursive=False)),
            ("top_duplicate_after", _duplicates(merged, recursive=False)),
            ("all_tree_duplicate_before", _duplicates(rows, recursive=True)),
            ("all_tree_duplicate_after", _duplicates(merged, recursive=True)),
        ):
            if found:
                report[key].append({"id": product_id, "duplicates": found})
    report["counts"] = {
        key: len(report[key])
        for key in (
            "top_duplicate_before",
            "top_duplicate_after",
            "all_tree_duplicate_before",
            "all_tree_duplicate_after",
        )
    }
    output = Path(__file__).with_name("result.json")
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "files_total": report["files_total"],
        "multi_column": report["multi_column"],
        **report["counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
