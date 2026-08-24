"""Candidate-artifact support for the pinned release test profile."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "test.sh"
STAMP_PARITY = REPO_ROOT / "scripts" / "tests" / "test_catalog_stamp_parity_release.py"
SOURCE_OF_TRUTH = REPO_ROOT / "scripts" / "tests" / "test_source_of_truth_contract.py"


def _runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_release_profile_accepts_preserved_candidate_root() -> None:
    text = _runner_text()

    assert 'RELEASE_CANDIDATE_ROOT="${PG_RELEASE_CANDIDATE_ROOT:-}"' in text
    assert 'release_artifact_dirs' in text
    assert '"$RELEASE_CANDIDATE_ROOT/dist"' in text
    assert '"$RELEASE_CANDIDATE_ROOT/final_db_output"' in text


def test_candidate_release_uses_candidate_freshness_without_flutter_parity() -> None:
    text = _runner_text()

    assert 'release_preflight_candidate_check' in text
    assert '--skip-interaction-inputs' in text
    assert 'if [[ -z "$RELEASE_CANDIDATE_ROOT" && -d "$FLUTTER_REPO" ]]' in text


def test_candidate_root_must_be_absolute_and_complete() -> None:
    text = _runner_text()

    assert 'PG_RELEASE_CANDIDATE_ROOT must be an absolute path' in text
    assert 'candidate dist/final_db_output pair is incomplete' in text


def test_catalog_stamp_parity_uses_the_shared_release_artifact_resolver() -> None:
    text = STAMP_PARITY.read_text(encoding="utf-8")

    assert "from scripts.release_artifact_paths import catalog_dist_dir" in text
    assert "DIST = catalog_dist_dir()" in text
    assert 'DIST = ROOT / "scripts" / "dist"' not in text


def test_interaction_parity_uses_the_shared_release_artifact_resolver() -> None:
    text = SOURCE_OF_TRUTH.read_text(encoding="utf-8")

    assert "from scripts.release_artifact_paths import catalog_dist_dir" in text
    assert "dist = catalog_dist_dir()" in text
