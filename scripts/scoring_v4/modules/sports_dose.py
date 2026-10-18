"""v4 sports-module Dose dimension.

Sports actives are evaluated against exercise-nutrition dose bands rather
than the generic RDA/UL proxy used for vitamins and minerals.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
from dataclasses import asdict

from scoring_v4.exposure import row_exposure
from serving_frequency import has_loading_protocol

from scoring_v4.modules.generic_helpers import _norm_text, _safe_list, get_active_ingredients
from scoring_input_contract import classify_ingredient_roles, is_lent_blend_mass, normalize_product_evidence_scope
from scoring_v4.modules.sports_helpers import (
    ALPHA_GPC_CANONICALS,
    ATP_CANONICALS,
    BCAA_AGGREGATE_CANONICALS,
    BETA_ALANINE_CANONICALS,
    BETAINE_CANONICALS,
    CAFFEINE_CANONICALS,
    CITRULLINE_CANONICALS,
    CREATINE_CANONICALS,
    HMB_CANONICALS,
    SPORTS_BAND_CANONICALS,
    SPORTS_PROTEIN_CANONICALS,
    TAURINE_CANONICALS,
    canonical,
    dose_g,
    dose_mg,
    group_bcaa,
    group_eaa,
    primary_sports_identity,
    sports_dosed_rows,
    sports_identity_rows,
    sports_rows,
)


PHASE_MARKER = "P1.7_sports_dose_v1"
METHOD_MARKER = "sports_active_dose_bands_v1"
# Daily basis verified against NIH ODS exercise fact sheet; caffeine is per use.
_DAILY_CANONICALS = CREATINE_CANONICALS | BETA_ALANINE_CANONICALS | HMB_CANONICALS

from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "sports")["sports"]


DIMENSION_CAP = _DM["dimension_cap"]


def score_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(product, dict):
        product = {}

    identity, primary, basis, aggregation, scored = _best_primary_score(product)
    identity, primary, basis = _apply_offlist_dose_floor(product, identity, primary, basis)
    completeness = _score_ratio_or_completeness(product, identity)
    not_evaluable = _not_evaluable_reason(product, primary)
    if (
        primary <= 0
        and identity
        and basis
        and not_evaluable == "no_sports_primary_dose"
        and basis != "no_sports_primary_dose"
    ):
        not_evaluable = basis

    components = {
        "sports_primary_active_dose": round(primary, 4),
        "sports_ratio_or_completeness": round(completeness, 4),
    }
    # Transparency B5 owns blend opacity; a hidden primary amount is recorded
    # as not evaluable here and earns no substitute credit (V4.1 Step 4).
    penalties: Dict[str, float] = {}
    score = _clamp(
        0.0,
        DIMENSION_CAP,
        sum(components.values()) - sum(abs(float(v)) for v in penalties.values()),
    )
    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "method": METHOD_MARKER,
        "primary_identity": identity,
        "dose_basis": basis,
        "dose_aggregation": aggregation,
        "dose_contributions": [{"ingredient": name, "assessment": label, "credit_raw": round(points, 4)}
                               for name, points, label in scored],
        "benchmark_exposures": [
            asdict(row_exposure(product, row, basis="daily" if canonical(row) in _DAILY_CANONICALS else "per_use", unit="g"))
            for row in sports_dosed_rows(product)
            if canonical(row) in _DAILY_CANONICALS | CAFFEINE_CANONICALS
        ],
        "daily_interval_selection": "minimum_directed_use",

    }
    unknown_daily = [e for e in metadata["benchmark_exposures"] if e["benchmark_amount"] is None and e["uncertainty"]]
    if unknown_daily and primary <= 0:
        not_evaluable = unknown_daily[0]["uncertainty"]
    if not_evaluable:
        metadata["not_evaluable_reason"] = not_evaluable
    if not_evaluable == "opaque_primary_sports_blend" and sports_identity_rows(product):
        # Dose V4.1 section 2.3: named sports actives whose amounts the label
        # hides take the shared neutral; Transparency B5 keeps the opacity.
        # With no identified active there is nothing to assess (strict hold).
        from scoring_v4.modules.generic_helpers import archetype_dose_reference, dose_reference_scope, unbenchmarked_dose_credit
        from scoring_v4.modules.sports_helpers import sports_subtype

        with dose_reference_scope(archetype_dose_reference("sports", module_metadata={"sports_subtype": sports_subtype(product)})):
            components["sports_primary_active_dose"] = round(unbenchmarked_dose_credit(), 4)
        metadata["dose_basis"] = "hidden_amount_neutral"
        score = _clamp(0.0, DIMENSION_CAP, sum(components.values()))

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _dominant_disclosed_active_is_offlist(product: Dict[str, Any]) -> bool:
    """True when the product's mass-dominant disclosed active has no sports dose band.

    Such a product (e.g. L-carnitine 1 g + a token BCAA) would otherwise have its
    real primary ignored by the band rubric and crater to a trace accessory.
    When the heaviest amount is a blend total, the primary is an undisclosed
    blend, not an off-list active: the blend is scored on its disclosure and
    no nutrient's RDA adequacy stands in for it (Ravage 2219).
    """
    best_row: Optional[Dict[str, Any]] = None
    best_g = 0.0
    for row in get_active_ingredients(product or {}):
        if not isinstance(row, dict) or is_lent_blend_mass(row):
            continue
        grams = dose_g(row)
        if grams is not None and grams > best_g:
            best_g = grams
            best_row = row
    if best_row is None or (
        _norm_text(best_row.get("evidence_type")) == "blend_anchor_mass"
        and normalize_product_evidence_scope(best_row.get("evidence_scope")) == "blend_level"
    ):
        return False
    return canonical(best_row) not in SPORTS_BAND_CANONICALS


def _apply_offlist_dose_floor(
    product: Dict[str, Any],
    identity: Optional[str],
    primary: float,
    basis: Optional[str],
) -> Tuple[Optional[str], float, Optional[str]]:
    """Coverage-gap floor for sports products whose primary has no sports band.

    Routing a product to sports must not DISCARD a disclosed active the band rubric
    does not recognise. When the mass-dominant disclosed active is off-list, credit
    it via the generic dose-adequacy proxy (the same scorer the generic module uses)
    and take the better of the two. On-list sports actives keep their strict bands,
    so an under-dosed creatine / BCAA is never rescued by this floor.
    """
    if not _dominant_disclosed_active_is_offlist(product):
        return identity, primary, basis
    try:
        from scoring_v4.modules.generic_dose import score_dose as _generic_dose
        from scoring_v4.modules.generic_helpers import archetype_dose_reference, dose_reference_scope
        from scoring_v4.modules.sports_helpers import sports_subtype

        reference = archetype_dose_reference("sports", module_metadata={"sports_subtype": sports_subtype(product)})
        with dose_reference_scope(reference):
            proxy = float((_generic_dose(product) or {}).get("score") or 0.0)
    except Exception:
        proxy = 0.0
    if proxy > primary:
        return None, proxy, "generic_dose_proxy_for_offlist_primary"
    return identity, primary, basis


def _score_primary(product: Dict[str, Any], identity: Optional[str]) -> Tuple[float, Optional[str]]:
    rows = sports_dosed_rows(product)
    if identity == "protein":
        grams = _max_g(rows, SPORTS_PROTEIN_CANONICALS)
        if grams is None:
            return 0.0, "protein_no_dose"
        if grams < 15:
            return 8.0, "protein_under_15_g"
        if grams < 20:
            return 16.0, "protein_15_to_20_g"
        if grams <= 40:
            return 20.0, "protein_20_to_40_g"
        # Dose V4.1 D3: above a studied range adequacy plateaus.
        return 20.0, "protein_above_40_g"

    if identity == "creatine":
        def creatine_band(grams: float) -> Tuple[float, str]:
            if grams < 2:
                return 8.0, "creatine_under_2_g"
            if grams < 3:
                return 16.0, "creatine_2_to_3_g"
            if grams <= 10:
                return 20.0, "creatine_3_to_10_g"
            # DSLD prints a loading phase's servings as the daily maximum. The
            # reviewed NIH ODS loading protocol is ~20 g/day for 5-7 days, so a
            # labelled loading regimen up to 20 g/day earns full credit; anything
            # above it, or without loading directions, keeps the high-dose band.
            if grams <= 20 and has_loading_protocol(product):
                return 20.0, "creatine_loading_protocol_up_to_20_g"
            # Dose V4.1 D3: the label still names the regimen; adequacy plateaus.
            return 20.0, "creatine_above_10_g_no_loading_protocol"

        return _daily_band(product, rows, CREATINE_CANONICALS, creatine_band, "creatine_no_dose")

    if identity == "beta_alanine":
        def beta_alanine_band(grams: float) -> Tuple[float, str]:
            if grams < 2:
                return 8.0, "beta_alanine_under_2_g"
            if grams < 4:
                return 16.0, "beta_alanine_2_to_4_g"
            if grams <= 6:
                return 20.0, "beta_alanine_4_to_6_g"
            return 20.0, "beta_alanine_above_6_g"

        return _daily_band(product, rows, BETA_ALANINE_CANONICALS, beta_alanine_band, "beta_alanine_no_dose")

    if identity == "citrulline":
        row = _first_row(rows, CITRULLINE_CANONICALS)
        grams = dose_g(row or {})
        if grams is None:
            return 0.0, "citrulline_no_dose"
        label = _norm_text((row or {}).get("name") or (row or {}).get("matched_form"))
        malate = "malate" in label
        if malate:
            if grams < 6:
                return _partial(grams, 6.0, 14.0), "citrulline_malate_under_6_g"
            if grams < 8:
                return 14.0, "citrulline_malate_6_to_8_g"
            return 20.0, "citrulline_malate_8_to_12_g"
        if grams < 3:
            return _partial(grams, 3.0, 16.0), "l_citrulline_under_3_g"
        if grams < 6:
            return 16.0, "l_citrulline_3_to_6_g"
        return 20.0, "l_citrulline_6_to_8_g"

    if identity == "hmb":
        def hmb_band(grams: float) -> Tuple[float, str]:
            if grams < 1.5:
                return _partial(grams, 1.5, 8.0), "hmb_under_1_5_g"
            if grams < 3:
                return 16.0, "hmb_1_5_to_3_g"
            if grams <= 6:
                return 20.0, "hmb_3_to_6_g"
            return 20.0, "hmb_above_6_g"

        return _daily_band(product, rows, HMB_CANONICALS, hmb_band, "hmb_no_dose")

    if identity == "bcaa":
        grouped = group_bcaa(rows)
        if not grouped["complete"]:
            # This existing band assesses the disclosed BCAA preparation as
            # a whole, not any individual amino acid. Keep it outside the
            # individual-dose list and never borrow a parent total for it.
            aggregate = _max_g(
                [row for row in sports_identity_rows(product)
                 if not is_lent_blend_mass(row)],
                BCAA_AGGREGATE_CANONICALS,
            )
            if aggregate is None:
                return 0.0, "bcaa_incomplete"
            # Disclosed BCAA aggregate ("BCAA 7 g 2:1:1") with no per-amino split.
            # BCAA reliably aids recovery (CK/soreness) but not performance
            # (PMID 33586928) -> credit as a recovery aid, capped below ergogenics.
            if aggregate < 2:
                return _partial(aggregate, 2.0, 8.0), "bcaa_aggregate_under_2_g"
            if aggregate < 5:
                return 10.0, "bcaa_aggregate_2_to_5_g"
            return 14.0, "bcaa_aggregate_at_least_5_g"
        total = float(grouped["total_g"])
        if total < 3:
            return _partial(total, 3.0, 12.0), "bcaa_under_3_g"
        if total < 5:
            return 12.0, "bcaa_3_to_5_g"
        if _bcaa_ratio_is_close(grouped.get("ratio")):
            return 20.0, "bcaa_at_least_5_g_ratio_complete"
        return 14.0, "bcaa_at_least_5_g_ratio_incomplete"

    if identity == "eaa":
        grouped = group_eaa(rows)
        count = int(grouped.get("count") or 0)
        total = float(grouped["total_g"])
        aggregate_total = grouped.get("aggregate_total_g")
        if count < 6:
            return 0.0, "eaa_incomplete_under_6"
        if count < 9:
            if total < 5:
                return _partial(total, 5.0, 10.0), "eaa_partial_profile_under_5_g"
            if total < 8:
                return 10.0, "eaa_partial_profile_5_to_8_g"
            return 12.0, "eaa_partial_profile_at_least_8_g"
        if total < 5:
            return _partial(total, 5.0, 12.0), "eaa_under_5_g"
        if total < 8:
            return 14.0, (
                "eaa_complete_aggregate_5_to_8_g"
                if aggregate_total is not None
                else "eaa_5_to_8_g"
            )
        return 20.0, (
            "eaa_complete_aggregate_at_least_8_g"
            if aggregate_total is not None
            else "eaa_complete_at_least_8_g"
        )

    if identity == "alpha_gpc":
        mg = _max_mg(rows, ALPHA_GPC_CANONICALS)
        if mg is None:
            return 0.0, "alpha_gpc_no_dose"
        if mg < 300:
            return _partial(mg, 300.0, 8.0), "alpha_gpc_under_300_mg"
        if mg < 600:
            return 14.0, "alpha_gpc_300_to_600_mg"
        # 600 mg is the reviewed top dose band. Evidence certainty is scored in
        # Evidence, so it does not reduce otherwise adequate Dose credit here.
        return 20.0, "alpha_gpc_at_least_600_mg"

    if identity == "atp":
        mg = _max_mg(rows, ATP_CANONICALS)
        if mg is None:
            return 0.0, "atp_no_dose"
        if mg < 400:
            return _partial(mg, 400.0, 20.0), "atp_under_400_mg"
        # Dose V4.1 §2.2: evidence strength never caps Dose. Oral ATP's
        # weak-equivocal evidence (PMID 34957398) is the Evidence pillar's.
        return 20.0, "atp_at_least_400_mg"

    if identity == "caffeine":
        mg = _max_benchmark_amount(product, rows, CAFFEINE_CANONICALS, basis="per_use", unit="mg")
        if mg is None:
            return 0.0, "caffeine_no_dose"
        if mg < 150:
            return _partial(mg, 150.0, 8.0), "caffeine_under_150_mg"
        if mg < 200:
            return 14.0, "caffeine_150_to_200_mg"
        if mg <= 400:
            # 3-6 mg/kg (~200-400 mg) ergogenic (ISSN PMID 33388079; strong).
            return 18.0, "caffeine_200_to_400_mg"
        # Dose V4.1 D3: per-use adequacy plateaus; total daily caffeine is
        # judged once by the product-level dose-safety ceiling.
        return 18.0, "caffeine_above_400_mg"

    if identity == "betaine":
        grams = _max_g(rows, BETAINE_CANONICALS)
        if grams is None:
            return 0.0, "betaine_no_dose"
        if grams < 2.5:
            return _partial(grams, 2.5, 20.0), "betaine_under_2_5_g"
        # 2.5 g/day chronic for strength/power (PMC2915951). Dose V4.1 §2.2:
        # its moderate certainty is the Evidence pillar's, not a Dose cap.
        return 20.0, "betaine_at_least_2_5_g"

    if identity == "taurine":
        grams = _max_g(rows, TAURINE_CANONICALS)
        if grams is None:
            return 0.0, "taurine_no_dose"
        # Flat dose-response (PMID 40852891): adequacy plateaus at 1 g. Dose
        # V4.1 §2.2: its weak certainty is the Evidence pillar's, not a Dose cap.
        if grams < 1.0:
            return _partial(grams, 1.0, 20.0), "taurine_under_1_g"
        return 20.0, "taurine_at_least_1_g"

    return 0.0, "no_sports_primary_dose"


_IDENTITY_CANONICALS = (
    ("protein", SPORTS_PROTEIN_CANONICALS), ("creatine", CREATINE_CANONICALS),
    ("beta_alanine", BETA_ALANINE_CANONICALS), ("citrulline", CITRULLINE_CANONICALS),
    ("hmb", HMB_CANONICALS), ("alpha_gpc", ALPHA_GPC_CANONICALS), ("atp", ATP_CANONICALS),
    ("caffeine", CAFFEINE_CANONICALS), ("betaine", BETAINE_CANONICALS), ("taurine", TAURINE_CANONICALS),
)


def _co_primary_identities(product: Dict[str, Any]) -> list[str]:
    """Banded identities that are claim-prominent or mass-major on the label.

    Every sports active drives the route, so the shared role owner's
    materiality mode decides which of them are co-primaries.
    """
    rows = sports_identity_rows(product)
    roles = classify_ingredient_roles(product, module="sports", rows=rows, materiality_only=True)
    found = []
    for row, role in zip(rows, roles):
        if role.get("role") not in {"claim_prominent", "major"}:
            continue
        key = canonical(row)
        identity = next((name for name, canons in _IDENTITY_CANONICALS if key in canons), None)
        if identity and identity not in found:
            found.append(identity)
    return found


def _best_primary_score(product: Dict[str, Any]) -> Tuple[Optional[str], float, Optional[str], str, list]:
    """Score the product's sports primary (Dose V4.1 \u00a73.2).

    One banded primary from the shared role owner scores against its own
    benchmark; several co-primaries average. Without a role-owned banded
    primary, the dose-supported anchor with the highest credit is used, since
    a fixed canonical priority is unsafe for pre-workouts.
    """
    shared_primary = primary_sports_identity(product)
    co_primaries = [identity for identity in _co_primary_identities(product)
                    if identity != "protein" or shared_primary == "protein"]
    if len(co_primaries) > 1:
        scored = [(identity, *_score_primary(product, identity)) for identity in co_primaries]
        average = sum(score for _, score, _ in scored) / len(scored)
        lead = max(scored, key=lambda item: item[1])
        return lead[0], round(average, 4), lead[2], "co_primary_average", scored
    if co_primaries:
        score, basis = _score_primary(product, co_primaries[0])
        return co_primaries[0], score, basis, "single_primary", [(co_primaries[0], score, basis)]
    identity, score, basis = _strongest_primary_score(product, shared_primary)
    return identity, score, basis, "strongest_dosed_anchor", ([(identity, score, basis)] if identity else [])


def _strongest_primary_score(product: Dict[str, Any], shared_primary: Optional[str]) -> Tuple[Optional[str], float, Optional[str]]:
    best_identity: Optional[str] = None
    best_score = 0.0
    best_basis: Optional[str] = "no_sports_primary_dose"
    for identity in (
        "protein", "creatine", "bcaa", "eaa", "beta_alanine", "citrulline", "hmb",
        "alpha_gpc", "atp", "caffeine", "betaine", "taurine",
    ):
        # Protein's flat low-amount band must not compete when the shared
        # purpose owner identifies it as an incidental amino-mixture source.
        if identity == "protein" and shared_primary != "protein":
            continue
        score, basis = _score_primary(product, identity)
        if score > best_score:
            best_identity = identity
            best_score = score
            best_basis = basis
    if best_identity is None:
        fallback_identity = shared_primary
        if fallback_identity:
            _score, basis = _score_primary(product, fallback_identity)
            return fallback_identity, 0.0, basis
    return best_identity, best_score, best_basis


def _score_ratio_or_completeness(product: Dict[str, Any], identity: Optional[str]) -> float:
    rows = sports_rows(product)
    if identity == "bcaa" and _bcaa_ratio_is_close(group_bcaa(rows).get("ratio")):
        return 2.0
    if identity == "eaa" and group_eaa(rows)["complete"]:
        return 2.0
    return 0.0


def _not_evaluable_reason(product: Dict[str, Any], primary_score: float) -> Optional[str]:
    if primary_score > 0:
        return None
    blends = [b for b in _safe_list((product or {}).get("proprietary_blends")) if isinstance(b, dict)]
    if any(_norm_text(blend.get("disclosure_level")) in {"none", "partial", ""} for blend in blends):
        return "opaque_primary_sports_blend"
    return "no_sports_primary_dose"


def _max_benchmark_amount(product: Dict[str, Any], rows: list[Dict[str, Any]], canonicals: frozenset[str], *, basis: str, unit: str, top: bool = False) -> Optional[float]:
    exposures = [row_exposure(product, row, basis=basis, unit=unit)
                 for row in rows if canonical(row) in canonicals]
    values = [e.benchmark_maximum if top else e.benchmark_amount for e in exposures]
    values = [v for v in values if v is not None]
    return max(values) if values else None


def _daily_band(
    product: Dict[str, Any],
    rows: list[Dict[str, Any]],
    canonicals: frozenset[str],
    band: Callable[[float], Tuple[float, str]],
    no_dose: str,
) -> Tuple[float, str]:
    """Adequacy at the minimum directed daily use, the above-range reduction
    at the maximum: the lower of the two band scores (on a tie, the maximum's
    label, which names a loading peak that kept full credit)."""
    low = _max_benchmark_amount(product, rows, canonicals, basis="daily", unit="g")
    high = _max_benchmark_amount(product, rows, canonicals, basis="daily", unit="g", top=True)
    if low is None or high is None:
        return 0.0, no_dose
    return min(band(high), band(low), key=lambda scored: scored[0])


def _max_g(rows: list[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[float]:
    values = [dose_g(row) for row in rows if canonical(row) in canonicals]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _max_mg(rows: list[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[float]:
    values = [dose_mg(row) for row in rows if canonical(row) in canonicals]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _first_row(rows: list[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[Dict[str, Any]]:
    for row in rows:
        if canonical(row) in canonicals:
            return row
    return None


def _partial(value: float, target: float, max_points: float) -> float:
    if target <= 0:
        return 0.0
    return _clamp(0.0, max_points, (value / target) * max_points)


def _bcaa_ratio_is_close(ratio: Any) -> bool:
    if not ratio or len(ratio) != 3:
        return False
    leucine, iso, val = ratio
    return 1.7 <= float(leucine) <= 2.3 and 0.8 <= float(iso) <= 1.2 and 0.8 <= float(val) <= 1.2


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))
