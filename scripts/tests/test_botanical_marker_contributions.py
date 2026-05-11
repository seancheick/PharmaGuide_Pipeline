"""Regression tests for scripts/data/botanical_marker_contributions.json.

Ensures the data file structure is stable, every value has a citation, and
every citation passes evidence-id provenance checks (USDA_FDC:<id> or
PMID:<id>). Content verification of citations against live APIs lives in
scripts/api_audit/verify_botanical_composition.py — not run here so the test
suite stays offline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DATA_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "botanical_marker_contributions.json"
)

REQUIRED_BOTANICALS = {
    "acerola_cherry",
    "tomato",
    "camu_camu",
    "turmeric",
    "broccoli_sprout",
    "cayenne_pepper",
    "sophora_japonica",
    "horse_chestnut_seed",
    "japanese_knotweed",
}

EXPECTED_MARKER_MAP = {
    "acerola_cherry": "vitamin_c",
    "tomato": "lycopene",
    "camu_camu": "vitamin_c",
    "turmeric": "curcumin",
    "broccoli_sprout": "sulforaphane",
    "cayenne_pepper": "capsaicin",
    "sophora_japonica": "quercetin",
    "horse_chestnut_seed": "aescin",
    "japanese_knotweed": "resveratrol",
}

USDA_FDC_PATTERN = re.compile(r"^USDA_FDC:\d+$")
PMID_PATTERN = re.compile(r"^PMID:\d+$")


@pytest.fixture(scope="module")
def data():
    assert DATA_PATH.exists(), f"{DATA_PATH} missing — run verify_botanical_composition.py --build-baseline"
    with DATA_PATH.open() as f:
        return json.load(f)


def test_metadata_present(data):
    meta = data.get("_metadata") or {}
    assert meta.get("schema_version") == "1.0.0"
    assert meta.get("total_entries", 0) >= len(REQUIRED_BOTANICALS)
    assert any("USDA" in s for s in meta.get("source_authorities", []))
    assert any("PubMed" in s for s in meta.get("source_authorities", []))


def test_all_required_botanicals_present(data):
    botanicals = data.get("botanicals", {})
    missing = REQUIRED_BOTANICALS - set(botanicals.keys())
    assert not missing, f"Missing botanical entries: {missing}"


@pytest.mark.parametrize("botanical_id,expected_marker", sorted(EXPECTED_MARKER_MAP.items()))
def test_botanical_has_expected_marker(data, botanical_id, expected_marker):
    entry = data["botanicals"][botanical_id]
    markers = [c["marker_canonical_id"] for c in entry.get("delivers", [])]
    assert expected_marker in markers, (
        f"{botanical_id} missing {expected_marker} in delivers[] — got {markers}"
    )


@pytest.mark.parametrize("botanical_id", sorted(REQUIRED_BOTANICALS))
def test_every_contribution_has_citation_with_url(data, botanical_id):
    entry = data["botanicals"][botanical_id]
    for contribution in entry.get("delivers", []):
        assert contribution.get("evidence_source"), f"{botanical_id} missing evidence_source"
        assert contribution.get("evidence_url"), f"{botanical_id} missing evidence_url"
        assert contribution.get("evidence_id"), f"{botanical_id} missing evidence_id"
        # Provenance must trace to USDA FDC or PubMed PMID — no hallucinated IDs.
        eid = contribution["evidence_id"]
        assert USDA_FDC_PATTERN.match(eid) or PMID_PATTERN.match(eid), (
            f"{botanical_id} evidence_id {eid!r} is not USDA_FDC:<id> or PMID:<id> — "
            "per critical_no_hallucinated_citations memory all IDs must be content-verifiable."
        )


@pytest.mark.parametrize("botanical_id", sorted(REQUIRED_BOTANICALS))
def test_model_consistency(data, botanical_id):
    entry = data["botanicals"][botanical_id]
    for contribution in entry.get("delivers", []):
        model = contribution.get("model")
        assert model in {"default_contribution", "standardization_required"}, (
            f"{botanical_id} unknown model {model!r}"
        )
        if model == "default_contribution":
            assert contribution.get("default_contribution_mg_per_g") is not None
            assert contribution.get("min_standardization_pct_required") is None
            assert USDA_FDC_PATTERN.match(contribution["evidence_id"]), (
                f"{botanical_id} default_contribution must cite USDA FDC"
            )
        else:  # standardization_required
            pct = contribution.get("min_standardization_pct_required")
            assert pct is not None and pct > 0, (
                f"{botanical_id} standardization_required must have min_standardization_pct_required"
            )
            assert PMID_PATTERN.match(contribution["evidence_id"]), (
                f"{botanical_id} standardization_required must cite PubMed PMID"
            )


def test_no_orphan_botanicals(data):
    """Every botanical in data file is one of the 9 in-scope for identity/bioactivity split."""
    extras = set(data["botanicals"].keys()) - REQUIRED_BOTANICALS
    assert not extras, (
        f"Unexpected botanical entries: {extras}. If adding new entries, update REQUIRED_BOTANICALS "
        "in this test file alongside the data update."
    )
