"""Second cohort: raw labels with a blend heading that prints a total over at least one
undisclosed member (the shape fresh enrichment projects as identity-bearing lent rows),
plus a seeded random sample of the rest. Excludes labels already frozen.

usage: select_cohort2.py raw_root already.json[,more.json] sample_n out.json
"""
import glob, json, random, sys

root, already_files, sample_n, out = sys.argv[1], sys.argv[2].split(","), int(sys.argv[3]), sys.argv[4]
already = set()
for f in already_files:
    already |= {str(x) for x in json.load(open(f))}


def qty(row):
    q = row.get("quantity") or []
    return max((float(x.get("quantity") or 0) for x in q if isinstance(x, dict)), default=0.0) if isinstance(q, list) else 0.0


def has_heading_total(rows):
    for row in rows or []:
        nested = row.get("nestedRows") or []
        if nested and qty(row) > 0 and any(qty(n) <= 0 for n in nested):
            return True
        if has_heading_total(nested):
            return True
    return False


structural, rest = [], []
for path in sorted(glob.glob(root + "/*/*.json")):
    pid = path.rsplit("/", 1)[1][:-5]
    if pid in already:
        continue
    try:
        raw = json.load(open(path))
    except Exception:
        continue
    (structural if has_heading_total(raw.get("ingredientRows")) else rest).append(pid)
random.Random(20261001).shuffle(rest)
sample = sorted(rest[:sample_n])
ids = sorted(set(structural) | set(sample))
json.dump(ids, open(out, "w"))
print("structural", len(structural), "sample", len(sample), "total", len(ids), "remaining_unsampled", len(rest) - len(sample))
