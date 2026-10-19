#!/usr/bin/env python3
"""Add the NASEM child Tolerable Upper Intake Levels to scripts/data/rda_optimal_uls.json.

One explicit patch per nutrient, transcribed by hand from the National Academies DRI summary
tables (NCBI Bookshelf NBK545442, Appendix J): Tolerable Upper Intake Levels, Vitamins
(https://www.ncbi.nlm.nih.gov/books/NBK545442/table/appJ_tab8/) and Elements
(https://www.ncbi.nlm.nih.gov/books/NBK545442/table/appJ_tab9/), read 2026-10-19. Receipts per entry:
research.md beside this script.

Rows carry the UL only (``rda_ai`` null): adequacy stays on the adult reference profile; the rows
exist for the label-population safety screen. NASEM's "Children 1-3 y / 4-8 y" rows are not
sex-specific, so they are written for both Male and Female; its 9-13 y Male and Female values are
identical for every nutrient below. Vanadium is deliberately absent (table note d: the animal data
"could be used to set a UL for adults but not children and adolescents"), so a child label keeps
its explicit reference gap for vanadium.

    $PG_PYTHON scripts/audits/pediatric_ul_rows_20261019/apply.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

import data_batch  # noqa: E402
from reference_data_contract import semantic_rda_ul_fingerprint  # noqa: E402

DATA = REPO / "scripts" / "data" / "rda_optimal_uls.json"
REFERENCE_VERSION = "5.1.6-2026-10-19-folate-ul-label-units"
AGES = ("1-3", "4-8", "9-13")

# id: (UL 1-3 y, UL 4-8 y, UL 9-13 y) in the record's own unit.
CHILD_ULS = {
    # Vitamins table (appJ_tab8)
    "vitamin_a": (600, 900, 1700),      # mcg RAE; table: preformed vitamin A, ug/d
    "vitamin_c": (400, 650, 1200),      # mg
    "vitamin_d": (63, 75, 100),         # mcg
    "vitamin_e": (200, 300, 600),       # mg alpha-tocopherol; any supplemental form
    "niacin": (10, 15, 20),             # record unit mg NE; table mg/d synthetic forms
    "vitamin_b6": (30, 40, 60),         # mg
    "folate": (510, 680, 1020),         # mcg DFE; table 300/400/600 ug folic acid x 1.7 (canonical FDA label units)
    "choline": (1000, 1000, 2000),      # mg; table 1.0/1.0/2.0 g/d
    # Elements table (appJ_tab9)
    "boron": (3, 6, 11),                # mg
    "calcium": (2500, 2500, 3000),      # mg
    "copper": (1000, 3000, 5000),       # mcg
    "fluoride": (1.3, 2.2, 10),         # mg
    "iodine": (200, 300, 600),          # mcg
    "iron": (40, 40, 40),               # mg
    "magnesium": (65, 110, 350),        # mg; pharmacological agents only (table note b)
    "manganese": (2, 3, 6),             # mg
    "molybdenum": (300, 600, 1100),     # mcg
    "nickel": (0.2, 0.3, 0.6),          # mg; soluble nickel salts
    "phosphorus": (3000, 3000, 4000),   # mg; table 3/3/4 g/d
    "selenium": (90, 150, 280),         # mcg
    "zinc": (7, 12, 23),                # mg
    "chloride": (2300, 2900, 3400),     # mg; table 2.3/2.9/3.4 g/d
}


def child_rows(group: str, uls: tuple) -> list[dict]:
    return [{"group": group, "age_range": age, "rda_ai": None, "ul": ul,
             "rda_ai_status": None, "ul_status": None} for age, ul in zip(AGES, uls)]


def main() -> int:
    blob = data_batch.load(DATA)
    by_id = {record["id"]: record for record in blob["nutrient_recommendations"]}
    for nutrient_id, uls in CHILD_ULS.items():
        record = by_id[nutrient_id]
        rows = record["data"]
        if any(row.get("age_range") in AGES for row in rows):
            raise SystemExit(f"{nutrient_id} already has child rows")
        out = []
        for group in ("Male", "Female"):
            out += child_rows(group, uls)
            out += [row for row in rows if row.get("group") == group]
        out += [row for row in rows if row.get("group") not in {"Male", "Female"}]
        assert len(out) == len(rows) + 6, nutrient_id
        record["data"] = out
    # Keep the initial batch recipe consistent with the follow-up unit correction.
    # Native folic-acid limits do not change; both sides use FDA label DFE x1.7.
    folate = by_id["folate"]
    for row in folate["data"]:
        row["ul"] = {1334: 1360, 1667: 1700}.get(row.get("ul"), row.get("ul"))
    folate["highest_ul"] = 1700
    folate["ul_note"] = ("UL is 1000 mcg/day of synthetic folic acid. Stored as 1700 mcg DFE using the same FDA label conversion (1.7) as unit_conversions.json, so exposure and limit share a unit convention. The physiological with-food DFE relation is separate; no underlying folic-acid UL changes. UL applies to synthetic folic acid from supplements and fortified foods only.")
    for key in ("preparation", "rationale"):
        folate["reference_semantics"][key] = folate["reference_semantics"][key].replace(
            "Existing1667DFE represents1000mcg synthetic folic acid with food conversion, not a new FNB UL.",
            "The stored1700 labelDFE represents1000mcg synthetic folic acid using the canonical FDA labeling factor1.7; this unit reconciliation does not change the FNB folic-acid UL.")
    contract = blob["_metadata"]["reference_data_contract"]
    contract["reference_version"] = REFERENCE_VERSION
    contract["semantic_fingerprint"] = semantic_rda_ul_fingerprint(blob)
    changes = data_batch.save(DATA, blob)
    print(f"patched {len(CHILD_ULS)} nutrients; recount changes: {changes}")
    print("fingerprint", contract["semantic_fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
