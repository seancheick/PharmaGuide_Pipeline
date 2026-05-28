import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_chromium_identity_lookup_is_not_banned_payload():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    chromium_key = normalizer.matcher.preprocess_text("Chromium")

    payload = normalizer._fast_exact_lookup.get(chromium_key)
    assert payload is not None
    assert payload.get("type") == "ingredient"
    assert payload.get("standard_name") == "Chromium"


def test_chromium_unii_resolves_to_iqm_identity_not_hexavalent_payload():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    payload, method = normalizer._try_unii_match({
        "name": "Chromium",
        "uniiCode": "0R0008Q3JB",
        "category": "mineral",
        "ingredientGroup": "Chromium",
        "forms": [],
    })

    assert method == "unii_exact_match"
    assert payload.get("type") == "ingredient"
    assert payload.get("standard_name") == "Chromium"


def test_cleaner_emits_iqm_chromium_for_generic_chromium_unii():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    row = {
        "name": "Chromium",
        "uniiCode": "0R0008Q3JB",
        "category": "mineral",
        "ingredientGroup": "Chromium",
        "quantity": [{"quantity": 35, "unit": "mcg"}],
        "forms": [],
    }

    cleaned = normalizer._process_single_ingredient_enhanced(row, is_active=True)

    assert cleaned["standardName"] == "Chromium"
    assert cleaned["canonical_id"] == "chromium"
    assert cleaned["canonical_source_db"] == "ingredient_quality_map"


def test_safety_normalization_preserves_qualified_chromium_forms():
    from identity.safety import safety_normalize_text

    assert safety_normalize_text("chromium(6+)") != safety_normalize_text("chromium")
    assert safety_normalize_text("Cr(VI)") != safety_normalize_text("cr")
    assert "hexavalent" in safety_normalize_text("Chromium (VI) — Hexavalent Chromium")
    assert "high dose" in safety_normalize_text("Green Tea Extract (High Dose)")
    assert "e171" in safety_normalize_text("Titanium Dioxide E171")


def test_derived_standard_name_is_not_safety_evidence_for_mapped_iqm_active():
    from build_final_db import (
        _active_banned_recall_evidence_terms,
        _get_active_banned_recalled_index,
        _resolve_active_safety_contract,
    )

    terms = _active_banned_recall_evidence_terms(
        raw_source_text="Chromium",
        name="Chromium",
        standard_name="Chromium (VI) — Hexavalent Chromium",
        forms=[],
        identity_mapped=True,
    )
    assert "chromium vi hexavalent chromium" not in terms

    contract = _resolve_active_safety_contract(
        harmful_hit=None,
        harmful_ref={},
        ingredient_hits=[],
        name_terms=terms,
        banned_recalled_index=_get_active_banned_recalled_index(),
    )
    assert contract["is_safety_concern"] is False
    assert contract["matched_rule_id"] is None
