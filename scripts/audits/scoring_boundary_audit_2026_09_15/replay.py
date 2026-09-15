"""Read-only full-corpus replay of the changed verification assembly boundary.

Uses the actual baseline/candidate assembler, never a copied scoring formula.
Does not regenerate, replace or publish product artifacts. Old module inputs
are held constant; fresh GMP-collector integration is covered separately.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from scoring_v4.quality_score import _pillar_verification, _config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="515ef8c5")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
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
