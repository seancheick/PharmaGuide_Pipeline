"""Corpus invariant: no enriched record derives its daily servings from its
serving size (moved from test_serving_basis_daily_servings.py, 2026-09-29).

It scans every enriched batch (~48 s alone), so it runs in the artifact profile
(scripts/test_profiles.py ARTIFACT_TEST_FILES, run by the release rung with the
heavy timeout); under the fast rung's parallel 120 s cap it timed out.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_serving_basis_daily_servings import serving_frequency_violations

ENRICHED_DIRS = sorted(
    (Path(__file__).parent.parent / "products").glob("output_*_enriched/enriched/*.json")
)


@pytest.mark.skipif(not ENRICHED_DIRS, reason="no enriched output present")
def test_no_enriched_record_derives_frequency_from_serving_size() -> None:
    """Corpus invariant over the stage that actually owns provenance.

    The detail blob keeps only basis_count/basis_unit/min/max, so it cannot be
    audited for provenance — this runs where `basis_reason` and
    `servings_per_day_source` still exist.
    """
    offenders = []
    scanned = 0
    for batch in ENRICHED_DIRS:
        try:
            payload = json.loads(batch.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        records = payload if isinstance(payload, list) else payload.get("products") or []
        if isinstance(records, dict):
            records = list(records.values())
        for record in records:
            if not isinstance(record, dict):
                continue
            scanned += 1
            problems = serving_frequency_violations(record)
            if problems:
                offenders.append((record.get("dsld_id"), problems[0]))

    assert scanned, "no enriched records scanned — the guard would pass vacuously"
    assert not offenders, (
        f"{len(offenders)} of {scanned} enriched records violate the serving-frequency "
        f"invariants; first 5: {offenders[:5]}"
    )
