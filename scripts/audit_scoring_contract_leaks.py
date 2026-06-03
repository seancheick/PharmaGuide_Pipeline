#!/usr/bin/env python3
"""Audit the v4 scoring surface for raw-field reads that bypass the contract.

Scans Python files under scripts/scoring_v4/ plus the v4 shadow entrypoint using
the AST to find both .get("field") and row["field"] reads where the field is in
the forbidden set. Known violations are allowlisted by stable finding id with a
justification; new violations cause a non-zero exit.

Usage:
    python3 scripts/audit_scoring_contract_leaks.py
    python3 scripts/audit_scoring_contract_leaks.py --json   # machine-readable only

Exit codes:
    0  All findings are allowlisted (no new violations)
    1  New violations found
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
V4_DIR = SCRIPTS_DIR / "scoring_v4"
V4_ENTRYPOINTS = (SCRIPTS_DIR / "score_supplements_v4_shadow.py",)
REPORT_DIR = SCRIPTS_DIR.parent / "reports"

FORBIDDEN_FIELDS: dict[str, str] = {
    "match_type": "RAW_MATCH_TYPE",
    "match_method": "RAW_MATCH_TYPE",
    "raw_source_text": "RAW_SOURCE_TEXT",
    "quantity": "RAW_QUANTITY_UNIT",
    "unit": "RAW_QUANTITY_UNIT",
    "unit_normalized": "RAW_QUANTITY_UNIT",
    "activeIngredients": "RAW_ACTIVE_LISTS",
    "inactiveIngredients": "RAW_ACTIVE_LISTS",
}

# Stable finding id -> justification.
# Populated with known Pass-A violations; these are pending native ScoringEvidence
# and SafetySignal emission in the enricher before P5.
ALLOWLIST: dict[str, str] = {
    "scripts/scoring_v4/gate_completeness.py|_has_enzyme_activity_evidence|get|unit|30c24beac47d": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/gate_safety.py|_ingredient_name_terms|get|raw_source_text|defe2b573198": "pass_a_known_pending_native_safety_signal_contract",
    "scripts/scoring_v4/modules/botanical_profile.py|_mass_mg|get|quantity|437869d0a4ab": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/botanical_profile.py|_mass_mg|get|unit|d22733e3184e": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/botanical_profile.py|_mass_mg|get|unit_normalized|c7a08b90a025": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/botanical_profile.py|_range_mg|get|unit|83418ab1801f": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/brand_testing_posture.py|score_brand_testing_posture|get|match_type|2d68ef6686e9": "pass_a_known_pending_native_safety_signal_contract",
    "scripts/scoring_v4/modules/collagen_profile.py|_range_mg|get|unit|83418ab1801f": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_evidence.py|_dose_map|get|quantity|aacd9ff64a58": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_evidence.py|_dose_map|get|unit_normalized|320965a122ab": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_evidence.py|_dose_map|get|unit|44abae5cc7d8": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_evidence.py|_dose_map|get|raw_source_text|0fe1043d3c32": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_formulation.py|_penalty_b0_moderate_watchlist|get|match_type|c4b5077cd8a7": "pass_a_known_pending_native_safety_signal_contract",
    "scripts/scoring_v4/modules/generic_formulation.py|_penalty_b0_moderate_watchlist|get|match_method|dbf3af2e35bf": "pass_a_known_pending_native_safety_signal_contract",
    "scripts/scoring_v4/modules/generic_helpers.py|has_usable_individual_dose|get|quantity|3fd4e11ae842": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_helpers.py|has_usable_individual_dose|get|unit_normalized|dcf5fcc7cc91": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_helpers.py|has_usable_individual_dose|get|unit|30c24beac47d": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_manufacturer.py|_score_d1_reputation|get|match_type|2d68ef6686e9": "pass_a_known_pending_native_safety_signal_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_score_b5_proprietary_blend_penalty|get|unit|33fd471d33c2": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_score_b5_proprietary_blend_penalty|get|unit|d9cb180449d5": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_is_b5_scoreable_blend|get|unit|33fd471d33c2": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_blend_child_payload|get|unit|d9cb180449d5": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_blend_child_payload|get|unit_normalized|7a4fb5de2b96": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_blend_child_payload|get|unit|d9cb180449d5": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_blend_child_payload|get|unit_normalized|7a4fb5de2b96": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_blend_child_payload|get|unit|d9cb180449d5": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_blend_dedupe_fingerprint|get|unit|33fd471d33c2": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_sum_total_active_mg|get|quantity|aacd9ff64a58": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_sum_total_active_mg|get|unit_normalized|320965a122ab": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/generic_transparency.py|_sum_total_active_mg|get|unit|44abae5cc7d8": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/multi_prenatal_dose.py|_quantity_mg|get|quantity|3fd4e11ae842": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/multi_prenatal_dose.py|_quantity_mg|get|unit_normalized|dcf5fcc7cc91": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/multi_prenatal_dose.py|_quantity_mg|get|unit|30c24beac47d": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/omega_dose.py|_sum_epa_dha_per_serving|get|unit|44abae5cc7d8": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/omega_transparency.py|_epa_or_dha_disclosed|get|unit|44abae5cc7d8": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/omega_transparency.py|_epa_or_dha_disclosed|get|unit_normalized|320965a122ab": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/sports_helpers.py|dose_g|get|quantity|21bfa8900072": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/sports_helpers.py|dose_g|get|unit_normalized|c466ec896cc8": "pass_a_known_pending_native_evidence_contract",
    "scripts/scoring_v4/modules/sports_helpers.py|dose_g|get|unit|a4456c65c40e": "pass_a_known_pending_native_evidence_contract",
}


def iter_scan_files() -> list[Path]:
    """Return the complete v4 scoring surface audited for contract leaks."""
    files = list(V4_DIR.rglob("*.py"))
    files.extend(path for path in V4_ENTRYPOINTS if path.exists())
    return sorted(set(files))


def _field_from_subscript(node: ast.Subscript) -> str | None:
    value = node.slice
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _field_from_get_call(node: ast.Call) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "get":
        return None
    if not node.args:
        return None
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _stable_id(
    *,
    rel_file: str,
    function: str,
    access_kind: str,
    field: str,
    snippet: str,
) -> str:
    snippet_hash = hashlib.sha1(snippet.strip().encode("utf-8")).hexdigest()[:12]
    return "|".join((rel_file, function or "<module>", access_kind, field, snippet_hash))


class _LeakVisitor(ast.NodeVisitor):
    def __init__(self, *, filepath: Path, source: str) -> None:
        self.filepath = filepath
        self.source = source
        self.function_stack: list[str] = []
        self.findings: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        field = _field_from_get_call(node)
        if field in FORBIDDEN_FIELDS:
            self._add(node=node, field=field, access_kind="get")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        field = _field_from_subscript(node)
        if field in FORBIDDEN_FIELDS and isinstance(node.ctx, ast.Load):
            self._add(node=node, field=field, access_kind="subscript")
        self.generic_visit(node)

    def _add(self, *, node: ast.AST, field: str, access_kind: str) -> None:
        try:
            rel_file = str(self.filepath.relative_to(SCRIPTS_DIR.parent))
        except ValueError:
            rel_file = str(self.filepath)
        function = ".".join(self.function_stack)
        snippet = ast.get_source_segment(self.source, node) or f"{access_kind}:{field}"
        finding_id = _stable_id(
            rel_file=rel_file,
            function=function,
            access_kind=access_kind,
            field=field,
            snippet=snippet,
        )
        is_allowlisted = finding_id in ALLOWLIST
        self.findings.append({
            "id": finding_id,
            "file": rel_file,
            "line": getattr(node, "lineno", 0),
            "function": function or "<module>",
            "access_kind": access_kind,
            "snippet": snippet,
            "category": FORBIDDEN_FIELDS[field],
            "field": field,
            "allowlisted": is_allowlisted,
            "allowlist_reason": ALLOWLIST.get(finding_id),
        })


def _scan_file(filepath: Path) -> list[dict]:
    """Parse a single Python file and return findings."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    visitor = _LeakVisitor(filepath=filepath, source=source)
    visitor.visit(tree)
    return visitor.findings


def main() -> int:
    json_only = "--json" in sys.argv

    all_findings: list[dict] = []
    for pyfile in iter_scan_files():
        all_findings.extend(_scan_file(pyfile))

    new_violations = [f for f in all_findings if not f["allowlisted"]]
    allowlisted = [f for f in all_findings if f["allowlisted"]]

    report = {
        "total_findings": len(all_findings),
        "allowlisted": len(allowlisted),
        "new_violations": len(new_violations),
        "findings": all_findings,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "scoring_v4_contract_leak_audit.json"
    report_path.write_text(json.dumps(report, indent=2))

    if json_only:
        print(json.dumps(report, indent=2))
    else:
        print(f"Contract leak audit: {len(all_findings)} findings "
              f"({len(allowlisted)} allowlisted, {len(new_violations)} new)")
        if new_violations:
            print("\nNEW VIOLATIONS (must fix or allowlist):")
            for f in new_violations:
                print(
                    f"  {f['file']}:{f['line']}  {f['access_kind']}({f['field']!r})  "
                    f"[{f['category']}] id={f['id']}"
                )
        print(f"\nReport: {report_path}")

    return 1 if new_violations else 0


if __name__ == "__main__":
    sys.exit(main())
