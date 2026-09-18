#!/usr/bin/env python3
"""Render the owner review packet from wave1_contexts.json (read-only).

One decision group per identity, ordered by catalog impact x uncertainty, so the
reviewer verifies structured evidence instead of researching papers. Nothing here
is applied; every context is pending and every synthesis is a proposal.

    python3 scripts/audits/evidence_expansion_2026_09/build_review_packet.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
PACKET = Path(__file__).resolve().parents[3] / "docs/plans/EVIDENCE_EXPANSION_WAVE1_REVIEW_PACKET_2026-09.md"


def quote(text: str, limit: int = 240) -> str:
    text = str(text).replace("|", "\\|").replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> int:
    payload = json.loads((OUT / "wave1_contexts.json").read_text())
    candidates = sorted(payload["candidates"],
                        key=lambda c: -(c["catalog_impact"]["evidence_zero_products"]
                                        + c["catalog_impact"]["evidence_le8_products"]))
    lines = [
        "# Evidence expansion — Wave 1 review packet (2026-09-17)", "",
        "**Status: PENDING. Nothing in this packet has been applied.** No production data was written, no score "
        "moved, no scoring rule changed, no catalog rebuild, no release.", "",
        "Claude authored every context as `source_verified_pending_clinical_review`. Approval is the owner's act. "
        "The reviewer string on any approval must say engineering owner — never clinician — unless a clinician signs.", "",
        "Each PMID below was re-fetched live from PubMed after screening; every quote is a verbatim contiguous span "
        "of the live abstract, checked by `validate_wave1_contexts.py` and `verify_shortlist.py`.", "",
        "## Decision summary", "",
        "| identity | products | Ev=0 | Ev≤8 | contexts | proposal | scorer class |",
        "|---|---:|---:|---:|---:|---|:--:|"]
    for c in candidates:
        impact = c["catalog_impact"]
        lines.append(f"| [{c['label_name']}](#{c['canonical_id'].replace('_', '-')}) | {impact['products']} | "
                     f"{impact['evidence_zero_products']} | {impact['evidence_le8_products']} | {len(c['contexts'])} | "
                     f"{c['proposed_record_level_synthesis']['proposal'].split('—')[0].strip()} | "
                     f"{c['scorer_compatibility']['class']} |")
    lines += ["", "Scorer class: **A** = the current generic scorer can apply this evidence safely; "
              "**B** = the context is valid but the scorer is too coarse, so the production synthesis is held. "
              "This is an audit determination, not a production field.", ""]

    for c in candidates:
        impact = c["catalog_impact"]
        synthesis = c["proposed_record_level_synthesis"]
        lines += [f"## {c['label_name']}", "",
                  f"`{c['canonical_id']}` — {impact['products']} products, {impact['brands']} brands, "
                  f"{impact['slots']} label rows; Evidence mean {impact['evidence_mean']}, "
                  f"{impact['evidence_zero_products']} at zero, {impact['evidence_le8_products']} at ≤8. "
                  f"Review state today: {impact['review_state']}.", "",
                  f"**Label reality.** {c['label_reality']}", ""]
        # Generated from the measured corpus distribution, never hand-typed prose.
        if c.get("label_exposure_measured"):
            lines += [c["label_exposure_measured"], ""]
        counts = c["publication_vs_trial_count"]
        lines += [f"**Publications vs trials.** {counts['publications']} publications, "
                  f"{counts['unique_trials_or_cohorts']} unique trials/cohorts, "
                  f"{counts['independent_replications']} independent replications. {counts['note']}", "",
                  "### Contexts (all pending)", ""]
        for ctx in c["contexts"]:
            dose = ctx["dose"]
            values = ", ".join(f"{v:g}" for v in dose.get("values") or []) or "not resolved"
            lines += [f"**`{ctx['context_id']}`** — PMID {', '.join(ctx['source_pmids'])} · "
                      f"{ctx.get('study_design', ctx['evidence_role'])} · {ctx['evidence_role']} · "
                      f"funding: {ctx.get('funding', 'unreported')}", "",
                      f"- Identity: {ctx['identity_scope']} — " +
                      "; ".join(f"{k}: {v}" for k, v in ctx["identity"].items()),
                      f"- Exposure: {ctx['exposure_basis']}, route {ctx['route']}, dose {values} "
                      f"{dose.get('unit')} ({dose.get('dose_status')})",
                      f"- Population: {ctx['population']['description']}",
                      "- Outcomes: " + "; ".join(
                          f"{o['name']} ({o['hierarchy']}/{o['kind']}) → **{o['direction']}**"
                          for o in ctx["outcomes"])]
            for evidence in ctx.get("outcome_provenance", [])[:2]:
                lines.append(f"  - > {quote(evidence['quote'])}")
            if dose.get("source_provenance"):
                lines.append(f"  - dose > {quote(dose['source_provenance']['quote'])}")
            lines.append("- Limitations: " + " ".join(f"({i + 1}) {lim}" for i, lim in enumerate(ctx["limitations"])))
            lines.append("")
        if c.get("scorer_compatibility_probe"):
            probe = c["scorer_compatibility_probe"]
            lines += ["### Live probe against the current architecture", "", f"{probe['method']}", ""]
            for result in probe["results"]:
                lines.append(f"- **{result['dsld_id']} {result['product']}** — {result['result']}")
            lines += ["", probe["conclusion"], ""]
        lines += ["### Proposed synthesis (for your decision)", "",
                  f"**{synthesis['proposal']}**", "", synthesis["rationale"], ""]
        for key in ("fields_if_population_is_ever_enforced", "fields_if_material_scoping_becomes_possible",
                    "if_owner_approves_anyway", "proposed_fields"):
            if key in synthesis:
                lines += [f"<details><summary>{key.replace('_', ' ')}</summary>", "",
                          "```json", json.dumps(synthesis[key], indent=1), "```", "</details>", ""]
        if synthesis.get("what_would_unblock_it"):
            lines += ["**What would unblock it:**"] + [f"- {x}" for x in synthesis["what_would_unblock_it"]] + [""]
        if synthesis.get("owner_decisions_needed"):
            lines += ["**Decisions needed from you:**"] + [f"- {x}" for x in synthesis["owner_decisions_needed"]] + [""]
        lines += [f"- Evidence strength: {synthesis['evidence_strength']}",
                  f"- Applicability to labels: {synthesis['applicability_to_labels']}",
                  f"- Review completeness: {synthesis['review_completeness']}",
                  f"- Scorer compatibility: **class {c['scorer_compatibility']['class']}** — "
                  f"{c['scorer_compatibility']['reason']}", ""]
        if c.get("authoritative_references"):
            lines += ["### Authoritative guidance (recorded as references, not study contexts)", "",
                      "The frozen context contract requires a PMID and a regulator assessment has none, so these use "
                      "the shape the registry already has for non-PubMed sources.", ""]
            for ref in c["authoritative_references"]:
                lines += [f"**{ref['authority']}** — {ref['title']}  ",
                          f"{ref['url']} · retrieved {ref['retrieved']} · {ref['verification']}", ""]
                for q in ref.get("quotes", []):
                    lines.append(f"> {quote(q, 400)}")
                lines.append("")
                if ref.get("why_it_does_not_change_the_hold"):
                    lines += [f"*{ref['why_it_does_not_change_the_hold']}*", ""]
                if ref.get("destination"):
                    lines += [f"*Destination: {ref['destination']}*", ""]
        if c.get("handoff"):
            lines += ["### Handoffs to other owners (no clinical interpretation here)", "",
                      "| PMID | role | destination | reason |", "|---|---|---|---|"]
            for h in c["handoff"]:
                lines.append(f"| {h['pmid']} | {h['role']} | {h['destination']} | {quote(h['reason'], 160)} |")
            lines.append("")
        if c.get("high_risk_flags"):
            lines += [f"### High-risk queue: {', '.join(c['high_risk_flags'])}", "",
                      "Flagged for eventual clinician countersignature; it does not block the owner review above.", ""]
        lines += ["**Actions:** approve · approve with correction · reject · hold · request adjudication · "
                  "request more source review", "", "---", ""]

    PACKET.parent.mkdir(parents=True, exist_ok=True)
    PACKET.write_text("\n".join(lines) + "\n")
    print(f"wrote {PACKET} ({len(lines)} lines, {len(candidates)} decision groups)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
