"""Corpus rows whose name contains an allergen alias as words but whose product has no hit for it."""
import json, re, sys, glob
from collections import Counter, defaultdict
W = str(__import__("pathlib").Path(__file__).resolve().parents[3])
A = json.load(open(f"{W}/scripts/data/allergens.json"))["allergens"]
def norm(t): return re.sub(r"[^a-z0-9]+", " ", str(t or "").lower()).strip()
terms = []
for e in A:
    for t in {norm(e["standard_name"]), *(norm(a) for a in e.get("aliases", []))}:
        if t: terms.append((t, e["id"]))
terms.sort(key=lambda x: -len(x[0]))
rows = []
products = 0
for f in sorted(glob.glob("/Users/seancheick/Downloads/dsld_clean/scripts/products/output_*_enriched/enriched/*.json")):
    for p in json.load(open(f)):
        products += 1
        hit_ids = {h.get("allergen_id") for h in p.get("allergen_hits") or []}
        for sec in ("activeIngredients", "inactiveIngredients"):
            for ing in p.get(sec) or []:
                name = norm(ing.get("name")); std = norm(ing.get("standardName"))
                for t, aid in terms:
                    pat = rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])"
                    if re.search(pat, name) or re.search(pat, std):
                        if aid not in hit_ids:
                            rows.append({"id": p.get("id"), "brand": f.split("output_")[1].split("_enriched")[0], "sec": sec, "name": ing.get("name"), "std": ing.get("standardName"), "term": t, "allergen": aid})
                        break
print("products", products, "candidate_rows", len(rows), "products_affected", len({r['id'] for r in rows}))
by = Counter((r["allergen"]) for r in rows); print(by.most_common())
names = Counter((r["allergen"], norm(r["name"])) for r in rows)
json.dump(rows, open(sys.argv[1], "w"), indent=1)
for (a, n), c in names.most_common(120): print(c, a, "|", n)
