"""The backed-studies citation gate audits each PMID/ingredient claim."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "api_audit"
if str(AUDIT) not in sys.path:
    sys.path.insert(0, str(AUDIT))

from verify_backed_studies_citations import collect_claims  # noqa: E402


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
