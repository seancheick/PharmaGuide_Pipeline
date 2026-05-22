"""v4 Omega Formulation dimension — P1.6.1.

Scores omega/fish-oil formulation quality against the 25-point rubric in
SCORING_V4_PROPOSAL §9 + scripts/data/omega_rubric.json.

Components:
    form_tier            — molecular form (TG 8 / PL 7 / rTG 6 / EE 4 /
                           undefined 2). Requires EXPLICIT label disclosure.
    source_disclosed     — marine source named (fish / krill / algae /
                           cod liver / specific species). +4.
    premium_form_a2_carry — only awarded when form_tier != undefined.
                           Carries v3's A2 premium-delivery credit forward
                           when EPA/DHA + molecular form are both labeled. +5.
    sustainability_cert  — Friend of the Sea or MSC verified by rules_db
                           (score_eligible=True in
                           certification_data.evidence_based). +4.

Maximum reachable score with current sub-components: 8 + 4 + 5 + 4 = 21/25.
The 4-point headroom is intentional and reserved for a future concentration/
purity sub-component when reliable label signals are available
(P1.6.7+ TBD). Per Sean's 'do not invent fields' rule, we don't fabricate
concentration credit from inferred fish-oil-mass ratios when labels are silent.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). v3's A2 premium-form logic is independently
reimplemented here in policy terms (form disclosed → +5 carryforward).

Conservative discipline: form is credited ONLY when the label or
ingredient panel explicitly says "triglyceride", "ethyl ester",
"phospholipid", "re-esterified", or names a phospholipid-form source
like krill. Bare "fish oil" does NOT imply TG — many commodity fish oils
are sold as natural TG but processing is opaque without label disclosure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from scoring_v4.modules.generic_helpers import get_active_ingredients


REPO_ROOT = Path(__file__).resolve().parents[3]
RUBRIC_PATH = REPO_ROOT / "scripts" / "data" / "omega_rubric.json"


PHASE_MARKER = "P1.6.1_omega_formulation"
CAP_FORMULATION = 25.0


# Form-detection regex — order matters (most-specific first). Each
# pattern uses word boundaries to avoid false-positives (e.g. "triglyceride"
# matches but "diglyceride" does not).
#
# Why "krill" maps to PL: krill omega-3 is naturally bound as
# phosphatidylcholine (phospholipid form). This is well-established
# clinical biochemistry — krill = PL by default unless the label says
# otherwise. Other sources (fish/algae/cod liver) require explicit
# "triglyceride"/"ester"/"phospholipid" disclosure to credit form.
_FORM_PATTERNS = [
    ("pl", re.compile(
        r"\b(phospholipid[s]?|phosphatidyl|krill\s+oil|krill)\b",
        re.IGNORECASE,
    )),
    ("rtg", re.compile(
        r"\b(re[\s-]?esterified|reesterified|rtg|r-tg)\b",
        re.IGNORECASE,
    )),
    ("ee", re.compile(
        r"\b(ethyl\s+ester[s]?|fatty\s+acid\s+ethyl\s+ester[s]?|"
        r"ee\s+form)\b",
        re.IGNORECASE,
    )),
    ("tg", re.compile(
        r"\b(natural[\s-]?triglyceride[s]?|triglyceride[s]?|tg\s+form|"
        r"triglyceride\s+form)\b",
        re.IGNORECASE,
    )),
]


# Carrier MCT wording is not an omega-3 molecular-form disclosure. These
# phrases appear in real mixed fatty-acid products and must not unlock TG
# form credit or the premium-form carry.
_MCT_TRIGLYCERIDE_PATTERN = re.compile(
    r"\b(?:mct|medium[\s-]?chain|middle[\s-]?chain|caprylic|capric|c8|c10|"
    r"coconut)\b.{0,48}\btriglyceride[s]?\b|"
    r"\btriglyceride[s]?\b.{0,48}\b(?:mct|medium[\s-]?chain|"
    r"middle[\s-]?chain|caprylic|capric|c8|c10|coconut)\b",
    re.IGNORECASE,
)


# Source-detection regex — any marine source keyword counts.
_SOURCE_PATTERN = re.compile(
    r"\b(fish\s+oil|fish\s+body\s+oil|cod\s+liver|krill|squid|calanus|"
    r"salmon|sardine|anchovy|mackerel|menhaden|herring|tuna|"
    r"algae|algal|microalgae|deep\s+sea\s+fish)\b",
    re.IGNORECASE,
)


# Sustainability cert programs the rubric recognizes. Matched
# case-insensitively against rules_db evidence display_name.
_SUSTAINABILITY_PROGRAMS = ("friend of the sea", "msc", "marine stewardship council")


def _load_rubric() -> Dict[str, Any]:
    """Load omega_rubric.json. Loaded fresh per call so tests that monkey-patch
    the config file see the change. In production this is a few-µs JSON parse
    per scored product; negligible vs the rest of the pipeline."""
    return json.loads(RUBRIC_PATH.read_text())


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _gather_text_surfaces(product: Dict[str, Any]) -> List[str]:
    """Return separate labeled-text surfaces where form/source keywords
    may appear. Keeping surfaces separate lets form detection ignore
    MCT-carrier rows without suppressing a valid standalone omega form
    row like Sports Research's 'Triglycerides'."""
    parts: List[str] = []
    for key in ("product_name", "fullName", "brand_name", "brandName", "bundleName"):
        v = product.get(key)
        if v:
            parts.append(str(v))

    for ing in get_active_ingredients(product):
        if not isinstance(ing, dict):
            continue
        for ing_key in ("name", "standard_name", "ingredient_name", "standardName"):
            v = ing.get(ing_key)
            if v:
                parts.append(str(v))
    return parts


def _gather_text_corpus(product: Dict[str, Any]) -> str:
    """Concatenate label surfaces for broad source detection."""
    parts = _gather_text_surfaces(product)
    return " ".join(parts)


def _detect_form(product: Dict[str, Any]) -> str:
    """Return one of {pl, rtg, ee, tg, undefined}.

    Order is most-specific first — PL > rTG > EE > TG. A product that
    matches multiple patterns (e.g. krill oil packaged as 'triglycerides')
    takes the more-specific PL form. This is rare but possible with
    multi-ingredient stacks.
    """
    surfaces = _gather_text_surfaces(product)
    for form_label, pattern in _FORM_PATTERNS:
        for surface in surfaces:
            if form_label == "tg" and _MCT_TRIGLYCERIDE_PATTERN.search(surface):
                continue
            if pattern.search(surface):
                return form_label
    return "undefined"


def _source_disclosed(product: Dict[str, Any]) -> bool:
    """True when the product name or ingredient panel discloses a marine
    source (fish, krill, algae, cod liver, specific species)."""
    haystack = _gather_text_corpus(product)
    return bool(_SOURCE_PATTERN.search(haystack))


_OMEGA_INGREDIENT_CANONICALS = {"epa", "dha", "epa_dha", "fish_oil"}


def _has_omega_signal(product: Dict[str, Any]) -> bool:
    """True when the product carries any omega signal — EPA/DHA/fish_oil
    canonical in the ingredient panel, or a marine source keyword in the
    name/ingredient text. Used to gate the form_tier=undefined baseline
    (2 pts) so empty / non-omega products score 0 instead of inheriting
    the omega-class undefined-form credit."""
    if _source_disclosed(product):
        return True
    for ing in get_active_ingredients(product):
        if not isinstance(ing, dict):
            continue
        canon = str(ing.get("canonical_id") or "").strip().lower()
        if canon in _OMEGA_INGREDIENT_CANONICALS:
            return True
    return False


def _sustainability_cert_verified(product: Dict[str, Any]) -> Optional[str]:
    """Return the matched sustainability program display_name if the
    product has a rules_db-verified Friend of the Sea / MSC cert.
    None if no qualifying sustainability cert is present.

    Per omega_rubric.formulation.sustainability_cert.eligibility =
    "rules_db_verified": the cert must appear in
    certification_data.evidence_based.third_party_programs with
    score_eligible == True. Bare label-text claims at
    verified_cert_programs[].scope=claimed_only do NOT qualify — that
    path is the same manufacturer-overcredit hole P0.1b closed off.
    """
    cert_data = _safe_dict(product.get("certification_data"))
    evidence = _safe_dict(cert_data.get("evidence_based"))
    programs = _safe_list(evidence.get("third_party_programs"))

    for entry in programs:
        if not isinstance(entry, dict):
            continue
        if not entry.get("score_eligible"):
            continue
        display_name = str(entry.get("display_name") or "").strip().lower()
        # Match either the display_name or a derived rule_id token
        if display_name in _SUSTAINABILITY_PROGRAMS:
            return entry.get("display_name")
        rule_id = str(entry.get("rule_id") or "").strip().upper()
        if rule_id in {"CERT_FRIEND_OF_THE_SEA", "CERT_MSC"}:
            return entry.get("display_name") or rule_id
    return None


def score_formulation(product: Any) -> Dict[str, Any]:
    """Score omega-class Formulation dimension.

    P1.6.1 implementation. Returns a payload mirroring the
    probiotic/generic Formulation contract so the orchestrator wires
    it identically.

    Args:
        product: Enriched product dict.

    Returns:
        {
            "score": float (0..CAP_FORMULATION),
            "max": CAP_FORMULATION,
            "components": {sub_name: pts},
            "penalties": {},  # No formulation-side penalties in P1.6
            "metadata": {phase, form_detected, raw_score, cap_applied, ...},
        }
    """
    if not isinstance(product, dict):
        product = {}

    rubric = _load_rubric()
    form_cfg = rubric["formulation"]
    form_tier_table = form_cfg["form_tier"]
    source_pts = float(form_cfg["source_disclosed"]["score"])
    premium_pts = float(form_cfg["premium_form_a2_carry"]["score"])
    sustainability_pts = float(form_cfg["sustainability_cert"]["score"])

    form_detected = _detect_form(product)
    has_omega = _has_omega_signal(product)
    form_score = float(form_tier_table.get(form_detected, form_tier_table["undefined"]))

    components: Dict[str, float] = {}
    # form_tier=undefined (2 pts) is the "labeled the active, not the form"
    # baseline — only awarded when the product actually carries an omega
    # signal. A truly empty / non-omega product scores 0 here. Real-world
    # impact: zero (completeness gate already rejects non-omega input);
    # this branch protects audit/test surfaces that call score_formulation
    # directly.
    if form_detected != "undefined" or has_omega:
        components["form_tier"] = form_score

    if _source_disclosed(product):
        components["source_disclosed"] = source_pts

    # Premium-form A2 carryforward: only when the molecular form is
    # explicitly labeled (form_detected != "undefined"). This is the
    # transparency-rewarding component — labeling EPA/DHA WITH the
    # molecular form lets the scorer credit bioavailability tier,
    # which the consumer can compare on shelf.
    if form_detected != "undefined":
        components["premium_form_a2_carry"] = premium_pts

    sustainability_match = _sustainability_cert_verified(product)
    if sustainability_match:
        components["sustainability_cert"] = sustainability_pts

    raw_score = sum(components.values())
    score = max(0.0, min(CAP_FORMULATION, raw_score))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "cap_applied": raw_score > CAP_FORMULATION,
        "form_detected": form_detected,
        "source_disclosed": "source_disclosed" in components,
        "sustainability_cert_program": sustainability_match,
        "max_reachable_in_p161": 21.0,
        "_max_reachable_note": (
            "Current sub-components sum to 21/25 maximum. 4-point headroom "
            "is reserved for a future concentration/purity sub-component "
            "(P1.6.7+). Do not interpret a 21/25 score as a cap-applied event."
        ),
    }

    return {
        "score": round(score, 2),
        "max": CAP_FORMULATION,
        "components": components,
        "penalties": {},
        "metadata": metadata,
    }
