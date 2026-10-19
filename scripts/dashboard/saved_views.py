"""Product Explorer filters and saved audit views (pure pandas, no Streamlit).

Saved views are audit STATES ("show me every product with this condition"), not
anomalies; anomalies live in findings_rules. Every filter reads an indexed column.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from scripts.dashboard.score_index import PILLARS

EPS = 0.05
# realized and nominal deductions each carry a 0.1-grid rounding residue (findings_rules.REALIZED_TOL)
ABSORB_MIN = 0.11
UNRATED_FORM_ENTRIES = ("A1_unrated_neutral", "panel_form_quality_unrated_neutral")

SAVED_VIEWS: dict[str, dict[str, Any]] = {
    "Evidence = 0 (all states)": {"pillar_zero": ["evidence"]},
    "Evidence applicability gaps": {"evidence_state": ["applicability_unestablished",
                                                       "research_present_applicability_unestablished"]},
    "Evidence review incomplete": {"evidence_state": ["clinical_review_not_covered", "native_research_review_incomplete",
                                                      "human_clinical_evidence_unestablished",
                                                      "identity_material_unresolved", "literature_resolution_required"]},
    "Evidence reviewed — no qualifying evidence / null": {"evidence_state": ["no_qualifying_human_evidence",
                                                                            "evaluated_null", "evaluated_unfavorable"]},
    "Dose neutral": {"pillar_neutral": ["dose"]},
    "Dose capped by safety ceiling": {"dose_cap": True},
    "Dose ceiling evaluated (over a limit)": {"dose_ceiling_present": True},
    "Verification unknown (neutral 6)": {"verification_fail_open": True},
    "No product-level certification": {"product_cert": False, "quality_score_status": ["scored"]},
    "Formula checks below 10": {"pillar_range": {"safety_hygiene": (None, 10 - EPS)}},
    "Unrated forms": {"entry_ids": list(UNRATED_FORM_ENTRIES)},
    "High score, low confidence": {"score_min": 70, "confidence": ["low"]},  # whole-number shipped score
    "Partial products in rankings": {"quality_score_status": ["scored"], "quality_assessment_status": ["partial"]},
    "Floors absorbing deductions": {"absorbed_min": ABSORB_MIN, "has_floor": True},
    "Has a cap": {"has_cap": True},
    "Tier changed vs baseline": {"flag": "tier_changed"},
    "Candidate ≠ release": {"flag": "differs_from_release"},
    "Unexplained score movers": {"flag": "unexplained"},
    "Suppressed or not scored": {"quality_score_status": ["suppressed_safety", "not_scored"]},
    "Unmapped actives": {"unmapped": True},
    "Low route confidence": {"route_confidence": ["low"]},
}

_LIST_COLUMNS = ("tier", "quality_score_status", "quality_assessment_status", "product_safety_status", "confidence",
                 "route_confidence", "module", "category", "brand_name", "evidence_state", "evidence_display_state",
                 "dose_basis", "verification_tier", "config_version")


def _contains(series: pd.Series, item: str) -> pd.Series:
    return series.map(lambda value: item in list(value) if value is not None and not isinstance(value, float) else False)


def apply_filters(frame: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """Return the rows matching every key in ``spec``. Unknown keys raise (no silent no-op)."""
    if frame.empty or not spec:
        return frame
    mask = pd.Series(True, index=frame.index)
    for key, value in spec.items():
        if value is None or value == [] or value == "":
            continue
        if key in _LIST_COLUMNS:
            mask &= frame[key].isin(list(value))
        elif key == "score_min":  # thresholds compare the shipped whole number, like the tiers
            mask &= frame["shipped_total"] >= value
        elif key == "score_max":
            mask &= frame["shipped_total"] <= value
        elif key == "pillar_range":
            for pillar, (lo, hi) in value.items():
                column = frame[f"pillar_{pillar}"]
                if lo is not None:
                    mask &= column >= lo
                if hi is not None:
                    mask &= column <= hi
        elif key == "pillar_zero":
            for pillar in value:
                mask &= frame[f"pillar_{pillar}"].abs() < EPS
        elif key == "pillar_at_max":
            for pillar, maximum in value.items():
                mask &= frame[f"pillar_{pillar}"] >= maximum - EPS
        elif key == "pillar_neutral":
            for pillar in value:
                mask &= _contains(frame["neutral_only_pillars"], pillar)
        elif key == "high_total_low_pillar":
            maxima = value
            low = pd.Series(False, index=frame.index)
            for pillar in PILLARS:
                low |= frame[f"pillar_{pillar}"] <= 0.25 * maxima[pillar]
            mask &= (frame["shipped_total"] >= 70) & low
        elif key == "dose_cap":
            mask &= frame["dose_cap_applied"].fillna(False).astype(bool) == bool(value)
        elif key == "dose_ceiling_present":
            mask &= frame["dose_ceiling_present"].fillna(False).astype(bool) == bool(value)
        elif key == "verification_fail_open":
            mask &= frame["verification_fail_open"].fillna(False).astype(bool) == bool(value)
        elif key == "product_cert":
            has = frame["verification_cert"].fillna(0) > EPS
            mask &= has if value else ~has
        elif key in ("has_deduction", "has_cap", "has_floor", "has_neutral"):
            mask &= frame[key].fillna(False).astype(bool) == bool(value)
        elif key == "unawarded_min":
            mask &= frame["unawarded_total"] >= value
        elif key == "absorbed_min":
            mask &= frame["absorbed_points"] >= value
        elif key == "fully_absorbed":
            mask &= frame["has_deduction"].fillna(False).astype(bool) & (frame["realized_deductions"].abs() < EPS) \
                & (frame["nominal_deductions"] < -ABSORB_MIN)
        elif key == "entry_ids":
            hit = pd.Series(False, index=frame.index)
            for entry in value:
                hit |= _contains(frame["receipt_entry_ids"], entry)
            mask &= hit
        elif key == "unmapped":
            mask &= (frame["unmapped_actives_total"].fillna(0) > 0) == bool(value)
        elif key == "missing_provenance":
            mask &= frame["config_fingerprint"].isna() == bool(value)
        elif key == "flag":
            mask &= frame[value].fillna(False).astype(bool) if value in frame else False
        elif key == "search":
            text = str(value).strip().lower()
            mask &= (frame["dsld_id"].astype(str).str.lower() == text) \
                | frame["product_name"].fillna("").str.lower().str.contains(text, regex=False) \
                | frame["brand_name"].fillna("").str.lower().str.contains(text, regex=False)
        else:
            raise KeyError(f"unknown explorer filter {key!r}")
    return frame[mask]


def attach_comparison(frame: pd.DataFrame, deltas: pd.DataFrame | None, *, release: pd.DataFrame | None) -> pd.DataFrame:
    """Add the flag columns saved views use (release diff, tier change, unexplained)."""
    out = frame.copy()
    out["differs_from_release"] = False
    out["release_total"] = None
    if release is not None and not release.empty:
        rel = release.set_index("dsld_id")[["total", "tier", "product_safety_status"]].rename(
            columns={"total": "release_total", "tier": "release_tier", "product_safety_status": "release_safety"})
        out = out.drop(columns=["release_total"]).join(rel, on="dsld_id")
        out["differs_from_release"] = (
            # release ships a whole number via the scorer's rounding rule; compare like with like
            (out["shipped_total"].fillna(-1) != out["release_total"].fillna(-1))
            | (out["product_safety_status"].fillna("") != out["release_safety"].fillna(""))
        ) & out["release_safety"].notna()
    out["tier_changed"] = False
    out["unexplained"] = False
    if deltas is not None and not deltas.empty:
        flags = deltas.set_index("dsld_id")[["tier_crossed", "explained"]]
        out = out.join(flags, on="dsld_id")
        out["tier_changed"] = out["tier_crossed"].fillna(False).astype(bool)
        out["unexplained"] = ~out["explained"].fillna(True).astype(bool)
        out = out.drop(columns=["tier_crossed", "explained"])
    return out
