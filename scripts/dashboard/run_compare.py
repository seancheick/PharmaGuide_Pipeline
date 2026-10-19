"""Compare two indexed runs product by product. Read-only; causes come from replay.

Pillar causes reuse ``audits.quality_redesign.replay.reason_codes`` on the stored
``slim`` projection. Run-level causes (config, stage code, reference data) are taken
from run provenance, so a movement is "unexplained" only when neither the pillar
inputs nor the run inputs changed.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd

from scripts.dashboard.score_index import PILLARS, REPO_ROOT  # noqa: F401  (sys.path set by score_index)
from audits.quality_redesign.replay import reason_codes  # noqa: E402

TableReader = Callable[..., pd.DataFrame]
_PRODUCT_COLUMNS = [
    "dsld_id", "product_name", "brand_name", "module", "category", "total", "tier",
    "quality_score_status", "quality_assessment_status", "product_safety_status",
    "safety_signals", "blocking_reason", "safety_signal_reason", "suppressed_reason",
    "receipt_entry_ids", *[f"pillar_{name}" for name in PILLARS],
]
_SAFETY_CAUSE_FIELDS = ("safety_signals", "blocking_reason", "safety_signal_reason", "suppressed_reason")
MOVE_EPS = 0.05


def run_level_causes(base: dict[str, Any], cand: dict[str, Any]) -> list[str]:
    causes = []
    if sorted(base.get("config_fingerprints") or []) != sorted(cand.get("config_fingerprints") or []) \
            or sorted(base.get("config_versions") or []) != sorted(cand.get("config_versions") or []):
        causes.append("config")
    for key, label in (("artifact_stage_code_fingerprints", "stage_code"),
                       ("artifact_reference_data_fingerprints", "reference_data")):
        if base.get(key) is not None and cand.get(key) is not None and sorted(base[key]) != sorted(cand[key]):
            causes.append(label)
    if base.get("plane") != cand.get("plane"):
        causes.append(f"plane:{base.get('plane')}→{cand.get('plane')}")
    return causes


def _listish(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    return [str(item) for item in list(value)]


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, (list, tuple)) or hasattr(a, "__array__") or isinstance(b, (list, tuple)) or hasattr(b, "__array__"):
        return _listish(a) == _listish(b)
    a_na = a is None or (isinstance(a, float) and pd.isna(a))
    b_na = b is None or (isinstance(b, float) and pd.isna(b))
    return (a_na and b_na) or (not a_na and not b_na and a == b)


def compare(read: TableReader, base: dict[str, Any], cand: dict[str, Any]) -> pd.DataFrame:
    """One row per product in either run. ``read(run_key, table, columns=None)``."""
    left = {r["dsld_id"]: r for r in read(base["run_key"], "products", columns=_PRODUCT_COLUMNS).to_dict("records")}
    right = {r["dsld_id"]: r for r in read(cand["run_key"], "products", columns=_PRODUCT_COLUMNS).to_dict("records")}
    slim_left = _slim_map(read, base)
    slim_right = _slim_map(read, cand)
    run_causes = run_level_causes(base, cand)
    rows = []
    for pid in sorted(set(left) | set(right)):
        b = left.get(pid)
        a = right.get(pid)
        row: dict[str, Any] = {"dsld_id": pid}
        ref = a if a is not None else b
        row.update({"product_name": ref["product_name"], "brand_name": ref["brand_name"],
                    "module": ref["module"], "category": ref["category"]})
        row["presence"] = "both" if a is not None and b is not None else ("added" if a is not None else "removed")
        for side, record in (("before", b), ("after", a)):
            for field in ("total", "tier", "quality_score_status", "quality_assessment_status", "product_safety_status"):
                row[f"{field}_{side}"] = None if record is None else record[field]
        tb, ta = row["total_before"], row["total_after"]
        row["delta"] = round(ta - tb, 2) if pd.notna(tb) and pd.notna(ta) else None
        changed = []
        for name in PILLARS:
            pb = None if b is None else b[f"pillar_{name}"]
            pa_ = None if a is None else a[f"pillar_{name}"]
            delta = round(pa_ - pb, 2) if pd.notna(pb) and pd.notna(pa_) else None
            row[f"delta_{name}"] = delta
            if delta is not None and abs(delta) >= MOVE_EPS:
                changed.append(name)
        row["changed_pillars"] = changed
        row["tier_crossed"] = row["presence"] == "both" and not _same(row["tier_before"], row["tier_after"])
        row["status_changed"] = row["presence"] == "both" and not _same(row["quality_score_status_before"], row["quality_score_status_after"])
        row["safety_changed"] = row["presence"] == "both" and not _same(row["product_safety_status_before"], row["product_safety_status_after"])
        safety_causes = []
        if row["safety_changed"]:
            safety_causes = [f for f in _SAFETY_CAUSE_FIELDS if not _same(b[f], a[f])]
            if "reference_data" in run_causes:
                safety_causes.append("run:reference_data")
        row["safety_causes"] = safety_causes
        before_ids = set(_listish(None if b is None else b["receipt_entry_ids"]))
        after_ids = set(_listish(None if a is None else a["receipt_entry_ids"]))
        row["entries_added"] = sorted(after_ids - before_ids)
        row["entries_removed"] = sorted(before_ids - after_ids)
        codes = []
        if pid in slim_left and pid in slim_right and changed:
            codes = reason_codes(slim_left[pid], slim_right[pid], eps=MOVE_EPS)
        row["reason_codes"] = json.dumps(codes)
        pillar_unattributed = any(code.get("causes") == ["unattributed"] for code in codes)
        moved = bool(changed) or (row["delta"] is not None and abs(row["delta"]) >= MOVE_EPS)
        fidelity_ok = base.get("fidelity") != "pillar_totals_only" and cand.get("fidelity") != "pillar_totals_only"
        row["run_causes"] = run_causes
        row["explained"] = (not moved) or bool(run_causes) or (fidelity_ok and bool(codes) and not pillar_unattributed)
        row["cause_fidelity"] = "pillar_causes" if fidelity_ok and codes else ("run_only" if run_causes else "pillar_deltas_only")
        rows.append(row)
    frame = pd.DataFrame(rows)
    numeric = ["total_before", "total_after", "delta", *[f"delta_{name}" for name in PILLARS]]
    for column in numeric:  # an all-None column would otherwise be object dtype
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _slim_map(read: TableReader, run: dict[str, Any]) -> dict[str, dict]:
    if run.get("fidelity") == "pillar_totals_only":
        return {}
    frame = read(run["run_key"], "slim")
    return {pid: json.loads(text) for pid, text in zip(frame["dsld_id"], frame["slim_json"])}


def summarize(deltas: pd.DataFrame) -> dict[str, int]:
    if deltas.empty:
        return {}
    both = deltas[deltas["presence"] == "both"]
    return {
        "products": int(len(deltas)),
        "added": int((deltas["presence"] == "added").sum()),
        "removed": int((deltas["presence"] == "removed").sum()),
        "moved": int((both["delta"].abs() >= MOVE_EPS).sum()),
        "tier_crossed": int(both["tier_crossed"].sum()),
        "status_changed": int(both["status_changed"].sum()),
        "safety_changed": int(both["safety_changed"].sum()),
        "unexplained": int((~both["explained"]).sum()),
    }
