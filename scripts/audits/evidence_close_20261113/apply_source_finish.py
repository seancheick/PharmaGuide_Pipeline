"""Apply the 13 no-credit source decisions and their free-text corrections.

Run from scripts/: ``$PG_PYTHON audits/evidence_close_20261113/apply_source_finish.py``.
Idempotence is refused on purpose: a context id that already exists aborts.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]

import data_batch  # noqa: E402
from source_finish_contexts import CONTEXTS  # noqa: E402

PATH = HERE.parents[1] / "data" / "backed_clinical_studies.json"

INULIN_OLD = "PMID 35833477 full Methods remains unread; no whole-ingredient completion or general Dose benchmark follows."
INULIN_NEW = ("PMID 35833477 full Methods remains unread; on November 13, 2026 it closed as a no-credit source "
              "decision (agent review of the abstract and recovered supplements), so no credit or general Dose "
              "benchmark follows from it.")
INULIN_LIMIT_OLD = "Independent source 35833477 remains unfinished; no whole-ingredient or product completion follows automatically."
INULIN_LIMIT_NEW = ("Independent source 35833477 closed separately as a no-credit decision on 2026-11-13; this trial "
                    "alone sets no whole-ingredient credit.")
BLACK_SEED_OLD = ("Black seed oil (Nigella sativa) has strong evidence from multiple large meta-analyses (16-30 RCTs) "
                  "with consistent glycemic and blood pressure endpoints. FBG and HbA1c reductions are well-replicated "
                  "across studies.")
BLACK_SEED_NEW = ("Human sources concern glycemic, lipid and blood-pressure outcomes across seed and oil "
                  "preparations. PMID 40210172 (16 RCTs in type 2 diabetes) reports lower fasting glucose, HbA1c, "
                  "total and LDL cholesterol with several null outcomes; PMID 37341696 reports small blood-pressure "
                  "reductions with very high heterogeneity; PMID 21675032 is a seed-capsule dose study in type 2 "
                  "diabetes without a stated placebo arm. On November 13, 2026 these three sources "
                  "closed as no-credit decisions from their PubMed abstracts (agent review, not clinician review); "
                  "no general benefit transfers to black seed oil.")


def replace_once(text, old, new, where):
    if text.count(old) != 1:
        raise SystemExit(f"{where}: expected exactly one match for the old text")
    return text.replace(old, new)


def main():
    blob = data_batch.load(PATH)
    rows = next(v for v in blob.values() if isinstance(v, list))
    by_id = {row["id"]: row for row in rows}
    for ctx in CONTEXTS:
        record = by_id[ctx["components"][0]]
        existing = {c.get("context_id") for c in record["study_contexts"]}
        if ctx["context_id"] in existing:
            raise SystemExit(f"{ctx['context_id']} already present")
        record["study_contexts"].append(ctx)
    inulin = by_id["INGR_INULIN"]
    inulin["notes"] = replace_once(inulin["notes"], INULIN_OLD, INULIN_NEW, "inulin notes")
    trial = next(c for c in inulin["study_contexts"] if c.get("context_id") == "ingr_inulin_27492975_scoped_source")
    trial["limitations"] = [INULIN_LIMIT_NEW if item == INULIN_LIMIT_OLD else item for item in trial["limitations"]]
    if INULIN_LIMIT_NEW not in trial["limitations"]:
        raise SystemExit("inulin trial limitation not found")
    black = by_id["INGR_BLACK_SEED_OIL"]
    black["notes"] = replace_once(black["notes"], BLACK_SEED_OLD, BLACK_SEED_NEW, "black seed notes")
    print(data_batch.save(PATH, blob))


if __name__ == "__main__":
    main()
