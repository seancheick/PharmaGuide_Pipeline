"""Per-product rule changes between two replay --full --blob record dirs.
argv: BASE_RECORDS CAND_RECORDS OUT_TSV"""
import csv, gzip, json, sys
from pathlib import Path

BASE, CAND, OUT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]


def warnings(path):
    blob = json.load(gzip.open(path, "rt")).get("blob") or {}
    out = {}
    for w in (blob.get("warnings") or []) + (blob.get("warnings_profile_gated") or []):
        if isinstance(w, dict) and w.get("source_rule_id"):
            out.setdefault(w["source_rule_id"], []).append(
                (w.get("alert_body"), w.get("action"), w.get("detail")))
    return blob.get("product_name"), out


rows = []
for p in sorted(BASE.glob("*.json.gz")):
    q = CAND / p.name
    if not q.exists():
        continue
    name, a = warnings(p)
    _, b = warnings(q)
    added, removed = sorted(set(b) - set(a)), sorted(set(a) - set(b))
    reworded = sorted(r for r in set(a) & set(b) if sorted(map(str, a[r])) != sorted(map(str, b[r])))
    if added or removed or reworded:
        change = "added" if added else "removed" if removed else "reworded"
        rows.append([p.name.split(".")[0], name, change, ";".join(added), ";".join(removed), ";".join(reworded)])
with open(OUT, "w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(["id", "product", "change", "rules_added", "rules_removed", "rules_reworded"])
    writer.writerows(rows)
counts = {}
for row in rows:
    counts[row[2]] = counts.get(row[2], 0) + 1
print(counts)
