"""Manifest of the false total-vs-forms notes distributed in the v6 packets.

`build_review_doc.py` inferred "X is the TOTAL; do NOT add the entries after it"
from arithmetic coincidence -- whether the next 2-3 amounts happened to sum to
the current one -- with no identity evidence. Thirty such notes reached all three
reviewers. This reconstructs exactly which were false, so the affected products
can be handled explicitly instead of entering the calibration regression
unmarked.

The instruction is not cosmetic. Told that `Leucine 3000` is the total and
Isoleucine+Valine are its forms, a pharmacist scores a 6000 mg BCAA product as
3000 mg -- so `dose_0_20` is the pillar at direct risk, with `formulation_0_20`
and `evidence_0_20` exposed where the perceived dose changes the comparison.

Joins on product name + brand, both of which the packet carries in the clear.
Neither baseline key is opened; blinding covers engine scores, not identity.

Usage: python3 build_contamination_manifest.py [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import re
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FREEZE = ROOT / "reports" / "v4_reviewer_benchmark_2026_08_06_v6"
BLOBS = ROOT / "dist" / "detail_blobs"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "audits"))

from build_review_doc import rollup  # noqa: E402
from v4_reviewer_benchmark_freeze import _reviewer_packet_row  # noqa: E402

# Pillars a mis-stated total can move, worst first. A reviewer who believes the
# constituent amounts are already included scores a materially smaller dose.
AFFECTED_PILLARS = "dose_0_20;formulation_0_20;evidence_0_20"

# Branched-chain amino acids are the one family here that reviewers routinely
# aggregate into a single "total BCAA" figure, which is exactly what a false
# "do not add these" instruction would deflate. Nobody sums taurine into
# beta-alanine, so those notes have no conventional total to distort.
BCAA = {"leucine", "isoleucine", "valine"}

TO_MG = {"g": 1000.0, "gram(s)": 1000.0, "grams": 1000.0, "mg": 1.0, "mcg": 0.001}


def superseded_rule(act):
    """The rule as shipped in the v6 packets, reproduced to recover its output."""
    for i, a in enumerate(act):
        q = a.get("quantity")
        if not isinstance(q, (int, float)) or q <= 0:
            continue
        for w in (2, 3):
            nxt = act[i + 1:i + 1 + w]
            qs = [x.get("quantity") for x in nxt]
            if len(nxt) >= 2 and all(isinstance(v, (int, float)) for v in qs) \
                    and abs(sum(qs) - q) < 1e-6:
                return a, nxt
        else:
            continue
        break
    return None


def _amount(chunk):
    match = re.search(r"([\d.]+)\s*([A-Za-z()]*)$", chunk.strip())
    return (float(match.group(1)), match.group(2).lower()) if match else (None, "")


def parse_note(text):
    """'Leucine 750.0mg == Isoleucine 250.0mg + Valine 500.0mg' -> parts."""
    left, _, right = text.partition(" == ")
    parent = (left.rsplit(" ", 1)[0].strip(),) + _amount(left)
    kids = [(chunk.rsplit(" ", 1)[0].strip(),) + _amount(chunk)
            for chunk in right.split(" + ")]
    return parent, kids


def classify(status, sent_text):
    """What kind of wrong the sent note was, and whether it could move a dose.

    `wrong_parent` / `wrong_children` are deliberately absent: every retracted
    note turned out to have no parent/child relationship anywhere in the
    product, so no such case exists in this freeze. Adding empty buckets would
    imply a distinction the data does not support.
    """
    if status == "retained_unchanged":
        return "valid_total", "not_applicable"
    if status == "retained_changed":
        return "corrected_to_different_rollup", "dose_total_at_risk"

    parent, kids = parse_note(sent_text)
    units = {parent[2]} | {k[2] for k in kids}
    names = {parent[0].lower()} | {k[0].lower() for k in kids}

    if any(k[1] == 0 for k in kids):
        kind = "phantom_zero_row_rollup"
    elif len(units) > 1:
        kind = "mixed_unit_false_rollup"
    else:
        kind = "false_total_instruction"

    # Only a family the reviewer would conventionally aggregate can be deflated
    # by "do not add these". Everything else names ingredients a reviewer scores
    # one by one, so the instruction has no total to distort.
    risk = "dose_total_at_risk" if names <= BCAA else "inert_no_conventional_total"
    return kind, risk


def rationale_evidence(sent_text, answer, serving_info):
    """Did the reviewer's own free-text state the true sum, or the deflated one?

    Free text is not proof of the score, but where the reviewer wrote a total it
    is the most direct evidence available of whether the note was acted on.
    """
    if answer is None:
        return "not_returned"
    text = (answer.get("rationale") or "").lower()
    parent, kids = parse_note(sent_text)
    try:
        servings = float(serving_info.get("max_servings_per_day") or 1)
        parent_mg = parent[1] * TO_MG[parent[2]]
        kids_mg = sum(k[1] * TO_MG[k[2]] for k in kids)
    except (KeyError, TypeError):
        return "no_checkable_figure"

    def written(mg):
        forms = set()
        for value, suffix in ((mg, "mg"), (mg / 1000.0, "g")):
            rendered = f"{value:g}"
            # require a word boundary so "5 g" does not match "2.5 g betaine"
            forms |= {rf"\b{re.escape(rendered)}\s*{suffix}\b"}
        return any(re.search(f, text) for f in forms)

    true_sum = (parent_mg + kids_mg) * servings
    deflated = parent_mg * servings
    if written(true_sum):
        return "ignored_note_stated_true_sum"
    if written(deflated):
        return "possibly_followed_note"
    return "no_checkable_figure"


def describe(parent, kids):
    parts = " + ".join(f"{k.get('name')} {k.get('quantity')}{k.get('unit') or ''}"
                       for k in kids)
    return (f"{parent.get('name')} {parent.get('quantity')}"
            f"{parent.get('unit') or ''} == {parts}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()

    if not BLOBS.is_dir():
        print(f"detail blobs not built at {BLOBS}", file=sys.stderr)
        return 2

    by_product = {}
    for path in BLOBS.glob("*.json"):
        detail = json.loads(path.read_text())
        key = ((detail.get("product_name") or "").strip(),
               (detail.get("brand_name") or "").strip())
        by_product[key] = detail

    orders = {}
    for slotmap in sorted((HERE / "responses").glob("slotmap_*.json")):
        payload = json.loads(slotmap.read_text())
        orders[payload["reviewer_id"]] = payload["order"]

    returned, answers_by_id = set(), {}
    for answers in sorted((HERE / "responses").glob("answers_*.csv")):
        for row in csv.DictReader(answers.open()):
            returned.add((row["reviewer_id"], row["benchmark_id"]))
            answers_by_id[row["benchmark_id"]] = row

    rows, tally = [], {"retracted": 0, "retained_unchanged": 0, "retained_changed": 0}
    for packet_row in csv.DictReader((FREEZE / "reviewer_packet.csv").open()):
        act = json.loads(packet_row["active_ingredients_json"] or "[]")
        sent = superseded_rule(act)
        if not sent:
            continue
        detail = by_product.get((packet_row["product_name"].strip(),
                                 packet_row["brand_name"].strip()))
        if detail is None:
            raise SystemExit(f"unmatched product: {packet_row['product_name']}")

        current = rollup(json.loads(
            _reviewer_packet_row("PG-X", 1, detail)["active_ingredients_json"]))
        sent_text = describe(*sent)

        if current is None:
            status, truth = "retracted", "none — no parent/child nesting on the label"
        elif (current[0].get("name") == sent[0].get("name")
                and current[0].get("quantity") == sent[0].get("quantity")):
            status, truth = "retained_unchanged", describe(*current)
        else:
            status, truth = "retained_changed", describe(*current)
        tally[status] += 1

        contamination_class, bias = classify(status, sent_text)
        serving_info = json.loads(packet_row["serving_info_json"] or "{}")
        for reviewer, order in sorted(orders.items()):
            bid = packet_row["benchmark_id"]
            was_returned = (reviewer, bid) in returned
            rows.append({
                "reviewer": reviewer,
                "benchmark_id": bid,
                "reviewer_order": order.get(bid, ""),
                "product_name": packet_row["product_name"],
                "brand_name": packet_row["brand_name"],
                "note_status": status,
                "note_was_false": "yes" if status != "retained_unchanged" else "no",
                "contamination_class": contamination_class,
                "likely_direction_of_bias": bias,
                "sent_note_text": sent_text,
                "true_structural_relationship": truth,
                "likely_affected_pillars": (
                    AFFECTED_PILLARS if status != "retained_unchanged" else ""),
                "response_returned": "yes" if was_returned else "no",
                "reviewer_rationale_evidence": (
                    rationale_evidence(sent_text, answers_by_id.get(bid), serving_info)
                    if was_returned and status != "retained_unchanged" else ""),
            })

    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "CONTAMINATION_v6_rollup_notes.csv"
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    products = len(rows) // max(len(orders), 1)
    false_products = tally["retracted"] + tally["retained_changed"]
    exposed = sum(1 for r in rows
                  if r["note_was_false"] == "yes" and r["response_returned"] == "yes")
    print(f"{out}")
    print(f"  notes sent per reviewer : {products}")
    print(f"  retracted               : {tally['retracted']}")
    print(f"  retained unchanged      : {tally['retained_unchanged']}")
    print(f"  retained but changed    : {tally['retained_changed']}")
    print(f"  FALSE claims sent       : {false_products}"
          f"  (retracted + retained_changed)")
    print(f"  reviewers in manifest   : {', '.join(sorted(orders))}")
    print(f"  returned responses already exposed to a false note: {exposed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
