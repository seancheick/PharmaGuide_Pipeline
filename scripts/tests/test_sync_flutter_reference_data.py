from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from reference_data_contract import ReferenceDataContractError  # noqa: E402
import sync_flutter_reference_data as sync_mod  # noqa: E402
from sync_flutter_reference_data import (  # noqa: E402
    sync_reference_data,
    validate_flutter_reference_data,
)


def test_sync_replaces_app_copy_with_validated_canonical_artifact(tmp_path: Path) -> None:
    source = Path(__file__).parent.parent / "data" / "rda_optimal_uls.json"
    flutter_repo = tmp_path / "PharmaGuide-ai"
    destination = flutter_repo / "assets" / "reference_data" / "rda_optimal_uls.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"nutrient_recommendations": []}\n')

    with pytest.raises(ReferenceDataContractError, match="semantic fingerprints differ"):
        validate_flutter_reference_data(source_path=source, flutter_repo=flutter_repo)

    result = sync_reference_data(source_path=source, flutter_repo=flutter_repo)

    assert destination.read_bytes() == source.read_bytes()
    assert result["destination"] == destination
    assert result["reference_data_version"] == "5.0.0-2026-06-28"
    assert result["reference_data_fingerprint"].startswith("sha256:")
    assert json.loads(destination.read_text())["_metadata"]["total_entries"] == 77
    validate_flutter_reference_data(source_path=source, flutter_repo=flutter_repo)


def test_sync_product_type_vocab_uses_pipeline_file_as_only_source(tmp_path: Path) -> None:
    assert hasattr(sync_mod, "sync_product_type_vocab")
    assert hasattr(sync_mod, "validate_flutter_product_type_vocab")

    source = Path(__file__).parent.parent / "data" / "product_type_vocab.json"
    flutter_repo = tmp_path / "PharmaGuide-ai"
    destination = flutter_repo / "assets" / "data" / "product_type_vocab.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"product_types": []}\n')

    with pytest.raises(ValueError, match="product-type vocabulary differs"):
        sync_mod.validate_flutter_product_type_vocab(
            source_path=source,
            flutter_repo=flutter_repo,
        )

    result = sync_mod.sync_product_type_vocab(
        source_path=source,
        flutter_repo=flutter_repo,
    )

    assert destination.read_bytes() == source.read_bytes()
    assert result["destination"] == destination
    assert result["schema_version"] == "1.1.0"
    assert result["total_entries"] == 22
    sync_mod.validate_flutter_product_type_vocab(
        source_path=source,
        flutter_repo=flutter_repo,
    )


def test_sync_clinical_taxonomy_uses_pipeline_file_as_only_source(
    tmp_path: Path,
) -> None:
    source = Path(__file__).parent.parent / "data" / "clinical_risk_taxonomy.json"
    flutter_repo = tmp_path / "PharmaGuide-ai"
    destination = (
        flutter_repo / "assets" / "reference_data" / "clinical_risk_taxonomy.json"
    )
    destination.parent.mkdir(parents=True)
    destination.write_text('{"conditions": []}\n')

    with pytest.raises(ValueError, match="clinical-risk taxonomy differs"):
        sync_mod.validate_flutter_clinical_taxonomy(
            source_path=source,
            flutter_repo=flutter_repo,
        )

    result = sync_mod.sync_clinical_taxonomy(
        source_path=source,
        flutter_repo=flutter_repo,
    )

    assert destination.read_bytes() == source.read_bytes()
    assert result["destination"] == destination
    assert result["schema_version"] == "5.3.0"
    assert result["conditions"] == 15
    assert result["profile_flags"] == 8


def test_sync_timing_rules_uses_pipeline_file_as_only_source(
    tmp_path: Path,
) -> None:
    source = Path(__file__).parent.parent / "data" / "timing_rules.json"
    flutter_repo = tmp_path / "PharmaGuide-ai"
    destination = (
        flutter_repo / "assets" / "reference_data" / "timing_rules.json"
    )
    destination.parent.mkdir(parents=True)
    destination.write_text('{"timing_rules": []}\n')

    with pytest.raises(ValueError, match="timing rules differ"):
        sync_mod.validate_flutter_timing_rules(
            source_path=source,
            flutter_repo=flutter_repo,
        )

    result = sync_mod.sync_timing_rules(
        source_path=source,
        flutter_repo=flutter_repo,
    )

    assert destination.read_bytes() == source.read_bytes()
    assert result["destination"] == destination
    assert result["schema_version"] == "5.3.0"
    assert result["total_entries"] == 32
    sync_mod.validate_flutter_timing_rules(
        source_path=source,
        flutter_repo=flutter_repo,
    )
