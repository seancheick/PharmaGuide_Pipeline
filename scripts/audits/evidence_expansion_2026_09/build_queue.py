#!/usr/bin/env python3
"""Evidence curation priority queue for the non-probiotic lane (read-only over inventory.json).

Two rankings, because the lanes differ from the probiotic queue this adapts
(scripts/audits/probiotic_curation_queue_2026_09_13), where every product sat at
Evidence <= 8. Here the slots x (0.25 + share <= 8) base term lets well-evidenced
multivitamin nutrients outrank identities whose products are actually at zero.
  gap priority      = products at Evidence <= 8 x uncertainty          (new-evidence waves)
  exposure priority = slots x (0.25 + share <= 8) x uncertainty        (legacy-record backfill)
  uncertainty: not reviewed 2.0, legacy record without review state 1.5, reviewed 1.0

Columns the formula does NOT read are shown beside it so evidence gaps and identity
gaps stay distinguishable:
  * normalization blocker: share of the identity's rows with an unmapped form, or no dose;
  * candidate_discovery_volume: PubMed count of human RCT / SR / MA records for the name.
    Workload signal only. It is never written to a context, never read by synthesis,
    and says nothing about evidence strength.

    python3 scripts/audits/evidence_expansion_2026_09/build_queue.py [--pubmed-top N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

UNCERTAINTY = {"not_reviewed": 2.0, "legacy_review_state_not_established": 1.5,
               "reviewed_no_qualifying_evidence_in_documented_scope": 1.0}
DISCOVERY_FILTER = ('AND (randomized controlled trial[pt] OR meta-analysis[pt] OR systematic review[pt]) '
                    'AND humans[mh]')


def exposure_priority(identity: dict) -> float:
    share_low = identity["evidence_le8_products"] / identity["products"]
    return round(identity["slots"] * (0.25 + share_low) * UNCERTAINTY[identity["review_state"]], 1)


def gap_priority(identity: dict) -> float:
    return round(identity["evidence_le8_products"] * UNCERTAINTY[identity["review_state"]], 1)


def discovery_query(identity: dict) -> str:
    # "Vitamin B9 (Folate)" is two names, not one phrase.
    parts = [part.strip() for part in re.split(r"[()]", identity["top_name"]) if part.strip()]
    names = " OR ".join(f'"{part}"[tiab]' for part in parts)
    return f"({names}) {DISCOVERY_FILTER}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pubmed-top", type=int, default=0,
                        help="look up candidate_discovery_volume for the top N queue items")
    args = parser.parse_args()
    inventory = json.loads((OUT / "inventory.json").read_text())
    queue = [dict(identity, gap_priority=gap_priority(identity), exposure_priority=exposure_priority(identity))
             for identity in inventory["identities"]]
    queue.sort(key=lambda row: (-row["gap_priority"], -row["exposure_priority"], row["canonical_id"]))

    lookups = []
    if args.pubmed_top:
        import env_loader  # noqa: F401  (loads NCBI_API_KEY)
        from api_audit.pubmed_client import PubMedClient
        client = PubMedClient()
        for row in queue[:args.pubmed_top]:
            query = discovery_query(row)
            result = client.esearch(query, retmax=0)
            count = int(((result or {}).get("esearchresult") or {}).get("count") or 0)
            row["candidate_discovery_volume"] = count
            lookups.append({"canonical_id": row["canonical_id"], "query": query, "count": count})

    for rank, row in enumerate(queue, 1):
        row["gap_rank"] = rank
    for rank, row in enumerate(sorted(queue, key=lambda r: (-r["exposure_priority"], r["canonical_id"])), 1):
        row["exposure_rank"] = rank
    payload = {"_metadata": {"built": dt.date.today().isoformat(), "formula": __doc__.split("\n\n")[1],
                             "discovery_volume_lookups": lookups,
                             "discovery_volume_note": "workload signal only; not evidence strength"},
               "queue": queue}
    (OUT / "queue.json").write_text(json.dumps(payload, indent=1))

    header = ("| rank | identity | name | category | slots | products | brands | mean Ev | Ev=0 | Ev≤8 | review state "
              "| legacy records | dosed share | form-unmapped share | discovery vol | gap prio | exposure prio |")
    rule = "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|"

    def table(rows, rank_key):
        out = [header, rule]
        for row in rows:
            out.append(
                f"| {row[rank_key]} | `{row['canonical_id']}` | {row['top_name']} | {row['category']} | {row['slots']} | "
                f"{row['products']} | {row['brands']} | {row['evidence_mean']} | {row['evidence_zero_products']} | "
                f"{row['evidence_le8_products']} | {row['review_state']} | {', '.join(row['registry_entry_ids_key_overlap']) or '—'} | "
                f"{row['dosed_slot_share']} | {row['form_unmapped_slot_share']} | {row.get('candidate_discovery_volume', '—')} | "
                f"{row['gap_priority']} | {row['exposure_priority']} |")
        return out

    lines = ["# Evidence curation queue — non-probiotic lane", "",
             f"Built {payload['_metadata']['built']} from `inventory.json`. Discovery volume = PubMed human RCT/SR/MA "
             "count for the name: **workload only, never evidence strength**.", "",
             "```", __doc__.split("\n\n")[1], "```", "",
             "## Gap queue (new-evidence waves)", ""] + table(queue[:80], "gap_rank") + [
             "", "## Exposure queue (legacy-record backfill)", ""] + table(
                 sorted(queue, key=lambda r: r["exposure_rank"])[:40], "exposure_rank")
    (OUT / "QUEUE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(f"{r['gap_rank']:>3} {r['canonical_id']:<28} le8={r['evidence_le8_products']:<4} zero={r['evidence_zero_products']:<4} "
                    f"{r['review_state'][:12]:<12} vol={r.get('candidate_discovery_volume', '-')}" for r in queue[:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
