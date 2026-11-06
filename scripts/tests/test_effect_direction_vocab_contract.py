#!/usr/bin/env python3
"""Contract tests for `data/effect_direction_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "effect_direction_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["effect_directions"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 5


def test_exactly_5(items):
    assert len(items) == 5


REQUIRED = {"id", "name", "notes", "multiplier"}


def test_required_fields(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_5(items):
    expected = {"positive_strong", "positive_weak", "mixed", "null", "negative"}
    assert {i["id"] for i in items} == expected


def test_multipliers_match_scoring_config(items):
    cfg_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "scoring_config.json"
    )
    cfg = json.load(open(cfg_path))
    expected = cfg["section_C_evidence_research"]["effect_direction_multipliers"]
    actual = {i["id"]: i["multiplier"] for i in items}
    assert actual == expected, (
        f"vocab multipliers diverge from scoring_config: "
        f"vocab={actual} vs cfg={expected}"
    )


def test_notes_within_char_limit(items):
    for i in items:
        assert len(i["notes"]) <= 200


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_every_clinical_study_effect_direction_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "backed_clinical_studies.json"
    )
    found = set()
    data = json.load(open(path, encoding="utf-8"))
    # Sean's November6 source-specific interpretation preserves the observed
    # label. It does not add moderate to the five legacy multiplier meanings.
    approved = [r for r in data["backed_clinical_studies"] if r["id"] == "INGR_L_GLUTAMINE"]
    assert len(approved) == 1
    record = approved[0]
    assert record["effect_direction"] == "positive_moderate"
    qualifying = [c for c in record["study_contexts"] if c.get("scoring_eligible")]
    assert len(qualifying) == 1
    assert qualifying[0]["context_id"] == "l_glutamine_30108163_pi_ibsd_primary"
    assert qualifying[0]["source_pmids"] == ["30108163"]
    assert qualifying[0]["review_status"] == "clinician_approved"
    # Remove only that approved top-level observed value. Any other record or
    # nested undeclared effect label must still fail the original vocabulary guard.
    record = {k: v for k, v in record.items() if k != "effect_direction"}
    data["backed_clinical_studies"] = [
        record if r["id"] == "INGR_L_GLUTAMINE" else r
        for r in data["backed_clinical_studies"]
    ]
    _walk(data, "effect_direction", found)
    vocab_ids = {i["id"] for i in items}
    assert found <= vocab_ids, f"effect_directions NOT in vocab: {found - vocab_ids}"


def test_legacy_reference_weights_are_not_advertised_as_current_scoring(vocab, items):
    assert 'legacy v3' in vocab['_metadata']['purpose'].lower()
    assert 'quality_score.json' in vocab['_metadata']['alignment']
    assert all('multiplier' not in item['notes'].lower() for item in items)
