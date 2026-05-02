#!/usr/bin/env python3
"""
Contract tests for `data/clinical_indication_vocab.json` (locked v1.0.0,
2026-05-01).

Single source of truth for clinical-indication category labels used by
backed_clinical_studies.json (197 entries, 22 distinct categories).
"""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "clinical_indication_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def indications(vocab):
    return vocab["clinical_indications"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 22
    assert "LOCKED" in md["status"]


def test_exactly_22(indications):
    assert len(indications) == 22


REQUIRED = {"id", "name", "notes", "related_condition_ids", "examples"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def test_required_fields(indications):
    for ind in indications:
        assert set(ind.keys()) == REQUIRED, (
            f"{ind.get('id')!r} drift: missing={REQUIRED - set(ind)}, "
            f"extra={set(ind) - REQUIRED}"
        )


def test_ids_unique_and_snake(indications):
    ids = [i["id"] for i in indications]
    assert len(set(ids)) == len(ids)
    for iid in ids:
        assert ID_PATTERN.match(iid)


def test_canonical_22_ids(indications):
    expected = {
        "adaptogen_stress", "aging_longevity", "anti_inflammatory", "antioxidant",
        "cardiovascular", "cognitive_neurological", "digestive_gut", "eye_health",
        "general_herbs", "hormonal_endocrine", "immune", "joint_bone",
        "liver_detox", "metabolic_blood_sugar", "mineral_supplement",
        "mitochondrial_energy", "probiotics", "skin_hair_collagen", "sleep_mood",
        "sports_performance", "urinary_genitourinary", "vitamin_supplement",
    }
    actual = {i["id"] for i in indications}
    assert actual == expected, f"missing={expected-actual} extra={actual-expected}"


def test_notes_within_char_limit(indications):
    over = [(i["id"], len(i["notes"])) for i in indications if len(i["notes"]) > 200]
    assert not over, f"notes >200 chars: {over}"


def test_examples_nonempty(indications):
    for i in indications:
        assert isinstance(i["examples"], list)
        assert i["examples"], f"{i['id']}: empty examples"


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_every_clinical_study_category_in_vocab(indications):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "backed_clinical_studies.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "category", found)
    vocab_ids = {i["id"] for i in indications}
    unknown = found - vocab_ids
    assert not unknown, f"clinical study categories NOT in vocab: {unknown}"


def test_related_condition_ids_in_condition_vocab(indications):
    cond_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "condition_vocab.json"
    )
    cond_ids = {c["id"] for c in json.load(open(cond_path))["conditions"]}
    for i in indications:
        for cid in i.get("related_condition_ids", []):
            assert cid in cond_ids, f"{i['id']} references {cid} not in condition_vocab"
