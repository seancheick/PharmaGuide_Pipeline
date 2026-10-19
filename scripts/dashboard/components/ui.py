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


def empty_index_notice(command: str) -> None:
    st.warning("The dashboard index has not been built yet.", icon=":material/database:")
    st.code(command, language="bash")
    st.caption("The index is built from existing pipeline artifacts only; it never runs the pipeline or a scorer.")


def muted(text: str) -> None:
    st.markdown(f'<span style="color:{TOKENS["muted"]};font-size:0.85rem">{escape(text)}</span>',
                unsafe_allow_html=True)
