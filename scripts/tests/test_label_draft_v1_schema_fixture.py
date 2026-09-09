"""The partial-draft contract (label_draft_v1) is paired across repos.

A draft may carry explicit unknowns; it is not an approved label. The same
fixture file lives in the app repo (Deno validator) and here (Python
validator); both pin its checksum so the two validators cannot drift.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "submission_review"
    / "fixtures"
    / "label_draft_v1_cases.json"
)
FIXTURE_SHA256 = "6e7e5499704a3b142aa9d85dbadf717f4b2fb1d46bd01b0bda3bc5ad4bdf2924"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_label_draft_v1_fixture_contract_stays_checksum_pinned() -> None:
    canonical = json.dumps(
        _fixture(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == FIXTURE_SHA256


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
