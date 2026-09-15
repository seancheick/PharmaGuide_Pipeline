#!/usr/bin/env python3
"""Apply the 2026-09-14 evidence-bound strain identity batch, one operation at a time.

Usage: apply_identity_batch.py [--apply] [--only KEY ...]

Dry run by default. Every operation is applied to an in-memory registry and
must pass its guards before the next one runs:

* add_identity  - id is new, no alias key is owned by another identity, the
                  designation is not already registered, and every expected
                  label resolves through the production matcher to the new id
                  and to no other identity.
* add_alias     - target exists, the alias key is unowned, and expected labels
                  resolve to the target only.
* merge_duplicate - the stub has no study contexts and no context names it as
                  a component; its aliases move to the named identity, the stub
                  is removed, and expected labels resolve to the target only.
* correct_deposit - the old alias and deposit must be exactly what the source
                  said; skipped while pending_authoritative_check is true.

Nothing here touches dr_pham_signoff, study_contexts, evidence or dose tiers.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from studied_formulas import clinical_strain_identity_matches  # noqa: E402

REG = ROOT / "scripts/data/clinically_relevant_strains.json"
SPEC = Path(__file__).with_name("identity_batch_2026_09_14.json")
TODAY = "2026-09-14"
METHOD = "PubMed abstract and Europe PMC open-access full text read for the designation, species and deposit"
STATUSES = {"designation_verified", "designation_found_species_unconfirmed"}


def _key(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _names(entry) -> list[str]:
    return [entry["standard_name"], *entry.get("aliases", [])]


def _owners(entries) -> dict[str, set[str]]:
    owned: dict[str, set[str]] = {}
    for entry in entries:
        for name in _names(entry):
            owned.setdefault(_key(name), set()).add(entry["id"])
    return owned


def _require_evidence(op) -> None:
    evidence = op.get("evidence") or []
    if not evidence or not all(e.get("pmid") and e.get("quote") and e.get("location") for e in evidence):
        raise SystemExit(f"REFUSED {op['key']}: every operation needs pmid + location + quote evidence")


def _resolves_only_to(entries, label: str, target: str) -> list[str]:
    return sorted(e["id"] for e in entries if clinical_strain_identity_matches(label, e))


def _prove_labels(entries, op, target: str, labels) -> None:
    for label in labels:
        hits = _resolves_only_to(entries, label, target)
        if hits != [target]:
            raise SystemExit(f"REFUSED {op['key']}: label {label!r} resolves to {hits}, expected [{target}]")


def _add_identity(entries, op) -> None:
    ident = op["id"]
    if any(e["id"] == ident for e in entries):
        raise SystemExit(f"REFUSED {op['key']}: {ident} already present")
    if op["verification"] not in STATUSES:
        raise SystemExit(f"REFUSED {op['key']}: verification {op['verification']!r} not allowed in this batch")
    if not op.get("pmids"):
        raise SystemExit(f"REFUSED {op['key']}: no source PMIDs")
    owned = _owners(entries)
    clashes = {n: sorted(owned[_key(n)]) for n in [op["standard_name"], *op["aliases"]] if _key(n) in owned}
    if clashes:
        raise SystemExit(f"REFUSED {op['key']}: alias already owned {clashes}")
    entry = {
        "id": ident,
        "standard_name": op["standard_name"],
        "aliases": list(op["aliases"]),
        "evidence_level": "unreviewed",
        "key_benefits": [],
        "notable_studies": "Strain designation recognized on product labels and named with its species in the cited literature; no clinical evidence review has been performed for this identity.",
        "identity_verification": {
            "status": op["verification"],
            "source_pmids": list(op["pmids"]),
            "deposit_ids": list(op.get("deposits") or []),
            "supplier": op.get("supplier"),
            "verified_on": TODAY,
            "method": METHOD,
            "note": op.get("note"),
        },
        "cfu_thresholds": {
            "indication_primary": None,
            "tiers_cfu_per_day": None,
            "dr_pham_signoff": False,
            "evidence": None,
        },
        "study_contexts": [],
    }
    entries.append(entry)
    _prove_labels(entries, op, ident, op["expect_labels"])


def _add_alias(entries, op) -> None:
    target = next((e for e in entries if e["id"] == op["target"]), None)
    if target is None:
        raise SystemExit(f"REFUSED {op['key']}: target {op['target']} missing")
    owned = _owners(entries)
    for alias in op["aliases"]:
        holders = owned.get(_key(alias), set())
        if holders:
            raise SystemExit(f"REFUSED {op['key']}: alias {alias!r} already owned by {sorted(holders)}")
        target["aliases"].append(alias)
    _prove_labels(entries, op, target["id"], op["expect_labels"])


def _merge_duplicate(entries, op) -> None:
    source = next((e for e in entries if e["id"] == op["source"]), None)
    target = next((e for e in entries if e["id"] == op["target"]), None)
    if source is None or target is None:
        raise SystemExit(f"REFUSED {op['key']}: source or target missing")
    if source.get("study_contexts"):
        raise SystemExit(f"REFUSED {op['key']}: {source['id']} has study contexts")
    referencing = [c["context_id"] for e in entries for c in e.get("study_contexts", []) if source["id"] in c.get("components", [])]
    if referencing:
        raise SystemExit(f"REFUSED {op['key']}: contexts reference {source['id']}: {referencing}")
    if (source.get("cfu_thresholds") or {}).get("dr_pham_signoff") is True:
        raise SystemExit(f"REFUSED {op['key']}: source carries a sign-off")
    target_keys = {_key(n) for n in _names(target)}
    others = _owners([e for e in entries if e["id"] not in (source["id"], target["id"])])
    moved = []
    for alias in _names(source):
        k = _key(alias)
        if k in others:
            raise SystemExit(f"REFUSED {op['key']}: alias {alias!r} also owned by {sorted(others[k])}")
        if k not in target_keys:
            target["aliases"].append(alias)
            target_keys.add(k)
            moved.append(alias)
    entries.remove(source)
    block = target.get("identity_verification")
    if isinstance(block, dict):
        deposit = op.get("deposit")
        if deposit and deposit not in block.setdefault("deposit_ids", []):
            block["deposit_ids"].append(deposit)
        for e in op["evidence"]:
            if e["pmid"] not in block.setdefault("source_pmids", []):
                block["source_pmids"].append(e["pmid"])
        if op.get("upgrade_target_status"):
            block["status"] = op["upgrade_target_status"]
            block["verified_on"] = TODAY
            block["method"] = METHOD
        note = f"{TODAY}: {deposit} crosswalk; duplicate stub {source['id']} merged."
        block["note"] = f"{block['note']} {note}".strip() if block.get("note") else note
    op["_moved_aliases"] = moved
    _prove_labels(entries, op, target["id"], op["expect_labels"])


def _correct_deposit(entries, op) -> None:
    for fix in op["corrections"]:
        target = next((e for e in entries if e["id"] == fix["target"]), None)
        if target is None:
            raise SystemExit(f"REFUSED {op['key']}: target {fix['target']} missing")
        old, new = fix["replace_alias"]
        if old not in target["aliases"]:
            raise SystemExit(f"REFUSED {op['key']}: {fix['target']} lacks alias {old!r}")
        block = target.get("identity_verification") or {}
        if block.get("deposit_ids") != fix["deposit_ids"][0]:
            raise SystemExit(f"REFUSED {op['key']}: {fix['target']} deposit_ids {block.get('deposit_ids')} != {fix['deposit_ids'][0]}")
        target["aliases"][target["aliases"].index(old)] = new
        block["deposit_ids"] = list(fix["deposit_ids"][1])
    owned = _owners(entries)
    for fix in op["corrections"]:
        target = next(e for e in entries if e["id"] == fix["target"])
        for alias in fix.get("add_aliases", []):
            if _key(alias) in owned:
                raise SystemExit(f"REFUSED {op['key']}: alias {alias!r} already owned by {sorted(owned[_key(alias)])}")
            target["aliases"].append(alias)
        block = target["identity_verification"]
        for e in op["evidence"]:
            if e["pmid"] not in block["source_pmids"]:
                block["source_pmids"].append(e["pmid"])
        note = f"{TODAY}: deposit corrected to {block['deposit_ids'][0]} ({op['note']})"
        block["note"] = f"{block['note']} {note}".strip() if block.get("note") else note
    for fix in op["corrections"]:
        _prove_labels(entries, op, fix["target"], fix["expect_labels"])


HANDLERS = {"add_identity": _add_identity, "add_alias": _add_alias, "merge_duplicate": _merge_duplicate, "correct_deposit": _correct_deposit}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    raw = REG.read_text(encoding="utf-8")
    registry = json.loads(raw)
    if json.dumps(registry, indent=2, ensure_ascii=False) + "\n" != raw:
        raise SystemExit("REFUSED: registry is not byte-stable through json.dumps(indent=2, ensure_ascii=False)")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    entries = registry["clinically_relevant_strains"]
    before_ids = {e["id"] for e in entries}
    before_shared = {k for k, v in _owners(entries).items() if len(v) > 1}
    applied, skipped = [], []
    for op in spec["operations"]:
        if args.only and op["key"] not in args.only:
            continue
        if op.get("pending_authoritative_check"):
            skipped.append(op["key"])
            print(f"SKIP  {op['key']}: pending authoritative check")
            continue
        _require_evidence(op)
        snapshot = copy.deepcopy(entries)
        HANDLERS[op["op"]](entries, op)
        applied.append(op)
        extra = f" moved={op['_moved_aliases']}" if "_moved_aliases" in op else ""
        print(f"OK    {op['key']} ({op['op']}){extra}")
        del snapshot
    after_shared = {k for k, v in _owners(entries).items() if len(v) > 1}
    if after_shared - before_shared:
        raise SystemExit(f"REFUSED: new alias keys shared by two identities: {sorted(after_shared - before_shared)}")
    if not all(e.get("cfu_thresholds", {}).get("dr_pham_signoff") in (True, False) for e in entries):
        raise SystemExit("REFUSED: sign-off flag malformed")
    meta = registry["_metadata"]
    meta["total_entries"] = len(entries)
    meta["last_updated"] = TODAY
    added = sorted({e["id"] for e in entries} - before_ids)
    removed = sorted(before_ids - {e["id"] for e in entries})
    meta["identity_batch_note_2026_09_14"] = (
        f"Evidence-bound identity batch (scripts/audits/probiotic_registry_expansion_2026_09_14): "
        f"{len(added)} identities added, {len(removed)} duplicate SD-deposit stubs merged into their named strains, "
        f"{sum(1 for o in applied if o['op'] == 'add_alias')} alias sets added"
        f"{', Lab4 NCIMB deposits corrected' if any(o['op'] == 'correct_deposit' for o in applied) else ''}. "
        "Every change cites PubMed/Europe PMC evidence; no sign-off, context, evidence or dose tier changed."
    )
    print(f"\nentries {len(before_ids)} -> {len(entries)} | added {len(added)} | merged away {len(removed)} | skipped {skipped}")
    if args.apply:
        REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("WRITTEN", REG)
    else:
        print("dry run; registry unchanged")


if __name__ == "__main__":
    main()
