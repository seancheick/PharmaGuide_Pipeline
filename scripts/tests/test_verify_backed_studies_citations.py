"""The backed-studies citation gate audits each PMID/ingredient claim."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "api_audit"
if str(AUDIT) not in sys.path:
    sys.path.insert(0, str(AUDIT))

from verify_backed_studies_citations import collect_claims  # noqa: E402


def test_ghost_topic_check_resolves_binomial_through_canonical_registry() -> None:
    """DGL's GutGard RCT must pass the ghost check at the source.

    PMID 21747893 was a historical GHOST-SUSPECT false positive: the topic
    check compared against stored ingredient words only, and 'Glycyrrhiza
    glabra' shares no word with 'deglycyrrhizinated'. The canonical registry
    resolves DGL to the licorice entry, whose form aliases carry
    'glycyrrhiza' — so the live title now overlaps deterministically.
    """
    payload = json.loads(
        (ROOT / "scripts" / "data" / "backed_clinical_studies.json").read_text()
    )
    claims = collect_claims(payload["backed_clinical_studies"])
    tw = claims[("21747893", "PRECLIN_DGL")]["tw"]
    assert {"glycyrrhiza", "glabra"} & tw, (
        "canonical expansion must surface the binomial vocabulary"
    )


def test_ghost_topic_check_resolves_active_of_source_chain() -> None:
    """The BCM-95 knee-OA trial must pass the ghost check at the source.

    PMID 33516238's live title names only 'turmeric'; the evidence entry is
    formulation-scoped curcumin. Canonical expansion follows the IQM
    active_in relationship (curcumin → turmeric) so the topic set reaches
    the source-botanical name without any local synonym map.
    """
    payload = json.loads(
        (ROOT / "scripts" / "data" / "backed_clinical_studies.json").read_text()
    )
    entry = next(
        e for e in payload["backed_clinical_studies"]
        if e.get("id") == "BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN"
    )
    assert "BCM-95" in (entry.get("aliases") or []), (
        "the entry's own formulation alias must resolve through the registry"
    )
    claims = collect_claims(payload["backed_clinical_studies"])
    tw = claims[("33516238", "BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN")]["tw"]
    assert "turmeric" in tw
    assert "curcumin" in tw


def test_shared_pmid_keeps_ingredient_claims_separate() -> None:
    entries = [
        {
            "id": "INGREDIENT_A",
            "standard_name": "Magnesium",
            "references_structured": [{"pmid": "12345", "title": "Paper"}],
        },
        {
            "id": "INGREDIENT_B",
            "standard_name": "Curcumin",
            "references_structured": [{"pmid": "12345", "title": "Paper"}],
        },
    ]

    claims = collect_claims(entries)

    assert set(claims) == {("12345", "INGREDIENT_A"), ("12345", "INGREDIENT_B")}
    assert "magnesium" in claims[("12345", "INGREDIENT_A")]["tw"]
    assert "curcumin" not in claims[("12345", "INGREDIENT_A")]["tw"]
    assert "curcumin" in claims[("12345", "INGREDIENT_B")]["tw"]


def test_bcm95_title_heuristic_false_positive_has_entry_scoped_review() -> None:
    payload = json.loads(
        (ROOT / "scripts" / "data" / "backed_studies_ghost_review.json").read_text()
    )
    reviewed = {
        (str(item.get("pmid")), str(item.get("entry_id"))): item
        for item in payload["reviewed"]
    }

    item = reviewed[("33516238", "BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN")]
    assert "BCM-95" in item["rationale"]
    assert "abstract" in item["rationale"].lower()
