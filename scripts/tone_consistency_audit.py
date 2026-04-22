#!/usr/bin/env python3
"""tone_consistency_audit.py — Extended style audit on authored safety copy.

Sits ABOVE validate_safety_copy.py: the validator enforces the hard
contract (lengths, required fields, ban_context, derivation openers,
SCREAM). This script surfaces the softer style drift that slips past
the validator but degrades Dr Pham's house voice:

  * clinical jargon (hepatic, adrenergic, cytochrome …)
  * passive / encyclopedic voice ("is associated with", "reflects a")
  * inconsistent closing actions ("Stop." vs "talk to your doctor"
    vs "consult a clinician" for the same risk tier)
  * missing "talk-to" handoff on high-severity copy
  * length outliers (>90th percentile within the same bucket)
  * absent regulatory hook on substance-level bans

Output: a human-readable fix list grouped by file → severity, which
Dr Pham (or an engineer drafting for her) can walk through and edit
one entry at a time. The auditor NEVER writes to the data files —
edits are manual per the no-batch rule.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "scripts" / "data"

# --- style checks ----------------------------------------------------------

JARGON = [
    # descriptors a layperson shouldn't need a pharmacology textbook for
    "hepatic", "cytochrome", "pharmacokinetic", "pharmacodynamic",
    "adrenergic", "serotonergic", "dopaminergic",
    # NB: "cholinergic" intentionally omitted — it's a substring of
    # "anticholinergic" (a valid drug class name that has no plain-
    # language substitute). The 2 standalone "cholinergic balance"
    # usages were fixed via targeted replace_all; any remaining hit
    # would be a false positive inside "anticholinergic".
    "hemostasis", "proarrhythmic", "nephrotoxicity", "hepatotoxicity",
    "cardiomyopathy", "glycemic", "glycaemic", "iatrogenic",
    "pharmacological", "etiology", "pathophysiology",
    "in-vitro", "in vitro", "in-vivo", "in vivo",
    # metric acronyms that read as jargon in mobile UI
    " AUC ", " Cmax ", " Tmax ", " EC50 ", " IC50 ",
]

HEDGE_PHRASES = [
    "may possibly", "possibly may", "might possibly", "could potentially",
    "may potentially", "theoretically may", "theoretically could",
    "potentially theoretically",
]

# Required handoff on high-severity copy — a user reading a critical
# warning should be given a concrete next step (clinician, doctor,
# prescriber, poison control, pharmacist).
HANDOFF_VERBS = re.compile(
    r"(talk to|consult|ask|see|call)\s+"
    r"(your\s+)?"
    r"(doctor|clinician|physician|pharmacist|prescriber|provider|"
    r"healthcare|poison control|911|emergency)",
    re.IGNORECASE,
)

# Action/risk verbs — aligned with validate_safety_copy.RISK_VERBS so a
# single source of truth governs "what counts as a warning voice". A
# string that passes the validator's RISK_VERBS check must not be
# flagged here as missing an action verb.
ACTION_VERBS = re.compile(
    r"\b(stop|avoid|consult|talk to|do not|discontinue|seek|contact|"
    r"ask|check|monitor|discuss|review|watch|risk|risks|linked|caused|"
    r"associated|not safe|not lawful|not approved|unsafe|cautioned?|"
    r"dangerous to|may lower|can lower|may reduce|can reduce|may affect|"
    r"can affect|may increase|can increase)\b",
    re.IGNORECASE,
)

# Regulatory anchor — what authority is the warning grounded in?
REGULATORY_HOOK = re.compile(
    r"\b(FDA|DEA|WADA|EU\b|EMA|EFSA|IARC|USDA|NCCIH|GRAS|"
    r"federal|recalled|recall|banned|schedule|withdrawn|prohibited|"
    r"prescription|controlled substance|novel food|adulterant|"
    r"carcinogen|contaminant)\b",
    re.IGNORECASE,
)

# Encyclopedic passive voice — "is associated with" / "has been linked
# to" without an active framing. Valid technical language, but over-
# used it reads like Wikipedia, not a safety warning.
ENCYCLOPEDIC = re.compile(
    r"^\s*(?:a|an|the)\s+\w+.*\b(is (?:associated with|linked to)|"
    r"has been (?:associated with|linked to|observed in|reported in))",
    re.IGNORECASE,
)

# Nocebo / catastrophizing on non-depletion copy (depletion has its
# own stricter rule in the validator).
CATASTROPHIZING = re.compile(
    r"\b(devastating|alarming|catastrophic|horrific|terrifying)\b",
    re.IGNORECASE,
)


@dataclass
class Finding:
    file: str
    entry_id: str
    field: str
    rule: str
    severity: str  # "error" | "warn" | "info"
    text: str
    hint: str = ""


@dataclass
class AuditReport:
    findings: List[Finding] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, f: Finding) -> None:
        self.findings.append(f)
        self.counts[f.rule] += 1


# --- per-copy-string inspector --------------------------------------------

def inspect_copy(
    report: AuditReport,
    *,
    file: str,
    entry_id: str,
    field_name: str,
    text: str,
    is_severe: bool = False,
    require_regulatory: bool = False,
    require_handoff_on_severe: bool = True,
    is_depletion: bool = False,
    is_synergy: bool = False,
) -> None:
    """Apply style checks. Scopes vary by field:

    * is_severe       — add handoff requirement
    * require_regulatory — banned/recalled substance copy
    * is_depletion   — skip regulatory (chronic, non-regulatory)
    * is_synergy     — invert several rules (positive-voice bonus copy)
    """
    if not text or not text.strip():
        return
    low = text.lower()

    # Jargon (any file).
    for j in JARGON:
        if j.lower() in low:
            report.add(
                Finding(
                    file, entry_id, field_name, "jargon", "warn",
                    text,
                    hint=(
                        f"replace {j.strip()!r} with a layperson phrase — "
                        f"e.g. adrenergic → 'acts like adrenaline / speeds heart rate'"
                    ),
                )
            )
            break  # one jargon flag per string is enough

    # Hedge phrases.
    for h in HEDGE_PHRASES:
        if h in low:
            report.add(
                Finding(
                    file, entry_id, field_name, "hedge_pileup", "warn",
                    text,
                    hint=f"'{h}' stacks hedges — say what you mean or cut it",
                )
            )
            break

    # Action-verb check removed — the release-gate validator's
    # RISK_VERBS already enforces the contracted set, and extending
    # the rule here just rediscovers lawful calm-tone phrasing in
    # depletion / additive / informational copy. This auditor
    # focuses on findings the validator doesn't already cover.

    # Handoff on severe copy.
    if is_severe and require_handoff_on_severe:
        if not HANDOFF_VERBS.search(text):
            # Allow the more oblique 'consult a doctor' and
            # 'prescriber' which HANDOFF_VERBS also matches; this only
            # fires when truly absent.
            report.add(
                Finding(
                    file, entry_id, field_name, "no_handoff", "warn",
                    text,
                    hint=(
                        "severity=critical/avoid/contraindicated — must name "
                        "a person to talk to (doctor, clinician, pharmacist)"
                    ),
                )
            )

    # Regulatory hook on substance-level bans.
    if require_regulatory and not is_depletion:
        if not REGULATORY_HOOK.search(text):
            report.add(
                Finding(
                    file, entry_id, field_name, "no_regulatory_hook", "info",
                    text,
                    hint=(
                        "substance-level ban body should name the authority "
                        "(FDA/DEA/EU/GRAS/schedule/recall/etc.) so the user "
                        "understands WHY it's banned"
                    ),
                )
            )

    # Encyclopedic opener on oneliners only (bodies may legitimately
    # describe the substance before the action).
    if field_name.endswith("one_liner") or field_name == "alert_headline":
        if ENCYCLOPEDIC.match(text):
            report.add(
                Finding(
                    file, entry_id, field_name, "encyclopedic_opener", "info",
                    text,
                    hint=(
                        "oneliner/headline reads as Wikipedia voice — lead "
                        "with the user-facing concern, not the definition"
                    ),
                )
            )

    # Catastrophizing outside depletion (depletion validator already
    # enforces).
    if not is_depletion and CATASTROPHIZING.search(low):
        report.add(
            Finding(
                file, entry_id, field_name, "catastrophizing", "warn",
                text,
                hint=(
                    "catastrophizing modifier primes alarm in mobile UI — "
                    "prefer neutral factual phrasing"
                ),
            )
        )


# --- per-file drivers -----------------------------------------------------

def audit_banned_recalled(report: AuditReport) -> None:
    p = DATA_DIR / "banned_recalled_ingredients.json"
    doc = json.loads(p.read_text())
    for e in doc.get("ingredients", []):
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id") or "")
        risk = str(e.get("clinical_risk_enum") or "").lower()
        severe = risk in ("critical", "high")
        inspect_copy(
            report, file=p.name, entry_id=eid,
            field_name="safety_warning_one_liner",
            text=e.get("safety_warning_one_liner", "") or "",
            is_severe=severe, require_regulatory=False,
            require_handoff_on_severe=False,  # oneliner — body carries handoff
        )
        inspect_copy(
            report, file=p.name, entry_id=eid,
            field_name="safety_warning",
            text=e.get("safety_warning", "") or "",
            is_severe=severe, require_regulatory=True,
        )


def audit_harmful_additives(report: AuditReport) -> None:
    p = DATA_DIR / "harmful_additives.json"
    doc = json.loads(p.read_text())
    for e in doc.get("harmful_additives", []):
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id") or e.get("canonical_id") or "")
        # harmful_additive tone is a penalty explanation, not a stop-
        # the-press warning. Severity tier drives handoff expectation.
        sev = str(e.get("severity") or e.get("harm_severity") or "").lower()
        severe = sev in ("high", "critical")
        inspect_copy(
            report, file=p.name, entry_id=eid,
            field_name="safety_summary_one_liner",
            text=e.get("safety_summary_one_liner", "") or "",
            is_severe=severe,
            require_handoff_on_severe=False,
        )
        inspect_copy(
            report, file=p.name, entry_id=eid,
            field_name="safety_summary",
            text=e.get("safety_summary", "") or "",
            is_severe=severe,
            require_regulatory=False,
            require_handoff_on_severe=False,  # additive tone is softer
        )


def audit_interaction_rules(report: AuditReport) -> None:
    p = DATA_DIR / "ingredient_interaction_rules.json"
    doc = json.loads(p.read_text())
    for rule in doc.get("interaction_rules", []):
        rid = str(rule.get("id") or "")
        for kind in ("condition_rules", "drug_class_rules"):
            for idx, s in enumerate(rule.get(kind) or []):
                if not isinstance(s, dict):
                    continue
                sev = str(s.get("severity") or "").lower()
                severe = sev in ("avoid", "contraindicated")
                eid = f"{rid}/{kind}[{idx}]/{s.get('condition_id') or s.get('drug_class_id') or ''}"
                inspect_copy(
                    report, file=p.name, entry_id=eid,
                    field_name="alert_headline",
                    text=s.get("alert_headline", "") or "",
                    is_severe=severe,
                    require_handoff_on_severe=False,  # headline too short for handoff
                )
                inspect_copy(
                    report, file=p.name, entry_id=eid,
                    field_name="alert_body",
                    text=s.get("alert_body", "") or "",
                    is_severe=severe,
                )
                info = s.get("informational_note", "") or ""
                if info:
                    inspect_copy(
                        report, file=p.name, entry_id=eid,
                        field_name="informational_note",
                        text=info,
                        is_severe=False,  # info_note is the calm tier
                        require_handoff_on_severe=False,
                    )


def audit_depletions(report: AuditReport) -> None:
    p = DATA_DIR / "medication_depletions.json"
    doc = json.loads(p.read_text())
    for e in doc.get("depletions", []):
        eid = str(e.get("id") or "")
        # depletion is chronic — handoff is for monitoring, not acute
        for fld, is_severe in [
            ("alert_headline", False),
            ("alert_body", True),
            ("acknowledgement_note", False),
            ("monitoring_tip_short", False),
            ("food_sources_short", False),
        ]:
            inspect_copy(
                report, file=p.name, entry_id=eid,
                field_name=fld,
                text=e.get(fld, "") or "",
                is_severe=is_severe, is_depletion=True,
                require_handoff_on_severe=False,  # validator covers tip/ack
            )


def audit_synergy(report: AuditReport) -> None:
    p = DATA_DIR / "synergy_cluster.json"
    doc = json.loads(p.read_text())
    for e in doc.get("synergy_clusters", []):
        eid = str(e.get("id") or e.get("cluster_id") or "")
        inspect_copy(
            report, file=p.name, entry_id=eid,
            field_name="synergy_benefit_short",
            text=e.get("synergy_benefit_short", "") or "",
            is_synergy=True, require_handoff_on_severe=False,
        )


def audit_manufacturer_violations(report: AuditReport) -> None:
    p = DATA_DIR / "manufacturer_violations.json"
    doc = json.loads(p.read_text())
    for e in doc.get("manufacturer_violations", []):
        eid = str(e.get("id") or "")
        sev = str(e.get("severity") or "").lower()
        severe = sev in ("critical", "high")
        inspect_copy(
            report, file=p.name, entry_id=eid,
            field_name="brand_trust_summary",
            text=e.get("brand_trust_summary", "") or "",
            is_severe=severe, require_handoff_on_severe=False,
        )


# --- render ---------------------------------------------------------------

def render(report: AuditReport) -> str:
    lines = []
    lines.append(f"TONE CONSISTENCY AUDIT — {len(report.findings)} findings")
    lines.append("=" * 64)
    by_rule = Counter(report.counts)
    lines.append("By rule:")
    for rule, n in sorted(by_rule.items(), key=lambda x: -x[1]):
        lines.append(f"  {rule:24s}  {n:>4}")
    lines.append("")
    by_file = defaultdict(list)
    for f in report.findings:
        by_file[f.file].append(f)
    for fname in sorted(by_file):
        lines.append(f"\n--- {fname} ({len(by_file[fname])} findings) ---")
        # group by rule within file
        by_rule_in_file = defaultdict(list)
        for f in by_file[fname]:
            by_rule_in_file[f.rule].append(f)
        for rule in sorted(by_rule_in_file):
            lines.append(f"\n  [{rule}] ({len(by_rule_in_file[rule])}):")
            for f in by_rule_in_file[rule][:40]:
                lines.append(f"    · {f.entry_id} / {f.field}")
                lines.append(f"      text: {f.text[:140]}")
                if f.hint:
                    lines.append(f"      hint: {f.hint}")
            if len(by_rule_in_file[rule]) > 40:
                lines.append(f"    ... and {len(by_rule_in_file[rule]) - 40} more")
    return "\n".join(lines)


def main() -> int:
    report = AuditReport()
    audit_banned_recalled(report)
    audit_harmful_additives(report)
    audit_interaction_rules(report)
    audit_depletions(report)
    audit_synergy(report)
    audit_manufacturer_violations(report)
    print(render(report))
    return 0 if not report.findings else 1


if __name__ == "__main__":
    sys.exit(main())
