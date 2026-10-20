"""Static census: _named_in_title on main (OLD_REF) vs this checkout, over every
product_scoring_evidence row of the full-corpus baseline records.
argv: CHECKOUT OLD_REF RECORDS_DIR OUT_TSV"""
import ast, glob, gzip, json, subprocess, sys
CHECKOUT, OLD_REF, RECORDS, OUT = sys.argv[1:5]
sys.path.insert(0, f"{CHECKOUT}/scripts")
import scoring_input_contract as sic
old_src = subprocess.check_output(["git", "-C", CHECKOUT, "show", f"{OLD_REF}:scripts/scoring_input_contract.py"], text=True)
tree = ast.parse(old_src)
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_named_in_title")
ns = dict(vars(sic))
exec(compile(ast.Module(body=[fn], type_ignores=[]), "old", "exec"), ns)
old, new = ns["_named_in_title"], sic._named_in_title
rows = flips = 0
with open(OUT, "w") as out:
    out.write("dsld_id\ttitle\trow_name\tstandardName\tcanonical_id\told\tnew\n")
    for p in sorted(glob.glob(f"{RECORDS}/*.json.gz")):
        e = json.load(gzip.open(p, "rt")).get("enriched") or {}
        title = sic._norm(e.get("product_name") or e.get("fullName"))
        iqd = e.get("ingredient_quality_data") or {}
        seen = set()
        for r in (e.get("product_scoring_evidence") or []) + (iqd.get("ingredients") or []):
            if not isinstance(r, dict):
                continue
            key = (r.get("raw_source_path"), r.get("canonical_id"), r.get("name"))
            if key in seen:
                continue
            seen.add(key)
            rows += 1
            a, b = old(r, title), new(r, title)
            if a != b:
                flips += 1
                out.write(f"{e.get('id')}\t{e.get('product_name')}\t{r.get('name')}\t{r.get('standardName')}\t{r.get('canonical_id')}\t{a}\t{b}\n")
print(f"rows {rows} flips {flips}")
