#!/usr/bin/env python3
"""Copy the canonical RDA/UL artifact into the Flutter bundle.

This is the only supported writer for Flutter's ``rda_optimal_uls.json``.
It validates the canonical stamp and semantic parity before reporting success.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from reference_data_contract import (
    ReferenceDataContractError,
    assert_semantic_parity,
    validate_declared_reference_stamp,
)


DEFAULT_SOURCE = Path(__file__).parent / "data" / "rda_optimal_uls.json"
DESTINATION_RELATIVE_PATH = Path("assets/reference_data/rda_optimal_uls.json")


def _load_canonical(*, source_path: Path) -> tuple[Path, dict[str, Any], dict[str, str]]:
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Canonical RDA/UL artifact not found: {source_path}")
    canonical = json.loads(source_path.read_text(encoding="utf-8"))
    return source_path, canonical, validate_declared_reference_stamp(canonical)


def validate_flutter_reference_data(
    *, source_path: Path, flutter_repo: Path
) -> dict[str, Any]:
    """Semantic parity gate for an already-generated Flutter copy."""
    source_path, canonical, stamp = _load_canonical(source_path=source_path)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    if not destination.is_file():
        raise FileNotFoundError(f"Flutter RDA/UL artifact not found: {destination}")
    copied = json.loads(destination.read_text(encoding="utf-8"))
    assert_semantic_parity(canonical, copied)
    copied_stamp = validate_declared_reference_stamp(copied)
    if copied_stamp != stamp:
        raise ReferenceDataContractError(
            "Flutter RDA/UL reference stamp differs from canonical: "
            f"canonical={stamp}, flutter={copied_stamp}"
        )
    return {**stamp, "source": source_path, "destination": destination}


def sync_reference_data(*, source_path: Path, flutter_repo: Path) -> dict[str, Any]:
    """Validate and byte-copy the canonical RDA/UL artifact into Flutter."""
    source_path, _, _ = _load_canonical(source_path=source_path)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    return validate_flutter_reference_data(source_path=source_path, flutter_repo=flutter_repo)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync the canonical pipeline RDA/UL artifact into Flutter.",
    )
    parser.add_argument(
        "--flutter-repo",
        required=True,
        help="Path to the PharmaGuide Flutter repository.",
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Canonical RDA/UL artifact (default: scripts/data/rda_optimal_uls.json).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate semantic parity without writing the Flutter copy.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    operation = validate_flutter_reference_data if args.check else sync_reference_data
    result = operation(source_path=Path(args.source), flutter_repo=Path(args.flutter_repo))
    verb = "Validated" if args.check else "Synced"
    print(
        f"{verb} RDA/UL reference data: "
        f"version={result['reference_data_version']} "
        f"fingerprint={result['reference_data_fingerprint']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
