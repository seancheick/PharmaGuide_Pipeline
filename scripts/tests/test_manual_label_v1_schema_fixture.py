from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "submission_review"
    / "fixtures"
    / "manual_label_v1_cases.json"
)
FIXTURE_SHA256 = "6dd08b64eaab05530e4c3b2e97e1e483bc203c5ed7750affb0cd981db086767a"


def test_manual_label_v1_fixture_contract_stays_checksum_pinned() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(
        fixture,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == FIXTURE_SHA256


def test_manual_label_v1_accepts_and_rejects_shared_contract_cases() -> None:
    from product_submission_import import (
        SubmissionImportError,
        _validate_label_payload,
    )

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        if case["valid"]:
            _validate_label_payload(case["payload"])
        else:
            with pytest.raises(SubmissionImportError):
                _validate_label_payload(case["payload"])
