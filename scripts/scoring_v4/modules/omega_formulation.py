"""v4 Omega Formulation dimension — P1.6.1.

Scores omega/fish-oil formulation quality against the 25-point rubric in
SCORING_V4_PROPOSAL §9 + scripts/data/omega_rubric.json.

Components:
    form_tier            — IQM-owned parent-relative form quality, scaled to
                           the omega component's 8-point allocation. The name
                           stays stable for breakdown consumers; the old
                           omega-only TG/rTG/PL/EE point table is retired.
    source_disclosed     — RETIRED 2026-09-18 (0 points). Naming the marine
                           source is a disclosure fact; Transparency scores it.
    premium_form_a2_carry — RETIRED 2026-09-18 (0 points). It paid a second
                           time for the molecular form form_tier already scores.
    epa_dha_concentration — EPA+DHA / parent omega oil mass when both are
                           disclosed. +0..4.
    sustainability_cert  — Friend of the Sea or MSC verified by rules_db
                           (score_eligible=True in
                           certification_data.evidence_based). 0 points since
                           quality_score 1.2.0: a consumer attribute recorded in
                           metadata (sustainability_cert_program), not a
                           formulation-quality signal.

Maximum reachable score with current sub-components: 8 + 4 = 12/25.
The 2-point headroom is intentional and reserved for future lot-level purity
signals. Per Sean's 'do not invent fields' rule, concentration credit requires
label-disclosed parent omega oil mass and EPA/DHA mass.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). v3's A2 premium-form carry was retired here on
2026-09-18: it re-paid for the molecular form that form_tier already scores.

Conservative discipline: form quality is credited only from mapped IQM rows.
The label-text detector remains explanatory metadata for Transparency and
reason copy; it cannot override or manufacture an enriched form rating.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from normalization import omega_molecular_form_disclosures
from scoring_v4.modules.generic_formulation import shared_formulation_penalty_detail
from scoring_v4.modules.generic_helpers import bio_score_of, get_active_ingredients
from scoring_input_contract import epa_dha_amounts_per_serving, role_driver_canonicals
from scoring_reference_resolver import parent_relative_form_quality


PHASE_MARKER = "P1.6.1_omega_formulation"
from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "omega")["omega"]


CAP_FORMULATION = _FVM["cap_formulation"]
BIO_SCORE_MAX = 15.0


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
    # Krill oil names its phospholipid-bound carrier by identity. This remains
    # explanatory metadata; IQM owns the actual quality value. Preserve the
    # existing precedence for a mixed krill + triglyceride label.
    if any(re.search(r"\bkrill(?:\s+oil)?\b", surface, re.IGNORECASE) for surface in surfaces):
        return "pl"

    tokens = omega_molecular_form_disclosures(surfaces)
    if tokens:
        token = tokens[0]
        return {
            "phospholipid": "pl",
            "re-esterified triglyceride": "rtg",
            "ethyl ester": "ee",
            "triglyceride": "tg",
        }[token]

    # A mapped IQM row can prove molecular form even when the original label
    # surface is unavailable to a scorer-only replay. This is presentation
    # metadata only; quality itself is calculated from the same IQM row below.
    for row in get_active_ingredients(product):
        if not isinstance(row, dict) or row.get("mapped") is False:
            continue
        form = str(row.get("matched_form") or row.get("form_id") or "").lower()
        if "phospholipid" in form or "phosphatidyl" in form:
            return "pl"
        if "re-esterified" in form or "reesterified" in form or "rtg" in form:
            return "rtg"
        if "ethyl ester" in form:
            return "ee"
        if "triglyceride" in form and "unspecified" not in form:
            return "tg"
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
    name/ingredient text. Used to keep direct calls on empty/non-omega inputs
    from emitting an omega form component."""
    if _source_disclosed(product):
        return True
    for ing in get_active_ingredients(product):
        if not isinstance(ing, dict):
            continue
        canon = str(ing.get("canonical_id") or "").strip().lower()
        if canon in _OMEGA_INGREDIENT_CANONICALS:
            return True
    return False


def _score_iqm_form_quality(product: Dict[str, Any], cap: float) -> Dict[str, Any]:
    """Score molecular-form quality from enriched IQM rows only.

    Parent-oil rows are the most specific owner when present (for example,
    ``krill_oil`` or ``fish_oil``). Otherwise EPA/DHA rows carry the form.
    When several qualifying rows remain and their proportions are unknown, the
    weakest reviewed form wins, matching the shared multi-form policy.
    """
    drivers = role_driver_canonicals("omega")
    parent_ids = drivers - {"epa", "dha", "epa_dha"}
    candidates: List[Dict[str, Any]] = []
    for row in get_active_ingredients(product):
        if not isinstance(row, dict) or row.get("mapped") is False:
            continue
        canonical = str(row.get("canonical_id") or "").strip().lower()
        if canonical not in drivers:
            continue
        raw = bio_score_of(row)
        relative = parent_relative_form_quality(canonical, raw)
        if relative is None:
            continue
        candidates.append({
            "canonical_id": canonical,
            "matched_form": row.get("matched_form"),
            "raw_bio_score": round(float(raw), 4),
            "parent_relative_quality": round(float(relative), 4),
        })

    parent_rows = [row for row in candidates if row["canonical_id"] in parent_ids]
    selected = parent_rows or candidates
    if not selected:
        return {"score": 0.0, "status": "iqm_form_quality_unavailable", "rows": []}

    quality = min(row["parent_relative_quality"] for row in selected)
    return {
        "score": round(quality / BIO_SCORE_MAX * cap, 4),
        "status": "scored_from_iqm_parent_rows" if parent_rows else "scored_from_iqm_epa_dha_rows",
        "quality_0_15": round(quality, 4),
        "rows": selected,
    }


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
    # EPA+DHA comes from the one omega amount owner that Dose and Evidence
    # read, so the concentration numerator can never count a row they refuse.
    epa, dha, combined = epa_dha_amounts_per_serving(product)
    oil = 0.0
    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        mg = _row_mg(row)
        if mg is not None and _is_parent_oil_row(row):
            oil += mg

    return {
        "epa_dha_mg": max(epa + dha, combined),
        "oil_mg": oil,
    }


def _total_fat_upper_bound_mg(product: Dict[str, Any]) -> Optional[float]:
    """Largest oil mass the declared Total Fat allows.

    Many omega labels print EPA/DHA and Total Fat but no oil mass. FDA rounds
    Total Fat to the nearest 0.5 g up to 5 g and to the nearest 1 g above
    (21 CFR 101.9(c)(2)), so the true fat is below the declared value plus half
    an increment. Using that bound can only understate concentration.
    """
    total_fat = _safe_dict(_safe_dict(product.get("nutritionalInfo")).get("totalFat"))
    declared_mg = _to_mg(total_fat.get("amount"), total_fat.get("unit"))
    if declared_mg is None:
        return None
    # A declared 5 g may be a rounded 5.49 g, so 5 g takes the 1 g bound.
    return declared_mg + (250.0 if declared_mg < 5000.0 else 500.0)


def _score_epa_dha_concentration(product: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    masses = _epa_dha_and_oil_mass_mg(product)
    epa_dha_mg = masses["epa_dha_mg"]
    oil_mg = masses["oil_mg"]
    oil_mass_source = "label_oil_row"
    if oil_mg <= 0:
        fat_bound_mg = _total_fat_upper_bound_mg(product)
        if fat_bound_mg is not None:
            oil_mg = fat_bound_mg
            oil_mass_source = "total_fat_rounding_upper_bound"
    payload: Dict[str, Any] = {
        "score": 0.0,
        "epa_dha_mg": round(epa_dha_mg, 4),
        "oil_mg": round(oil_mg, 4),
        "oil_mass_source": oil_mass_source,
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
    form_quality_cap = float(_safe_dict(form_cfg.get("form_quality")).get("cap", 8.0))
    sustainability_pts = float(form_cfg["sustainability_cert"]["score"])
    concentration_cfg = _safe_dict(form_cfg.get("epa_dha_concentration"))

    form_detected = _detect_form(product)
    has_omega = _has_omega_signal(product)
    form_quality = _score_iqm_form_quality(product, form_quality_cap)

    components: Dict[str, float] = {}
    if has_omega and form_quality["score"] > 0:
        components["form_tier"] = form_quality["score"]

    # Source disclosure and the premium-form carry were retired 2026-09-18.
    # Naming the marine source is a disclosure fact that Transparency scores,
    # and the carry paid a second time for the molecular form the tier above
    # already scores. Detection stays for the metadata that explains the label.
    concentration = _score_epa_dha_concentration(product, concentration_cfg)
    if concentration["score"] > 0:
        components["epa_dha_concentration"] = concentration["score"]

    sustainability_match = _sustainability_cert_verified(product)
    if sustainability_match and sustainability_pts > 0:
        components["sustainability_cert"] = sustainability_pts

    shared_penalties = shared_formulation_penalty_detail(product)
    penalties = dict(shared_penalties["penalties"])
    penalty_magnitude = sum(abs(float(value or 0.0)) for value in penalties.values())

    raw_score = sum(components.values())
    pre_penalty_score = raw_score
    score = max(0.0, min(CAP_FORMULATION, raw_score - penalty_magnitude))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "pre_penalty_score": round(pre_penalty_score, 4),
        "cap_applied": raw_score > CAP_FORMULATION,
        "form_detected": form_detected,
        "form_quality_source": "ingredient_quality_map",
        "iqm_form_quality": form_quality,
        "source_disclosed": _source_disclosed(product),
        "epa_dha_concentration": concentration,
        "sustainability_cert_program": sustainability_match,
        "max_reachable_in_p161": 12.0,
        "_max_reachable_note": (
            "Current sub-components sum to 12/25 maximum: IQM molecular form 8 + EPA/DHA "
            "concentration 4. Source disclosure and the premium-form carry were retired "
            "2026-09-18 (Transparency owns disclosure); sustainability certification is an "
            "attribute worth 0 points. Do not interpret a 12/25 score as a cap-applied event."
        ),
    }
    metadata.update(shared_penalties["metadata"])

    return {
        "score": round(score, 2),
        "max": CAP_FORMULATION,
        "components": components,
        "penalties": penalties,
        "metadata": metadata,
    }
