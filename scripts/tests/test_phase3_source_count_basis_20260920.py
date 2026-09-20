"""Phase-3 source-resolution counts must stay reconcilable (2026-09-20).

The phase was summarised in three places with three different totals, because none
of them stated its denominator. `COUNT_BASIS_20260920.md` fixes the definitions and
`count_reconciliation_20260920.py` derives every number from the receipts ledger.

These tests pin the derivation so a future edit to the receipts cannot silently
change the published totals, and so the "applied" claim stays tied to measured
replay evidence rather than to a written-down intention.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = REPO_ROOT / "scripts" / "audits" / "quarantine_triage_20260919"
SOURCE_DIR = AUDIT_DIR / "source_resolution_20260920"
RECEIPTS = SOURCE_DIR / "SOURCE_RESOLUTION_RECEIPTS_20260920.json"
ROWLEVEL_REPLAY = (
    AUDIT_DIR / "SOURCE_CORRECTION_ROWLEVEL_REPLAY_c9e9d6ba_to_candidate_20260920.json"
)
COUNT_SCRIPT = SOURCE_DIR / "count_reconciliation_20260920.py"
COUNT_BASIS = SOURCE_DIR / "COUNT_BASIS_20260920.md"


pytestmark = pytest.mark.skipif(
    not RECEIPTS.exists(),
    reason="Phase-3 source-resolution receipts not present in this checkout",
)


def _load(path: Path):
    return json.loads(path.read_text())


def _items(receipts: dict):
    """(section, product_id, final_state) for every receipt item.

    ``products`` is a mapping in some sections and a sequence in others, and the
    section-level ``vitamin_e_note`` is a finding about already-counted rows rather
    than an item of its own.
    """
    items = receipts["items"]
    out = []

    def entries(value):
        if isinstance(value, dict):
            return [
                (pid, (body or {}).get("final_state") if isinstance(body, dict) else None)
                for pid, body in value.items()
            ]
        if isinstance(value, list):
            pairs = []
            for body in value:
                if isinstance(body, dict):
                    pid = body.get("dsld_id") or body.get("product_id") or body.get("id")
                    pairs.append((pid, body.get("final_state")))
                elif isinstance(body, str):
                    pairs.append((body, None))
            return pairs
        return []

    for section in ("A_e2_unit_defects", "B_needs_info", "C_vitamin_a_form_gap",
                    "D_folate_residuals"):
        body = items[section]
        default = body.get("final_state") if section == "C_vitamin_a_form_gap" else None
        for pid, state in entries(body.get("products")):
            state = state or default
            if isinstance(state, str) and pid is not None:
                out.append((section, str(pid), state))

    tail = items["E_serrapeptase_269360"]
    out.append(("E_serrapeptase_269360", "269360", tail.get("final_state")))
    return out


def test_receipt_item_totals_match_the_published_basis():
    counts: "dict[str, int]" = {}
    for _section, _pid, state in _items(_load(RECEIPTS)):
        counts[state] = counts.get(state, 0) + 1

    assert counts.get("source_verified_correction") == 11
    assert counts.get("source_record_correct_no_change") == 6
    assert counts.get("source_insufficient_keep_withheld") == 3
    assert counts.get("intentional_non_scoreable") == 3
    # 23 receipt items: the section-level vitamin-E note is deliberately excluded.
    assert sum(counts.values()) == 23


def _not_applied(receipts: dict) -> set:
    """Product ids whose receipt records ``applied: false``."""
    found = set()

    def visit(value):
        if isinstance(value, dict):
            if value.get("applied") is False:
                pid = value.get("dsld_id") or value.get("product_id") or value.get("id")
                if pid is not None:
                    found.add(str(pid))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(receipts.get("items", {}))
    return found


def test_one_correction_receipt_is_reported_not_applied():
    """201420 is the single exception, and the ledger says so mechanically."""
    receipts = _load(RECEIPTS)
    corrected = {pid for _s, pid, st in _items(receipts)
                 if st == "source_verified_correction"}
    assert len(corrected) == 10

    changed = {str(i) for i in _load(ROWLEVEL_REPLAY)["changed_ids"]}
    assert len(changed) == 9

    # The applied set is measured, and the exception is the ledger's own flag -
    # not an assumption that every receipt was implemented.
    flagged = _not_applied(receipts)
    assert flagged == {"201420"}
    assert corrected - flagged == changed

    entry = next(
        body for body in _load(RECEIPTS)["items"]["D_folate_residuals"]["products"]
        if body.get("dsld_id") == "201420"
    )
    assert entry["applied"] is False
    assert entry.get("why_not_applied"), "an unapplied correction must say why"


def test_count_basis_script_agrees_with_the_ledger():
    script = COUNT_SCRIPT
    assert script.exists(), "count reconciliation script missing"
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "11/6/3/3" in result.stdout


def test_no_summary_still_publishes_the_superseded_totals():
    """Guard the specific stale wordings that were corrected."""
    stale = re.compile(r"10 corrections|9 records confirmed|source_verified_correction` \| \*\*9\*\*")
    for path in (COUNT_BASIS.parent / "PHARMACIST_PACKET_PHASE3_FINAL_20260920.md",
                 COUNT_BASIS.parent / "SOURCE_RECONCILIATION_20260920.md"):
        text = path.read_text()
        assert not stale.search(text), f"stale count wording remains in {path.name}"
