from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from identity_integrity import (
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
    "magnesium": "magnesium",
}


def fake_resolver(candidate: str) -> str | None:
    return CANONICALS.get(normalize_label_display(candidate).casefold())


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


def test_no_structured_identity_uses_coherent_supplied_taxonomy():
    decision = resolve_identity(
        row={"raw_source_text": "Magnesium Citrate"},
        supplied_canonical_id="magnesium",
        resolve_candidate=fake_resolver,
    )

    assert decision.disposition == "taxonomy_only"
    assert decision.canonical_id_before == "magnesium"
    assert decision.canonical_id == "magnesium"
    assert decision.label_display_name == "Magnesium Citrate"
    assert decision.scoreable_identity is True


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
