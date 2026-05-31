from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import audit_scoring_contract_leaks as audit  # noqa: E402


def test_leak_audit_detects_get_and_subscript_access(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        "\n".join(
            [
                "def score(row, product):",
                "    dose = row.get('quantity')",
                "    unit = row['unit']",
                "    ingredients = product['activeIngredients']",
                "    return dose, unit, ingredients",
            ]
        )
    )

    findings = audit._scan_file(sample)

    assert {(item["access_kind"], item["field"]) for item in findings} == {
        ("get", "quantity"),
        ("subscript", "unit"),
        ("subscript", "activeIngredients"),
    }
    assert all(item["id"] for item in findings)
    assert all(item["function"] == "score" for item in findings)


def test_leak_audit_scans_v4_shadow_entrypoint() -> None:
    scanned = {path.name for path in audit.iter_scan_files()}

    assert "score_supplements_v4_shadow.py" in scanned
