"""Fail-closed input contracts for the label-ledger corpus audit."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import audit_label_ledger_reconciliation as audit


def _run(monkeypatch, capsys, *args):
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_label_ledger_reconciliation.py", *map(str, args)],
    )
    exit_code = audit.main()
    output = capsys.readouterr().out
    payload = json.loads(output.split("\n\n", 1)[0])
    return exit_code, payload, output


def test_missing_brand_is_an_input_failure(monkeypatch, capsys, tmp_path):
    exit_code, payload, output = _run(
        monkeypatch,
        capsys,
        "--staging",
        tmp_path,
        "--brands",
        "MissingBrand",
        "--per-brand",
        "1",
    )

    assert exit_code == 1
    assert payload["products_checked"] == 0
    assert payload["input_errors"] == 1
    assert payload["by_brand"]["MissingBrand"]["status"] == "missing"
    assert "FAILURES" in output


def test_unreadable_sample_is_an_input_failure(monkeypatch, capsys, tmp_path):
    brand_dir = tmp_path / "BrokenBrand"
    brand_dir.mkdir()
    (brand_dir / "broken.json").write_text("{not valid json")

    exit_code, payload, output = _run(
        monkeypatch,
        capsys,
        "--staging",
        tmp_path,
        "--brands",
        "BrokenBrand",
        "--per-brand",
        "1",
    )

    assert exit_code == 1
    assert payload["products_checked"] == 0
    assert payload["input_errors"] == 1
    assert payload["by_brand"]["BrokenBrand"]["sampled"] == 1
    assert payload["by_brand"]["BrokenBrand"]["products"] == 0
    assert payload["by_brand"]["BrokenBrand"]["unreadable_files"] == 1
    assert "FAILURES" in output


def test_unsupported_source_structure_blocks_the_audit(monkeypatch, capsys, tmp_path):
    brand_dir = tmp_path / "UnsupportedBrand"
    brand_dir.mkdir()
    (brand_dir / "unsupported.json").write_text(
        json.dumps(
            {
                "id": "unsupported-audit",
                "fullName": "Unsupported label shape",
                "ingredientRows": {"unexpected": "object"},
                "otheringredients": {"ingredients": []},
            }
        )
    )

    exit_code, payload, output = _run(
        monkeypatch,
        capsys,
        "--staging",
        tmp_path,
        "--brands",
        "UnsupportedBrand",
        "--per-brand",
        "1",
    )

    assert exit_code == 1
    assert payload["products_checked"] == 1
    assert payload["contract_errors"] >= 1
    assert (
        payload["errors_by_rule"].get("H.8", 0) >= 1
    ), "unsupported label identity must block the preflight audit"
    assert "FAILURES" in output
