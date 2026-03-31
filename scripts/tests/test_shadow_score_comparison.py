#!/usr/bin/env python3

from pathlib import Path

import pytest

from shadow_score_comparison import validate_shadow_pair


def test_validate_shadow_pair_rejects_identical_inputs():
    with pytest.raises(ValueError, match="identical"):
        validate_shadow_pair("score_supplements.py", "score_supplements.py")


def test_validate_shadow_pair_accepts_distinct_modules(tmp_path):
    baseline = tmp_path / "baseline.py"
    candidate = tmp_path / "candidate.py"
    baseline.write_text("class SupplementScorer:\n    pass\n")
    candidate.write_text("class SupplementScorer:\n    pass\n")

    baseline_path, candidate_path = validate_shadow_pair(str(baseline), str(candidate))
    assert baseline_path == Path(baseline)
    assert candidate_path == Path(candidate)
