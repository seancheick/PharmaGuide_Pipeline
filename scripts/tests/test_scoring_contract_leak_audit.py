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


def test_leak_audit_scans_v4_entrypoint() -> None:
    scanned = {path.name for path in audit.iter_scan_files()}

    assert "score_supplements_v4.py" in scanned


def test_profile_selector_audit_detects_raw_routing_fields(tmp_path: Path) -> None:
    sample = tmp_path / "generic_dose.py"
    sample.write_text(
        "\n".join(
            [
                "def route_again(row, product):",
                "    taxonomy = row.get('raw_taxonomy')",
                "    title = product['product_name']",
                "    source = row.get('canonical_source_db')",
                "    return taxonomy, title, source",
            ]
        )
    )

    findings = audit.scan_profile_selector_leaks([sample])

    assert {(item["access_kind"], item["field"]) for item in findings} == {
        ("get", "raw_taxonomy"),
        ("subscript", "product_name"),
        ("get", "canonical_source_db"),
    }
    assert all(item["category"].startswith("PROFILE_SELECTOR_") for item in findings)
    assert all(not item["allowlisted"] for item in findings)


def test_real_generic_profile_selectors_do_not_read_raw_routing_fields() -> None:
    assert audit.scan_profile_selector_leaks() == []


def test_every_allowlisted_read_is_a_named_kind_and_the_live_tree_passes() -> None:
    """Exceptions are pass-A pending contracts, named canonical owners, or legacy
    debt recorded from origin/main; any other downstream raw read fails."""
    import audit_scoring_contract_leaks as audit
    kinds = ("pass_a_known_pending_", "canonical_owner: ", "legacy_debt_main_0b7bf3f7")
    assert all(reason.startswith(kinds) for reason in audit.ALLOWLIST.values())
    owners = {key.split("|")[0] + "|" + key.split("|")[1]
              for key, reason in audit.ALLOWLIST.items() if reason.startswith("canonical_owner: ")}
    assert owners == {"scripts/scoring_v4/exposure.py|row_exposure",
                      "scripts/scoring_v4/modules/fiber_digestive_helpers.py|nutrition_fiber_exposure"}
    findings = [f for path in audit.iter_scan_files() for f in audit._scan_file(path)]
    assert findings and all(f["allowlisted"] for f in findings)
    assert set(audit.ALLOWLIST) <= {f["id"] for f in findings}, "stale allowlist entry"
