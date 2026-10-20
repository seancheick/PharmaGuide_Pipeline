#!/usr/bin/env python3
"""Apply the reviewed literature-record corrections (research.md) to
scripts/data/literature_evidence_records.json.

usage: $PG_PYTHON scripts/audits/literature_records_review_20261020/apply.py a|b [--dry-run]
       $PG_PYTHON .../apply.py expect-a|expect-ab   (keys for data_batch.py check --expect)

  a  spec_a.SPEC: records whose Evidence determination changes
  b  spec_b.SPEC: study-fact corrections whose determination does not change (apply after a)

Every patch is explicit in the spec; nothing is fetched or generated here. The script refuses
to run if a spec key or PMID is missing, and prints the resolver-level determination of every
patched record before and after, so batch b can prove it changed none.
"""
import argparse
import copy
import datetime
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

DATA = REPO / "scripts" / "data" / "literature_evidence_records.json"
D = "__DELETE__"
KEYWORDS = ("applicability unestablished", "prohibited", "blocked")


def _load_spec(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def determination(r):
    """The resolver branch this record reaches (evidence_resolver.py literature step)."""
    prov = r.get("verification_provenance") or {}
    if not (r.get("verification_result") == "authoritative_pubmed_verified" and prov.get("all_pmids_verified") is True
            and not prov.get("retractions_found")):
        return "verification_pending"
    eff = r.get("effect_direction")
    if eff in {"null", "negative", "reviewed_null_unfavorable", "no_qualifying_human_evidence"}:
        return "reviewed_null" if r.get("qualifying_human_studies") else "no_qualifying"
    if eff == "not_efficacy_relevant":
        return "not_efficacy_relevant"
    if eff in {"identity_material_unresolved", "identity_insufficient"}:
        return "identity_unresolved"
    app = str(r.get("applicability_decision") or "").lower()
    if eff == "applicability_unestablished" or any(k in app for k in KEYWORDS):
        return "applicability_unestablished"
    return "reviewed_clinical"


# Studies keep their own schema: rows with `design` use primary_endpoint/effect/notes.
_ALIASES = {"study_type": "design", "effect_direction": "effect", "outcome": "notes"}


def _set(row, key, value):
    if key not in row and key in _ALIASES and _ALIASES[key] in row:
        key = _ALIASES[key]
    if value == D:
        row.pop(key, None)
    else:
        row[key] = value


def _patch_study(rec, row, patch, replacements, now):
    patch = dict(patch)
    new_pmid = patch.pop("_replace_pmid", None)
    if new_pmid:
        rep = replacements[new_pmid]
        row["pmid"] = new_pmid
        row["title"] = rep["title"]
        row["verification_provenance"] = {
            "pmid_verified": True,
            "authoritative_live_title": rep["title"],
            "human_subjects_verified": True,
            "topic_match_verified": True,
            "retracted": False,
            "verified_source": f"https://pubmed.ncbi.nlm.nih.gov/{new_pmid}/",
            "verified_at": now,
            "abstract_evidence_quote": rep["quote"],
        }
    for key, value in patch.items():
        _set(row, key, value)


def apply(blob, spec_mod):
    records = blob["literature_evidence_records"]
    by_cid = {r["canonical_id"]: r for r in records}
    replacements = getattr(spec_mod, "REPLACEMENTS", {})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report = []
    for cid, patch in spec_mod.SPEC.items():
        rec = by_cid[cid]  # KeyError = spec names a record that does not exist
        before = determination(rec)
        studies = rec["qualifying_human_studies"]
        for skey, spatch in (patch.get("studies") or {}).items():
            pmid, occ = skey if isinstance(skey, tuple) else (skey, 0)
            hits = [i for i, s in enumerate(studies) if str(s.get("pmid")) == pmid]
            if len(hits) <= occ:
                raise SystemExit(f"{cid}: PMID {pmid} occurrence {occ} not found")
            idx = hits[occ]
            if spatch == "REMOVE":
                studies.pop(idx)
            else:
                _patch_study(rec, studies[idx], spatch, replacements, now)
        for key, value in (patch.get("record") or {}).items():
            if key == "_pending":
                rec["verification_result"] = "verification_failure_unresolved"
                rec.setdefault("verification_provenance", {})["all_pmids_verified"] = False
                continue
            _set(rec, key, value)
        report.append((cid, before, determination(rec)))
    meta = blob["_metadata"]
    meta["verified_studies_count"] = sum(len(r.get("qualifying_human_studies") or []) for r in records)
    meta["verified_records_count"] = len(records)
    return report


def expect_keys(batches):
    """data_batch keys (list positions) of the records a batch patches, for `data_batch.py check --expect`."""
    records = data_batch.load(DATA)["literature_evidence_records"]
    pos = {r["canonical_id"]: i for i, r in enumerate(records)}
    cids = [c for b in batches for c in _load_spec(f"spec_{b}").SPEC]
    return ",".join(f"literature_evidence_records[{pos[c]}]" for c in dict.fromkeys(cids))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", choices=["a", "b", "expect-a", "expect-b", "expect-ab"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.batch.startswith("expect-"):
        print(expect_keys(list(args.batch.split("-")[1])))
        return
    spec_mod = _load_spec(f"spec_{args.batch}")
    blob = data_batch.load(DATA)
    original = copy.deepcopy(blob)
    report = apply(blob, spec_mod)
    moved = [(c, b, a) for c, b, a in report if b != a]
    for c, b, a in report:
        print(f"{c}: {b} -> {a}" if b != a else f"{c}: {b} (unchanged)")
    print(f"{len(report)} records patched; {len(moved)} change determination")
    if args.batch == "b" and moved:
        raise SystemExit("batch b must not change a determination")
    if not args.dry_run and blob != original:
        data_batch.save(DATA, blob)


if __name__ == "__main__":
    main()

