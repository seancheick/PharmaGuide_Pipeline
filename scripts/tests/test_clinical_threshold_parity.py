#!/usr/bin/env python3
"""Clinical-threshold parity gate: the B7 UL-exceedance threshold.

The Flutter app's PipelineUlVerdict.exceedsUl
(lib/services/stack/stack_nutrient_aggregator.dart) falls back to
`pctUl >= 150.0` to judge a nutrient "over UL" WHEN the pipeline emitted a
percentage but no definitive `over_ul` bool. That 150 mirrors THIS repo's B7
threshold:
  - scripts/scoring_v4/config/quality_score.json
    -> dose_safety_policy.ul_pct_threshold

If they diverge, the app silently applies stale clinical policy for whether a
nutrient reads as over its Upper Limit.

This test pins the pipeline value; the app repo's
test/safety_invariants/clinical_threshold_parity_test.dart pins the identical
value. The two identical pins are the parity contract — neither side can change
the B7 threshold without a visible, reviewed pin bump in both.

(This is the "one brain, no drift" lock for the single genuine clinical
duplication. The app's 50/80/100/200 intake/UL *tier bands* are NOT locked here:
they are app-owned UI classification with no pipeline equivalent — the pipeline
owns the actual UL verdict via `over_ul`, which the app already defers to.)
"""
from __future__ import annotations

import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
QUALITY_SCORE = SCRIPTS / "scoring_v4" / "config" / "quality_score.json"
SCORING_CONFIG = SCRIPTS / "config" / "scoring_config.json"

# Confirmed UL exceedance, as a percent of UL (Dose V4.1 §2.4: exactly 100% is
# not an exceedance). MUST equal pinnedB7UlPctThreshold in the app repo's
# test/safety_invariants/clinical_threshold_parity_test.dart. The 150% zero
# band is Dose scoring policy only and is not the app's "over UL" test.
PINNED_B7_UL_PCT_THRESHOLD = 100.0


def _find_all(obj, key):
    """Recursively collect every value stored under `key` anywhere in obj."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                found.append(v)
            found.extend(_find_all(v, key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_all(item, key))
    return found


def test_quality_score_b7_thresholds_match_pin():
    data = json.loads(QUALITY_SCORE.read_text())
    value = data["dose_safety_ceiling"]["exceeds_above_pct"]
    assert float(value) == PINNED_B7_UL_PCT_THRESHOLD, (
        f"dose_safety_ceiling.exceeds_above_pct={value} != pinned "
        f"{PINNED_B7_UL_PCT_THRESHOLD}.\n"
        "If B7 changed, update this pin AND the app pin "
        "(test/safety_invariants/clinical_threshold_parity_test.dart)."
    )


def test_legacy_scoring_config_cannot_redeclare_b7_policy():
    """The retired /80 config may supply enrichment vocabulary, not v4 B7."""
    data = json.loads(SCORING_CONFIG.read_text())
    blocks = _find_all(data, "B7_dose_safety")
    assert blocks == [], (
        "legacy scoring_config.json redeclared live B7 policy; "
        "quality_score.json must remain the only owner"
    )
