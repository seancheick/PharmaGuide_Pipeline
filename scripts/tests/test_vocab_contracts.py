#!/usr/bin/env python3
"""Parametrized contract tests for simple vocab/reference arrays.

These specs replace one-file-per-vocab tests where the old files only checked
shape, locked IDs, simple display enums, and one-level source-data membership.
Vocab contracts with bespoke clinical assertions stay in their dedicated files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any

import pytest


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

LOWER_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
DISPLAY_TONES = {"positive", "neutral", "info", "warning", "danger"}
DISPLAY_COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
DISPLAY_ICONS = {"check", "info", "warning", "alert", "block"}


@dataclass(frozen=True)
class MembershipSpec:
    source_file: str
    field_name: str
    canonical_values: frozenset[str] | None = None
    skip_if_missing: bool = False


@dataclass(frozen=True)
class GroupSpec:
    field_name: str
    expected_by_value: dict[str, frozenset[str]]


@dataclass(frozen=True)
class VocabSpec:
    name: str
    source_file: str
    collection_key: str
    schema_version: str
    total_entries: int | None
    expected_ids: frozenset[str]
    required_fields: frozenset[str]
    exact_fields: bool = True
    id_pattern: re.Pattern[str] = LOWER_SNAKE
    metadata_contains: dict[str, str] = field(default_factory=dict)
    string_fields: frozenset[str] = field(default_factory=lambda: frozenset({"id", "name", "notes"}))
    char_limits: dict[str, int] = field(default_factory=lambda: {"notes": 200})
    enum_fields: dict[str, frozenset[Any]] = field(default_factory=dict)
    bool_fields: frozenset[str] = field(default_factory=frozenset)
    int_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)
    exact_values_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    forbidden_ids: frozenset[str] = field(default_factory=frozenset)
    group_specs: tuple[GroupSpec, ...] = ()
    memberships: tuple[MembershipSpec, ...] = ()


DISPLAY_FIELDS = frozenset({"id", "name", "short_label", "tone", "ui_color", "ui_icon", "action", "notes"})
DISPLAY_ENUMS = {
    "tone": frozenset(DISPLAY_TONES),
    "ui_color": frozenset(DISPLAY_COLORS),
    "ui_icon": frozenset(DISPLAY_ICONS),
}
DISPLAY_CHAR_LIMITS = {"short_label": 12, "action": 40, "notes": 200}
DISPLAY_STRING_FIELDS = frozenset({"id", "name", "short_label", "tone", "ui_color", "ui_icon", "action", "notes"})


SPECS: tuple[VocabSpec, ...] = (
    VocabSpec(
        name="allergen_prevalence",
        source_file="allergen_prevalence_vocab.json",
        collection_key="allergen_prevalences",
        schema_version="1.0.0",
        total_entries=3,
        expected_ids=frozenset({"high", "moderate", "low"}),
        required_fields=DISPLAY_FIELDS | frozenset({"_examples_in_data"}),
        exact_fields=False,
        string_fields=DISPLAY_STRING_FIELDS,
        char_limits=DISPLAY_CHAR_LIMITS,
        enum_fields=DISPLAY_ENUMS,
        memberships=(MembershipSpec("allergens.json", "prevalence", frozenset({"high", "moderate", "low"})),),
    ),
    VocabSpec(
        name="allergen_regulatory_status",
        source_file="allergen_regulatory_status_vocab.json",
        collection_key="allergen_regulatory_statuses",
        schema_version="1.0.0",
        total_entries=3,
        expected_ids=frozenset({"fda_major", "eu_major", "eu_allergen"}),
        required_fields=frozenset({"id", "name", "notes", "authority"}),
        string_fields=frozenset({"id", "name", "notes", "authority"}),
        enum_fields={"authority": frozenset({"FDA", "EU"})},
        memberships=(MembershipSpec("allergens.json", "regulatory_status", frozenset({"fda_major", "eu_major", "eu_allergen"})),),
    ),
    VocabSpec(
        name="ban_context",
        source_file="ban_context_vocab.json",
        collection_key="ban_contexts",
        schema_version="1.0.0",
        total_entries=5,
        expected_ids=frozenset({"substance", "adulterant_in_supplements", "contamination_recall", "watchlist", "export_restricted"}),
        required_fields=frozenset({"id", "name", "notes", "when_it_applies", "action_recommendation"}),
        string_fields=frozenset({"id", "name", "notes", "when_it_applies", "action_recommendation"}),
        memberships=(MembershipSpec("banned_recalled_ingredients.json", "ban_context", frozenset({"substance", "adulterant_in_supplements", "contamination_recall", "watchlist", "export_restricted"})),),
    ),
    VocabSpec(
        name="banned_status",
        source_file="banned_status_vocab.json",
        collection_key="banned_statuses",
        schema_version="1.0.0",
        total_entries=4,
        metadata_contains={"status": "LOCKED"},
        expected_ids=frozenset({"banned", "recalled", "high_risk", "watchlist"}),
        required_fields=DISPLAY_FIELDS | frozenset({"regulatory_basis"}),
        string_fields=DISPLAY_STRING_FIELDS | frozenset({"regulatory_basis"}),
        char_limits=DISPLAY_CHAR_LIMITS,
        enum_fields=DISPLAY_ENUMS,
        memberships=(MembershipSpec("banned_recalled_ingredients.json", "status", frozenset({"banned", "recalled", "high_risk", "watchlist"})),),
    ),
    VocabSpec(
        name="clinical_risk",
        source_file="clinical_risk_vocab.json",
        collection_key="clinical_risks",
        schema_version="1.0.0",
        total_entries=5,
        expected_ids=frozenset({"critical", "high", "moderate", "dose_dependent", "low"}),
        required_fields=DISPLAY_FIELDS | frozenset({"severity_weight"}),
        string_fields=DISPLAY_STRING_FIELDS,
        char_limits=DISPLAY_CHAR_LIMITS,
        enum_fields=DISPLAY_ENUMS,
        int_ranges={"severity_weight": (1, 5)},
        memberships=(MembershipSpec("banned_recalled_ingredients.json", "clinical_risk_enum", frozenset({"critical", "high", "moderate", "dose_dependent", "low"})),),
    ),
    VocabSpec(
        name="confidence_tier",
        source_file="confidence_tier_vocab.json",
        collection_key="confidence_tiers",
        schema_version="1.0.0",
        total_entries=3,
        expected_ids=frozenset({"high", "medium", "low"}),
        required_fields=DISPLAY_FIELDS,
        string_fields=DISPLAY_STRING_FIELDS,
        char_limits=DISPLAY_CHAR_LIMITS,
        enum_fields=DISPLAY_ENUMS,
        memberships=(
            MembershipSpec("harmful_additives.json", "confidence", frozenset({"high", "medium", "low"})),
            MembershipSpec("backed_clinical_studies.json", "effect_direction_confidence", frozenset({"high", "medium", "low"})),
        ),
    ),
    VocabSpec(
        name="efsa_genotoxicity",
        source_file="efsa_genotoxicity_vocab.json",
        collection_key="genotoxicity_classifications",
        schema_version="1.0.0",
        total_entries=7,
        expected_ids=frozenset({"negative", "positive", "equivocal", "insufficient_data", "indirect", "cannot_be_excluded", "under_review"}),
        required_fields=frozenset({"id", "name", "notes"}),
        memberships=(MembershipSpec("efsa_openfoodtox_reference.json", "genotoxicity", skip_if_missing=True),),
    ),
    VocabSpec(
        name="efsa_status",
        source_file="efsa_status_vocab.json",
        collection_key="efsa_statuses",
        schema_version="1.0.0",
        total_entries=10,
        expected_ids=frozenset({"approved", "approved_with_restrictions", "approved_restricted", "restricted_eu", "banned_eu", "not_authorised_eu", "contaminant_monitored", "under_review", "food_ingredient", "extraction_solvent"}),
        required_fields=frozenset({"id", "name", "notes"}),
        memberships=(MembershipSpec("efsa_openfoodtox_reference.json", "efsa_status", skip_if_missing=True),),
    ),
    VocabSpec(
        name="legal_status",
        source_file="legal_status_vocab.json",
        collection_key="legal_statuses",
        schema_version="1.0.0",
        total_entries=10,
        expected_ids=frozenset({"not_lawful_as_supplement", "adulterant", "banned_federal", "banned_state", "controlled_substance", "wada_prohibited", "restricted", "high_risk", "contaminant_risk", "lawful"}),
        required_fields=frozenset({"id", "name", "notes", "authority", "implication"}),
        string_fields=frozenset({"id", "name", "notes", "authority", "implication"}),
        enum_fields={"authority": frozenset({"FDA", "DEA", "WADA", "state", "EU"})},
        memberships=(MembershipSpec("banned_recalled_ingredients.json", "legal_status_enum", frozenset({"not_lawful_as_supplement", "adulterant", "banned_federal", "banned_state", "controlled_substance", "wada_prohibited", "restricted", "high_risk", "contaminant_risk", "lawful"})),),
    ),
    VocabSpec(
        name="manufacturer_trust_tier",
        source_file="manufacturer_trust_tier_vocab.json",
        collection_key="manufacturer_trust_tiers",
        schema_version="1.0.0",
        total_entries=4,
        expected_ids=frozenset({"trusted", "neutral", "violations_minor", "violations_critical"}),
        required_fields=DISPLAY_FIELDS | frozenset({"derivation_rule"}),
        string_fields=DISPLAY_STRING_FIELDS | frozenset({"derivation_rule"}),
        char_limits=DISPLAY_CHAR_LIMITS,
        enum_fields=DISPLAY_ENUMS,
    ),
    VocabSpec(
        name="match_mode",
        source_file="match_mode_vocab.json",
        collection_key="match_modes",
        schema_version="1.0.0",
        total_entries=3,
        expected_ids=frozenset({"active", "disabled", "historical"}),
        required_fields=frozenset({"id", "name", "notes", "fires_in_scoring"}),
        bool_fields=frozenset({"fires_in_scoring"}),
        exact_values_by_id={
            "active": {"fires_in_scoring": True},
            "disabled": {"fires_in_scoring": False},
            "historical": {"fires_in_scoring": False},
        },
        memberships=(MembershipSpec("banned_recalled_ingredients.json", "match_mode", frozenset({"active", "disabled", "historical"})),),
    ),
    VocabSpec(
        name="product_forms",
        source_file="clinical_risk_taxonomy.json",
        collection_key="product_forms",
        schema_version="5.2.0",
        total_entries=None,
        expected_ids=frozenset({"topical_only", "oral", "capsule", "tablet", "powder", "liquid_oral", "culinary_turmeric", "high_potency_extract", "unknown"}),
        required_fields=frozenset({"id", "label", "category", "description"}),
        exact_fields=False,
        string_fields=frozenset({"id", "label", "category", "description"}),
        enum_fields={"category": frozenset({"delivery_route", "potency_class"})},
        char_limits={},
        group_specs=(
            GroupSpec("category", {
                "delivery_route": frozenset({"topical_only", "oral", "capsule", "tablet", "powder", "liquid_oral"}),
                "potency_class": frozenset({"culinary_turmeric", "high_potency_extract", "unknown"}),
            }),
        ),
    ),
    VocabSpec(
        name="profile_flags",
        source_file="clinical_risk_taxonomy.json",
        collection_key="profile_flags",
        schema_version="5.2.0",
        total_entries=None,
        expected_ids=frozenset({"pregnant", "trying_to_conceive", "breastfeeding", "post_op_recovery", "surgery_scheduled", "hypoglycemia_history", "bleeding_history", "severely_immunocompromised"}),
        required_fields=frozenset({"id", "label", "category", "description"}),
        exact_fields=False,
        string_fields=frozenset({"id", "label", "category", "description"}),
        enum_fields={"category": frozenset({"reproductive", "perioperative", "metabolic", "hematologic", "immune"})},
        char_limits={},
        forbidden_ids=frozenset({"first_trimester", "second_trimester", "third_trimester", "kidney_disease_known", "liver_disease_known"}),
    ),
    VocabSpec(
        name="score_contribution_tier",
        source_file="score_contribution_tier_vocab.json",
        collection_key="score_contribution_tiers",
        schema_version="1.0.0",
        total_entries=3,
        expected_ids=frozenset({"tier_1", "tier_2", "tier_3"}),
        required_fields=DISPLAY_FIELDS | frozenset({"tier_rank"}),
        string_fields=DISPLAY_STRING_FIELDS,
        char_limits=DISPLAY_CHAR_LIMITS,
        int_ranges={"tier_rank": (1, 3)},
        exact_values_by_id={"tier_1": {"tier_rank": 1}, "tier_2": {"tier_rank": 2}, "tier_3": {"tier_rank": 3}},
        memberships=(MembershipSpec("backed_clinical_studies.json", "score_contribution", frozenset({"tier_1", "tier_2", "tier_3"})),),
    ),
    VocabSpec(
        name="signal_strength",
        source_file="signal_strength_vocab.json",
        collection_key="signal_strengths",
        schema_version="1.0.0",
        total_entries=3,
        expected_ids=frozenset({"strong", "moderate", "weak"}),
        required_fields=DISPLAY_FIELDS | frozenset({"threshold_definition"}),
        string_fields=DISPLAY_STRING_FIELDS | frozenset({"threshold_definition"}),
        char_limits=DISPLAY_CHAR_LIMITS,
        enum_fields=DISPLAY_ENUMS,
        memberships=(MembershipSpec("caers_adverse_event_signals.json", "signal_strength", frozenset({"strong", "moderate", "weak"}), skip_if_missing=True),),
    ),
)

EXACT_VALUE_SPECS = tuple(spec for spec in SPECS if spec.exact_values_by_id)
FORBIDDEN_ID_SPECS = tuple(spec for spec in SPECS if spec.forbidden_ids)
GROUP_SPECS = tuple(spec for spec in SPECS if spec.group_specs)
MEMBERSHIP_SPECS = tuple(spec for spec in SPECS if spec.memberships)


@pytest.fixture(scope="module")
def vocab_payloads() -> dict[str, dict[str, Any]]:
    return {spec.name: _load_json(spec.source_file) for spec in SPECS}


def _load_json(relpath: str) -> dict[str, Any]:
    with (DATA_DIR / relpath).open(encoding="utf-8") as f:
        return json.load(f)


def _items(spec: VocabSpec, payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    payload = payloads[spec.name]
    assert spec.collection_key in payload, f"{spec.source_file} missing {spec.collection_key}"
    items = payload[spec.collection_key]
    assert isinstance(items, list), f"{spec.collection_key} must be a list"
    return items


def _walk_field_values(obj: Any, key: str, found: set[str]) -> None:
    if isinstance(obj, dict):
        for current_key, value in obj.items():
            if current_key == key and isinstance(value, str):
                found.add(value)
            _walk_field_values(value, key, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_field_values(item, key, found)


def _ids(items: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in items}


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_metadata_contract(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    metadata = vocab_payloads[spec.name]["_metadata"]
    assert metadata["schema_version"] == spec.schema_version
    if spec.total_entries is not None:
        assert metadata["total_entries"] == spec.total_entries
    for field_name, expected_substring in spec.metadata_contains.items():
        assert expected_substring in metadata[field_name]


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_locked_ids(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    items = _items(spec, vocab_payloads)
    actual = _ids(items)
    assert len(items) == len(spec.expected_ids), f"{spec.name} count drift"
    assert actual == spec.expected_ids, (
        f"{spec.name} ids drift: missing={spec.expected_ids - actual}, "
        f"extra={actual - spec.expected_ids}"
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_required_fields(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    for item in _items(spec, vocab_payloads):
        keys = set(item)
        missing = spec.required_fields - keys
        assert not missing, f"{spec.name}:{item.get('id')!r} missing {missing}"
        if spec.exact_fields:
            extra = keys - spec.required_fields
            assert not extra, f"{spec.name}:{item.get('id')!r} unexpected {extra}"


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_ids_are_unique_and_well_formed(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    ids = [item["id"] for item in _items(spec, vocab_payloads)]
    assert len(ids) == len(set(ids)), f"{spec.name} has duplicate IDs"
    for item_id in ids:
        assert spec.id_pattern.match(item_id), f"{spec.name} id {item_id!r} has invalid shape"


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_string_fields_are_nonempty(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    for item in _items(spec, vocab_payloads):
        for field_name in spec.string_fields:
            if field_name not in item:
                continue
            value = item[field_name]
            assert isinstance(value, str) and value.strip(), (
                f"{spec.name}:{item['id']} field {field_name} must be a nonempty string"
            )


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_char_limits(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    for item in _items(spec, vocab_payloads):
        for field_name, limit in spec.char_limits.items():
            if field_name in item:
                assert len(item[field_name]) <= limit, (
                    f"{spec.name}:{item['id']} {field_name} exceeds {limit} chars"
                )


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_enum_fields(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    for item in _items(spec, vocab_payloads):
        for field_name, allowed in spec.enum_fields.items():
            assert item[field_name] in allowed, (
                f"{spec.name}:{item['id']} {field_name}={item[field_name]!r} "
                f"not in {sorted(allowed)}"
            )


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_vocab_typed_fields(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    for item in _items(spec, vocab_payloads):
        for field_name in spec.bool_fields:
            assert isinstance(item[field_name], bool), f"{spec.name}:{item['id']} {field_name} must be bool"
        for field_name, (low, high) in spec.int_ranges.items():
            value = item[field_name]
            assert isinstance(value, int) and low <= value <= high, (
                f"{spec.name}:{item['id']} {field_name}={value!r} outside [{low}, {high}]"
            )


@pytest.mark.parametrize("spec", EXACT_VALUE_SPECS, ids=lambda spec: spec.name)
def test_vocab_exact_values_by_id(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    by_id = {item["id"]: item for item in _items(spec, vocab_payloads)}
    for item_id, expected_fields in spec.exact_values_by_id.items():
        for field_name, expected_value in expected_fields.items():
            assert by_id[item_id][field_name] == expected_value


@pytest.mark.parametrize("spec", FORBIDDEN_ID_SPECS, ids=lambda spec: spec.name)
def test_vocab_forbidden_ids_absent(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    leaked = _ids(_items(spec, vocab_payloads)) & spec.forbidden_ids
    assert not leaked, f"{spec.name} contains forbidden IDs: {leaked}"


@pytest.mark.parametrize("spec", GROUP_SPECS, ids=lambda spec: spec.name)
def test_vocab_group_membership(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    items = _items(spec, vocab_payloads)
    for group_spec in spec.group_specs:
        for group_value, expected_ids in group_spec.expected_by_value.items():
            actual_ids = {item["id"] for item in items if item[group_spec.field_name] == group_value}
            missing = expected_ids - actual_ids
            assert not missing, f"{spec.name}:{group_value} missing {missing}"


@pytest.mark.parametrize("spec", MEMBERSHIP_SPECS, ids=lambda spec: spec.name)
def test_vocab_source_membership(spec: VocabSpec, vocab_payloads: dict[str, dict[str, Any]]) -> None:
    vocab_ids = _ids(_items(spec, vocab_payloads))
    for membership in spec.memberships:
        path = DATA_DIR / membership.source_file
        if membership.skip_if_missing and not path.exists():
            continue
        assert path.exists(), f"source file missing: {membership.source_file}"
        found: set[str] = set()
        _walk_field_values(_load_json(membership.source_file), membership.field_name, found)
        in_scope = found
        if membership.canonical_values is not None:
            in_scope = found & membership.canonical_values
        unknown = in_scope - vocab_ids
        assert not unknown, (
            f"{spec.name}: {membership.source_file}.{membership.field_name} "
            f"values not in vocab: {unknown}"
        )
