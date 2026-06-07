"""v4 Omega Formulation dimension — P1.6.1.

Scores omega/fish-oil formulation quality against the 25-point rubric in
SCORING_V4_PROPOSAL §9 + scripts/data/omega_rubric.json.

Components:
    form_tier            — molecular form (TG 8 / rTG 8 / PL 7 / EE 4 /
                           undefined 2). Requires EXPLICIT label disclosure.
    source_disclosed     — marine source named (fish / krill / algae /
                           cod liver / specific species). +4.
    premium_form_a2_carry — only awarded when form_tier != undefined.
                           Carries v3's A2 premium-delivery credit forward
                           when EPA/DHA + molecular form are both labeled. +5.
    epa_dha_concentration — EPA+DHA / parent omega oil mass when both are
                           disclosed. +0..4.
    sustainability_cert  — Friend of the Sea or MSC verified by rules_db
                           (score_eligible=True in
                           certification_data.evidence_based). +2.

Maximum reachable score with current sub-components: 8 + 4 + 5 + 4 + 2 = 23/25.
The 2-point headroom is intentional and reserved for future lot-level purity
signals. Per Sean's 'do not invent fields' rule, concentration credit requires
label-disclosed parent omega oil mass and EPA/DHA mass.

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

import re
from typing import Any, Dict, List, Optional

from scoring_v4.modules.generic_helpers import get_active_ingredients


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

_TRIGLYCERIDE_HEALTH_CLAIM_PATTERN = re.compile(
    r"\b(?:healthy|normal|blood|serum|plasma|support(?:s|ing)?|maintain(?:s|ing)?|"
    r"already\s+within)\b.{0,64}\btriglyceride[s]?\s+level[s]?\b|"
    r"\btriglyceride[s]?\s+level[s]?\b.{0,64}\b(?:healthy|normal|range|blood|serum|"
    r"plasma|support(?:s|ing)?|maintain(?:s|ing)?|already\s+within)\b",
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
_QUALITY_PROGRAM_KEYWORDS = (
    "ifos",
    "nsf",
    "usp",
    "informed",
    "consumerlab",
    "eurofins",
    "bscg",
)
DATA_LIMITED_FORM_FLOOR = 19.0
DATA_LIMITED_FORM_MIN_EPA_DHA_MG = 750.0


def _load_rubric() -> Dict[str, Any]:
    """Load omega_rubric.json. Loaded fresh per call so tests that monkey-patch
    the config file see the change. In production this is a few-µs JSON parse
    per scored product; negligible vs the rest of the pipeline."""
    from scoring_v4.config_registry import load_rubric
    return load_rubric("omega")  # Phase 0: shared registry (validated + fingerprinted)


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

    # Label text and structured statements are real form-disclosure surfaces:
    # gold-standard brands (Nordic Naturals, etc.) state the molecular form there
    # ("All fish oils are in the triglyceride form" / "Superior Triglyceride Form")
    # rather than in the product name or ingredient panel. Each is appended as its
    # OWN surface so the MCT-carrier guard still applies per-surface.
    label_text = product.get("labelText")
    if isinstance(label_text, dict):
        raw = label_text.get("raw")
        if raw:
            parts.append(str(raw))
    elif label_text:
        parts.append(str(label_text))
    for statement in product.get("statements") or []:
        if isinstance(statement, dict):
            note = statement.get("notes") or statement.get("text")
            if note:
                parts.append(str(note))
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
            if form_label == "tg" and _TRIGLYCERIDE_HEALTH_CLAIM_PATTERN.search(surface):
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
_EPA_DHA_CANONICALS = {"epa", "dha", "epa_dha"}
_OIL_MASS_CANONICALS = {"fish_oil"}
_OIL_MASS_NAME_PATTERN = re.compile(
    r"\b(fish\s+oil|fish\s+body\s+oil|cod\s+liver\s+oil|krill\s+oil|"
    r"algae\s+oil|algal\s+oil|microalgae\s+oil|deep\s+sea\s+fish\s+oil|"
    r"oil\s+concentrate|fish\s+oil\s+concentrate)\b",
    re.IGNORECASE,
)
_UNIT_TO_MG: Dict[str, float] = {
    "mg": 1.0,
    "milligram": 1.0,
    "milligrams": 1.0,
    "g": 1000.0,
    "gram": 1000.0,
    "grams": 1000.0,
    "gram(s)": 1000.0,
    "mcg": 0.001,
    "ug": 0.001,
    "µg": 0.001,
    "microgram": 0.001,
    "micrograms": 0.001,
}


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


def _to_mg(quantity: Any, unit: Any) -> Optional[float]:
    try:
        q = float(quantity)
    except (TypeError, ValueError):
        return None
    if q <= 0:
        return None
    factor = _UNIT_TO_MG.get(str(unit or "").strip().lower())
    if factor is None:
        return None
    return q * factor


def _row_mg(row: Dict[str, Any]) -> Optional[float]:
    for qty_key in ("quantity", "amount", "dose", "dosage"):
        mg = _to_mg(row.get(qty_key), row.get("unit") or row.get("dose_unit"))
        if mg is not None:
            return mg
    return None


def _is_parent_oil_row(row: Dict[str, Any]) -> bool:
    canon = str(row.get("canonical_id") or "").strip().lower()
    if canon in _OIL_MASS_CANONICALS:
        return True
    if canon in _EPA_DHA_CANONICALS:
        return False
    text = " ".join(
        str(row.get(key) or "")
        for key in ("name", "standard_name", "ingredient_name", "standardName")
    )
    return bool(_OIL_MASS_NAME_PATTERN.search(text))


def _epa_dha_and_oil_mass_mg(product: Dict[str, Any]) -> Dict[str, float]:
    epa = 0.0
    dha = 0.0
    combined = 0.0
    oil = 0.0

    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        mg = _row_mg(row)
        if mg is None:
            continue
        canon = str(row.get("canonical_id") or "").strip().lower()
        if canon == "epa":
            epa += mg
        elif canon == "dha":
            dha += mg
        elif canon == "epa_dha":
            combined += mg
        elif _is_parent_oil_row(row):
            oil += mg

    return {
        "epa_dha_mg": max(epa + dha, combined),
        "oil_mg": oil,
    }


def _score_epa_dha_concentration(product: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    masses = _epa_dha_and_oil_mass_mg(product)
    epa_dha_mg = masses["epa_dha_mg"]
    oil_mg = masses["oil_mg"]
    payload: Dict[str, Any] = {
        "score": 0.0,
        "epa_dha_mg": round(epa_dha_mg, 4),
        "oil_mg": round(oil_mg, 4),
    }
    if epa_dha_mg <= 0:
        payload["status"] = "missing_epa_dha_mass"
        return payload
    if oil_mg <= 0:
        payload["status"] = "missing_oil_mass"
        return payload

    ratio = epa_dha_mg / oil_mg
    payload["ratio"] = round(ratio, 4)
    bands = _safe_list(cfg.get("score_bands"))
    for band in bands:
        if not isinstance(band, dict):
            continue
        try:
            threshold = float(band.get("min_ratio", 0.0) or 0.0)
            score = float(band.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if ratio >= threshold:
            payload.update({
                "score": score,
                "status": "scored",
                "band": band.get("label"),
            })
            return payload
    payload["status"] = "below_lowest_band"
    return payload


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


def _verified_quality_programs(product: Dict[str, Any]) -> List[str]:
    """Return score-eligible third-party quality programs.

    This intentionally excludes bare claims and sustainability-only programs.
    The data-limited fallback below is for products with verified quality/
    purity evidence, not for commodity fish oil labels that only disclose
    EPA/DHA + source.
    """
    cert_data = _safe_dict(product.get("certification_data"))
    evidence = _safe_dict(cert_data.get("evidence_based"))
    programs: List[str] = []
    for entry in _safe_list(evidence.get("third_party_programs")):
        if not isinstance(entry, dict) or not entry.get("score_eligible"):
            continue
        display = str(entry.get("display_name") or "").strip()
        rule_id = str(entry.get("rule_id") or "").strip()
        haystack = f"{display} {rule_id}".lower()
        if any(token in haystack for token in _QUALITY_PROGRAM_KEYWORDS):
            programs.append(display or rule_id)
    for entry in _safe_list(cert_data.get("verified_cert_programs")):
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "").strip().lower()
        if scope not in {"sku", "product_line"}:
            continue
        if not _verified_cert_brand_matches_product(product, entry):
            continue
        display = str(entry.get("program") or entry.get("display_name") or "").strip()
        rule_id = str(entry.get("rule_id") or "").strip()
        haystack = f"{display} {rule_id}".lower()
        if any(token in haystack for token in _QUALITY_PROGRAM_KEYWORDS):
            programs.append(display or rule_id)
    deduped: List[str] = []
    seen = set()
    for program in programs:
        key = program.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(program)
    return deduped


def _brand_key(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(inc|llc|ltd|co|company|the|registered|trademark|tm|r)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _verified_cert_brand_matches_product(product: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    matched_brand = _brand_key(entry.get("matched_brand"))
    if not matched_brand:
        return True
    product_brands = [
        _brand_key(product.get(key))
        for key in ("brandName", "brand_name", "brand", "manufacturer_name")
        if _brand_key(product.get(key))
    ]
    if not product_brands:
        return False
    return any(
        matched_brand == brand
        or (len(matched_brand) >= 5 and matched_brand in brand)
        or (len(brand) >= 5 and brand in matched_brand)
        for brand in product_brands
    )


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
    concentration_cfg = _safe_dict(form_cfg.get("epa_dha_concentration"))

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

    concentration = _score_epa_dha_concentration(product, concentration_cfg)
    if concentration["score"] > 0:
        components["epa_dha_concentration"] = concentration["score"]

    sustainability_match = _sustainability_cert_verified(product)
    if sustainability_match:
        components["sustainability_cert"] = sustainability_pts

    raw_score = sum(components.values())
    masses = _epa_dha_and_oil_mass_mg(product)
    quality_programs = _verified_quality_programs(product)
    data_limited_form_floor: Dict[str, Any] = {
        "applied": False,
        "floor": DATA_LIMITED_FORM_FLOOR,
        "min_epa_dha_mg": DATA_LIMITED_FORM_MIN_EPA_DHA_MG,
        "epa_dha_mg": round(masses["epa_dha_mg"], 4),
        "quality_programs": quality_programs,
    }
    if (
        form_detected == "undefined"
        and "source_disclosed" in components
        and masses["epa_dha_mg"] >= DATA_LIMITED_FORM_MIN_EPA_DHA_MG
        and quality_programs
        and raw_score < DATA_LIMITED_FORM_FLOOR
    ):
        floor_adjustment = DATA_LIMITED_FORM_FLOOR - raw_score
        components["data_limited_formulation_floor"] = round(floor_adjustment, 4)
        raw_score = sum(components.values())
        data_limited_form_floor["applied"] = True
        data_limited_form_floor["adjustment"] = round(floor_adjustment, 4)

    score = max(0.0, min(CAP_FORMULATION, raw_score))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "cap_applied": raw_score > CAP_FORMULATION,
        "form_detected": form_detected,
        "source_disclosed": "source_disclosed" in components,
        "epa_dha_concentration": concentration,
        "sustainability_cert_program": sustainability_match,
        "data_limited_form_floor_applied": bool(data_limited_form_floor["applied"]),
        "data_limited_form_floor": data_limited_form_floor,
        "max_reachable_in_p161": 23.0,
        "_max_reachable_note": (
            "Current sub-components sum to 23/25 maximum. 2-point headroom "
            "is reserved for future lot-level purity evidence. Do not interpret "
            "a 23/25 score as a cap-applied event."
        ),
    }

    return {
        "score": round(score, 2),
        "max": CAP_FORMULATION,
        "components": components,
        "penalties": {},
        "metadata": metadata,
    }
