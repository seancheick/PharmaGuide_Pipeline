"""Compare Bulk 1340 enriched snapshot records against live DSLD (2026-09-19).

Team instruction #5/#8: classify each of the five quarantined Bulk 1340
products as unchanged_since_snapshot vs changed_upstream, with row-level
diff for the nutrients driving the safety/completeness gates.
"""
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

SNAPSHOT = Path("/tmp/bulk1340_enriched.json")


def fetch_live(dsld_id):
    url = f"https://api.ods.od.nih.gov/dsld/v9/label/{dsld_id}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def walk_live(rows, out):
    """Flatten live ingredientRows including nestedRows with quantized amounts."""
    for row in rows:
        quantities = row.get("quantity") or []
        per_serving = None
        for q in quantities:
            if not isinstance(q, dict):
                continue
            if q.get("servingSizeQuantity") == 360 or len(quantities) == 1:
                per_serving = q.get("quantity")
                break
        out.append(
            {
                "name": str(row.get("name") or row.get("originalIngredient") or "").strip(),
                "per_serving": per_serving,
                "unii": row.get("uniiCode"),
            }
        )
        walk_live(row.get("nestedRows") or [], out)


def snapshot_rows(rec):
    out = []
    for row in rec.get("activeIngredients") or []:
        out.append((str(row.get("name")), float(row.get("quantity") or 0), str(row.get("unit"))))
    return out


def live_rows_360g(live):
    out = []
    for row in live.get("ingredientRows") or []:
        flat = []
        walk_live([row], flat)
        out.extend(flat)
    return out


def main():
    hits = json.loads(SNAPSHOT.read_text())
    report = {}
    for pid, rec in sorted(hits.items()):
        live = fetch_live(pid)
        snap_rows = snapshot_rows(rec)
        live_flat = live_rows_360g(live)
        live_named = {}
        for entry in live_flat:
            if entry["name"]:
                live_named.setdefault(entry["name"].lower(), []).append(entry)

        snap_names = {n.lower() for n, _, _ in snap_rows}
        live_names = set(live_named.keys())

        only_snapshot = sorted(snap_names - live_names)
        only_live = sorted(live_names - snap_names)
        report[pid] = {
            "live_fullName": live.get("fullName"),
            "live_src": live.get("src"),
            "snapshot_row_count": len(snap_rows),
            "live_row_count": len(live_flat),
            "rows_only_in_snapshot": only_snapshot,
            "rows_only_in_live": only_live,
        }
    out = REPO / "reports" / "quarantine_triage_2026_09_19" / "bulk1340_live_comparison.json"
    out.write_text(json.dumps(report, indent=2))
    for pid, r in report.items():
        print(f"=== {pid} {r['live_fullName']} ===")
        print(f"  snapshot rows={r['snapshot_row_count']} live rows={r['live_row_count']}")
        print(f"  only in snapshot: {r['rows_only_in_snapshot']}")
        print(f"  only in live: {r['rows_only_in_live']}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
