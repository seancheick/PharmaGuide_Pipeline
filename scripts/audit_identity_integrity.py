#!/usr/bin/env python3
"""Release gate: every active ingredient ships a resolved, label-faithful identity.

Module-agnostic. The same identity contract is enforced for every v4 scoring
route (``class_for_product`` over ``VALID_CLASSES``), so a source identity error
cannot slip in through any single module. The gate emits one disposition record
per active row and fails the release for:

- an unresolved ``identity_conflict``;
- a ``missing_display_label`` row;
- a resolved (``clean``/``repaired``) row whose authoritative canonical identity
  does not match the repaired label evidence;
- a missing or unrecognized disposition (a Task-2 stamping regression).

Disposition vocabulary and scoreability come from ``identity_integrity``; the
route inventory comes from the v4 router. Neither is duplicated here.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from identity_integrity import IDENTITY_DISPOSITIONS
from scoring_v4.router import VALID_CLASSES, class_for_product

Classifier = Callable[[dict[str, Any]], str]

DEFAULT_PRODUCTS_DIR = "scripts/products"
_FAILURE_CAP = 40


@dataclass(frozen=True)
class DispositionRecord:
    """One audited active row. ``violation is None`` means the row passed."""

    product_id: str
    route: str
    source_path: str
    label_display_name: str | None
    label_display_form: str | None
    supplied_canonical: str | None
    final_canonical: str | None
    disposition: str | None
    scoreable_identity: bool
    rationale: str
    violation: str | None

    @property
    def failed(self) -> bool:
        return self.violation is not None


def _active_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    iqd = product.get("ingredient_quality_data")
    if not isinstance(iqd, dict):
        return []
    rows = iqd.get("ingredients")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _row_violation(row: dict[str, Any]) -> str | None:
    disposition = row.get("identity_disposition")
    if disposition not in IDENTITY_DISPOSITIONS:
        return f"missing_or_invalid_disposition:{disposition!r}"
    if disposition == "identity_conflict":
        return "unresolved_identity_conflict"
    if disposition == "missing_display_label":
        return "missing_display_label"
    # A resolved row must carry the canonical identity the resolver approved from
    # label evidence: the authoritative canonical_id and the post-repair
    # canonical_id_after must agree and be present. taxonomy_only rows are
    # permitted with or without an inferred canonical, so they are not asserted.
    if disposition in ("clean", "repaired"):
        final = row.get("canonical_id_after")
        if not final:
            return "resolved_row_missing_final_canonical"
        if row.get("canonical_id") != final:
            return f"canonical_mismatch_after_repair:{row.get('canonical_id')!r}!={final!r}"
    return None


def audit_product(
    product: dict[str, Any],
    *,
    classify: Classifier = class_for_product,
    source: str = "",
) -> list[DispositionRecord]:
    """Return one DispositionRecord for every active row in ``product``."""
    route = classify(product)
    if route not in VALID_CLASSES:
        route = "generic"
    product_id = str(product.get("dsld_id") or product.get("id") or "unknown")
    records: list[DispositionRecord] = []
    for row in _active_rows(product):
        records.append(
            DispositionRecord(
                product_id=product_id,
                route=route,
                source_path=str(row.get("raw_source_path") or source or ""),
                label_display_name=row.get("label_display_name"),
                label_display_form=row.get("label_display_form"),
                supplied_canonical=row.get("canonical_id_before"),
                final_canonical=row.get("canonical_id_after"),
                disposition=row.get("identity_disposition"),
                scoreable_identity=bool(row.get("scoreable_identity")),
                rationale=str(row.get("identity_resolution_rationale") or ""),
                violation=_row_violation(row),
            )
        )
    return records


def _enriched_files(products_dir: Path) -> Iterator[Path]:
    yield from sorted(products_dir.glob("output_*_enriched/enriched/*.json"))


def audit_enriched_outputs(
    *,
    products_dir: Path | str,
    classify: Classifier = class_for_product,
) -> list[DispositionRecord]:
    """Scan every enriched artifact under ``products_dir``.

    A missing products directory yields no records (an auto-skipped release with
    only an already-gated dist/ artifact must not fail for want of an old
    products directory).
    """
    records: list[DispositionRecord] = []
    for path in _enriched_files(Path(products_dir)):
        products = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(products, list):
            raise ValueError(f"enriched batch is not a list: {path}")
        for product in products:
            if isinstance(product, dict):
                records.extend(audit_product(product, classify=classify, source=path.name))
    return records


def _format_summary(records: list[DispositionRecord]) -> str:
    by_disposition = Counter(r.disposition for r in records)
    by_route = Counter(r.route for r in records)
    lines = [
        f"active rows audited: {len(records)}",
        "dispositions: "
        + ", ".join(f"{k}={v}" for k, v in sorted(by_disposition.items(), key=lambda kv: str(kv[0]))),
        "routes: " + ", ".join(f"{k}={v}" for k, v in sorted(by_route.items())),
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-dir", default=DEFAULT_PRODUCTS_DIR)
    args = parser.parse_args()

    records = audit_enriched_outputs(products_dir=Path(args.products_dir))
    print(_format_summary(records))

    failures = [r for r in records if r.failed]
    if failures:
        failures.sort(key=lambda r: (r.source_path, r.product_id, r.violation or ""))
        print(f"\nidentity integrity gate FAILED: {len(failures)} active row(s) unresolved:")
        for record in failures[:_FAILURE_CAP]:
            print(
                f"  {record.source_path}:{record.product_id} "
                f"[{record.route}] {record.label_display_name!r} -> {record.violation}"
            )
        if len(failures) > _FAILURE_CAP:
            print(f"  ... and {len(failures) - _FAILURE_CAP} more")
        return 1

    print("identity integrity gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
