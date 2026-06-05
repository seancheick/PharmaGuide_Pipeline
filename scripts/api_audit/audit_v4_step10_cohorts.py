"""V4 Step 10 — Validation Cohorts + automated cutover gates.

Single runnable harness for the v4-finalization Step 10 exit gate. Consumes the
v3↔v4 comparison rows from `v4_full_corpus_delta.build_rows` (shipped v3 scored
artifacts as baseline, fresh v4 shadow scores) and produces:

  1. The 4 AUTOMATED cutover gates (GREEN/RED):
       G1  shipped_safety_downgrades == 0   (v3 CAUTION+ → v4 more permissive)
       G2  no confirmed banned/recalled product becomes v4 SAFE
       G3  no v3-scored product becomes v4 NOT_SCORED (unexplained)
       G4  no product is v4 CAUTION solely because of ADJUNCT missing data
           (reported as review candidates — adjunct attribution needs an eye)

  2. The 8 MANUAL review cohorts, each written as a scaffold CSV with a
     `classification` slot per product (correct | tune | data_issue |
     deliberate_v3_divergence):
       - balanced_side_by_side (100)     [delegates to v4_side_by_side_review.py]
       - recovered_blends (100)
       - botanical (50)
       - collagen (50)
       - probiotic_primary (50) + probiotic_multi_adjunct (50)
       - omega (50) + sports (50)
       - threshold_near (50)

Run AFTER a fresh full pipeline run so the enriched+scored artifacts under
--products-root reflect all landed fixes. Deterministic selection (sorted by
dsld_id) so cohorts are reproducible.

  python3 scripts/api_audit/audit_v4_step10_cohorts.py
  python3 scripts/api_audit/audit_v4_step10_cohorts.py --products-root <dir> --dist-db <v3.db>

Exit 0 iff G1-G3 are GREEN. G4 + cohorts are always advisory (manual review).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_ROOT.parent
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit"), str(SCRIPTS_ROOT / "scoring_v4")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import v4_full_corpus_delta as delta  # noqa: E402
import v4_shadow_canary_report as canary  # noqa: E402  (index builders + helpers)

DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_step10_validation"

_SAFE = "SAFE"
_NOT_SCORED = "NOT_SCORED"
# Safety ordering: SAFE is the most permissive; a move to any of these is a downgrade.
_WORSE_THAN_SAFE = {"POOR", "CAUTION", "UNSAFE", "BLOCKED", "NOT_SCORED"}


def _norm(v: Any) -> str:
    return str(v or "").strip().upper()


# ─── Automated gates ────────────────────────────────────────────────────────

# Canonical safety lattice (matches v4_full_corpus_delta.write_verdict_flips_csv).
# Higher = more cautious. A SAFETY DOWNGRADE is the dangerous direction: v3 flagged
# the product (CAUTION+) and v4 made it MORE permissive (under-warning). v3 SAFE →
# v4 CAUTION is the conservative direction and is NOT a downgrade.
_SAFETY_RANK = {"BLOCKED": 4, "UNSAFE": 3, "CAUTION": 2, "POOR": 1, "SAFE": 0}


def gate_safety_downgrades(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """G1 (canonical): v3 was CAUTION+ and v4 made it strictly more permissive —
    the under-warning regression. Mirrors write_verdict_flips_csv's flip_kind."""
    hits = []
    for r in rows:
        if not r.get("in_shipped_universe", True):
            continue
        v3 = _SAFETY_RANK.get(_norm(r.get("v3_verdict")))
        v4 = _SAFETY_RANK.get(_norm(r.get("v4_verdict")))
        if v3 is not None and v4 is not None and v3 >= _SAFETY_RANK["CAUTION"] and v4 < v3:
            hits.append(r)
    return {"name": "G1_shipped_safety_downgrades", "count": len(hits),
            "green": len(hits) == 0, "examples": _examples(hits)}


def metric_new_cautions(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Advisory (NOT a blocker): v3 SAFE → v4 CAUTION/BLOCKED. The conservative
    direction — v4 adding a caution v3 lacked. Worth eyeballing for over-warning,
    but adding caution is never a safety regression."""
    hits = [r for r in rows
            if r.get("in_shipped_universe", True)
            and _norm(r.get("v3_verdict")) == _SAFE
            and _norm(r.get("v4_verdict")) in {"CAUTION", "UNSAFE", "BLOCKED"}]
    return {"name": "M_new_cautions_v3safe_to_v4caution", "count": len(hits),
            "green": True, "advisory": True, "examples": _examples(hits)}


def _has_banned_or_recalled(r: Dict[str, Any], enriched_index: Dict[str, Any]) -> bool:
    e = enriched_index.get(str(r.get("dsld_id"))) or {}
    if e.get("has_banned_substance") or e.get("has_recalled_ingredient"):
        return True
    # active-row safety flags (banned/recalled) — RYR-style alias matches
    for a in (e.get("activeIngredients") or []):
        if not isinstance(a, dict):
            continue
        for fl in (a.get("safety_flags") or []):
            if isinstance(fl, dict) and _norm(fl.get("status")) in {"BANNED", "RECALLED"}:
                return True
    # v3 already gated it for safety
    return _norm(r.get("v3_safety_verdict")) in {"BLOCKED", "UNSAFE"}


def gate_banned_not_safe(rows: List[Dict[str, Any]], enriched_index: Dict[str, Any]) -> Dict[str, Any]:
    """G2: a confirmed banned/recalled product must never be v4 SAFE."""
    hits = [r for r in rows
            if _norm(r.get("v4_verdict")) == _SAFE and _has_banned_or_recalled(r, enriched_index)]
    return {"name": "G2_banned_recalled_became_safe", "count": len(hits),
            "green": len(hits) == 0, "examples": _examples(hits)}


def gate_new_not_scored(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """G3: a product v3 could score must not silently become v4 NOT_SCORED."""
    hits = [r for r in rows
            if _norm(r.get("v3_verdict")) not in {"", _NOT_SCORED}
            and _norm(r.get("v4_verdict")) == _NOT_SCORED]
    return {"name": "G3_v3_scored_to_v4_not_scored", "count": len(hits),
            "green": len(hits) == 0, "examples": _examples(hits)}


_ADJUNCT_HINT_TERMS = ("adjunct", "secondary", "minor")


def gate_adjunct_caution(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """G4 (advisory): v4 CAUTION whose only completeness gap looks adjunct-driven.
    Adjunct attribution can't be proven from the row alone, so these are emitted
    as REVIEW CANDIDATES, not a hard failure."""
    cands = []
    for r in rows:
        if _norm(r.get("v4_verdict")) != "CAUTION":
            continue
        missing = [str(m).lower() for m in (r.get("v4_completeness_missing") or [])]
        if missing and any(any(t in m for t in _ADJUNCT_HINT_TERMS) for m in missing):
            cands.append(r)
    return {"name": "G4_adjunct_driven_caution_candidates", "count": len(cands),
            "green": True, "advisory": True, "examples": _examples(cands)}


def _examples(rows: List[Dict[str, Any]], n: int = 12) -> List[Dict[str, Any]]:
    out = []
    for r in sorted(rows, key=lambda x: str(x.get("dsld_id")))[:n]:
        out.append({"dsld_id": r.get("dsld_id"), "product_name": r.get("product_name"),
                    "v3_verdict": r.get("v3_verdict"), "v4_verdict": r.get("v4_verdict"),
                    "v3_score": r.get("v3_shipped_score"), "v4_score": r.get("v4_score"),
                    "module": r.get("v4_module")})
    return out


# ─── Cohort selectors ───────────────────────────────────────────────────────

def _scored(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in rows if r.get("status") == "scored" and r.get("v4_score") is not None]


def _module_is(r: Dict[str, Any], module: str) -> bool:
    return _norm(r.get("v4_module")) == _norm(module)


def _is_botanical(r: Dict[str, Any]) -> bool:
    md = r.get("v4_module_metadata") or {}
    prof = str(md.get("profile") or md.get("profile_type") or "").lower()
    return "botanical" in prof or _norm(r.get("primary_class")) == "HERBAL_BOTANICAL"


def _is_collagen(r: Dict[str, Any]) -> bool:
    md = r.get("v4_module_metadata") or {}
    prof = str(md.get("profile") or md.get("profile_type") or "").lower()
    return "collagen" in prof or _norm(r.get("primary_class")) == "COLLAGEN"


def _is_recovered_blend(r: Dict[str, Any]) -> bool:
    # v4 produced a real score for a proprietary-blend product (blend signal comes
    # from the enriched proprietary_data, annotated onto the row in build_cohorts).
    return bool(r.get("_has_blend")) and r.get("v4_score") is not None


def _is_threshold_near(r: Dict[str, Any], band: float = 2.5) -> bool:
    s = r.get("v4_score")
    if s is None:
        return False
    # POOR/SAFE/CAUTION boundaries live around the verdict cutoffs; flag products
    # within `band` points of a 5-point gridline as boundary-sensitive.
    for edge in (40.0, 50.0, 60.0):
        if abs(s - edge) <= band:
            return True
    return False


def _take(rows: List[Dict[str, Any]], pred: Callable[[Dict[str, Any]], bool], n: int) -> List[Dict[str, Any]]:
    sel = [r for r in _scored_cache if pred(r)]
    return sorted(sel, key=lambda x: str(x.get("dsld_id")))[:n]


_scored_cache: List[Dict[str, Any]] = []

COHORT_FIELDS = ["dsld_id", "product_name", "brand_name", "v4_module",
                 "v3_verdict", "v3_shipped_score", "v4_verdict", "v4_score",
                 "score_delta_vs_v3", "v4_dimensions", "compression_flags",
                 "classification", "reviewer_note"]


def _write_cohort(rows: List[Dict[str, Any]], out_dir: Path, name: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COHORT_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({
                "dsld_id": r.get("dsld_id"), "product_name": r.get("product_name"),
                "brand_name": r.get("brand_name"), "v4_module": r.get("v4_module"),
                "v3_verdict": r.get("v3_verdict"), "v3_shipped_score": r.get("v3_shipped_score"),
                "v4_verdict": r.get("v4_verdict"), "v4_score": r.get("v4_score"),
                "score_delta_vs_v3": r.get("score_delta_vs_v3"),
                "v4_dimensions": json.dumps(r.get("v4_dimensions") or {}),
                "compression_flags": json.dumps(r.get("compression_flags") or []),
                "classification": "",  # reviewer fills: correct|tune|data_issue|deliberate_v3_divergence
                "reviewer_note": "",
            })
    return len(rows)


def build_cohorts(rows: List[Dict[str, Any]], out_root: Path,
                  enriched_index: Dict[str, Any] | None = None) -> Dict[str, Any]:
    global _scored_cache
    _scored_cache = _scored(rows)
    # Annotate each scored row with enriched-side signals the selectors need
    # (proprietary blend / probiotic content) — these don't live on the v4 row.
    ei = enriched_index or {}
    for r in _scored_cache:
        e = ei.get(str(r.get("dsld_id"))) or {}
        pdata = e.get("proprietary_data") if isinstance(e.get("proprietary_data"), dict) else {}
        prob = e.get("probiotic_data") if isinstance(e.get("probiotic_data"), dict) else {}
        r["_has_blend"] = bool(pdata.get("has_proprietary_blends"))
        r["_has_probiotic_data"] = bool(prob.get("is_probiotic_product"))
    specs = [
        ("recovered_blends", _is_recovered_blend, 100, "v4_recovered_blends"),
        ("botanical", _is_botanical, 50, "v4_botanical_review"),
        ("collagen", _is_collagen, 50, "v4_collagen_review"),
        ("probiotic_primary", lambda r: _module_is(r, "probiotic"), 50, "v4_probiotic_review"),
        ("probiotic_multi_adjunct",
         lambda r: _module_is(r, "multi_or_prenatal") and bool(r.get("_has_probiotic_data")),
         50, "v4_probiotic_review"),
        ("omega", lambda r: _module_is(r, "omega"), 50, "v4_omega_sports_review"),
        ("sports", lambda r: _module_is(r, "sports"), 50, "v4_omega_sports_review"),
        ("threshold_near", _is_threshold_near, 50, "v4_threshold_review"),
    ]
    counts: Dict[str, Any] = {}
    for name, pred, n, subdir in specs:
        sel = _take(rows, pred, n)
        counts[name] = _write_cohort(sel, REPO_ROOT / "reports" / subdir, name)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--products-root", type=Path, default=delta.DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--dist-db", type=Path, default=delta.DEFAULT_DIST_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--cohorts-only", action="store_true",
                        help="skip gates; just emit cohort scaffolds")
    args = parser.parse_args()

    enriched_index = canary.build_enriched_index(args.products_root)
    scored_index = canary.build_scored_index(args.products_root)
    if not scored_index:
        print(f"ERROR: no shipped v3 scored outputs under {args.products_root}", file=sys.stderr)
        return 1
    shipped = delta.load_shipped_universe(args.dist_db)
    rows = delta.build_rows(enriched_index, scored_index)
    for r in rows:
        r["in_shipped_universe"] = (not shipped) or (r.get("dsld_id") in shipped)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    gates = []
    if not args.cohorts_only:
        gates = [
            gate_safety_downgrades(rows),
            gate_banned_not_safe(rows, enriched_index),
            gate_new_not_scored(rows),
            gate_adjunct_caution(rows),
            metric_new_cautions(rows),
        ]

    cohorts = build_cohorts(rows, args.out_dir, enriched_index)

    hard_gates = [g for g in gates if not g.get("advisory")]
    green = all(g["green"] for g in hard_gates)
    summary = {
        "products_compared": len(rows),
        "scored_v4": len(_scored(rows)),
        "gates": gates,
        "hard_gates_green": green,
        "cohort_counts": cohorts,
    }
    (args.out_dir / "step10_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"hard_gates_green": green,
                      "gates": [{"name": g["name"], "count": g["count"], "green": g["green"]} for g in gates],
                      "cohort_counts": cohorts}, indent=2))
    return 0 if green else 1


if __name__ == "__main__":
    raise SystemExit(main())
