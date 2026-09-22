"""Field census across every artifact layer (closure audit 2026-09-21).

For each field of each layer -- cleaned, enriched, scored, detail blob (top
level and the three row lists the app renders), core DB column -- report how
often it is present and populated in the real corpus, which code writes and
reads it (static, quoted-literal match), and whether the app reads it.

The census is a report, not a second declaration. The only hard failure is the
one the release already owns: a detail-blob top-level key missing from
audit_contract_sync.BLOB_TOP_LEVEL. Everything else is flagged for review:

  NO_CONSUMER      emitted, but no pipeline/dashboard/app reader found
  NEVER_POPULATED  present on products but always null/empty

Usage (from the repo root):
    python3 scripts/audits/closure_20260921/field_census.py \
        --products-dir scripts/products --build-dir scripts/final_db_output \
        --flutter-lib "$HOME/PharmaGuide ai/lib" --out /path/census.json
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from audit_contract_sync import BLOB_TOP_LEVEL  # noqa: E402

BLOB_ROW_LISTS = ("ingredients", "inactive_ingredients", "warnings")


def _populated(value) -> bool:
    return value not in (None, "", [], {})


def _count(records, layer_counts):
    for record in records:
        if not isinstance(record, dict):
            continue
        for key, value in record.items():
            entry = layer_counts[key]
            entry[0] += 1
            entry[1] += _populated(value)


def _product_file(path_and_layer):
    path, layer = path_and_layer
    counts = collections.defaultdict(lambda: [0, 0])
    products = json.load(open(path))
    _count(products, counts)
    return layer, len(products), {k: tuple(v) for k, v in counts.items()}


def _blob_chunk(paths):
    top = collections.defaultdict(lambda: [0, 0])
    rows = {name: collections.defaultdict(lambda: [0, 0]) for name in BLOB_ROW_LISTS}
    row_totals = collections.Counter()
    for path in paths:
        blob = json.load(open(path))
        _count([blob], top)
        for name in BLOB_ROW_LISTS:
            items = blob.get(name) or []
            row_totals[name] += len(items)
            _count(items, rows[name])
    return len(paths), {k: tuple(v) for k, v in top.items()}, {
        name: {k: tuple(v) for k, v in counts.items()} for name, counts in rows.items()}, row_totals


def _merge(into, counts):
    for key, (present, populated) in counts.items():
        entry = into.setdefault(key, [0, 0])
        entry[0] += present
        entry[1] += populated


def _sources(root: Path, exclude: tuple[str, ...], suffix: str) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text(errors="ignore")
        for path in root.rglob(f"*{suffix}")
        if not any(part in exclude for part in path.relative_to(root).parts)
    }


def _refs(key: str, sources: dict[str, str]) -> tuple[list[str], list[str]]:
    q = re.escape(key)
    read = re.compile(rf"""\.get\(\s*["']{q}["']|\[\s*["']{q}["']\s*\](?!\s*=[^=])|["']{q}["']\s+(?:not\s+)?in\b""")
    write = re.compile(rf"""["']{q}["']\s*:|\[\s*["']{q}["']\s*\]\s*=[^=]|setdefault\(\s*["']{q}["']""")
    readers = sorted(name for name, text in sources.items() if read.search(text))
    writers = sorted(name for name, text in sources.items() if write.search(text))
    return writers, readers


def _mentions(key: str, sources: dict[str, str], *, bare: bool = False) -> list[str]:
    # Core columns are also read inside raw SQL strings, where they are bare words.
    pattern = re.compile(rf"\b{re.escape(key)}\b" if bare else rf"""["']{re.escape(key)}["']""")
    return sorted(name for name, text in sources.items() if pattern.search(text))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--products-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--flutter-lib", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    products = Path(args.products_dir)
    jobs = [(p, "cleaned") for p in sorted(glob.glob(str(products / "output_*/cleaned/*.json")))]
    jobs += [(p, "enriched") for p in sorted(glob.glob(str(products / "output_*_enriched/enriched/*.json")))]
    jobs += [(p, "scored") for p in sorted(glob.glob(str(products / "output_*_scored/scored/*.json")))]
    layers = {"cleaned": {}, "enriched": {}, "scored": {}}
    totals = collections.Counter()
    blob_paths = sorted(glob.glob(str(Path(args.build_dir) / "detail_blobs" / "*.json")))
    blob_top: dict = {}
    blob_rows = {name: {} for name in BLOB_ROW_LISTS}
    with ProcessPoolExecutor(8) as pool:
        for layer, n, counts in pool.map(_product_file, jobs):
            totals[layer] += n
            _merge(layers[layer], counts)
        for n, top, rows, row_totals in pool.map(_blob_chunk, [blob_paths[i::8] for i in range(8)]):
            totals["blob"] += n
            _merge(blob_top, top)
            for name in BLOB_ROW_LISTS:
                _merge(blob_rows[name], rows[name])
                totals[f"blob.{name}[]"] += row_totals[name]
    layers["blob"] = blob_top
    for name in BLOB_ROW_LISTS:
        layers[f"blob.{name}[]"] = blob_rows[name]

    conn = sqlite3.connect(Path(args.build_dir) / "pharmaguide_core.db")
    core_total = conn.execute("SELECT COUNT(*) FROM products_core").fetchone()[0]
    totals["core"] = core_total
    layers["core"] = {}
    for (_, column, *_rest) in conn.execute("PRAGMA table_info(products_core)"):
        populated = conn.execute(
            f"SELECT COUNT(*) FROM products_core WHERE \"{column}\" IS NOT NULL AND CAST(\"{column}\" AS TEXT) NOT IN ('', '[]', '{{}}')"
        ).fetchone()[0]
        layers["core"][column] = [core_total, populated]

    pipeline = _sources(SCRIPTS, ("tests", "audits", "dashboard", "__pycache__", "products", "dist", "final_db_output"), ".py")
    dashboard = _sources(SCRIPTS / "dashboard", ("__pycache__",), ".py")
    flutter = _sources(Path(args.flutter_lib), (), ".dart")
    app_root = Path(args.flutter_lib).parent
    flutter.update({f"supabase/{k}": v for k, v in _sources(app_root / "supabase", ("node_modules",), ".ts").items()})
    flutter.update({f"supabase/{k}": v for k, v in _sources(app_root / "supabase", ("node_modules",), ".sql").items()})

    report = {"totals": dict(totals), "layers": {}, "flags": collections.Counter()}
    undeclared = sorted(set(blob_top) - set(BLOB_TOP_LEVEL))
    for layer, counts in layers.items():
        rows = {}
        for key in sorted(counts):
            present, populated = counts[key]
            writers, readers = _refs(key, pipeline)
            dash = _mentions(key, dashboard)
            app = _mentions(key, flutter, bare=(layer == "core"))
            flags = []
            if not readers and not dash and not app:
                flags.append("NO_CONSUMER")
            if present and not populated:
                flags.append("NEVER_POPULATED")
            if layer == "blob":
                spec = BLOB_TOP_LEVEL.get(key)
                declared = (spec or {}).get("presence") or ("required" if (spec or {}).get("required") else None)
            else:
                declared = None
            for flag in flags:
                report["flags"][f"{layer}:{flag}"] += 1
            rows[key] = {
                "present": present, "populated": populated,
                "writers": writers[:6], "readers": readers[:6],
                "dashboard": bool(dash), "flutter": app[:4],
                "declared": declared, "flags": flags,
            }
        report["layers"][layer] = rows
    report["blob_top_level_undeclared"] = undeclared
    report["flags"] = dict(report["flags"])
    Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True))

    print(json.dumps({"totals": report["totals"], "flags": report["flags"],
                      "blob_top_level_undeclared": undeclared}, indent=1))
    return 1 if undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())
