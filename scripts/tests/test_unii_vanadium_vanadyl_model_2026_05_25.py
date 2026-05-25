#!/usr/bin/env python3
"""Regression coverage for Vanadium vs Vanadyl Sulfate UNII ownership.

P0 UNII audit 2026-05-25: exact UNII 6DU9Y533FA is VANADYL SULFATE
(GSRS-verified), while elemental Vanadium owns UNII 00J9J9XKDE. The same
exact UNII must not be modeled both as a form under ``vanadium`` and as the
standalone ``vanadyl_sulfate`` IQM parent.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "api_audit"))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
import audit_unii_same_tier_conflicts as unii_audit  # noqa: E402


IQM_PATH = REPO_ROOT / "scripts/data/ingredient_quality_map.json"


def _iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


def _normalizer() -> EnhancedDSLDNormalizer:
    logging.getLogger("enhanced_normalizer").setLevel(logging.ERROR)
    return EnhancedDSLDNormalizer()


def _exact_lookup(text: str) -> dict | None:
    normalizer = _normalizer()
    key = normalizer.matcher.preprocess_text(text)
    return normalizer._fast_exact_lookup.get(key)


def test_exact_unii_ownership_is_not_duplicated_between_vanadium_and_vanadyl():
    iqm = _iqm()

    assert iqm["vanadium"]["external_ids"]["unii"] == "00J9J9XKDE"
    assert iqm["vanadyl_sulfate"]["external_ids"]["unii"] == "6DU9Y533FA"

    vanadium_forms = iqm["vanadium"]["forms"]
    assert "vanadium (unspecified)" in vanadium_forms
    assert "vanadyl sulfate" not in vanadium_forms
    assert (vanadium_forms["vanadium (unspecified)"].get("external_ids") or {}).get("unii") is None
    assert "6DU9Y533FA" in vanadium_forms["vanadium (unspecified)"]["unii_note"]


def test_generic_vanadium_exact_lookup_stays_on_element_parent():
    payload = _exact_lookup("Vanadium")

    assert payload is not None
    assert payload["standard_name"] == "Vanadium"
    assert payload["type"] == "ingredient"


def test_explicit_vanadyl_sulfate_terms_route_to_vanadyl_parent():
    for text in ["Vanadyl Sulfate", "Vanadium Sulfate", "vanadyl", "vanadium citrate"]:
        payload = _exact_lookup(text)
        assert payload is not None, text
        assert payload["standard_name"] == "Vanadyl Sulfate", text
        assert payload["type"] == "ingredient", text


def test_vanadyl_sulfate_forms_obey_class_equivalence_bio_score_floor():
    forms = _iqm()["vanadyl_sulfate"]["forms"]
    expected_bio = {
        "vanadyl sulfate (VOSO4)": 7,
        "bis(maltolato)oxovanadium (BMOV)": 7,
        "bis(picolinato)oxovanadium (BPOV)": 7,
        "sodium vanadate": 7,
        "vanadyl sulfate (unspecified)": 7,
        "vanadium aspartate": 7,
        "vanadium citrate": 7,
    }

    for form_name, bio_score in expected_bio.items():
        form = forms[form_name]
        assert form["bio_score"] == bio_score, form_name
        assert form["score"] == bio_score, form_name
        notes = form.get("notes", "").lower()
        assert "23982218" in notes or "dr pham c12" in notes or "v class" in notes, form_name


def test_vanadyl_sulfate_unii_no_longer_has_same_tier_conflict():
    groups = unii_audit.find_same_tier_groups(unii_audit.collect_unii_records(REPO_ROOT))

    assert not [group for group in groups if group.unii == "6DU9Y533FA"]
