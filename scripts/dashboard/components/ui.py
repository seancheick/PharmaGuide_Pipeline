"""Shared UI pieces: plain-language state labels, pillar bars, KPI row, exportable tables.

Labels describe what the artifact recorded; they never re-derive a score.
"""

from __future__ import annotations

import io
from html import escape
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from scripts.dashboard.components.data_table import arrow_safe
from scripts.dashboard.components.theme import KIND_LABELS, PILLAR_COLORS, SEVERITY, TOKENS
from scripts.dashboard.score_index import PILLAR_LABELS, PILLARS

EVIDENCE_STATE_LABELS = {
    "evaluated_applicable": "assessed",
    "evaluated_authority": "assessed by authority reference",
    "authority_supported": "authority-supported",
    "evaluated_null": "reviewed — null result",
    "evaluated_unfavorable": "reviewed — unfavorable",
    "no_qualifying_human_evidence": "reviewed — no qualifying human evidence",
    "applicability_unestablished": "applicability not established",
    "research_present_applicability_unestablished": "research exists, applicability not established",
    "clinical_review_not_covered": "review incomplete — not yet covered",
    "native_research_review_incomplete": "review incomplete — native research",
    "human_clinical_evidence_unestablished": "review incomplete — human evidence unestablished",
    "identity_material_unresolved": "review incomplete — identity unresolved",
    "literature_resolution_required": "review incomplete — literature to resolve",
    "no_assessable_actives": "not applicable — no assessable actives",
    "not_efficacy_relevant": "not applicable — not efficacy-relevant",
}
DOSE_BASIS_LABELS = {
    "disclosed_no_reference": "no applicable dose benchmark",
    "limited_assessability_unbenchmarked_purpose": "purpose not benchmarked",
    "blend_total_only": "amount hidden in a blend",
    "completed_no_general_benchmark": "reviewed — no general benchmark",
    "partial_credit_without_rda_proxy": "partial credit — no RDA proxy",
    "partial_credit_primary_active_unassessed": "partial credit — primary active unassessed",
    "mixed_purpose_average": "mixed-purpose average",
}
STATUS_LABELS = {
    "scored": "Scored",
    "not_scored": "Not scored",
    "suppressed_safety": "Suppressed (safety)",
    "complete": "Complete",
    "partial": "Partial",
    "failed": "Failed",
    "no_known_catalog_concern": "No known concerns",
    "caution": "Caution",
    "blocked": "Blocked",
}


def human(value: Any, mapping: dict[str, str] | None = None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    text = str(value)
    return (mapping or STATUS_LABELS).get(text, text.replace("_", " "))


def _listish(value: Any) -> list:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return list(value)


def pillar_state(pillar: str, row: dict[str, Any]) -> str | None:
    """Why a pillar reads the way it does, from recorded state fields only."""
    neutral = set(_listish(row.get("neutral_only_pillars")))
    if pillar == "evidence":
        state = row.get("evidence_state")
        if isinstance(state, str) and state not in ("evaluated_applicable",):
            return EVIDENCE_STATE_LABELS.get(state, human(state))
        return None
    if pillar == "dose":
        if bool(row.get("dose_cap_applied")):
            nutrient = row.get("dose_cap_nutrient")
            pct = row.get("dose_cap_pct_ul")
            detail = f" ({nutrient} at {pct:.0f}% of its upper limit)" if isinstance(pct, (int, float)) and not pd.isna(pct) else ""
            return "capped by the Dose safety ceiling" + detail
        if "dose" in neutral:
            return "neutral — " + DOSE_BASIS_LABELS.get(str(row.get("dose_basis")), human(row.get("dose_basis")))
        return None
    if pillar == "verification":
        if bool(row.get("verification_fail_open")):
            return "neutral unknown — no verification evidence, not a failure"
        return None
    if pillar == "safety_hygiene" and "safety_hygiene" in neutral:
        return "catalog screen only — not personal safety"
    if pillar in neutral:
        return "neutral credit only"
    return None


def pillar_bars(row: dict[str, Any], maxima: dict[str, float]) -> None:
    """Six stateful bars; a value is never shown without its state."""
    html = []
    for pillar in PILLARS:
        score = row.get(f"pillar_{pillar}")
        mx = maxima.get(pillar, 1.0)
        pct = 0.0 if score is None or pd.isna(score) else max(0.0, min(100.0, float(score) / mx * 100))
        value = "—" if score is None or pd.isna(score) else f"{float(score):.1f} / {mx:g}"
        state = pillar_state(pillar, row)
        html.append(
            f'<div class="pg-pillar"><span>{escape(PILLAR_LABELS[pillar])}</span>'
            f'<div class="pg-track"><div class="pg-fill" style="width:{pct:.1f}%;background:{PILLAR_COLORS[pillar]}"></div></div>'
            f'<span style="text-align:right">{value}</span>'
            + (f'<span></span><span class="pg-state">{escape(state)}</span>' if state else "")
            + "</div>"
        )
    st.markdown("".join(html), unsafe_allow_html=True)


def chip(text: str, tone: str = "") -> str:
    return f'<span class="pg-chip {tone}">{escape(str(text))}</span>'


def chips(items: Iterable[tuple[str, str]]) -> None:
    st.markdown("".join(chip(text, tone) for text, tone in items), unsafe_allow_html=True)


def page_header(title: str, subtitle: str, eyebrow: str | None = None) -> None:
    if eyebrow:
        st.markdown(f'<div class="pg-eyebrow">{escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="pg-sub">{escape(subtitle)}</div>', unsafe_allow_html=True)


def kpis(items: list[tuple[str, Any, str | None]], per_row: int = 5) -> None:
    """Metric tiles, at most ``per_row`` per row so values never truncate."""
    for start in range(0, len(items), per_row):
        chunk = items[start:start + per_row]
        columns = st.columns(per_row if len(items) > per_row else len(chunk))
        for column, (label, value, help_text) in zip(columns, chunk):
            column.metric(label, value, help=help_text, border=True)


def severity_tone(severity: str) -> str:
    return severity if severity in SEVERITY else ""


def pillar_column_config(maxima: dict[str, float]) -> dict[str, Any]:
    return {
        f"pillar_{p}": st.column_config.ProgressColumn(
            PILLAR_LABELS[p], min_value=0.0, max_value=float(maxima.get(p, 20)), format="%.1f",
            help=f"{PILLAR_LABELS[p]} points out of {maxima.get(p, 20):g}",
        )
        for p in PILLARS
    }


def export_buttons(frame: pd.DataFrame, *, name: str, run_key: str | None, key: str) -> None:
    stamp = f"{name}__{run_key or 'norun'}"
    left, right, _ = st.columns([1, 1, 6])
    left.download_button("CSV", frame.to_csv(index=False).encode(), file_name=f"{stamp}.csv",
                         mime="text/csv", key=f"{key}-csv", width="stretch")
    buffer = io.BytesIO()
    _parquet_safe(frame).to_parquet(buffer, index=False)
    right.download_button("Parquet", buffer.getvalue(), file_name=f"{stamp}.parquet",
                          mime="application/octet-stream", key=f"{key}-pq", width="stretch")


def _parquet_safe(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if out[column].dtype == object and out[column].map(lambda v: isinstance(v, (dict, set))).any():
            out[column] = out[column].map(lambda v: str(v) if isinstance(v, (dict, set)) else v)
    return out


def table(frame: pd.DataFrame, *, key: str, name: str, run_key: str | None = None,
          column_config: dict | None = None, height: int = 420, select: bool = False,
          caption: str | None = None) -> list[int]:
    """Every table is exportable (CSV/Parquet, stamped with the run key). Returns selected rows."""
    if frame.empty:
        st.info("No products match.")
        return []
    if caption:
        st.caption(caption)
    display = frame.copy()
    display.columns = [str(column) for column in display.columns]  # a NaN label breaks Arrow in the browser
    for column in display.columns:  # list columns render as text, numbers stay numeric
        if display[column].map(lambda v: isinstance(v, (list, tuple)) or hasattr(v, "tolist")).any():
            display[column] = display[column].map(lambda v: ", ".join(map(str, list(v))) if v is not None and not isinstance(v, (str, float)) else v)
    display = arrow_safe(display)
    event = st.dataframe(
        display, key=key, hide_index=True, height=min(height, 40 + 35 * len(display)), width="stretch",
        column_config=column_config or {},
        on_select="rerun" if select else "ignore",
        selection_mode="single-row" if select else "multi-row",
    )
    export_buttons(frame, name=name, run_key=run_key, key=key)
    if select and event is not None:
        try:
            return list(event.selection.rows)
        except AttributeError:
            return []
    return []


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, human(kind))


# Plain names for receipt entry ids (the scorer's component keys). Display only; the id is always shown beside it.
RECEIPT_LABELS = {
    "A1_bio_score": "Ingredient form quality (absorption)",
    "A1_unrated_neutral": "Baseline for forms with no quality rating",
    "A3_delivery_system": "Delivery system",
    "A4_absorption_enhancer": "Absorption enhancer",
    "A5b_standardized_botanical": "Standardized botanical extract",
    "panel_form_quality": "Form quality across the nutrient panel",
    "b_form_quality": "B-vitamin form quality",
    "form_tier": "Ingredient form quality",
    "epa_dha_concentration": "EPA/DHA concentration",
    "sports_protein_source_quality": "Protein source quality",
    "fiber_source_quality": "Fiber source quality",
    "recognized_botanical_identity": "Recognized botanical identity",
    "extract_not_whole_herb": "Extract rather than whole herb",
    "marker_standardization_declared": "Standardization marker declared",
    "weak_or_unidentified_botanical": "Weak or unidentified botanical",
    "recognized_collagen_identity": "Recognized collagen identity",
    "hydrolyzed_peptides": "Hydrolyzed collagen peptides",
    "supplemental_window_proxy": "Doses within the supplemental range",
    "botanical_clinical_dose": "Botanical at a studied dose",
    "collagen_clinical_dose": "Collagen at a studied dose",
    "joint_support_dose": "Joint actives at studied doses",
    "sleep_support_dose": "Sleep actives at studied doses",
    "rda_ai_coverage": "Nutrients meeting the RDA/AI",
    "critical_nutrient_coverage": "Critical nutrients covered",
    "prenatal_complement_support": "Prenatal nutrients covered",
    "b_rda_ai_coverage": "B vitamins meeting the RDA/AI",
    "epa_dha_band": "EPA/DHA daily amount",
    "cfu_adequacy": "Probiotic count (CFU) adequate",
    "studied_formula_dose_adequacy": "Studied formula at its studied dose",
    "sports_primary_active_dose": "Main sports active at an effective dose",
    "sports_ratio_or_completeness": "Sports formula ratio or completeness",
    "fiber_effective_dose": "Fiber at an effective dose",
    "vitamin_c_daily_range": "Vitamin C daily amount",
    "vitamin_d_daily_range": "Vitamin D daily amount",
    "zinc_daily_range": "Zinc daily amount",
    "copper_balance": "Copper balanced against zinc",
    "selenium_daily_range": "Selenium daily amount",
    "beta_glucan_disclosed": "Beta-glucan amount disclosed",
    "quercetin_disclosed": "Quercetin amount disclosed",
    "elderberry_disclosed": "Elderberry amount disclosed",
    "daily_use_discipline": "Daily-use dosing baseline",
    "dose_safety_ceiling": "Dose safety cap (over the upper limit)",
    "clinical_evidence_pipeline": "Clinical evidence for the actives",
    "depth_bonus": "Depth of the evidence",
    "evidence_family_certainty": "Certainty of the evidence",
    "product_applicability": "Evidence matches this product's dose and form",
    "independent_replication_consistency": "Independent, consistent replication",
    "clinical_evidence": "Clinical evidence",
    "essential_panel_authority": "Essential nutrients backed by an authority reference",
    "b_nutrient_authority_panel": "B vitamins backed by an authority reference",
    "primary_evidence_floor": "Minimum for the primary evidence",
    "immune_support_evidence_cap": "Immune-support evidence cap",
    "joint_support_evidence_cap": "Joint-support evidence cap",
    "clear_disclosure_base": "Starting points for a clear label",
    "complete_active_identity_dose_disclosure": "Every active named with its amount",
    "B3_claim_compliance": "Claims stay within allowed wording",
    "hypoallergenic_bonus": "Allergen-free claim supported",
    "panel_identity_disclosure": "Panel ingredients identified",
    "panel_individual_dose_disclosure": "Panel amounts listed individually",
    "strain_identities_named": "Probiotic strains named",
    "per_strain_cfu_on_label": "CFU listed per strain",
    "aggregate_cfu_disclosure_proxy": "Total CFU disclosed",
    "aggregate_native_afu_disclosure": "Total AFU disclosed",
    "epa_or_dha_disclosed": "EPA or DHA amount disclosed",
    "form_disclosed": "Ingredient form disclosed",
    "source_disclosed": "Source disclosed",
    "B2_false_allergen_free_claim": "Unsupported allergen-free claim",
    "B5_proprietary_blend_opacity": "Amounts hidden in a proprietary blend",
    "B6_marketing_claims": "Marketing claims",
    "immune_high_variability_botanical_stack": "Highly variable botanical stack",
    "sports_amino_spiking_risk": "Amino-spiking risk",
    "sports_collagen_not_complete_protein": "Collagen counted as complete protein",
    "neutral_baseline": "Starting points",
    "cert": "Third-party certification",
    "coa_batch": "Batch certificate of analysis",
    "gmp": "GMP manufacturing",
    "brand_testing": "Brand-reported testing",
    "brand_only_cert": "Brand-only certification",
    "reputation": "Manufacturer reputation",
    "product_level_floor": "Minimum for product-level certification",
    "manufacturing_ceiling": "Cap for manufacturing-level evidence only",
    "claim_or_brand_ceiling": "Cap for claim- or brand-level evidence only",
    "verification_cap": "Verification maximum",
    "quality_system_violation_penalty": "Manufacturer quality-system violation",
    "verification_floor": "Verification minimum",
    "catalog_screen": "Starting points (catalog screen)",
    "class_i_recall_penalty": "Class I recall",
    "clean_label_penalty": "Clean-label issues",
    "additive_or_sweetener_penalty": "Additives or sweeteners",
    "safety_hygiene_floor": "Formula-checks minimum",
    "rounding": "Rounded to one decimal",
}


def receipt_label(entry_id: Any) -> str:
    """Plain name of one receipt line; unknown ids fall back to a readable form of the id."""
    text = str(entry_id)
    if text in RECEIPT_LABELS:
        return RECEIPT_LABELS[text]
    for suffix, template in (("_unrated_neutral", "{} — baseline for unrated forms"), ("_pillar_bounds", "{} pillar limit"),
                             ("_bounds", "{} limit"), ("_not_evaluable", "{} not evaluable")):
        if text.endswith(suffix):
            stem = text[: -len(suffix)]
            return template.format(RECEIPT_LABELS.get(stem, stem.replace("_", " ").capitalize()))
    return text.replace("_", " ").capitalize()


def empty_index_notice(command: str) -> None:
    st.warning("The dashboard index has not been built yet.", icon=":material/database:")
    st.code(command, language="bash")
    st.caption("The index is built from existing pipeline artifacts only; it never runs the pipeline or a scorer.")


def muted(text: str) -> None:
    st.markdown(f'<span style="color:{TOKENS["muted"]};font-size:0.85rem">{escape(text)}</span>',
                unsafe_allow_html=True)
