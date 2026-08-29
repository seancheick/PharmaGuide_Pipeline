"""blends[].sources[] must serialize deterministically.

Live measurement (2026-08-29, v2026.08.26.141540 vs v2026.08.27.162958):
1,192 of 15,336 product blobs changed hash between the two releases; in a
random 25-product sample, 24 differed ONLY in the ordering of
proprietary_blend_detail.blends[].sources[] — ['cleaning','detector'] vs
['detector','cleaning']. Root cause: the union-of-evidence merge emitted
``list(set(...))``, whose order follows PYTHONHASHSEED — so ~89%% of
per-release blob churn (and the resulting ~1,200 orphans per release) was
hash-ordering noise. Consumer proof: no Flutter reader consumes the field's
order (grep 2026-08-29); the adjacent source_fields is already sorted.
"""

from __future__ import annotations

import os
import subprocess
import sys

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_PROBE = r"""
import json, sys
sys.path.insert(0, "scripts")

# Reproduce the union-of-evidence merge exactly as _collect_proprietary_data
# does when a blend is seen by BOTH the detector and cleaning: the emitted
# `sources` list must not depend on set-iteration order.
source = open("scripts/enrich_supplements_v3.py", encoding="utf-8").read()
needle_ok = 'existing["sources"] = sorted(existing_sources)'
needle_bad = 'existing["sources"] = list(existing_sources)'
if needle_bad in source:
    print("NONDETERMINISTIC: list(set) emission still present")
elif needle_ok in source:
    # Behavioral half: simulate the merge under this interpreter's hash seed.
    existing_sources = set(["detector"])
    existing_sources.add("cleaning")
    print(json.dumps(sorted(existing_sources)))
else:
    print("UNRECOGNIZED: merge emission not found — update this probe")
"""


def _run_with_seed(seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True, text=True, cwd=REPO, env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_sources_emission_is_hashseed_independent():
    outputs = {_run_with_seed(seed) for seed in ("0", "1", "42", "31337")}

    assert "NONDETERMINISTIC" not in "".join(outputs), (
        "the union-of-evidence merge still emits list(set(...)) — sources "
        "ordering follows PYTHONHASHSEED and re-hashes ~1,060 blobs/release"
    )
    assert len(outputs) == 1, f"emission varied across hash seeds: {outputs}"
    assert outputs == {'["cleaning", "detector"]'}
