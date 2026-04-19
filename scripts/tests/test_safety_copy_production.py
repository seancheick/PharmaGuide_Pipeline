"""Release-gate tests — run the safety-copy validator against the LIVE
production data files in --strict mode.

Complements test_validate_safety_copy.py, which tests the validator's
logic with synthetic fixtures. This file tests the actual production
JSON in scripts/data/ and fails CI the moment any file drops out of
strict compliance (missing authored field, SCREAM word accidentally
merged, contract violation from a schema bump, etc.).

Each test runs in <50ms. Total add: ~0.3 seconds to the full suite.

Why separate from test_validate_safety_copy.py:
- That file uses injected fixtures and stays green regardless of
  authoring progress on the live data.
- This file fails loudly when production copy regresses, which is
  what we want for the release gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_safety_copy import (  # noqa: E402
    validate_banned_recalled_file,
    validate_depletions_file,
    validate_harmful_additives_file,
    validate_interaction_rules_file,
    validate_manufacturer_violations_file,
    validate_synergy_cluster_file,
)

DATA_DIR = SCRIPTS_DIR / "data"


def _assert_strict_clean(result, label: str) -> None:
    """Helper: fail with every validator error formatted for a human.

    Dumps the full error list (or first 20 if huge) so CI output points
    directly at the offending entry without needing to re-run locally.
    """
    if result.errors:
        preview = "\n".join(f"  - {e}" for e in result.errors[:20])
        more = f"\n  ... and {len(result.errors) - 20} more" if len(result.errors) > 20 else ""
        pytest.fail(
            f"{label}: strict validator reported {len(result.errors)} error(s):\n{preview}{more}"
        )


def test_banned_recalled_production_strict():
    """banned_recalled_ingredients.json must pass strict validation.

    Covers: ban_context enum, safety_warning (50-200 chars), one-liner
    (20-80 chars), adulterant-guardrail rule, contamination_recall
    regulatory-verb rule.
    """
    path = DATA_DIR / "banned_recalled_ingredients.json"
    if not path.exists():
        pytest.skip(f"{path.name} not present in this build")
    r = validate_banned_recalled_file(path, strict=True)
    _assert_strict_clean(r, path.name)


def test_interaction_rules_production_strict():
    """ingredient_interaction_rules.json must pass strict validation.

    Covers: alert_headline / alert_body / informational_note on every
    severe sub-rule (avoid / contraindicated) and every pregnancy_lactation
    block + non-severe sub-rules after round 2b-full.
    """
    path = DATA_DIR / "ingredient_interaction_rules.json"
    if not path.exists():
        pytest.skip(f"{path.name} not present in this build")
    r = validate_interaction_rules_file(path, strict=True)
    _assert_strict_clean(r, path.name)


def test_depletions_production_strict():
    """medication_depletions.json must pass strict validation.

    Covers: alert_headline, alert_body, acknowledgement_note,
    monitoring_tip_short, adequacy_threshold mutual-exclusion (mcg XOR
    mg, never both), nocebo rules.
    """
    path = DATA_DIR / "medication_depletions.json"
    if not path.exists():
        pytest.skip(f"{path.name} not present in this build")
    r = validate_depletions_file(path, strict=True)
    _assert_strict_clean(r, path.name)


def test_harmful_additives_production_strict():
    """harmful_additives.json must pass strict validation.

    Covers: safety_summary (50-200 chars), safety_summary_one_liner
    (20-80 chars), SCREAM-word block, terminal-punctuation rule.
    """
    path = DATA_DIR / "harmful_additives.json"
    if not path.exists():
        pytest.skip(f"{path.name} not present in this build")
    r = validate_harmful_additives_file(path, strict=True)
    _assert_strict_clean(r, path.name)


def test_synergy_production_strict():
    """synergy_cluster.json must pass strict validation.

    Covers: synergy_benefit_short (40-160 chars), no alarm/nocebo words
    (synergy is positive messaging), no SCREAM words.
    """
    path = DATA_DIR / "synergy_cluster.json"
    if not path.exists():
        pytest.skip(f"{path.name} not present in this build")
    r = validate_synergy_cluster_file(path, strict=True)
    _assert_strict_clean(r, path.name)


def test_manufacturer_violations_production_strict():
    """manufacturer_violations.json must pass strict validation.

    Covers: brand_trust_summary (40-120 chars), terminal punctuation,
    no semicolons, SCREAM-word block. Alarming adjectives are OK here
    — serious recalls deserve serious voice.
    """
    path = DATA_DIR / "manufacturer_violations.json"
    if not path.exists():
        pytest.skip(f"{path.name} not present in this build")
    r = validate_manufacturer_violations_file(path, strict=True)
    _assert_strict_clean(r, path.name)
