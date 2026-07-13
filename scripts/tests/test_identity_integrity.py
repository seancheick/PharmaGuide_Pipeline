from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from identity_integrity import (
    build_canonical_identity_registry,
    IdentityDecision,
    extract_label_evidence,
    is_identity_scoreable,
    normalize_label_display,
    resolve_identity,
)


CANONICALS = {
    "epa": "epa",
    "epa (eicosapentaenoic acid)": "epa",
    "eicosapentaenoic acid": "epa",
    "dha": "dha",
    "dha (docosahexaenoic acid)": "dha",
    "docosahexaenoic acid": "dha",
    "docosahexaenoic acid ethyl ester": "dha",
    "magnesium": "magnesium",
}


def fake_resolver(candidate: str) -> str | None:
    return CANONICALS.get(normalize_label_display(candidate).casefold())


def test_canonical_identity_registry_has_one_priority_and_ambiguity_contract():
    registry = build_canonical_identity_registry(
        {
            "ingredient_quality_map": {
                "_metadata": {},
                "coq10": {
                    "standard_name": "Coenzyme Q10",
                    "aliases": ["Shared Alias", "Branded(TM) CoQ10"],
                    "forms": {
                        "ubiquinone": {"aliases": ["Coenzyme Q-10"]},
                    },
                    "match_rules": {},
                },
            },
            "standardized_botanicals": {
                "standardized_botanicals": [
                    {
                        "id": "elderberry_std",
                        "standard_name": "European Elder",
                        "aliases": ["Shared Alias"],
                    }
                ]
            },
            "botanical_ingredients": {
                "botanical_ingredients": [
                    {
                        "id": "elderberry",
                        "standard_name": "Black Elderberry",
                        "aliases": ["Sambucus nigra"],
                    }
                ]
            },
            "other_ingredients": {
                "other_ingredients": [
                    {
                        "id": "OI_EDTA",
                        "standard_name": "EDTA",
                        "aliases": ["EDTA Disodium"],
                    }
                ]
            },
            "proprietary_blends": {
                "proprietary_blend_concerns": [
                    {
                        "id": "BLEND_GENERAL",
                        "standard_name": "General Blend",
                        "blend_terms": ["Proprietary Blend"],
                    }
                ]
            },
        }
    )

    assert registry.resolve_unambiguous("Coenzyme Q-10") == "coq10"
    assert registry.preferred_index["branded(tm) coq10"] == (
        "coq10",
        "ingredient_quality_map",
    )
    assert registry.resolve_unambiguous("Branded CoQ10") == "coq10"
    assert registry.resolve_unambiguous("Sambucus nigra") == "elderberry"
    assert registry.resolve_unambiguous("EDTA Disodium") == "OI_EDTA"
    assert registry.resolve_unambiguous("Proprietary Blend") == "BLEND_GENERAL"
    assert registry.resolve_unambiguous("Shared Alias") is None
    assert registry.resolve_preferred("Shared Alias") == (
        "coq10",
        "ingredient_quality_map",
    )


def test_registry_prefers_specific_standard_name_over_umbrella_form_alias():
    registry = build_canonical_identity_registry(
        {
            "ingredient_quality_map": {
                "digestive_enzymes": {
                    "standard_name": "Digestive Enzymes",
                    "aliases": [],
                    "forms": {
                        "specific enzymes": {"aliases": ["Bromelain"]},
                    },
                    "match_rules": {},
                },
                "bromelain": {
                    "standard_name": "Bromelain",
                    "aliases": ["bromelain enzyme"],
                    "forms": {},
                    "match_rules": {},
                },
            },
            "other_ingredients": {
                "other_ingredients": [
                    {
                        "id": "OI_BROMELAIN",
                        "standard_name": "Bromelain",
                        "aliases": [],
                    }
                ]
            },
        }
    )

    assert registry.resolve_preferred("Bromelain") == (
        "bromelain",
        "ingredient_quality_map",
    )
    assert registry.resolve_unambiguous("Bromelain") is None


def test_registry_rejects_equal_priority_alias_conflicts():
    registry = build_canonical_identity_registry(
        {
            "ingredient_quality_map": {
                "first": {
                    "standard_name": "First",
                    "aliases": ["Shared"],
                    "forms": {},
                    "match_rules": {},
                },
                "second": {
                    "standard_name": "Second",
                    "aliases": ["Shared"],
                    "forms": {},
                    "match_rules": {},
                },
            }
        }
    )

    assert registry.resolve_preferred("Shared") is None
    assert "shared" not in registry.preferred_index


def test_resolved_outer_identity_wins_over_parenthetical_acronym():
    candidates = {
        "medium chain triglycerides": "mct_oil",
        "mct": "other_ingredient_mct",
    }

    decision = resolve_identity(
        row={
            "raw_source_text": "Medium Chain Triglycerides",
            "ingredientGroup": "Medium Chain Triglycerides (MCT)",
        },
        supplied_canonical_id="mct_oil",
        resolve_candidate=lambda value: candidates.get(
            normalize_label_display(value).casefold()
        ),
    )

    assert decision.disposition == "clean"
    assert decision.canonical_id == "mct_oil"


def test_declared_group_beats_ambiguous_alternate_name():
    candidates = {
        "alpha-linolenic acid": "alpha_linolenic_acid",
        "ala": "alpha_lipoic_acid",
    }

    decision = resolve_identity(
        row={
            "raw_source_text": "Alpha-Linolenic Acid",
            "ingredientGroup": "Alpha-Linolenic Acid",
            "alternateNames": ["ALA"],
        },
        supplied_canonical_id="alpha_linolenic_acid",
        resolve_candidate=lambda value: candidates.get(
            normalize_label_display(value).casefold()
        ),
    )

    assert decision.disposition == "clean"
    assert decision.canonical_id == "alpha_linolenic_acid"


def test_explicit_cross_registry_equivalence_collapses_only_reviewed_identity():
    registry = build_canonical_identity_registry(
        {
            "ingredient_quality_map": {
                "mct_oil": {
                    "standard_name": "MCT Oil",
                    "aliases": [],
                    "forms": {},
                    "match_rules": {},
                }
            },
            "other_ingredients": {
                "other_ingredients": [
                    {
                        "id": "PII_MCT",
                        "standard_name": "Medium Chain Triglycerides",
                        "aliases": ["MCT"],
                    }
                ]
            },
            "canonical_equivalences": {
                "equivalences": [
                    {
                        "source_db": "other_ingredients",
                        "source_id": "PII_MCT",
                        "target_db": "ingredient_quality_map",
                        "target_id": "mct_oil",
                        "relation": "exact_equivalent",
                        "basis": "same-substance review",
                    }
                ]
            },
        }
    )

    assert registry.resolve_verified_preferred("Medium Chain Triglycerides") == (
        "mct_oil",
        "ingredient_quality_map",
    )
    assert registry.resolve_verified_preferred("MCT") == (
        "mct_oil",
        "ingredient_quality_map",
    )


def test_equivalence_target_must_exist_in_declared_registry():
    with pytest.raises(ValueError, match="target_id"):
        build_canonical_identity_registry(
            {
                "ingredient_quality_map": {
                    "mct_oil": {
                        "standard_name": "MCT Oil",
                        "aliases": [],
                        "forms": {},
                        "match_rules": {},
                    }
                },
                "other_ingredients": {
                    "other_ingredients": [
                        {
                            "id": "PII_MCT",
                            "standard_name": "Medium Chain Triglycerides",
                            "aliases": [],
                        }
                    ]
                },
                "canonical_equivalences": {
                    "equivalences": [
                        {
                            "source_db": "other_ingredients",
                            "source_id": "PII_MCT",
                            "target_db": "ingredient_quality_map",
                            "target_id": "missing",
                            "relation": "exact_equivalent",
                            "basis": "test",
                        }
                    ]
                },
            }
        )


def test_equivalence_cannot_override_an_iqm_canonical_target():
    with pytest.raises(ValueError, match="conflicting canonical redirect"):
        build_canonical_identity_registry(
            {
                "ingredient_quality_map": {
                    "legacy": {
                        "standard_name": "Legacy",
                        "aliases": [],
                        "forms": {},
                        "match_rules": {"target_id": "preferred"},
                    },
                    "preferred": {
                        "standard_name": "Preferred",
                        "aliases": [],
                        "forms": {},
                        "match_rules": {},
                    },
                },
                "other_ingredients": {
                    "other_ingredients": [
                        {
                            "id": "other_legacy",
                            "standard_name": "Other Legacy",
                            "aliases": [],
                        }
                    ]
                },
                "canonical_equivalences": {
                    "equivalences": [
                        {
                            "source_db": "ingredient_quality_map",
                            "source_id": "legacy",
                            "target_db": "other_ingredients",
                            "target_id": "other_legacy",
                            "relation": "exact_equivalent",
                            "basis": "test conflict",
                        }
                    ]
                },
            }
        )


def test_normalize_label_display_uses_the_approved_operation_order():
    value = "  ＥＰＡ™\t(tm)  ® ℠ (r)\n(sm)  "

    assert normalize_label_display(value) == "EPA"
    assert normalize_label_display(None) == ""


def test_extract_label_evidence_is_limited_to_line_level_fields():
    row = {
        "raw_source_text": "Literal row name",
        "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
        "raw_taxonomy": {"ingredientGroup": "Eicosapentaenoic Acid"},
        "label_nutrient_context": "EPA",
        "alternateNames": ["Eicosapentaenoic Acid"],
        "forms": [{"prefix": "as", "name": "Ethyl Esters"}],
        "product_name": "EPA Heart Health",
        "marketing_text": "High-potency omega EPA",
        "parent_blend_name": "Fish Oil EPA Blend",
    }

    evidence = extract_label_evidence(row)

    assert [(item.field, item.value, item.kind) for item in evidence] == [
        ("raw_source_text", "Literal row name", "source_name"),
        (
            "ingredientGroup",
            "EPA (Eicosapentaenoic Acid)",
            "structured_identity",
        ),
        (
            "raw_taxonomy.ingredientGroup",
            "Eicosapentaenoic Acid",
            "structured_identity",
        ),
        ("label_nutrient_context", "EPA", "structured_identity"),
        ("alternateNames[0]", "Eicosapentaenoic Acid", "structured_identity"),
        ("forms[0]", "as Ethyl Esters", "source_form"),
    ]
    assert not any(
        text in item.value
        for item in evidence
        for text in ("Heart Health", "High-potency", "Fish Oil EPA Blend")
    )


def test_extract_label_evidence_falls_back_to_raw_taxonomy_forms():
    evidence = extract_label_evidence(
        {
            "raw_source_text": "EPA",
            "raw_taxonomy": {
                "forms": [{"prefix": "as", "name": "Ethyl Esters"}],
            },
        }
    )

    assert ("raw_taxonomy.forms[0]", "as Ethyl Esters", "source_form") in [
        (item.field, item.value, item.kind) for item in evidence
    ]


def test_structured_epa_label_repairs_conflicting_dha_taxonomy():
    decision = resolve_identity(
        row={
            "raw_source_text": "Docosahexaenoic Acid Ethyl Ester",
            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
            "forms": [{"prefix": "as", "name": "Ethyl Esters"}],
        },
        supplied_canonical_id="dha",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "repaired"
    assert decision.canonical_id_before == "dha"
    assert decision.canonical_id == "epa"
    assert decision.source_label_name == "EPA"
    assert decision.label_display_name == "EPA"
    assert decision.source_label_form == "as Ethyl Esters"
    assert decision.label_display_form == "as Ethyl Esters"
    assert decision.scoreable_identity is True
    assert decision.rationale


def test_matching_structured_identity_is_clean():
    decision = resolve_identity(
        row={
            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
            "forms": [{"prefix": "as", "name": "Ethyl Esters"}],
        },
        supplied_canonical_id="dha",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "clean"
    assert decision.canonical_id == "dha"
    assert decision.label_display_name == "DHA"
    assert decision.scoreable_identity is True


def test_source_name_stays_literal_while_display_name_is_normalized():
    decision = resolve_identity(
        row={"ingredientGroup": "ＥＰＡ™ (Eicosapentaenoic Acid)"},
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert decision.source_label_name == "ＥＰＡ™"
    assert decision.label_display_name == "EPA"


def test_parenthetical_label_is_preserved_unless_both_sides_resolve_identically():
    decision = resolve_identity(
        row={"ingredientGroup": "Magnesium (as Citrate)"},
        supplied_canonical_id="magnesium",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "clean"
    assert decision.source_label_name == "Magnesium (as Citrate)"
    assert decision.label_display_name == "Magnesium (as Citrate)"


def test_no_structured_identity_uses_coherent_supplied_taxonomy():
    decision = resolve_identity(
        row={"raw_source_text": "Magnesium Citrate"},
        supplied_canonical_id="magnesium",
        resolve_candidate=fake_resolver,
        taxonomy_coherent=True,
    )

    assert decision.disposition == "taxonomy_only"
    assert decision.canonical_id_before == "magnesium"
    assert decision.canonical_id == "magnesium"
    assert decision.label_display_name == "Magnesium Citrate"
    assert decision.scoreable_identity is True


def test_unresolvable_structured_text_uses_verified_taxonomy_without_repairing():
    decision = resolve_identity(
        row={
            "raw_source_text": "Nattokinase",
            "ingredientGroup": "Nattokinase",
        },
        supplied_canonical_id="nattokinase",
        resolve_candidate=lambda _: None,
        taxonomy_coherent=True,
    )

    assert decision.disposition == "taxonomy_only"
    assert decision.canonical_id_before == "nattokinase"
    assert decision.canonical_id == "nattokinase"
    assert decision.label_display_name == "Nattokinase"
    assert decision.scoreable_identity is True


def test_unresolvable_structured_text_does_not_block_matching_literal_identity():
    decision = resolve_identity(
        row={
            "raw_source_text": "EPA",
            "ingredientGroup": "Fatty Acid (unspecified)",
        },
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
        taxonomy_coherent=False,
    )

    assert decision.disposition == "clean"
    assert decision.canonical_id == "epa"
    assert decision.scoreable_identity is True


def test_unresolved_form_does_not_block_raw_identity_validation():
    decision = resolve_identity(
        row={
            "raw_source_text": "EPA",
            "forms": [{"prefix": "as", "name": "Ethyl Esters"}],
        },
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "clean"
    assert decision.canonical_id == "epa"
    assert decision.source_label_form == "as Ethyl Esters"
    assert decision.label_display_form == "as Ethyl Esters"
    assert decision.scoreable_identity is True


def test_unresolved_form_does_not_block_taxonomy_compatibility_path():
    decision = resolve_identity(
        row={
            "raw_source_text": "Magnesium Citrate",
            "forms": [{"prefix": "as", "name": "Citrate"}],
        },
        supplied_canonical_id="magnesium",
        resolve_candidate=fake_resolver,
        taxonomy_coherent=True,
    )

    assert decision.disposition == "taxonomy_only"
    assert decision.canonical_id == "magnesium"
    assert decision.source_label_form == "as Citrate"
    assert decision.label_display_form == "as Citrate"
    assert decision.scoreable_identity is True


def test_resolvable_form_cannot_repair_canonical_identity():
    decision = resolve_identity(
        row={
            "raw_source_text": "Fish Oil",
            "forms": [{"name": "DHA"}],
        },
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id_before == "epa"
    assert decision.canonical_id is None
    assert decision.source_label_form == "DHA"
    assert decision.label_display_form == "DHA"
    assert decision.scoreable_identity is False


def test_unresolved_raw_identity_is_blocked_without_explicit_taxonomy_coherence():
    decision = resolve_identity(
        row={"raw_source_text": "Magnesium Citrate"},
        supplied_canonical_id="magnesium",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False


def test_canonical_registry_ids_are_compared_exactly():
    def noncanonical_resolver(candidate: str) -> str | None:
        if normalize_label_display(candidate).casefold() == "epa":
            return "EPA"
        return None

    decision = resolve_identity(
        row={"raw_source_text": "EPA"},
        supplied_canonical_id="epa",
        resolve_candidate=noncanonical_resolver,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False


def test_raw_identity_cannot_repair_conflicting_supplied_canonical():
    decision = resolve_identity(
        row={"raw_source_text": "DHA"},
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id_before == "epa"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False


def test_missing_supplied_canonical_is_identity_conflict():
    decision = resolve_identity(
        row={"raw_source_text": "Unknown ingredient"},
        supplied_canonical_id=None,
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False


def test_unresolved_structured_identity_blocks_taxonomy_fallback():
    decision = resolve_identity(
        row={
            "raw_source_text": "Unknown ingredient",
            "ingredientGroup": "Unknown high-specific ingredient",
        },
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id_before == "epa"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False


def test_conflicting_structured_canonicals_are_not_scoreable():
    decision = resolve_identity(
        row={
            "raw_source_text": "Omega-3 fatty acids",
            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
            "label_nutrient_context": "DHA (Docosahexaenoic Acid)",
        },
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id_before == "epa"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False
    assert "dha" in decision.rationale
    assert "epa" in decision.rationale


def test_missing_literal_display_label_is_not_replaced_by_canonical_name():
    decision = resolve_identity(
        row={"forms": [{"prefix": "as", "name": "Ethyl Esters"}]},
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "missing_display_label"
    assert decision.source_label_name is None
    assert decision.label_display_name is None
    assert decision.canonical_id_before == "epa"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False


@pytest.mark.parametrize(
    ("disposition", "expected"),
    [
        ("clean", True),
        ("repaired", True),
        ("taxonomy_only", True),
        ("identity_conflict", False),
        ("missing_display_label", False),
        ("unknown", False),
    ],
)
def test_scoreability_policy_has_one_shared_helper(disposition, expected):
    assert is_identity_scoreable(disposition) is expected


def test_identity_decision_and_evidence_are_immutable():
    decision = resolve_identity(
        row={"ingredientGroup": "EPA (Eicosapentaenoic Acid)"},
        supplied_canonical_id="epa",
        resolve_candidate=fake_resolver,
    )

    assert isinstance(decision, IdentityDecision)
    assert isinstance(decision.evidence, tuple)
    with pytest.raises(FrozenInstanceError):
        decision.disposition = "repaired"
    with pytest.raises(FrozenInstanceError):
        decision.evidence[0].value = "DHA"


def test_candidate_resolution_never_uses_product_or_parent_blend_text():
    resolved_candidates = []

    def recording_resolver(candidate: str) -> str | None:
        resolved_candidates.append(candidate)
        return fake_resolver(candidate)

    resolve_identity(
        row={
            "raw_source_text": "Omega-3 fatty acids",
            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
            "product_name": "DHA Maximum Strength",
            "marketing_text": "Made with DHA",
            "parent_blend_text": "DHA Fish Oil Blend",
        },
        supplied_canonical_id="dha",
        resolve_candidate=recording_resolver,
    )

    assert "EPA (Eicosapentaenoic Acid)" in resolved_candidates
    assert not any("Maximum Strength" in value for value in resolved_candidates)
    assert not any("Made with" in value for value in resolved_candidates)
    assert not any("Fish Oil Blend" in value for value in resolved_candidates)
