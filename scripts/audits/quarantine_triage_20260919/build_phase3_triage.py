#!/usr/bin/env python3
"""Build the Phase-3 clinical triage table (2026-09-19 remediation).

Consumes the frozen baseline (baseline_products.json) plus the CURRENT
canonical registry, and classifies every quarantined product into:

  heals_mechanical   — conflict names that now resolve through the canonical
                       owner (Nickel/Tin via the 2026-09-19 IQM additions,
                       7-KETO-DHEA / Calcium already present)
  intentional_ns     — already dispositioned intentional_non_scoreable
  safety_policy_hold — quarantine_reason == safety_policy_review_required
                        (designed review state)
  clinical_triage    — everything else: needs a canonical-home / disposition
                       decision, presented here with rationale

Output: reports/quarantine_triage_2026_09_19/PHASE3_TRIAGE.md (the sign-off
artifact). Read-only; no data is changed by this script.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

from identity_integrity import build_canonical_identity_registry  # noqa: E402

TRIAGE = REPO / "reports" / "quarantine_triage_2026_09_19"
OUT = TRIAGE / "PHASE3_TRIAGE.md"

# Canonical facts collected during the 2026-09-19 investigation. Each entry:
# unresolved label name -> (owner proposal, rationale, risk if cleared naively)
CANONICAL_NOTES = {
    "Bitter Orange Citrus Bioflavonoids": (
        "alias under IQM citrus_bioflavonoids",
        "Label names bioflavonoids FROM bitter orange — the material identity is "
        "citrus bioflavonoids; RISK_BITTER_ORANGE stays a CAUTION safety signal "
        "(synephrine risk note retained). citrus bioflavonoids ≠ synephrine "
        "extract: no evidence transfer.",
        "aliasing to synephrine or dropping the risk note",
    ),
    "Bitter Orange Citrus Bioflavonoid": (
        "alias under IQM citrus_bioflavonoids",
        "Singular variant of the same material identity.",
        "aliasing to synephrine or dropping the risk note",
    ),
    "EDTA Disodium": (
        "other_ingredients excipient identity + product disposition",
        "Six of the rows are standalone 500 mg EDTA products (chelation use) — "
        "the substance IS the product. Disposition (intentional non-scoreable vs "
        "scored excipient identity) is a clinical call.",
        "scoring a chelation-therapy product as a routine supplement",
    ),
    "Calcium Disodium EDTA": (
        "other_ingredients excipient identity + product disposition",
        "Same standalone-product situation as EDTA Disodium.",
        "scoring a chelation-therapy product as a routine supplement",
    ),
    "Mannitol": (
        "other_ingredients excipient identity + product disposition",
        "Standalone 3 g mannitol products (osmotic/diagnostic use) plus excipient "
        "contexts; disposition is a clinical call.",
        "scoring an osmotic-agent product as a routine supplement",
    ),
    "EpiCor dried Yeast Fermentate Complex": (
        "resolve through existing dried-yeast-fermentate identity model",
        "The canonical fermentate identity machinery exists "
        "(test_dried_yeast_fermentate_identity.py). Check whether EpiCor is "
        "representable as generic identity + branded-material qualifier before "
        "adding anything.",
        "a second competing identity for the same clinical material",
    ),
    "Bis-Beta Carboxyethyl Germanium Sesquioxide": (
        "product disposition decision (standalone germanium products)",
        "Two standalone single-substance germanium bottles (150/100 mg). "
        "RISK_GERMANIUM fires as CAUTION today; identity vs disposition call is "
        "clinical (organic germanium compounds have renal-toxicity history).",
        "clearing a risk-flagged standalone substance without a recorded decision",
    ),
    "Maltodextrin": (
        "other_ingredients excipient identity or intentional-non-scoreable",
        "One gummy-filler row (Immune Support). The taxonomy already recognizes "
        "'standalone_carbohydrate_powder'; this row needs its product-context "
        "decision.",
        "another excipient exception list",
    ),
    "Litesse Polydextrose Fiber": (
        "polydextrose identity (fiber) + product disposition",
        "Litesse is a branded polydextrose; IQM has a generic fiber owner. "
        "Branded-material qualifier vs generic identity is the model question.",
        "a second competing identity for the same material",
    ),
    "Litesse Polydextrose": (
        "polydextrose identity (fiber) + product disposition",
        "Same as above (non-fiber-suffixed variant).",
        "a second competing identity for the same material",
    ),
    "Miroestrol": (
        "product disposition (watchlisted estrogenic compound)",
        "PM Phytogen Complex names miroestrol (Pueraria mirifica constituent, "
        "endocrine-risk watchlist). Identity home vs blocked-ship is clinical.",
        "scoring an endocrine-active watchlist compound",
    ),
    "Withaferin A": (
        "product disposition (watchlisted withanolide)",
        "Isolated cytotoxic withanolide named directly on a label; ashwagandha "
        "the herb is fine, the isolated aglycone is watchlisted.",
        "scoring an isolated cytotoxic constituent",
    ),
    "Silver": (
        "product disposition (colloidal silver)",
        "FDA has warned colloidal silver is not safe/effective; ADD_ "
        "COLLOIDAL_SILVER recognition without primary identity.",
        "scoring a product FDA considers unsafe as a supplement",
    ),
    "Ginkgolic Acid": (
        "product disposition (ginkgo contaminant)",
        "Ginkgolic acid is a knobi allergen CONTAMINANT of ginkgo extract, not "
        "an intended ingredient — the product likely fails a contaminant limit.",
        "normalizing a named contaminant as an ingredient",
    ),
    "3,3-Azo-17a-Methyl-5a-Androstan-17b-Ol": (
        "keep quarantined — safety_policy_review_required",
        "Confirmed synthetic-steroid watchlist match with unresolved US policy; "
        "the quarantine IS the designed state until policy review completes.",
        "shipping a designer steroid as scored",
    ),
    "2, 17a-Dimethyl-17b-Hydroxy-5a-Androst-2-Ene": (
        "keep quarantined — safety_policy_review_required",
        "Same designer-steroid policy-review lane.",
        "shipping a designer steroid as scored",
    ),
    "17a-Ethyl-Estr-5(6)-Ene-3B-Diol": (
        "keep quarantined — safety_policy_review_required",
        "Same designer-steroid policy-review lane.",
        "shipping a designer steroid as scored",
    ),
}


def main() -> int:
    baseline = json.loads((TRIAGE / "baseline_products.json").read_text())
    candidates = {
        c["dsld_id"]: c
        for c in json.loads(
            (TRIAGE / "phase2_banned_candidate_ids.json").read_text()
        )["candidates"]
    }

    iqm = json.loads((REPO / "scripts" / "data" / "ingredient_quality_map.json").read_text())
    dbs = {"ingredient_quality_map": iqm}
    for f in ("other_ingredients", "botanical_ingredients", "standardized_botanicals"):
        dbs[f] = json.loads((REPO / "scripts" / "data" / f"{f}.json").read_text())
    reg = build_canonical_identity_registry(dbs)

    heals, triage, intentional, policy_hold = [], [], [], []
    unresolved_name_counter: Counter = Counter()

    for dsld, row in sorted(baseline.items(), key=lambda kv: int(kv[0])):
        conflict_names = sorted({
            str(c.get("source_label_name"))
            for c in row.get("conflict_rows") or []
        })
        unresolved = [n for n in conflict_names if reg.resolve_preferred(n) is None]
        banned = candidates.get(dsld, {}).get("banned_ids") or []

        dims = row.get("gate_readiness") or {}
        dose_dim = dims.get("dose") or {}
        ident_dim = dims.get("identity") or {}
        dose_code = dose_dim.get("reason_code")
        ident_code = ident_dim.get("reason_code")
        dose_incomplete = dose_dim.get("readiness") == "incomplete"
        sur = row.get("score_unavailable_reason")

        rec = {
            "dsld_id": dsld,
            "product": row.get("product_name"),
            "conflict_names": conflict_names,
            "unresolved_after_fixes": unresolved,
            "banned_ids": banned,
            "gate": f"dose:{dose_code} identity:{ident_code}",
            "score_unavailable_reason": sur,
        }

        # A product only heals mechanically when its identity conflicts resolve
        # AND no dose incompleteness remains. Dose-blocked products with no
        # identity conflicts at all are NOT healed by identity repair.
        if (
            not unresolved
            and not dose_incomplete
            and ident_code != "no_score_eligible_active_rows"
            and dose_code != "no_score_eligible_active_rows"
        ):
            heals.append(rec)
            continue
        if sur == "intentional_non_scoreable_product":
            intentional.append(rec)
            continue
        if sur == "safety_policy_review_required" and not unresolved:
            policy_hold.append(rec)
            continue

        for n in unresolved:
            unresolved_name_counter[n] += 1
        rec["proposal"], rec["rationale"], rec["risk"] = (
            CANONICAL_NOTES.get(
                unresolved[0] if unresolved else "",
                (
                    "manual review",
                    "No canonical note collected; review the label directly.",
                    "an unexplained disposition",
                ),
            )
        )
        triage.append(rec)

    def fmt(rec, key_order):
        lines = [f"### {rec['dsld_id']} — {rec.get('product') or '?'}"]
        for k in key_order:
            v = rec.get(k)
            if v in (None, [], ""):
                continue
            lines.append(f"- **{k}**: {v}")
        return "\n".join(lines) + "\n"

    parts = [
        "# Phase-3 clinical triage — sign-off required",
        "",
        "Products below remain quarantined after the mechanical fixes "
        "(Nickel/Tin canonical identities; 7-Keto-DHEA/Calcium already canonical).",
        "Each has a recommended disposition and the risk of clearing it naively.",
        "**Nothing in this file is applied automatically** — every decision here",
        "needs a human clinical call.",
        "",
        f"- heals mechanically (no action): **{len(heals)}**",
        f"- already intentional_non_scoreable: **{len(intentional)}**",
        f"- safety-policy review hold (designed state): **{len(policy_hold)}**",
        f"- clinical triage required: **{len(triage)}**",
        "",
        "## Unresolved conflict names in the triage set",
        "",
    ]
    for nm, v in unresolved_name_counter.most_common():
        parts.append(f"- {v:3d} × {nm}")

    for title, bucket in (
        ("Clinical triage required", triage),
        ("Safety-policy review hold (stays quarantined by design)", policy_hold),
        ("Already intentional non-scoreable (explained)", intentional),
    ):
        parts += [f"\n## {title} ({len(bucket)})\n"]
        for rec in bucket:
            parts.append(fmt(rec, (
                "gate", "conflict_names", "unresolved_after_fixes", "banned_ids",
                "proposal", "rationale", "risk",
            )))

    OUT.write_text("\n".join(parts) + "\n")
    print(f"heals={len(heals)} intentional={len(intentional)} "
          f"policy_hold={len(policy_hold)} triage={len(triage)} -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
