from __future__ import annotations

import streamlit as st
import pandas as pd


def arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Make a display DataFrame serializable by Streamlit/pyarrow.

    Blob-derived tables (e.g. the Inspector's ingredient rows) have object
    columns with mixed types across products — `is_additive` is bool on some
    rows and absent (NaN) on others, other columns mix int/bool or carry
    lists/dicts. pyarrow then raises e.g. 'Expected integer, got bool' and
    Streamlit logs a traceback before falling back. Stringifying object columns
    (None/NaN -> "") sidesteps it entirely. Display-only; numeric/bool dtype
    columns are left untouched so they still render natively.
    """
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            def _cell(v):
                if v is None:
                    return ""
                if isinstance(v, float) and pd.isna(v):
                    return ""
                return v if isinstance(v, str) else str(v)
            out[col] = out[col].map(_cell)
    return out


def data_table(
    df: pd.DataFrame, 
    color_columns: dict[str, dict[str, str]] | None = None, 
    max_rows: int = 100,
    height: int = 360,
):
    """
    Styled DataFrame wrapper with row limit and conditional formatting.
    color_columns example: {"verdict": {"SAFE": "green", "BLOCKED": "red"}}
    """
    if df.empty:
        st.info("No records to display")
        return

    display_df = arrow_safe(df.head(max_rows))

    if len(df) > max_rows:
        st.caption(f"Showing top {max_rows} of {len(df)} results")
        
    def apply_style(val, column_styles):
        if val in column_styles:
            color = column_styles[val]
            return f'background-color: {color}; color: white; font-weight: bold'
        return ''

    styled_df = display_df.style
    
    if color_columns:
        for col, styles in color_columns.items():
            if col in display_df.columns:
                styled_df = styled_df.map(
                    lambda x: apply_style(x, styles),
                    subset=[col]
                )

    styled_df = styled_df.set_table_styles(
        [
            {
                'selector': 'th',
                'props': [
                    ('font-size', '0.92rem'),
                    ('padding', '0.75rem 0.9rem'),
                    ('background-color', '#f8fafc'),
                    ('color', '#334155'),
                ],
            },
            {
                'selector': 'td',
                'props': [
                    ('font-size', '0.88rem'),
                    ('padding', '0.65rem 0.9rem'),
                    ('color', '#334155'),
                ],
            },
        ]
    )
    st.dataframe(styled_df, width="stretch", height=height)
