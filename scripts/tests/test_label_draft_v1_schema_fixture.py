"""The partial-draft contract (label_draft_v1) is paired across repos.

A draft may carry explicit unknowns; it is not an approved label. The same
fixture file lives in the app repo (Deno validator) and here (Python
validator); both pin its checksum so the two validators cannot drift.
"""
from __future__ import annotations

import hashlib
import copy
import json
from pathlib import Path

import pytest

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "submission_review"
    / "fixtures"
    / "label_draft_v1_cases.json"
)
FIXTURE_SHA256 = "849eb10a21f5f4901b579a3f7be070c0eaf861bb72551c30f27bebbe1cb04c15"
MUTATIONS_SHA256 = "a4b24d91433ab34e7c4eef22e8f75e09d9fddc37dddf637d0fe06ade8050c0c4"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", json.loads(FIXTURE_PATH.with_name("label_draft_v1_mutations.json").read_text())["cases"], ids=lambda c: c["name"])
def test_paired_provenance_and_malformed_cases(case):
    from submission_review.extraction.envelope import LabelDraftError, validate_label_draft_v1
    draft = copy.deepcopy(_fixture()["cases"][0]["payload"])
    for change in case["changes"]:
        target = draft
        for part in change["path"][:-1]:
            target = target[part]
        target[change["path"][-1]] = change["value"]
    def remove_refs(value):
        if isinstance(value, dict):
            value.pop("input_id", None)
            for child in value.values():
                remove_refs(child)
        elif isinstance(value, list):
            for child in value:
                remove_refs(child)
    if case.get("remove_input_refs"):
        remove_refs(draft)
    if case["valid"]:
        assert validate_label_draft_v1(draft) == draft
    else:
        with pytest.raises(LabelDraftError):
            validate_label_draft_v1(draft)


def test_label_draft_v1_fixture_contract_stays_checksum_pinned() -> None:
    canonical = json.dumps(
        _fixture(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == FIXTURE_SHA256
    mutations = json.loads(FIXTURE_PATH.with_name("label_draft_v1_mutations.json").read_text())
    canonical = json.dumps(mutations, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == MUTATIONS_SHA256


def test_label_draft_v1_accepts_and_rejects_shared_contract_cases() -> None:
    from submission_review.extraction.envelope import (
        LabelDraftError,
        validate_label_draft_v1,
    )

    for case in _fixture()["cases"]:
        if case["valid"]:
            validated = validate_label_draft_v1(case["payload"])
            assert validated["schema_version"] == "label_draft_v1", case["name"]
        else:
            with pytest.raises(LabelDraftError):
                validate_label_draft_v1(case["payload"])


def test_label_draft_v1_never_carries_model_minted_identities() -> None:
    from submission_review.extraction.envelope import FORBIDDEN_KEYS

    assert {"canonical_id", "cui", "unii", "pmid", "score", "verdict"} <= FORBIDDEN_KEYS


def test_valid_drafts_are_returned_unmodified() -> None:
    # Validation never normalizes label text; scoring normalization is downstream.
    from submission_review.extraction.envelope import validate_label_draft_v1

    for case in _fixture()["cases"]:
        if case["valid"]:
            assert validate_label_draft_v1(case["payload"]) == case["payload"]
