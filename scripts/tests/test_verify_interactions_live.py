"""Live integration tests for verify_interactions.py.

Hit real RxNorm and UMLS endpoints. Gated by PHARMAGUIDE_LIVE_TESTS=1
so offline pytest runs stay hermetic (per INTERACTION_DB_SPEC §13 E10).

Run:
    PHARMAGUIDE_LIVE_TESTS=1 python3 -m pytest \\
        scripts/tests/test_verify_interactions_live.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api_audit"))

import verify_interactions as vi  # noqa: E402

LIVE = os.environ.get("PHARMAGUIDE_LIVE_TESTS", "").strip() == "1"
UMLS_KEY = os.environ.get("UMLS_API_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="Live tests gated by PHARMAGUIDE_LIVE_TESTS=1",
)


def test_rxnorm_resolves_warfarin_ingredient():
    client = vi.RxNormClient()
    # 11289 = warfarin (ingredient TTY=IN)
    props = client.properties("11289")
    assert props is not None
    assert "warfarin" in props["name"].lower()
    assert props["tty"] in {"IN", "PIN"}


def test_rxnorm_404_returns_none():
    client = vi.RxNormClient()
    # Bogus rxcui. NLM returns empty properties for invalid codes.
    props = client.properties("999999999999")
    assert props is None


def test_rxnorm_rejects_non_numeric():
    client = vi.RxNormClient()
    assert client.properties("not-a-rxcui") is None


@pytest.mark.skipif(not UMLS_KEY, reason="UMLS_API_KEY not set in environment")
def test_umls_exact_search_vitamin_k():
    from verify_cui import UMLSClient  # type: ignore

    client = UMLSClient(api_key=UMLS_KEY)
    result = client.search_exact("Vitamin K")
    assert result is not None
    # Vitamin K has a documented CUI; accept either the compound or the
    # vitamin-specific concept — either validates the flow works end-to-end.
    assert "cui" in result
    assert result["cui"].startswith("C")


def test_end_to_end_live_verification(tmp_path):
    """Full pipeline smoke test against real APIs."""
    from datetime import datetime, timezone

    import json

    entry = {
        "id": "LIVE_WAR_VITK",
        "type": "Med-Sup",
        "agent1_name": "Warfarin",
        "agent1_id": "11289",
        "agent2_name": "Vitamin K",
        "agent2_id": "C0042839",
        "severity": "Major",
        "interaction_effect_type": "Inhibitor",
        "mechanism": "Affects INR/clotting time",
        "management": "Monitor INR closely.",
        "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/28458697/"],
    }

    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "one.json").write_text(json.dumps([entry]))

    # Minimal IQM (matches real repo file's canonical_id)
    iqm = tmp_path / "iqm.json"
    iqm.write_text(
        json.dumps({"vitamin_k": {"cui": "C0042839", "standard_name": "Vitamin K"}})
    )
    dc = tmp_path / "dc.json"
    dc.write_text(json.dumps({"_metadata": {"schema_version": "1.0.0"}, "classes": {}}))

    report_path = tmp_path / "report.json"
    normalized_path = tmp_path / "normalized.json"

    argv = [
        "--drafts",
        str(drafts),
        "--iqm",
        str(iqm),
        "--drug-classes",
        str(dc),
        "--report",
        str(report_path),
        "--normalized-out",
        str(normalized_path),
    ]
    if not UMLS_KEY:
        argv.append("--no-umls")

    rc = vi.main(argv)
    assert rc == 0, f"verify_interactions returned {rc}"

    report = json.loads(report_path.read_text())
    assert report["valid"] == 1
    assert report["errors"] == 0
