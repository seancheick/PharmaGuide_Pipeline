#!/usr/bin/env python3
"""Derive the Phase-3 source-resolution counts from the receipts ledger.

The phase was summarised in three places (the receipts ledger, the reconciliation
table and the pharmacist packet) with different totals, because none of them
stated its denominator. This script fixes the denominators by deriving every
number from ``SOURCE_RESOLUTION_RECEIPTS_20260920.json`` and asserting the totals
the packet and reconciliation table quote.

Two bases are reported, and they legitimately differ:

* **receipt items** — one row per product-and-issue. This is the ledger's own
  unit of record, and the basis for 11 / 6 / 3 / 3 (23 items). The section-level
  `vitamin_e_note` is a finding about three already-counted rows, not a separate
  item, and is deliberately not counted.
* **distinct products** — the same receipts collapsed per product. Ten products
  carry a correction receipt (243808 carries two: a vitamin-A form correction in
  section C and a folate structural correction in section D), and all ten are
  applied.

Every applied correction is additionally cross-checked against measured replay
evidence, so "applied" means "measured on the corpus", not "written down". Two
replays cover the phase: the source-correction A/B (nine products) and the
closure A/B that resolves ``201420`` through the folate dose-safety contract
(one product). ``201420`` is deliberately **not** a row rewrite: its declared
total and its own nested breakdown carry the identical raw text, so the source
conclusion is implemented structurally in the scoring contract instead (see the
receipt's ``implementation`` field).

Usage:
  python3 count_reconciliation_20260920.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT_DIR = HERE.parent

RECEIPTS = HERE / "SOURCE_RESOLUTION_RECEIPTS_20260920.json"
ROWLEVEL_REPLAY = AUDIT_DIR / "SOURCE_CORRECTION_ROWLEVEL_REPLAY_c9e9d6ba_to_candidate_20260920.json"
SCORED_REPLAY = AUDIT_DIR / "SOURCE_CORRECTION_SCORED_REPLAY_c9e9d6ba_to_candidate_20260920.json"
# The closure replay: base 5fb0d0f1 -> the folate declared-total fix. Its only
# changed product is 201420, which the source-correction replay above cannot
# contain because the fix is structural rather than a row correction.
FOLATE_REPLAY = AUDIT_DIR / "FOLATE_201420_SCORED_REPLAY_5fb0d0f1_to_closure_20260920.json"

CORRECTION = "source_verified_correction"
NO_CHANGE = "source_record_correct_no_change"
WITHHELD = "source_insufficient_keep_withheld"
NON_SCOREABLE = "intentional_non_scoreable"

# The ledger used to carry one ``"applied": false`` receipt (201420) whose
# correction the row-wise mechanism could not scope. That is now closed through
# the dose-safety contract, so the expected set is empty and the check below
# fails loudly if any receipt ever claims a correction it cannot implement.
NOT_APPLIED_EXPECTED: "set[str]" = set()


def not_applied_products(receipts: dict) -> "set[str]":
    """Product ids whose receipt explicitly records ``applied: false``."""
    found: "set[str]" = set()

    def visit(value: object) -> None:
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


def _str_or_none(value: object) -> "str | None":
    return value if isinstance(value, str) else None


def receipt_items(receipts: dict) -> "list[tuple[str, str, str]]":
    """Return ``(section, product_id, final_state)`` for every receipt item."""
    items = receipts["items"]
    out: "list[tuple[str, str, str]]" = []

    def add(section: str, pid: object, state: object) -> None:
        state_str = _str_or_none(state)
        if state_str and pid is not None:
            out.append((section, str(pid), state_str))

    def entries(value: object) -> "list[tuple[object, object]]":
        """``products`` is a mapping in some sections and a sequence in others."""
        if isinstance(value, dict):
            return [
                (pid, (body or {}).get("final_state") if isinstance(body, dict) else None)
                for pid, body in value.items()
            ]
        if isinstance(value, list):
            pairs: "list[tuple[object, object]]" = []
            for body in value:
                if isinstance(body, dict):
                    pid = body.get("dsld_id") or body.get("product_id") or body.get("id")
                    pairs.append((pid, body.get("final_state")))
                elif isinstance(body, str):
                    pairs.append((body, None))
            return pairs
        return []

    # A — E2 unit defects: per-product states, plus one section-level note.
    section = items["A_e2_unit_defects"]
    for pid, state in entries(section.get("products")):
        add("A_e2_unit_defects", pid, state)
    add("A_e2_unit_defects", "vitamin_e_note", section.get("vitamin_e_note"))

    # B — needs_info: per-product states.
    for pid, state in entries(items["B_needs_info"].get("products")):
        add("B_needs_info", pid, state)

    # C — vitamin-A form gap: one section-level verdict covering its product list.
    section = items["C_vitamin_a_form_gap"]
    for pid, state in entries(section.get("products")):
        add("C_vitamin_a_form_gap", pid, state or section.get("final_state"))

    # D — folate residuals: per-product states.
    for pid, state in entries(items["D_folate_residuals"].get("products")):
        add("D_folate_residuals", pid, state)

    # E — serrapeptase: single product.
    section = items["E_serrapeptase_269360"]
    add("E_serrapeptase_269360", section.get("dsld_id") or section.get("product", "269360"),
        section.get("final_state"))

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="assert the documented totals")
    args = parser.parse_args()

    receipts = json.loads(RECEIPTS.read_text())
    items = receipt_items(receipts)

    counts: "dict[str, int]" = {}
    for _section, _pid, state in items:
        counts[state] = counts.get(state, 0) + 1

    # Applied vs reported-not-applied, per distinct product.
    corrected_products = sorted({pid for _s, pid, st in items if st == CORRECTION})
    flagged = not_applied_products(receipts)
    applied = [pid for pid in corrected_products if pid not in flagged]
    not_applied = [pid for pid in corrected_products if pid in flagged]

    rowlevel = json.loads(ROWLEVEL_REPLAY.read_text())
    scored = json.loads(SCORED_REPLAY.read_text())
    folate = json.loads(FOLATE_REPLAY.read_text())
    changed_ids = sorted(str(i) for i in rowlevel["changed_ids"])
    conclusion_ids = sorted(
        str(c.get("dsld_id") or c.get("product_id")) for c in scored["conclusion_changes"]
    )
    folate_changed_ids = sorted(str(i) for i in folate["changed_ids"])

    print("receipt items (ledger basis)")
    for state in (CORRECTION, NO_CHANGE, WITHHELD, NON_SCOREABLE):
        print(f"  {state:<34} {counts.get(state, 0)}")
    print(f"  {'TOTAL receipt items':<34} {len(items)}")

    print("\ndistinct products")
    print(f"  correction receipts                {len(corrected_products)}  {corrected_products}")
    print(f"  of which applied (replay-verified) {len(applied)}  {applied}")
    print(f"  of which reported, NOT applied     {len(not_applied)}  {not_applied}")

    print("\nmeasured on the frozen replays")
    print(f"  row-level changed products         {len(changed_ids)}  {changed_ids}")
    print(f"  scored conclusion changes          {len(conclusion_ids)}  {conclusion_ids}")
    print(f"  score changes                      {len(scored['score_changes'])}")
    print(f"  quarantine exits / entries         {len(scored['quarantine_exits'])} / {len(scored['quarantine_entries'])}")
    print(f"  safety changes                     {len(scored['safety_changes'])}")
    print(f"  outside expected families          {len(scored['outside_expected_families'])}")
    print(f"  closure replay changed products    {len(folate_changed_ids)}  {folate_changed_ids}")
    print(f"  closure replay records compared    {folate['records_compared']}")

    if not args.check:
        return 0

    expected = {CORRECTION: 11, NO_CHANGE: 6, WITHHELD: 3, NON_SCOREABLE: 3}
    problems: "list[str]" = []
    for state, want in expected.items():
        got = counts.get(state, 0)
        if got != want:
            problems.append(f"{state}: ledger says {got}, documented total is {want}")
    if len(items) != 23:
        problems.append(f"receipt items: {len(items)}, documented total is 23")
    if len(corrected_products) != 10:
        problems.append(f"corrected products: {len(corrected_products)}, documented total is 10")
    if len(applied) != 10:
        problems.append(f"applied corrections: {len(applied)}, documented total is 10")
    if flagged != NOT_APPLIED_EXPECTED:
        problems.append(
            f"receipts flag {sorted(flagged)} as not applied, documented is "
            f"{sorted(NOT_APPLIED_EXPECTED)}"
        )
    if set(not_applied) != set(receipts_flagged := flagged & set(corrected_products)):
        problems.append(
            f"not-applied set {sorted(not_applied)} disagrees with the ledger's "
            f"{sorted(receipts_flagged)} for corrected products"
        )
    measured = set(changed_ids) | set(folate_changed_ids)
    if not set(applied) <= measured:
        missing = sorted(set(applied) - measured)
        problems.append(f"applied corrections absent from both replays: {missing}")
    if "201420" not in folate_changed_ids:
        problems.append(
            "the closure replay does not contain 201420, so its applied state is "
            "not measured"
        )

    if problems:
        for line in problems:
            print(f"FAIL: {line}", file=sys.stderr)
        return 1

    print(
        "\nOK: ledger, packet and replays agree on 11/6/3/3 items, 10 products, "
        "10 applied."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
