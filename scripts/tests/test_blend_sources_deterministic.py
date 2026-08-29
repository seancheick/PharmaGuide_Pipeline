"""blends[].sources[] must serialize deterministically — proven behaviorally.

Live measurement (2026-08-29, v2026.08.26.141540 vs v2026.08.27.162958):
1,192 of 15,336 product blobs changed hash between the releases, and the
full-population normalization pass attributes the bulk to the ORDER of
``proprietary_blend_detail.blends[].sources[]`` — the union-of-evidence merge
emitted ``list(set(...))``, whose iteration order follows PYTHONHASHSEED.

This test exercises the REAL producer, ``SupplementEnricherV3
._merge_blend_evidence``, in subprocesses under several hash seeds and
requires byte-identical serialized output — not merely that the source text
contains ``sorted``.
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_DRIVER = r"""
import json, sys
sys.path.insert(0, "scripts")
from enrich_supplements_v3 import SupplementEnricherV3

# __init__ loads databases; the merge under test touches none of that state
# on this path (the alias branch is bypassed by an exact dedupe-key match),
# so construct without it.
enricher = object.__new__(SupplementEnricherV3)

detector = [{
    "name": "Performance Blend",
    "total_weight": 500.0,
    "nested_count": 0,
    "sources": ["detector"],
    "source_field": "activeIngredients[2]",
}]
cleaning = [{
    "name": "Performance Blend",
    "total_weight": 500.0,
    "nested_count": 0,
    "sources": ["cleaning"],
    "source_field": "activeIngredients[2]",
}]

merged = enricher._merge_blend_evidence(detector, cleaning)
assert len(merged) == 1, f"expected one merged blend, got {len(merged)}"
print(json.dumps(merged, sort_keys=False, ensure_ascii=False))
"""


def _run_with_seed(seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    result = subprocess.run(
        [sys.executable, "-c", _DRIVER],
        capture_output=True, text=True, cwd=REPO, env=env,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout.strip()


def test_merged_blend_serialization_is_hashseed_independent():
    """The exact defect: under list(set(...)), different PYTHONHASHSEED values
    produced ['detector','cleaning'] vs ['cleaning','detector'] and re-hashed
    the content-addressed blob. The real merge must now emit identical bytes
    under every seed."""
    outputs = {_run_with_seed(seed) for seed in ("0", "1", "42", "31337")}

    assert len(outputs) == 1, (
        f"_merge_blend_evidence output varied across hash seeds:\n{outputs}"
    )
    import json

    merged = json.loads(next(iter(outputs)))
    assert merged[0]["sources"] == ["cleaning", "detector"], (
        "sources must be the sorted union of both evidence channels"
    )
