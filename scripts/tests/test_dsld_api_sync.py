#!/usr/bin/env python3
"""Tests for dsld_api_sync pure helpers and non-network command paths."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_extract_ids_from_hits_response():
    from dsld_api_sync import _extract_ids_from_response

    response = {
        "hits": [
            {"_source": {"id": 101}},
            {"_source": {"id": 202}},
        ]
    }

    assert _extract_ids_from_response(response) == [101, 202]


def test_extract_ids_from_hits_response_uses_hit_id_fallback():
    from dsld_api_sync import _extract_ids_from_response

    response = {
        "hits": [
            {"_id": "101", "_source": {"brandName": "A"}},
            {"_id": "202", "_source": {"brandName": "B"}},
        ]
    }

    assert _extract_ids_from_response(response) == [101, 202]


def test_extract_ids_from_list_response():
    from dsld_api_sync import _extract_ids_from_response

    response = [{"id": 11}, {"id": 22}, {"missing": 33}]

    assert _extract_ids_from_response(response) == [11, 22]


def test_write_raw_label_writes_compact_json(tmp_path):
    from dsld_api_sync import write_raw_label

    label = {"id": 13418, "fullName": "Test", "ingredientRows": []}
    output = write_raw_label(label, tmp_path)

    assert output == tmp_path / "13418.json"
    assert output.exists()
    assert output.read_text(encoding="utf-8") == '{"id":13418,"fullName":"Test","ingredientRows":[]}'


def test_write_raw_label_snapshot_creates_snapshot_subdir(tmp_path):
    from dsld_api_sync import write_raw_label

    label = {"id": 241695, "fullName": "Snapshot", "ingredientRows": []}
    output = write_raw_label(label, tmp_path, snapshot=True)

    assert "_snapshots" in str(output)
    assert output.name == "241695.json"
    assert output.exists()


def test_write_raw_label_requires_id(tmp_path):
    from dsld_api_sync import write_raw_label

    with pytest.raises(ValueError, match="missing 'id'"):
        write_raw_label({"fullName": "No ID"}, tmp_path)


def test_parity_check_ignores_source_and_src():
    from dsld_api_sync import parity_check

    api_label = {"id": 1, "fullName": "Product", "_source": "api", "src": "api/label/1"}
    ref_label = {"id": 1, "fullName": "Product", "_source": "manual", "src": "manual/file.json"}

    report = parity_check(api_label, ref_label)

    assert report["parity_score"] == 1.0
    assert report["value_mismatches"] == {}
    assert report["type_mismatches"] == {}


def test_parity_check_detects_nested_structure_difference():
    from dsld_api_sync import parity_check

    api_label = {
        "id": 1,
        "ingredientRows": [{"name": "A", "forms": []}],
    }
    ref_label = {
        "id": 1,
        "ingredientRows": [{"name": "A", "amount": "10 mg"}],
    }

    report = parity_check(api_label, ref_label)

    assert "ingredientRows" in report["nested_diffs"]
    assert report["parity_score"] < 1.0


def test_build_parser_has_expected_subcommands():
    from dsld_api_sync import build_parser

    parser = build_parser()
    args = parser.parse_args(["sync-query", "--query", "vitamin d", "--output-dir", "/tmp/out"])

    assert args.command == "sync-query"
    assert args.query == "vitamin d"
    assert args.output_dir == "/tmp/out"


def test_check_version_returns_failure_when_client_raises(monkeypatch, capsys):
    import dsld_api_sync

    class FakeClient:
        def get_version(self):
            raise RuntimeError("HTML instead of JSON")

    monkeypatch.setattr(dsld_api_sync, "DSLDApiClient", FakeClient)

    code = dsld_api_sync._cmd_check_version(type("Args", (), {})())
    captured = capsys.readouterr()

    assert code == 1
    assert "FAILED" in captured.err


def test_check_version_prints_structured_version(monkeypatch, capsys):
    import dsld_api_sync

    class FakeClient:
        def get_version(self):
            return {
                "title": "DSLD API",
                "config": "production",
                "version": "9.4.0",
                "versionTimeStamp": "January 2026",
            }

    monkeypatch.setattr(dsld_api_sync, "DSLDApiClient", FakeClient)

    code = dsld_api_sync._cmd_check_version(type("Args", (), {})())
    captured = capsys.readouterr()

    assert code == 0
    assert "version: 9.4.0" in captured.out
    assert "config: production" in captured.out


def test_probe_reports_missing_reference_file(monkeypatch, capsys, tmp_path):
    import dsld_api_sync

    class FakeClient:
        def fetch_label(self, dsld_id):
            return {"id": dsld_id, "fullName": "Test", "brandName": "Brand"}

    monkeypatch.setattr(dsld_api_sync, "DSLDApiClient", FakeClient)
    args = type("Args", (), {"id": 13418, "reference": str(tmp_path / "missing.json")})()

    code = dsld_api_sync._cmd_probe(args)
    captured = capsys.readouterr()

    assert code == 1
    assert "reference file not found" in captured.err


def test_canonical_payload_sha256_ignores_source_metadata():
    from dsld_api_sync import canonical_payload_sha256

    label_a = {"id": 1, "fullName": "Product", "_source": "api", "ingredientRows": []}
    label_b = {"ingredientRows": [], "fullName": "Product", "id": 1, "_source": "manual"}

    assert canonical_payload_sha256(label_a) == canonical_payload_sha256(label_b)


def test_route_label_to_form_uses_langual_code():
    from dsld_api_sync import route_label_to_form

    label = {"physicalState": {"langualCode": "E0176", "langualCodeDescription": "Gummy or Jelly"}}

    assert route_label_to_form(label) == "gummies"


def test_route_label_to_form_maps_other_codes_to_other():
    from dsld_api_sync import route_label_to_form

    label = {"physicalState": {"langualCode": "E0177", "langualCodeDescription": "Unknown"}}

    assert route_label_to_form(label) == "other"


def test_route_label_to_form_falls_back_to_filter_code():
    from dsld_api_sync import route_label_to_form

    label = {"physicalState": {}, "productType": {}}

    assert route_label_to_form(label, filter_form_code="e0161") == "softgels"


def test_classify_label_change_new_changed_and_unchanged():
    from dsld_api_sync import classify_label_change

    label = {
        "id": 13418,
        "productVersionCode": "v1",
        "offMarket": False,
        "fullName": "Product",
        "ingredientRows": [],
    }

    new_result = classify_label_change(label, existing_state=None, canonical_form="gummies")
    assert new_result["status"] == "new"

    existing_state = {
        "id": 13418,
        "product_version_code": "v1",
        "off_market": False,
        "canonical_form": "gummies",
        "payload_sha256": new_result["payload_sha256"],
    }

    unchanged_result = classify_label_change(label, existing_state=existing_state, canonical_form="gummies")
    assert unchanged_result["status"] == "unchanged"

    changed_version = dict(label)
    changed_version["productVersionCode"] = "v2"
    changed_result = classify_label_change(changed_version, existing_state=existing_state, canonical_form="gummies")
    assert changed_result["status"] == "changed"


def test_build_parser_supports_sync_filter_and_sync_delta():
    from dsld_api_sync import build_parser

    parser = build_parser()

    args = parser.parse_args([
        "sync-filter",
        "--supplement-form",
        "e0176",
        "--status",
        "2",
        "--canonical-root",
        "raw_data/forms",
        "--state-file",
        "/tmp/dsld_state.json",
    ])
    assert args.command == "sync-filter"
    assert args.supplement_form == "e0176"
    assert args.canonical_root == "raw_data/forms"

    args = parser.parse_args([
        "sync-delta",
        "--brand",
        "Olly",
        "--canonical-root",
        "raw_data/forms",
        "--state-file",
        "/tmp/dsld_state.json",
        "--delta-output-dir",
        "/tmp/delta",
    ])
    assert args.command == "sync-delta"
    assert args.brand == "Olly"
    assert args.delta_output_dir == "/tmp/delta"
    assert args.dated_delta is False


def test_build_parser_supports_dated_delta_flag():
    from dsld_api_sync import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "sync-delta",
        "--brand",
        "Olly",
        "--canonical-root",
        "raw_data/forms",
        "--state-file",
        "/tmp/dsld_state.json",
        "--delta-output-dir",
        "/tmp/delta",
        "--dated-delta",
    ])

    assert args.command == "sync-delta"
    assert args.dated_delta is True


def test_build_parser_supports_sync_delta_report_dir():
    from dsld_api_sync import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "sync-delta",
        "--brand",
        "Olly",
        "--canonical-root",
        "raw_data/forms",
        "--state-file",
        "/tmp/dsld_state.json",
        "--report-dir",
        "/tmp/reports/olly",
    ])

    assert args.command == "sync-delta"
    assert args.report_dir == "/tmp/reports/olly"


def test_sync_filter_writes_canonical_form_and_state(monkeypatch, tmp_path):
    import dsld_api_sync

    class FakeClient:
        def search_filter(self, *, size=1000, from_=0, **filters):
            return {"hits": [{"_source": {"id": 101}}]}

        def fetch_label(self, dsld_id):
            return {
                "id": dsld_id,
                "fullName": "Gummy Product",
                "brandName": "Brand",
                "productVersionCode": "v1",
                "offMarket": False,
                "ingredientRows": [],
                "physicalState": {"langualCode": "E0176", "langualCodeDescription": "Gummy or Jelly"},
            }

    monkeypatch.setattr(dsld_api_sync, "DSLDApiClient", FakeClient)

    canonical_root = tmp_path / "forms"
    state_file = tmp_path / "state.json"
    args = type(
        "Args",
        (),
        {
            "supplement_form": "e0176",
            "ingredient_name": None,
            "ingredient_category": None,
            "brand": None,
            "status": 2,
            "date_start": None,
            "date_end": None,
            "limit": 10,
            "snapshot": False,
            "staging_dir": None,
            "canonical_root": str(canonical_root),
            "state_file": str(state_file),
        },
    )()

    code = dsld_api_sync._cmd_sync_filter(args)

    assert code == 0
    assert (canonical_root / "gummies" / "101.json").exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["labels"]["101"]["canonical_form"] == "gummies"


def test_sync_delta_writes_only_changed_labels_to_delta_dir(monkeypatch, tmp_path):
    import dsld_api_sync

    class FakeClient:
        def search_filter(self, *, size=1000, from_=0, **filters):
            return {"hits": [{"_source": {"id": 101}}, {"_source": {"id": 202}}]}

        def fetch_label(self, dsld_id):
            labels = {
                101: {
                    "id": 101,
                    "fullName": "Existing Product",
                    "brandName": "Brand",
                    "productVersionCode": "v1",
                    "offMarket": False,
                    "ingredientRows": [],
                    "physicalState": {"langualCode": "E0176", "langualCodeDescription": "Gummy or Jelly"},
                },
                202: {
                    "id": 202,
                    "fullName": "New Product",
                    "brandName": "Brand",
                    "productVersionCode": "v1",
                    "offMarket": False,
                    "ingredientRows": [],
                    "physicalState": {"langualCode": "E0161", "langualCodeDescription": "Softgel Capsule"},
                },
            }
            return labels[dsld_id]

    monkeypatch.setattr(dsld_api_sync, "DSLDApiClient", FakeClient)

    canonical_root = tmp_path / "forms"
    state_file = tmp_path / "state.json"
    existing_label = {
        "id": 101,
        "fullName": "Existing Product",
        "brandName": "Brand",
        "productVersionCode": "v1",
        "offMarket": False,
        "ingredientRows": [],
        "physicalState": {"langualCode": "E0176", "langualCodeDescription": "Gummy or Jelly"},
    }
    state = {
        "_metadata": {"version": "1.0"},
        "labels": {
            "101": {
                "id": 101,
                "brand_name": "Brand",
                "product_version_code": "v1",
                "off_market": False,
                "entry_date": None,
                "canonical_form": "gummies",
                "payload_sha256": dsld_api_sync.canonical_payload_sha256(existing_label),
                "current_raw_path": str(canonical_root / "gummies" / "101.json"),
                "first_seen_at": "2026-03-30T00:00:00+00:00",
                "last_seen_at": "2026-03-30T00:00:00+00:00",
                "last_sync_source": "seed",
                "last_status_filter": 2,
                "last_query_context": {},
            }
        },
    }
    state_file.write_text(json.dumps(state), encoding="utf-8")

    delta_dir = tmp_path / "delta"
    args = type(
        "Args",
        (),
        {
            "supplement_form": None,
            "ingredient_name": None,
            "ingredient_category": None,
            "brand": "Brand",
            "status": 2,
            "date_start": None,
            "date_end": None,
            "limit": 10,
            "canonical_root": str(canonical_root),
            "state_file": str(state_file),
            "delta_output_dir": str(delta_dir),
            "dated_delta": False,
            "force_refetch": False,
        },
    )()

    code = dsld_api_sync._cmd_sync_delta(args)

    assert code == 0
    assert not (delta_dir / "101.json").exists()
    assert (delta_dir / "202.json").exists()
    assert (canonical_root / "softgels" / "202.json").exists()


def test_sync_delta_writes_to_fresh_timestamped_delta_subdir(monkeypatch, tmp_path):
    import dsld_api_sync

    class FakeClient:
        def search_filter(self, *, size=1000, from_=0, **filters):
            return {"hits": [{"_source": {"id": 202}}]}

        def fetch_label(self, dsld_id):
            return {
                "id": dsld_id,
                "fullName": "New Product",
                "brandName": "Brand",
                "productVersionCode": "v1",
                "offMarket": False,
                "ingredientRows": [],
                "physicalState": {"langualCode": "E0161", "langualCodeDescription": "Softgel Capsule"},
            }

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            from datetime import datetime

            return datetime(2026, 3, 30, 15, 4, 5, tzinfo=tz)

    monkeypatch.setattr(dsld_api_sync, "DSLDApiClient", FakeClient)
    monkeypatch.setattr(dsld_api_sync, "datetime", FixedDateTime)

    canonical_root = tmp_path / "forms"
    state_file = tmp_path / "state.json"
    delta_root = tmp_path / "delta"
    args = type(
        "Args",
        (),
        {
            "supplement_form": None,
            "ingredient_name": None,
            "ingredient_category": None,
            "brand": "Brand",
            "status": 2,
            "date_start": None,
            "date_end": None,
            "limit": 10,
            "canonical_root": str(canonical_root),
            "state_file": str(state_file),
            "delta_output_dir": str(delta_root),
            "dated_delta": True,
            "report_dir": None,
            "force_refetch": False,
        },
    )()

    code = dsld_api_sync._cmd_sync_delta(args)

    assert code == 0
    stamped_dir = delta_root / "2026-03-30T15-04-05"
    assert (stamped_dir / "202.json").exists()
    assert not (delta_root / "202.json").exists()


def test_sync_delta_writes_json_report(monkeypatch, tmp_path):
    import dsld_api_sync

    class FakeClient:
        def search_filter(self, *, size=1000, from_=0, **filters):
            return {"hits": [{"_source": {"id": 101}}, {"_source": {"id": 202}}]}

        def fetch_label(self, dsld_id):
            labels = {
                101: {
                    "id": 101,
                    "fullName": "Existing Product",
                    "brandName": "Brand",
                    "productVersionCode": "v1",
                    "offMarket": False,
                    "ingredientRows": [],
                    "physicalState": {"langualCode": "E0176", "langualCodeDescription": "Gummy or Jelly"},
                },
                202: {
                    "id": 202,
                    "fullName": "New Product",
                    "brandName": "Brand",
                    "productVersionCode": "v1",
                    "offMarket": True,
                    "ingredientRows": [],
                    "physicalState": {"langualCode": "E0161", "langualCodeDescription": "Softgel Capsule"},
                },
            }
            return labels[dsld_id]

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            from datetime import datetime

            return datetime(2026, 3, 30, 15, 4, 5, tzinfo=tz)

    monkeypatch.setattr(dsld_api_sync, "DSLDApiClient", FakeClient)
    monkeypatch.setattr(dsld_api_sync, "datetime", FixedDateTime)

    canonical_root = tmp_path / "forms"
    state_file = tmp_path / "state.json"
    delta_root = tmp_path / "delta"
    report_root = tmp_path / "reports"
    existing_label = {
        "id": 101,
        "fullName": "Existing Product",
        "brandName": "Brand",
        "productVersionCode": "v1",
        "offMarket": False,
        "ingredientRows": [],
        "physicalState": {"langualCode": "E0176", "langualCodeDescription": "Gummy or Jelly"},
    }
    state = {
        "_metadata": {"version": "1.0"},
        "labels": {
            "101": {
                "id": 101,
                "brand_name": "Brand",
                "product_version_code": "v1",
                "off_market": False,
                "entry_date": None,
                "canonical_form": "gummies",
                "payload_sha256": dsld_api_sync.canonical_payload_sha256(existing_label),
                "current_raw_path": str(canonical_root / "gummies" / "101.json"),
                "first_seen_at": "2026-03-30T00:00:00+00:00",
                "last_seen_at": "2026-03-30T00:00:00+00:00",
                "last_sync_source": "seed",
                "last_status_filter": 2,
                "last_query_context": {},
            }
        },
    }
    state_file.write_text(json.dumps(state), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "supplement_form": None,
            "ingredient_name": None,
            "ingredient_category": None,
            "brand": "Brand",
            "status": 2,
            "date_start": None,
            "date_end": None,
            "limit": 10,
            "canonical_root": str(canonical_root),
            "state_file": str(state_file),
            "delta_output_dir": str(delta_root),
            "dated_delta": True,
            "report_dir": str(report_root),
            "force_refetch": False,
        },
    )()

    code = dsld_api_sync._cmd_sync_delta(args)

    assert code == 0
    report_path = report_root / "2026-03-30T15-04-05.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["summary"]["candidate_count"] == 2
    assert report["summary"]["new_count"] == 1
    assert report["summary"]["unchanged_count"] == 1
    assert report["summary"]["delta_written"] == 1
    assert report["summary"]["off_market_count"] == 1
    assert report["delta_output_dir"].endswith("/delta/2026-03-30T15-04-05")
    assert report["new_ids"] == [202]
    assert report["unchanged_ids"] == [101]
    assert report["off_market_ids"] == [202]
