"""Synthetic-only document → response → lock → sparse-stage contracts.

No historical answers or baseline keys are read. Fixture ratings are explicitly
test data, not human evaluations or clinical evidence.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from audits import v4_reviewer_benchmark_analysis as analysis
from audits.v4_reviewer_benchmark_freeze import _response_template_rows
from test_v4_reviewer_benchmark_analysis import (
    _baseline, _registry_rows, _response, _sha256, _spec, _write_csv,
)


SCRIPTS = Path(__file__).resolve().parents[1]
DOCS = SCRIPTS / "audits" / "v4_reviewer_benchmark"
ANALYZER = SCRIPTS / "audits" / "v4_reviewer_benchmark_analysis.py"
ATTESTATIONS = ("ai_assistance_used", "prior_ai_review_seen", "engine_output_seen")


def _run(script, *arguments):
    return subprocess.run(
        [sys.executable, str(script), *map(str, arguments)],
        capture_output=True, text=True, check=False,
    )


@pytest.fixture
def frozen(tmp_path):
    root = tmp_path / "synthetic-freeze"
    root.mkdir()
    spec = _spec()
    spec["primary_design"]["required_ratings"] = 12
    packet = [{
        "benchmark_id": f"PG-{number:02X}",
        "review_sequence": number,
        "product_name": f"Synthetic fixture {number}",
        "brand_name": "Synthetic test brand",
        "active_ingredients_json": "[]",
    } for number in range(1, 5)]
    template = _response_template_rows(packet, 3, seed="roundtrip-fixture")
    # Pin distinct randomized assignments, none derived from review_sequence.
    orders = {1: [3, 1, 4, 2], 2: [4, 2, 1, 3], 3: [2, 4, 3, 1]}
    for row in template:
        row["reviewer_order"] = orders[row["reviewer_slot"]][row["review_sequence"] - 1]
    _write_csv(root / "reviewer_packet.csv", packet)
    _write_csv(root / "reviewer_response_template.csv", template)
    (root / "ANALYSIS_SPEC.json").write_text(json.dumps(spec))
    manifest = {
        "freeze_id": spec["freeze_id"],
        "analysis_contract": {
            "response_contract_version": "2.0.0",
            "analysis_spec_sha256": _sha256(root / "ANALYSIS_SPEC.json"),
            "analysis_script_sha256": _sha256(ANALYZER),
        },
        "artifacts": {name: {"sha256": _sha256(root / name)} for name in (
            "reviewer_packet.csv", "reviewer_response_template.csv",
        )},
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root, packet, template, spec


def _document(frozen, tmp_path, slot=1):
    root, _, _, _ = frozen
    out = tmp_path / f"document-{slot}"
    result = _run(DOCS / "build_review_doc.py", "--freeze-dir", root,
                  "--slot", slot, "--reviewer-id", f"R{slot}", "--out", out)
    assert result.returncode == 0, result.stdout + result.stderr
    return out / f"REVIEW_R{slot}.md", out / f".slotmap_R{slot}.json"


def _fill(doc):
    text = doc.read_text()
    for field in ATTESTATIONS:
        text = re.sub(rf"^{field.upper()}:[^\n]*$", f"{field.upper()}: no", text, flags=re.M)
    def fill_block(match):
        block = match.group(0)
        if not re.search(r"^ID:", block, re.M):
            return block
        sequence = int(re.search(r"ID: PG-([0-9A-F]+)", block)[1], 16)
        values = {
            "FORMULATION (0-20)": str(10 + sequence), "DOSE (0-20)": "12",
            "EVIDENCE (0-20)": "11", "TRANSPARENCY (0-15)": "10",
            "VERIFICATION (0-15)": "9", "QUALITY (0-10)": "8",
            "SAFETY": "no_known_catalog_concern", "DRIVER": "",
            "CONFIDENCE": "high", "LABEL ENOUGH?": "yes",
            "SOURCES": "https://example.org/synthetic-source; https://example.org/synthetic-context",
            "WHY": "Synthetic fixture rationale; not a clinical evaluation.",
            "ODD": "none",
        }
        for key, value in values.items():
            block = re.sub(rf"^{re.escape(key)}:[^\n]*$", f"{key}: {value}", block, flags=re.M)
        return block
    text = re.sub(r"```[^\n]*\n.*?```", fill_block, text, flags=re.S)
    doc.write_text(text)


def _parse(frozen, doc, slotmap, out):
    return _run(DOCS / "parse_review_doc.py", "--freeze-dir", frozen[0],
                "--doc", doc, "--slotmap", slotmap, "--out", out)


def _lock_inputs(frozen, tmp_path, rows):
    root, _, _, _ = frozen
    registry_path = tmp_path / "registry.csv"
    responses_path = tmp_path / "responses.csv"
    _write_csv(registry_path, _registry_rows())
    _write_csv(responses_path, rows)
    return dict(
        manifest_path=root / "manifest.json",
        analysis_spec_path=root / "ANALYSIS_SPEC.json",
        analysis_script_path=ANALYZER,
        reviewer_packet_path=root / "reviewer_packet.csv",
        reviewer_template_path=root / "reviewer_response_template.csv",
        reviewer_registry_path=registry_path,
        responses_path=responses_path,
    )


def _input_arguments(inputs):
    return [part for field, path in inputs.items() if field != "analysis_script_path"
            for part in ("--" + field.removesuffix("_path").replace("_", "-"), str(path))]


def _ratings(frozen):
    return [dict(_response(row["benchmark_id"], row["review_sequence"], row["reviewer_slot"]),
                 reviewer_order=str(row["reviewer_order"])) for row in frozen[2]]


def _stage_baseline():
    # Frozen master positions 2 and 4, with sparse different reviewer orders.
    return [dict(_baseline()[0], benchmark_id=f"PG-{sequence:02X}",
                 review_sequence=str(sequence)) for sequence in (2, 4)]


def test_document_parser_lock_and_sparse_stage_roundtrip(frozen, tmp_path):
    rows = []
    for slot in (1, 2, 3):
        doc, slotmap = _document(frozen, tmp_path, slot)
        generated = doc.read_text()
        for field in ATTESTATIONS:
            assert re.search(rf"^{field.upper()}:\s*$", generated, re.M)
        _fill(doc)
        out = tmp_path / f"answers-{slot}"
        parsed = _parse(frozen, doc, slotmap, out)
        assert parsed.returncode == 0, parsed.stdout + parsed.stderr
        with (out / f"answers_R{slot}.csv").open() as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == list(analysis.RESPONSE_FIELDS)
            rows.extend(reader)
    assert len(rows) == 12
    assert all(row["protocol_deviation"] == "" for row in rows)
    assert all(len(json.loads(row["source_citations_json"])) == 2 for row in rows)
    expected = {(row["benchmark_id"], str(row["reviewer_slot"])): row for row in frozen[2]}
    for row in rows:
        assigned = expected[row["benchmark_id"], row["reviewer_slot"]]
        assert int(row["review_sequence"]) == assigned["review_sequence"]
        assert int(row["reviewer_order"]) == assigned["reviewer_order"]
    inputs = _lock_inputs(frozen, tmp_path, rows)
    lock = analysis.build_response_lock(**inputs, locked_on="synthetic-fixture")
    analysis.verify_response_lock(lock, **inputs)
    result = analysis.analyze_benchmark(
        _stage_baseline(), rows, _registry_rows(), frozen[3], stage="development",
        reviewer_packet_rows=frozen[1], reviewer_template_rows=frozen[2],
    )
    assert result["sample"]["analyzed_products"] == 2
    assert result["sample"]["primary_ratings"] == 6
    assert result["sample"]["reviewer_panel_size"] == 3
    lock_path = tmp_path / "new-response-lock.json"
    cli_lock = _run(ANALYZER, "lock-responses", *_input_arguments(inputs),
                    "--locked-on", "synthetic-fixture", "--output", lock_path)
    assert cli_lock.returncode == 0, cli_lock.stdout + cli_lock.stderr
    baseline_path = tmp_path / "synthetic-development-key.csv"
    _write_csv(baseline_path, _stage_baseline())
    report_path = tmp_path / "new-analysis.json"
    cli_analysis = _run(ANALYZER, "analyze-development", *_input_arguments(inputs),
                        "--response-lock", lock_path, "--baseline-key", baseline_path,
                        "--output", report_path)
    assert cli_analysis.returncode == 0, cli_analysis.stdout + cli_analysis.stderr
    assert json.loads(report_path.read_text())["sample"]["primary_ratings"] == 6


@pytest.mark.parametrize("field", ATTESTATIONS)
@pytest.mark.parametrize("value", ["yes", "unknown"])
def test_exposed_or_unknown_reviewer_blocks_primary_not_reduced_panel(frozen, field, value):
    rows = _ratings(frozen)
    for row in rows:
        if row["reviewer_slot"] == "1":
            row[field] = value
    result = analysis.analyze_benchmark(
        _stage_baseline(), rows, _registry_rows(), frozen[3], stage="development",
        reviewer_packet_rows=frozen[1], reviewer_template_rows=frozen[2],
    )
    assert result["status"] == "blocked_independent_primary_analysis"
    assert result["sample"]["primary_ratings"] == 0
    assert result["sample"]["reviewer_panel_size"] == 3
    assert result["agreement"] == {}
    assert result["overall"] is None
    assert result["sensitivity_all_locked_responses"]["products"] == 2
    assert result["sensitivity_all_locked_responses"]["independent_primary"] is False
    assert result["calibration"]["eligible"] is False


@pytest.mark.parametrize("before,after", [
    ("AI_ASSISTANCE_USED: no", "AI_ASSISTANCE_USED:"),
    ("PRIOR_AI_REVIEW_SEEN: no", "PRIOR_AI_REVIEW_SEEN: maybe"),
    ("ENGINE_OUTPUT_SEEN: no\n", ""),
    ("FORMULATION (0-20): 13", "FORMULATION (0-20): 13 (guessed)"),
    ("DOSE (0-20): 12", "DOSE (0-20): nan"),
    ("EVIDENCE (0-20): 11", "EVIDENCE (0-20):"),
    ("WHY: Synthetic fixture rationale; not a clinical evaluation.", "WHY:"),
    ("https://example.org/synthetic-source; https://example.org/synthetic-context", "not a citation"),
    ("https://example.org/synthetic-source; https://example.org/synthetic-context", ""),
    ("https://example.org/synthetic-source; https://example.org/synthetic-context", "https://example.org/source;;"),
])
def test_invalid_document_writes_no_csv(frozen, tmp_path, before, after):
    doc, slotmap = _document(frozen, tmp_path)
    _fill(doc)
    original = doc.read_text()
    assert before in original
    doc.write_text(original.replace(before, after, 1))
    out = tmp_path / "invalid-answers"
    parsed = _parse(frozen, doc, slotmap, out)
    assert parsed.returncode != 0
    assert not (out / "answers_R1.csv").exists()


@pytest.mark.parametrize("change", ["duplicate", "partial", "legacy_map", "changed_map", "changed_packet"])
def test_document_provenance_and_complete_set_fail_closed(frozen, tmp_path, change):
    doc, slotmap = _document(frozen, tmp_path)
    _fill(doc)
    block = re.search(r"```\nID:.*?```", doc.read_text(), re.S)[0]
    if change == "duplicate":
        doc.write_text(doc.read_text() + "\n" + block)
    elif change == "partial":
        doc.write_text(doc.read_text().replace(block, "", 1))
    elif change == "legacy_map":
        slotmap.write_text(json.dumps({"slot": 1, "reviewer_id": "R1", "order": {"PG-01": 1}}))
    elif change == "changed_map":
        data = json.loads(slotmap.read_text())
        data["reviews"]["PG-01"]["review_sequence"] = 2
        slotmap.write_text(json.dumps(data))
    else:
        with (frozen[0] / "reviewer_packet.csv").open("a") as handle:
            handle.write("\n")
    out = tmp_path / "invalid-answers"
    result = _parse(frozen, doc, slotmap, out)
    assert result.returncode != 0
    assert not (out / "answers_R1.csv").exists()


def test_documents_answers_and_locks_never_overwrite(frozen, tmp_path):
    doc, slotmap = _document(frozen, tmp_path)
    _fill(doc)
    original = doc.read_bytes()
    repeated = _run(DOCS / "build_review_doc.py", "--freeze-dir", frozen[0],
                    "--slot", 1, "--reviewer-id", "R1", "--out", doc.parent)
    assert repeated.returncode != 0
    assert doc.read_bytes() == original
    out = tmp_path / "answers"
    assert _parse(frozen, doc, slotmap, out).returncode == 0
    answer = out / "answers_R1.csv"
    saved = answer.read_bytes()
    assert _parse(frozen, doc, slotmap, out).returncode != 0
    assert answer.read_bytes() == saved
    inputs = _lock_inputs(frozen, tmp_path, _ratings(frozen))
    target = tmp_path / "existing-lock.json"
    target.write_text("existing lock remains")
    arguments = ["lock-responses", "--locked-on", "fixture", "--output", str(target)]
    arguments += _input_arguments(inputs)
    assert _run(ANALYZER, *arguments).returncode != 0
    assert target.read_text() == "existing lock remains"


def test_packet_mutation_or_missing_packet_hash_invalidates_lock(frozen, tmp_path):
    inputs = _lock_inputs(frozen, tmp_path, _ratings(frozen))
    lock = analysis.build_response_lock(**inputs, locked_on="synthetic-fixture")
    missing = dict(lock)
    del missing["reviewer_packet_sha256"]
    with pytest.raises(analysis.AnalysisContractError, match="reviewer_packet_sha256"):
        analysis.verify_response_lock(missing, **inputs)
    with inputs["reviewer_packet_path"].open("a") as handle:
        handle.write("\n")
    with pytest.raises(analysis.AnalysisContractError, match="reviewer_packet_sha256"):
        analysis.verify_response_lock(lock, **inputs)


def test_changed_shared_validator_code_invalidates_lock(frozen, tmp_path):
    inputs = _lock_inputs(frozen, tmp_path, _ratings(frozen))
    script_copy = tmp_path / "analysis.py"
    script_copy.write_bytes(ANALYZER.read_bytes())
    inputs["analysis_script_path"] = script_copy
    lock = analysis.build_response_lock(**inputs, locked_on="synthetic-fixture")
    with script_copy.open("a") as handle:
        handle.write("\n# changed shared validator\n")
    with pytest.raises(analysis.AnalysisContractError, match="analysis_script_sha256"):
        analysis.verify_response_lock(lock, **inputs)


def test_full_lock_rejects_missing_rater_and_order_reassignment(frozen, tmp_path):
    rows = _ratings(frozen)
    rows[0]["reviewer_order"], rows[1]["reviewer_order"] = rows[1]["reviewer_order"], rows[0]["reviewer_order"]
    inputs = _lock_inputs(frozen, tmp_path, rows)
    with pytest.raises(analysis.AnalysisContractError, match="reviewer_order"):
        analysis.build_response_lock(**inputs, locked_on="fixture")
    _write_csv(inputs["responses_path"], _ratings(frozen)[1:])
    with pytest.raises(analysis.AnalysisContractError, match="fixed panel"):
        analysis.build_response_lock(**inputs, locked_on="fixture")


def test_none_is_no_deviation_but_actual_text_and_exposure_history_survive(frozen):
    rows = _ratings(frozen)
    for row in rows:
        row["protocol_deviation"] = " NONE "
    target = next(row for row in rows if row["benchmark_id"] == "PG-02" and row["reviewer_slot"] == "1")
    target["protocol_deviation"] = "Saw an AI-generated review before scoring."
    target["prior_ai_review_seen"] = "yes"
    corrected = dict(target, review_round="2", correction_reason="Synthetic arithmetic correction",
                     prior_ai_review_seen="no", protocol_deviation="none")
    rows.append(corrected)
    result = analysis.analyze_benchmark(
        _stage_baseline(), rows, _registry_rows(), frozen[3], stage="development",
        reviewer_packet_rows=frozen[1], reviewer_template_rows=frozen[2],
    )
    assert result["sample"]["excluded_benchmark_ids"] == ["PG-02"]
    assert result["sample"]["analyzed_products"] == 1


def test_template_uses_ordered_contract_with_blank_attestations(frozen):
    assert tuple(frozen[2][0]) == analysis.RESPONSE_FIELDS
    assert all(row[field] == "" for row in frozen[2] for field in ATTESTATIONS)


def test_parser_retains_true_deviation_text(frozen, tmp_path):
    doc, slotmap = _document(frozen, tmp_path)
    _fill(doc)
    compromise = "Prior AI review discussed this product; source access also failed."
    doc.write_text(doc.read_text().replace("ODD: none", f"ODD: {compromise}", 1))
    out = tmp_path / "exploratory-answers"
    assert _parse(frozen, doc, slotmap, out).returncode == 0
    with (out / "answers_R1.csv").open() as handle:
        assert next(csv.DictReader(handle))["protocol_deviation"] == compromise


def test_checked_in_new_contract_is_draft_not_historical_ratification():
    spec = json.loads((DOCS / "ANALYSIS_SPEC.json").read_text())
    assert spec["response_contract_version"] == "2.0.0"
    assert spec["analysis_version"] == "2.0.0"
    assert spec["freeze_id"] != "2026-08-06-v6"
    assert spec["status"] == "draft_unratified_new_freeze_required"
    assert spec["decision_thresholds"]["calibration_eligibility"] is False
    assert list(spec["rating_contract"]["pillar_limits"].values()) == [20, 20, 20, 15, 15, 10]
    assert [tier["min"] for tier in spec["tier_thresholds"]] == [95, 90, 80, 70, 55, 0]


@pytest.mark.parametrize("panel_size", [2, 4])
def test_freeze_rejects_a_non_three_rater_design_before_reading_inputs(monkeypatch, panel_size):
    from types import SimpleNamespace
    from audits import v4_reviewer_benchmark_freeze as freeze

    monkeypatch.setattr(freeze, "_parse_args", lambda argv: SimpleNamespace(reviewers_per_product=panel_size))
    with pytest.raises(ValueError, match="exactly three"):
        freeze.main([])
