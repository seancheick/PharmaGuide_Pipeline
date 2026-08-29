from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from analyze_blob_churn import (
    BlobIntegrityError,
    StoragePayloadFetcher,
    analyze_changed_pairs,
    build_changed_pairs,
    classify_payload_change,
)


def _encoded(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _entry(payload: bytes) -> dict[str, object]:
    digest = _hash(payload)
    return {
        "blob_sha256": digest,
        "storage_path": f"shared/details/sha256/{digest[:2]}/{digest}.json",
        "blob_version": 1,
    }


def test_changed_pair_ledger_is_complete_sorted_and_fingerprinted() -> None:
    first_old = _encoded({"id": "1", "value": "old"})
    first_new = _encoded({"id": "1", "value": "new"})
    unchanged = _encoded({"id": "2", "value": "same"})
    third_old = _encoded({"id": "10", "value": "old"})
    third_new = _encoded({"id": "10", "value": "new"})

    pairs, fingerprint = build_changed_pairs(
        {
            "10": _entry(third_old),
            "2": _entry(unchanged),
            "1": _entry(first_old),
        },
        {
            "1": _entry(first_new),
            "2": _entry(unchanged),
            "10": _entry(third_new),
            "added": _entry(_encoded({"id": "added"})),
        },
    )

    assert [pair.product_id for pair in pairs] == ["1", "10"]
    assert len(fingerprint) == 64
    assert fingerprint == build_changed_pairs(
        {
            "1": _entry(first_old),
            "2": _entry(unchanged),
            "10": _entry(third_old),
        },
        {
            "10": _entry(third_new),
            "2": _entry(unchanged),
            "1": _entry(first_new),
        },
    )[1]


def test_change_classifier_separates_sources_order_from_other_order_and_semantics() -> None:
    sources_old = {"blends": [{"sources": ["cleaning", "detector"]}]}
    sources_new = {"blends": [{"sources": ["detector", "cleaning"]}]}
    other_old = {"warnings": [{"code": "A"}, {"code": "B"}]}
    other_new = {"warnings": [{"code": "B"}, {"code": "A"}]}

    assert classify_payload_change(sources_old, sources_new).classification == (
        "sources_order_only"
    )
    assert classify_payload_change(other_old, other_new).classification == (
        "other_order_only"
    )

    semantic = classify_payload_change(
        {"quality_pillars_v4": {"dose": {"score": 10}}},
        {"quality_pillars_v4": {"dose": {"score": 11}}},
    )
    assert semantic.classification == "semantic"
    assert semantic.changed_fields == ("quality_pillars_v4.dose.score",)


def test_analysis_verifies_content_hashes_and_records_every_pair() -> None:
    old_payload = _encoded({"blends": [{"sources": ["cleaning", "detector"]}]})
    new_payload = _encoded({"blends": [{"sources": ["detector", "cleaning"]}]})
    old_index = {"7": _entry(old_payload)}
    new_index = {"7": _entry(new_payload)}
    pairs, fingerprint = build_changed_pairs(old_index, new_index)
    payloads = {
        pairs[0].old_storage_path: old_payload,
        pairs[0].new_storage_path: new_payload,
    }

    report, ledger = analyze_changed_pairs(
        pairs,
        pair_fingerprint=fingerprint,
        fetch_payload=payloads.__getitem__,
    )

    assert report["changed_pairs"] == 1
    assert report["sources_order_only"] == 1
    assert report["errors"] == 0
    assert ledger[0]["product_id"] == "7"
    assert ledger[0]["classification"] == "sources_order_only"
    assert ledger[0]["old_blob_sha256"] == pairs[0].old_blob_sha256
    assert ledger[0]["new_blob_sha256"] == pairs[0].new_blob_sha256

    payloads[pairs[0].old_storage_path] = b"not the indexed object"
    with pytest.raises(BlobIntegrityError, match="old blob hash mismatch"):
        analyze_changed_pairs(
            pairs,
            pair_fingerprint=fingerprint,
            fetch_payload=payloads.__getitem__,
        )


def test_storage_fetcher_falls_back_to_the_explicit_quarantine_date() -> None:
    digest = "a" * 64
    active_path = f"shared/details/sha256/aa/{digest}.json"
    quarantine_path = f"shared/quarantine/2026-08-28/aa/{digest}.json"

    class FakeBucket:
        def __init__(self) -> None:
            self.paths: list[str] = []

        def download(self, path: str) -> bytes:
            self.paths.append(path)
            if path == active_path:
                raise RuntimeError("not found")
            if path == quarantine_path:
                return b"payload"
            raise AssertionError(path)

    bucket = FakeBucket()
    fetch = StoragePayloadFetcher(bucket, quarantine_dates=("2026-08-28",))

    assert fetch(active_path) == b"payload"
    assert bucket.paths == [active_path, quarantine_path]


def test_committed_full_population_report_has_a_complete_pair_ledger() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report = json.loads(
        (repo_root / "reports/storage_cleanup/churn_diagnosis_reproducible_2026-08-29.json")
        .read_text()
    )
    ledger = json.loads(
        (repo_root / "reports/storage_cleanup/churn_pair_ledger_2026-08-29.json")
        .read_text()
    )
    pairs = ledger["pairs"]

    assert report["changed_pairs"] == ledger["pair_count"] == len(pairs) == 1192
    assert report["pair_fingerprint_sha256"] == ledger["pair_fingerprint_sha256"]
    assert report["old_index_sha256"] == ledger["old_index_sha256"]
    assert report["new_index_sha256"] == ledger["new_index_sha256"]
    assert report["errors"] == 0
    assert len({pair["product_id"] for pair in pairs}) == len(pairs)

    classes = Counter(pair["classification"] for pair in pairs)
    assert classes == {
        "sources_order_only": 1044,
        "semantic": 148,
    }
