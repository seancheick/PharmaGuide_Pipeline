from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from reference_data_contract import ReferenceDataContractError  # noqa: E402
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
