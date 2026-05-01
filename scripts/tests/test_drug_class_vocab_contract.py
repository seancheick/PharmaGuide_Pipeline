#!/usr/bin/env python3
"""
Contract tests for `data/drug_class_vocab.json` (locked v1.0.0, 2026-04-30).

Single source of truth for drug-class labels migrated from the hardcoded
`drugClassLabels` map in `lib/core/constants/schema_ids.dart` (13 user-
selectable) plus 8 rule-only drug classes referenced by interaction
rules but not surfaced as profile picks (CYP substrates, narrow families).

Locked decisions:
  - Exactly 21 drug classes (13 user_selectable + 8 rule-only)
  - Lean schema + extras: id, name, notes, examples, rx_status, user_selectable
  - All IDs lowercase snake_case
  - rx_status enum: rx_only | otc | mixed
  - Cross-data: every drug_class_id in interaction_rules must be in vocab
"""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "drug_class_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def drug_classes(vocab):
    return vocab["drug_classes"]


def test_metadata_block_present(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 21
    assert md["user_selectable_count"] == 13
    assert md["rule_only_count"] == 8
    assert "LOCKED" in md["status"]


def test_exactly_21_drug_classes_locked(drug_classes):
    assert len(drug_classes) == 21


def test_user_selectable_split_correct(drug_classes):
    selectable = [d for d in drug_classes if d.get("user_selectable")]
    rule_only = [d for d in drug_classes if not d.get("user_selectable")]
    assert len(selectable) == 13, f"expected 13 user_selectable; got {len(selectable)}"
    assert len(rule_only) == 8, f"expected 8 rule-only; got {len(rule_only)}"


REQUIRED_FIELDS = {"id", "name", "notes", "examples", "rx_status", "user_selectable"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ALLOWED_RX_STATUS = {"rx_only", "otc", "mixed"}


def test_required_fields_present(drug_classes):
    for d in drug_classes:
        keys = set(d.keys())
        missing = REQUIRED_FIELDS - keys
        extra = keys - REQUIRED_FIELDS
        assert not missing, f"drug_class {d.get('id')!r} missing: {missing}"
        assert not extra, f"drug_class {d['id']!r} extra fields: {extra}"


def test_every_id_unique_and_snake_case(drug_classes):
    ids = [d["id"] for d in drug_classes]
    assert len(set(ids)) == len(ids), "duplicate drug_class IDs"
    for did in ids:
        assert ID_PATTERN.match(did), f"id {did!r} not snake_case"


def test_user_selectable_13_match_schema_ids_dart(drug_classes):
    """The 13 user_selectable IDs must match `drugClasses` in
    lib/core/constants/schema_ids.dart"""
    expected = {
        "anticoagulants", "antiplatelets", "nsaids", "antihypertensives",
        "hypoglycemics", "thyroid_medications", "sedatives",
        "immunosuppressants", "statins", "antidepressants_ssri_snri",
        "maois", "cardiac_glycosides", "anticholinergics",
    }
    actual = {d["id"] for d in drug_classes if d.get("user_selectable")}
    assert actual == expected, f"missing={expected-actual} extra={actual-expected}"


def test_notes_within_char_limit(drug_classes):
    over = [(d["id"], len(d["notes"])) for d in drug_classes if len(d["notes"]) > 200]
    assert not over, f"notes exceed 200 chars: {over}"
    empty = [d["id"] for d in drug_classes if not d["notes"].strip()]
    assert not empty, f"empty notes: {empty}"


def test_examples_nonempty(drug_classes):
    for d in drug_classes:
        assert isinstance(d["examples"], list), f"{d['id']}: examples not list"
        assert d["examples"], f"{d['id']}: empty examples list"
        for ex in d["examples"]:
            assert isinstance(ex, str) and ex.strip(), f"{d['id']}: bad example {ex!r}"


def test_rx_status_in_allowed_enum(drug_classes):
    for d in drug_classes:
        assert d["rx_status"] in ALLOWED_RX_STATUS, (
            f"{d['id']} rx_status={d['rx_status']!r}"
        )


def test_user_selectable_is_bool(drug_classes):
    for d in drug_classes:
        assert isinstance(d["user_selectable"], bool), (
            f"{d['id']} user_selectable not bool"
        )


# ---------------------------------------------------------------------------
# Cross-data membership
# ---------------------------------------------------------------------------


def _walk_drug_class_ids(obj, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "drug_class_id" and isinstance(v, str):
                found.add(v)
            elif k == "drug_classes" and isinstance(v, list):
                for x in v:
                    if isinstance(x, str):
                        found.add(x)
            _walk_drug_class_ids(v, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk_drug_class_ids(x, found)


def test_every_interaction_rule_drug_class_id_in_vocab(drug_classes):
    found = set()
    for relpath in (
        "ingredient_interaction_rules.json",
        "ingredient_interaction_rules_Reviewed.json",
        "clinical_risk_taxonomy.json",
    ):
        path = os.path.join(os.path.dirname(__file__), "..", "data", relpath)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            _walk_drug_class_ids(json.load(f), found)

    vocab_ids = {d["id"] for d in drug_classes}
    unknown = found - vocab_ids
    unknown = {x for x in unknown if x and x not in {"none", "n/a"}}
    assert not unknown, (
        f"drug_class_ids in source data NOT in vocab: {unknown}. "
        "Either add to vocab or fix the source data."
    )
