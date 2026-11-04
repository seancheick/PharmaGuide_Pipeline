#!/usr/bin/env python3
"""Compare strict scoring contract failures in stored scored output with this audit's list.

Usage: compare_strict_contract.py <products_root> [<scored_root_pattern>]
Default pattern: output_*_scored/scored/scored_*.json. Reads only; exits 1 on any difference.
strict_contract_findings.json holds the ids and reasons the rescore at eb47098a8 reported.
"""
import glob
import json
import sys
from pathlib import Path


def main():
    root = sys.argv[1]
    pattern = sys.argv[2] if len(sys.argv) > 2 else "output_*_scored/scored/scored_*.json"
    expected = json.loads((Path(__file__).parent / "strict_contract_findings.json").read_text(encoding="utf-8"))
    found, products = {}, 0
    for path in glob.glob(f"{root}/{pattern}"):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for product in data if isinstance(data, list) else data.get("products", []):
            products += 1
            contract = product.get("strict_scoring_contract") or {}
            if contract.get("passed") is False:
                found[str(product.get("dsld_id"))] = contract.get("findings")
    only_expected = sorted(set(expected) - set(found))
    only_found = sorted(set(found) - set(expected))
    changed = sorted(key for key in set(expected) & set(found) if expected[key] != found[key])
    print(f"products {products}, listed {len(expected)}, found {len(found)}")
    print(f"only listed {only_expected}\nonly found {only_found}\nreason changed {changed}")
    sys.exit(1 if only_expected or only_found or changed else 0)


if __name__ == "__main__":
    main()
