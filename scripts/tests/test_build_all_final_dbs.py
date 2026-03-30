"""Tests for build_all_final_dbs.py."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def test_filter_pairs_supports_case_insensitive_include_and_exclude():
    from build_all_final_dbs import filter_pairs

    enriched = ["/tmp/pure-enriched", "/tmp/nordic-enriched", "/tmp/nature-enriched"]
    scored = ["/tmp/pure-scored", "/tmp/nordic-scored", "/tmp/nature-scored"]
    paired = ["Pure-2026", "Nordic-Naturals-2026", "Nature-Made-2026"]

    selected_enriched, selected_scored, selected_paired = filter_pairs(
        enriched,
        scored,
        paired,
        include_patterns=["nordic", "nature"],
        exclude_patterns=["made"],
    )

    assert selected_paired == ["Nordic-Naturals-2026"]
    assert selected_enriched == ["/tmp/nordic-enriched"]
    assert selected_scored == ["/tmp/nordic-scored"]


def test_filter_pairs_returns_all_when_no_filters():
    from build_all_final_dbs import filter_pairs

    enriched = ["/tmp/a-enriched"]
    scored = ["/tmp/a-scored"]
    paired = ["A-Brand"]

    selected_enriched, selected_scored, selected_paired = filter_pairs(
        enriched,
        scored,
        paired,
        include_patterns=[],
        exclude_patterns=[],
    )

    assert selected_paired == paired
    assert selected_enriched == enriched
    assert selected_scored == scored


def test_filter_pairs_by_explicit_prefixes():
    from build_all_final_dbs import filter_pairs_by_prefixes

    enriched = ["/tmp/pure-enriched", "/tmp/nordic-enriched", "/tmp/nature-enriched"]
    scored = ["/tmp/pure-scored", "/tmp/nordic-scored", "/tmp/nature-scored"]
    paired = ["Pure-2026", "Nordic-2026", "Nature-2026"]

    selected_enriched, selected_scored, selected_paired = filter_pairs_by_prefixes(
        enriched,
        scored,
        paired,
        {"Nordic-2026", "Nature-2026"},
    )

    assert selected_paired == ["Nordic-2026", "Nature-2026"]
    assert selected_enriched == ["/tmp/nordic-enriched", "/tmp/nature-enriched"]
    assert selected_scored == ["/tmp/nordic-scored", "/tmp/nature-scored"]


def test_compute_directory_fingerprint_changes_when_json_changes(tmp_path):
    from build_all_final_dbs import compute_directory_fingerprint

    data_dir = tmp_path / "enriched"
    data_dir.mkdir()
    file_path = data_dir / "a.json"
    file_path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    before = compute_directory_fingerprint(str(data_dir))
    file_path.write_text(json.dumps({"a": 2}), encoding="utf-8")
    after = compute_directory_fingerprint(str(data_dir))

    assert before != after


def test_filter_changed_pairs_returns_only_new_or_modified_pairs():
    from build_all_final_dbs import filter_changed_pairs

    current_state = {
        "Nordic-2026": {"combined_fingerprint": "same"},
        "Pure-2026": {"combined_fingerprint": "changed"},
        "Olly-2026": {"combined_fingerprint": "new"},
    }
    previous_state = {
        "Nordic-2026": {"combined_fingerprint": "same"},
        "Pure-2026": {"combined_fingerprint": "old"},
    }

    enriched = ["/tmp/nordic-enriched", "/tmp/pure-enriched", "/tmp/olly-enriched"]
    scored = ["/tmp/nordic-scored", "/tmp/pure-scored", "/tmp/olly-scored"]
    paired = ["Nordic-2026", "Pure-2026", "Olly-2026"]

    selected_enriched, selected_scored, selected_paired = filter_changed_pairs(
        enriched,
        scored,
        paired,
        current_state=current_state,
        previous_state=previous_state,
    )

    assert selected_paired == ["Pure-2026", "Olly-2026"]
    assert selected_enriched == ["/tmp/pure-enriched", "/tmp/olly-enriched"]
    assert selected_scored == ["/tmp/pure-scored", "/tmp/olly-scored"]


def test_build_pair_output_dir_sanitizes_brand_prefix():
    from build_all_final_dbs import build_pair_output_dir

    output_dir = build_pair_output_dir("/tmp/exports", "Nordic Naturals/2026")

    assert output_dir == str(Path("/tmp/exports") / "Nordic-Naturals-2026")


def test_load_change_journal_returns_changed_prefixes_after_cursor(tmp_path):
    from build_all_final_dbs import load_change_journal

    journal_path = tmp_path / "journal.json"
    journal_path.write_text(
        json.dumps(
            {
                "entries": [
                    {"prefix": "Pure-2026", "changed_at": "2026-03-29T10:00:00Z"},
                    {"prefix": "Nordic-2026", "changed_at": "2026-03-29T11:00:00Z"},
                    {"brand_prefix": "Nordic-2026", "changed_at": "2026-03-29T12:00:00Z"},
                    {"pair_prefix": "Nature-2026", "changed_at": "2026-03-29T13:00:00Z"},
                ]
            }
        ),
        encoding="utf-8",
    )

    changed_prefixes, latest_cursor = load_change_journal(
        str(journal_path),
        since_cursor="2026-03-29T10:30:00Z",
    )

    assert changed_prefixes == {"Nordic-2026", "Nature-2026"}
    assert latest_cursor == "2026-03-29T13:00:00Z"


def test_save_state_file_persists_journal_cursor(tmp_path):
    from build_all_final_dbs import load_state, save_state_file

    state_path = tmp_path / "state.json"
    save_state_file(
        str(state_path),
        {"Nordic-2026": {"combined_fingerprint": "abc"}},
        metadata={"journal_cursor": "2026-03-29T13:00:00Z"},
    )

    state = load_state(str(state_path))
    assert state["pairs"]["Nordic-2026"]["combined_fingerprint"] == "abc"
    assert state["journal_cursor"] == "2026-03-29T13:00:00Z"


def test_assemble_release_artifact_uses_all_discovered_pair_outputs(tmp_path):
    from assemble_final_db_release import discover_pair_output_dirs
    from build_all_final_dbs import assemble_release_artifact
    from test_assemble_final_db_release import _write_pair_output

    pair_root = tmp_path / "pair_outputs"
    _write_pair_output(pair_root, "Nordic", "1001", "Nordic Product")
    _write_pair_output(pair_root, "Pure", "2002", "Pure Product")

    output_dir = tmp_path / "release"
    result = assemble_release_artifact(str(pair_root), str(output_dir))

    assert result["product_count"] == 2
    assert sorted(discover_pair_output_dirs(str(pair_root))) == [
        str(pair_root / "Nordic"),
        str(pair_root / "Pure"),
    ]
    assert (output_dir / "pharmaguide_core.db").exists()
    assert (output_dir / "detail_index.json").exists()


def test_main_rejects_assemble_release_without_per_pair_output_root(tmp_path):
    from build_all_final_dbs import main

    with patch.object(
        sys,
        "argv",
        [
            "build_all_final_dbs.py",
            "--scan-dir",
            str(tmp_path),
            "--assemble-release-output",
            str(tmp_path / "release"),
        ],
    ):
        try:
            main()
        except SystemExit as exc:
            assert exc.code == 1
        else:
            raise AssertionError("Expected SystemExit when assembling without per-pair output root")
