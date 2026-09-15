#!/usr/bin/env python3
"""Extract a frozen calibration packet, or create the pass-2 packet once.

Run from the repo root:
  select_packet.py [--packet pass1|pass2]
      Extract the enriched record for every id in the committed id file into
      scripts/products/_rubric_packet/<packet>_products.json (gitignored).
      Reproducible: ids are frozen, nothing is re-selected.
  select_packet.py --create-pass2
      One-time: choose the generic-dose and verification groups, write
      packet_ids_pass2.json, then extract. Refuses to overwrite it.

Pass-1 groups were chosen once from the 2026-09-13 scored breakdowns (criteria
in git history at commit 7e810cae); their ids are frozen in packet_ids.json.
Pass-2 dose groups are verification-invariant (no testing data, no reputation,
no GMP points) so dose and verification changes cannot contaminate each other's
groups; verification groups exclude generic RDA-window products for the same reason.
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRODUCTS = ROOT / "scripts/products"
HERE = Path(__file__).resolve().parent
ID_FILES = {"pass1": HERE / "packet_ids.json", "pass2": HERE / "packet_ids_pass2.json"}
DIETARY_DOMINANT = {"potassium"}


def products_path(packet: str) -> Path:
    name = "packet_products.json" if packet == "pass1" else f"packet_{packet}_products.json"
    return PRODUCTS / "_rubric_packet" / name


def _enriched(wanted=None):
    for f in sorted(glob.glob(str(PRODUCTS / "output_*_enriched/enriched/*.json"))):
        for p in json.load(open(f)):
            pid = str(p.get("dsld_id") or p.get("id"))
            if wanted is None or pid in wanted:
                yield pid, p


def _pick(rows, n):
    rows = sorted(rows, key=lambda r: (not r["id"].isdigit(), int(r["id"]) if r["id"].isdigit() else 0, r["id"]))
    if len(rows) <= n:
        return rows
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def _window_rows(product):
    rows = []
    for row in ((product.get("rda_ul_data") or {}).get("adequacy_results") or []):
        if not isinstance(row, dict) or row.get("pct_rda") is None:
            continue
        if str(row.get("canonical_id") or row.get("nutrient") or "").lower() in DIETARY_DOMINANT:
            continue
        rows.append(row)
    return rows


def _positive(value) -> bool:
    """Return whether a legacy/current component carries a positive signal.

    Packet selection reads both the pre-1.3 ``soft`` component and the current
    ``reputation`` component.  Stored JSON may contain either numbers or numeric
    strings, so a truthiness check is not sufficient (``"0"`` is truthy).
    """
    try:
        return float(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _flag(value) -> bool:
    """Parse a stored boolean/flag without treating ``"false"`` as true."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none", "null"}
    return bool(value)


def _verification_selection_flags(v, claim_only: bool = False):
    """Classify verification signals for pass-2 packet selection.

    This intentionally understands both snapshot shapes: quality_score 1.2
    stored reputation/region under ``soft`` and quality_score 1.3 stores the
    same brand context under ``reputation``.  A label-only GMP claim is a
    claim-only group even though its public GMP component is now zero.
    """
    hard = any(_positive(v.get(key)) for key in (
        "cert", "coa_batch", "gmp", "brand_testing", "brand_only_cert",
    ))
    reputation = _positive(v.get("reputation")) or _positive(v.get("soft"))
    plain_unknown = not hard and not reputation and not claim_only
    # Reputation is still a claim/brand signal even when a product also has a
    # label-only GMP claim. Do not silently drop that overlap from the packet;
    # reserve the GMP-only group for claims with no other brand evidence.
    unknown_with_reputation = reputation and not hard
    return plain_unknown, unknown_with_reputation


def create_pass2() -> None:
    if ID_FILES["pass2"].exists():
        raise SystemExit("REFUSED: packet_ids_pass2.json exists; its ids are frozen")
    scored = {}
    for f in sorted(glob.glob(str(PRODUCTS / "output_*_scored/scored/*.json"))):
        for r in json.load(open(f)):
            if r.get("_v4_quality_status") != "scored":
                continue
            bd = r.get("_v4_module_breakdown") or {}
            scored[str(r["dsld_id"])] = {
                "module": r.get("_v4_module"),
                "window": "supplemental_window_proxy" in (((bd.get("dimensions") or {}).get("dose") or {}).get("components") or {}),
                "verif": (r.get("quality_pillars_v4") or {}).get("verification", {}).get("components") or {},
            }
    groups = defaultdict(list)
    for pid, p in _enriched():
        s = scored.get(pid)
        if s is None:
            continue
        v = s["verif"]
        row = {"id": pid, "module": s["module"], "name": p.get("product_name")}
        gmp = ((p.get("certification_data") or {}).get("gmp") or {})
        claim_only = _flag(gmp.get("claimed")) and not any(
            _flag(gmp.get(k)) for k in ("nsf_gmp", "gmp_certified_or_compliant", "fda_registered")
        )
        plain_unknown, unknown_with_reputation = _verification_selection_flags(v, claim_only)
        window = _window_rows(p)
        if s["module"] == "generic" and s["window"] and plain_unknown:
            if len(window) >= 3:
                groups["dose_multi_nutrient"].append(row)
            elif len(window) == 1:
                w = window[0]
                pct_rda, pct_ul = float(w["pct_rda"]), w.get("pct_ul")
                pct_ul = None if pct_ul is None else float(pct_ul)
                rda, ul = w.get("rda_ai"), w.get("ul")
                if pct_ul is not None and pct_ul > 100:
                    groups["control_dose_over_ul"].append(row)
                elif rda and ul and float(ul) < float(rda):
                    groups["dose_ul_below_rda"].append(row)
                elif pct_rda < 20:
                    groups["dose_below_20pct"].append(row)
                elif pct_rda < 100:
                    groups["dose_20_to_100pct"].append(row)
                else:
                    groups["control_dose_at_or_above_100pct"].append(row)
            continue
        if s["module"] == "generic" and s["window"]:
            continue
        cert = v.get("cert") or 0
        coa = v.get("coa_batch") or 0
        if _positive(coa) and not _positive(cert):
            groups["verif_batch_coa"].append(row)
        elif _positive(cert) and float(cert) >= 5:
            groups["verif_registry_cert"].append(row)
        elif _positive(cert) and float(cert) == 2:
            groups["verif_label_asserted_cert"].append(row)
        elif _positive(v.get("brand_only_cert")):
            groups["verif_brand_facility_cert"].append(row)
        elif claim_only and not _positive(v.get("reputation")) and not _positive(v.get("soft")):
            groups["verif_gmp_claim_only"].append(row)
        elif unknown_with_reputation:
            groups["verif_unknown_with_reputation"].append(row)
        elif plain_unknown:
            groups["control_verif_unknown_plain"].append(row)
    sizes = {"dose_multi_nutrient": 6, "dose_ul_below_rda": 6, "dose_below_20pct": 6, "dose_20_to_100pct": 8,
             "control_dose_over_ul": 5, "control_dose_at_or_above_100pct": 6, "verif_batch_coa": 6,
             "verif_registry_cert": 6, "verif_label_asserted_cert": 6, "verif_brand_facility_cert": 6,
             "verif_gmp_claim_only": 6, "verif_unknown_with_reputation": 6, "control_verif_unknown_plain": 6}
    packet = [{**r, "group": g} for g, n in sizes.items() for r in _pick(groups[g], n)]
    ID_FILES["pass2"].write_text(json.dumps({"_metadata": {
        "purpose": "Pass-2 packet (generic dose + verification). Groups prefixed control_ must not move.",
        "selected_on": "2026-09-14",
        "selected_from": "enriched facts + module and verification components of the 2026-09-13 scored outputs",
        "available_per_group": {g: len(groups[g]) for g in sizes}}, "products": packet}, indent=2) + "\n")


def extract(packet: str) -> None:
    ids = json.loads(ID_FILES[packet].read_text())["products"]
    wanted = {p["id"] for p in ids}
    records = dict(_enriched(wanted))
    missing = sorted(wanted - set(records))
    if missing:
        raise SystemExit(f"REFUSED: ids missing from enriched outputs: {missing}")
    out = products_path(packet)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([records[p["id"]] for p in ids]))
    counts = defaultdict(int)
    for p in ids:
        counts[p["group"]] += 1
    print(f"{packet}: {len(ids)} products -> {out}", dict(counts))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", choices=sorted(ID_FILES), default="pass1")
    parser.add_argument("--create-pass2", action="store_true")
    args = parser.parse_args()
    if args.create_pass2:
        create_pass2()
        extract("pass2")
    else:
        extract(args.packet)


if __name__ == "__main__":
    main()
