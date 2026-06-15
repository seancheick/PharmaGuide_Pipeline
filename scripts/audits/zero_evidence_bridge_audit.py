#!/usr/bin/env python3
"""Grouped zero-evidence bridge audit.

For every scored product whose V4 evidence pillar == 0, collect the active
ingredient canonicals, then classify each distinct canonical against the verified
evidence corpus (`backed_clinical_studies.json`) as:

  - matched            : key already matches a verified entry (should NOT be 0 — anomaly)
  - bridgeable         : no direct match, but a deterministic normalization
                         (L-/D-/DL-/acetyl- prefix strip, or verified standard_name
                         tokens ⊆ canonical tokens, e.g. branded EGb761 → ginkgo)
                         resolves to a verified entry → add a safe alias
  - no_entry           : no verified entry exists under any safe normalization
                         (correctly unsupported unless a real PMID is added)

Reuses the production matcher's `_canonical_text` / `_entry_identity_keys`, so the
key space matches the scorer exactly. Data source defaults to the base checkout
(the worktree has no built catalog); override with --blobs.

Output: scripts/audits/zero_evidence_bridge_audit.{md,json}
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from scoring_v4.modules.generic_evidence import (  # noqa: E402
    _canonical_text,
    _entry_identity_keys,
    _BACKED_CLINICAL_STUDIES_PATH,
)

_PREFIXES = ("l ", "d ", "dl ", "acetyl l ", "n acetyl l ", "l alpha ")


def _strip_stereo(key: str) -> str:
    k = key
    for p in _PREFIXES:
        if k.startswith(p):
            return k[len(p):].strip()
    return k


def _verified_index():
    raw = json.loads(_BACKED_CLINICAL_STUDIES_PATH.read_text())
    entries = raw.get("backed_clinical_studies") if isinstance(raw, dict) else raw
    keyset = set()
    std_tokens = {}  # canonical_text(standard_name) -> entry id
    for e in entries:
        for k in _entry_identity_keys(e):
            if k:
                keyset.add(k)
        std = _canonical_text(e.get("standard_name"))
        if std:
            std_tokens[std] = e.get("id") or e.get("standard_name")
    return keyset, std_tokens


def _classify(canon_key, keyset, std_tokens):
    if canon_key in keyset:
        return "matched", None, None
    stripped = _strip_stereo(canon_key)
    if stripped != canon_key and stripped in keyset:
        return "bridgeable", std_tokens.get(stripped, stripped), "stereoisomer/prefix"
    # branded/descriptive: a verified standard_name's tokens are a subset of ours
    ctoks = set(canon_key.split())
    for std, eid in std_tokens.items():
        stoks = set(std.split())
        if stoks and stoks < ctoks:  # strict subset → canonical is std + extra (brand/form)
            return "bridgeable", eid, "branded/descriptive"
    return "no_entry", None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blobs", default=str(ROOT.parent / "Downloads/dsld_clean/scripts/final_db_output/detail_blobs"))
    ap.add_argument("--out", default=str(ROOT / "scripts/audits/zero_evidence_bridge_audit"))
    args = ap.parse_args()

    blobs_dir = Path(args.blobs)
    if not blobs_dir.exists():
        # fall back to a sibling base checkout layout
        alt = Path("/Users/seancheick/Downloads/dsld_clean/scripts/final_db_output/detail_blobs")
        blobs_dir = alt if alt.exists() else blobs_dir
    if not blobs_dir.exists():
        print(f"ERROR: blobs dir not found: {blobs_dir}", file=sys.stderr)
        sys.exit(2)

    keyset, std_tokens = _verified_index()

    zero_products = 0
    canon_freq = Counter()                  # canonical_text(canonical) -> count among zero-evidence products
    canon_label = {}                        # canonical_text -> a human label
    for bf in blobs_dir.glob("*.json"):
        try:
            blob = json.loads(bf.read_text())
        except Exception:
            continue
        ev = (blob.get("quality_pillars_v4") or {}).get("evidence") or {}
        if ev.get("score") != 0:
            continue
        zero_products += 1
        seen = set()
        for ing in blob.get("ingredients", []) or []:
            canon = ing.get("canonical_id") or ing.get("standard_name") or ing.get("name")
            ck = _canonical_text(canon)
            if not ck or ck in seen:
                continue
            seen.add(ck)
            canon_freq[ck] += 1
            canon_label.setdefault(ck, str(ing.get("standard_name") or ing.get("name") or canon))

    buckets = defaultdict(list)
    for ck, freq in canon_freq.most_common():
        cls, matched, how = _classify(ck, keyset, std_tokens)
        buckets[cls].append((ck, canon_label.get(ck, ck), freq, matched, how))

    # ---- write outputs ----
    out_json = Path(args.out + ".json")
    out_md = Path(args.out + ".md")
    summary = {k: len(v) for k, v in buckets.items()}
    out_json.write_text(json.dumps(
        {"zero_evidence_products": zero_products, "summary": summary,
         "buckets": {k: [{"canonical": c, "label": l, "products": f, "matched_entry": m, "how": h}
                         for (c, l, f, m, h) in v] for k, v in buckets.items()}},
        indent=2))

    lines = [f"# Zero-evidence bridge audit\n",
             f"Zero-evidence scored products: **{zero_products}**",
             f"Distinct zero-evidence canonicals: **{sum(len(v) for v in buckets.values())}**",
             f"Classification: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(buckets.items())) + "\n"]
    bridge = buckets.get("bridgeable", [])
    lines.append(f"## BRIDGEABLE ({len(bridge)}) — add safe aliases, ranked by products unlocked\n")
    lines.append("| canonical (key) | label | products | → verified entry | how |")
    lines.append("|---|---|---|---|---|")
    for c, l, f, m, h in sorted(bridge, key=lambda x: -x[2]):
        lines.append(f"| {c} | {l} | {f} | {m} | {h} |")
    anomaly = buckets.get("matched", [])
    if anomaly:
        lines.append(f"\n## ANOMALY: matched but scored 0 ({len(anomaly)}) — investigate scorer\n")
        for c, l, f, m, h in sorted(anomaly, key=lambda x: -x[2])[:30]:
            lines.append(f"- {c} ({l}) — {f} products")
    lines.append(f"\n## no_entry: {len(buckets.get('no_entry', []))} canonicals (correctly 0 unless a real PMID is added)")
    out_md.write_text("\n".join(lines) + "\n")

    print("\n".join(lines[:6]))
    print(f"\nBRIDGEABLE (top 25):")
    for c, l, f, m, h in sorted(bridge, key=lambda x: -x[2])[:25]:
        print(f"  {f:4d}  {c:32s} -> {m}  [{h}]")
    print(f"\nWrote {out_md}\nWrote {out_json}")


if __name__ == "__main__":
    main()
