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


def test_banned_substance_enricher_emits_canonical_safety_flags():
    from enrich_supplements_v3 import SupplementEnricherV3

    result = SupplementEnricherV3()._check_banned_substances([
        {"name": "Delta-8 THC", "standardName": "Delta-8 THC"}
    ])

    flags = result.get("safety_flags", [])
    assert any(flag.get("entry_id") == "BANNED_DELTA8_THC" for flag in flags)
    flag = next(flag for flag in flags if flag.get("entry_id") == "BANNED_DELTA8_THC")
    assert flag["source_db"] == "banned_recalled_ingredients"
    assert flag["status"] == "high_risk"
    assert flag["severity"] == "high"
    assert flag["match_type"] in {"exact", "alias"}

    legacy_hit = next(
        hit for hit in result.get("substances", [])
        if hit.get("banned_id") == "BANNED_DELTA8_THC"
    )
    assert legacy_hit["safety_flag"] == flag


def test_bare_chromium_standardname_cannot_create_hexavalent_safety_flag():
    from enrich_supplements_v3 import SupplementEnricherV3

    result = SupplementEnricherV3()._check_banned_substances([
        {
            "name": "Chromium",
            "raw_source_text": "Chromium",
            "standardName": "Chromium (VI) — Hexavalent Chromium",
            "standard_name": "Chromium (VI) — Hexavalent Chromium",
            "forms": [],
        }
    ])

    assert not any(
        flag.get("entry_id") == "HM_CHROMIUM_HEXAVALENT"
        for flag in result.get("safety_flags", [])
    )


def test_explicit_hexavalent_chromium_still_creates_safety_flag():
    from enrich_supplements_v3 import SupplementEnricherV3

    result = SupplementEnricherV3()._check_banned_substances([
        {
            "name": "Hexavalent Chromium",
            "raw_source_text": "Hexavalent Chromium",
            "standardName": "Chromium",
            "standard_name": "Chromium",
            "forms": [],
        }
    ])

    flag = next(
        flag for flag in result.get("safety_flags", [])
        if flag.get("entry_id") == "HM_CHROMIUM_HEXAVALENT"
    )
    assert flag["match_type"] == "explicit_form_evidence"
    assert flag["status"] == "high_risk"


def test_negative_match_terms_support_exact_mode_objects():
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3()
    terms = [{"term": "chromium", "match_mode": "exact"}]

    assert enricher._has_negative_match_term("chromium", terms) is True
    assert enricher._has_negative_match_term("chromium picolinate", terms) is False


def test_safety_precedence_and_strict_index_are_shared():
    from identity.safety import build_safety_exact_index, top_safety_flag

    flags = [
        {"entry_id": "WATCH", "status": "watchlist"},
        {"entry_id": "BAN", "status": "banned"},
        {"entry_id": "HIGH", "status": "high_risk"},
    ]
    assert top_safety_flag(flags)["entry_id"] == "BAN"

    index = build_safety_exact_index([
        {
            "id": "HM_CHROMIUM_HEXAVALENT",
            "standard_name": "Chromium (VI) — Hexavalent Chromium",
            "aliases": ["chromium(6+)", "chromium"],
        }
    ])
    assert "chromium(6+)" in index
    assert "chromium" in index
    assert "chromium(6+)" != "chromium"


def test_standardname_safety_audit_rejects_standardname_only_safety_evidence(tmp_path):
    from api_audit.audit_standardname_safety_separation import audit

    detail_dir = tmp_path / "detail_blobs"
    detail_dir.mkdir()
    (detail_dir / "bad.json").write_text("""{
      "dsld_id": "bad-standardname-only",
      "ingredients": [{
        "name": "Chromium",
        "raw_source_text": "Chromium",
        "standard_name": "Chromium (VI) — Hexavalent Chromium",
        "standardName": "Chromium (VI) — Hexavalent Chromium",
        "canonical_source_db": "ingredient_quality_map",
        "safety_flags": [{
          "entry_id": "HM_CHROMIUM_HEXAVALENT",
          "source_db": "banned_recalled_ingredients",
          "status": "high_risk",
          "severity": "high",
          "match_type": "exact",
          "matched_variant": "Hexavalent Chromium",
          "evidence_text": "Hexavalent Chromium",
          "confidence": "high"
        }]
      }]
    }""")

    codes = {finding["code"] for finding in audit(tmp_path)}
    assert "SAFETY_FLAG_SUPPORTED_ONLY_BY_STANDARD_NAME" in codes


def test_standardname_safety_audit_rejects_safety_source_identity(tmp_path):
    from api_audit.audit_standardname_safety_separation import audit

    detail_dir = tmp_path / "detail_blobs"
    detail_dir.mkdir()
    (detail_dir / "bad.json").write_text("""{
      "dsld_id": "bad-safety-identity",
      "ingredients": [{
        "name": "Chromium",
        "raw_source_text": "Chromium",
        "standard_name": "Chromium",
        "standardName": "Chromium",
        "canonical_source_db": "banned_recalled_ingredients",
        "safety_flags": []
      }]
    }""")

    codes = {finding["code"] for finding in audit(tmp_path)}
    assert "IDENTITY_FROM_SAFETY_SOURCE" in codes


def test_reference_data_audit_rejects_qualified_safety_alias_collapsing_to_identity(tmp_path):
    from api_audit.audit_standardname_safety_separation import audit_reference_data

    data_dir = tmp_path
    (data_dir / "ingredient_quality_map.json").write_text("""{
      "chromium": {"standard_name": "Chromium", "aliases": []}
    }""")
    (data_dir / "standardized_botanicals.json").write_text("[]")
    (data_dir / "botanical_ingredients.json").write_text("[]")
    (data_dir / "other_ingredients.json").write_text("[]")
    (data_dir / "banned_recalled_ingredients.json").write_text("""{
      "ingredients": [{
        "id": "HM_CHROMIUM_HEXAVALENT",
        "standard_name": "Chromium (VI) — Hexavalent Chromium",
        "aliases": ["Chromium"]
      }]
    }""")
    (data_dir / "harmful_additives.json").write_text("""{"additives": []}""")

    findings = audit_reference_data(data_dir)
    assert any(
        finding["code"] == "QUALIFIED_SAFETY_ALIAS_COLLAPSES_TO_IDENTITY"
        for finding in findings
    )
