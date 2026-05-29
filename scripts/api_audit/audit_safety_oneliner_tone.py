#!/usr/bin/env python3
"""Phase 1 tone audit for banned_recalled_ingredients.json safety one-liners.

READ-ONLY. Produces a report — never edits the data file. The "No batch edits
to safety copy" SOP means tone changes must go through reviewed batches; this
audit is the input to that review, not a substitute for it.

Classification model (status + ban_context + clinical_risk, NOT raw string
replacement):

  review_bucket = ALREADY_ALIGNED
    - one-liner already uses a soft, risk-matched action
      (Avoid / Talk to your doctor / Consider / Do not use)
      and carries no bare/clipped "Stop" defect.

  review_bucket = MECHANICAL_SAFE
    - one-liner ends in a *clipped/abrupt* Stop defect that can be fixed
      WITHOUT changing the action semantics or risk level:
        "Stop."                         -> "Stop using."
        "Stop and consult."             -> "Stop using and talk to your doctor."
        "Stop and consult your doctor." -> "Stop using and talk to your doctor."
        "Stop and consult a doctor."    -> "Stop using and talk to a doctor."
      These are grammar/clarity fixes only. "Stop using" is never weaker than
      "Stop." — it just names the object. Whether the entry should ultimately
      use a DIFFERENT verb (Avoid / Do not use) is a CONTEXT decision and is
      deferred to clinical review (see suggested_context_action).

  review_bucket = NEEDS_CLINICAL_REVIEW
    - contamination_recall (product-level: likely "Do not use this recalled product")
    - adulterant_in_supplements (hidden-drug guardrail wording)
    - acute critical-risk substances (may warrant "Stop immediately and seek
      medical advice" rather than the generic mechanical fix)
    - any non-standard Stop variant already in use ("Stop immediately.",
      "Stop and test.") — these are intentional, documented acute hazards and
      must not be flattened by a mechanical pass.

The suggested_context_action column encodes the rubric both reviewers converged
on. It is ADVISORY for the review bucket — the audit does not apply it.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"
DEFAULT_OUTPUT = ROOT / "reports" / "safety_oneliner_tone_audit.csv"

# Context-keyed default action phrase (advisory, for the review bucket).
_CONTEXT_ACTION = {
    "watchlist": "Avoid. / Talk to your doctor.",
    "contamination_recall": "Do not use this recalled product.",
    "adulterant_in_supplements": "Stop using and talk to your doctor.",
    "export_restricted": "Talk to your doctor.",
    "substance": None,  # depends on clinical_risk — resolved below
}


def _closing_pattern(one_liner: str) -> str:
    """Classify the trailing action phrase of a one-liner."""
    s = (one_liner or "").strip()
    if not s:
        return "(empty)"
    checks = [
        (r"\bStop\.\s*$", "Stop."),
        (r"\bStop and consult\.\s*$", "Stop and consult."),
        (r"\bStop and consult (your|a) doctor\.\s*$", "Stop and consult your/a doctor."),
        (r"\bStop immediately\b.*$", "Stop immediately (acute)"),
        (r"\bStop and test\b.*$", "Stop and test (acute)"),
        (r"\bStop using\b.*$", "Stop using (already clear)"),
        (r"\bDo not use\b.*$", "Do not use (already clear)"),
        (r"\bAvoid\b.*$", "Avoid"),
        (r"\b(Talk to|Consult|Discuss with|Speak with|Consider)\b.*$", "Talk/Consult/Consider"),
    ]
    for pat, label in checks:
        if re.search(pat, s):
            return label
    return "Other"


# Mechanical-safe rewrites: clipped Stop defect -> clear Stop-using phrasing.
# Each maps a closing pattern to its deterministic replacement transform.
_MECHANICAL_CLOSINGS = {
    "Stop.": ("Stop.", "Stop using."),
    "Stop and consult.": ("Stop and consult.", "Stop using and talk to your doctor."),
}


def _mechanical_fix(one_liner: str, closing: str) -> Optional[str]:
    """Return the deterministically-fixed one-liner, or None if no clean fix."""
    s = (one_liner or "").strip()
    if closing in _MECHANICAL_CLOSINGS:
        old, new = _MECHANICAL_CLOSINGS[closing]
        return re.sub(re.escape(old) + r"\s*$", new, s)
    if closing == "Stop and consult your/a doctor.":
        # Normalize "consult your/a doctor" -> "talk to your/a doctor",
        # softening "Stop" -> "Stop using" but preserving your/a.
        fixed = re.sub(r"\bStop and consult (your|a) doctor\.\s*$",
                       r"Stop using and talk to \1 doctor.", s)
        return fixed
    return None


def _suggested_context_action(status: str, ban_context: str, clinical_risk: str) -> str:
    if ban_context == "watchlist" or status == "watchlist":
        return "Avoid. / Talk to your doctor."
    if ban_context == "contamination_recall":
        return "Do not use this recalled product."
    if ban_context == "adulterant_in_supplements":
        return "Stop using and talk to your doctor. (hidden-drug guardrail)"
    if ban_context == "export_restricted":
        return "Talk to your doctor."
    # substance
    if clinical_risk == "critical":
        return "Stop using and talk to your doctor. (review for 'Stop immediately' if acute)"
    if clinical_risk in ("high", "dose_dependent"):
        return "Stop using and talk to your doctor."
    return "Avoid."  # moderate / low regulatory substance


# Action-phrase strength scale (weak -> strong). Used to detect the inverse
# defect the first audit missed: a SOFT closer ("Avoid." / "Talk to your
# doctor.") on an entry whose context warrants a STRONGER action (heavy-metal
# toxin, critical hazard) is NOT "aligned" — it is an under-statement that
# needs clinical review just as much as an over-harsh "Stop." does.
_ACTION_STRENGTH = {
    "(empty)": 0,
    "Avoid": 1,
    "Talk/Consult/Consider": 2,
    "Stop.": 3,
    "Stop and consult.": 3,
    "Stop and consult your/a doctor.": 3,
    "Stop using (already clear)": 3,
    "Do not use (already clear)": 4,
    "Stop and test (acute)": 4,
    "Stop immediately (acute)": 5,
    "Other": 2,
}

# Heavy-metal / cumulative-toxin substances — soft "Avoid." understates the
# current-use action even though they are not flagged as adulterants/recalls.
_HEAVY_METAL_TOKENS = (
    "arsenic", "cadmium", "lead", "mercury", "thallium", "antimony",
    "chromium_vi", "hexavalent", "heavy_metal", "heavy metal",
)


def _is_heavy_metal(entry_id: str, one_liner: str) -> bool:
    blob = f"{entry_id} {one_liner}".lower()
    return any(tok in blob for tok in _HEAVY_METAL_TOKENS)


def _is_wada(entry_id: str) -> bool:
    return entry_id.upper().startswith("WADA")


def _suggested_strength(status: str, ban_context: str, clinical_risk: str,
                        heavy_metal: bool, wada: bool) -> int:
    if ban_context == "watchlist" or status == "watchlist":
        return 1  # Avoid
    if ban_context == "contamination_recall":
        return 4  # Do not use this recalled product
    if ban_context == "adulterant_in_supplements":
        return 3  # Stop using and talk to your doctor
    if wada:
        return 2  # competition eligibility, not acute health danger — Talk to physician
    if ban_context == "export_restricted":
        return 2
    # substance
    if heavy_metal:
        return 3  # cumulative toxin: current-use action, not future avoidance
    if clinical_risk == "critical":
        return 3  # at least Stop using; reviewer decides if 'Stop immediately'
    if clinical_risk in ("high", "dose_dependent"):
        return 3
    return 1  # moderate / low regulatory substance -> Avoid


def _review_bucket(status: str, ban_context: str, clinical_risk: str,
                   closing: str, has_mechanical: bool,
                   heavy_metal: bool, wada: bool) -> str:
    current_strength = _ACTION_STRENGTH.get(closing, 2)
    suggested_strength = _suggested_strength(
        status, ban_context, clinical_risk, heavy_metal, wada
    )

    # Documented acute variants must never be flattened.
    if closing in ("Stop immediately (acute)", "Stop and test (acute)"):
        return "NEEDS_CLINICAL_REVIEW"

    # INVERSE DEFECT: current copy is softer than the context warrants.
    # Heavy metals, modafinil, critical hazards reading "Avoid." land here —
    # the human decides whether the soft phrasing is intentional (e.g. WADA
    # competition rules) or an under-statement that must be strengthened.
    if current_strength < suggested_strength:
        return "ACTION_MISMATCH_REVIEW"

    # High-impact contexts get human eyes even when a mechanical fix exists —
    # the verb itself (Stop using vs Do not use vs Stop immediately) is a
    # clinical-actionability decision, not a grammar fix.
    if ban_context in ("contamination_recall", "adulterant_in_supplements"):
        return "NEEDS_CLINICAL_REVIEW"
    if heavy_metal or wada:
        return "NEEDS_CLINICAL_REVIEW"
    if clinical_risk == "critical":
        return "NEEDS_CLINICAL_REVIEW"

    # Already soft/clear AND strong enough for its context — nothing to do.
    if closing in ("Avoid", "Talk/Consult/Consider", "Do not use (already clear)",
                   "Stop using (already clear)"):
        return "ALREADY_ALIGNED"

    # MECHANICAL_SAFE — NARROWED per clinical review:
    # only non-critical / non-high regulatory SUBSTANCE entries with a pure
    # clipped-grammar defect, where the deterministic fix lands at exactly the
    # context-suggested strength (no semantic gap). High-risk botanicals,
    # heavy metals, WADA, adulterants, recalls are all excluded above.
    if (
        has_mechanical
        and ban_context == "substance"
        and clinical_risk in ("moderate", "low", "dose_dependent")
    ):
        return "MECHANICAL_SAFE"

    if closing == "(empty)":
        return "NEEDS_CLINICAL_REVIEW"
    return "NEEDS_CLINICAL_REVIEW"


def audit(input_path: Path, output_path: Path) -> Dict[str, int]:
    doc = json.loads(input_path.read_text(encoding="utf-8"))
    entries = doc.get("ingredients", [])
    rows = []
    counts: Dict[str, int] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        status = str(e.get("status") or "")
        ban_context = str(e.get("ban_context") or "")
        clinical_risk = str(e.get("clinical_risk_enum") or e.get("clinical_risk") or "")
        one = str(e.get("safety_warning_one_liner") or "")
        entry_id = str(e.get("id") or "")
        closing = _closing_pattern(one)
        mech = _mechanical_fix(one, closing)
        heavy_metal = _is_heavy_metal(entry_id, one)
        wada = _is_wada(entry_id)
        bucket = _review_bucket(
            status, ban_context, clinical_risk, closing,
            mech is not None, heavy_metal, wada,
        )
        counts[bucket] = counts.get(bucket, 0) + 1
        rows.append({
            "id": entry_id,
            "status": status,
            "ban_context": ban_context,
            "clinical_risk": clinical_risk,
            "current_one_liner": one,
            "closing_pattern": closing,
            "current_strength": _ACTION_STRENGTH.get(closing, 2),
            "suggested_strength": _suggested_strength(
                status, ban_context, clinical_risk, heavy_metal, wada
            ),
            "review_bucket": bucket,
            "mechanical_fix": mech or "",
            "suggested_context_action": _suggested_context_action(status, ban_context, clinical_risk),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "status", "ban_context", "clinical_risk",
        "current_one_liner", "closing_pattern",
        "current_strength", "suggested_strength",
        "review_bucket", "mechanical_fix", "suggested_context_action",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    counts["total"] = len(rows)
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 1 safety one-liner tone audit (read-only)")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    counts = audit(args.input, args.output)
    print("Safety one-liner tone audit (READ-ONLY — no data edits):")
    for k in ("total", "ALREADY_ALIGNED", "MECHANICAL_SAFE",
              "ACTION_MISMATCH_REVIEW", "NEEDS_CLINICAL_REVIEW"):
        if k in counts:
            print(f"  {k}: {counts[k]}")
    print(f"  output: {args.output}")


if __name__ == "__main__":
    main()
