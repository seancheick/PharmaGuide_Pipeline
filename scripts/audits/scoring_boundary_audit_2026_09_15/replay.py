"""Read-only full-corpus replay of the changed verification assembly boundary.

Uses the actual baseline/candidate assembler, never a copied scoring formula.
Does not regenerate, replace or publish product artifacts. Old module inputs
are held constant; fresh GMP-collector integration is covered separately.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def snapshot_probiotics(checkout, products_root):
    """Call one isolated checkout's real scorer; never copy scoring arithmetic."""
    sys.path.insert(0, str(checkout / "scripts"))
    from score_supplements_v4 import score_product_v4
    from scoring_v4.router import class_for_product
    from scoring_v4.config_registry import all_config_provenance
    from scoring_v4.quality_score import _config

    limits = {key: value["weight"] for key, value in _config()["pillars"].items()}
    files, rows, routes = [], {}, Counter()
    for path in sorted(products_root.glob("output_*_enriched/enriched/*.json")):
        if path.name.startswith("."):
            continue
        raw = path.read_bytes()
        products = json.loads(raw)
        if not isinstance(products, list):
            raise ValueError(f"Unexpected batch shape: {path}")
        files.append({"path": str(path.relative_to(products_root)),
                      "sha256": hashlib.sha256(raw).hexdigest(), "count": len(products)})
        for product in products:
            if not isinstance(product, dict):
                raise ValueError(f"Malformed product in {path}")
            route = class_for_product(product)
            routes[route] += 1
            if route != "probiotic":
                continue
            pid = str(product.get("dsld_id") or product.get("id") or "")
            if not pid or pid in rows:
                raise ValueError(f"Missing/duplicate routed product id: {pid!r}")
            result = score_product_v4(product)
            status, score = result.get("quality_score_status"), result.get("quality_score_v4_100")
            pillars = result.get("quality_pillars_v4") or {}
            def bounded(value, cap):
                return (not isinstance(value, bool) and isinstance(value, (int, float))
                        and math.isfinite(value) and 0 <= value <= cap)
            if status not in {"scored", "not_scored", "suppressed_safety"}:
                raise ValueError(f"Invalid status for {pid}: {status}")
            if status == "scored":
                if (not bounded(score, 100) or set(pillars) != set(limits)
                        or any(not isinstance(pillars[key], dict)
                               or not bounded(pillars[key].get("score"), cap)
                               for key, cap in limits.items())):
                    raise ValueError(f"Incomplete public score for {pid}")
            elif score is not None:
                raise ValueError(f"Unexpected public number for {status}: {pid}")
            # This entry point returns v4_breakdown; _v4_module_breakdown is
            # the later artifact projection, not the scorer's return shape.
            dims = ((result.get("v4_breakdown") or {}).get("module") or {}).get("dimensions") or {}
            if status == "scored" and any(
                not isinstance(dims.get(key), dict)
                for key in ("formulation", "dose", "transparency")
            ):
                raise ValueError(f"Missing module dimensions for {pid}")
            rows[pid] = {
                "name": product.get("product_name"), "status": status, "score": score,
                "pillars": pillars,
                "dimensions": {key: dims.get(key) for key in ("formulation", "dose", "transparency")},
            }
    if not rows or not any(row["status"] == "scored" for row in rows.values()):
        raise ValueError("No scored probiotic products: comparison would be vacuous")
    git = lambda *args: subprocess.run(["git", "-C", str(checkout), *args],
                                      capture_output=True, check=True).stdout
    return {"_meta": {
        "scope": "all stored enriched products routed as probiotic; no regeneration",
        "checkout_commit": git("rev-parse", "HEAD").decode().strip(),
        "checkout_dirty": bool(git("status", "--porcelain").strip()),
        "tracked_diff_sha256": hashlib.sha256(git("diff", "--binary", "HEAD")).hexdigest(),
        "scoring_configs": all_config_provenance(), "input_files": files,
        "routes": dict(routes), "count": len(rows),
    }, "products": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="515ef8c5")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--probiotic-checkout", type=Path,
                        help="Snapshot probiotic public scores using this isolated checkout")
    parser.add_argument("--products-root", type=Path, default=ROOT / "scripts/products")
    args = parser.parse_args()
    if args.probiotic_checkout:
        report = snapshot_probiotics(args.probiotic_checkout.resolve(), args.products_root.resolve())
        args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps({key: value for key, value in report["_meta"].items()
                          if key not in {"input_files", "scoring_configs"}}))
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    from scoring_v4.quality_score import _pillar_verification, _config
    source = subprocess.run(["git", "show", f"{args.baseline}:scripts/scoring_v4/quality_score.py"],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    baseline = {"__name__": "scoring_v4.audit_baseline", "__file__": str(ROOT / "scripts/scoring_v4/quality_score.py")}
    exec(compile(source, baseline["__file__"], "exec"), baseline)
    changes, transitions, statuses = [], Counter(), Counter()
    checked = 0
    cfg = _config()
    for path in sorted((ROOT / "scripts/products").glob("output_*_scored/scored/*.json")):
        if path.name.startswith("."):
            continue
        products = json.loads(path.read_text())
        if not isinstance(products, list):
            raise ValueError(f"Unexpected batch shape: {path}")
        for product in products:
            statuses[product.get("quality_score_status")] += 1
            bd = product.get("_v4_module_breakdown")
            if not bd:
                continue
            before = baseline["_pillar_verification"](bd, 15, cfg)
            after = _pillar_verification(bd, 15, cfg)
            checked += 1
            if before["score"] != after["score"] or before["components"]["tier"] != after["components"]["tier"]:
                transitions[f'{before["components"]["tier"]} -> {after["components"]["tier"]}'] += 1
                changes.append({"id": product.get("dsld_id") or product.get("id"),
                                "before": before, "after": after})
    report = {"baseline": args.baseline, "scope": "verification pillar, frozen stored module inputs; not a rebuilt catalog",
              "statuses": dict(statuses), "checked": checked, "changed": len(changes),
              "transitions": dict(transitions), "changes": changes}
    if not checked:
        raise ValueError("Empty corpus")
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "changes"}))


if __name__ == "__main__":
    main()
