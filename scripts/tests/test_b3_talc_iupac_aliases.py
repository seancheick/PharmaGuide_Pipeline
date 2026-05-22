"""B3: ensure talc IUPAC-nomenclature aliases route to BANNED_ADD_TALC.

The May 22 2026 pipeline run surfaced 6 unmapped inactive
occurrences under the chemical names 'Magnesium Silicate Hydroxide'
(×3) and 'Silicate Hydroxide' (×3). Both ARE talc by IUPAC
nomenclature — talc's chemical formula is Mg3Si4O10(OH)2, which
the IUPAC name 'magnesium silicate hydroxide' describes exactly.

Manufacturers may use the chemical-name form to avoid the
consumer-recognized 'talc' label (which carries asbestos-
contamination connotations from the J&J recalls and IARC's
Group 2A classification). This batch adds the missing aliases
so the cleaner correctly flags these labels under the existing
BANNED_ADD_TALC safety entry (UNII 7SEV7J4R1U, contaminant_risk).

Why this is safety-critical

Talc-containing supplements have asbestos-contamination risk
when not COA-verified. Routing the IUPAC chemical-name variants
through the talc safety entry ensures these products receive the
contaminant_risk flag in scoring rather than slipping through as
unmapped inactives.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def banned_doc() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "banned_recalled_ingredients.json")) as f:
        return json.load(f)


def _find_talc(doc):
    # banned_recalled_ingredients.json uses 'ingredients' as the array key
    entries = doc.get("ingredients") or doc.get("banned_recalled_ingredients") or []
    for e in entries:
        if isinstance(e, dict) and e.get("id") == "BANNED_ADD_TALC":
            return e
    return None


def test_talc_entry_present_with_correct_unii(banned_doc):
    e = _find_talc(banned_doc)
    assert e, "BANNED_ADD_TALC entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "7SEV7J4R1U", (
        f"Talc UNII must be '7SEV7J4R1U' (verified via FDA UNII cache). "
        f"Got: {e.get('external_ids')}"
    )


def test_iupac_chemical_name_aliases_present(banned_doc):
    """'Magnesium Silicate Hydroxide' = Mg3Si4O10(OH)2 = TALC by IUPAC.
    'Silicate Hydroxide' (label-truncated form) must also route to
    the talc safety entry."""
    e = _find_talc(banned_doc)
    aliases = [(a or "").strip().lower() for a in (e.get("aliases") or [])]
    for required in ("magnesium silicate hydroxide", "silicate hydroxide"):
        assert required in aliases, (
            f"BANNED_ADD_TALC must carry IUPAC-name alias '{required}'. "
            f"Got: {e.get('aliases')}"
        )


def test_existing_safety_metadata_preserved(banned_doc):
    """The expanded alias list must NOT regress any existing safety
    metadata. Reason text, status, class_tags should all remain."""
    e = _find_talc(banned_doc)
    assert e.get("status") == "high_risk"
    assert "asbestos" in (e.get("reason") or "").lower()
    class_tags = e.get("class_tags") or []
    assert "asbestos_contamination_risk" in class_tags
    assert "contaminant_risk" in class_tags
