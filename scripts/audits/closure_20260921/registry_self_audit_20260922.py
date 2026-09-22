#!/usr/bin/env python3
"""Correct what the 2026-09-22 registry self-audit found in the DATA.

``pham_registry_reconcile_20260922.py`` audits the registry against Dr Pham's
packet. Every packet decision already held; the audit found stale copies of
facts other fields own:

* ``evidence_level`` disagreed with the effective evidence strength on 14
  identities (it is the registry-level copy of that strength);
* six identities listed the same alias twice in different case;
* five packet identities named a benefit their own reviewed evidence does not
  show in ``indication_primary``, the text the app prints beside the strain.
  Bi-07's and HEAL9's came from combination trials, BB-12's from neither of its
  reviewed questions, 35624's and Nissle's stated benefits Dr Pham reviewed as
  null or as active-comparator evidence;
* Bi-07's and BB-12's reviewed single-strain records had no ``study_design``
  although the verified abstracts are two crossover RCTs and an RCT.

Each entry is edited explicitly and asserted against its current value first.

    python3 scripts/audits/closure_20260921/registry_self_audit_20260922.py          # dry run
    python3 scripts/audits/closure_20260921/registry_self_audit_20260922.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

REG = ROOT / "scripts/data/clinically_relevant_strains.json"
BASIS_REL = "scripts/audits/closure_20260921/REGISTRY_SELF_AUDIT_20260922.json"

# id -> (current evidence_level, the level of its effective evidence strength)
EVIDENCE_LEVEL = {
    "STRAIN_REUTERI_PRODENTIS": ("high", "moderate"),
    "STRAIN_COAGULANS_MTCC5856": ("high", "moderate"),
    "STRAIN_COAGULANS_IS2": ("high", "moderate"),
    "STRAIN_ACIDOPHILUS_NCFM": ("high", "low"),
    "STRAIN_LACTIS_BB12": ("low", "high"),
    "STRAIN_LONGUM_BB536": ("high", "moderate"),
    "STRAIN_SUBTILIS_DE111": ("moderate", "low"),
    "STRAIN_CASEI_431": ("high", "low"),
    "STRAIN_LACTIS_BL04": ("high", "moderate"),
    "STRAIN_GASSERI_SBT2055": ("high", "moderate"),
    "STRAIN_GASSERI_BNR17": ("high", "moderate"),
    "STRAIN_ACIDOPHILUS_DDS1": ("high", "low"),
    "STRAIN_PARACASEI_LPC37": ("high", "moderate"),
    "STRAIN_LACTIS_UABla12": ("moderate", "low"),
}

# id -> (index, the case-variant alias to drop; the first spelling stays)
ALIAS_DUPLICATES = {
    "STRAIN_K12": (6, "Blis K12 Streptococcus salivarius"),
    "STRAIN_PLANTARUM_LP01": (7, "Lp-01"),
    "STRAIN_PLANTARUM_LP115": (4, "L. plantarum LP-115"),
    "STRAIN_RHAMNOSUS_LR32": (4, "L. rhamnosus LR-32"),
    "STRAIN_INFANTIS_BI26": (4, "Bifidobacterium infantis BI-26"),
    "STRAIN_PLANTARUM_UALP05": (1, "L. plantarum UALp-05"),
}

INDICATIONS = {
    "STRAIN_LACTIS_BI07": (
        "immune support and respiratory health",
        "lactose digestion in acute lactose challenges (breath-hydrogen surrogate improved; GI symptoms not improved)"),
    "STRAIN_LACTIS_BB12": (
        "immune support and gut health",
        "infant colic in breastfed infants; adult stool-frequency primary endpoint not met"),
    "STRAIN_PLANTARUM_HEAL9": (
        "immune support and cold prevention",
        "cognitive test performance in moderately stressed adults (one exploratory trial; perceived stress and "
        "cortisol not improved)"),
    "STRAIN_INFANTIS_35624": (
        "irritable bowel syndrome symptom relief",
        "irritable bowel syndrome symptoms (pooled single-strain trials did not improve pain, bloating or bowel habit)"),
    "STRAIN_NISSLE_1917": (
        "ulcerative colitis remission maintenance",
        "ulcerative colitis remission maintenance (equivalent to mesalazine in its main trial; no placebo comparison)"),
}

STUDY_DESIGN = {
    ("STRAIN_LACTIS_BI07", "bi07_lactose_challenges_36149331"): "crossover_rct",
    ("STRAIN_LACTIS_BB12", "bb12_low_stool_frequency_26382580"): "rct",
}


def apply(registry: dict) -> list[dict]:
    from clinical_evidence_schema import validate_frozen_context
    from studied_formulas import clinical_strain_identity_matches

    by_id = {e["id"]: e for e in registry["clinically_relevant_strains"]}
    changes = []
    for sid, (old, new) in EVIDENCE_LEVEL.items():
        assert by_id[sid]["evidence_level"] == old, (sid, by_id[sid]["evidence_level"])
        by_id[sid]["evidence_level"] = new
        changes.append({"id": sid, "field": "evidence_level", "old": old, "new": new})
    for sid, (index, alias) in ALIAS_DUPLICATES.items():
        aliases = by_id[sid]["aliases"]
        assert aliases[index] == alias, (sid, aliases[index])
        kept = next(a for a in aliases if a != alias and a.lower() == alias.lower())
        del aliases[index]
        # Matching is case-insensitive, so the dropped spelling still resolves.
        assert clinical_strain_identity_matches(alias, by_id[sid]), (sid, alias)
        changes.append({"id": sid, "field": "aliases", "old": alias, "new": None, "kept": kept})
    for sid, (old, new) in INDICATIONS.items():
        thresholds = by_id[sid]["cfu_thresholds"]
        assert thresholds["indication_primary"] == old, (sid, thresholds["indication_primary"])
        thresholds["indication_primary"] = new
        changes.append({"id": sid, "field": "cfu_thresholds.indication_primary", "old": old, "new": new})
    known = set(by_id)
    for (sid, cid), design in STUDY_DESIGN.items():
        context = next(c for c in by_id[sid]["study_contexts"] if c["context_id"] == cid)
        assert "study_design" not in context, (cid, context.get("study_design"))
        context["study_design"] = design
        assert validate_frozen_context(context, known_component_ids=known) == [], cid
        changes.append({"id": sid, "field": f"study_contexts[{cid}].study_design", "old": None, "new": design})
    registry["_metadata"]["registry_self_audit_note_2026_09_22"] = (
        "Registry self-audit against Dr Pham's 2026-09-22 packet: every packet decision held. Corrected stale copies "
        "of owned facts: evidence_level now equals the effective evidence strength on 14 identities; 6 case-duplicate "
        "aliases dropped; indication_primary of Bi-07, BB-12, HEAL9, 35624 and Nissle 1917 bound to their own "
        "reviewed evidence; study_design recorded on the Bi-07 and BB-12 records from their verified abstracts. "
        f"Basis: {BASIS_REL}.")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw = REG.read_text(encoding="utf-8")
    registry = json.loads(raw)
    assert json.dumps(registry, indent=2, ensure_ascii=False) + "\n" == raw, "registry not in canonical form"
    assert "registry_self_audit_note_2026_09_22" not in registry["_metadata"], "already applied"
    before = deepcopy(registry)
    changes = apply(registry)
    old = {e["id"]: e for e in before["clinically_relevant_strains"]}
    changed = [e["id"] for e in registry["clinically_relevant_strains"] if old[e["id"]] != e]
    print(f"{len(changes)} changes in {len(changed)} identities:", ", ".join(changed))
    if args.apply:
        REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", REG.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
