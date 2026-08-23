#!/usr/bin/env python3
"""Copy canonical pipeline reference data into the Flutter bundle.

This is the only supported writer for Flutter's canonical reference-data
copies. It validates parity before success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from build_medication_depletions_artifact import (
    _default_content_version,
    build_artifact as _build_depletions_artifact,
)
from reference_data_contract import (
    ReferenceDataContractError,
    assert_semantic_parity,
    validate_declared_reference_stamp,
)


DEFAULT_SOURCE = Path(__file__).parent / "data" / "rda_optimal_uls.json"
DESTINATION_RELATIVE_PATH = Path("assets/reference_data/rda_optimal_uls.json")
DEFAULT_PRODUCT_TYPE_SOURCE = Path(__file__).parent / "data" / "product_type_vocab.json"
PRODUCT_TYPE_DESTINATION_RELATIVE_PATH = Path("assets/data/product_type_vocab.json")
DEFAULT_DEPLETIONS_SOURCE = Path(__file__).parent / "data" / "medication_depletions.json"
DEPLETIONS_DESTINATION_RELATIVE_PATH = Path(
    "assets/reference_data/medication_depletions.json"
)
DEFAULT_CLINICAL_TAXONOMY_SOURCE = (
    Path(__file__).parent / "data" / "clinical_risk_taxonomy.json"
)
CLINICAL_TAXONOMY_DESTINATION_RELATIVE_PATH = Path(
    "assets/reference_data/clinical_risk_taxonomy.json"
)
DEFAULT_TIMING_RULES_SOURCE = Path(__file__).parent / "data" / "timing_rules.json"
TIMING_RULES_DESTINATION_RELATIVE_PATH = Path(
    "assets/reference_data/timing_rules.json"
)
# Only clinician-verified timing guidance may reach a production artifact.
PUBLISHABLE_TIMING_REVIEW_STATES = frozenset({"verified"})
MANIFEST_DESTINATION_RELATIVE_PATH = Path(
    "assets/reference_data/reference_data_manifest.json"
)

# Every artifact this script owns. The manifest below records a SHA-256 for each
# so the FLUTTER repo can detect drift on its own.
#
# Before this existed, parity was enforced only here: running the sync overwrote
# the Flutter copy and then compared it to the source it had just written, which
# always agreed. A hand-edit to the app's copy vanished with no signal, and the
# Flutter repo had no way to notice — it has SHA-256 release gates for the
# catalog and interaction DBs, but none for reference data.
MANIFESTED_ARTIFACTS = (
    DESTINATION_RELATIVE_PATH,
    PRODUCT_TYPE_DESTINATION_RELATIVE_PATH,
    DEPLETIONS_DESTINATION_RELATIVE_PATH,
    CLINICAL_TAXONOMY_DESTINATION_RELATIVE_PATH,
    TIMING_RULES_DESTINATION_RELATIVE_PATH,
)


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_reference_data_manifest(*, flutter_repo: Path) -> dict[str, Any]:
    """Record a SHA-256 for every synced artifact, for the Flutter-side gate."""
    flutter_repo = flutter_repo.resolve()
    entries = {}
    for relative in MANIFESTED_ARTIFACTS:
        target = flutter_repo / relative
        if not target.is_file():
            raise FileNotFoundError(f"Synced artifact missing: {target}")
        entries[relative.as_posix()] = _sha256_of(target)
    manifest = {
        "_comment": (
            "Written by scripts/sync_flutter_reference_data.py. Hand edits to "
            "any listed asset will fail the Flutter reference-data release "
            "gate until the pipeline regenerates this manifest."
        ),
        "artifacts": entries,
    }
    destination = flutter_repo / MANIFEST_DESTINATION_RELATIVE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def validate_reference_data_manifest(*, flutter_repo: Path) -> dict[str, Any]:
    """Fail when a synced artifact no longer matches its recorded hash."""
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / MANIFEST_DESTINATION_RELATIVE_PATH
    if not destination.is_file():
        raise FileNotFoundError(f"Reference-data manifest not found: {destination}")
    manifest = json.loads(destination.read_text(encoding="utf-8"))
    recorded = manifest.get("artifacts")
    if not isinstance(recorded, dict):
        raise ValueError("Reference-data manifest has no artifacts map")
    expected_keys = {relative.as_posix() for relative in MANIFESTED_ARTIFACTS}
    if set(recorded) != expected_keys:
        missing = sorted(expected_keys - set(recorded))
        extra = sorted(set(recorded) - expected_keys)
        raise ValueError(
            f"Reference-data manifest key drift (missing={missing}, extra={extra})"
        )
    for relative, expected_hash in sorted(recorded.items()):
        actual = _sha256_of(flutter_repo / relative)
        if actual != expected_hash:
            raise ValueError(
                f"{relative} does not match its recorded hash "
                f"(expected {expected_hash}, found {actual})"
            )
    return manifest


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


def _load_product_type_vocab(source_path: Path) -> tuple[Path, dict[str, Any]]:
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Canonical product-type vocabulary not found: {source_path}")
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    metadata = payload.get("_metadata")
    entries = payload.get("product_types")
    if not isinstance(metadata, dict) or not isinstance(entries, list):
        raise ValueError("canonical product-type vocabulary has an invalid shape")
    ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    if (
        len(ids) != len(entries)
        or any(not isinstance(item, str) or not item for item in ids)
        or len(set(ids)) != len(ids)
        or metadata.get("total_entries") != len(entries)
    ):
        raise ValueError("canonical product-type vocabulary metadata/IDs are invalid")
    return source_path, payload


def validate_flutter_product_type_vocab(
    *, source_path: Path, flutter_repo: Path
) -> dict[str, Any]:
    """Require the Flutter asset to be the canonical pipeline vocabulary."""
    source_path, canonical = _load_product_type_vocab(source_path)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / PRODUCT_TYPE_DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    if not destination.is_file():
        raise FileNotFoundError(f"Flutter product-type vocabulary not found: {destination}")
    copied = json.loads(destination.read_text(encoding="utf-8"))
    if copied != canonical or destination.read_bytes() != source_path.read_bytes():
        raise ValueError("Flutter product-type vocabulary differs from canonical pipeline source")
    metadata = canonical["_metadata"]
    return {
        "source": source_path,
        "destination": destination,
        "schema_version": metadata["schema_version"],
        "total_entries": metadata["total_entries"],
    }


def sync_product_type_vocab(*, source_path: Path, flutter_repo: Path) -> dict[str, Any]:
    """Validate and byte-copy the canonical product-type vocabulary."""
    source_path, _ = _load_product_type_vocab(source_path)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / PRODUCT_TYPE_DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    return validate_flutter_product_type_vocab(
        source_path=source_path,
        flutter_repo=flutter_repo,
    )


def _load_clinical_taxonomy(source_path: Path) -> tuple[Path, dict[str, Any]]:
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(
            f"Canonical clinical-risk taxonomy not found: {source_path}"
        )
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    metadata = payload.get("_metadata")
    conditions = payload.get("conditions")
    profile_flags = payload.get("profile_flags")
    if not all(
        (
            isinstance(metadata, dict),
            isinstance(conditions, list),
            isinstance(profile_flags, list),
        )
    ):
        raise ValueError("canonical clinical-risk taxonomy has an invalid shape")
    if metadata.get("total_entries") != sum(
        len(value)
        for key, value in payload.items()
        if key != "_metadata" and isinstance(value, list)
    ):
        raise ValueError("canonical clinical-risk taxonomy metadata is stale")
    return source_path, payload


def validate_flutter_clinical_taxonomy(
    *, source_path: Path, flutter_repo: Path
) -> dict[str, Any]:
    """Require Flutter to bundle the canonical pipeline clinical taxonomy."""
    source_path, canonical = _load_clinical_taxonomy(source_path)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / CLINICAL_TAXONOMY_DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    if not destination.is_file():
        raise FileNotFoundError(
            f"Flutter clinical-risk taxonomy not found: {destination}"
        )
    copied = json.loads(destination.read_text(encoding="utf-8"))
    if copied != canonical or destination.read_bytes() != source_path.read_bytes():
        raise ValueError(
            "Flutter clinical-risk taxonomy differs from canonical pipeline source"
        )
    metadata = canonical["_metadata"]
    return {
        "source": source_path,
        "destination": destination,
        "schema_version": metadata["schema_version"],
        "total_entries": metadata["total_entries"],
        "conditions": len(canonical["conditions"]),
        "profile_flags": len(canonical["profile_flags"]),
    }


def sync_clinical_taxonomy(
    *, source_path: Path, flutter_repo: Path
) -> dict[str, Any]:
    """Byte-copy the sole authored clinical-profile taxonomy into Flutter."""
    source_path, _ = _load_clinical_taxonomy(source_path)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / CLINICAL_TAXONOMY_DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    return validate_flutter_clinical_taxonomy(
        source_path=source_path,
        flutter_repo=flutter_repo,
    )


def _load_timing_rules(source_path: Path) -> tuple[Path, dict[str, Any]]:
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(
            f"Canonical timing rules not found: {source_path}"
        )
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    metadata = payload.get("_metadata")
    rules = payload.get("timing_rules")
    if not isinstance(metadata, dict) or not isinstance(rules, list):
        raise ValueError("canonical timing rules have an invalid shape")
    if metadata.get("total_entries") != len(rules):
        raise ValueError("canonical timing-rules metadata is stale")
    return source_path, payload


def publishable_timing_rules(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical timing rules with unreviewed guidance withheld.

    ``timing_evaluation_service`` already indexes only ``review_status:
    verified`` rules, but the asset shipped every rule and relied on the reader
    to hide them. Clinical guidance nobody has signed off should not be inside
    the bundle at all.

    Withheld ids are reported in ``_metadata`` so the remediation backlog stays
    visible rather than vanishing from the artifact.
    """
    rules = payload.get("timing_rules")
    metadata = payload.get("_metadata")
    if not isinstance(rules, list) or not isinstance(metadata, dict):
        raise ValueError("canonical timing rules have an invalid shape")

    kept: list[dict[str, Any]] = []
    withheld_ids: list[str] = []
    withheld_by_status: dict[str, int] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("canonical timing rules contain a non-object rule")
        status = str(rule.get("review_status") or "").strip().lower()
        if status in PUBLISHABLE_TIMING_REVIEW_STATES:
            kept.append(rule)
            continue
        withheld_ids.append(str(rule.get("id") or rule.get("rule_id")))
        withheld_by_status[status or "missing"] = (
            withheld_by_status.get(status or "missing", 0) + 1
        )

    projected_metadata = dict(metadata)
    projected_metadata["total_entries"] = len(kept)
    projected_metadata["withheld_entries"] = len(withheld_ids)
    projected_metadata["withheld_entry_ids"] = sorted(withheld_ids)
    projected_metadata["withheld_by_review_status"] = dict(
        sorted(withheld_by_status.items())
    )
    projected_metadata["publishable_review_states"] = sorted(
        PUBLISHABLE_TIMING_REVIEW_STATES
    )
    return {**payload, "_metadata": projected_metadata, "timing_rules": kept}


def _timing_rules_bytes(projection: dict[str, Any]) -> bytes:
    return (
        json.dumps(projection, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    ).encode("utf-8")


def validate_flutter_timing_rules(
    *, source_path: Path, flutter_repo: Path
) -> dict[str, Any]:
    """Require the app to bundle the published timing-rules projection.

    The parity contract is unchanged in strength -- the destination must equal
    the pipeline's own output byte for byte. What it equals is now the
    publishable projection rather than the raw canonical file, so unreviewed
    guidance cannot reach the bundle and still pass parity.
    """
    source_path, canonical = _load_timing_rules(source_path)
    projection = publishable_timing_rules(canonical)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / TIMING_RULES_DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    if not destination.is_file():
        raise FileNotFoundError(f"Flutter timing rules not found: {destination}")
    if (
        destination.read_bytes() != _timing_rules_bytes(projection)
        or json.loads(destination.read_text(encoding="utf-8")) != projection
    ):
        raise ValueError(
            "Flutter timing rules differ from the published pipeline projection"
        )
    metadata = projection["_metadata"]
    return {
        "source": source_path,
        "destination": destination,
        "schema_version": metadata["schema_version"],
        "total_entries": metadata["total_entries"],
        "withheld_entries": metadata["withheld_entries"],
    }


def sync_timing_rules(
    *, source_path: Path, flutter_repo: Path
) -> dict[str, Any]:
    """Write the published timing-rules projection into Flutter."""
    source_path, canonical = _load_timing_rules(source_path)
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / TIMING_RULES_DESTINATION_RELATIVE_PATH
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_timing_rules_bytes(publishable_timing_rules(canonical)))
    return validate_flutter_timing_rules(
        source_path=source_path,
        flutter_repo=flutter_repo,
    )


def sync_medication_depletions(
    *, source_path: Path, flutter_repo: Path, content_version: str | None = None
) -> dict[str, Any]:
    """Generate the versioned medication-depletions artifact from canonical
    source and write it into Flutter. Unlike the other reference data this asset
    is GENERATED (validated + stamped), not byte-copied — it is the pipeline's
    bundled fallback for the app and replaces the manual copy."""
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(
            f"Canonical medication_depletions not found: {source_path}"
        )
    flutter_repo = flutter_repo.resolve()
    if not flutter_repo.is_dir():
        raise FileNotFoundError(f"Flutter repository not found: {flutter_repo}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    version = content_version or _default_content_version()
    artifact = _build_depletions_artifact(source, content_version=version)
    destination = flutter_repo / DEPLETIONS_DESTINATION_RELATIVE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return validate_flutter_medication_depletions(
        source_path=source_path, flutter_repo=flutter_repo
    )


def validate_flutter_medication_depletions(
    *, source_path: Path, flutter_repo: Path
) -> dict[str, Any]:
    """Require the Flutter copy to match the pipeline-generated artifact by
    content (content_hash + entries), ignoring the release stamp, and to carry
    the full versioned metadata the app validates before activation."""
    source_path = source_path.resolve()
    flutter_repo = flutter_repo.resolve()
    destination = flutter_repo / DEPLETIONS_DESTINATION_RELATIVE_PATH
    if not destination.is_file():
        raise FileNotFoundError(
            f"Flutter medication_depletions artifact not found: {destination}"
        )
    source = json.loads(source_path.read_text(encoding="utf-8"))
    expected = _build_depletions_artifact(source, content_version="validate")
    copied = json.loads(destination.read_text(encoding="utf-8"))
    meta = copied.get("_metadata")
    if not isinstance(meta, dict):
        raise ValueError("Flutter medication_depletions artifact has no _metadata")
    for key in (
        "schema_version",
        "content_version",
        "content_hash",
        "minimum_runtime_contract",
    ):
        if key not in meta:
            raise ValueError(
                f"Flutter medication_depletions artifact missing _metadata.{key}"
            )
    if meta["content_hash"] != expected["_metadata"]["content_hash"]:
        raise ValueError(
            "Flutter medication_depletions content_hash differs from canonical "
            f"(flutter={meta['content_hash']}, "
            f"canonical={expected['_metadata']['content_hash']})"
        )
    if copied.get("depletions") != expected["depletions"]:
        raise ValueError(
            "Flutter medication_depletions entries differ from the canonical "
            "pipeline-generated artifact"
        )
    return {
        "source": source_path,
        "destination": destination,
        "schema_version": meta["schema_version"],
        "content_hash": meta["content_hash"],
        "minimum_runtime_contract": meta["minimum_runtime_contract"],
        "total_entries": meta.get("total_entries"),
    }


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
        "--product-type-source",
        default=str(DEFAULT_PRODUCT_TYPE_SOURCE),
        help="Canonical product-type vocabulary (default: scripts/data/product_type_vocab.json).",
    )
    parser.add_argument(
        "--depletions-source",
        default=str(DEFAULT_DEPLETIONS_SOURCE),
        help="Canonical medication_depletions.json "
        "(default: scripts/data/medication_depletions.json).",
    )
    parser.add_argument(
        "--clinical-taxonomy-source",
        default=str(DEFAULT_CLINICAL_TAXONOMY_SOURCE),
        help="Canonical clinical_risk_taxonomy.json "
        "(default: scripts/data/clinical_risk_taxonomy.json).",
    )
    parser.add_argument(
        "--timing-rules-source",
        default=str(DEFAULT_TIMING_RULES_SOURCE),
        help="Canonical timing_rules.json "
        "(default: scripts/data/timing_rules.json).",
    )
    parser.add_argument(
        "--content-version",
        default=None,
        help="Release stamp for the generated depletions artifact "
        "(default: today's UTC date).",
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
    product_operation = (
        validate_flutter_product_type_vocab if args.check else sync_product_type_vocab
    )
    product_result = product_operation(
        source_path=Path(args.product_type_source),
        flutter_repo=Path(args.flutter_repo),
    )
    taxonomy_operation = (
        validate_flutter_clinical_taxonomy if args.check else sync_clinical_taxonomy
    )
    taxonomy_result = taxonomy_operation(
        source_path=Path(args.clinical_taxonomy_source),
        flutter_repo=Path(args.flutter_repo),
    )
    timing_operation = (
        validate_flutter_timing_rules if args.check else sync_timing_rules
    )
    timing_result = timing_operation(
        source_path=Path(args.timing_rules_source),
        flutter_repo=Path(args.flutter_repo),
    )
    depletion_kwargs: dict[str, Any] = dict(
        source_path=Path(args.depletions_source),
        flutter_repo=Path(args.flutter_repo),
    )
    if args.check:
        depletion_result = validate_flutter_medication_depletions(**depletion_kwargs)
    else:
        depletion_result = sync_medication_depletions(
            **depletion_kwargs, content_version=args.content_version
        )
    if args.check:
        manifest = validate_reference_data_manifest(flutter_repo=Path(args.flutter_repo))
    else:
        manifest = write_reference_data_manifest(flutter_repo=Path(args.flutter_repo))

    verb = "Validated" if args.check else "Synced"
    print(
        f"{verb} RDA/UL reference data: "
        f"version={result['reference_data_version']} "
        f"fingerprint={result['reference_data_fingerprint']}"
    )
    print(
        f"{verb} product-type vocabulary: "
        f"schema={product_result['schema_version']} "
        f"entries={product_result['total_entries']}"
    )
    print(
        f"{verb} medication depletions: "
        f"schema={depletion_result['schema_version']} "
        f"entries={depletion_result['total_entries']} "
        f"contract={depletion_result['minimum_runtime_contract']}"
    )
    print(
        f"{verb} clinical-profile taxonomy: "
        f"schema={taxonomy_result['schema_version']} "
        f"conditions={taxonomy_result['conditions']} "
        f"profile_flags={taxonomy_result['profile_flags']}"
    )
    print(
        f"{verb} timing rules: "
        f"schema={timing_result['schema_version']} "
        f"entries={timing_result['total_entries']}"
    )
    print(f"{verb} reference-data manifest: artifacts={len(manifest['artifacts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
