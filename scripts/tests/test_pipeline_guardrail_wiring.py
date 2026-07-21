"""Operational release gates must fail closed before scoring."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from run_pipeline import PipelineRunner


def test_pre_score_loader_rejects_corrupt_json(tmp_path):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    (enriched / "valid.json").write_text(json.dumps({"dsld_id": "1"}))
    (enriched / "corrupt.json").write_text('{"dsld_id": ', encoding="utf-8")

    runner = PipelineRunner()
    products, error = runner._load_products_for_gates(str(enriched))

    assert products is None
    assert error["error"] == "enriched_json_load_failed"
    assert error["failed_files"] == ["corrupt.json"]


def test_stage3_runtime_points_only_to_v4_producer():
    runner = PipelineRunner()

    assert runner.config["scripts"]["score"] == "score_products_v4.py"
    assert "score" not in runner.config["configs"]


def test_pre_score_loader_rejects_empty_directory(tmp_path):
    enriched = tmp_path / "enriched"
    enriched.mkdir()

    products, error = PipelineRunner()._load_products_for_gates(str(enriched))

    assert products is None
    assert error["error"] == "no_enriched_products"


def test_missing_coverage_gate_module_fails_closed(tmp_path, monkeypatch):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    (enriched / "p.json").write_text(json.dumps({"dsld_id": "1"}))
    monkeypatch.setitem(sys.modules, "coverage_gate", None)

    can_proceed, summary = PipelineRunner().run_coverage_gate(
        str(enriched), str(tmp_path), block_on_failure=True
    )

    assert can_proceed is False
    assert summary["error"] == "required_gate_unavailable"


def test_contract_gate_blocks_error_and_strict_warning(monkeypatch):
    import enrichment_contract_validator as validator_module

    class FakeValidator:
        received_strict_mode = None

        def __init__(self, strict_mode=False):
            FakeValidator.received_strict_mode = strict_mode

        def validate_batch(self, products):
            return {
                "1": [SimpleNamespace(severity="warning", rule="test_rule")],
            }

    monkeypatch.setattr(
        validator_module, "EnrichmentContractValidator", FakeValidator
    )
    runner = PipelineRunner()

    can_proceed, summary = runner.run_enrichment_contract_gate(
        [{"dsld_id": "1"}], strict_mode=True
    )

    assert can_proceed is False
    assert FakeValidator.received_strict_mode is True
    assert summary == {
        "products_checked": 1,
        "products_with_violations": 1,
        "errors": 0,
        "warnings": 1,
    }


def test_pipeline_runs_contract_then_coverage_on_same_loaded_products(
    tmp_path, monkeypatch
):
    import run_pipeline as pipeline_module

    runner = PipelineRunner()
    shared_products = [{"dsld_id": "1"}]
    calls = []

    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)
    monkeypatch.setattr(
        runner,
        "_load_products_for_gates",
        lambda _path, **_kwargs: (shared_products, None),
    )
    monkeypatch.setattr(pipeline_module, "quarantine_stage_outputs", lambda *_args: [])
    monkeypatch.setattr(
        pipeline_module,
        "write_stage_manifest_from_directory",
        lambda *_args, **_kwargs: tmp_path / ".stage_manifest.json",
    )

    def contract_gate(products, strict_mode=False, report_dir=None, run_id=None):
        calls.append(("contract", products, strict_mode, report_dir))
        return True, {"ok": True}

    def coverage_gate(
        enriched_dir,
        output_dir,
        block_on_failure=True,
        dry_run=False,
        strict_mode=False,
        products=None,
        run_id=None,
    ):
        calls.append(("coverage", products, strict_mode))
        return True, {"ok": True}

    monkeypatch.setattr(runner, "run_enrichment_contract_gate", contract_gate)
    monkeypatch.setattr(runner, "run_coverage_gate", coverage_gate)
    monkeypatch.setattr(runner, "run_score", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runner, "_validate_input_dir", lambda *_args: True)

    result = runner.run_pipeline(
        stages=["score"],
        output_prefix=str(tmp_path / "output_Test"),
        strict_release_gates=True,
    )

    assert result["success"] is True
    assert [call[0] for call in calls] == ["contract", "coverage"]
    assert calls[0][1] is shared_products
    assert calls[1][1] is shared_products
    assert calls[0][2] is True
    assert calls[1][2] is True
    assert calls[0][3] == str(tmp_path / "output_Test_enriched")


def test_strict_release_mode_rejects_gate_bypasses(tmp_path, monkeypatch):
    runner = PipelineRunner()
    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)

    result = runner.run_pipeline(
        stages=["score"],
        output_prefix=str(tmp_path / "output_Test"),
        strict_release_gates=True,
        skip_coverage_gate=True,
    )

    assert result["success"] is False
    assert result["stages_failed"] == ["release_gate_configuration"]


def test_strict_enrichment_requires_clean_stage_manifest(tmp_path, monkeypatch):
    runner = PipelineRunner()
    cleaned = tmp_path / "output_Test" / "cleaned"
    cleaned.mkdir(parents=True)
    (cleaned / "cleaned_batch_1.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)
    monkeypatch.setattr(runner, "_validate_input_dir", lambda *_args: True)

    result = runner.run_pipeline(
        stages=["enrich"],
        output_prefix=str(tmp_path / "output_Test"),
        strict_release_gates=True,
    )

    assert result["success"] is False
    assert result["stages_failed"] == ["clean_stage_ownership"]


def test_pipeline_propagates_one_run_id_to_every_stage(tmp_path, monkeypatch):
    runner = PipelineRunner()
    captured = []
    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)
    monkeypatch.setattr(runner, "_validate_input_dir", lambda *_args: True)

    def fake_run_script(_script, args, _dry_run=False):
        captured.append(args[args.index("--run-id") + 1])
        return True

    monkeypatch.setattr(runner, "_run_script", fake_run_script)

    result = runner.run_pipeline(
        stages=["enrich", "score"],
        output_prefix=str(tmp_path / "output_Test"),
        dry_run=True,
        run_id="review-run-1",
    )

    assert result["run_id"] == "review-run-1"
    assert captured == ["review-run-1", "review-run-1"]
