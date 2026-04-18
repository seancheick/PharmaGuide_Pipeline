#!/usr/bin/env python3
"""
validate_safety_copy.py — Build-time validator for authored medical-grade copy.

Enforces the field contracts defined in scripts/SAFETY_DATA_PATH_C_PLAN.md for:
  * scripts/data/banned_recalled_ingredients.json  — ban_context, safety_warning,
    safety_warning_one_liner
  * scripts/data/ingredient_interaction_rules.json — alert_headline, alert_body,
    informational_note on each condition_rule / drug_class_rule
  * scripts/data/medication_depletions.json        — alert_headline, alert_body,
    acknowledgement_note, monitoring_tip_short per depletion entry

Fail-loud: any violation returns a non-zero exit and prints the offending entry
so the build gate (CI) halts before shipping.

Usage:
  python3 scripts/validate_safety_copy.py                          # validate all
  python3 scripts/validate_safety_copy.py --banned-recalled-only
  python3 scripts/validate_safety_copy.py --interaction-rules-only
  python3 scripts/validate_safety_copy.py --depletions-only
  python3 scripts/validate_safety_copy.py --strict                 # require ALL
                                                                    # authored
                                                                    # fields
                                                                    # populated
                                                                    # (release-
                                                                    # gate mode)

During authoring transition, the default mode treats missing authored fields
as warnings (PASS). Strict mode promotes missing fields to errors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "scripts" / "data"

VALID_BAN_CONTEXTS = {
    "substance",
    "adulterant_in_supplements",
    "watchlist",
    "export_restricted",
}

# Opener patterns the old derivation template produced. If authored copy
# starts with these, the author likely pasted a derived string unchanged.
BAD_OPENERS = re.compile(
    r"^[A-Z][\w\-]+ is (?:a |an |the )?(?:prescription|synthetic|FDA|an\s+)",
    re.IGNORECASE,
)

# Risk/action verbs we require in safety_warning. Authored copy that lacks
# ALL of these is encyclopedic definition, not a warning.
RISK_VERBS = ("stop", "avoid", "consult", "risk", "linked", "caused",
              "associated", "do not", "talk to")

# Adulterant-context guardrail — the copy MUST clarify the "in supplement"
# framing so users on prescribed versions don't panic.
ADULTERANT_GUARDRAIL = re.compile(
    r"(in|within|found in|as an adulterant in)\s+[^.]{0,40}(supplement|product|dietary)",
    re.IGNORECASE,
)

# Profile-conditional framing required in alert_body for avoid/
# contraindicated rules — ensures copy reads as "if you take X" not "DON'T
# TAKE X" when surfaced to any user.
CONDITIONAL_FRAMING = re.compile(
    r"(if you|when you|people who|do not combine|talk to|discuss with|"
    r"monitor|ask your)",
    re.IGNORECASE,
)

# Informational notes must not sound like directives.
IMPERATIVE_VERBS = re.compile(
    r"\b(stop|avoid|do not|don't|never|always)\b",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def extend(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# banned_recalled_ingredients.json per-entry validator
# ---------------------------------------------------------------------------


def validate_banned_recalled_entry(
    entry: Dict[str, Any],
    strict: bool = False,
) -> ValidationResult:
    """Apply Path C contract rules to a single banned_recalled entry."""
    res = ValidationResult()
    canonical_id = str(entry.get("id") or entry.get("canonical_id") or "")
    std_name = str(entry.get("standard_name") or "").strip()
    ban_context = entry.get("ban_context")
    sw = entry.get("safety_warning")
    swol = entry.get("safety_warning_one_liner")

    if canonical_id and canonical_id != canonical_id.lower():
        # Path C §Footgun C — lowercase invariant for canonical_id.
        # Banned/recalled uses UPPER historically across 143 entries.
        # Changing the casing would cascade into Flutter joins and the
        # cross-references in ingredient_interaction_rules.json's
        # subject_ref blocks, so this stays a WARN even under strict
        # mode — authoring work shouldn't be blocked on migration debt
        # that belongs to a separate cleanup pass. Strict mode on the
        # NEWLY authored copy fields is still enforced below.
        res.warn(f"{canonical_id}: canonical_id is not lowercase")

    # ban_context is required in strict mode, optional during authoring.
    if ban_context is None:
        msg = f"{canonical_id}: missing ban_context"
        (res.fail if strict else res.warn)(msg)
    elif ban_context not in VALID_BAN_CONTEXTS:
        res.fail(
            f"{canonical_id}: invalid ban_context={ban_context!r} "
            f"(allowed: {sorted(VALID_BAN_CONTEXTS)})"
        )

    # safety_warning contract.
    if sw is None:
        msg = f"{canonical_id}: missing safety_warning"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(sw, str):
        res.fail(f"{canonical_id}: safety_warning must be string, got {type(sw).__name__}")
    else:
        sw_s = sw.strip()
        if std_name and sw_s.startswith(f"{std_name} is "):
            res.fail(
                f"{canonical_id}: safety_warning starts with derivation template "
                f"'{std_name} is ...'"
            )
        if BAD_OPENERS.match(sw_s):
            res.fail(
                f"{canonical_id}: safety_warning uses encyclopedic opener "
                f"('is a prescription/synthetic/FDA ...')"
            )
        if not (50 <= len(sw_s) <= 200):
            res.fail(
                f"{canonical_id}: safety_warning length {len(sw_s)} outside [50, 200]"
            )
        if not any(v in sw_s.lower() for v in RISK_VERBS):
            res.fail(
                f"{canonical_id}: safety_warning missing risk/action verb "
                f"(need one of: {RISK_VERBS})"
            )
        if ban_context == "adulterant_in_supplements":
            if not ADULTERANT_GUARDRAIL.search(sw_s):
                res.fail(
                    f"{canonical_id}: adulterant_in_supplements entry must contain "
                    f"'in supplement/product/dietary' clinical guardrail in "
                    f"safety_warning — users on prescribed versions must not panic"
                )

    # safety_warning_one_liner contract.
    if swol is None:
        msg = f"{canonical_id}: missing safety_warning_one_liner"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(swol, str):
        res.fail(
            f"{canonical_id}: safety_warning_one_liner must be string, got "
            f"{type(swol).__name__}"
        )
    else:
        swol_s = swol.strip()
        if std_name and swol_s.startswith(f"{std_name} is "):
            res.fail(f"{canonical_id}: safety_warning_one_liner starts with derivation template")
        if not (20 <= len(swol_s) <= 80):
            res.fail(
                f"{canonical_id}: safety_warning_one_liner length {len(swol_s)} "
                f"outside [20, 80]"
            )
        if not swol_s.endswith((".", "!")):
            res.fail(f"{canonical_id}: safety_warning_one_liner must end with . or !")
        if ";" in swol_s:
            res.fail(f"{canonical_id}: safety_warning_one_liner contains semicolon")

    # warning_message must not return (Flutter strip-list from Sprint 27.6).
    if "warning_message" in entry:
        res.fail(
            f"{canonical_id}: legacy derived 'warning_message' field present — "
            f"Flutter removed this in Sprint 27.6 (see HANDOFF_PIPELINE_SAFETY_DATA.md)"
        )

    return res


# ---------------------------------------------------------------------------
# ingredient_interaction_rules.json per-sub-rule validator
# ---------------------------------------------------------------------------


def validate_interaction_sub_rule(
    rule_id: str,
    sub_rule_kind: str,  # "condition_rule" | "drug_class_rule" |
                         # "pregnancy_lactation"
    sub_rule: Dict[str, Any],
    severity: str,
    strict: bool = False,
) -> ValidationResult:
    """Apply authored-copy contract rules to a single sub-rule."""
    res = ValidationResult()
    ah = sub_rule.get("alert_headline")
    ab = sub_rule.get("alert_body")
    info = sub_rule.get("informational_note")
    tag = f"{rule_id}/{sub_rule_kind}"

    sev_lower = (severity or "").strip().lower()
    is_severe = sev_lower in ("avoid", "contraindicated")

    # alert_headline contract.
    if ah is None:
        msg = f"{tag}: missing alert_headline"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(ah, str):
        res.fail(f"{tag}: alert_headline must be string")
    else:
        s = ah.strip()
        if not (20 <= len(s) <= 60):
            res.fail(f"{tag}: alert_headline length {len(s)} outside [20, 60]")
        # No SCREAMING verbs — block the specific alarm words the old
        # derived copy would have produced. Medical acronyms (MAOI, FDA,
        # SSRI, NSAID, CYP3A4, etc.) are legitimate and stay allowed.
        screaming = re.compile(
            r"\b(STOP|AVOID|NEVER|ALWAYS|DANGER|WARNING|URGENT|CRITICAL|"
            r"DO NOT|DON'T)\b"
        )
        if screaming.search(s):
            res.fail(f"{tag}: alert_headline contains screaming alarm word")
        if s.endswith("!"):
            res.fail(f"{tag}: alert_headline should not end with !")

    # alert_body contract.
    if ab is None:
        msg = f"{tag}: missing alert_body"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(ab, str):
        res.fail(f"{tag}: alert_body must be string")
    else:
        s = ab.strip()
        if not (60 <= len(s) <= 200):
            res.fail(f"{tag}: alert_body length {len(s)} outside [60, 200]")
        if is_severe and not CONDITIONAL_FRAMING.search(s):
            res.fail(
                f"{tag}: alert_body for severity={sev_lower!r} must use "
                f"conditional framing ('if you take', 'talk to', etc.) — "
                f"otherwise it reads as a directive to every user"
            )

    # informational_note contract.
    if info is None:
        # Informational note is only REQUIRED for avoid/contraindicated
        # rules (what a user sees without a profile). Caution/monitor/info
        # rules can omit it and rely on alert_body.
        if is_severe:
            msg = f"{tag}: missing informational_note (required for severity={sev_lower})"
            (res.fail if strict else res.warn)(msg)
    elif not isinstance(info, str):
        res.fail(f"{tag}: informational_note must be string")
    else:
        s = info.strip()
        if not (40 <= len(s) <= 120):
            res.fail(f"{tag}: informational_note length {len(s)} outside [40, 120]")
        if IMPERATIVE_VERBS.search(s):
            res.fail(
                f"{tag}: informational_note contains imperative verb "
                f"(stop/avoid/do not/never/always) — use conditional framing instead"
            )

    return res


def validate_interaction_rule(
    rule: Dict[str, Any],
    strict: bool = False,
) -> ValidationResult:
    """Apply validator to every sub-rule of a single interaction rule."""
    res = ValidationResult()
    rule_id = str(rule.get("id") or "")

    subject_ref = rule.get("subject_ref") or {}
    cid = str(subject_ref.get("canonical_id") or "")
    if cid and cid != cid.lower() and (subject_ref.get("db") or "") not in (
        "banned_recalled_ingredients",
        "harmful_additives",
        "other_ingredients",
    ):
        # Only enforce lowercase on DBs that have converted to lowercase
        # IDs. Legacy uppercase prefixes (BANNED_, ADD_, NHA_, RISK_) stay
        # WARN-only because changing casing would cascade into
        # cross-file references. See Footgun C in the handoff doc.
        msg = f"{rule_id}: subject canonical_id is not lowercase ({cid})"
        res.warn(msg)

    for sub in rule.get("condition_rules") or []:
        if isinstance(sub, dict):
            sev = str(sub.get("severity") or "")
            res.extend(
                validate_interaction_sub_rule(
                    rule_id, "condition_rule", sub, sev, strict
                )
            )
    for sub in rule.get("drug_class_rules") or []:
        if isinstance(sub, dict):
            sev = str(sub.get("severity") or "")
            res.extend(
                validate_interaction_sub_rule(
                    rule_id, "drug_class_rule", sub, sev, strict
                )
            )

    return res


# ---------------------------------------------------------------------------
# File-level drivers
# ---------------------------------------------------------------------------


def validate_banned_recalled_file(path: Path, strict: bool) -> ValidationResult:
    res = ValidationResult()
    with path.open() as f:
        doc = json.load(f)
    entries = doc.get("ingredients", [])
    for entry in entries:
        if isinstance(entry, dict):
            res.extend(validate_banned_recalled_entry(entry, strict))
    md = doc.get("_metadata", {}) or {}
    if md.get("flutter_top_level_key") != "recalled_ingredients":
        # Footgun D — top-level key stability contract.
        msg = (
            f"{path.name}: _metadata.flutter_top_level_key missing or != "
            f"'recalled_ingredients'"
        )
        (res.fail if strict else res.warn)(msg)
    return res


# ---------------------------------------------------------------------------
# medication_depletions.json per-entry validator (v5.2)
#
# Depletion copy MUST land softer than interaction-rule copy because
# depletion is chronic (onset in months-to-years), not acute. A user
# reading their stack should feel informed, not alarmed.
# ---------------------------------------------------------------------------


ONSET_FRAMING = re.compile(
    r"(over time|long-term|chronic|gradually|may develop|years|months|"
    r"with regular use)",
    re.IGNORECASE,
)

# Acknowledgement copy validates a user who is ALREADY covering the
# depletion. It must read as praise + context, NOT as hedging or a
# continued warning. Block any caution framing.
CAUTION_VERBS_IN_ACK = re.compile(
    r"\b(risk|deficiency|avoid|worry|danger|harm|concern|watch out|urgent)\b",
    re.IGNORECASE,
)

# Monitoring tips must direct gentle attention, not alarm. Soft action
# verbs are required; loud ones are banned.
MONITORING_ACTION_VERBS = re.compile(
    r"\b(check|consider|monitor|watch|ask|discuss|review)\b",
    re.IGNORECASE,
)

MONITORING_LOUD_VERBS = re.compile(
    r"\b(stop|urgent|immediately|avoid|emergency|critical)\b",
    re.IGNORECASE,
)

# Food-sources copy uses *inclusive* framing — "found in", "include",
# "good sources are" — not prescriptive directives. Imperative verbs
# push the user toward dietary change they didn't ask for; inclusive
# phrasing respects autonomy ("here's what's available to you").
FOOD_IMPERATIVE_VERBS = re.compile(
    r"\b(eat|consume|add more|include more|increase|boost|incorporate|"
    r"get more|start taking|cut back)\b",
    re.IGNORECASE,
)

# Food-sources copy is inclusive and positive. It never carries the
# same alarm cues as the other fields, but guardrail it anyway to stay
# consistent with the rest of the depletion-copy tone.
FOOD_SOURCES_BANNED_WORDS = re.compile(
    r"\b(deficiency|deficient|dangerous|severe|urgent|stop|avoid|"
    r"immediately|at risk)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Clinical-UX nocebo rules (schema v5.2.1 — added per Dr. Pham review).
#
# The original validator caught screaming, derivation-template openers, and
# imperative verbs in acknowledgements — the loud tone violations. These
# extras catch the *quiet* ones: numeric alarm priming, absolute claims,
# acute-tense framing, catastrophizing modifiers, and symptom-listing
# nocebo. All apply to layperson-facing depletion copy.
# ---------------------------------------------------------------------------

# Numeric stats in body copy. "30% develop deficiency" is true and sourced,
# but in a 200-character mobile card it reads as "you're at significant
# risk" rather than context. Percentages and ratios belong in the detail
# expander (which reads `clinical_impact`), not the primary body.
NUMERIC_STATS_IN_COPY = re.compile(
    r"(\d+\s*%|\d+\s+in\s+\d+|\b1/\d+\b|one\s+in\s+\w+)",
    re.IGNORECASE,
)

# Absolute causal claims overstate a probabilistic relationship.
# Depletion is chronic and multifactorial; "leads to" / "will cause"
# promises a determinism the evidence doesn't support.
ABSOLUTE_CAUSAL_CLAIMS = re.compile(
    r"\b(will cause|always causes?|never causes?|leads to|results in|"
    r"guaranteed to|definitely|certainly will)\b",
    re.IGNORECASE,
)

# Acute-tense framing directly contradicts the chronic nature of
# depletion. "Immediately" in depletion copy is either wrong or
# accidentally alarming.
ACUTE_FRAMING_WORDS = re.compile(
    r"\b(suddenly|immediately|rapidly|quickly|acute|acutely|instantly|"
    r"right away|at once)\b",
    re.IGNORECASE,
)

# Catastrophizing modifiers prime threat response. "Significant" is
# allowed as a severity-tier VALUE in metadata, but banned in user-
# facing copy. Body / headline / tip all avoid these.
CATASTROPHIZING_MODIFIERS = re.compile(
    r"\b(severe|serious|dangerous|major|significant|critical|substantial|"
    r"devastating|alarming|worrying)\b",
    re.IGNORECASE,
)

# Known symptom vocabulary — listing too many primes users to feel
# them (nocebo). Cap at 2 per body. Expand this list as authoring
# surfaces new symptom terms.
_SYMPTOM_WORDS_PATTERN = (
    r"fatigue|tingling|numbness|cramps?|pain|weakness|nausea|dizziness|"
    r"headache|anemia|neuropathy|bleeding|palpitations?|arrhythmia|"
    r"confusion|insomnia|anxiety|irritability|tremor|tremors|sweating|"
    r"shortness of breath|chest pain|heart palpitations"
)
SYMPTOM_WORD_RE = re.compile(rf"\b({_SYMPTOM_WORDS_PATTERN})\b", re.IGNORECASE)

# Sentence counter — ≤2 is ideal for mobile; 3 is tolerable; 4+ buries
# the lede. Split on `.` / `?` / `!` followed by whitespace or EOS.
_SENTENCE_SPLIT_RE = re.compile(r"[.?!]+(?:\s|$)")


def _depletion_nocebo_checks(
    field_name: str,
    text: str,
    dep_id: str,
    res: "ValidationResult",
    *,
    is_body: bool = False,
) -> None:
    """Apply the v5.2.1 clinical-UX nocebo rules to a single authored
    field. FAIL on hard violations, WARN on style violations.

    [is_body] triggers the body-only checks (sentence cap, symptom-
    count, numerics) which are meaningless on a 20-60 char headline.
    """
    if ACUTE_FRAMING_WORDS.search(text):
        res.fail(
            f"{dep_id}: {field_name} uses acute-tense framing "
            f"(suddenly|immediately|rapidly|quickly|acute|acutely) — "
            f"depletion is chronic, tone must reflect that"
        )
    cat_match = CATASTROPHIZING_MODIFIERS.search(text)
    if cat_match:
        res.warn(
            f"{dep_id}: {field_name} contains catastrophizing modifier "
            f"({cat_match.group(0)!r}) — primes threat response in mobile "
            f"UI; prefer neutral phrasing"
        )
    if is_body:
        if NUMERIC_STATS_IN_COPY.search(text):
            res.fail(
                f"{dep_id}: {field_name} contains numeric stat "
                f"(percentage or ratio) — alarm-forward in mobile UI; "
                f"move stats to clinical_impact (shown in detail expander)"
            )
        if ABSOLUTE_CAUSAL_CLAIMS.search(text):
            res.fail(
                f"{dep_id}: {field_name} uses absolute causal claim "
                f"(will cause|leads to|always|results in) — depletion is "
                f"probabilistic; prefer 'can lower' / 'may reduce'"
            )
        symptom_hits = SYMPTOM_WORD_RE.findall(text)
        if len(symptom_hits) > 2:
            res.warn(
                f"{dep_id}: {field_name} lists {len(symptom_hits)} symptom "
                f"terms ({', '.join(symptom_hits)}) — nocebo risk; cap at "
                f"2 symptoms in user-facing body, move the rest to "
                f"clinical_impact"
            )
        sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
        if len(sentences) > 3:
            res.warn(
                f"{dep_id}: {field_name} has {len(sentences)} sentences — "
                f"mobile UI body scans best at ≤2 sentences; 3+ buries the "
                f"lede"
            )


def validate_depletion_entry(
    entry: Dict[str, Any],
    strict: bool = False,
) -> ValidationResult:
    """Apply v5.2 layperson-copy contract to a single depletion entry."""
    res = ValidationResult()
    dep_id = str(entry.get("id") or "")
    drug_ref = entry.get("drug_ref") or {}
    drug_name = str(drug_ref.get("display_name") or "")
    nutrient = entry.get("depleted_nutrient") or {}
    nutrient_name = str(nutrient.get("standard_name") or "")

    ah = entry.get("alert_headline")
    ab = entry.get("alert_body")
    ack = entry.get("acknowledgement_note")
    tip = entry.get("monitoring_tip_short")

    # alert_headline contract.
    if ah is None:
        msg = f"{dep_id}: missing alert_headline"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(ah, str):
        res.fail(f"{dep_id}: alert_headline must be string")
    else:
        s = ah.strip()
        if not (20 <= len(s) <= 60):
            res.fail(f"{dep_id}: alert_headline length {len(s)} outside [20, 60]")
        # "Depleted by X" framing reads as damage being done to the user.
        if re.match(r"^\s*depleted by\b", s, re.IGNORECASE):
            res.fail(
                f"{dep_id}: alert_headline starts with 'Depleted by …' — "
                f"reads as medication damaging user. Use 'May lower X over "
                f"time' or 'Can affect X long-term' framing."
            )
        screaming = re.compile(
            r"\b(STOP|AVOID|NEVER|ALWAYS|DANGER|WARNING|URGENT|CRITICAL)\b"
        )
        if screaming.search(s):
            res.fail(f"{dep_id}: alert_headline contains screaming alarm word")
        if s.endswith("!"):
            res.fail(f"{dep_id}: alert_headline should not end with !")
        _depletion_nocebo_checks("alert_headline", s, dep_id, res)

    # alert_body contract — must contain onset framing since depletion
    # is chronic. A user who reads this should understand this isn't
    # happening today.
    if ab is None:
        msg = f"{dep_id}: missing alert_body"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(ab, str):
        res.fail(f"{dep_id}: alert_body must be string")
    else:
        s = ab.strip()
        if not (60 <= len(s) <= 200):
            res.fail(f"{dep_id}: alert_body length {len(s)} outside [60, 200]")
        if not ONSET_FRAMING.search(s):
            res.fail(
                f"{dep_id}: alert_body must include onset framing (over "
                f"time, long-term, chronic, gradually, may develop, years, "
                f"months, with regular use) — depletion is chronic, not acute"
            )
        _depletion_nocebo_checks("alert_body", s, dep_id, res, is_body=True)

    # acknowledgement_note contract — shown when user is ALREADY
    # covering. Must NOT sound cautionary.
    if ack is None:
        msg = f"{dep_id}: missing acknowledgement_note"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(ack, str):
        res.fail(f"{dep_id}: acknowledgement_note must be string")
    else:
        s = ack.strip()
        if not (40 <= len(s) <= 120):
            res.fail(
                f"{dep_id}: acknowledgement_note length {len(s)} outside [40, 120]"
            )
        if CAUTION_VERBS_IN_ACK.search(s):
            res.fail(
                f"{dep_id}: acknowledgement_note contains caution verb "
                f"(risk|deficiency|avoid|worry|danger|harm|concern|watch "
                f"out|urgent) — this copy is for users who are already "
                f"covering the depletion; it should validate, not hedge"
            )

    # monitoring_tip_short contract — layperson action, soft voicing.
    if tip is None:
        msg = f"{dep_id}: missing monitoring_tip_short"
        (res.fail if strict else res.warn)(msg)
    elif not isinstance(tip, str):
        res.fail(f"{dep_id}: monitoring_tip_short must be string")
    else:
        s = tip.strip()
        if not (40 <= len(s) <= 120):
            res.fail(
                f"{dep_id}: monitoring_tip_short length {len(s)} outside "
                f"[40, 120]"
            )
        if not MONITORING_ACTION_VERBS.search(s):
            res.fail(
                f"{dep_id}: monitoring_tip_short must contain a soft action "
                f"verb (check|consider|monitor|watch|ask|discuss|review)"
            )
        if MONITORING_LOUD_VERBS.search(s):
            res.fail(
                f"{dep_id}: monitoring_tip_short contains loud verb "
                f"(stop|urgent|immediately|avoid|emergency|critical) — "
                f"depletion is chronic; tone should be calm"
            )
        _depletion_nocebo_checks("monitoring_tip_short", s, dep_id, res)

    # adequacy_threshold — if present, must be a positive number.
    # Dr. Pham picks ONE field (mcg OR mg) based on the nutrient's
    # conventional unit. Setting both creates silent ambiguity — the
    # checker would have to pick one, and either choice might be wrong.
    set_thresholds = []
    for field_name in ("adequacy_threshold_mcg", "adequacy_threshold_mg"):
        val = entry.get(field_name)
        if val is not None:
            if not isinstance(val, (int, float)) or val <= 0:
                res.fail(
                    f"{dep_id}: {field_name} must be a positive number, "
                    f"got {val!r}"
                )
            else:
                set_thresholds.append(field_name)
    if len(set_thresholds) > 1:
        res.fail(
            f"{dep_id}: both adequacy_threshold_mcg AND "
            f"adequacy_threshold_mg are set — pick ONE based on the "
            f"nutrient's conventional unit (B12 → mcg, magnesium → mg, "
            f"vitamin D → mcg using the mass equivalent of IU)"
        )

    # food_sources_short — optional, inclusive "here's what's available"
    # framing. NOT required because some depletions (metformin/B12,
    # PPI/B12, statin/CoQ10) are absorption-blocked and food isn't a
    # meaningful substitute — Dr. Pham's clinical judgment. Entries may
    # either omit the field entirely OR author it with the absorption-
    # blocked hint pattern.
    fs = entry.get("food_sources_short")
    if fs is not None:
        if not isinstance(fs, str):
            res.fail(f"{dep_id}: food_sources_short must be string")
        else:
            s = fs.strip()
            if not (40 <= len(s) <= 160):
                # 160 upper bound (vs 120 on tip) — food lists naturally
                # run longer, and the absorption-blocked hint needs
                # room to explain.
                res.fail(
                    f"{dep_id}: food_sources_short length {len(s)} outside "
                    f"[40, 160]"
                )
            if FOOD_IMPERATIVE_VERBS.search(s):
                res.warn(
                    f"{dep_id}: food_sources_short uses imperative framing "
                    f"(eat/consume/increase/etc.) — prefer inclusive "
                    f"phrasing like 'Food sources include...', 'Found in...', "
                    f"'Good sources are...'"
                )
            if FOOD_SOURCES_BANNED_WORDS.search(s):
                res.fail(
                    f"{dep_id}: food_sources_short contains alarm word "
                    f"(deficiency|dangerous|severe|urgent|stop|avoid|"
                    f"at risk) — this field is inclusive/positive only"
                )

    return res


def validate_depletions_file(path: Path, strict: bool) -> ValidationResult:
    res = ValidationResult()
    with path.open() as f:
        doc = json.load(f)
    for entry in doc.get("depletions", []):
        if isinstance(entry, dict):
            res.extend(validate_depletion_entry(entry, strict))
    md = doc.get("_metadata", {}) or {}
    if md.get("flutter_top_level_key") != "depletions":
        msg = (
            f"{path.name}: _metadata.flutter_top_level_key missing or != "
            f"'depletions'"
        )
        (res.fail if strict else res.warn)(msg)
    return res


def validate_interaction_rules_file(path: Path, strict: bool) -> ValidationResult:
    res = ValidationResult()
    with path.open() as f:
        doc = json.load(f)
    rules = doc.get("interaction_rules", []) or []
    for rule in rules:
        if isinstance(rule, dict):
            res.extend(validate_interaction_rule(rule, strict))
    md = doc.get("_metadata", {}) or {}
    if md.get("flutter_top_level_key") != "interaction_rules":
        msg = (
            f"{path.name}: _metadata.flutter_top_level_key missing or != "
            f"'interaction_rules'"
        )
        (res.fail if strict else res.warn)(msg)
    return res


# ---------------------------------------------------------------------------
# Canonical-id lowercase invariant across all bundled data files
# ---------------------------------------------------------------------------


BUNDLED_CANONICAL_ID_PATHS: List[Tuple[str, str, str]] = [
    # (filename, list_key, id_field) — files where canonical_id MUST be
    # lowercase.
    ("ingredient_quality_map.json", "ingredient_quality_map", "canonical_id"),
    ("synergy_cluster.json", "synergy_clusters", "cluster_id"),
    ("harmful_additives.json", "harmful_additives", "canonical_id"),
    ("allergens.json", "allergens", "canonical_id"),
]


def validate_canonical_id_lowercase(strict: bool) -> ValidationResult:
    res = ValidationResult()
    for fname, list_key, id_field in BUNDLED_CANONICAL_ID_PATHS:
        p = DATA_DIR / fname
        if not p.exists():
            continue
        with p.open() as f:
            doc = json.load(f)
        entries = doc.get(list_key, []) or []
        for e in entries:
            if not isinstance(e, dict):
                continue
            cid = str(e.get(id_field) or "")
            if cid and cid != cid.lower():
                msg = f"{fname}: {id_field}={cid!r} is not lowercase"
                (res.fail if strict else res.warn)(msg)
            # whitespace check
            if cid and cid != cid.strip() or (cid and " " in cid):
                res.fail(f"{fname}: {id_field}={cid!r} contains whitespace")
    return res


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--banned-recalled-only", action="store_true")
    ap.add_argument("--interaction-rules-only", action="store_true")
    ap.add_argument("--depletions-only", action="store_true")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing authored fields and lowercase-invariant warnings "
             "as errors (release-gate mode).",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors, suppress warnings.",
    )
    args = ap.parse_args(argv)

    total = ValidationResult()
    did_run_any = False
    any_single_flag = (
        args.banned_recalled_only
        or args.interaction_rules_only
        or args.depletions_only
    )

    if not any_single_flag or args.banned_recalled_only:
        p = DATA_DIR / "banned_recalled_ingredients.json"
        if p.exists():
            total.extend(validate_banned_recalled_file(p, args.strict))
            did_run_any = True

    if not any_single_flag or args.interaction_rules_only:
        p = DATA_DIR / "ingredient_interaction_rules.json"
        if p.exists():
            total.extend(validate_interaction_rules_file(p, args.strict))
            did_run_any = True

    if not any_single_flag or args.depletions_only:
        p = DATA_DIR / "medication_depletions.json"
        if p.exists():
            total.extend(validate_depletions_file(p, args.strict))
            did_run_any = True

    # Cross-file canonical_id lowercase invariant.
    if not any_single_flag:
        total.extend(validate_canonical_id_lowercase(args.strict))

    if not did_run_any:
        print("validate_safety_copy: no input files found", file=sys.stderr)
        return 2

    if total.warnings and not args.quiet:
        print(f"\nWARNINGS ({len(total.warnings)}):", file=sys.stderr)
        for w in total.warnings[:200]:
            print(f"  WARN: {w}", file=sys.stderr)
        if len(total.warnings) > 200:
            print(f"  ... and {len(total.warnings) - 200} more", file=sys.stderr)

    if total.errors:
        print(f"\nERRORS ({len(total.errors)}):", file=sys.stderr)
        for e in total.errors:
            print(f"  FAIL: {e}", file=sys.stderr)
        print(
            f"\n{'RELEASE-STRICT' if args.strict else 'AUTHORING'} "
            f"mode: FAILED with {len(total.errors)} errors.",
            file=sys.stderr,
        )
        return 1

    mode = "strict" if args.strict else "authoring"
    print(f"validate_safety_copy: OK ({mode} mode, {len(total.warnings)} warnings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
