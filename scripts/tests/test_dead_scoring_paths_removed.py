"""Code that runs on every product but reaches no consumer must not exist.

Two paths were doing exactly that:

``scoring_v4/display_calibration.py`` computed ``v4_display_100`` — a convex
top-band lift over the raw score — for every product on every scoring run. Its
own docstring called it superseded, and Stage 3 discards the value: it is absent
from the scored artifact, from the export, and from the app. It was a config
load and a transform per product in service of nothing.

``sports_dose`` declared a ``stimulant_high_caffeine`` penalty key that was
never populated and always emitted 0.0. A permanently-zero penalty in a shipped
breakdown reads as "checked and clean" when nothing was ever checked.

Neither removal moves a score. These assertions keep them gone.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SCRIPTS = Path(__file__).parent.parent

from score_supplements_v4 import V4_SCORER_KEYS
from scoring_v4.modules.sports_dose import score_dose as score_sports_dose


def test_display_calibration_module_is_gone():
    assert importlib.util.find_spec("scoring_v4.display_calibration") is None


def test_display_calibration_config_is_gone():
    assert not (SCRIPTS / "scoring_v4" / "config" / "display_calibration.json").exists()


def test_scorer_contract_no_longer_advertises_a_display_score():
    assert "v4_display_100" not in V4_SCORER_KEYS


def test_no_production_source_references_the_display_layer():
    """A deleted concept must not survive as a dangling reference.

    Searches TRACKED source only. An earlier version walked the live working
    tree, which made it order-dependent: other tests write generated artifacts
    under ``scripts/`` while this one runs, so it passed alone and failed in the
    full suite. The invariant that actually matters is about committed source,
    and ``git grep`` answers exactly that — deterministically, and without
    seeing anything a test happens to be writing at the time.
    """
    result = subprocess.run(
        ["git", "grep", "--name-only", "-e", "display_calibration", "-e", "v4_display_100",
         "--", "*.py", "*.json", ":!:tests/", ":!:products/"],
        cwd=SCRIPTS, capture_output=True, text=True,
    )
    # git grep exits 1 when there are no matches, which is the passing case.
    assert result.returncode in (0, 1), f"git grep failed: {result.stderr.strip()}"
    offenders = [line for line in result.stdout.splitlines() if line.strip()]
    assert offenders == [], f"dangling display-calibration references: {offenders}"


def test_sports_dose_declares_no_permanently_zero_penalty():
    product = {
        "activeIngredients": [{
            "name": "Creatine Monohydrate",
            "standardName": "Creatine Monohydrate",
            "canonical_id": "creatine_monohydrate",
            "quantity": 5.0,
            "unit": "g",
            "dailyValue": None,
        }],
    }
    penalties = score_sports_dose(product)["penalties"]
    assert "stimulant_high_caffeine" not in penalties
