"""Report-only census: detail-blob ingredient-row keys not declared in audit_contract_sync.

usage (repo root): python3 scripts/audits/ingredient_row_key_census_20260925/census.py [build_dir]
build_dir defaults to scripts/dist. Reads blobs only; changes nothing.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_contract_sync import ACTIVE_CONTRACT, INACTIVE_CONTRACT, BLOB_TOP_LEVEL  # noqa: E402

build = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scripts" / "dist"
paths = sorted((build / "detail_blobs").glob("*.json"))
top_undeclared = set()
counts = {s: collections.Counter() for s in ("ingredients", "inactive_ingredients")}
rows = collections.Counter()
for path in paths:
    blob = json.loads(path.read_text())
    top_undeclared |= set(blob) - set(BLOB_TOP_LEVEL)
    for section, contract in (("ingredients", ACTIVE_CONTRACT), ("inactive_ingredients", INACTIVE_CONTRACT)):
        for row in blob.get(section) or []:
            if isinstance(row, dict):
                rows[section] += 1
                counts[section].update(k for k in row if k not in contract)

print(f"blobs={len(paths)} top_level_undeclared={sorted(top_undeclared)}")
for section, contract in (("ingredients", ACTIVE_CONTRACT), ("inactive_ingredients", INACTIVE_CONTRACT)):
    print(f"{section}: rows={rows[section]} declared={len(contract)} undeclared={len(counts[section])}")
    for key, n in counts[section].most_common():
        print(f"  {key} {n}")
