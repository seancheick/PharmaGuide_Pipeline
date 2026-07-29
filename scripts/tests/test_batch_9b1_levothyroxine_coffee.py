"""Batch 9.B.1 regression lock — DSI_LEVOTHYROXINE_COFFEE Minor → Moderate.

Per clinician-authorized scope (2026-05-27):
  - Severity promotion only. Mechanism, management, source_urls, PMIDs,
    and agent identification stay unchanged.
  - The entry was promoted because the timing rule (take levothyroxine
    with water, separate coffee 30–60 min) is a standard endocrinology
    recommendation backed by PMID 18341376 (Benvenga 2008 — 'Altered
    intestinal absorption of L-thyroxine caused by coffee', the
    8-case-series + in vivo/vitro paper). Missing the separation causes
    chronic TSH drift and unnecessary dose escalation — real, common,
    avoidable harm.
  - DSI_SSRI_FISHOIL deprecation and the other 24 Minor entries are
    explicitly out of scope for this batch. They wait for Batch 9.B.2 —
    a schema design proposal for background/deprecated routing — before
    any further data edits.

This test is the policy lock: any future change to severity, PMID, or
class-vs-drug-specific scoping must consciously update this assertion
with a documented clinical reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CURATED_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curated_interactions"
    / "curated_interactions_v1.json"
)


@pytest.fixture(scope="module")
def curated() -> dict:
    return json.loads(CURATED_PATH.read_text())


@pytest.fixture(scope="module")
def coffee_entry(curated) -> dict:
    for e in curated["interactions"]:
        if e["id"] == "DSI_LEVOTHYROXINE_COFFEE":
            return e
    raise AssertionError("curated_interactions_v1.json missing DSI_LEVOTHYROXINE_COFFEE")


def test_severity_is_moderate(coffee_entry):
    """DSI_LEVOTHYROXINE_COFFEE must be at Moderate severity after Batch 9.B.1.
    Was Minor in v1 of curated_interactions_v1.json; promoted because the
    timing rule is a standard endocrinology recommendation with direct
    PubMed-content-verified support (PMID 18341376)."""
    assert coffee_entry["severity"] == "Moderate", (
        "DSI_LEVOTHYROXINE_COFFEE.severity must be 'Moderate' after Wave 9.B.1. "
        "Reverting to Minor would put a well-evidenced standard endocrinology "
        "timing rule back below the user-facing alert bar."
    )


def test_pmid_18341376_retained(coffee_entry):
    """PMID 18341376 is the load-bearing content-verified citation
    (Benvenga 2008, 'Altered intestinal absorption of L-thyroxine caused
    by coffee'). It must remain in both source_pmids and
    verification.verified_pmids."""
    assert "18341376" in (coffee_entry.get("source_pmids") or []), (
        "DSI_LEVOTHYROXINE_COFFEE.source_pmids must retain PMID 18341376."
    )
    verified = (coffee_entry.get("verification") or {}).get("verified_pmids") or []
    assert "18341376" in verified, (
        "DSI_LEVOTHYROXINE_COFFEE.verification.verified_pmids must retain 18341376."
    )


def test_levothyroxine_specific_not_class(coffee_entry):
    """agent1_id must remain the levothyroxine RxCUI '10582' — NOT a drug
    class like 'class:thyroid_medications'. The timing rule is specific to
    levothyroxine PK; broadening to a class alert would inappropriately
    surface this for liothyronine / desiccated thyroid / etc., where the
    coffee evidence is thinner."""
    assert coffee_entry["agent1_id"] == "10582", (
        "DSI_LEVOTHYROXINE_COFFEE.agent1_id must remain '10582' "
        "(levothyroxine RxCUI). Do not promote to a class:thyroid alert."
    )


def test_management_text_retains_timing_separation(coffee_entry):
    """The management text must keep the concrete timing-separation rule
    (water-only + 30–60 minutes before coffee). Severity promotion is
    pointless without the actionable instruction."""
    mgmt = coffee_entry.get("management") or ""
    assert "water" in mgmt.lower(), (
        "Management text must keep the 'take with water' instruction."
    )
    assert "30" in mgmt and "60" in mgmt, (
        "Management text must keep the 30–60 minute timing separation."
    )


def test_unsupported_dsi_ssri_fishoil_background_pair_stays_retired(curated):
    """Disease/physiology association does not establish a consumer-facing
    SSRI×fish-oil interaction. Keep the retired background row out unless a
    new evidence and clinical-review cycle supports exact attribution."""
    ids = {entry["id"] for entry in curated["interactions"]}
    assert "DSI_SSRI_FISHOIL" not in ids, (
        "DSI_SSRI_FISHOIL was retired after the adversarial clinical audit. "
        "Do not restore it as an active pair without new reviewed evidence."
    )
