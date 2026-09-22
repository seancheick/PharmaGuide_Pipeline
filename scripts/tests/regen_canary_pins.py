#!/usr/bin/env python3
"""Re-freeze the real-catalog canary pins from the scorer, never by hand.

The slow-tier canaries (gate, omega Formulation, omega Trust, cross-module
generic/sports/probiotic) pin values computed from the enriched corpus on disk.
After an approved scoring change and a fresh pipeline run, this tool recomputes
every pin through the same call the test makes and prints an old -> new ledger.
``--write`` rewrites only the numeric/verdict fields inside each pin's own
literal; labels, traits and structure are untouched, and the ledger is what a
reviewer reads before committing.

    python3 scripts/tests/regen_canary_pins.py            # ledger only
    python3 scripts/tests/regen_canary_pins.py --write    # rewrite the pins
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
sys.path.insert(0, str(TESTS))


def _fmt(value):
    return "None" if value is None else (f'"{value}"' if isinstance(value, str) else repr(round(float(value), 1)))


def _block(text: str, key: str) -> tuple[int, int]:
    """Span of the ``"key": {...}`` literal (brace-matched)."""
    start = text.index(f'"{key}": {{')
    depth, i = 0, text.index("{", start)
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return start, j + 1
    raise ValueError(key)


def _set_field(block: str, field: str, value) -> str:
    if field == "score_range":
        new = f'"score_range": ({_fmt(value[0])}, {_fmt(value[1])})'
        out, n = re.subn(r'"score_range":\s*\([^)]*\)', new, block, count=1)
    else:
        out, n = re.subn(rf'"{field}":\s*(None|"[^"]*"|-?[0-9.]+)', f'"{field}": {_fmt(value)}', block, count=1)
    assert n == 1, (field, block[:80])
    return out


def _centered(old: tuple, new: float) -> tuple:
    half = (float(old[1]) - float(old[0])) / 2
    return (new - half, new + half)


def gate(changes):
    import test_v4_gate_canary_diversity as t
    from score_supplements_v4 import score_product_v4
    products = t._load_canaries()
    for pid, exp in t.V4_CANARIES.items():
        if pid not in products:
            continue
        out = score_product_v4(products[pid])
        new = {"verdict": out["v4_verdict"], "confidence": out["v4_confidence"]}
        if "score" in exp:
            new["score"] = out["raw_score_v4_100"]
        if "score_range" in exp:
            lo, hi = exp["score_range"]
            if not lo <= out["raw_score_v4_100"] <= hi:
                new["score_range"] = _centered(exp["score_range"], out["raw_score_v4_100"])
        diff = {k: (exp.get(k), v) for k, v in new.items() if exp.get(k) != v}
        if diff:
            changes.append(("test_v4_gate_canary_diversity.py", pid, exp["label"], diff))


def cross_module(changes):
    import test_v4_cross_module_canary_diversity as t
    from scoring_v4.modules.generic import score_generic
    from scoring_v4.modules.probiotic import score_probiotic
    from scoring_v4.modules.sports import score_sports
    products = t._load_canaries()
    for pins, scorer in ((t.GENERIC_CANARIES, score_generic), (t.SPORTS_CANARIES, score_sports),
                         (t.PROBIOTIC_CANARIES, score_probiotic)):
        for pid, exp in pins.items():
            if pid not in products:
                continue
            breakdown = scorer(products[pid]).to_breakdown()
            score = breakdown["score_100"]
            diff = {}
            lo, hi = exp["score_range"]
            if not lo <= score <= hi:
                diff["score_range"] = (exp["score_range"], _centered(exp["score_range"], score))
            # A pinned dimension trait is recomputed through the same call too,
            # so no pin is ever updated by hand.
            pinned_dose = (exp.get("traits") or {}).get("dose_score")
            dose = breakdown["dimensions"]["dose"]["score"]
            if pinned_dose is not None and abs(float(dose) - float(pinned_dose)) > 1e-9:
                diff["dose_score"] = (pinned_dose, dose)
            if diff:
                changes.append(("test_v4_cross_module_canary_diversity.py", pid, exp["label"], diff))


def omega(changes):
    import test_v4_omega_canary_diversity_p161 as t
    from scoring_v4.modules.omega_formulation import score_formulation
    products = t._load_canaries(set(t.CANARY_TARGETS))
    for pid, (route, form, lo, hi, label) in t.CANARY_TARGETS.items():
        if pid not in products:
            continue
        payload = score_formulation(products[pid])
        score, new_form = payload["score"], payload["metadata"]["form_detected"]
        if not lo <= score <= hi or new_form != form:
            changes.append(("test_v4_omega_canary_diversity_p161.py", pid, label,
                            {"formulation": ((form, lo, hi), (new_form, score, score))}))


def trust(changes):
    import test_v4_omega_trust_p164 as t
    from scoring_v4.modules.omega_trust import score_trust
    products = t._load_canaries(t._CANARY_TRUST_IDS)
    for pid in sorted(t._CANARY_TRUST_IDS):
        if pid not in products:
            continue
        score = score_trust(products[pid])["score"]
        if score != t._CANARY_TRUST_EXPECTED[pid]:
            changes.append(("test_v4_omega_trust_p164.py", pid, pid, {"trust": (t._CANARY_TRUST_EXPECTED[pid], score)}))


def write(changes):
    by_file: dict[str, list] = {}
    for change in changes:
        by_file.setdefault(change[0], []).append(change)
    for name, items in by_file.items():
        path = TESTS / name
        text = path.read_text()
        for _, pid, _, diff in items:
            if "formulation" in diff:
                (old_form, _, _), (form, lo, hi) = diff["formulation"]
                pattern = rf'("{pid}":\s*\("omega",\s*)"{old_form}",\s*[0-9.]+,\s*[0-9.]+,'
                text, n = re.subn(pattern, rf'\1"{form}", {_fmt(lo)}, {_fmt(hi)},', text, count=1)
                assert n == 1, pid
            elif "trust" in diff:
                text, n = re.subn(rf'("{pid}":\s*)[0-9.]+,', rf"\g<1>{_fmt(diff['trust'][1])},", text, count=1)
                assert n == 1, pid
            else:
                start, end = _block(text, pid)
                block = text[start:end]
                for field, (_, value) in diff.items():
                    block = _set_field(block, field, value)
                text = text[:start] + block + text[end:]
        path.write_text(text)
        print("rewrote", name, len(items), "pins")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changes: list = []
    for step in (gate, cross_module, omega, trust):
        step(changes)
    for name, pid, label, diff in changes:
        print(f"{name:44} {pid:>10}  {str(label)[:44]:44}  " + json.dumps(diff, default=str))
    print(len(changes), "pins differ from the current scorer")
    if args.write and changes:
        write(changes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
