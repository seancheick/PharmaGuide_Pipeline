from pathlib import Path

from dataset_paths import brand_dataset_root


def test_brand_dataset_root_defaults_outside_icloud_documents(tmp_path):
    assert brand_dataset_root(environ={}, home=tmp_path) == (
        tmp_path / "Downloads" / "PharmaGuide_Datasets" / "staging" / "brands"
    )


def test_brand_dataset_root_honors_explicit_environment_override(tmp_path):
    override = tmp_path / "verified-local-corpus"

    assert brand_dataset_root(
        environ={"PHARMAGUIDE_DATASET_ROOT": str(override)},
        home=Path("/unused"),
    ) == override
