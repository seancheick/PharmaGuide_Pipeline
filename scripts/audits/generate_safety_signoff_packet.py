#!/usr/bin/env python3
"""Generate the itemized US safety-policy sign-off packet.

Two rules on this branch relax a consumer-facing verdict. Both are held at
their previous status by ``pending_us_policy_signoff`` until an operator
approves them. This emits the evidence an operator needs to make that call,
per product, derived from the artifacts rather than written by hand.

Usage:
    python3 scripts/audits/generate_safety_signoff_packet.py \
        --held-db scripts/dist/pharmaguide_core.db \
        --proposed-db /path/to/candidate/dist/pharmaguide_core.db \
        --out docs/release_candidates/safety_signoff_packet_2026_08_22.md
"""
from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

RULES = {
    "RISK_RED_YEAST_RICE": {
        "title": "Generic red yeast rice",
        "needles": ("yeast rice", "monascus", "red koji"),
        "held": "banned",
        "proposed": "high_risk",
        "basis": (
            "No US prohibition applies to red yeast rice as such. The FDA "
            "action addresses products with enhanced or added lovastatin; "
            "NCCIH records monacolin K content ranging from none to "
            "substantial and usually undeclared."
        ),
        "previous_mechanism": (
            "The shipped block did NOT come from this rule. A stale contaminant "
            "snapshot matched generic 'red yeast rice' to BANNED_RED_YEAST_RICE "
            "(match_type=alias, matched_variant='red yeast rice') even though "
            "that rule sets requires_explicit_form_evidence and lists only "
            "monacolin K / lovastatin variants. Verified on blob 206443 in the "
            "2026-08-19 build. On the evidence this is a defect fix, not a "
            "policy relaxation."
        ),
        "source": "https://www.nccih.nih.gov/health/red-yeast-rice",
        "effect": (
            "BLOCKED (hard block, product suppressed from scoring) -> CAUTION "
            "(scored, high-risk review surfaced to the consumer)."
        ),
        "residual_risk": (
            "A product whose monacolin K happens to be high is treated as a "
            "review rather than a block. Explicit monacolin K / lovastatin "
            "declarations still hard-block via BANNED_RED_YEAST_RICE."
        ),
    },
    "ADD_SODIUM_TETRABORATE": {
        "title": "Sodium tetraborate as a declared boron source",
        "needles": ("tetraborate", "borax"),
        "held": "banned",
        "proposed": "watchlist",
        "basis": (
            "NIH ODS lists sodium borate and sodium tetraborate among the "
            "boron forms used in dietary supplements, and notes Supplement "
            "Facts panels declare elemental boron rather than compound mass. "
            "No US supplement prohibition was established for this form."
        ),
        "previous_mechanism": (
            "The shipped block came from an EU food-additive ban driving a US "
            "market verdict: safety_jurisdiction_projection defaulted "
            "us_applicable to True for any rule with no declared jurisdiction. "
            "Two questions are tangled and both need an answer -- whether an EU "
            "food-additive ban should drive a US supplement verdict at all, and "
            "whether borax as a declared boron source salt is the same thing as "
            "borax as a standalone additive."
        ),
        "source": "https://ods.od.nih.gov/factsheets/Boron-HealthProfessional/",
        "effect": (
            "BLOCKED (hard block) -> SAFE or CAUTION, depending on the rest of "
            "the product's safety profile."
        ),
        "residual_risk": (
            "Borax as a standalone additive is a different question from borax "
            "as the declared source salt of a nutritionally-relevant boron "
            "dose. The retired rule covered both; this releases both."
        ),
    },
}


def _verdicts(db_path: Path) -> dict[str, tuple]:
    con = sqlite3.connect(str(db_path))
    try:
        return {
            str(r[0]): (r[1], r[2], r[3])
            for r in con.execute(
                "select dsld_id, verdict, blocking_reason, product_name "
                "from products_core"
            )
        }
    finally:
        con.close()


def _matches(product: dict, needles: tuple) -> list[tuple[str, str, str]]:
    """Return (role, row name, matched text) for each declaring row."""
    out = []
    for key, role in (("activeIngredients", "active"),
                      ("inactiveIngredients", "inactive")):
        for ing in product.get(key) or []:
            if not isinstance(ing, dict):
                continue
            texts = [ing.get("name"), ing.get("standardName"),
                     ing.get("raw_source_text")]
            for form in ing.get("forms") or []:
                if isinstance(form, dict):
                    texts += [form.get("name"), form.get("prefix")]
                elif form:
                    texts.append(form)
            for text in texts:
                value = str(text or "")
                if any(n in value.lower() for n in needles):
                    out.append((role, str(ing.get("name") or ""), value))
                    break
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--held-db", required=True, type=Path)
    ap.add_argument("--proposed-db", required=True, type=Path)
    ap.add_argument("--products-dir", default=str(REPO / "scripts" / "products"))
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    held = _verdicts(args.held_db)
    proposed = _verdicts(args.proposed_db)

    corpus: dict[str, dict] = {}
    pattern = f"{args.products_dir}/output_*_enriched/enriched/*.json"
    for path in sorted(glob.glob(pattern)):
        if path.endswith(".stage_manifest.json"):
            continue
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload if isinstance(payload, list) else (
            payload.get("products") or payload.get("items")
            or payload.get("data") or [payload]
        )
        for product in rows:
            if isinstance(product, dict):
                pid = str(product.get("dsld_id") or product.get("dsldId") or "")
                if pid:
                    corpus[pid] = product

    lines = [
        "# US safety-policy sign-off packet — 2026-08-22",
        "",
        "Status: **awaiting operator clinical-policy sign-off**",
        "",
        "Two rules relax a consumer-facing verdict. Both are held at their",
        "previous status by `pending_us_policy_signoff` in",
        "`scripts/data/banned_recalled_ingredients.json`, so the shipped",
        "treatment is unchanged until each is approved. Approving one is a",
        "single field flip: set `approved: true` and record `approved_by` /",
        "`approved_at`.",
        "",
        "Generated by `scripts/audits/generate_safety_signoff_packet.py` from the",
        "held and proposed catalogs — not written by hand.",
        "",
    ]

    grand_total = 0
    for rule_id, spec in RULES.items():
        affected = []
        for pid, product in corpus.items():
            hits = _matches(product, spec["needles"])
            if not hits:
                continue
            if pid not in held or pid not in proposed:
                continue
            if held[pid][0] == proposed[pid][0]:
                continue
            affected.append((pid, product, hits))
        affected.sort(key=lambda item: item[0])
        grand_total += len(affected)

        lines += [
            f"## {spec['title']} (`{rule_id}`)",
            "",
            f"- **Held status:** `{spec['held']}` (what ships today)",
            f"- **Proposed status:** `{spec['proposed']}`",
            f"- **Products affected:** {len(affected)}",
            f"- **US jurisdictional basis:** {spec['basis']}",
            f"- **What actually produced the previous verdict:** "
            f"{spec['previous_mechanism']}",
            f"- **Authoritative source:** {spec['source']}",
            f"- **Consumer-facing effect:** {spec['effect']}",
            f"- **Residual risk if approved:** {spec['residual_risk']}",
            "",
            "| DSLD | Product | Held | Proposed | Role | Declaring row | Matched text |",
            "|---|---|---|---|---|---|---|",
        ]
        for pid, product, hits in affected:
            name = str(held[pid][2] or product.get("product_name") or "")[:44]
            role, row_name, matched = hits[0]
            lines.append(
                f"| `{pid}` | {name} | {held[pid][0]} | {proposed[pid][0]} | "
                f"{role} | {row_name[:28]} | {matched[:40]} |"
            )
        lines += ["", ""]

    lines += [
        "## Decision",
        "",
        f"Total products awaiting sign-off: **{grand_total}**.",
        "",
        "- [ ] Approve `RISK_RED_YEAST_RICE` banned → high_risk",
        "- [ ] Approve `ADD_SODIUM_TETRABORATE` banned → watchlist",
        "",
        "Partially hydrogenated oils are **not** on this list. `33212` and",
        "`33230` were a defect, are blocked again, and are not a policy choice:",
        "FDA removed PHOs from GRAS and the compliance period has closed.",
        "",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out} ({grand_total} products)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
