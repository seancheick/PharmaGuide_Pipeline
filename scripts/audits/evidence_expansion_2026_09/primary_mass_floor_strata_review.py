#!/usr/bin/env python3
"""The acceptance test for the primary-mass Evidence floor.

One question, thirteen strata:

    Does the floor prevent under-scoring of products with genuinely supportive
    REVIEWED evidence, without ever saying more than the evidence direction
    supports?

This does not re-derive anything. Policies come from the calibration module's
own ``build_policies`` and the anchor is found by its ``anchor_entry``, so there
is no second implementation of what a policy means. Directions come from
``generic_evidence``; reviewed provenance comes from
``clinical_applicability.reviewed_entries``. No new table, no new registry.

A stratum with no representative is printed as EMPTY. Two of them are empty
structurally rather than by luck: ``_EFFECT_FLOOR_MULTIPLIER`` maps null and
negative to 0.0 and ``_primary_mass_floor`` skips any anchor whose multiplier is
<= 0, so neither direction can anchor a floor under ANY policy.

usage:
  primary_mass_floor_strata_review.py --calibration primary_mass_floor_calibration.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1]
sys.path.insert(0, str(SCRIPTS))

import clinical_applicability as ca                      # noqa: E402
from scoring_v4.modules import generic_evidence as ge    # noqa: E402

POLICY = "direction_ceiling"


def decisive(row) -> bool:
    return row["policies"]["baseline"]["total"] != row["policies"]["no_primary_mass_floor"]["total"]


#: (key, question this stratum answers, predicate)
STRATA = [
    ("positive_strong_reviewed",
     "a reviewed positive_strong primary may keep the strong floor",
     lambda r: r["direction"] == "positive_strong" and r["floor_anchor_in_reviewed_registry"] and decisive(r)),
    ("positive_weak_reviewed",
     "positive_weak must NOT be promoted to a strong floor",
     lambda r: r["direction"] == "positive_weak" and r["floor_anchor_in_reviewed_registry"] and decisive(r)),
    ("mixed_reviewed",
     "mixed evidence must be ceiling-constrained",
     lambda r: r["direction"] == "mixed" and r["floor_anchor_in_reviewed_registry"] and decisive(r)),
    ("null_direction",
     "null evidence must never create an affirmative floor",
     lambda r: r["direction"] == "null"),
    ("negative_direction",
     "negative evidence must never create an affirmative floor",
     lambda r: r["direction"] == "negative"),
    ("unreviewed_anchor",
     "an anchor outside the reviewed registry must not pass as reviewed evidence",
     lambda r: r["floor_kind"] == "primary_mass" and not r["floor_anchor_in_reviewed_registry"] and decisive(r)),
    ("nutrition_authority",
     "adequacy stays separately owned and is held out of the comparison",
     lambda r: r["floor_kind"] == "nutrition_authority"),
    ("shadowed_by_pipeline",
     "when pipeline Evidence already exceeds the floor, final Evidence is unchanged",
     lambda r: r["floor_kind"] == "primary_mass" and not decisive(r)),
    ("branded_rct",
     "a branded RCT anchor behaves like its direction, not like its branding",
     lambda r: r["evidence_level"] == "branded-rct" and decisive(r)),
    ("product_human",
     "product-level human evidence behaves like its direction",
     lambda r: r["evidence_level"] == "product-human" and decisive(r)),
    ("strain_clinical",
     "strain-clinical evidence behaves like its direction",
     lambda r: r["evidence_level"] == "strain-clinical"),
    ("single_rct_anchor",
     "the weakest study type still cannot overstate its direction",
     lambda r: r["study_type"] == "rct_single" and decisive(r)),
    ("tier_changing",
     "a floor that moves the PUBLIC tier is the highest-visibility case",
     lambda r: r["floor_kind"] == "primary_mass"
               and r["policies"]["baseline"]["tier"] != r["policies"]["no_primary_mass_floor"]["tier"]),
]


def pick(rows, predicate):
    """Deterministic representative: first dsld_id in sorted order.

    Sorted as (is_not_numeric, width, text) so catalog ids order numerically and
    submission ids (PG_SUB_...) sort after them instead of raising.
    """
    hits = [r for r in rows if predicate(r)]
    if not hits:
        return None, 0

    def key(row):
        raw = str(row["dsld_id"])
        return (not raw.isdigit(), len(raw) if raw.isdigit() else 0, raw)

    return min(hits, key=key), len(hits)


def provenance(row) -> str:
    if row["floor_kind"] == "nutrition_authority":
        return "n/a (authority floor)"
    if row["floor_anchor_in_reviewed_registry"]:
        return "REVIEWED (in registry)"
    rec = row["floor_anchor_record"]
    live = ca.reviewed_entries()
    lit = ge._RECOVERED_COLLAGEN_PEPTIDES_MATCH if rec == "RECOVERED_COLLAGEN_PEPTIDES_V1" else None
    if lit:
        src = (lit.get("source_data") or "").split(":")[-1]
        ref = live.get(src)
        if ref and all(ref.get(f) == lit.get(f)
                       for f in ("effect_direction", "study_type", "evidence_level")):
            return f"RECOVERED -> verified against reviewed {src}"
        return f"RECOVERED -> claims {src}, NOT verified"
    return "UNREVIEWED"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration", type=Path,
                    default=HERE / "primary_mass_floor_calibration.json")
    ap.add_argument("--out", type=Path, default=HERE / "PRIMARY_MASS_FLOOR_STRATA_REVIEW.md")
    args = ap.parse_args()

    rows = json.loads(args.calibration.read_text())["products"]

    lines = [
        "# PRIMARY-MASS FLOOR — 13-STRATUM SANITY REVIEW",
        "",
        f"Policy under review: `{POLICY}`. Representative per stratum is the lowest",
        "dsld_id among its members, so the selection is reproducible and not curated.",
        "",
        "`floor` is the raw floor the anchor proposes; `final` is Evidence after the",
        "policy applies. A stratum with no member is printed EMPTY rather than filled",
        "with an invented example.",
        "",
    ]

    findings = []
    for key, question, predicate in STRATA:
        row, n = pick(rows, predicate)
        lines += [f"## `{key}`  (n={n})", "", f"*{question}*", ""]
        if row is None:
            lines += ["**EMPTY — no product in the corpus matches this stratum.**", ""]
            if key in ("null_direction", "negative_direction"):
                mult = ge._EFFECT_FLOOR_MULTIPLIER.get(key.split("_")[0], 0.0)
                lines += [
                    f"Structurally empty, not merely absent: `_EFFECT_FLOOR_MULTIPLIER"
                    f"[{key.split('_')[0]!r}] = {mult}`, and `_primary_mass_floor` skips any",
                    "anchor whose multiplier is <= 0. No policy can create this case.",
                    "",
                ]
            continue

        b = row["policies"]["baseline"]
        d = row["policies"][POLICY]
        z = row["policies"]["no_primary_mass_floor"]
        prov = provenance(row)
        lines += [
            f"| field | value |",
            f"|---|---|",
            f"| product | `{row['dsld_id']}` ({row['brand_dir']}) |",
            f"| module / archetype | {row['module']} / {row.get('archetype')} |",
            f"| mass-dominant active | `{row['floor_anchor_canonical']}` |",
            f"| anchor record | `{row['floor_anchor_record']}` — {row['floor_anchor_standard_name']} |",
            f"| provenance | **{prov}** |",
            f"| evidence direction | `{row['direction']}` |",
            f"| study type / level | {row['study_type']} / {row['evidence_level']} |",
            f"| raw pipeline Evidence (floor suppressed) | {row['raw_without_mass_floor']} |",
            f"| candidate floor | {row['raw_floor']} |",
            "",
            f"| policy | Evidence | total | tier |",
            f"|---|---|---|---|",
            f"| baseline | {b['evidence']} | {b['total']} | {b['tier']} |",
            f"| `{POLICY}` | {d['evidence']} | {d['total']} | {d['tier']} |",
            f"| no_primary_mass_floor | {z['evidence']} | {z['total']} | {z['tier']} |",
            "",
        ]
        if prov.startswith("RECOVERED") and "NOT verified" in prov:
            findings.append(f"{key}: anchor {row['floor_anchor_record']} is unverified")
        # The direction rule governs the PRIMARY-MASS floor only. A
        # nutrition_authority row is a different owner (NUTRITION_AUTHORITY_FLOOR)
        # and adequacy carries no efficacy direction, so asserting the direction
        # ceiling against it is a category error, not a violation.
        if (row["floor_kind"] == "primary_mass"
                and row["direction"] != "positive_strong"
                and d["evidence"] > ge.PRIMARY_FLOOR_MODERATE):
            findings.append(
                f"{key}: {row['direction']} reached Evidence {d['evidence']} above the "
                f"MODERATE base {ge.PRIMARY_FLOOR_MODERATE}")

    lines += ["## Findings", ""]
    lines += [f"- {f}" for f in findings] if findings else ["None."]
    lines.append("")
    args.out.write_text("\n".join(lines))
    print("\n".join(lines[:4]))
    print(f"wrote {args.out}")
    print(f"findings: {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
